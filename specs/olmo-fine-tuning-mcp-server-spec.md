# OLMo Fine-Tuning MCP Server - Specification

**Created**: 2025-11-18
**Status**: Draft Specification
**Type**: MCP Server Tool
**Source**: Generalized from `mpo-api-authn-server/security-ai-analysis`

---

## Executive Summary

This specification defines an **MCP (Model Context Protocol) server** that provides generalized, configurable fine-tuning capabilities for language models, based on the proven architecture from your security AI analysis project.

### Value Proposition

**Instead of:** Manually copying and adapting training code for each new project
**You Get:** An MCP server that generates complete, production-ready fine-tuning pipelines with a single tool call

### Key Benefits

✅ **Reusability**: One MCP server powers fine-tuning across multiple projects
✅ **Configurability**: Supports multiple base models (OLMo, Llama, Mistral, etc.)
✅ **Proven Architecture**: Based on your working security AI training system
✅ **MLX Optimization**: Apple Silicon optimization with 3-4X performance improvement
✅ **Sequential Training**: 2-stage fine-tuning with catastrophic forgetting prevention
✅ **Quality-Weighted Sampling**: Intelligent dataset balancing (2.5X boost for high-quality data)

---

## Part 1: Architecture Analysis - Existing System

### Current System Components (from security-ai-analysis)

Your existing training system has these sophisticated components:

#### 1. **Configuration Management** (`config_manager.py`)
```python
class OLMoSecurityConfig:
    """
    Unified configuration with environment variable overrides

    Features:
    - External model directories (shareable across projects)
    - Fine-tuning parameters (learning rate, batch size, iterations)
    - LoRA configuration (rank, alpha, dropout, target modules)
    - MLX optimization settings
    - HuggingFace upload configuration
    - Multi-domain validation thresholds
    """
```

**Key Patterns to Extract:**
- Environment variable override system (`OLMO_*` prefix)
- Structured configuration sections (fine_tuning, knowledge_base, validation)
- Path resolution with `expanduser()` support
- Fail-fast validation

#### 2. **MLX Trainer** (`mlx_trainer.py`)
```python
class MLXTrainer:
    """
    MLX-optimized training with quality-weighted sampling

    Features:
    - Quality-weighted dataset duplication (2.5X for high-quality examples)
    - Sequential 2-stage training (general → domain-specific)
    - LoRA adapter resumption for Stage 2
    - Automatic metadata saving for reproducibility
    """
```

**Key Patterns to Extract:**
- Quality weighting algorithm (lines 66-141)
- MLX command generation (lines 197-208)
- Adapter resumption for continuing training (lines 427-492)
- Training metadata persistence

#### 3. **Training Run Manager** (`training_run_manager.py`)
```python
class TrainingRunManager:
    """
    Structured training run management with manifest-based tracking

    Features:
    - Hierarchical directory structure (stage1/stage2 isolation)
    - JSON manifest for artifact tracking (v2.0 format)
    - MLX data format handling (train.jsonl/valid.jsonl)
    - Evaluation result persistence
    """
```

**Key Patterns to Extract:**
- Run manifest schema (lines 20-69)
- Directory structure generation (lines 265-348)
- Stage isolation pattern
- Artifact path resolution

#### 4. **Model Analyzer** (`olmo_analyzer.py`)
```python
class OLMoSecurityAnalyzer:
    """
    MLX-optimized inference with dual-mode support

    Features:
    - MLX-optimized loading (3-4X faster on Apple Silicon)
    - Transformers fallback for non-MLX environments
    - Configurable generation parameters
    - Template-based fallback for model failures
    """
```

**Key Patterns to Extract:**
- MLX vs transformers detection logic (lines 103-110)
- Generation parameter configuration (temperature, top_p, max_tokens)
- Fail-fast error handling

### Reusable Abstractions Identified

| Component | Abstraction | Configurable Parameters |
|-----------|------------|------------------------|
| **Configuration** | `BaseFineTuningConfig` | model_name, base_model_id, learning_rate, batch_size, lora_config |
| **Trainer** | `GenericMLXTrainer` | quality_weight_multiplier, num_stages, stage_iterations |
| **Run Manager** | `TrainingRunManager` | output_dir, manifest_version, stage_count |
| **Dataset Handler** | `DatasetPreparator` | format (jsonl, csv, parquet), quality_field, split_ratios |

