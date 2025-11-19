# OLMo Fine-Tuning MCP Server - Bootstrap & CodeCarbon Integration

**Created**: 2025-11-18
**Status**: Implementation Guide
**Depends On**: `mcp-server-generator`, `olmo-fine-tuning-mcp-server-spec.md`
**Purpose**: Step-by-step guide to bootstrap OLMo fine-tuning MCP server using existing tooling

---

## Overview

This guide shows how to use your existing **`mcp-server-generator`** to bootstrap the OLMo fine-tuning MCP server, with comprehensive **CodeCarbon integration** for carbon emissions tracking throughout the training pipeline.

### What This Adds

1. ✅ **Bootstrap Instructions**: Use `mcp-server-generator` to create the MCP server scaffold
2. ✅ **CodeCarbon Integration**: Comprehensive emissions tracking at every level
3. ✅ **Tool Definitions**: Ready-to-use `tools.json` for generator
4. ✅ **Implementation Workflow**: Step-by-step development guide

---

## Part 1: Bootstrap with mcp-server-generator

### Step 1: Define Tools

Create `tools.json` with all 6 tools for the OLMo fine-tuning MCP server:

```json
{
  "tools": [
    {
      "name": "generate_fine_tuning_project",
      "description": "Generate a complete fine-tuning project with configurable base model and comprehensive CodeCarbon emissions tracking",
      "parameters": [
        {
          "name": "project_name",
          "type": "string",
          "description": "Name of the fine-tuning project (e.g., 'health-narrative-olmo')",
          "required": true
        },
        {
          "name": "output_dir",
          "type": "string",
          "description": "Directory where project will be created",
          "required": true
        },
        {
          "name": "base_model_config",
          "type": "object",
          "description": "Base model configuration with type, model_id, local_path, and quantization",
          "required": true
        },
        {
          "name": "training_config",
          "type": "object",
          "description": "Training configuration: num_stages, iterations, learning_rate, batch_size, quality_weight_multiplier",
          "required": false
        },
        {
          "name": "lora_config",
          "type": "object",
          "description": "LoRA configuration: rank, alpha, dropout, target_modules",
          "required": false
        },
        {
          "name": "dataset_config",
          "type": "object",
          "description": "Dataset configuration: format, quality_field, instruction_field, output_field",
          "required": false
        },
        {
          "name": "features",
          "type": "object",
          "description": "Feature flags: enable_mlx_optimization, enable_quality_weighting, enable_carbontracking, enable_mlflow, enable_huggingface_upload",
          "required": false
        },
        {
          "name": "carbon_config",
          "type": "object",
          "description": "CodeCarbon configuration: project_name, country_iso_code, offline_mode, emissions_endpoint",
          "required": false
        },
        {
          "name": "integrations",
          "type": "object",
          "description": "Integration URIs: mlflow_tracking_uri, codecarbon_project_name, wandb_project",
          "required": false
        }
      ]
    },
    {
      "name": "configure_training_run",
      "description": "Create a training run configuration for an existing project",
      "parameters": [
        {
          "name": "project_path",
          "type": "string",
          "description": "Path to existing fine-tuning project",
          "required": true
        },
        {
          "name": "run_name",
          "type": "string",
          "description": "Name for this training run (e.g., 'health-narratives-v1')",
          "required": true
        },
        {
          "name": "training_data",
          "type": "object",
          "description": "Training data paths: train_dataset, validation_dataset, test_dataset",
          "required": true
        },
        {
          "name": "override_params",
          "type": "object",
          "description": "Override default training parameters for this run",
          "required": false
        }
      ]
    },
    {
      "name": "start_training",
      "description": "Execute training for a configured run with emissions tracking",
      "parameters": [
        {
          "name": "project_path",
          "type": "string",
          "description": "Path to fine-tuning project",
          "required": true
        },
        {
          "name": "run_id",
          "type": "string",
          "description": "Training run ID",
          "required": true
        },
        {
          "name": "stage",
          "type": "number",
          "description": "Stage to train (1 or 2), or null for auto (both stages)",
          "required": false
        },
        {
          "name": "async_mode",
          "type": "boolean",
          "description": "Run training in background (true) or wait for completion (false)",
          "required": false
        }
      ]
    },
    {
      "name": "monitor_training_progress",
      "description": "Check training progress and carbon emissions metrics",
      "parameters": [
        {
          "name": "project_path",
          "type": "string",
          "description": "Path to fine-tuning project",
          "required": true
        },
        {
          "name": "run_id",
          "type": "string",
          "description": "Training run ID to monitor",
          "required": true
        },
        {
          "name": "include_emissions",
          "type": "boolean",
          "description": "Include CodeCarbon emissions data in response",
          "required": false
        }
      ]
    },
    {
      "name": "evaluate_model",
      "description": "Run evaluation on trained model",
      "parameters": [
        {
          "name": "project_path",
          "type": "string",
          "description": "Path to fine-tuning project",
          "required": true
        },
        {
          "name": "run_id",
          "type": "string",
          "description": "Training run ID",
          "required": true
        },
        {
          "name": "test_dataset",
          "type": "string",
          "description": "Path to test dataset",
          "required": true
        },
        {
          "name": "stage",
          "type": "number",
          "description": "Which stage model to evaluate (1 or 2)",
          "required": true
        }
      ]
    },
    {
      "name": "export_model",
      "description": "Export trained model for deployment",
      "parameters": [
        {
          "name": "project_path",
          "type": "string",
          "description": "Path to fine-tuning project",
          "required": true
        },
        {
          "name": "run_id",
          "type": "string",
          "description": "Training run ID",
          "required": true
        },
        {
          "name": "stage",
          "type": "number",
          "description": "Which stage model to export (1 or 2)",
          "required": true
        },
        {
          "name": "export_format",
          "type": "string",
          "description": "Export format: 'mlx', 'gguf', 'safetensors', or 'huggingface'",
          "required": true
        },
        {
          "name": "export_path",
          "type": "string",
          "description": "Where to export the model",
          "required": true
        },
        {
          "name": "merge_adapters",
          "type": "boolean",
          "description": "Merge LoRA adapters into base model",
          "required": false
        },
        {
          "name": "upload_to_huggingface",
          "type": "boolean",
          "description": "Upload to HuggingFace Hub after export",
          "required": false
        },
        {
          "name": "hf_repo_id",
          "type": "string",
          "description": "HuggingFace repository ID (if uploading)",
          "required": false
        }
      ]
    }
  ]
}
```

