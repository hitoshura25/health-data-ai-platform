# AI Query Interface with Training Pipeline - Comprehensive Specification

**Created**: 2025-11-18
**Status**: Draft Specification
**Component**: AI Query Interface + Training Pipeline
**Dependencies**: ETL Narrative Engine (training data source)

---

## Executive Summary

This specification addresses three critical enhancements to the AI Query Interface service:

1. **Model Selection**: Adopt **OLMo-7B** (Allen Institute AI) as the primary language model
2. **Training Pipeline**: Implement a complete fine-tuning workflow for clinical narrative data
3. **Carbon Tracking**: Integrate **CodeCarbon** for environmental impact monitoring

### Current State vs. Proposed State

| Aspect | Current Implementation Plan | Proposed Enhancement |
|--------|---------------------------|---------------------|
| **Model** | Generic `transformers` library | **OLMo-7B** (allenai/OLMo-7B) |
| **Training** | ❌ Not specified | ✅ Complete fine-tuning pipeline |
| **Carbon Tracking** | ❌ Not included | ✅ CodeCarbon + MLflow integration |
| **Model Management** | MLflow (serving only) | MLflow (training + serving) |

---

## Part 1: Model Selection - Why OLMo-7B?

### Rationale for OLMo

**OLMo** (Open Language Model) from the Allen Institute for AI is the optimal choice for this health data platform:

#### Technical Advantages
1. **Fully Open Source**: Apache 2.0 license with complete training transparency
2. **HuggingFace Compatible**: Seamless integration with existing `transformers` stack
3. **Fine-Tuning Optimized**: Designed for domain adaptation with efficient training
4. **Model Size Options**: 1B, 7B parameters (7B recommended for quality vs. compute balance)
5. **Medical Research Friendly**: AI2 supports scientific and healthcare applications

#### Practical Benefits for Health Data
- **Privacy-First**: Can be self-hosted without data leaving infrastructure
- **Clinical Adaptation**: Fine-tuning on clinical narratives improves health data understanding
- **Cost Efficiency**: Lower compute requirements than GPT-4 class models
- **Regulatory Compliance**: Full control over model behavior and outputs
- **Transparency**: Complete access to training data, code, and model weights

### Model Specification

```python
# Primary Model
model_id: "allenai/OLMo-7B"
model_type: "causal language model"
parameters: 7B
context_window: 2048 tokens
framework: "PyTorch + HuggingFace Transformers"

# Alternative for Resource-Constrained Environments
fallback_model_id: "allenai/OLMo-1B"
fallback_parameters: 1B
```

### Deployment Architecture

```yaml
Model Serving Strategy:
  - Stage: "Staging" → OLMo-7B (fine-tuned on recent data)
  - Stage: "Production" → OLMo-7B (human-approved, validated model)
  - Fallback: Base OLMo-7B (pre-trained, no fine-tuning)

Compute Requirements:
  - Training: GPU with 24GB+ VRAM (A10G, RTX 4090, or better)
  - Inference: GPU with 16GB+ VRAM or CPU with 32GB+ RAM
  - Batch Inference: Recommended for cost efficiency
```

---

## Part 2: Training Pipeline Architecture

### Overview

The training pipeline transforms ETL-generated clinical narratives into a fine-tuned OLMo model through a structured, monitored process.

### Training Data Flow

```
ETL Narrative Engine → Training Data (JSONL) → Training Pipeline → Fine-Tuned Model → MLflow Registry
                              ↓
                      CodeCarbon Monitoring
                              ↓
                      Emissions Reports
```

### Training Data Format (from ETL Engine)

The ETL Narrative Engine already generates training-ready data:

