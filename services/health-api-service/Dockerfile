# Multi-stage Dockerfile for Health API Service
# Supports both arm64 (Oracle Ampere A1) and amd64
# Build: docker buildx build --platform linux/arm64,linux/amd64 -t health-api:latest .

# Build stage
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies (system-wide, not --user)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.13-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder (system-wide installation)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY ./app /app/app

# Create non-root user
RUN groupadd -r healthapi && useradd -r -g healthapi healthapi \
    && chown -R healthapi:healthapi /app

USER healthapi

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health/live || exit 1

# Run application
# uvicorn will automatically use uvloop if installed (production performance optimization)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]