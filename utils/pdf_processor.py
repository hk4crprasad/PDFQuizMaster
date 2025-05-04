import PyPDF2
import re
import os
import logging
import tempfile
import subprocess
import threading
import time
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Azure Document Intelligence imports
from pypdf import PdfReader, PdfWriter
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

# Set up logging
logger = logging.getLogger(__name__)

# Global variable to store PDF processing status
processing_status = {}

# Azure Document Intelligence configuration from environment variables
AZURE_ENDPOINT = os.environ.get("AZURE_DOC_ENDPOINT")
AZURE_KEY = os.environ.get("AZURE_DOC_KEY")
AZURE_CHUNK_SIZE = int(os.environ.get("AZURE_CHUNK_SIZE", "6"))  # pages per split - Azure has limits on document size

def extract_text_from_pdf(pdf_path: str, pdf_id: str = None, use_azure_ocr: bool = False) -> Tuple[str, Optional[str]]:
    """
    Extract text and title from a PDF file.
    If standard text extraction fails or returns minimal text, OCR is used.
    
    Args:
        pdf_path: Path to the PDF file
        pdf_id: Unique ID for tracking processing status
        use_azure_ocr: Whether to use Azure Document Intelligence for OCR processing
        
    Returns:
        Tuple of (extracted_text, title)
    """
    try:
        # Initialize processing status if pdf_id provided
        if pdf_id:
            processing_status[pdf_id] = {
                'step': 1,
                'progress': 10,
                'status': 'Extracting text from PDF',
                'complete': False
            }
        
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Try to extract title from document info
            title = None
            if reader.metadata and hasattr(reader.metadata, 'title') and reader.metadata.title:
                title = reader.metadata.title
            
            # Extract text from all pages using PyPDF2
            text = ""
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                
                # Update progress if pdf_id provided
                if pdf_id:
                    progress = min(30, 10 + int(20 * (page_num + 1) / len(reader.pages)))
                    processing_status[pdf_id]['progress'] = progress
            
            # If pdf_id provided, update status
            if pdf_id:
                processing_status[pdf_id]['step'] = 2
                processing_status[pdf_id]['status'] = 'Analyzing text quality'
            
            # Check if text extraction was successful
            has_sufficient_text = len(text.strip()) >= 100
            
            # Only use OCR if text extraction yielded very little text (likely scanned PDF) or if Azure OCR is requested
            if not has_sufficient_text or use_azure_ocr:
                if use_azure_ocr:
                    logger.info("Using Azure Document Intelligence for OCR processing...")
                    if pdf_id:
                        processing_status[pdf_id]['status'] = 'Running Azure Document Intelligence OCR'
                        processing_status[pdf_id]['progress'] = 35
                    
                    # Run Azure OCR
                    azure_text = extract_text_with_azure_ocr(pdf_path, pdf_id)
                    if azure_text:
                        text = azure_text
                        if pdf_id:
                            processing_status[pdf_id]['progress'] = 65
                            processing_status[pdf_id]['ocr_complete'] = True
                    else:
                        logger.warning("Azure OCR failed. Falling back to local OCR methods.")
                        # Fall back to regular OCR methods
                
                if not use_azure_ocr or not azure_text:
                    logger.info("Using advanced OCR processing due to insufficient text...")
                    
                    # Run OCR in a separate thread if tracking status
                    if pdf_id:
                        thread = threading.Thread(target=process_with_ocrmypdf, args=(pdf_path, pdf_id))
                        thread.daemon = True
                        thread.start()
                        
                        # Wait for OCR to complete or timeout after 5 minutes
                        start_time = time.time()
                        while time.time() - start_time < 300:  # 5 minutes timeout
                            if processing_status[pdf_id].get('ocr_complete', False):
                                break
                            time.sleep(1)
                        
                        # Use OCR output if available, otherwise fallback to original text
                        ocr_path = f"{pdf_path}_ocr.pdf"
                        if os.path.exists(ocr_path):
                            ocr_text = extract_text_from_ocr_pdf(ocr_path)
                            if ocr_text:
                                text = ocr_text
                    else:
                        # Synchronous OCR for non-tracked PDFs
                        ocr_text = extract_text_with_ocr(pdf_path)
                        if ocr_text:
                            text = ocr_text
            else:
                # Skip OCR for PDFs with sufficient extractable text
                logger.info("PDF contains sufficient extractable text. Skipping OCR processing.")
                if pdf_id:
                    processing_status[pdf_id]['progress'] = 65
                    processing_status[pdf_id]['status'] = 'Text extraction successful. Proceeding with analysis.'
                    processing_status[pdf_id]['ocr_complete'] = True
            
            # If no title was found in metadata, try to extract from first page
            if not title:
                # Simple heuristic: first line of text might be the title
                first_lines = text.strip().split('\n', 3)
                if first_lines and len(first_lines[0]) < 100:  # Assume titles aren't too long
                    title = first_lines[0].strip()
            
            # Clean up the text
            text = clean_text(text)
            
            # Update status if pdf_id provided
            if pdf_id:
                processing_status[pdf_id]['step'] = 3
                processing_status[pdf_id]['progress'] = 70
                processing_status[pdf_id]['status'] = 'Generating questions'
            
            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return text, title
            
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        
        # Update status if pdf_id provided
        if pdf_id:
            processing_status[pdf_id]['status'] = f"Error: {str(e)}"
        
        return "", None