```jsonl
{
  "instruction": "Analyze my blood glucose data from September 22, 2025 and provide detailed clinical insights including glucose control assessment and recommendations.",
  "output": "Your glucose monitoring data from 2025-09-22 shows 48 readings with an average glucose level of 125.3 mg/dL. You spent 72.5% of time in the target glucose range (70-180 mg/dL). This indicates good glucose management...",
  "metadata": {
    "source_s3_key": "raw/BloodGlucoseRecord/2025/09/22/user123_20250922_120000_dexcom_a1b2c3d4.avro",
    "record_type": "BloodGlucoseRecord",
    "training_category": "metabolic_diabetes",
    "complexity_level": "high_clinical",
    "clinical_relevance": "high_clinical_relevance",
    "records_processed": 48,
    "quality_score": 0.95
  }
}
```

**Data Location**: `s3://health-data/training/{category}/{year}/{month}/health_journal_{year}_{month}.jsonl`

**Categories**:
- `metabolic_diabetes` (glucose data)
- `cardiovascular_fitness` (heart rate data)
- `sleep_recovery` (sleep sessions)
- `physical_activity` (steps, movement)
- `energy_metabolism` (calories)
- `autonomic_health` (HRV data)

### Training Pipeline Components

#### 1. Data Preparation Module

```python
class TrainingDataPreparator:
    """Prepares ETL-generated data for OLMo fine-tuning"""

    def __init__(self, s3_client, min_quality_score: float = 0.7):
        self.s3_client = s3_client
        self.min_quality_score = min_quality_score

    async def load_training_data(
        self,
        categories: List[str],
        date_range: Tuple[datetime, datetime],
        min_samples: int = 100
    ) -> pd.DataFrame:
        """
        Load and validate training data from S3

        Filters:
        - quality_score >= min_quality_score
        - complexity_level in ["moderate_clinical", "high_clinical"]
        - clinical_relevance != "standard_clinical_relevance"

        Returns DataFrame with columns:
        - instruction: str
        - output: str
        - category: str
        - quality_score: float
        - complexity_level: str
        """
        pass

    async def prepare_dataset(
        self,
        df: pd.DataFrame,
        train_split: float = 0.8,
        val_split: float = 0.1,
        test_split: float = 0.1
    ) -> Dict[str, Dataset]:
        """
        Prepare HuggingFace datasets for training

        Returns:
        {
            "train": Dataset,
            "validation": Dataset,
            "test": Dataset
        }
        """
        pass

    def format_for_instruction_tuning(self, example: Dict) -> Dict:
        """
        Format instruction-output pairs for OLMo fine-tuning

        Format:
        <|user|> {instruction}
        <|assistant|> {output}
        """
        prompt = f"<|user|>\n{example['instruction']}\n<|assistant|>\n{example['output']}"
        return {"text": prompt}
```

#### 2. Fine-Tuning Configuration

```python
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType

class OLMoFineTuningConfig:
    """Configuration for OLMo-7B fine-tuning with LoRA"""

    # Model Configuration
    model_name: str = "allenai/OLMo-7B"
    use_lora: bool = True  # Parameter-efficient fine-tuning

    # LoRA Configuration (reduces memory footprint)
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,  # Low-rank adaptation dimension
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        bias="none"
    )

    # Training Hyperparameters
    training_args = TrainingArguments(
        output_dir="./training_runs",
        num_train_epochs=3,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        gradient_accumulation_steps=8,  # Effective batch size = 32
        learning_rate=2e-4,
        warmup_steps=100,
        logging_steps=10,
        save_steps=500,
        eval_steps=500,
        evaluation_strategy="steps",
        save_strategy="steps",
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        fp16=True,  # Mixed precision training
        gradient_checkpointing=True,  # Memory optimization
        optim="adamw_torch",
        report_to=["mlflow", "codecarbon"],  # Dual tracking
    )

    # Data Configuration
    max_sequence_length: int = 512
    data_collator: DataCollatorForLanguageModeling = None  # Initialized with tokenizer
```

**Why LoRA (Low-Rank Adaptation)?**
- **Memory Efficient**: Fine-tunes only ~1% of parameters
- **Fast Training**: Reduces training time by 60-70%
- **Quality Preservation**: Maintains base model performance
- **Storage Efficient**: Adapter weights are <100MB vs full model (14GB)