### Step 2: Generate MCP Server Scaffold

Use your `mcp-server-generator` to create the boilerplate:

```bash
# Navigate to where you want to create the MCP server
cd ~/projects

# Generate the MCP server scaffold
hitoshura25-mcp-server-generator-cli \
  --project-name olmo-fine-tuning \
  --description "MCP server for generating configurable fine-tuning projects with CodeCarbon emissions tracking" \
  --author "Vinayak Menon" \
  --email "your-email@example.com" \
  --tools-file tools.json \
  --prefix AUTO
```

**What Gets Generated:**
```
hitoshura25-olmo-fine-tuning/
├── .gitignore
├── README.md
├── MCP-USAGE.md
├── LICENSE
├── setup.py
├── pyproject.toml
├── requirements.txt
├── MANIFEST.in
├── hitoshura25_olmo_fine_tuning/
│   ├── __init__.py
│   ├── server.py          # MCP server implementation (generated)
│   ├── cli.py             # CLI interface (generated)
│   ├── generator.py       # Core logic (TODO stubs)
│   └── tests/
│       ├── __init__.py
│       ├── test_server.py
│       └── test_generator.py
└── .github/
    └── workflows/
        └── pypi-publish.yml
```

### Step 3: Implement Core Logic

Now implement the TODO stubs in `generator.py` with the actual fine-tuning project generation logic:

