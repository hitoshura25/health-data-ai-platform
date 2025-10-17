FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY deployment/scripts/entrypoint.sh /app/deployment/scripts/entrypoint.sh
RUN chmod +x /app/deployment/scripts/entrypoint.sh
ENTRYPOINT ["/app/deployment/scripts/entrypoint.sh"]