#### 3. Training Pipeline Implementation

```python
import mlflow
from codecarbon import EmissionsTracker
import torch
from typing import Dict, Any

class ClinicalNarrativeTrainer:
    """Complete training pipeline with monitoring and tracking"""

    def __init__(self, config: OLMoFineTuningConfig):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.emissions_tracker = None

    async def initialize(self):
        """Initialize model, tokenizer, and tracking"""

        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        self.tokenizer.pad_token = self.tokenizer.eos_token

        # Load base model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype=torch.float16,
            device_map="auto"
        )

        # Apply LoRA if configured
        if self.config.use_lora:
            self.model = get_peft_model(self.model, self.config.lora_config)
            self.model.print_trainable_parameters()

        # Initialize emissions tracking
        self.emissions_tracker = EmissionsTracker(
            project_name="health-ai-olmo-training",
            output_dir="./emissions",
            tracking_mode="process"
        )

    async def train(
        self,
        train_dataset: Dataset,
        val_dataset: Dataset,
        run_name: str = None
    ) -> Dict[str, Any]:
        """
        Execute fine-tuning with comprehensive tracking

        Returns:
        {
            "model_uri": str,  # MLflow model URI
            "metrics": Dict[str, float],
            "emissions": Dict[str, float],
            "training_duration_hours": float
        }
        """

        # Start MLflow run
        mlflow.set_experiment("health-narrative-olmo-finetuning")

        with mlflow.start_run(run_name=run_name) as run:
            # Start carbon tracking
            self.emissions_tracker.start()

            start_time = time.time()

            # Log configuration
            mlflow.log_params({
                "model_name": self.config.model_name,
                "use_lora": self.config.use_lora,
                "num_train_epochs": self.config.training_args.num_train_epochs,
                "learning_rate": self.config.training_args.learning_rate,
                "train_samples": len(train_dataset),
                "val_samples": len(val_dataset)
            })

            # Data collator for language modeling
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False  # Causal LM, not masked LM
            )

            # Create trainer
            trainer = Trainer(
                model=self.model,
                args=self.config.training_args,
                train_dataset=train_dataset,
                eval_dataset=val_dataset,
                data_collator=data_collator,
                tokenizer=self.tokenizer
            )

            # Train model
            train_result = trainer.train()

            # Stop carbon tracking
            emissions_data = self.emissions_tracker.stop()

            # Calculate metrics
            training_duration = (time.time() - start_time) / 3600  # hours

            # Log emissions to MLflow
            mlflow.log_metrics({
                "carbon_emissions_kg": emissions_data,
                "training_duration_hours": training_duration,
                "final_train_loss": train_result.metrics["train_loss"],
                "final_eval_loss": trainer.evaluate()["eval_loss"]
            })

            # Save model to MLflow
            model_info = mlflow.transformers.log_model(
                transformers_model={
                    "model": self.model,
                    "tokenizer": self.tokenizer
                },
                artifact_path="olmo-health-narrative",
                registered_model_name="health-query-olmo"
            )

            return {
                "model_uri": model_info.model_uri,
                "run_id": run.info.run_id,
                "metrics": {
                    "train_loss": train_result.metrics["train_loss"],
                    "eval_loss": trainer.evaluate()["eval_loss"]
                },
                "emissions": {
                    "carbon_kg": emissions_data,
                    "duration_hours": training_duration
                },
                "training_duration_hours": training_duration
            }
```

#### 4. Training Schedule Strategy