```python
# hitoshura25_olmo_fine_tuning/generator.py

import json
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Environment, FileSystemLoader
import shutil

class FineTuningProjectGenerator:
    """Generate fine-tuning projects with configurable models and CodeCarbon tracking"""

    def __init__(self):
        self.templates_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(loader=FileSystemLoader(str(self.templates_dir)))

    def generate_fine_tuning_project(
        self,
        project_name: str,
        output_dir: str,
        base_model_config: Dict[str, Any],
        training_config: Optional[Dict[str, Any]] = None,
        lora_config: Optional[Dict[str, Any]] = None,
        dataset_config: Optional[Dict[str, Any]] = None,
        features: Optional[Dict[str, Any]] = None,
        carbon_config: Optional[Dict[str, Any]] = None,
        integrations: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate complete fine-tuning project

        Args:
            project_name: Name of the project
            output_dir: Where to create the project
            base_model_config: Model configuration (type, model_id, local_path, quantization)
            training_config: Training parameters
            lora_config: LoRA parameters
            dataset_config: Dataset format and fields
            features: Feature flags (mlx, quality weighting, carbon tracking, etc.)
            carbon_config: CodeCarbon configuration
            integrations: MLflow, Wandb, etc.

        Returns:
            Result dictionary with project path and metadata
        """
        # Set defaults
        features = features or {}
        carbon_config = carbon_config or {}
        training_config = training_config or {}
        lora_config = lora_config or {}

        # Enable CodeCarbon by default
        enable_carbon = features.get("enable_carbontracking", True)

        project_path = Path(output_dir) / project_name
        project_path.mkdir(parents=True, exist_ok=True)

        # Create directory structure
        self._create_directories(project_path)

        # Generate configuration files
        self._generate_config_files(
            project_path,
            project_name,
            base_model_config,
            training_config,
            lora_config,
            dataset_config,
            features,
            carbon_config,
            integrations
        )

        # Copy trainer modules
        self._copy_trainer_modules(
            project_path,
            base_model_config["type"],
            enable_carbon
        )

        # Generate scripts
        self._generate_scripts(project_path, enable_carbon)

        # Generate requirements.txt
        self._generate_requirements(project_path, features)

        # Generate README
        self._generate_readme(project_path, project_name, features)

        # Generate .env.example
        self._generate_env_example(project_path)

        return {
            "success": True,
            "project_path": str(project_path),
            "features_enabled": {
                "mlx_optimization": features.get("enable_mlx_optimization", True),
                "quality_weighting": features.get("enable_quality_weighting", True),
                "carbon_tracking": enable_carbon,
                "mlflow_tracking": features.get("enable_mlflow", False),
                "huggingface_upload": features.get("enable_huggingface_upload", False)
            },
            "carbon_tracking_configured": enable_carbon,
            "next_steps": self._get_next_steps(project_path)
        }

    def _create_directories(self, project_path: Path):
        """Create project directory structure"""
        directories = [
            "config",
            "trainer",
            "data/raw",
            "data/processed",
            "data/quality_reports",
            "runs",
            "scripts",
            "tests",
            "logs",
            "emissions"  # For CodeCarbon reports
        ]

        for dir_path in directories:
            (project_path / dir_path).mkdir(parents=True, exist_ok=True)

    # ... additional methods for generation
```

---

## Part 2: Comprehensive CodeCarbon Integration

### CodeCarbon Architecture

CodeCarbon will be integrated at **three levels**:

```
Level 1: Training Session Tracking (per training run)
         ↓
Level 2: MLflow Integration (logged as metrics)
         ↓
Level 3: Aggregated Reporting (across all runs)
```

### Level 1: Training Session Tracking

**Implementation in Generated Projects** (`trainer/mlx_trainer.py`):

