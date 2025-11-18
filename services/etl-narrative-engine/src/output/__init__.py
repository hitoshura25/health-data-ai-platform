"""
Training data output module for ETL Narrative Engine.

Module 4: Transforms clinical narratives into JSONL training data for AI model fine-tuning.
"""

from .training_deduplicator import TrainingDeduplicator
from .training_formatter import TrainingDataFormatter

__all__ = ['TrainingDataFormatter', 'TrainingDeduplicator']