```python
class TrainingScheduler:
    """Manages when and how often to retrain models"""

    # Training Triggers
    TRIGGERS = {
        "monthly": "Scheduled monthly retraining",
        "feedback_threshold": "Poor feedback triggers retraining (avg rating < 3.0)",
        "data_volume": "Sufficient new data available (10,000+ samples)",
        "manual": "Human-initiated retraining"
    }

    async def should_trigger_training(self) -> Dict[str, bool]:
        """
        Evaluate training triggers

        Returns:
        {
            "should_train": bool,
            "reason": str,
            "estimated_samples": int,
            "last_training_date": datetime
        }
        """

        # Check monthly schedule
        last_training = await self._get_last_training_date()
        days_since = (datetime.utcnow() - last_training).days

        if days_since >= 30:
            return {
                "should_train": True,
                "reason": "monthly",
                "estimated_samples": await self._count_new_samples(),
                "last_training_date": last_training
            }

        # Check feedback quality
        avg_feedback = await self._get_recent_feedback_average()
        if avg_feedback < 3.0:
            return {
                "should_train": True,
                "reason": "feedback_threshold",
                "average_feedback": avg_feedback,
                "last_training_date": last_training
            }

        # Check data volume
        new_samples = await self._count_new_samples()
        if new_samples >= 10000:
            return {
                "should_train": True,
                "reason": "data_volume",
                "estimated_samples": new_samples,
                "last_training_date": last_training
            }

        return {
            "should_train": False,
            "reason": "no_trigger_met",
            "last_training_date": last_training
        }
```

---

## Part 3: CodeCarbon Integration

### Overview

CodeCarbon tracks the environmental impact of model training by monitoring GPU, CPU, and RAM energy consumption.

### Architecture

```
Training Pipeline
       ↓
EmissionsTracker (CodeCarbon)
       ↓
  Emissions Data
       ↓
MLflow (metrics + artifacts)
       ↓
Emissions Reports + Dashboards
```

### Implementation

#### 1. CodeCarbon Configuration

```python
from codecarbon import EmissionsTracker, OfflineEmissionsTracker

class CarbonTracking:
    """Carbon emissions tracking configuration"""

    @staticmethod
    def create_tracker(
        project_name: str = "health-ai-training",
        online: bool = True,
        country_iso_code: str = "USA"
    ) -> EmissionsTracker:
        """
        Create emissions tracker

        Online mode: Fetches live carbon intensity data
        Offline mode: Uses static regional data
        """

        if online:
            return EmissionsTracker(
                project_name=project_name,
                output_dir="./emissions",
                tracking_mode="process",
                log_level="INFO",
                save_to_file=True,
                save_to_logger=True,
                gpu_ids=None,  # Track all GPUs
                emissions_endpoint="https://api.electricitymap.org/v3/carbon-intensity/latest",
                country_iso_code=country_iso_code
            )
        else:
            return OfflineEmissionsTracker(
                project_name=project_name,
                output_dir="./emissions",
                country_iso_code=country_iso_code
            )
```

#### 2. MLflow Integration

```python
class MLflowCarbonIntegration:
    """Integrate CodeCarbon metrics into MLflow"""

    @staticmethod
    def log_emissions(
        emissions_data: float,
        tracker: EmissionsTracker,
        additional_metrics: Dict[str, float] = None
    ):
        """
        Log carbon emissions to MLflow

        Metrics logged:
        - carbon_emissions_kg: Total CO2 emissions
        - energy_consumed_kwh: Total energy consumed
        - carbon_intensity: Regional carbon intensity
        - compute_hours: GPU/CPU hours
        """

        # Primary emission metric
        mlflow.log_metric("carbon_emissions_kg", emissions_data)

        # Detailed breakdown
        if hasattr(tracker, "_total_energy"):
            mlflow.log_metric("energy_consumed_kwh", tracker._total_energy.kWh)
            mlflow.log_metric("cpu_energy_kwh", tracker._cpu_energy.kWh)
            mlflow.log_metric("gpu_energy_kwh", tracker._gpu_energy.kWh)
            mlflow.log_metric("ram_energy_kwh", tracker._ram_energy.kWh)

        # Carbon intensity (gCO2/kWh)
        if hasattr(tracker, "_carbon_intensity"):
            mlflow.log_metric("carbon_intensity_gco2_kwh", tracker._carbon_intensity)

        # Additional context
        if additional_metrics:
            mlflow.log_metrics(additional_metrics)

        # Save emissions report as artifact
        emissions_file = "emissions.csv"
        if os.path.exists(emissions_file):
            mlflow.log_artifact(emissions_file, artifact_path="emissions_reports")
```