```python
from codecarbon import EmissionsTracker, OfflineEmissionsTracker
from typing import Optional
import mlflow
import time

class CarbonTrackedMLXTrainer:
    """MLX trainer with comprehensive CodeCarbon tracking"""

    def __init__(self, config):
        self.config = config
        self.emissions_tracker: Optional[EmissionsTracker] = None

        # CodeCarbon configuration from project config
        self.carbon_config = config.carbon_tracking

    def _initialize_carbon_tracker(self, run_id: str, stage: int) -> EmissionsTracker:
        """
        Initialize CodeCarbon emissions tracker

        Args:
            run_id: Training run identifier
            stage: Training stage (1 or 2)

        Returns:
            Configured EmissionsTracker instance
        """
        # Determine online vs offline mode
        use_online = not self.carbon_config.get("offline_mode", False)

        tracker_kwargs = {
            "project_name": f"{self.carbon_config.get('project_name', 'fine-tuning')}-stage{stage}",
            "output_dir": str(self.config.project_path / "emissions"),
            "output_file": f"{run_id}_stage{stage}_emissions.csv",
            "tracking_mode": "process",  # Track only this process
            "log_level": "INFO",
            "save_to_file": True,
            "save_to_logger": True,
            "gpu_ids": None  # Track all GPUs
        }

        if use_online:
            # Online mode: fetch live carbon intensity data
            tracker = EmissionsTracker(
                **tracker_kwargs,
                country_iso_code=self.carbon_config.get("country_iso_code", "USA"),
                emissions_endpoint=self.carbon_config.get(
                    "emissions_endpoint",
                    "https://api.electricitymap.org/v3/carbon-intensity/latest"
                )
            )
        else:
            # Offline mode: use static regional data
            tracker = OfflineEmissionsTracker(
                **tracker_kwargs,
                country_iso_code=self.carbon_config.get("country_iso_code", "USA")
            )

        return tracker

    async def train_stage(
        self,
        stage: int,
        train_dataset: Path,
        val_dataset: Path,
        output_dir: Path,
        run_id: str
    ) -> Dict[str, Any]:
        """
        Train a single stage with comprehensive carbon tracking

        Returns training metrics AND emissions data
        """
        # Initialize carbon tracker
        self.emissions_tracker = self._initialize_carbon_tracker(run_id, stage)

        # Start tracking
        self.emissions_tracker.start()
        start_time = time.time()

        try:
            # Run MLX training
            training_result = await self._run_mlx_training(
                train_dataset,
                val_dataset,
                output_dir
            )

            # Stop tracking and get emissions
            emissions_data = self.emissions_tracker.stop()

            training_duration = time.time() - start_time

            # Build comprehensive result
            result = {
                **training_result,
                "carbon_emissions": {
                    "total_emissions_kg_co2": round(emissions_data, 6),
                    "duration_hours": round(training_duration / 3600, 2),
                    "emissions_per_hour_kg": round(emissions_data / (training_duration / 3600), 6),
                    "emissions_file": str(self.config.project_path / "emissions" / f"{run_id}_stage{stage}_emissions.csv")
                }
            }

            # Log to MLflow if enabled
            if self.config.mlflow_enabled:
                self._log_emissions_to_mlflow(emissions_data, training_duration, stage)

            return result

        except Exception as e:
            # Ensure tracker is stopped even on failure
            if self.emissions_tracker:
                self.emissions_tracker.stop()
            raise

    def _log_emissions_to_mlflow(
        self,
        emissions_kg: float,
        duration_seconds: float,
        stage: int
    ):
        """Log carbon emissions to MLflow"""

        # Log primary emission metric
        mlflow.log_metric(f"stage{stage}_carbon_emissions_kg_co2", emissions_kg)
        mlflow.log_metric(f"stage{stage}_training_duration_hours", duration_seconds / 3600)
        mlflow.log_metric(f"stage{stage}_emissions_per_hour_kg", emissions_kg / (duration_seconds / 3600))

        # Log detailed breakdown if available
        if hasattr(self.emissions_tracker, "_total_energy"):
            mlflow.log_metric(f"stage{stage}_energy_consumed_kwh", self.emissions_tracker._total_energy.kWh)
            mlflow.log_metric(f"stage{stage}_cpu_energy_kwh", self.emissions_tracker._cpu_energy.kWh)
            mlflow.log_metric(f"stage{stage}_gpu_energy_kwh", self.emissions_tracker._gpu_energy.kWh)
            mlflow.log_metric(f"stage{stage}_ram_energy_kwh", self.emissions_tracker._ram_energy.kWh)

        # Log carbon intensity (gCO2/kWh)
        if hasattr(self.emissions_tracker, "_carbon_intensity"):
            mlflow.log_metric(f"stage{stage}_carbon_intensity_gco2_kwh", self.emissions_tracker._carbon_intensity)

        # Log emissions CSV as artifact
        emissions_file = self.config.project_path / "emissions" / f"stage{stage}_emissions.csv"
        if emissions_file.exists():
            mlflow.log_artifact(str(emissions_file), artifact_path=f"emissions/stage{stage}")
```

### Level 2: Real-Time Emissions Monitoring

**FastAPI Endpoint in Generated Projects** (`scripts/monitor_training.py`):

