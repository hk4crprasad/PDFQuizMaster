import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import List, Dict, Any
import tempfile
import logging
from utils.pdf_processor import extract_text_from_pdf
from utils.question_generator import generate_questions

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="PDF Test Generator API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "PDF Test Generator API is running"}

@app.post("/process_pdf")
async def process_pdf(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Process a PDF file and generate questions.
    
    Args:
        file: The uploaded PDF file
        
    Returns:
        Dictionary with generated questions and metadata
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    try:
        # Save the uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name
        
        # Extract text from PDF
        logger.info(f"Extracting text from {file.filename}")
        text, title = extract_text_from_pdf(temp_file_path)
        
        # Clean up temp file
        os.unlink(temp_file_path)
        
        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF")
        
        # Generate questions using LangChain and Azure OpenAI
        logger.info("Generating questions")
        questions = generate_questions(text)
        
        return {
            "title": title or file.filename,
            "questions": questions
        }
    
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
