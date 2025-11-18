"""
Heart Rate Clinical Processor

This module implements specialized clinical processing for heart rate data from
Android Health Connect. It analyzes heart rate patterns to identify cardiovascular
insights, exercise patterns, recovery metrics, and generates human-readable
narratives for AI model training.
"""

import statistics
from datetime import UTC, datetime
from typing import Any

import structlog

from ..validation.data_quality import ValidationResult
from .base_processor import BaseClinicalProcessor, ProcessingResult

logger = structlog.get_logger(__name__)


class HeartRateProcessor(BaseClinicalProcessor):
    """Clinical processor for heart rate data"""

    # Default maximum heart rate for zone calculations when user age is unknown
    # Based on typical adult max HR; ideally would use 220 - age formula
    DEFAULT_MAX_HR = 180

    async def initialize(self) -> None:
        """Initialize heart rate processor with clinical ranges"""
        self.ranges = {
            "severe_bradycardia": (0, 40),
            "bradycardia": (40, 60),
            "normal_resting": (60, 100),
            "elevated": (100, 120),
            "tachycardia": (120, 150),
            # Upper bound of 220 bpm represents the typical maximum achievable heart rate
            # Often calculated as 220 - age, though individual variation exists
            "severe_tachycardia": (150, 220),
        }

        self.hr_zones = [
            ("very_light", 0.50, 0.60),
            ("light", 0.60, 0.70),
            ("moderate", 0.70, 0.80),
            ("hard", 0.80, 0.90),
            ("maximum", 0.90, 1.00),
        ]

        self.logger.info("heart_rate_processor_initialized")

    async def process_with_clinical_insights(
        self,
        records: list[dict[str, Any]],
        message_data: dict[str, Any],
        validation_result: ValidationResult,
    ) -> ProcessingResult:
        """
        Process heart rate records and generate clinical narrative

        Args:
            records: Parsed HeartRateRecord Avro records
            message_data: Metadata from RabbitMQ message
            validation_result: Result from Module 2 validation

        Returns:
            ProcessingResult with narrative and clinical insights
        """
        start_time = datetime.now(UTC)

        try:
            # Extract heart rate samples
            samples = self._extract_heart_rate_samples(records)

            if not samples:
                return ProcessingResult(
                    success=False,
                    error_message="No valid heart rate samples found",
                    processing_time_seconds=0.0,
                )

            # Classify each sample
            classifications = self._classify_heart_rate(samples)

            # Identify patterns (resting, active, sleep)
            patterns = self._identify_patterns(samples, classifications)

            # Calculate metrics
            metrics = self._calculate_heart_rate_metrics(samples, patterns)

            # Generate clinical narrative
            narrative = self._generate_narrative(
                samples, classifications, patterns, metrics
            )

            # Extract structured clinical insights
            clinical_insights = self._extract_clinical_insights(
                classifications, patterns, metrics
            )

            processing_time = (datetime.now(UTC) - start_time).total_seconds()

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=processing_time,
                records_processed=len(records),
                quality_score=validation_result.quality_score,
                clinical_insights=clinical_insights,
            )

        except Exception as e:
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            self.logger.error(
                "heart_rate_processing_failed",
                error=str(e),
                processing_time=processing_time,
            )
            return ProcessingResult(
                success=False,
                error_message=f"Heart rate processing failed: {str(e)}",
                processing_time_seconds=processing_time,
            )

    def _extract_heart_rate_samples(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Extract heart rate samples from Avro records"""
        all_samples = []

        for record in records:
            try:
                # Extract samples array
                samples = record.get("samples", [])

                # Extract record-level timestamp
                time_data = record.get("time", {})
                record_epoch = time_data.get("epochMillis")

                # Extract metadata
                metadata = record.get("metadata", {})

                for sample in samples:
                    # Each sample has beatsPerMinute and time
                    bpm = sample.get("beatsPerMinute")
                    sample_time = sample.get("time", {})
                    sample_epoch = sample_time.get("epochMillis")

                    # Use sample time if available, otherwise record time
                    timestamp_millis = sample_epoch if sample_epoch else record_epoch

                    if bpm is not None and timestamp_millis is not None:
                        all_samples.append(
                            {
                                "bpm": bpm,
                                "timestamp": datetime.fromtimestamp(
                                    timestamp_millis / 1000, tz=UTC
                                ),
                                "epoch_millis": timestamp_millis,
                                "metadata": metadata,
                            }
                        )

            except (KeyError, TypeError, ValueError) as e:
                self.logger.debug(
                    "sample_extraction_error", error=str(e), record=record
                )
                continue

        # Sort by timestamp
        all_samples.sort(key=lambda x: x["timestamp"])

        return all_samples

    def _classify_heart_rate(
        self, samples: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Classify each heart rate sample"""
        classifications = []

        # Map categories to severity levels
        severity_map = {
            "severe_bradycardia": "critical",
            "bradycardia": "warning",  # Can be normal for athletes
            "normal_resting": "normal",
            "elevated": "info",
            "tachycardia": "warning",
            "severe_tachycardia": "critical",
        }

        for sample in samples:
            bpm = sample["bpm"]

            # Determine classification based on configured ranges
            category = None
            for range_name, (min_bpm, max_bpm) in self.ranges.items():
                if min_bpm <= bpm < max_bpm:
                    category = range_name
                    break

            # Fallback for values outside all ranges (shouldn't happen with proper ranges)
            if category is None:
                category = "severe_tachycardia" if bpm >= 220 else "severe_bradycardia"

            severity = severity_map.get(category, "warning")

            classifications.append(
                {
                    "sample": sample,
                    "category": category,
                    "severity": severity,
                    "bpm": bpm,
                    "timestamp": sample["timestamp"],
                }
            )

        return classifications

    def _identify_patterns(
        self, samples: list[dict[str, Any]], classifications: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Identify heart rate patterns"""
        patterns = {
            "resting_periods": [],
            "active_periods": [],
            "sleep_periods": [],
            "elevated_events": [],
            "bradycardia_events": [],
            "exercise_sessions": [],
        }

        # Identify resting periods (nighttime, low HR)
        for sample in samples:
            hour = sample["timestamp"].hour
            bpm = sample["bpm"]

            # Sleep/rest detection (10 PM - 6 AM, low HR)
            if (hour >= 22 or hour <= 6) and bpm < 80:
                patterns["sleep_periods"].append(
                    {"timestamp": sample["timestamp"], "bpm": bpm}
                )

        # Find resting heart rate (lowest 20th percentile during sleep)
        if patterns["sleep_periods"]:
            sleep_hrs = sorted([p["bpm"] for p in patterns["sleep_periods"]])
            rhr_samples = sleep_hrs[: max(1, len(sleep_hrs) // 5)]  # Bottom 20%
            patterns["resting_heart_rate"] = statistics.mean(rhr_samples)
        else:
            # Fallback: lowest HR overall
            if samples:
                patterns["resting_heart_rate"] = min(s["bpm"] for s in samples)

        # Identify elevated heart rate events
        for classification in classifications:
            if classification["category"] in ["tachycardia", "severe_tachycardia"]:
                patterns["elevated_events"].append(
                    {
                        "timestamp": classification["timestamp"],
                        "bpm": classification["bpm"],
                        "severity": classification["category"],
                    }
                )

        # Identify bradycardia events (excluding sleep)
        for sample in samples:
            hour = sample["timestamp"].hour
            if sample["bpm"] < 50 and not (hour >= 22 or hour <= 6):
                patterns["bradycardia_events"].append(
                    {"timestamp": sample["timestamp"], "bpm": sample["bpm"]}
                )

        # Identify potential exercise sessions (sustained elevated HR)
        patterns["exercise_sessions"] = self._detect_exercise_sessions(samples)

        return patterns

    def _detect_exercise_sessions(
        self, samples: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Detect exercise sessions from sustained elevated heart rate"""
        sessions = []
        current_session = None
        EXERCISE_THRESHOLD = 100  # bpm
        MIN_DURATION_MINUTES = 10

        for sample in samples:
            if sample["bpm"] >= EXERCISE_THRESHOLD:
                if current_session is None:
                    # Start new session
                    current_session = {
                        "start_time": sample["timestamp"],
                        "start_bpm": sample["bpm"],
                        "max_bpm": sample["bpm"],
                        "samples": [sample],
                    }
                else:
                    # Continue session
                    current_session["samples"].append(sample)
                    current_session["max_bpm"] = max(
                        current_session["max_bpm"], sample["bpm"]
                    )
            else:
                # End session if exists
                if current_session is not None:
                    duration = (
                        current_session["samples"][-1]["timestamp"]
                        - current_session["start_time"]
                    ).total_seconds() / 60

                    if duration >= MIN_DURATION_MINUTES:
                        current_session["end_time"] = current_session["samples"][-1][
                            "timestamp"
                        ]
                        current_session["duration_minutes"] = duration
                        current_session["avg_bpm"] = statistics.mean(
                            [s["bpm"] for s in current_session["samples"]]
                        )

                        # Calculate recovery using current sample (the one that ended the session)
                        current_session["recovery_bpm_1min"] = (
                            current_session["samples"][-1]["bpm"] - sample["bpm"]
                        )

                        sessions.append(current_session)

                    current_session = None

        # Handle session that continues to end of data
        if current_session is not None:
            duration = (
                current_session["samples"][-1]["timestamp"]
                - current_session["start_time"]
            ).total_seconds() / 60

            if duration >= MIN_DURATION_MINUTES:
                current_session["end_time"] = current_session["samples"][-1][
                    "timestamp"
                ]
                current_session["duration_minutes"] = duration
                current_session["avg_bpm"] = statistics.mean(
                    [s["bpm"] for s in current_session["samples"]]
                )
                sessions.append(current_session)

        return sessions

    def _calculate_heart_rate_metrics(
        self, samples: list[dict[str, Any]], patterns: dict[str, Any]
    ) -> dict[str, float]:
        """Calculate heart rate metrics"""
        if not samples:
            return {"insufficient_data": True}

        hr_values = [s["bpm"] for s in samples]

        # Basic statistics
        mean_hr = statistics.mean(hr_values)
        min_hr = min(hr_values)
        max_hr = max(hr_values)
        std_dev = statistics.stdev(hr_values) if len(hr_values) > 1 else 0

        # Resting heart rate
        resting_hr = patterns.get("resting_heart_rate", min_hr)

        # Time in zones (if we know approximate max HR)
        # Use default max HR for calculations
        zone_distribution = self._calculate_zone_distribution(
            hr_values, self.DEFAULT_MAX_HR
        )

        # Heart rate variability (SDNN - standard deviation of normal-to-normal)
        # This is a simple approximation, not true HRV
        hr_variability = std_dev

        return {
            "mean_heart_rate": round(mean_hr, 1),
            "min_heart_rate": min_hr,
            "max_heart_rate": max_hr,
            "resting_heart_rate": round(resting_hr, 1),
            "std_dev": round(std_dev, 1),
            "hr_variability_sdnn": round(hr_variability, 1),
            "zone_distribution": zone_distribution,
            "total_samples": len(samples),
        }

    def _calculate_zone_distribution(
        self, hr_values: list[float], max_hr: float
    ) -> dict[str, float]:
        """Calculate time distribution across heart rate zones"""
        zone_counts = {
            "very_light": 0,
            "light": 0,
            "moderate": 0,
            "hard": 0,
            "maximum": 0,
        }

        for hr in hr_values:
            hr_percent = hr / max_hr

            if hr_percent < 0.60:
                zone_counts["very_light"] += 1
            elif hr_percent < 0.70:
                zone_counts["light"] += 1
            elif hr_percent < 0.80:
                zone_counts["moderate"] += 1
            elif hr_percent < 0.90:
                zone_counts["hard"] += 1
            else:
                zone_counts["maximum"] += 1

        total = len(hr_values)
        return {
            zone: round((count / total) * 100, 1) for zone, count in zone_counts.items()
        }

    def _generate_narrative(
        self,
        samples: list[dict[str, Any]],
        classifications: list[dict[str, Any]],
        patterns: dict[str, Any],
        metrics: dict[str, float],
    ) -> str:
        """Generate clinical narrative from heart rate data"""
        narrative_parts = []

        # Summary statement
        total_samples = len(samples)
        duration_hours = (
            samples[-1]["timestamp"] - samples[0]["timestamp"]
        ).total_seconds() / 3600

        summary = (
            f"Heart rate data shows {total_samples} measurements over "
            f"{duration_hours:.1f} hours with mean heart rate of "
            f"{metrics['mean_heart_rate']} bpm."
        )
        narrative_parts.append(summary)

        # Resting heart rate assessment
        rhr = metrics.get("resting_heart_rate")
        if rhr:
            if rhr < 60:
                rhr_text = (
                    f"Resting heart rate is excellent at {rhr} bpm, "
                    f"indicating good cardiovascular fitness."
                )
            elif rhr <= 70:
                rhr_text = f"Resting heart rate is good at {rhr} bpm."
            elif rhr <= 80:
                rhr_text = f"Resting heart rate is average at {rhr} bpm."
            else:
                rhr_text = (
                    f"Resting heart rate is elevated at {rhr} bpm. "
                    f"Consider cardiovascular conditioning to improve fitness."
                )
            narrative_parts.append(rhr_text)

        # Exercise session summary
        exercise_sessions = patterns.get("exercise_sessions", [])
        if exercise_sessions:
            total_exercise_time = sum(s["duration_minutes"] for s in exercise_sessions)
            avg_exercise_hr = statistics.mean([s["avg_bpm"] for s in exercise_sessions])

            exercise_text = (
                f"Detected {len(exercise_sessions)} exercise session(s) "
                f"totaling {total_exercise_time:.0f} minutes with average "
                f"exercise heart rate of {avg_exercise_hr:.0f} bpm."
            )
            narrative_parts.append(exercise_text)

            # Recovery assessment
            sessions_with_recovery = [
                s for s in exercise_sessions if "recovery_bpm_1min" in s
            ]
            if sessions_with_recovery:
                avg_recovery = statistics.mean(
                    [s["recovery_bpm_1min"] for s in sessions_with_recovery]
                )

                if avg_recovery > 25:
                    recovery_text = (
                        f"Heart rate recovery is excellent (avg {avg_recovery:.0f} bpm drop), "
                        f"indicating strong cardiovascular fitness."
                    )
                elif avg_recovery > 15:
                    recovery_text = f"Heart rate recovery is good (avg {avg_recovery:.0f} bpm drop)."
                else:
                    recovery_text = (
                        f"Heart rate recovery is fair (avg {avg_recovery:.0f} bpm drop). "
                        f"Improved fitness may enhance recovery rate."
                    )
                narrative_parts.append(recovery_text)

        # Elevated heart rate events
        elevated_events = patterns.get("elevated_events", [])
        if elevated_events:
            severe_events = [
                e for e in elevated_events if e["severity"] == "severe_tachycardia"
            ]

            if severe_events:
                narrative_parts.append(
                    f"Alert: {len(severe_events)} severe tachycardia event(s) detected "
                    f"(>150 bpm). Medical review recommended if not exercise-related."
                )
            else:
                narrative_parts.append(
                    f"{len(elevated_events)} elevated heart rate reading(s) detected "
                    f"(120-150 bpm)."
                )

        # Bradycardia events (daytime only)
        brady_events = patterns.get("bradycardia_events", [])
        if brady_events:
            narrative_parts.append(
                f"{len(brady_events)} bradycardia reading(s) detected during waking hours "
                f"(<50 bpm). This may be normal for well-trained athletes."
            )

        # Zone distribution
        zone_dist = metrics.get("zone_distribution", {})
        if zone_dist:
            moderate_plus = (
                zone_dist.get("moderate", 0)
                + zone_dist.get("hard", 0)
                + zone_dist.get("maximum", 0)
            )

            if moderate_plus > 20:
                zone_text = (
                    f"{moderate_plus:.0f}% of time spent in moderate to vigorous "
                    f"intensity zones, indicating active cardiovascular exercise."
                )
                narrative_parts.append(zone_text)

        return " ".join(narrative_parts)

    def _extract_clinical_insights(
        self,
        classifications: list[dict[str, Any]],
        patterns: dict[str, Any],
        metrics: dict[str, float],
    ) -> dict[str, Any]:
        """Extract structured clinical insights for AI training"""
        # Count events by severity
        critical_events = sum(1 for c in classifications if c["severity"] == "critical")
        warning_events = sum(1 for c in classifications if c["severity"] == "warning")
        normal_events = sum(1 for c in classifications if c["severity"] == "normal")

        # Assess cardiovascular fitness based on resting HR
        rhr = metrics.get("resting_heart_rate", 100)
        if rhr < 60:
            fitness_level = "excellent"
        elif rhr <= 70:
            fitness_level = "good"
        elif rhr <= 80:
            fitness_level = "average"
        else:
            fitness_level = "below_average"

        return {
            "record_type": "HeartRateRecord",
            "total_samples": len(classifications),
            "critical_events": critical_events,
            "warning_events": warning_events,
            "normal_events": normal_events,
            "elevated_hr_events": len(patterns.get("elevated_events", [])),
            "bradycardia_events": len(patterns.get("bradycardia_events", [])),
            "exercise_sessions": len(patterns.get("exercise_sessions", [])),
            "heart_rate_metrics": metrics,
            "fitness_level": fitness_level,
            "resting_heart_rate": metrics.get("resting_heart_rate"),
        }