#### 3. Emissions Reporting

```python
class EmissionsReporter:
    """Generate comprehensive emissions reports"""

    async def generate_training_report(
        self,
        emissions_kg: float,
        training_duration_hours: float,
        model_name: str,
        dataset_size: int
    ) -> Dict[str, Any]:
        """
        Generate human-readable emissions report

        Includes:
        - Total emissions (kg CO2)
        - Equivalencies (miles driven, trees needed)
        - Cost estimates
        - Recommendations
        """

        # Calculate equivalencies
        miles_driven = emissions_kg * 2.4  # avg car: 0.41 kg CO2/mile
        trees_needed = emissions_kg / 21  # 1 tree absorbs ~21 kg CO2/year

        report = {
            "summary": {
                "total_emissions_kg_co2": round(emissions_kg, 3),
                "training_duration_hours": round(training_duration_hours, 2),
                "emissions_per_hour": round(emissions_kg / training_duration_hours, 4),
                "model_name": model_name,
                "dataset_size": dataset_size
            },
            "equivalencies": {
                "miles_driven_equivalent": round(miles_driven, 1),
                "trees_to_offset_1year": round(trees_needed, 1),
                "smartphones_charged": round(emissions_kg * 121.6, 0)  # 1 kg CO2 = 121 charges
            },
            "recommendations": self._generate_recommendations(emissions_kg, training_duration_hours),
            "timestamp": datetime.utcnow().isoformat()
        }

        # Log to MLflow as artifact
        await self._save_report_to_mlflow(report)

        return report

    def _generate_recommendations(
        self,
        emissions_kg: float,
        duration_hours: float
    ) -> List[str]:
        """Generate emissions reduction recommendations"""

        recommendations = []

        if emissions_kg > 5.0:
            recommendations.append(
                "Consider using cloud regions with lower carbon intensity (e.g., Quebec, Norway)"
            )
            recommendations.append(
                "Schedule training during off-peak hours when grid is cleaner"
            )

        if duration_hours > 12:
            recommendations.append(
                "Evaluate smaller model variants (OLMo-1B) for faster iterations"
            )
            recommendations.append(
                "Implement early stopping to reduce unnecessary training epochs"
            )

        recommendations.append(
            f"Offset {emissions_kg:.2f} kg CO2 through carbon credit purchases or tree planting"
        )

        return recommendations
```

### Emissions Monitoring Dashboard

```python
# FastAPI endpoint for emissions visualization
from fastapi import APIRouter
import mlflow

router = APIRouter(prefix="/emissions", tags=["carbon-tracking"])

@router.get("/training-history")
async def get_emissions_history(limit: int = 10):
    """
    Get historical emissions data from MLflow

    Returns:
    [
        {
            "run_id": str,
            "run_name": str,
            "timestamp": str,
            "emissions_kg": float,
            "duration_hours": float,
            "model_version": str
        }
    ]
    """

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("health-narrative-olmo-finetuning")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=["start_time DESC"],
        max_results=limit
    )

    emissions_data = []
    for run in runs:
        emissions_data.append({
            "run_id": run.info.run_id,
            "run_name": run.data.tags.get("mlflow.runName", "unnamed"),
            "timestamp": run.info.start_time,
            "emissions_kg": run.data.metrics.get("carbon_emissions_kg", 0),
            "duration_hours": run.data.metrics.get("training_duration_hours", 0),
            "model_version": run.data.params.get("model_name", "unknown")
        })

    return emissions_data

@router.get("/total-footprint")
async def get_total_carbon_footprint():
    """
    Calculate total carbon footprint across all training runs

    Returns:
    {
        "total_emissions_kg_co2": float,
        "total_training_hours": float,
        "total_runs": int,
        "average_per_run_kg": float,
        "trees_to_offset": float
    }
    """

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("health-narrative-olmo-finetuning")

    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        max_results=1000
    )

    total_emissions = sum(
        run.data.metrics.get("carbon_emissions_kg", 0) for run in runs
    )
    total_hours = sum(
        run.data.metrics.get("training_duration_hours", 0) for run in runs
    )

    return {
        "total_emissions_kg_co2": round(total_emissions, 3),
        "total_training_hours": round(total_hours, 2),
        "total_runs": len(runs),
        "average_per_run_kg": round(total_emissions / len(runs), 3) if runs else 0,
        "trees_to_offset_1year": round(total_emissions / 21, 1)
    }
```

---

## Part 4: Updated Technology Stack

### Dependencies Update

```python
# ai-query-interface/requirements.txt

# Core AI/ML (UPDATED)
transformers==4.38.0
torch==2.2.0
peft==0.8.0  # NEW: For LoRA fine-tuning
accelerate==0.27.0  # NEW: For distributed training

# Model Management
mlflow==2.10.2
datasets==2.17.0  # NEW: For training data management

# Carbon Tracking (NEW)
codecarbon==2.3.4
mlflow-emissions-sdk==0.0.2  # NEW: MLflow + CodeCarbon integration

# Existing dependencies
fastapi==0.104.1
uvicorn[standard]==0.24.0
structlog==23.2.0
numpy==1.26.3
pandas==2.2.0
aiofiles==23.2.0
tenacity==8.2.3
prometheus-client==0.19.0
```

### Infrastructure Requirements

```yaml
# Training Infrastructure
GPU_Requirements:
  minimum: "NVIDIA A10G (24GB VRAM)"
  recommended: "NVIDIA A100 (40GB VRAM)"
  fallback: "NVIDIA RTX 4090 (24GB VRAM)"

Storage_Requirements:
  model_storage: "50GB (base model + fine-tuned variants)"
  training_data: "10-100GB (depending on data volume)"
  mlflow_artifacts: "100GB+ (models, logs, emissions reports)"

Compute_Estimates:
  training_time_per_epoch: "2-4 hours (OLMo-7B with LoRA)"
  full_training_3_epochs: "6-12 hours"
  inference_latency: "200-500ms per query (batch size 1)"
```

---

## Part 5: Integration with Existing Services

### ETL Narrative Engine Integration

**Data Flow**:
```
ETL Engine → S3 Training Data → Training Pipeline → Fine-Tuned Model → Query Interface
```

**API Contract**:
```python
# ETL Engine exposes training data metadata
GET /etl/training-data/stats
Response:
{
    "total_samples": 50000,
    "by_category": {
        "metabolic_diabetes": 12000,
        "cardiovascular_fitness": 15000,
        "sleep_recovery": 10000,
        "physical_activity": 8000,
        "energy_metabolism": 3000,
        "autonomic_health": 2000
    },
    "date_range": {
        "earliest": "2025-01-01",
        "latest": "2025-11-18"
    },
    "average_quality_score": 0.89
}
```

### AI Query Interface Integration

**Model Loading Flow**:
```python
class EnhancedModelManager:
    """Updated model manager with OLMo support"""

    async def initialize(self):
        """Load OLMo model from MLflow"""

        try:
            # Try production model
            model_uri = "models:/health-query-olmo/Production"
            self.model = mlflow.transformers.load_model(model_uri)
            logger.info("Loaded production OLMo model")
        except Exception as e:
            logger.warning("Production model unavailable, falling back to staging")
            model_uri = "models:/health-query-olmo/Staging"
            self.model = mlflow.transformers.load_model(model_uri)
```

### Health API Service Integration

**New Training Trigger Endpoint**:
```python
# health-api-service/app/training/router.py

@router.post("/training/trigger")
async def trigger_training(
    reason: str,
    user: User = Depends(admin_user)  # Admin only
):
    """
    Manually trigger model retraining

    Reasons: "monthly", "feedback_poor", "data_available", "manual"
    """

    # Publish training job to message queue
    await publish_training_job({
        "reason": reason,
        "triggered_by": user.email,
        "timestamp": datetime.utcnow().isoformat()
    })

    return {"message": "Training job queued", "reason": reason}
```