---

## Part 2: MCP Server Design

### MCP Server Overview

```
┌─────────────────────────────────────────────────┐
│  OLMo Fine-Tuning MCP Server                    │
│                                                  │
│  Tools:                                          │
│  1. generate_fine_tuning_project                │
│  2. configure_training_run                       │
│  3. start_training                               │
│  4. monitor_training_progress                    │
│  5. evaluate_model                               │
│  6. export_model                                 │
└─────────────────────────────────────────────────┘
           │
           ▼
    Generated Project
           │
           ▼
┌─────────────────────────────────────────────────┐
│  {project_name}/                                 │
│  ├── config/                                     │
│  │   └── fine_tuning_config.yaml               │
│  ├── trainer/                                    │
│  │   ├── mlx_trainer.py                         │
│  │   └── training_run_manager.py               │
│  ├── data/                                       │
│  │   ├── train.jsonl                            │
│  │   └── valid.jsonl                            │
│  ├── scripts/                                    │
│  │   ├── train.py                               │
│  │   ├── evaluate.py                            │
│  │   └── export.py                              │
│  ├── requirements.txt                            │
│  └── README.md                                   │
└─────────────────────────────────────────────────┘
```

### Tool 1: `generate_fine_tuning_project`

**Purpose**: Generate a complete fine-tuning project with configurable base model

**Input Parameters**:
```python
{
    "project_name": str,  # e.g., "health-narrative-training"
    "output_dir": str,    # e.g., "./fine-tuning-projects"

    # Model Configuration
    "base_model": {
        "type": "olmo" | "llama" | "mistral" | "custom",
        "model_id": str,  # e.g., "allenai/OLMo-2-0425-1B-Instruct"
        "local_path": Optional[str],  # Path to local model
        "quantization": "q4" | "q8" | "none"
    },

    # Training Configuration
    "training": {
        "num_stages": 1 | 2,  # Single-stage or sequential
        "stage1_iterations": int,  # Default: 100
        "stage2_iterations": int,  # Default: 150 (if 2-stage)
        "learning_rate": float,   # Default: 2e-5
        "stage2_learning_rate": float,  # Default: 1e-6 (if 2-stage)
        "batch_size": int,  # Default: 4
        "quality_weight_multiplier": float  # Default: 2.5
    },

    # LoRA Configuration
    "lora": {
        "rank": int,  # Default: 8
        "alpha": int,  # Default: 16
        "dropout": float,  # Default: 0.05
        "target_modules": List[str]  # Default: ["q_proj", "v_proj"]
    },

    # Dataset Configuration
    "dataset": {
        "format": "jsonl" | "csv" | "parquet",
        "quality_field": Optional[str],  # For quality-weighted sampling
        "instruction_field": str,  # Default: "instruction"
        "output_field": str,  # Default: "output"
        "metadata_field": Optional[str]  # Default: "metadata"
    },

    # Features
    "features": {
        "enable_mlx_optimization": bool,  # Default: True (Apple Silicon)
        "enable_quality_weighting": bool,  # Default: True
        "enable_carbontracking": bool,  # Default: True
        "enable_huggingface_upload": bool,  # Default: False
        "enable_evaluation": bool  # Default: True
    },

    # Optional Integrations
    "integrations": {
        "mlflow_tracking_uri": Optional[str],
        "codecarbon_project_name": Optional[str],
        "wandb_project": Optional[str]
    }
}
```

**Output**:
```python
{
    "success": bool,
    "project_path": str,  # Absolute path to generated project
    "project_structure": {
        "config_file": str,
        "trainer_modules": List[str],
        "scripts": List[str],
        "requirements_file": str
    },
    "next_steps": List[str],  # Instructions for using the project
    "command_examples": {
        "train": str,  # Example: "python scripts/train.py --config config/fine_tuning_config.yaml"
        "evaluate": str,
        "export": str
    }
}
```

### Tool 2: `configure_training_run`

**Purpose**: Create a training run configuration for an existing project

