"""
Training data deduplication to prevent duplicate training examples.

Uses the same deduplication infrastructure as message processing,
with a separate key namespace for training data tracking.

Module 4 implementation as per specs/module-4-training-data-output.md
"""

import hashlib
from typing import Any

import structlog

logger = structlog.get_logger()


class TrainingDeduplicator:
    """
    Prevent duplicate training examples from being added to JSONL files.

    Uses content hashing (narrative + source key) to identify duplicates.
    Integrates with existing deduplication store (SQLite or Redis).

    Usage:
        deduplicator = TrainingDeduplicator(dedup_store)
        content_hash = deduplicator.generate_content_hash(narrative, source_key)

        if not await deduplicator.is_duplicate(content_hash):
            # Generate training output
            await formatter.generate_training_output(...)
            await deduplicator.mark_as_processed(content_hash, metadata)
    """

    # Key prefix for training deduplication (separate from message deduplication)
    TRAINING_PREFIX = "training:"

    def __init__(self, dedup_store: Any):
        """
        Initialize training deduplicator.

        Args:
            dedup_store: DeduplicationStore instance (SQLite or Redis)
        """
        self.dedup_store = dedup_store
        self.logger = structlog.get_logger()

    def generate_content_hash(self, narrative: str, source_key: str) -> str:
        """
        Generate unique hash for training example.

        Combines narrative content and source key to create a unique identifier.
        This ensures that:
        1. Same narrative from same source = duplicate (expected)
        2. Same narrative from different source = different (rare but possible)
        3. Different narrative from same source = different (shouldn't happen)

        Args:
            narrative: Clinical narrative text
            source_key: Source S3 key (e.g., 'raw/BloodGlucoseRecord/...')

        Returns:
            SHA-256 hash hex string (64 characters)
        """
        if not narrative or not source_key:
            raise ValueError("narrative and source_key must not be empty")

        # Combine narrative and source to create unique identifier
        content = f"{narrative}::{source_key}"
        hash_value = hashlib.sha256(content.encode('utf-8')).hexdigest()

        return hash_value

    async def is_duplicate(self, content_hash: str) -> bool:
        """
        Check if this training example already exists.

        Args:
            content_hash: Content hash from generate_content_hash()

        Returns:
            True if duplicate (already processed), False if new
        """
        # Use training-specific key prefix to avoid conflicts with message dedup
        training_key = f"{self.TRAINING_PREFIX}{content_hash}"

        try:
            # Check if key exists in deduplication store using is_already_processed
            # This works because the underlying stores check key existence
            exists = await self.dedup_store.is_already_processed(training_key)

            if exists:
                self.logger.debug(
                    "duplicate_training_example_detected",
                    content_hash=content_hash[:16]  # Log first 16 chars
                )
            else:
                self.logger.debug(
                    "new_training_example",
                    content_hash=content_hash[:16]
                )

            return exists

        except Exception as e:
            # If we can't determine duplicate status, log error and allow processing
            # Better to have occasional duplicates than to block all processing
            self.logger.error(
                "deduplication_check_failed",
                error=str(e),
                content_hash=content_hash[:16]
            )
            return False

    async def mark_as_processed(
        self,
        content_hash: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Mark training example as processed.

        Uses the dedup store's mark_processing_started to register the training key.
        This ensures the key exists for future duplicate checks.

        Args:
            content_hash: Content hash from generate_content_hash()
            metadata: Optional metadata to store (record_type, timestamp, etc.)

        Raises:
            Exception: If store operation fails
        """
        training_key = f"{self.TRAINING_PREFIX}{content_hash}"

        try:
            # Create minimal message_data for the dedup store
            # The store expects certain fields, so we provide training-specific values
            message_data = {
                'message_id': training_key,
                'correlation_id': metadata.get('correlation_id') if metadata else None,
                'user_id': metadata.get('user_id') if metadata else None,
                'record_type': metadata.get('record_type') if metadata else 'training',
                'key': metadata.get('source_key') if metadata else training_key,
                'bucket': metadata.get('source_bucket') if metadata else 'training',
            }

            # Mark as started (which registers the key in the dedup store)
            await self.dedup_store.mark_processing_started(message_data, training_key)

            self.logger.debug(
                "training_example_marked_processed",
                content_hash=content_hash[:16],
                has_metadata=metadata is not None
            )

        except Exception as e:
            # This is a critical operation - we should raise to prevent duplicates
            self.logger.error(
                "failed_to_mark_training_processed",
                error=str(e),
                content_hash=content_hash[:16]
            )
            raise
