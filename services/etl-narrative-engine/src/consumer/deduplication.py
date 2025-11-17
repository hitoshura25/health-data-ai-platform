"""
Deduplication storage implementations for ETL Narrative Engine.

Provides persistent tracking of processed messages to ensure idempotency.
Supports both SQLite (single instance) and Redis (distributed deployment).
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

import aiosqlite
import redis.asyncio as aioredis
import structlog

logger = structlog.get_logger()

# Maximum length for narrative preview stored in deduplication records
NARRATIVE_PREVIEW_MAX_LENGTH = 200


@dataclass
class ProcessingRecord:
    """Record of message processing status"""
    idempotency_key: str
    message_id: str
    correlation_id: str | None
    user_id: str | None
    record_type: str
    s3_key: str
    status: str  # 'processing_started', 'completed', 'failed'
    error_message: str | None = None
    error_type: str | None = None
    started_at: float = 0.0
    completed_at: float | None = None
    processing_time_seconds: float | None = None
    records_processed: int | None = None
    quality_score: float | None = None
    narrative_preview: str | None = None
    created_at: float = 0.0
    expires_at: float = 0.0

    def __post_init__(self):
        """Validate processing record fields"""
        # Validate timestamps
        if self.expires_at > 0 and self.created_at > 0 and self.expires_at < self.created_at:
            raise ValueError(
                f"expires_at ({self.expires_at}) must be greater than or equal to "
                f"created_at ({self.created_at})"
            )

        # Validate status
        valid_statuses = ['processing_started', 'completed', 'failed']
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status: {self.status}. "
                f"Must be one of: {valid_statuses}"
            )

        # Validate quality score if present
        if self.quality_score is not None and not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, "
                f"got {self.quality_score}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'ProcessingRecord':
        """Create from dictionary"""
        return cls(**data)


class DeduplicationStore(ABC):
    """Abstract interface for deduplication storage"""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the store"""
        pass

    @abstractmethod
    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message has already been processed"""
        pass

    @abstractmethod
    async def mark_processing_started(
        self, message_data: dict[str, Any], idempotency_key: str
    ) -> None:
        """Mark message as processing started"""
        pass

    @abstractmethod
    async def mark_processing_completed(
        self,
        idempotency_key: str,
        processing_time: float,
        records_processed: int,
        narrative: str,
        quality_score: float = 1.0
    ) -> None:
        """Mark message as successfully processed"""
        pass

    @abstractmethod
    async def mark_processing_failed(
        self, idempotency_key: str, error_message: str, error_type: str
    ) -> None:
        """Mark message as failed"""
        pass

    @abstractmethod
    async def cleanup_expired_records(self) -> int:
        """Remove expired records and return count deleted"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the store"""
        pass