**Input Parameters**:
```python
{
    "project_path": str,
    "run_name": str,  # e.g., "health-narratives-v1"
    "training_data": {
        "train_dataset": str,  # Path to train.jsonl
        "validation_dataset": str,  # Path to valid.jsonl
        "test_dataset": Optional[str]  # Path to test.jsonl
    },
    "override_params": Optional[Dict]  # Override default training params
}
```

**Output**:
```python
{
    "success": bool,
    "run_id": str,
    "run_directory": str,
    "manifest_path": str,
    "configuration_summary": Dict
}
```

### Tool 3: `start_training`

**Purpose**: Execute training for a configured run

**Input Parameters**:
```python
{
    "project_path": str,
    "run_id": str,
    "stage": 1 | 2 | None,  # None = auto (both stages if configured)
    "async_mode": bool  # True = return immediately, False = wait for completion
}
```

**Output**:
```python
{
    "success": bool,
    "run_id": str,
    "training_started": bool,
    "estimated_duration_minutes": int,
    "log_file": str,
    "monitor_command": str  # Command to monitor progress
}
```

### Tool 4: `monitor_training_progress`

**Purpose**: Check training progress and metrics

**Input Parameters**:
```python
{
    "project_path": str,
    "run_id": str
}
```

**Output**:
```python
{
    "run_id": str,
    "status": "running" | "completed" | "failed" | "not_started",
    "current_stage": 1 | 2 | None,
    "current_iteration": int,
    "total_iterations": int,
    "progress_percentage": float,
    "metrics": {
        "train_loss": float,
        "learning_rate": float,
        "tokens_per_second": float
    },
    "carbon_emissions_kg": Optional[float],
    "estimated_completion_time": Optional[str]
}
```

### Tool 5: `evaluate_model`

**Purpose**: Run evaluation on trained model

**Input Parameters**:
```python
{
    "project_path": str,
    "run_id": str,
    "test_dataset": str,
    "stage": 1 | 2  # Which stage model to evaluate
}
```

**Output**:
```python
{
    "success": bool,
    "run_id": str,
    "stage": int,
    "evaluation_results": {
        "accuracy": float,
        "perplexity": float,
        "custom_metrics": Dict
    },
    "results_file": str
}
```

### Tool 6: `export_model`

**Purpose**: Export trained model for deployment

**Input Parameters**:
```python
{
    "project_path": str,
    "run_id": str,
    "stage": 1 | 2,
    "export_format": "mlx" | "gguf" | "safetensors" | "huggingface",
    "export_path": str,
    "merge_adapters": bool,  # Merge LoRA adapters into base model
    "upload_to_huggingface": bool,
    "hf_repo_id": Optional[str]
}
```

**Output**:
```python
{
    "success": bool,
    "export_path": str,
    "export_format": str,
    "model_size_mb": float,
    "huggingface_url": Optional[str],
    "usage_instructions": str
}
```

---

## Part 3: Generated Project Structure

### Directory Layout

```
{project_name}/
├── config/
│   ├── fine_tuning_config.yaml      # Main configuration
│   └── model_config.json            # Model-specific settings
│
├── trainer/
│   ├── __init__.py
│   ├── base_trainer.py              # Abstract base trainer
│   ├── mlx_trainer.py               # MLX-optimized trainer
│   ├── transformers_trainer.py      # HuggingFace transformers fallback
│   ├── training_run_manager.py      # Run management with manifests
│   └── dataset_preparator.py        # Dataset loading and weighting
│
├── data/
│   ├── raw/                         # Original datasets
│   ├── processed/                   # Processed datasets
│   │   ├── train.jsonl
│   │   └── valid.jsonl
│   └── quality_reports/             # Data quality analysis
│
├── runs/
│   └── {run_name}-{timestamp}/
│       ├── run-manifest.json        # Training run metadata
│       ├── stage1/
│       │   ├── adapters/
│       │   ├── training-data/
│       │   └── evaluation/
│       ├── stage2/                  # (if 2-stage)
│       │   ├── adapters/
│       │   ├── training-data/
│       │   └── evaluation/
│       └── final-model/
│
├── scripts/
│   ├── train.py                     # Training entry point
│   ├── evaluate.py                  # Evaluation script
│   ├── export.py                    # Model export utility
│   └── prepare_dataset.py           # Dataset preparation
│
├── tests/
│   ├── test_trainer.py
│   ├── test_dataset.py
│   └── test_config.py
│
├── logs/
│   └── training-{timestamp}.log
│
├── .env.example                     # Environment variable template
├── requirements.txt                 # Python dependencies
├── README.md                        # Project documentation
└── pyproject.toml                   # Python project metadata
```

