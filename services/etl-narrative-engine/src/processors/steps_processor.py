"""
Steps processor for step count data.

Processes step count records and generates clinical narratives with activity analysis.
"""

import statistics
from datetime import UTC, datetime
from typing import Any

from ..validation.data_quality import ValidationResult
from .base_processor import BaseClinicalProcessor, ProcessingResult


class StepsProcessor(BaseClinicalProcessor):
    """Clinical processor for step count data"""

    async def initialize(self) -> None:
        """Initialize steps processor"""
        self.daily_target = 10000
        self.weekly_target = 70000  # 10k × 7 days
        self.logger.info("steps_processor_initialized", daily_target=self.daily_target)

    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: ValidationResult
    ) -> ProcessingResult:
        """Process step count records"""
        start_time = datetime.now(UTC)

        try:
            # Extract step records
            step_records = self._extract_step_records(records)

            if not step_records:
                processing_time = (datetime.now(UTC) - start_time).total_seconds()
                return ProcessingResult(
                    success=False,
                    error_message="No valid step records found",
                    processing_time_seconds=processing_time
                )

            # Aggregate by day
            daily_steps = self._aggregate_daily_steps(step_records)

            # Calculate metrics
            metrics = self._calculate_step_metrics(daily_steps)

            # Generate narrative
            narrative = self._generate_steps_narrative(daily_steps, metrics)

            # Clinical insights
            clinical_insights = {
                'record_type': 'StepsRecord',
                'total_records': len(step_records),
                'daily_steps': {str(k): v for k, v in daily_steps.items()},
                'metrics': metrics,
            }

            processing_time = (datetime.now(UTC) - start_time).total_seconds()

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=processing_time,
                records_processed=len(records),
                quality_score=validation_result.quality_score,
                clinical_insights=clinical_insights
            )

        except Exception as e:
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            self.logger.error("steps_processing_failed", error=str(e))
            return ProcessingResult(
                success=False,
                error_message=f"Steps processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )

    def _extract_step_records(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract step counts from Avro records"""

        step_records = []

        for record in records:
            try:
                count = record.get('count')
                start_time = record.get('startTime', {}).get('epochMillis')
                end_time = record.get('endTime', {}).get('epochMillis')

                if count and start_time and end_time:
                    step_records.append({
                        'count': count,
                        'start_time': datetime.fromtimestamp(start_time / 1000, tz=UTC),
                        'end_time': datetime.fromtimestamp(end_time / 1000, tz=UTC),
                    })

            except (KeyError, TypeError):
                continue

        return step_records

    def _aggregate_daily_steps(
        self,
        step_records: list[dict[str, Any]]
    ) -> dict[Any, int]:
        """Aggregate steps by day"""

        daily_totals: dict[Any, int] = {}

        for record in step_records:
            date = record['start_time'].date()
            daily_totals[date] = daily_totals.get(date, 0) + record['count']

        return daily_totals

    def _calculate_step_metrics(
        self,
        daily_steps: dict[Any, int]
    ) -> dict[str, Any]:
        """Calculate step count metrics"""

        if not daily_steps:
            return {'insufficient_data': True}

        step_counts = list(daily_steps.values())

        return {
            'total_days': len(daily_steps),
            'avg_daily_steps': round(statistics.mean(step_counts)),
            'max_daily_steps': max(step_counts),
            'min_daily_steps': min(step_counts),
            'days_meeting_target': sum(1 for s in step_counts if s >= self.daily_target),
            'total_steps': sum(step_counts),
        }

    def _generate_steps_narrative(
        self,
        daily_steps: dict[Any, int],
        metrics: dict[str, Any]
    ) -> str:
        """Generate narrative for step data"""

        parts = []

        avg_steps = metrics['avg_daily_steps']
        total_days = metrics['total_days']
        days_meeting_target = metrics['days_meeting_target']

        summary = (
            f"Step count data shows {total_days} day(s) with average of "
            f"{avg_steps:,} steps per day."
        )
        parts.append(summary)

        # Activity level assessment
        if avg_steps >= self.daily_target:
            activity_text = (
                f"Activity level is excellent, meeting WHO recommendation "
                f"of {self.daily_target:,} steps daily."
            )
        elif avg_steps >= 7500:
            activity_text = (
                f"Activity level is good ({avg_steps:,} steps), approaching "
                f"recommended {self.daily_target:,} steps."
            )
        else:
            activity_text = (
                f"Activity level is below recommended ({avg_steps:,} steps). "
                f"Aim for {self.daily_target:,} steps daily for optimal health."
            )
        parts.append(activity_text)

        # Target achievement
        if total_days >= 7:
            target_pct = (days_meeting_target / total_days) * 100
            target_text = (
                f"{days_meeting_target} of {total_days} days ({target_pct:.0f}%) "
                f"met the {self.daily_target:,}-step target."
            )
            parts.append(target_text)

        return " ".join(parts)
