# Health Data AI Platform - Service Template
# Replace this comment with your service name and description

FROM python:3.11-slim

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared components first (for better caching)
COPY shared/ ./shared/

# Copy service requirements and install Python dependencies
COPY services/your-service-name/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy service code
COPY services/your-service-name/app/ ./app/

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check (customize for your service)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port (customize for your service)
EXPOSE 8000

# Default command (customize for your service)
# For FastAPI services:
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# For background workers:
# CMD ["python", "-m", "app.worker"]

# For ML services:
# CMD ["python", "-m", "app.inference_server"]

# Build instructions:
# docker build -t health-platform/your-service-name -f services/your-service-name/Dockerfile .
# docker run -p 8000:8000 health-platform/your-service-name