### Configuration File Format

```yaml
# config/fine_tuning_config.yaml

# Project Metadata
project:
  name: "health-narrative-training"
  description: "Fine-tuning OLMo for health narrative generation"
  version: "1.0.0"

# Base Model Configuration
base_model:
  type: "olmo"
  model_id: "allenai/OLMo-2-0425-1B-Instruct"
  local_path: "~/ai-models/OLMo-2-1B-mlx-q4"
  quantization: "q4"

# Training Configuration
training:
  num_stages: 2

  # Stage 1: General Training
  stage1:
    iterations: 100
    learning_rate: 2.0e-5
    batch_size: 4
    warmup_steps: 10

  # Stage 2: Domain Specialization
  stage2:
    iterations: 150
    learning_rate: 1.0e-6
    batch_size: 4
    replay_ratio: 0.15  # 15% Stage 1 data for forgetting prevention

  # General Settings
  quality_weight_multiplier: 2.5
  save_steps: 50
  eval_steps: 25
  gradient_checkpointing: true

# LoRA Configuration
lora:
  rank: 8
  alpha: 16
  dropout: 0.05
  target_modules:
    - "q_proj"
    - "v_proj"
    - "k_proj"
    - "o_proj"

# Dataset Configuration
dataset:
  format: "jsonl"
  quality_field: "quality"
  instruction_field: "instruction"
  output_field: "output"
  metadata_field: "metadata"

  # Split ratios
  train_split: 0.8
  validation_split: 0.1
  test_split: 0.1

# MLX Optimization (Apple Silicon)
mlx:
  enabled: true
  memory_efficient: true
  gradient_checkpointing: true

# CodeCarbon Tracking
carbon_tracking:
  enabled: true
  project_name: "health-narrative-olmo"
  country_iso_code: "USA"
  output_dir: "./emissions"

# MLflow Integration
mlflow:
  enabled: false
  tracking_uri: "http://localhost:5000"
  experiment_name: "health-narrative-training"

# HuggingFace Upload
huggingface:
  enabled: false
  repo_prefix: "your-username"
  private_repos: true
  upload_staging_dir: "./upload_staging"

# Evaluation Configuration
evaluation:
  enabled: true
  metrics:
    - "perplexity"
    - "accuracy"
    - "bleu"

  # Validation thresholds
  stage1_threshold: 0.7
  stage2_threshold: 0.7
  sequential_threshold: 0.6
```

---

## Part 4: Implementation Details

### Core Module: `base_trainer.py`

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml

@dataclass
class TrainingConfig:
    """Training configuration data class"""
    model_type: str
    model_id: str
    local_path: Optional[Path]
    num_stages: int
    learning_rate: float
    batch_size: int
    lora_rank: int
    lora_alpha: int
    quality_weight_multiplier: float
    # ... additional fields

class BaseTrainer(ABC):
    """Abstract base trainer for all model types"""

    def __init__(self, config: TrainingConfig):
        self.config = config
        self.model = None
        self.tokenizer = None

    @abstractmethod
    def load_model(self) -> bool:
        """Load model and tokenizer"""
        pass

    @abstractmethod
    def train_stage(
        self,
        stage: int,
        train_dataset: Path,
        val_dataset: Path,
        output_dir: Path
    ) -> Dict[str, Any]:
        """Train a single stage"""
        pass

    @abstractmethod
    def evaluate(
        self,
        test_dataset: Path,
        model_path: Path
    ) -> Dict[str, float]:
        """Evaluate model on test dataset"""
        pass

    def save_training_metadata(
        self,
        output_dir: Path,
        metadata: Dict[str, Any]
    ):
        """Save training metadata for reproducibility"""
        metadata_file = output_dir / "training_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
```

### MCP Server Implementation

```python
# mcp_server/olmo_fine_tuning_server.py

from mcp.server import Server
from mcp.types import Tool, TextContent
import json
from pathlib import Path
from typing import Dict, Any

class OLMoFineTuningServer:
    """MCP Server for OLMo fine-tuning generation"""

    def __init__(self):
        self.server = Server("olmo-fine-tuning")
        self._register_tools()

    def _register_tools(self):
        """Register all MCP tools"""

        # Tool 1: Generate Fine-Tuning Project
        self.server.add_tool(
            Tool(
                name="generate_fine_tuning_project",
                description="Generate a complete fine-tuning project with configurable base model",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_name": {"type": "string"},
                        "output_dir": {"type": "string"},
                        "base_model": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "enum": ["olmo", "llama", "mistral", "custom"]},
                                "model_id": {"type": "string"},
                                "local_path": {"type": "string"},
                                "quantization": {"type": "string", "enum": ["q4", "q8", "none"]}
                            }
                        },
                        # ... additional parameters
                    },
                    "required": ["project_name", "output_dir", "base_model"]
                }
            ),
            self._handle_generate_project
        )

        # Tool 2: Configure Training Run
        self.server.add_tool(
            Tool(
                name="configure_training_run",
                description="Create a training run configuration for an existing project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string"},
                        "run_name": {"type": "string"},
                        "training_data": {
                            "type": "object",
                            "properties": {
                                "train_dataset": {"type": "string"},
                                "validation_dataset": {"type": "string"}
                            }
                        }
                    }
                }
            ),
            self._handle_configure_run
        )

        # ... register remaining tools

    async def _handle_generate_project(self, params: Dict[str, Any]) -> str:
        """Handle project generation"""
        project_generator = ProjectGenerator(params)
        result = await project_generator.generate()
        return json.dumps(result, indent=2)

    async def _handle_configure_run(self, params: Dict[str, Any]) -> str:
        """Handle training run configuration"""
        run_configurator = RunConfigurator(params)
        result = await run_configurator.configure()
        return json.dumps(result, indent=2)
```

### Project Generator

```python
# mcp_server/project_generator.py

from pathlib import Path
from typing import Dict, Any
import shutil
from jinja2 import Template

class ProjectGenerator:
    """Generate fine-tuning project from template"""

    TEMPLATES_DIR = Path(__file__).parent / "templates"

    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.project_name = params["project_name"]
        self.output_dir = Path(params["output_dir"])
        self.project_path = self.output_dir / self.project_name

    async def generate(self) -> Dict[str, Any]:
        """Generate complete project structure"""

        # Create directory structure
        self._create_directories()

        # Generate configuration files
        self._generate_config_files()

        # Copy trainer modules
        self._copy_trainer_modules()

        # Generate scripts
        self._generate_scripts()

        # Generate requirements.txt
        self._generate_requirements()

        # Generate README
        self._generate_readme()

        # Generate .env.example
        self._generate_env_example()

        return {
            "success": True,
            "project_path": str(self.project_path),
            "project_structure": self._get_structure(),
            "next_steps": self._get_next_steps(),
            "command_examples": self._get_command_examples()
        }

    def _create_directories(self):
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
            "logs"
        ]

        for dir_path in directories:
            (self.project_path / dir_path).mkdir(parents=True, exist_ok=True)

    def _generate_config_files(self):
        """Generate configuration files from templates"""

        # Load configuration template
        config_template = self._load_template("fine_tuning_config.yaml.jinja")

        # Render with parameters
        config_content = config_template.render(
            project_name=self.params["project_name"],
            base_model=self.params["base_model"],
            training=self.params.get("training", {}),
            lora=self.params.get("lora", {}),
            features=self.params.get("features", {})
        )

        # Save configuration
        config_file = self.project_path / "config" / "fine_tuning_config.yaml"
        with open(config_file, 'w') as f:
            f.write(config_content)

    def _copy_trainer_modules(self):
        """Copy trainer modules adapted from security-ai-analysis"""

        # Copy base modules
        module_mappings = {
            "base_trainer.py": "trainer/base_trainer.py",
            "mlx_trainer.py": "trainer/mlx_trainer.py",
            "transformers_trainer.py": "trainer/transformers_trainer.py",
            "training_run_manager.py": "trainer/training_run_manager.py",
            "dataset_preparator.py": "trainer/dataset_preparator.py"
        }

        for source, dest in module_mappings.items():
            source_path = self.TEMPLATES_DIR / "trainer_modules" / source
            dest_path = self.project_path / dest

            # Load template and render with configuration
            template = self._load_template(f"trainer_modules/{source}")
            rendered = template.render(
                model_type=self.params["base_model"]["type"],
                enable_mlx=self.params.get("features", {}).get("enable_mlx_optimization", True)
            )

            with open(dest_path, 'w') as f:
                f.write(rendered)

    def _generate_requirements(self):
        """Generate requirements.txt based on features"""

        base_requirements = [
            "pydantic==2.11.9",
            "pydantic-settings==2.11.0",
            "PyYAML==6.0.3",
            "datasets==4.1.1",
            "transformers==4.57.0",
            "torch==2.8.0"
        ]

        # Add conditional requirements
        if self.params.get("features", {}).get("enable_mlx_optimization"):
            base_requirements.extend([
                "mlx==0.29.2",
                "mlx-lm==0.27.1"
            ])

        if self.params.get("features", {}).get("enable_carbontracking"):
            base_requirements.append("codecarbon==2.3.4")

        if self.params.get("integrations", {}).get("mlflow_tracking_uri"):
            base_requirements.append("mlflow==2.10.2")

        requirements_file = self.project_path / "requirements.txt"
        with open(requirements_file, 'w') as f:
            f.write('\n'.join(sorted(base_requirements)))

    def _get_next_steps(self) -> list:
        """Generate next steps instructions"""
        return [
            f"1. Navigate to project: cd {self.project_path}",
            "2. Create virtual environment: python -m venv .venv",
            "3. Activate environment: source .venv/bin/activate",
            "4. Install dependencies: pip install -r requirements.txt",
            "5. Prepare your training data in data/raw/",
            "6. Configure training: edit config/fine_tuning_config.yaml",
            "7. Start training: python scripts/train.py"
        ]

    def _get_command_examples(self) -> Dict[str, str]:
        """Generate command examples"""
        return {
            "train": "python scripts/train.py --config config/fine_tuning_config.yaml",
            "evaluate": "python scripts/evaluate.py --run-id {run_id} --test-data data/test.jsonl",
            "export": "python scripts/export.py --run-id {run_id} --format mlx --output ./exported_model"
        }
```

---

## Part 5: Template Files

### Template: `fine_tuning_config.yaml.jinja`

```yaml
# Generated by OLMo Fine-Tuning MCP Server
# Project: {{ project_name }}

project:
  name: "{{ project_name }}"
  description: "Auto-generated fine-tuning project"
  version: "1.0.0"

base_model:
  type: "{{ base_model.type }}"
  model_id: "{{ base_model.model_id }}"
  {% if base_model.local_path %}
  local_path: "{{ base_model.local_path }}"
  {% endif %}
  quantization: "{{ base_model.quantization | default('q4') }}"

training:
  num_stages: {{ training.num_stages | default(1) }}

  {% if training.num_stages >= 1 %}
  stage1:
    iterations: {{ training.stage1_iterations | default(100) }}
    learning_rate: {{ training.learning_rate | default(2.0e-5) }}
    batch_size: {{ training.batch_size | default(4) }}
    warmup_steps: 10
  {% endif %}

  {% if training.num_stages == 2 %}
  stage2:
    iterations: {{ training.stage2_iterations | default(150) }}
    learning_rate: {{ training.stage2_learning_rate | default(1.0e-6) }}
    batch_size: {{ training.batch_size | default(4) }}
    replay_ratio: 0.15
  {% endif %}

  quality_weight_multiplier: {{ training.quality_weight_multiplier | default(2.5) }}
  save_steps: 50
  eval_steps: 25

lora:
  rank: {{ lora.rank | default(8) }}
  alpha: {{ lora.alpha | default(16) }}
  dropout: {{ lora.dropout | default(0.05) }}
  target_modules:
    {% for module in lora.target_modules | default(['q_proj', 'v_proj']) %}
    - "{{ module }}"
    {% endfor %}

# ... additional sections
```

---

## Part 6: Integration with Health Data AI Platform

### Use Case: Health Narrative Training

**Before (Manual Setup)**:
1. Copy training code from security-ai-analysis
2. Adapt for health narrative format
3. Configure paths, models, hyperparameters
4. Write training scripts
5. Test and debug

**After (MCP Server)**:
```python
# In Claude Code or any MCP client

# Generate complete fine-tuning project
result = await mcp_client.call_tool(
    "generate_fine_tuning_project",
    {
        "project_name": "health-narrative-olmo",
        "output_dir": "./services/ai-query-interface/training",
        "base_model": {
            "type": "olmo",
            "model_id": "allenai/OLMo-7B",
            "quantization": "q4"
        },
        "training": {
            "num_stages": 1,
            "stage1_iterations": 1000,
            "learning_rate": 2e-4,
            "batch_size": 4,
            "quality_weight_multiplier": 2.5
        },
        "lora": {
            "rank": 16,
            "alpha": 32,
            "dropout": 0.05
        },
        "dataset": {
            "format": "jsonl",
            "quality_field": "quality_score",
            "instruction_field": "instruction",
            "output_field": "output"
        },
        "features": {
            "enable_mlx_optimization": True,
            "enable_quality_weighting": True,
            "enable_carbontracking": True
        },
        "integrations": {
            "mlflow_tracking_uri": "http://localhost:5000",
            "codecarbon_project_name": "health-narrative-training"
        }
    }
)

# Project is ready to use!
# Just add your training data and run: python scripts/train.py
```

---

## Part 7: Advantages Over Manual Copying

### Comparison Table

| Aspect | Manual Copy & Adapt | MCP Server Generation |
|--------|-------------------|----------------------|
| **Setup Time** | 4-8 hours | 5 minutes |
| **Configuration Errors** | High risk (manual editing) | Low risk (validated templates) |
| **Consistency** | Varies per project | Standardized across projects |
| **Maintainability** | Duplicate code to maintain | Single source of truth (MCP server) |
| **Model Support** | Manual adaptation needed | Configurable (OLMo, Llama, Mistral, etc.) |
| **Updates** | Manual sync across projects | Update MCP server once |
| **Best Practices** | May be forgotten or skipped | Automatically included |
| **Documentation** | Often incomplete | Auto-generated README |

---

## Part 8: MCP Server Package Structure

```
olmo-fine-tuning-mcp-server/
├── src/
│   ├── olmo_fine_tuning_mcp/
│   │   ├── __init__.py
│   │   ├── server.py                  # MCP server implementation
│   │   ├── project_generator.py       # Project generation logic
│   │   ├── run_configurator.py        # Training run configuration
│   │   ├── training_executor.py       # Training execution handler
│   │   └── utils/
│   │       ├── config_validator.py
│   │       ├── template_renderer.py
│   │       └── model_detector.py
│   │
│   └── templates/
│       ├── fine_tuning_config.yaml.jinja
│       ├── README.md.jinja
│       ├── trainer_modules/
│       │   ├── base_trainer.py.jinja
│       │   ├── mlx_trainer.py.jinja
│       │   ├── transformers_trainer.py.jinja
│       │   ├── training_run_manager.py.jinja
│       │   └── dataset_preparator.py.jinja
│       └── scripts/
│           ├── train.py.jinja
│           ├── evaluate.py.jinja
│           └── export.py.jinja
│
├── tests/
│   ├── test_server.py
│   ├── test_project_generator.py
│   └── fixtures/
│
├── examples/
│   ├── health_narrative_example.py
│   ├── security_analysis_example.py
│   └── custom_model_example.py
│
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## Part 9: Installation & Usage

### Installation

```bash
# Install from PyPI
pip install olmo-fine-tuning-mcp

# Or install from source
git clone https://github.com/your-org/olmo-fine-tuning-mcp-server
cd olmo-fine-tuning-mcp-server
pip install -e .
```

### Configuration in Claude Code

```json
{
  "mcpServers": {
    "olmo-fine-tuning": {
      "command": "python",
      "args": ["-m", "olmo_fine_tuning_mcp.server"],
      "env": {
        "OLMO_TEMPLATES_DIR": "/path/to/templates",
        "OLMO_DEFAULT_OUTPUT_DIR": "./fine-tuning-projects"
      }
    }
  }
}
```

