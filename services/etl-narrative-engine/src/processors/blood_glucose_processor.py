"""
Blood Glucose Clinical Processor

This module implements specialized clinical processing for blood glucose data
from Android Health Connect. It analyzes glucose readings to identify clinically
significant patterns, generates human-readable narratives, and provides
structured clinical insights for AI model training.
"""

import statistics
from datetime import datetime
from typing import Any

import structlog

from ..validation.data_quality import ValidationResult
from .base_processor import BaseClinicalProcessor, ProcessingResult

logger = structlog.get_logger(__name__)


class BloodGlucoseProcessor(BaseClinicalProcessor):
    """
    Clinical processor for blood glucose data.

    Responsibilities:
    - Parse BloodGlucoseRecord Avro files
    - Classify glucose readings (hypoglycemia, normal, hyperglycemia)
    - Identify glucose patterns (fasting, post-meal, overnight)
    - Calculate glycemic variability metrics
    - Generate clinical narratives
    - Extract structured clinical insights
    """

    async def initialize(self) -> None:
        """Initialize glucose processor with clinical ranges."""
        # Clinical ranges based on American Diabetes Association guidelines
        self.ranges = {
            'severe_hypoglycemia': (0, 54),
            'hypoglycemia': (54, 70),
            'normal_fasting': (70, 100),
            'normal_general': (70, 140),
            'prediabetes_fasting': (100, 126),
            'hyperglycemia': (140, 180),
            'severe_hyperglycemia': (180, 600),
        }

        self.context_ranges = {
            'fasting': (70, 100),
            'post_meal': (70, 140),
            'bedtime': (90, 150),
        }

        self.logger.info(
            "blood_glucose_processor_initialized",
            ranges=self.ranges,
            context_ranges=self.context_ranges
        )

    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: ValidationResult
    ) -> ProcessingResult:
        """
        Process glucose records and generate clinical narrative.

        Args:
            records: Parsed BloodGlucoseRecord Avro records
            message_data: Metadata from RabbitMQ message
            validation_result: Result from Module 2 validation

        Returns:
            ProcessingResult with narrative and clinical insights
        """
        start_time = datetime.utcnow()

        try:
            # Extract glucose readings
            readings = self._extract_glucose_readings(records)

            if not readings:
                return ProcessingResult(
                    success=False,
                    error_message="No valid glucose readings found",
                    processing_time_seconds=0.0
                )

            # Classify each reading
            classifications = self._classify_readings(readings)

            # Identify patterns
            patterns = self._identify_patterns(readings, classifications)

            # Calculate variability metrics
            metrics = self._calculate_variability_metrics(readings)

            # Generate clinical narrative
            narrative = self._generate_narrative(
                readings, classifications, patterns, metrics
            )

            # Extract structured clinical insights
            clinical_insights = self._extract_clinical_insights(
                classifications, patterns, metrics
            )

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            self.logger.info(
                "blood_glucose_processing_complete",
                records_processed=len(records),
                readings_extracted=len(readings),
                processing_time_seconds=processing_time,
                quality_score=validation_result.quality_score
            )

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=processing_time,
                records_processed=len(records),
                quality_score=validation_result.quality_score,
                clinical_insights=clinical_insights
            )

        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            self.logger.error(
                "blood_glucose_processing_failed",
                error=str(e),
                processing_time_seconds=processing_time
            )
            return ProcessingResult(
                success=False,
                error_message=f"Glucose processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )

    def _extract_glucose_readings(
        self,
        records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract glucose values and timestamps from Avro records."""
        readings = []

        for record in records:
            try:
                # Extract glucose level - try both schema formats
                # New schema: direct field levelInMilligramsPerDeciliter
                glucose_mg_dl = record.get('levelInMilligramsPerDeciliter')

                # Old schema: nested in 'level' object
                if glucose_mg_dl is None:
                    level = record.get('level', {})
                    glucose_mg_dl = level.get('inMilligramsPerDeciliter')

                # Extract timestamp - try both schema formats
                # New schema: direct field timeEpochMillis
                epoch_millis = record.get('timeEpochMillis')

                # Old schema: nested in 'time' object
                if epoch_millis is None:
                    time_data = record.get('time', {})
                    epoch_millis = time_data.get('epochMillis')

                # Extract meal context - try both schema formats
                relation_to_meal = record.get('relationToMeal')
                if relation_to_meal is None:
                    metadata = record.get('metadata', {})
                    relation_to_meal = metadata.get('relationToMeal')

                # Extract specimen source (fingerstick vs CGM)
                specimen_source = record.get('specimenSource')

                if glucose_mg_dl is not None and epoch_millis is not None:
                    readings.append({
                        'glucose_mg_dl': glucose_mg_dl,
                        'timestamp': datetime.fromtimestamp(epoch_millis / 1000),
                        'epoch_millis': epoch_millis,
                        'relation_to_meal': relation_to_meal,
                        'specimen_source': specimen_source,
                    })

            except (KeyError, TypeError, ValueError) as e:
                # Skip malformed records
                self.logger.debug(
                    "skipping_malformed_record",
                    error=str(e),
                    record_sample=str(record)[:100]
                )
                continue

        # Sort by timestamp
        readings.sort(key=lambda x: x['timestamp'])

        self.logger.debug(
            "glucose_readings_extracted",
            total_records=len(records),
            valid_readings=len(readings)
        )

        return readings

    def _classify_readings(
        self,
        readings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Classify each glucose reading."""
        classifications = []

        for reading in readings:
            glucose = reading['glucose_mg_dl']

            # Determine classification
            if glucose < 54:
                category = 'severe_hypoglycemia'
                severity = 'critical'
            elif glucose < 70:
                category = 'hypoglycemia'
                severity = 'warning'
            elif glucose <= 100:
                category = 'normal_fasting'
                severity = 'normal'
            elif glucose <= 140:
                category = 'normal_general'
                severity = 'normal'
            elif glucose <= 180:
                category = 'hyperglycemia'
                severity = 'warning'
            else:
                category = 'severe_hyperglycemia'
                severity = 'critical'

            classifications.append({
                'reading': reading,
                'category': category,
                'severity': severity,
                'glucose_mg_dl': glucose,
                'timestamp': reading['timestamp']
            })

        return classifications

    def _identify_patterns(
        self,
        readings: list[dict[str, Any]],
        classifications: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Identify clinically significant glucose patterns."""
        patterns: dict[str, Any] = {
            'hypoglycemic_events': [],
            'hyperglycemic_events': [],
            'fasting_readings': [],
            'post_meal_readings': [],
            'overnight_readings': [],
            'trends': None
        }

        # Identify hypoglycemic events
        for classification in classifications:
            if (classification['severity'] in ['warning', 'critical'] and
                    classification['category'] in ['hypoglycemia', 'severe_hypoglycemia']):
                patterns['hypoglycemic_events'].append({
                    'timestamp': classification['timestamp'],
                    'glucose': classification['glucose_mg_dl'],
                    'severity': classification['category']
                })

        # Identify hyperglycemic events
        for classification in classifications:
            if classification['category'] in ['hyperglycemia', 'severe_hyperglycemia']:
                patterns['hyperglycemic_events'].append({
                    'timestamp': classification['timestamp'],
                    'glucose': classification['glucose_mg_dl'],
                    'severity': classification['category']
                })

        # Identify fasting readings (early morning, 6-10 AM)
        for reading in readings:
            hour = reading['timestamp'].hour
            if 6 <= hour <= 10:
                patterns['fasting_readings'].append({
                    'timestamp': reading['timestamp'],
                    'glucose': reading['glucose_mg_dl']
                })

        # Identify post-meal readings (using relation_to_meal metadata)
        for reading in readings:
            if reading.get('relation_to_meal') in ['AFTER_MEAL', 'POSTPRANDIAL']:
                patterns['post_meal_readings'].append({
                    'timestamp': reading['timestamp'],
                    'glucose': reading['glucose_mg_dl']
                })

        # Identify overnight readings (10 PM - 6 AM)
        for reading in readings:
            hour = reading['timestamp'].hour
            if hour >= 22 or hour <= 6:
                patterns['overnight_readings'].append({
                    'timestamp': reading['timestamp'],
                    'glucose': reading['glucose_mg_dl']
                })

        # Identify trends (improving, worsening, stable)
        if len(readings) >= 5:
            patterns['trends'] = self._analyze_trends(readings)

        return patterns

    def _analyze_trends(
        self,
        readings: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Analyze glucose trends over time."""
        if len(readings) < 5:
            return None

        # Split into first half and second half
        mid_point = len(readings) // 2
        first_half = readings[:mid_point]
        second_half = readings[mid_point:]

        first_mean = statistics.mean([r['glucose_mg_dl'] for r in first_half])
        second_mean = statistics.mean([r['glucose_mg_dl'] for r in second_half])

        # Calculate change percentage
        change_percent = ((second_mean - first_mean) / first_mean) * 100

        if abs(change_percent) < 5:
            trend = 'stable'
            description = "Glucose levels show stable trend over the period."
        elif change_percent < -5:
            trend = 'improving'
            description = (
                f"Glucose levels show improving trend over the period with "
                f"{abs(change_percent):.0f}% reduction in average glucose."
            )
        else:
            trend = 'worsening'
            description = (
                f"Glucose levels show worsening trend over the period with "
                f"{change_percent:.0f}% increase in average glucose."
            )

        return {
            'trend': trend,
            'change_percent': round(change_percent, 1),
            'first_period_mean': round(first_mean, 1),
            'second_period_mean': round(second_mean, 1),
            'description': description
        }

    def _calculate_variability_metrics(
        self,
        readings: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Calculate glycemic variability metrics."""
        if len(readings) < 2:
            return {'insufficient_data': True}

        glucose_values = [r['glucose_mg_dl'] for r in readings]

        # Mean glucose
        mean_glucose = statistics.mean(glucose_values)

        # Standard deviation
        std_dev = statistics.stdev(glucose_values) if len(glucose_values) > 1 else 0

        # Coefficient of Variation (CV)
        cv = (std_dev / mean_glucose * 100) if mean_glucose > 0 else 0

        # Time in Range (TIR) - 70-180 mg/dL
        in_range_count = sum(1 for g in glucose_values if 70 <= g <= 180)
        tir = (in_range_count / len(glucose_values)) * 100

        # Time below range (<70 mg/dL)
        below_range_count = sum(1 for g in glucose_values if g < 70)
        tbr = (below_range_count / len(glucose_values)) * 100

        # Time above range (>180 mg/dL)
        above_range_count = sum(1 for g in glucose_values if g > 180)
        tar = (above_range_count / len(glucose_values)) * 100

        return {
            'mean_glucose': round(mean_glucose, 1),
            'std_dev': round(std_dev, 1),
            'coefficient_of_variation': round(cv, 1),
            'time_in_range_percent': round(tir, 1),
            'time_below_range_percent': round(tbr, 1),
            'time_above_range_percent': round(tar, 1),
            'min_glucose': min(glucose_values),
            'max_glucose': max(glucose_values),
        }

    def _generate_narrative(
        self,
        readings: list[dict[str, Any]],
        classifications: list[dict[str, Any]],
        patterns: dict[str, Any],
        metrics: dict[str, float]
    ) -> str:
        """Generate clinical narrative from glucose data."""
        narrative_parts = []

        # Summary statement
        summary = self._generate_summary_statement(readings, metrics)
        narrative_parts.append(summary)

        # Variability assessment
        if 'coefficient_of_variation' in metrics:
            cv = metrics['coefficient_of_variation']
            tir = metrics['time_in_range_percent']

            if cv < 36 and tir >= 70:
                variability_text = (
                    f"Glucose control is excellent with low variability (CV {cv}%) "
                    f"and {tir}% time in target range (70-180 mg/dL)."
                )
            elif cv >= 36:
                variability_text = (
                    f"Glucose variability is high (CV {cv}%), indicating unstable control. "
                    f"Time in range is {tir}%."
                )
            else:
                variability_text = (
                    f"Glucose variability is moderate (CV {cv}%) with {tir}% time in range."
                )

            narrative_parts.append(variability_text)

        # Hypoglycemic events
        hypo_events = patterns.get('hypoglycemic_events', [])
        if hypo_events:
            severe_hypo = [e for e in hypo_events if e['severity'] == 'severe_hypoglycemia']
            mild_hypo = [e for e in hypo_events if e['severity'] == 'hypoglycemia']

            if severe_hypo:
                narrative_parts.append(
                    f"Alert: {len(severe_hypo)} severe hypoglycemic event(s) detected "
                    f"(<54 mg/dL), requiring immediate intervention."
                )

            if mild_hypo:
                narrative_parts.append(
                    f"{len(mild_hypo)} hypoglycemic reading(s) detected (54-70 mg/dL). "
                    f"Consider adjusting medication or meal timing."
                )

        # Hyperglycemic events
        hyper_events = patterns.get('hyperglycemic_events', [])
        if hyper_events:
            severe_hyper = [e for e in hyper_events if e['severity'] == 'severe_hyperglycemia']
            mild_hyper = [e for e in hyper_events if e['severity'] == 'hyperglycemia']

            if severe_hyper:
                narrative_parts.append(
                    f"{len(severe_hyper)} severe hyperglycemic reading(s) detected "
                    f"(>180 mg/dL). Medication adjustment may be needed."
                )
            elif mild_hyper:
                narrative_parts.append(
                    f"{len(mild_hyper)} elevated glucose reading(s) (140-180 mg/dL) observed."
                )

        # Fasting glucose assessment
        fasting_readings = patterns.get('fasting_readings', [])
        if fasting_readings:
            avg_fasting = statistics.mean([r['glucose'] for r in fasting_readings])

            if avg_fasting < 100:
                fasting_text = f"Fasting glucose is well-controlled (avg {avg_fasting:.0f} mg/dL)."
            elif avg_fasting <= 126:
                fasting_text = (
                    f"Fasting glucose is elevated (avg {avg_fasting:.0f} mg/dL), "
                    f"in prediabetes range (100-126 mg/dL)."
                )
            else:
                fasting_text = (
                    f"Fasting glucose is significantly elevated (avg {avg_fasting:.0f} mg/dL), "
                    f"consistent with diabetes (>126 mg/dL)."
                )

            narrative_parts.append(fasting_text)

        # Trend analysis
        trends = patterns.get('trends')
        if trends:
            narrative_parts.append(trends['description'])

        # Clinical recommendations
        recommendations = self._generate_recommendations(patterns, metrics)
        if recommendations:
            narrative_parts.append(f"Recommendations: {recommendations}")

        return " ".join(narrative_parts)

    def _generate_summary_statement(
        self,
        readings: list[dict[str, Any]],
        metrics: dict[str, float]
    ) -> str:
        """Generate summary statement for narrative."""
        if 'mean_glucose' not in metrics:
            return f"Blood glucose data shows {len(readings)} readings."

        # Calculate time span
        if len(readings) >= 2:
            first_time = readings[0]['timestamp']
            last_time = readings[-1]['timestamp']
            time_span = last_time - first_time
            days = max(1, time_span.days)
        else:
            days = 1

        mean_glucose = metrics['mean_glucose']

        return (
            f"Blood glucose data shows {len(readings)} readings over a {days}-day period "
            f"with mean glucose of {mean_glucose} mg/dL."
        )

    def _generate_recommendations(
        self,
        patterns: dict[str, Any],
        metrics: dict[str, float]
    ) -> str:
        """Generate clinical recommendations."""
        recommendations = []

        # Check for hypoglycemia risk
        hypo_events = patterns.get('hypoglycemic_events', [])
        if hypo_events:
            recommendations.append("Review medication timing to reduce hypoglycemic risk")

        # Check for hyperglycemia
        if 'time_above_range_percent' in metrics:
            tar = metrics['time_above_range_percent']
            if tar > 25:
                recommendations.append("Consider medication adjustment to reduce hyperglycemia")

        # Check for high variability
        if 'coefficient_of_variation' in metrics:
            cv = metrics['coefficient_of_variation']
            if cv >= 36:
                recommendations.append("Focus on consistent meal timing and carbohydrate intake to reduce variability")

        # Check fasting glucose
        fasting_readings = patterns.get('fasting_readings', [])
        if fasting_readings:
            avg_fasting = statistics.mean([r['glucose'] for r in fasting_readings])
            if avg_fasting > 100:
                recommendations.append("Monitor fasting glucose closely")

        # Check trends
        trends = patterns.get('trends')
        if trends and trends.get('trend') == 'improving':
            recommendations.append("Continue current management approach as trends are positive")

        return "; ".join(recommendations) if recommendations else ""

    def _extract_clinical_insights(
        self,
        classifications: list[dict[str, Any]],
        patterns: dict[str, Any],
        metrics: dict[str, float]
    ) -> dict[str, Any]:
        """Extract structured clinical insights for AI training."""
        # Count events by severity
        critical_events = sum(
            1 for c in classifications if c['severity'] == 'critical'
        )
        warning_events = sum(
            1 for c in classifications if c['severity'] == 'warning'
        )
        normal_events = sum(
            1 for c in classifications if c['severity'] == 'normal'
        )

        # Assess overall control
        if 'coefficient_of_variation' in metrics:
            cv = metrics['coefficient_of_variation']
            tir = metrics['time_in_range_percent']

            if cv < 36 and tir >= 70:
                control_status = 'excellent'
            elif cv < 36 and tir >= 50:
                control_status = 'good'
            elif tir >= 50:
                control_status = 'fair'
            else:
                control_status = 'poor'
        else:
            control_status = 'insufficient_data'

        return {
            'record_type': 'BloodGlucoseRecord',
            'total_readings': len(classifications),
            'critical_events': critical_events,
            'warning_events': warning_events,
            'normal_events': normal_events,
            'hypoglycemic_events_count': len(patterns.get('hypoglycemic_events', [])),
            'hyperglycemic_events_count': len(patterns.get('hyperglycemic_events', [])),
            'variability_metrics': metrics,
            'control_status': control_status,
            'fasting_readings_count': len(patterns.get('fasting_readings', [])),
            'post_meal_readings_count': len(patterns.get('post_meal_readings', [])),
            'overnight_readings_count': len(patterns.get('overnight_readings', [])),
            'trends': patterns.get('trends'),
        }