```python
from fastapi import FastAPI, HTTPException
from pathlib import Path
import pandas as pd
from typing import Dict, Any, List

app = FastAPI(title="Training Emissions Monitor")

@app.get("/emissions/{run_id}/current")
async def get_current_emissions(run_id: str) -> Dict[str, Any]:
    """
    Get real-time emissions data for a running training job

    Returns:
        Current emissions metrics and projections
    """
    emissions_dir = Path("./emissions")
    emissions_files = list(emissions_dir.glob(f"{run_id}_*.csv"))

    if not emissions_files:
        raise HTTPException(status_code=404, detail=f"No emissions data found for run {run_id}")

    # Load most recent emissions file
    latest_file = max(emissions_files, key=lambda p: p.stat().st_mtime)
    df = pd.read_csv(latest_file)

    # Get latest row
    latest = df.iloc[-1]

    return {
        "run_id": run_id,
        "current_emissions_kg_co2": float(latest.get("emissions", 0)),
        "duration_seconds": float(latest.get("duration", 0)),
        "energy_consumed_kwh": float(latest.get("energy_consumed", 0)),
        "cpu_power_w": float(latest.get("cpu_power", 0)),
        "gpu_power_w": float(latest.get("gpu_power", 0)),
        "ram_power_w": float(latest.get("ram_power", 0)),
        "carbon_intensity_gco2_kwh": float(latest.get("carbon_intensity", 0)),
        "country": str(latest.get("country_name", "Unknown")),
        "timestamp": str(latest.get("timestamp", "")),
        "emissions_file": str(latest_file)
    }

@app.get("/emissions/{run_id}/summary")
async def get_emissions_summary(run_id: str) -> Dict[str, Any]:
    """
    Get comprehensive emissions summary with equivalencies

    Returns:
        Total emissions, equivalencies (miles driven, trees needed), recommendations
    """
    emissions_dir = Path("./emissions")
    emissions_files = list(emissions_dir.glob(f"{run_id}_*.csv"))

    if not emissions_files:
        raise HTTPException(status_code=404, detail=f"No emissions data found for run {run_id}")

    # Load and aggregate all stage emissions
    total_emissions = 0
    total_duration = 0
    stages_data = []

    for file in sorted(emissions_files):
        df = pd.read_csv(file)
        latest = df.iloc[-1]

        stage_emissions = float(latest.get("emissions", 0))
        stage_duration = float(latest.get("duration", 0))

        total_emissions += stage_emissions
        total_duration += stage_duration

        stages_data.append({
            "file": file.name,
            "emissions_kg": stage_emissions,
            "duration_hours": stage_duration / 3600
        })

    # Calculate equivalencies
    miles_driven = total_emissions * 2.4  # avg car: 0.41 kg CO2/mile
    trees_needed_per_year = total_emissions / 21  # 1 tree absorbs ~21 kg CO2/year
    smartphones_charged = total_emissions * 121.6  # 1 kg CO2 = 121 charges

    # Generate recommendations
    recommendations = _generate_emissions_recommendations(total_emissions, total_duration / 3600)

    return {
        "run_id": run_id,
        "summary": {
            "total_emissions_kg_co2": round(total_emissions, 6),
            "total_duration_hours": round(total_duration / 3600, 2),
            "emissions_per_hour_kg": round(total_emissions / (total_duration / 3600), 6),
            "num_stages": len(stages_data)
        },
        "equivalencies": {
            "miles_driven_equivalent": round(miles_driven, 1),
            "trees_to_offset_1year": round(trees_needed_per_year, 1),
            "smartphones_charged": round(smartphones_charged, 0)
        },
        "stages": stages_data,
        "recommendations": recommendations,
        "carbon_offset_cost_usd": round(total_emissions * 0.50, 2)  # $0.50/kg CO2
    }

def _generate_emissions_recommendations(
    emissions_kg: float,
    duration_hours: float
) -> List[str]:
    """Generate personalized emissions reduction recommendations"""

    recommendations = []

    if emissions_kg > 5.0:
        recommendations.append(
            "💡 High emissions detected. Consider using cloud regions with lower carbon intensity "
            "(e.g., Quebec/Norway: hydro, France: nuclear)"
        )
        recommendations.append(
            "⏰ Schedule training during off-peak hours when grid is cleaner (typically 10pm-6am)"
        )

    if duration_hours > 12:
        recommendations.append(
            "⚡ Long training duration. Consider using smaller model variants (e.g., OLMo-1B instead of OLMo-7B) "
            "for faster iteration"
        )
        recommendations.append(
            "🛑 Implement early stopping to reduce unnecessary training epochs"
        )

    if emissions_kg > 0.5:
        recommendations.append(
            f"🌳 Offset {emissions_kg:.2f} kg CO2 through carbon credit purchases "
            f"(~${emissions_kg * 0.50:.2f}) or plant ~{emissions_kg / 21:.1f} trees"
        )

    recommendations.append(
        "📊 Track emissions trends over time to identify optimization opportunities"
    )

    return recommendations

@app.get("/emissions/aggregate")
async def get_aggregate_emissions() -> Dict[str, Any]:
    """
    Get aggregate emissions across all training runs

    Returns:
        Total footprint, trends, top emitting runs
    """
    emissions_dir = Path("./emissions")
    all_files = list(emissions_dir.glob("*_emissions.csv"))

    if not all_files:
        return {"total_emissions_kg_co2": 0, "total_runs": 0}

    total_emissions = 0
    total_duration = 0
    runs_data = []

    for file in all_files:
        df = pd.read_csv(file)
        latest = df.iloc[-1]

        emissions = float(latest.get("emissions", 0))
        duration = float(latest.get("duration", 0))

        total_emissions += emissions
        total_duration += duration

        runs_data.append({
            "file": file.name,
            "emissions_kg": emissions,
            "duration_hours": duration / 3600,
            "timestamp": str(latest.get("timestamp", ""))
        })

    # Sort by emissions (descending)
    runs_data = sorted(runs_data, key=lambda x: x["emissions_kg"], reverse=True)

    return {
        "total_emissions_kg_co2": round(total_emissions, 3),
        "total_duration_hours": round(total_duration / 3600, 2),
        "total_runs": len(runs_data),
        "average_per_run_kg": round(total_emissions / len(runs_data), 3) if runs_data else 0,
        "trees_to_offset_1year": round(total_emissions / 21, 1),
        "top_emitting_runs": runs_data[:10],
        "total_offset_cost_usd": round(total_emissions * 0.50, 2)
    }
```

