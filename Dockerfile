# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libsndfile1 \
    portaudio19-dev \
    python3-dev \
    tesseract-ocr \
    tesseract-ocr-ita \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements_official.txt .

# Install Python dependencies
RUN pip install -r requirements_official.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p content/archivio content/images content/pdf DIA_METRICS static/css static/js templates

# Expose port for Flask app
EXPOSE 5000

# Set environment variables
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1

# Run the Flask application
CMD ["python", "app.py"]
