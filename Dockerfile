# Use Python 3.10 as the base image
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install system dependencies required for PDF processing and OCR
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    ghostscript \
    poppler-utils \
    libmagic1 \
    qpdf \
    pkg-config \
    libpng-dev \
    libjpeg-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Make sure pip is up to date first
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create upload folder
RUN mkdir -p uploads && chmod 777 uploads

# Expose port 5000
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=main.py
ENV PYTHONUNBUFFERED=1

# Run gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--reuse-port", "--reload", "main:app"]