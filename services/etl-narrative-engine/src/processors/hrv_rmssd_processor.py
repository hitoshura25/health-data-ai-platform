"""
HRV RMSSD processor for heart rate variability data.

Processes HRV RMSSD records and generates clinical narratives with recovery analysis.
"""

import statistics
from datetime import datetime
from typing import Any

from .base_processor import BaseClinicalProcessor, ProcessingResult


class HRVRmssdProcessor(BaseClinicalProcessor):
    """Clinical processor for HRV RMSSD data"""

    async def initialize(self) -> None:
        """Initialize HRV processor"""
        self.optimal_hrv_threshold = 60  # ms
        self.logger.info("hrv_processor_initialized", optimal_threshold=self.optimal_hrv_threshold)

    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """Process HRV RMSSD records"""

        try:
            # Extract HRV readings
            hrv_readings = self._extract_hrv_readings(records)

            if not hrv_readings:
                return ProcessingResult(
                    success=False,
                    error_message="No valid HRV readings found"
                )

            # Calculate metrics
            metrics = self._calculate_hrv_metrics(hrv_readings)

            # Identify trends
            trends = self._analyze_hrv_trends(hrv_readings)

            # Generate narrative
            narrative = self._generate_hrv_narrative(hrv_readings, metrics, trends)

            # Clinical insights
            clinical_insights = {
                'record_type': 'HeartRateVariabilityRmssdRecord',
                'total_readings': len(hrv_readings),
                'metrics': metrics,
                'trends': trends,
            }

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=0.5,
                records_processed=len(records),
                clinical_insights=clinical_insights
            )

        except Exception as e:
            self.logger.error("hrv_processing_failed", error=str(e))
            return ProcessingResult(
                success=False,
                error_message=f"HRV processing failed: {str(e)}"
            )

    def _extract_hrv_readings(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract HRV RMSSD values from Avro records"""

        readings = []

        for record in records:
            try:
                hrv_data = record.get('heartRateVariabilityRmssd', {})
                rmssd_ms = hrv_data.get('inMilliseconds')

                time_data = record.get('time', {})
                timestamp = time_data.get('epochMillis')

                if rmssd_ms is not None and timestamp:
                    readings.append({
                        'rmssd_ms': rmssd_ms,
                        'timestamp': datetime.fromtimestamp(timestamp / 1000),
                    })

            except (KeyError, TypeError):
                continue

        # Sort by timestamp
        readings.sort(key=lambda x: x['timestamp'])

        return readings

    def _calculate_hrv_metrics(
        self,
        hrv_readings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Calculate HRV metrics"""

        if not hrv_readings:
            return {'insufficient_data': True}

        rmssd_values = [r['rmssd_ms'] for r in hrv_readings]

        avg_hrv = statistics.mean(rmssd_values)

        # Classify HRV level
        if avg_hrv < 20:
            hrv_category = 'very_low'
            recovery_status = 'poor'
        elif avg_hrv < 40:
            hrv_category = 'low'
            recovery_status = 'below_average'
        elif avg_hrv < 60:
            hrv_category = 'average'
            recovery_status = 'normal'
        elif avg_hrv < 80:
            hrv_category = 'good'
            recovery_status = 'good'
        else:
            hrv_category = 'excellent'
            recovery_status = 'excellent'

        return {
            'total_readings': len(hrv_readings),
            'avg_hrv_rmssd': round(avg_hrv, 1),
            'min_hrv': min(rmssd_values),
            'max_hrv': max(rmssd_values),
            'std_dev': round(statistics.stdev(rmssd_values), 1) if len(rmssd_values) > 1 else 0,
            'hrv_category': hrv_category,
            'recovery_status': recovery_status,
        }

    def _analyze_hrv_trends(
        self,
        hrv_readings: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Analyze HRV trends over time"""

        if len(hrv_readings) < 7:
            return {'insufficient_data': True}

        # Compare first half vs second half
        mid_point = len(hrv_readings) // 2
        first_half = [r['rmssd_ms'] for r in hrv_readings[:mid_point]]
        second_half = [r['rmssd_ms'] for r in hrv_readings[mid_point:]]

        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)

        change_pct = ((avg_second - avg_first) / avg_first) * 100

        if change_pct > 10:
            trend = 'improving'
            trend_description = (
                f"HRV is improving over time (+{change_pct:.1f}%), "
                f"indicating better recovery and adaptation to training."
            )
        elif change_pct < -10:
            trend = 'declining'
            trend_description = (
                f"HRV is declining over time ({change_pct:.1f}%), "
                f"which may indicate overtraining or increased stress."
            )
        else:
            trend = 'stable'
            trend_description = "HRV remains stable over the period."

        return {
            'trend': trend,
            'change_percent': round(change_pct, 1),
            'description': trend_description,
        }

    def _generate_hrv_narrative(
        self,
        hrv_readings: list[dict[str, Any]],
        metrics: dict[str, Any],
        trends: dict[str, Any]
    ) -> str:
        """Generate narrative for HRV data"""

        parts = []

        total_readings = len(hrv_readings)
        avg_hrv = metrics['avg_hrv_rmssd']
        recovery_status = metrics['recovery_status']

        summary = (
            f"Heart rate variability (HRV RMSSD) data shows {total_readings} reading(s) "
            f"with average of {avg_hrv} ms."
        )
        parts.append(summary)

        # Recovery status assessment
        if recovery_status == 'excellent':
            status_text = (
                f"HRV is excellent ({avg_hrv} ms), indicating superior "
                f"cardiovascular fitness and recovery capacity."
            )
        elif recovery_status == 'good':
            status_text = (
                f"HRV is good ({avg_hrv} ms), indicating healthy recovery "
                f"and stress management."
            )
        elif recovery_status == 'normal':
            status_text = f"HRV is in normal range ({avg_hrv} ms)."
        else:
            status_text = (
                f"HRV is below optimal ({avg_hrv} ms). Low HRV may indicate "
                f"stress, poor recovery, or overtraining. Consider rest and recovery."
            )
        parts.append(status_text)

        # Trends
        if not trends.get('insufficient_data'):
            parts.append(trends['description'])

        return " ".join(parts)