---

## Part 6: Monitoring & Observability

### Key Metrics to Track

```yaml
Training Metrics:
  - train_loss: "Model training loss"
  - eval_loss: "Validation loss"
  - perplexity: "Language model perplexity"
  - learning_rate: "Current learning rate"
  - gradient_norm: "Gradient stability"

Carbon Metrics:
  - carbon_emissions_kg: "Total CO2 emissions"
  - energy_consumed_kwh: "Total energy consumed"
  - carbon_intensity_gco2_kwh: "Regional carbon intensity"
  - gpu_hours: "GPU compute time"

Model Performance Metrics:
  - inference_latency_ms: "Query response time"
  - tokens_per_second: "Generation speed"
  - user_feedback_rating: "Average user satisfaction"
  - conversation_quality_score: "Multi-turn conversation quality"
```

### Alerts and Notifications

```python
class TrainingAlerts:
    """Alert conditions for training pipeline"""

    ALERT_CONDITIONS = {
        "high_carbon_emissions": {
            "metric": "carbon_emissions_kg",
            "threshold": 10.0,
            "message": "Training emissions exceeded 10 kg CO2"
        },
        "poor_model_performance": {
            "metric": "eval_loss",
            "threshold": 2.0,
            "message": "Validation loss is too high"
        },
        "training_timeout": {
            "metric": "training_duration_hours",
            "threshold": 24,
            "message": "Training exceeded 24 hours"
        }
    }
```

---

## Part 7: Testing Strategy

### Unit Tests

```python
# tests/test_training_pipeline.py

class TestTrainingPipeline:

    def test_data_preparation(self):
        """Test training data loading and filtering"""
        pass

    def test_lora_configuration(self):
        """Test LoRA adapter setup"""
        pass

    def test_emissions_tracking(self):
        """Test CodeCarbon integration"""
        pass

# tests/test_olmo_model.py

class TestOLMoModel:

    def test_model_loading(self):
        """Test OLMo model initialization"""
        pass

    def test_inference(self):
        """Test model inference on sample data"""
        pass

    def test_mlflow_logging(self):
        """Test MLflow model registry"""
        pass
```

### Integration Tests

```python
# tests/integration/test_e2e_training.py

class TestEndToEndTraining:

    async def test_full_training_pipeline(self):
        """
        Test complete training workflow:
        1. Load training data from S3
        2. Fine-tune OLMo model
        3. Log to MLflow
        4. Track carbon emissions
        5. Register model
        """
        pass

    async def test_model_serving(self):
        """
        Test trained model serving:
        1. Load model from MLflow
        2. Process health query
        3. Generate clinical response
        """
        pass
```

---

## Part 8: Deployment Strategy

### Training Job Execution

**Option 1: Scheduled Training (Recommended)**
```yaml
# Kubernetes CronJob
apiVersion: batch/v1
kind: CronJob
metadata:
  name: olmo-monthly-training
spec:
  schedule: "0 2 1 * *"  # 2 AM on 1st of month
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: training-job
            image: health-ai/olmo-trainer:latest
            resources:
              limits:
                nvidia.com/gpu: 1
                memory: "64Gi"
          restartPolicy: OnFailure
```

**Option 2: On-Demand Training**
```python
# FastAPI endpoint triggers training job
@router.post("/training/start")
async def start_training_job():
    # Submit to job queue or k8s job
    pass
```

### Model Deployment Pipeline

```
Training Complete → MLflow Registry (Staging) → Human Review → Promote to Production → AI Query Service Auto-Reload
```

