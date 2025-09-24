FROM python:3.11-slim

WORKDIR /app

# Copy only the requirements file to leverage Docker cache
COPY ./requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .
