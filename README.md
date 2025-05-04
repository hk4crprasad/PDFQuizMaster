# PDFQuizMaster

PDFQuizMaster is a web application that automatically generates multiple-choice tests from PDF documents. The application extracts text from PDFs (using OCR for scanned documents) and creates comprehensive tests with detailed analytics and performance tracking.

![PDFQuizMaster](static/img/logo.svg)

## Features

- **PDF Processing**: Upload and process PDFs up to 32MB in size
- **OCR Support**: Process scanned PDFs using advanced OCR technology
- **Azure Integration**: Option to use Azure Document Intelligence for superior OCR quality
- **Test Generation**: Automatically create 120 multiple-choice questions from any PDF
- **Interactive Tests**: Timed tests with progress tracking and navigation
- **Performance Analytics**: Track progress, view statistics, and earn achievements
- **User Profiles**: Create accounts to track progress across multiple tests
- **Responsive Design**: Works on desktop and mobile devices

## Technology Stack

- **Backend**: Flask (Python)
- **Database**: MongoDB (with GridFS for file storage)
- **OCR**: PyTesseract, OCRmyPDF, Azure Document Intelligence
- **Frontend**: HTML, CSS (Bootstrap), JavaScript
- **Authentication**: Flask-Login
- **Processing**: Background task processing for file handling

## Prerequisites

- Python 3.8+
- MongoDB database
- OCR dependencies (Tesseract, OCRmyPDF)
- Azure account (optional, for enhanced OCR)

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd PDFQuizMaster
   ```

2. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Install OCR dependencies (on Ubuntu/Debian):
   ```
   apt-get update
   apt-get install -y tesseract-ocr ocrmypdf
   ```

4. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file and add your credentials:
   - MongoDB connection string
   - Azure Document Intelligence credentials (optional)
   - Azure OpenAI credentials (optional)
   - Flask secret key

## Usage

1. Start the application:
   ```
   python main.py
   ```

2. Open a web browser and navigate to `http://localhost:5000`

3. Create an account or log in

4. Upload a PDF document and select OCR method:
   - Auto-detect (default): Uses OCR only if needed
   - Local OCR: Uses local OCR tools
   - Azure OCR: Uses Azure Document Intelligence for better results with complex documents

5. Wait for processing to complete (varies based on PDF size and complexity)

6. Take the generated test with 120 multiple-choice questions and a 60-minute time limit

7. View your results and track your progress in your profile

## PDF Requirements

- Supported format: PDF only
- Maximum file size: 32MB
- Both text and scanned PDFs are supported

## Azure Integration (Optional)

For better OCR results with complex scanned documents, you can configure Azure Document Intelligence (formerly Form Recognizer):

1. Create an Azure Document Intelligence resource
2. Add your Azure endpoint and key to the `.env` file
3. Select "Azure OCR" when uploading scanned PDFs

## Project Structure

- `/static` - Static assets (CSS, JavaScript, images)
- `/templates` - HTML templates
- `/uploads` - Temporary storage for PDF uploads
- `/utils` - Utility modules for PDF processing and question generation
- `/auth` - Authentication routes and utilities

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.