# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libffi-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories for persistent storage
RUN mkdir -p data/uploads data/stockr_backbone data/temp static logs src/static \
    && chmod -R 777 data logs static src/static src/static

# Expose port (Railway uses PORT env var)
EXPOSE ${PORT}

# Health check - disabled during debugging
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=5 \
    CMD curl -f http://localhost:${PORT}/ready || exit 1

# Run gunicorn directly (simpler, more reliable)
CMD sh -c "python -c \"import os; print('Python startup script running'); print(f'Env PORT: {os.getenv('PORT')}'); print(f'Env ENVIRONMENT: {os.getenv('ENVIRONMENT')}'); import src.main; print('src.main imported'); os.execvp('gunicorn', ['gunicorn', '--bind', '0.0.0.0:' + os.getenv('PORT', '8000'), '--workers', os.getenv('WEB_CONCURRENCY', '2'), '--worker-class', 'uvicorn.workers.UvicornWorker', '--timeout', '120', '--access-logfile', '-', '--error-logfile', '-', 'src.main:app'])\"