### Level 3: Emissions Dashboard (Streamlit)

**Generated in Projects** (`scripts/emissions_dashboard.py`):

```python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

st.set_page_config(page_title="Training Emissions Dashboard", layout="wide")

st.title("🌍 Training Carbon Emissions Dashboard")

# Load all emissions data
emissions_dir = Path("./emissions")
all_files = list(emissions_dir.glob("*_emissions.csv"))

if not all_files:
    st.warning("No emissions data found. Run a training session first.")
    st.stop()

# Aggregate data
all_data = []
for file in all_files:
    df = pd.read_csv(file)
    df["run_id"] = file.stem.rsplit("_", 2)[0]
    df["stage"] = file.stem.rsplit("_", 1)[0].split("_")[-1]
    all_data.append(df)

emissions_df = pd.concat(all_data, ignore_index=True)
emissions_df["timestamp"] = pd.to_datetime(emissions_df["timestamp"])

# Key Metrics
st.header("📊 Key Metrics")

col1, col2, col3, col4 = st.columns(4)

total_emissions = emissions_df["emissions"].sum()
total_runs = emissions_df["run_id"].nunique()
avg_emissions = total_emissions / total_runs if total_runs > 0 else 0
trees_needed = total_emissions / 21

col1.metric("Total Emissions", f"{total_emissions:.3f} kg CO₂")
col2.metric("Total Runs", total_runs)
col3.metric("Avg per Run", f"{avg_emissions:.3f} kg CO₂")
col4.metric("Trees to Offset (1 yr)", f"{trees_needed:.1f}")

# Emissions Over Time
st.header("📈 Emissions Trends")

fig_timeline = px.line(
    emissions_df,
    x="timestamp",
    y="emissions",
    color="run_id",
    title="Cumulative Emissions Over Time"
)
st.plotly_chart(fig_timeline, use_container_width=True)

# Emissions by Run
st.header("🏃 Emissions by Training Run")

run_emissions = emissions_df.groupby("run_id")["emissions"].sum().reset_index()
run_emissions = run_emissions.sort_values("emissions", ascending=False)

fig_runs = px.bar(
    run_emissions,
    x="run_id",
    y="emissions",
    title="Total Emissions per Training Run",
    labels={"emissions": "Emissions (kg CO₂)", "run_id": "Run ID"}
)
st.plotly_chart(fig_runs, use_container_width=True)

# Energy Breakdown
st.header("⚡ Energy Consumption Breakdown")

col1, col2 = st.columns(2)

with col1:
    energy_breakdown = pd.DataFrame({
        "Component": ["CPU", "GPU", "RAM"],
        "Energy (kWh)": [
            emissions_df["cpu_energy"].sum(),
            emissions_df["gpu_energy"].sum(),
            emissions_df["ram_energy"].sum()
        ]
    })

    fig_energy = px.pie(
        energy_breakdown,
        values="Energy (kWh)",
        names="Component",
        title="Energy Consumption by Component"
    )
    st.plotly_chart(fig_energy, use_container_width=True)

with col2:
    power_over_time = emissions_df.groupby("timestamp").agg({
        "cpu_power": "mean",
        "gpu_power": "mean",
        "ram_power": "mean"
    }).reset_index()

    fig_power = go.Figure()
    fig_power.add_trace(go.Scatter(x=power_over_time["timestamp"], y=power_over_time["cpu_power"], name="CPU", mode="lines"))
    fig_power.add_trace(go.Scatter(x=power_over_time["timestamp"], y=power_over_time["gpu_power"], name="GPU", mode="lines"))
    fig_power.add_trace(go.Scatter(x=power_over_time["timestamp"], y=power_over_time["ram_power"], name="RAM", mode="lines"))
    fig_power.update_layout(title="Power Consumption Over Time", yaxis_title="Power (W)")

    st.plotly_chart(fig_power, use_container_width=True)

# Carbon Intensity
st.header("🌐 Carbon Intensity Trends")

fig_intensity = px.line(
    emissions_df,
    x="timestamp",
    y="carbon_intensity",
    title="Grid Carbon Intensity Over Time",
    labels={"carbon_intensity": "Carbon Intensity (gCO₂/kWh)"}
)
st.plotly_chart(fig_intensity, use_container_width=True)

# Recommendations
st.header("💡 Optimization Recommendations")

if total_emissions > 5.0:
    st.warning("⚠️ High emissions detected across training runs")
    st.info("💡 **Recommendation**: Schedule training during off-peak hours (typically 10pm-6am) when grid is cleaner")
    st.info("🌍 **Recommendation**: Use cloud regions with low carbon intensity (Quebec, Norway, France)")

st.success(f"🌳 **Carbon Offset**: Plant {trees_needed:.1f} trees or purchase carbon credits (~${total_emissions * 0.50:.2f})")

# Raw Data
st.header("📋 Raw Emissions Data")
st.dataframe(emissions_df)
```

