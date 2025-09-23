# Health Data AI Platform - Schema Documentation

This directory contains Avro schemas for the Health Data AI Platform, derived from real Android Health Connect data.

## Directory Structure

```
schemas/
├── common/                 # Shared schema components
│   ├── metadata.avsc      # Common metadata structure
│   └── device.avsc        # Device information schema
├── health_records/        # Health data record schemas
│   ├── blood_glucose.avsc
│   ├── heart_rate.avsc
│   ├── sleep_session.avsc
│   ├── steps.avsc
│   ├── active_calories.avsc
│   └── heart_rate_variability.avsc
└── processing/           # Message queue schemas
    ├── health_data_message.avsc
    ├── etl_result.avsc
    └── error_message.avsc
```

## Health Record Types

### Blood Glucose Records
- **File**: `health_records/blood_glucose.avsc`
- **Clinical Context**: Includes meal type, relation to meal, and specimen source
- **Key Fields**:
  - `levelInMilligramsPerDeciliter`: Glucose level (normal: 70-140 mg/dL)
  - `specimenSource`: Source type (CGM, capillary blood, etc.)
  - `mealType`: Breakfast, lunch, dinner, or snack
  - `relationToMeal`: Fasting, before meal, after meal

### Heart Rate Records
- **File**: `health_records/heart_rate.avsc`
- **Structure**: Time-series samples with individual measurements
- **Key Fields**:
  - `samples`: Array of heart rate measurements with timestamps
  - `beatsPerMinute`: Heart rate value (normal resting: 60-100 bpm)

### Sleep Session Records
- **File**: `health_records/sleep_session.avsc`
- **Structure**: Sleep stages with detailed timing
- **Key Fields**:
  - `stages`: Array of sleep stage periods
  - `stage`: Sleep stage type (LIGHT, DEEP, REM, AWAKE, etc.)
  - `durationMillis`: Total sleep duration

### Steps Records
- **File**: `health_records/steps.avsc`
- **Structure**: Step count over time periods
- **Key Fields**:
  - `count`: Total steps in the time period
  - `startTimeEpochMillis`/`endTimeEpochMillis`: Time range

### Active Calories Records
- **File**: `health_records/active_calories.avsc`
- **Structure**: Energy expenditure over time periods
- **Key Fields**:
  - `energyInKilocalories`: Active calories burned (excludes BMR)

### Heart Rate Variability Records
- **File**: `health_records/heart_rate_variability.avsc`
- **Structure**: RMSSD HRV measurements
- **Key Fields**:
  - `heartRateVariabilityRmssd`: HRV value in milliseconds (normal: 20-50ms)

## Common Components

### Metadata Structure
All health records share the same metadata structure:
- `id`: Unique record identifier
- `dataOriginPackageName`: Source app package name
- `lastModifiedTimeEpochMillis`: Last modification timestamp
- `clientRecordId`: Optional client identifier
- `clientRecordVersion`: Version for client record management
- `device`: Optional device information

### Device Information
Device records contain:
- `manufacturer`: Device manufacturer (Samsung, Oura, Dexcom, etc.)
- `model`: Device model (Galaxy Watch 7, Oura Ring Gen 3, Stelo, etc.)
- `type`: Device type classification (smartwatch, ring, cgm, etc.)

## Processing Message Schemas

### Health Data Processing Message
- **File**: `processing/health_data_message.avsc`
- **Purpose**: Queue messages for health data processing
- **Key Features**:
  - Intelligent routing by record type
  - Deduplication support with idempotency keys
  - Retry logic with TTL and priority handling
  - Storage location references

### ETL Processing Result
- **File**: `processing/etl_result.avsc`
- **Purpose**: Results from ETL narrative engine processing
- **Key Features**:
  - Processing status (success, failed, quarantined)
  - Clinical narratives and structured insights
  - Quality scoring and error reporting
  - Training data location references

### Error Messages
- **File**: `processing/error_message.avsc`
- **Purpose**: Error reporting across all services
- **Key Features**:
  - Error classification and severity levels
  - Service component identification
  - Retry recommendations
  - Stack trace and debugging information

## Clinical Validation Ranges

The schemas include documentation of normal clinical ranges:

- **Blood Glucose**: 70-140 mg/dL (normal), <70 hypoglycemic, >180 hyperglycemic
- **Heart Rate**: 60-100 bpm (normal resting), <60 bradycardia, >100 tachycardia
- **HRV RMSSD**: 20-50ms (normal adult range)
- **Sleep Efficiency**: >85% considered good

## Usage with Python Types

The schemas correspond to Python dataclasses in `shared/types/`:

```python
from shared.types import AvroBloodGlucoseRecord, HealthDataProcessingMessage

# Type-safe health record handling
glucose_record = AvroBloodGlucoseRecord(...)

# Processing message creation
message = HealthDataProcessingMessage(
    record_type=HealthRecordType.BLOOD_GLUCOSE,
    ...
)
```

## Schema Evolution

When modifying schemas:

1. **Backward Compatibility**: Ensure existing data can still be read
2. **Default Values**: Add default values for new optional fields
3. **Documentation**: Update field documentation with clinical context
4. **Validation**: Update corresponding Python types and validators

## Validation Framework

The schemas work with the validation framework in `shared/validation/`:

- **Clinical Validators**: Validate against medical ranges and patterns
- **Schema Validators**: Validate structure against Avro schemas
- **Data Quality**: Assess completeness, accuracy, and clinical relevance

## Integration Points

These schemas are used across all platform services:

- **Health API Service**: Validates uploaded health data
- **Message Queue**: Routes messages using processing schemas
- **Data Lake**: Stores data according to health record schemas
- **ETL Engine**: Processes records and generates results
- **AI Interface**: Queries processed data for insights