def extract_text_with_azure_ocr(pdf_path: str, pdf_id: str = None) -> str:
    """
    Extract text from a PDF using Azure Document Intelligence (formerly Form Recognizer).
    This method splits large PDFs into chunks to handle Azure's size limits.
    
    Args:
        pdf_path: Path to the PDF file
        pdf_id: Optional tracking ID for status updates
        
    Returns:
        Extracted text as string
    """
    try:
        logger.info(f"Starting Azure Document Intelligence OCR for {pdf_path}")
        
        # Create a chunks directory if it doesn't exist
        os.makedirs("chunks", exist_ok=True)
        
        # Read the PDF
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        if pdf_id:
            processing_status[pdf_id]['status'] = f'Splitting PDF into chunks for Azure OCR ({total_pages} pages)'
        
        # Split into chunks to handle Azure's size limits
        chunk_paths = []
        for i in range(0, total_pages, AZURE_CHUNK_SIZE):
            writer = PdfWriter()
            
            # Add pages to this chunk
            for p in range(i, min(i + AZURE_CHUNK_SIZE, total_pages)):
                writer.add_page(reader.pages[p])
                
            # Generate unique chunk filename
            chunk_filename = f"chunks/chunk_{i//AZURE_CHUNK_SIZE + 1}_{os.path.basename(pdf_path)}.pdf"
            with open(chunk_filename, "wb") as out_f:
                writer.write(out_f)
            chunk_paths.append(chunk_filename)
            
        logger.info(f"Split PDF into {len(chunk_paths)} chunks for Azure processing")
        
        # Initialize Azure client
        client = DocumentAnalysisClient(
            endpoint=AZURE_ENDPOINT, 
            credential=AzureKeyCredential(AZURE_KEY)
        )
        
        # Process each chunk with Azure
        all_text = []
        for idx, chunk_file in enumerate(chunk_paths):
            if pdf_id:
                progress = 35 + min(30, int(30 * idx / len(chunk_paths)))
                processing_status[pdf_id]['progress'] = progress
                processing_status[pdf_id]['status'] = f'OCR processing chunk {idx+1}/{len(chunk_paths)}'
                
            logger.info(f"OCR processing chunk {idx+1}/{len(chunk_paths)}: {chunk_file}")
            
            try:
                with open(chunk_file, "rb") as fd:
                    poller = client.begin_analyze_document("prebuilt-read", document=fd)
                result = poller.result()
                
                for page in result.pages:
                    for line in page.lines:
                        all_text.append(line.content)
            except Exception as chunk_error:
                logger.error(f"Error processing chunk {idx+1}: {str(chunk_error)}")
                # Continue with next chunk even if one fails
                
        # Clean up chunk files
        for chunk_file in chunk_paths:
            try:
                if os.path.exists(chunk_file):
                    os.remove(chunk_file)
            except Exception as e:
                logger.warning(f"Could not remove chunk file {chunk_file}: {str(e)}")
                
        # Combine all text
        full_text = "\n".join(all_text)
        
        logger.info(f"Azure OCR completed successfully, extracted {len(full_text)} characters")
        return full_text
        
    except Exception as e:
        logger.error(f"Error performing Azure OCR on PDF: {str(e)}")
        return ""