### Usage:
```bash
# Start emissions dashboard
streamlit run scripts/emissions_dashboard.py
```

---

## Part 3: Updated Configuration Template

**Generated `config/fine_tuning_config.yaml`** with CodeCarbon:

```yaml
# Generated Fine-Tuning Configuration with CodeCarbon Integration

project:
  name: "{{ project_name }}"
  description: "Auto-generated fine-tuning project with comprehensive emissions tracking"
  version: "1.0.0"

base_model:
  type: "{{ base_model.type }}"
  model_id: "{{ base_model.model_id }}"
  {% if base_model.local_path %}
  local_path: "{{ base_model.local_path }}"
  {% endif %}
  quantization: "{{ base_model.quantization | default('q4') }}"

# ... training, lora, dataset sections ...

# CodeCarbon Configuration
carbon_tracking:
  enabled: {{ features.enable_carbontracking | default(true) }}
  project_name: "{{ carbon_config.project_name | default(project_name) }}"
  country_iso_code: "{{ carbon_config.country_iso_code | default('USA') }}"
  offline_mode: {{ carbon_config.offline_mode | default(false) }}

  # Online mode configuration (fetch live carbon intensity)
  {% if not carbon_config.offline_mode %}
  emissions_endpoint: "{{ carbon_config.emissions_endpoint | default('https://api.electricitymap.org/v3/carbon-intensity/latest') }}"
  {% endif %}

  # Output configuration
  output_dir: "./emissions"
  save_to_file: true
  save_to_logger: true
  tracking_mode: "process"  # Track only training process
  log_level: "INFO"

  # GPU tracking
  track_all_gpus: true

  # Emissions thresholds for alerts
  alerts:
    high_emissions_kg: 10.0  # Alert if single run exceeds this
    high_emissions_per_hour_kg: 2.0  # Alert if rate exceeds this

# MLflow Integration (for emissions logging)
mlflow:
  enabled: {{ features.enable_mlflow | default(false) }}
  tracking_uri: "{{ integrations.mlflow_tracking_uri | default('http://localhost:5000') }}"
  experiment_name: "{{ project_name }}-training"

  # Log emissions to MLflow
  log_emissions: {{ features.enable_carbontracking | default(true) }}
  emissions_artifact_path: "emissions_reports"
```

---

## Part 4: Updated Requirements.txt

**Generated `requirements.txt`** with CodeCarbon:

```txt
# Base requirements
pydantic==2.11.9
pydantic-settings==2.11.0
PyYAML==6.0.3
datasets==4.1.1
transformers==4.57.0
torch==2.8.0
Jinja2==3.1.6

# CodeCarbon for emissions tracking
codecarbon==2.3.4
pandas==2.2.3  # Required by CodeCarbon
requests==2.32.3  # For online carbon intensity API

{% if features.enable_mlx_optimization %}
# MLX optimization (Apple Silicon)
mlx==0.29.2
mlx-lm==0.27.1
{% endif %}

{% if features.enable_mlflow %}
# MLflow for experiment tracking
mlflow==2.10.2
{% endif %}

{% if features.enable_huggingface_upload %}
# HuggingFace Hub upload
huggingface-hub==0.35.3
{% endif %}

# Emissions dashboard (optional)
streamlit==1.39.0  # For emissions visualization
plotly==5.24.0  # For interactive charts
```

