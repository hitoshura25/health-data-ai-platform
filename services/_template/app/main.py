"""
Health Data AI Platform - Service Template Main Module

This template provides examples for different types of services.
Choose the appropriate section for your service type and remove the others.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

# Shared imports (available to all services)
from shared.common.logging import setup_logging
from shared.common.config import get_settings
from shared.contracts.api_models import BaseResponse, HealthCheckResponse
from shared.types import HealthDataProcessingMessage

# Choose your framework imports based on service type:

# For FastAPI Web Services (Health API Service):
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# For background workers (Message Queue, ETL Engine):
# import aio_pika
# from shared.common.message_queue import MessageQueueClient

# For ML services (AI Query Interface):
# import mlflow
# from transformers import pipeline

# Local imports
from .config import Settings
from .models import ServiceModel  # Create this file with your data models

# Initialize logging
logger = setup_logging()


# =============================================================================
# OPTION 1: FastAPI Web Service Template (Health API, etc.)
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    logger.info("Starting service...")

    # Startup tasks
    # - Initialize database connections
    # - Setup message queue clients
    # - Load ML models
    # - Validate configuration

    yield

    # Shutdown tasks
    # - Close database connections
    # - Close message queue connections
    # - Cleanup resources
    logger.info("Service stopped")


# Create FastAPI app
app = FastAPI(
    title="Your Service Name",
    description="Description of what your service does",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Health check endpoint."""
    # Add your health checks here:
    # - Database connectivity
    # - External service dependencies
    # - Memory/disk usage

    return HealthCheckResponse(
        success=True,
        overall_status="healthy",
        services={
            "self": {
                "service": "your-service-name",
                "status": "healthy",
                "message": "Service is running",
                "duration_ms": 1.0,
            }
        },
        summary={"healthy": 1, "degraded": 0, "unhealthy": 0},
    )


@app.get("/", response_model=BaseResponse)
async def root():
    """Root endpoint."""
    return BaseResponse(
        success=True,
        correlation_id="example-correlation-id"
    )


# Add your service-specific endpoints here
@app.post("/api/v1/your-endpoint")
async def your_endpoint(data: Dict[str, Any]):
    """Example endpoint - replace with your actual endpoints."""
    try:
        # Your business logic here
        result = {"message": "Success", "data": data}
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


def main():
    """Main entry point for FastAPI service."""
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="info",
    )


# =============================================================================
# OPTION 2: Background Worker Template (Message Queue, ETL Engine)
# =============================================================================

class BackgroundWorker:
    """Template for background worker services."""

    def __init__(self):
        self.settings = get_settings()
        self.running = False

    async def start(self):
        """Start the background worker."""
        logger.info("Starting background worker...")
        self.running = True

        # Initialize connections
        # - Message queue connection
        # - Database connection
        # - External service clients

        while self.running:
            try:
                await self.process_messages()
                await asyncio.sleep(1)  # Adjust based on your needs
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def stop(self):
        """Stop the background worker."""
        logger.info("Stopping background worker...")
        self.running = False

    async def process_messages(self):
        """Process messages from the queue."""
        # Your message processing logic here
        # Example:
        # message = await self.get_next_message()
        # if message:
        #     await self.handle_message(message)
        pass

    async def handle_message(self, message: HealthDataProcessingMessage):
        """Handle a single message."""
        try:
            # Your message processing logic here
            logger.info(f"Processing message: {message.id}")

            # Process the message
            # - Validate data
            # - Transform data
            # - Store results
            # - Send to next queue

            logger.info(f"Successfully processed message: {message.id}")
        except Exception as e:
            logger.error(f"Failed to process message {message.id}: {e}")
            # Handle failed message (retry, dead letter queue, etc.)


async def run_worker():
    """Run the background worker."""
    worker = BackgroundWorker()
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


# =============================================================================
# OPTION 3: ML Service Template (AI Query Interface)
# =============================================================================

class MLService:
    """Template for ML services."""

    def __init__(self):
        self.settings = get_settings()
        self.model = None

    async def initialize(self):
        """Initialize the ML service."""
        logger.info("Initializing ML service...")

        # Load your model
        # self.model = mlflow.pytorch.load_model("your-model-uri")
        # or
        # self.model = pipeline("text-generation", model="your-model")

        logger.info("ML service initialized")

    async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make predictions."""
        if not self.model:
            raise ValueError("Model not initialized")

        try:
            # Your prediction logic here
            # result = self.model.predict(input_data)
            result = {"prediction": "example", "confidence": 0.95}

            return result
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            raise


# =============================================================================
# Entry Point Selection
# =============================================================================

if __name__ == "__main__":
    # Choose the appropriate entry point for your service:

    # For FastAPI services:
    main()

    # For background workers:
    # asyncio.run(run_worker())

    # For ML services:
    # ml_service = MLService()
    # asyncio.run(ml_service.initialize())
    # # Then start your prediction server (FastAPI with ML endpoints)