def process_with_ocrmypdf(pdf_path: str, pdf_id: str) -> None:
    """
    Process PDF with ocrmypdf for better OCR results.
    
    Args:
        pdf_path: Path to the PDF file
        pdf_id: Unique ID for tracking processing status
    """
    try:
        # Update status
        processing_status[pdf_id]['status'] = 'Running advanced OCR with ocrmypdf'
        processing_status[pdf_id]['progress'] = 35
        
        # Output path for OCR'd PDF
        output_path = f"{pdf_path}_ocr.pdf"
        
        # Run ocrmypdf command
        cmd = ['ocrmypdf', pdf_path, output_path]
        logger.info(f"Running OCR command: {' '.join(cmd)}")
        
        # Execute ocrmypdf
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Process output
        total_pages = 0
        processed_pages = 0
        
        for line in process.stdout:
            logger.info(f"OCRMYPDF: {line.strip()}")
            
            # Try to parse progress information
            if 'Scanning contents:' in line:
                pages_match = re.search(r'(\d+)/(\d+)', line)
                if pages_match:
                    processed_pages = int(pages_match.group(1))
                    total_pages = int(pages_match.group(2))
                    
            # Update progress based on processed pages
            if total_pages > 0:
                progress = 35 + min(30, int(30 * processed_pages / total_pages))
                processing_status[pdf_id]['progress'] = progress
        
        # Wait for process to complete
        process.wait()
        
        # Check if successful
        if process.returncode == 0:
            logger.info(f"ocrmypdf completed successfully: {output_path}")
            processing_status[pdf_id]['progress'] = 65
        else:
            error_output = process.stderr.read()
            logger.error(f"ocrmypdf failed: {error_output}")
            
            # Fallback to regular OCR if ocrmypdf fails
            logger.info("Falling back to regular OCR")
            extract_text_with_ocr(pdf_path)
        
        # Mark OCR as complete
        processing_status[pdf_id]['ocr_complete'] = True
        
    except Exception as e:
        logger.error(f"Error in ocrmypdf processing: {str(e)}")
        processing_status[pdf_id]['ocr_complete'] = True
        
        # Fallback to regular OCR if ocrmypdf fails
        extract_text_with_ocr(pdf_path)

def extract_text_from_ocr_pdf(ocr_pdf_path: str) -> str:
    """
    Extract text from a PDF that has already been processed with OCR.
    
    Args:
        ocr_pdf_path: Path to the OCR'd PDF file
        
    Returns:
        Extracted text as string
    """
    try:
        with open(ocr_pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Extract text from all pages
            text = ""
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
            
            return text
            
    except Exception as e:
        logger.error(f"Error extracting text from OCR'd PDF: {str(e)}")
        return ""

def extract_text_with_ocr(pdf_path: str) -> str:
    """
    Extract text from a PDF using OCR (for scanned documents).
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as string
    """
    try:
        logger.info(f"Starting OCR processing for {pdf_path}")
        
        # Create a temporary directory for the images
        with tempfile.TemporaryDirectory() as temp_dir:
            # Convert PDF pages to images
            images = convert_from_path(pdf_path, dpi=300)
            logger.info(f"Converted PDF to {len(images)} images")
            
            # Process each image with OCR
            text = ""
            for i, image in enumerate(images):
                # Save the image temporarily
                image_path = os.path.join(temp_dir, f'page_{i}.png')
                image.save(image_path, 'PNG')
                
                # Extract text with pytesseract
                page_text = pytesseract.image_to_string(Image.open(image_path))
                text += page_text + "\n"
                
                # Log progress for longer documents
                if i > 0 and i % 5 == 0:
                    logger.info(f"OCR processed {i}/{len(images)} pages")
                
            logger.info(f"OCR completed successfully, extracted {len(text)} characters")
            return text
            
    except Exception as e:
        logger.error(f"Error performing OCR on PDF: {str(e)}")
        return ""

def clean_text(text: str) -> str:
    """
    Clean up extracted PDF text.
    
    Args:
        text: Raw text extracted from PDF
        
    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove page numbers (common formats)
    text = re.sub(r'\s+\d+\s+of\s+\d+\s+', ' ', text)
    text = re.sub(r'\s+Page\s+\d+\s+', ' ', text)
    
    # Remove headers/footers that might repeat on every page
    # This is a simplified approach - real-world PDFs might need more sophisticated cleaning
    
    # Remove unicode control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    return text.strip()
