from fastapi import FastAPI
from app.health.router import router as health_router

app = FastAPI(
    title="Health Data AI Platform - API Service",
    description="Secure health data upload and processing API for the Health Data AI Platform.",
    version="1.0.0"
)

app.include_router(health_router)

@app.get("/")
async def root():
    return {
        "message": "Health Data AI Platform API",
        "version": "1.0.0",
        "documentation": "/docs",
        "supported_formats": ["Apache Avro"],
        "supported_record_types": [
            "AvroBloodGlucoseRecord",
            "AvroHeartRateRecord",
            "AvroStepsRecord",
            "AvroSleepSessionRecord",
            "AvroActiveCaloriesBurnedRecord",
            "AvroHeartRateVariabilityRmssdRecord",
        ],
    }