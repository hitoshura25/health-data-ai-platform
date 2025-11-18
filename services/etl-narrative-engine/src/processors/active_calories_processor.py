"""
Active calories processor for energy expenditure data.

Processes active calories burned records and generates clinical narratives
with activity level analysis.
"""

import statistics
from datetime import UTC, datetime
from typing import Any

from ..validation.data_quality import ValidationResult
from .base_processor import BaseClinicalProcessor, ProcessingResult


class ActiveCaloriesProcessor(BaseClinicalProcessor):
    """Clinical processor for active calories burned data"""

    async def initialize(self) -> None:
        """Initialize active calories processor"""
        self.daily_target = 500  # Active calories
        self.weekly_target = 3500
        self.logger.info("active_calories_processor_initialized", daily_target=self.daily_target)

    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: ValidationResult
    ) -> ProcessingResult:
        """Process active calories records"""
        start_time = datetime.now(UTC)

        try:
            # Extract calorie records
            calorie_records = self._extract_calorie_records(records)

            if not calorie_records:
                processing_time = (datetime.now(UTC) - start_time).total_seconds()
                return ProcessingResult(
                    success=False,
                    error_message="No valid calorie records found",
                    processing_time_seconds=processing_time
                )

            # Aggregate by day
            daily_calories = self._aggregate_daily_calories(calorie_records)

            # Calculate metrics
            metrics = self._calculate_calorie_metrics(daily_calories)

            # Generate narrative
            narrative = self._generate_calories_narrative(daily_calories, metrics)

            # Clinical insights
            clinical_insights = {
                'record_type': 'ActiveCaloriesBurnedRecord',
                'total_records': len(calorie_records),
                'daily_calories': {str(k): v for k, v in daily_calories.items()},
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
            self.logger.error("calories_processing_failed", error=str(e))
            return ProcessingResult(
                success=False,
                error_message=f"Calories processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )

    def _extract_calorie_records(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract calorie data from Avro records"""

        calorie_records = []

        for record in records:
            try:
                energy = record.get('energy', {})
                calories = energy.get('inCalories') or energy.get('inKilocalories')

                start_time = record.get('startTime', {}).get('epochMillis')
                end_time = record.get('endTime', {}).get('epochMillis')

                if calories and start_time and end_time:
                    calorie_records.append({
                        'calories': calories,
                        'start_time': datetime.fromtimestamp(start_time / 1000, tz=UTC),
                        'end_time': datetime.fromtimestamp(end_time / 1000, tz=UTC),
                    })

            except (KeyError, TypeError):
                continue

        return calorie_records

    def _aggregate_daily_calories(
        self,
        calorie_records: list[dict[str, Any]]
    ) -> dict[Any, float]:
        """Aggregate calories by day"""

        daily_totals: dict[Any, float] = {}

        for record in calorie_records:
            date = record['start_time'].date()
            daily_totals[date] = daily_totals.get(date, 0) + record['calories']

        return daily_totals

    def _calculate_calorie_metrics(
        self,
        daily_calories: dict[Any, float]
    ) -> dict[str, Any]:
        """Calculate calorie burn metrics"""

        if not daily_calories:
            return {'insufficient_data': True}

        calorie_values = list(daily_calories.values())

        return {
            'total_days': len(daily_calories),
            'avg_daily_calories': round(statistics.mean(calorie_values)),
            'max_daily_calories': round(max(calorie_values)),
            'min_daily_calories': round(min(calorie_values)),
            'days_meeting_target': sum(1 for c in calorie_values if c >= self.daily_target),
            'total_calories': round(sum(calorie_values)),
        }

    def _generate_calories_narrative(
        self,
        daily_calories: dict[Any, float],
        metrics: dict[str, Any]
    ) -> str:
        """Generate narrative for calorie data"""

        parts = []

        avg_calories = metrics['avg_daily_calories']
        total_days = metrics['total_days']

        summary = (
            f"Active calorie burn data shows {total_days} day(s) with average of "
            f"{avg_calories} active calories burned per day."
        )
        parts.append(summary)

        # Activity level assessment
        if avg_calories >= 600:
            activity_text = (
                f"Activity level is very high ({avg_calories} cal/day), "
                f"indicating intensive exercise routine."
            )
        elif avg_calories >= 400:
            activity_text = (
                f"Activity level is good ({avg_calories} cal/day), "
                f"meeting moderate exercise recommendations."
            )
        elif avg_calories >= 200:
            activity_text = (
                f"Activity level is moderate ({avg_calories} cal/day). "
                f"Consider increasing to 400-600 calories for optimal fitness."
            )
        else:
            activity_text = (
                f"Activity level is low ({avg_calories} cal/day). "
                f"Aim for 300-600 active calories daily through exercise."
            )
        parts.append(activity_text)

        return " ".join(parts)