**Promotion Workflow**:
```python
class ModelPromotionWorkflow:
    """Human-gated model promotion"""

    async def create_promotion_request(
        self,
        model_version: str,
        performance_metrics: Dict,
        emissions_report: Dict
    ):
        """
        Create promotion request requiring manual approval

        Checklist:
        - Eval loss < threshold
        - User feedback analysis
        - Carbon emissions review
        - Clinical safety review
        """
        pass
```

---

## Part 9: Security & Compliance

### Data Privacy

```yaml
Training Data Security:
  - PHI_Removal: "Training data must not contain identifiable health information"
  - Anonymization: "User IDs must be hashed/anonymized"
  - Access_Control: "Training data access restricted to training pipeline service account"

Model Security:
  - Model_Isolation: "Training runs isolated from production inference"
  - Artifact_Encryption: "MLflow artifacts encrypted at rest"
  - Audit_Logging: "All model access and promotion events logged"
```

### HIPAA Compliance

```python
class HIPAACompliance:
    """HIPAA compliance checks for training data"""

    def validate_training_data(self, dataset: pd.DataFrame) -> bool:
        """
        Validate that training data is HIPAA compliant

        Checks:
        - No direct patient identifiers (names, DOB, SSN)
        - Timestamps truncated to day (not exact second)
        - Location data aggregated (state-level only)
        """
        pass
```

---

## Part 10: Cost Estimates

### Training Costs (Per Run)

```yaml
Cloud GPU (AWS g5.2xlarge - A10G 24GB):
  hourly_rate: $1.212/hour
  training_duration: 10 hours
  total_cost: ~$12.12

Storage (S3):
  training_data: ~$0.50/month
  model_artifacts: ~$2.00/month

MLflow Server:
  compute: $50-100/month (t3.medium)
  storage: $10-20/month

Total Monthly Cost Estimate:
  training_1x_monthly: $12-15
  infrastructure: $60-120
  total: $75-135/month
```

### Carbon Footprint Estimates

```yaml
Training Carbon Emissions (OLMo-7B):
  us_east_region: 2-4 kg CO2 per training run
  quebec_region: 0.3-0.6 kg CO2 per training run (hydroelectric)

Monthly Carbon Footprint:
  1_training_per_month: ~3 kg CO2
  trees_to_offset: ~0.14 trees/year
  offset_cost: ~$1.50/month (carbon credits)
```

---

## Summary & Next Steps

### What This Specification Adds

1. **✅ OLMo-7B Model**: Specific, production-ready model selection
2. **✅ Complete Training Pipeline**: End-to-end fine-tuning workflow
3. **✅ CodeCarbon Integration**: Environmental impact tracking
4. **✅ LoRA Fine-Tuning**: Efficient, cost-effective training
5. **✅ MLflow Integration**: Comprehensive model lifecycle management
6. **✅ Emissions Reporting**: Sustainability metrics and dashboards

### Implementation Priority

```
Phase 1: Foundation (Week 1-2)
  ☐ Set up MLflow with OLMo model registry
  ☐ Implement training data loader from ETL engine
  ☐ Configure CodeCarbon tracking

Phase 2: Training Pipeline (Week 3-4)
  ☐ Implement LoRA fine-tuning pipeline
  ☐ Integrate emissions tracking with MLflow
  ☐ Build training scheduler and triggers

Phase 3: Integration & Testing (Week 5-6)
  ☐ Integrate fine-tuned models with query interface
  ☐ Implement promotion workflow
  ☐ End-to-end testing

Phase 4: Monitoring & Production (Week 7-8)
  ☐ Emissions dashboard and reporting
  ☐ Production deployment
  ☐ Documentation and training
```

### Success Criteria

- ✅ Successfully fine-tune OLMo-7B on clinical narratives
- ✅ Track and report carbon emissions for all training runs
- ✅ Deploy fine-tuned model to production with human approval
- ✅ Achieve <3kg CO2 per training run
- ✅ Maintain user feedback rating >4.0 with fine-tuned model

---

**Specification Status**: Ready for validation and implementation planning
**Dependencies**: ETL Narrative Engine (training data source)
**Estimated Timeline**: 8 weeks to full production deployment