class SQLiteDeduplicationStore(DeduplicationStore):
    """SQLite-based deduplication store for single-instance deployment"""

    def __init__(self, db_path: str, retention_hours: int = 168):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file (or ":memory:" for testing)
            retention_hours: How long to keep records (default: 7 days)
        """
        self.db_path = db_path
        self.retention_hours = retention_hours
        self.logger = structlog.get_logger(store="sqlite", db_path=db_path)
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database and tables"""
        self.logger.info("initializing_sqlite_dedup_store")

        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_messages (
                idempotency_key TEXT PRIMARY KEY,
                message_id TEXT NOT NULL,
                correlation_id TEXT,
                user_id TEXT,
                record_type TEXT,
                s3_key TEXT,

                -- Processing status
                status TEXT NOT NULL,
                error_message TEXT,
                error_type TEXT,

                -- Timestamps
                started_at REAL NOT NULL,
                completed_at REAL,

                -- Processing results
                processing_time_seconds REAL,
                records_processed INTEGER,
                quality_score REAL,
                narrative_preview TEXT,

                -- Retention
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON processed_messages(status)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at
            ON processed_messages(expires_at)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id
            ON processed_messages(user_id)
        """)

        await self._conn.commit()
        self.logger.info("sqlite_dedup_store_initialized")

    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message already processed"""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        cursor = await self._conn.execute(
            "SELECT 1 FROM processed_messages WHERE idempotency_key = ?",
            (idempotency_key,)
        )
        result = await cursor.fetchone()
        return result is not None

    async def mark_processing_started(
        self, message_data: dict[str, Any], idempotency_key: str
    ) -> None:
        """Mark message as processing started"""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        now = time.time()
        expires_at = now + (self.retention_hours * 3600)

        record = ProcessingRecord(
            idempotency_key=idempotency_key,
            message_id=message_data.get("message_id", ""),
            correlation_id=message_data.get("correlation_id"),
            user_id=message_data.get("user_id"),
            record_type=message_data.get("record_type", ""),
            s3_key=message_data.get("key", ""),
            status="processing_started",
            started_at=now,
            created_at=now,
            expires_at=expires_at
        )

        await self._conn.execute("""
            INSERT OR REPLACE INTO processed_messages (
                idempotency_key, message_id, correlation_id, user_id, record_type, s3_key,
                status, started_at, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.idempotency_key, record.message_id, record.correlation_id,
            record.user_id, record.record_type, record.s3_key,
            record.status, record.started_at, record.created_at, record.expires_at
        ))

        await self._conn.commit()

        self.logger.info(
            "processing_started",
            idempotency_key=idempotency_key,
            record_type=record.record_type
        )

    async def mark_processing_completed(
        self,
        idempotency_key: str,
        processing_time: float,
        records_processed: int,
        narrative: str,
        quality_score: float = 1.0
    ) -> None:
        """Mark message as successfully processed"""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        now = time.time()
        narrative_preview = narrative[:NARRATIVE_PREVIEW_MAX_LENGTH] if narrative else None

        await self._conn.execute("""
            UPDATE processed_messages
            SET status = 'completed',
                completed_at = ?,
                processing_time_seconds = ?,
                records_processed = ?,
                quality_score = ?,
                narrative_preview = ?
            WHERE idempotency_key = ?
        """, (
            now, processing_time, records_processed,
            quality_score, narrative_preview, idempotency_key
        ))

        await self._conn.commit()

        self.logger.info(
            "processing_completed",
            idempotency_key=idempotency_key,
            processing_time=processing_time,
            records=records_processed
        )

    async def mark_processing_failed(
        self, idempotency_key: str, error_message: str, error_type: str
    ) -> None:
        """Mark message as failed"""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        now = time.time()

        await self._conn.execute("""
            UPDATE processed_messages
            SET status = 'failed',
                completed_at = ?,
                error_message = ?,
                error_type = ?
            WHERE idempotency_key = ?
        """, (now, error_message, error_type, idempotency_key))

        await self._conn.commit()

        self.logger.warning(
            "processing_failed",
            idempotency_key=idempotency_key,
            error_type=error_type
        )

    async def cleanup_expired_records(self) -> int:
        """Remove expired records"""
        if not self._conn:
            raise RuntimeError("Store not initialized")

        now = time.time()

        cursor = await self._conn.execute(
            "DELETE FROM processed_messages WHERE expires_at < ?",
            (now,)
        )

        await self._conn.commit()
        deleted_count = cursor.rowcount

        if deleted_count > 0:
            self.logger.info("cleanup_expired_records", deleted=deleted_count)

        return deleted_count

    async def close(self) -> None:
        """Close database connection"""
        if self._conn:
            await self._conn.close()
            self.logger.info("sqlite_dedup_store_closed")


class RedisDeduplicationStore(DeduplicationStore):
    """Redis-based deduplication store for distributed deployment"""

    def __init__(self, redis_url: str, retention_hours: int = 168):
        """
        Initialize Redis store.

        Args:
            redis_url: Redis connection URL
            retention_hours: How long to keep records (default: 7 days)
        """
        self.redis_url = redis_url
        self.retention_seconds = retention_hours * 3600
        self.logger = structlog.get_logger(store="redis")
        self._redis: aioredis.Redis | None = None

    async def initialize(self) -> None:
        """Connect to Redis"""
        self.logger.info("initializing_redis_dedup_store")

        self._redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        # Test connection
        await self._redis.ping()

        self.logger.info("redis_dedup_store_initialized")

    async def is_already_processed(self, idempotency_key: str) -> bool:
        """Check if message already processed"""
        if not self._redis:
            raise RuntimeError("Store not initialized")

        key = f"etl:processed:{idempotency_key}"
        exists = await self._redis.exists(key)
        return exists > 0

    async def mark_processing_started(
        self, message_data: dict[str, Any], idempotency_key: str
    ) -> None:
        """Mark message as processing started"""
        if not self._redis:
            raise RuntimeError("Store not initialized")

        now = time.time()

        record = ProcessingRecord(
            idempotency_key=idempotency_key,
            message_id=message_data.get("message_id", ""),
            correlation_id=message_data.get("correlation_id"),
            user_id=message_data.get("user_id"),
            record_type=message_data.get("record_type", ""),
            s3_key=message_data.get("key", ""),
            status="processing_started",
            started_at=now,
            created_at=now,
            expires_at=now + self.retention_seconds
        )

        # Store full record
        data_key = f"etl:processed:{idempotency_key}"
        await self._redis.setex(
            data_key,
            self.retention_seconds,
            json.dumps(record.to_dict())
        )

        # Store status separately for quick lookups
        status_key = f"etl:status:{idempotency_key}"
        await self._redis.setex(
            status_key,
            self.retention_seconds,
            "processing_started"
        )

        self.logger.info(
            "processing_started",
            idempotency_key=idempotency_key,
            record_type=record.record_type
        )

    async def mark_processing_completed(
        self,
        idempotency_key: str,
        processing_time: float,
        records_processed: int,
        narrative: str,
        quality_score: float = 1.0
    ) -> None:
        """Mark message as successfully processed"""
        if not self._redis:
            raise RuntimeError("Store not initialized")

        # Get existing record
        data_key = f"etl:processed:{idempotency_key}"
        data = await self._redis.get(data_key)

        if not data:
            self.logger.warning(
                "cannot_mark_completed_record_not_found",
                idempotency_key=idempotency_key
            )
            return

        record = ProcessingRecord.from_dict(json.loads(data))
        record.status = "completed"
        record.completed_at = time.time()
        record.processing_time_seconds = processing_time
        record.records_processed = records_processed
        record.quality_score = quality_score
        record.narrative_preview = narrative[:NARRATIVE_PREVIEW_MAX_LENGTH] if narrative else None

        # Update record
        await self._redis.setex(
            data_key,
            self.retention_seconds,
            json.dumps(record.to_dict())
        )

        # Update status
        status_key = f"etl:status:{idempotency_key}"
        await self._redis.setex(
            status_key,
            self.retention_seconds,
            "completed"
        )

        self.logger.info(
            "processing_completed",
            idempotency_key=idempotency_key,
            processing_time=processing_time,
            records=records_processed
        )

    async def mark_processing_failed(
        self, idempotency_key: str, error_message: str, error_type: str
    ) -> None:
        """Mark message as failed"""
        if not self._redis:
            raise RuntimeError("Store not initialized")

        # Get existing record
        data_key = f"etl:processed:{idempotency_key}"
        data = await self._redis.get(data_key)

        if not data:
            self.logger.warning(
                "cannot_mark_failed_record_not_found",
                idempotency_key=idempotency_key
            )
            return

        record = ProcessingRecord.from_dict(json.loads(data))
        record.status = "failed"
        record.completed_at = time.time()
        record.error_message = error_message
        record.error_type = error_type

        # Update record
        await self._redis.setex(
            data_key,
            self.retention_seconds,
            json.dumps(record.to_dict())
        )

        # Update status
        status_key = f"etl:status:{idempotency_key}"
        await self._redis.setex(
            status_key,
            self.retention_seconds,
            "failed"
        )

        self.logger.warning(
            "processing_failed",
            idempotency_key=idempotency_key,
            error_type=error_type
        )

    async def cleanup_expired_records(self) -> int:
        """
        Redis handles cleanup automatically via TTL.
        This method exists for interface compatibility.
        """
        self.logger.debug("redis_auto_cleanup_via_ttl")
        return 0

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()
            self.logger.info("redis_dedup_store_closed")
