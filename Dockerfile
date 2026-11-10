# Official Playwright Python image has all Chromium system dependencies pre-installed
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set working directory
WORKDIR /app

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure Chromium browser binary is ready
RUN playwright install chromium

# Copy application files
COPY backend /app/backend
COPY frontend /app/frontend

# Create storage directories
RUN mkdir -p /app/exports /app/backend/sessions

# Render assigns a dynamic PORT; default to 10000 (Render standard)
EXPOSE ${PORT:-10000}

# Start FastAPI – Render injects $PORT automatically
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