### Usage Example

```python
# Example 1: Health Narrative Training (OLMo-7B)
result = await mcp.call_tool(
    "generate_fine_tuning_project",
    {
        "project_name": "health-narrative-olmo7b",
        "output_dir": "./services/ai-query-interface/training",
        "base_model": {
            "type": "olmo",
            "model_id": "allenai/OLMo-7B"
        },
        "training": {"num_stages": 1, "stage1_iterations": 1000}
    }
)

# Example 2: Security Analysis (Llama-3.2-1B)
result = await mcp.call_tool(
    "generate_fine_tuning_project",
    {
        "project_name": "security-analysis-llama",
        "output_dir": "./security-training",
        "base_model": {
            "type": "llama",
            "model_id": "meta-llama/Llama-3.2-1B"
        },
        "training": {"num_stages": 2}
    }
)

# Example 3: Custom Model
result = await mcp.call_tool(
    "generate_fine_tuning_project",
    {
        "project_name": "custom-mistral-training",
        "output_dir": "./custom-training",
        "base_model": {
            "type": "mistral",
            "model_id": "mistralai/Mistral-7B-v0.1",
            "local_path": "~/models/Mistral-7B-mlx-q4"
        }
    }
)
```

---

## Part 10: Development Roadmap

### Phase 1: MVP (Weeks 1-2)
- ☐ Implement `generate_fine_tuning_project` tool
- ☐ Create base templates (config, trainer modules)
- ☐ Support OLMo model type
- ☐ Basic MLX optimization
- ☐ Quality-weighted sampling

### Phase 2: Multi-Model Support (Weeks 3-4)
- ☐ Add Llama model support
- ☐ Add Mistral model support
- ☐ Add custom model detection
- ☐ Implement `configure_training_run` tool
- ☐ Implement `start_training` tool

### Phase 3: Advanced Features (Weeks 5-6)
- ☐ CodeCarbon integration
- ☐ MLflow tracking
- ☐ Wandb integration
- ☐ Implement `monitor_training_progress` tool
- ☐ Implement `evaluate_model` tool

### Phase 4: Export & Deployment (Weeks 7-8)
- ☐ Implement `export_model` tool
- ☐ GGUF export support
- ☐ HuggingFace upload automation
- ☐ Model merging utilities
- ☐ Deployment documentation

---

## Summary & Recommendation

### Is This Worth Building?

**YES** - For the following reasons:

1. **✅ Proven Architecture**: Your security-ai-analysis system already works in production
2. **✅ Immediate Reusability**: Health narrative training project needs this NOW
3. **✅ Time Savings**: 4-8 hours manual setup → 5 minutes generation
4. **✅ Consistency**: Standardized best practices across projects
5. **✅ Maintainability**: Single source of truth for training infrastructure
6. **✅ Extensibility**: Easy to add new model types (Llama, Mistral, etc.)

### Recommended Approach

**Option A: Full MCP Server** (Recommended if you have many future fine-tuning projects)
- Invest 6-8 weeks to build complete MCP server
- Reuse across health-data-ai-platform, security-ai-analysis, and future projects
- Benefits compound with each new project

**Option B: Simplified Generator Script** (Recommended for 1-2 projects)
- Create a Python script (not full MCP server) that generates projects
- Takes 1-2 weeks to build
- Can be upgraded to MCP server later if needed

### Next Steps

1. **Decide**: Full MCP server vs. simplified generator
2. **Prioritize**: Which model types to support first (OLMo mandatory, others optional)
3. **Extract**: Pull reusable code from security-ai-analysis into templates
4. **Implement**: Start with MVP (generate_fine_tuning_project only)
5. **Test**: Generate health-narrative-olmo project and validate it works
6. **Iterate**: Add remaining tools based on actual usage

---

**Specification Status**: Ready for review and implementation decision
**Estimated Development Time**: 6-8 weeks (full MCP server) or 1-2 weeks (simplified generator)
**Primary Benefit**: Eliminate 4-8 hours of manual setup per fine-tuning project