---

## Part 5: Bootstrap Workflow Summary

### Complete Setup Process

```bash
# 1. Create tools.json (from Part 1)
cat > tools.json <<'EOF'
{
  "tools": [ ... ]  # Copy from Part 1
}
EOF

# 2. Generate MCP server scaffold
hitoshura25-mcp-server-generator-cli \
  --project-name olmo-fine-tuning \
  --description "MCP server for generating fine-tuning projects with CodeCarbon emissions tracking" \
  --author "Vinayak Menon" \
  --email "your@email.com" \
  --tools-file tools.json \
  --prefix AUTO

# 3. Navigate to generated project
cd hitoshura25-olmo-fine-tuning

# 4. Create templates directory
mkdir -p hitoshura25_olmo_fine_tuning/templates/trainer_modules
mkdir -p hitoshura25_olmo_fine_tuning/templates/scripts
mkdir -p hitoshura25_olmo_fine_tuning/templates/config

# 5. Add template files (Jinja2 templates for generated projects)
# - config/fine_tuning_config.yaml.jinja
# - trainer_modules/mlx_trainer.py.jinja (with CodeCarbon integration)
# - scripts/train.py.jinja
# - scripts/monitor_emissions.py.jinja
# - scripts/emissions_dashboard.py.jinja
# - README.md.jinja

# 6. Implement generator.py logic (from Part 2)
# Copy the FineTuningProjectGenerator class

# 7. Update requirements.txt
echo "codecarbon==2.3.4" >> requirements.txt
echo "streamlit==1.39.0" >> requirements.txt
echo "plotly==5.24.0" >> requirements.txt

# 8. Install and test
pip install -e .
pytest

# 9. Publish to PyPI (optional)
# GitHub Actions workflow already generated by mcp-server-generator
git add .
git commit -m "Implement OLMo fine-tuning MCP server with CodeCarbon integration"
git push origin main
# Workflow triggers on tag: git tag v0.1.0 && git push origin v0.1.0
```

### Using the Generated MCP Server

```bash
# Install from PyPI (after publishing)
pip install hitoshura25-olmo-fine-tuning

# Configure in Claude Code
cat >> ~/.config/claude-code/config.json <<'EOF'
{
  "mcpServers": {
    "olmo-fine-tuning": {
      "command": "hitoshura25-olmo-fine-tuning"
    }
  }
}
EOF

# Use in Claude Code
# Claude can now generate fine-tuning projects with:
# /tool-call generate_fine_tuning_project ...
```

---

## Summary

### What You Get

1. ✅ **Rapid Bootstrap**: Use existing `mcp-server-generator` to create scaffold in 5 minutes
2. ✅ **Comprehensive CodeCarbon**: Tracking at training, monitoring, and aggregate levels
3. ✅ **Emissions Dashboard**: Streamlit app with interactive charts
4. ✅ **MLflow Integration**: Emissions logged alongside training metrics
5. ✅ **Real-Time Monitoring**: FastAPI endpoints for live emissions data
6. ✅ **Recommendations**: Automated suggestions for reducing carbon footprint

### Development Timeline

**Week 1**: Bootstrap & Core Logic
- Use mcp-server-generator (5 minutes)
- Implement generator.py (2-3 days)
- Create Jinja2 templates (2-3 days)

**Week 2**: CodeCarbon Integration
- Add emissions tracking to trainers (2 days)
- Create monitoring endpoints (1 day)
- Build Streamlit dashboard (2 days)

**Week 3**: Testing & Documentation
- Write tests (2 days)
- Update documentation (1 day)
- Publish to PyPI (1 day)

**Total: 3 weeks** (vs. 6-8 weeks from scratch)

### Next Steps

1. ✅ Review this spec and `olmo-fine-tuning-mcp-server-spec.md`
2. Create `tools.json` from Part 1
3. Run `mcp-server-generator` to bootstrap
4. Implement `generator.py` with CodeCarbon integration
5. Test with health-narrative-olmo project
6. Publish to PyPI

The MCP server is ready to build! 🚀
