"""
Unit tests for HeartRateProcessor

Tests heart rate clinical processing including:
- Sample extraction from Avro records
- Heart rate classification (bradycardia, normal, tachycardia)
- Pattern identification (resting, exercise, sleep)
- Exercise session detection
- Metrics calculation
- Narrative generation
- Clinical insights extraction
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.processors.heart_rate_processor import HeartRateProcessor
from src.validation.data_quality import ValidationResult


@pytest.fixture
async def processor():
    """Create and initialize HeartRateProcessor"""
    proc = HeartRateProcessor()
    await proc.initialize()
    return proc


@pytest.fixture
def validation_result():
    """Create sample validation result"""
    return ValidationResult(is_valid=True, quality_score=0.95)


class TestHeartRateExtraction:
    """Test heart rate sample extraction from Avro records"""

    @pytest.mark.asyncio
    async def test_extract_heart_rate_samples_basic(self, processor):
        """Test extraction of HR samples from Avro records"""
        records = [
            {
                "samples": [
                    {"beatsPerMinute": 72, "time": {"epochMillis": 1700000000000}},
                    {"beatsPerMinute": 75, "time": {"epochMillis": 1700000060000}},
                ],
                "time": {"epochMillis": 1700000000000},
                "metadata": {},
            }
        ]

        samples = processor._extract_heart_rate_samples(records)

        assert len(samples) == 2
        assert samples[0]["bpm"] == 72
        assert samples[1]["bpm"] == 75
        assert samples[0]["epoch_millis"] == 1700000000000
        assert samples[1]["epoch_millis"] == 1700000060000

    @pytest.mark.asyncio
    async def test_extract_samples_sorted_by_timestamp(self, processor):
        """Test that samples are sorted chronologically"""
        records = [
            {
                "samples": [
                    {"beatsPerMinute": 80, "time": {"epochMillis": 1700000120000}},
                    {"beatsPerMinute": 72, "time": {"epochMillis": 1700000000000}},
                    {"beatsPerMinute": 75, "time": {"epochMillis": 1700000060000}},
                ],
                "time": {"epochMillis": 1700000000000},
                "metadata": {},
            }
        ]

        samples = processor._extract_heart_rate_samples(records)

        assert len(samples) == 3
        assert samples[0]["bpm"] == 72  # Earliest timestamp
        assert samples[1]["bpm"] == 75
        assert samples[2]["bpm"] == 80  # Latest timestamp

    @pytest.mark.asyncio
    async def test_extract_samples_fallback_to_record_time(self, processor):
        """Test fallback to record time when sample time is missing"""
        records = [
            {
                "samples": [
                    {"beatsPerMinute": 72},  # No sample time
                ],
                "time": {"epochMillis": 1700000000000},
                "metadata": {},
            }
        ]

        samples = processor._extract_heart_rate_samples(records)

        assert len(samples) == 1
        assert samples[0]["bpm"] == 72
        assert samples[0]["epoch_millis"] == 1700000000000

    @pytest.mark.asyncio
    async def test_extract_samples_skip_invalid(self, processor):
        """Test skipping samples with missing data"""
        records = [
            {
                "samples": [
                    {"beatsPerMinute": 72, "time": {"epochMillis": 1700000000000}},
                    {
                        "beatsPerMinute": None,
                        "time": {"epochMillis": 1700000060000},
                    },  # Invalid
                    {"time": {"epochMillis": 1700000120000}},  # No BPM
                ],
                "time": {"epochMillis": 1700000000000},
                "metadata": {},
            }
        ]

        samples = processor._extract_heart_rate_samples(records)

        assert len(samples) == 1  # Only valid sample
        assert samples[0]["bpm"] == 72


class TestHeartRateClassification:
    """Test heart rate classification logic"""

    @pytest.mark.asyncio
    async def test_classify_severe_bradycardia(self, processor):
        """Test classification of severe bradycardia (<40 bpm)"""
        samples = [
            {"bpm": 35, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "severe_bradycardia"
        assert classifications[0]["severity"] == "critical"
        assert classifications[0]["bpm"] == 35

    @pytest.mark.asyncio
    async def test_classify_bradycardia(self, processor):
        """Test classification of bradycardia (40-59 bpm)"""
        samples = [
            {"bpm": 55, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "bradycardia"
        assert classifications[0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_classify_normal_resting(self, processor):
        """Test classification of normal resting HR (60-100 bpm)"""
        samples = [
            {"bpm": 75, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "normal_resting"
        assert classifications[0]["severity"] == "normal"

    @pytest.mark.asyncio
    async def test_classify_elevated(self, processor):
        """Test classification of elevated HR (100-120 bpm)"""
        samples = [
            {"bpm": 110, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "elevated"
        assert classifications[0]["severity"] == "info"

    @pytest.mark.asyncio
    async def test_classify_tachycardia(self, processor):
        """Test classification of tachycardia (120-150 bpm)"""
        samples = [
            {"bpm": 135, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "tachycardia"
        assert classifications[0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_classify_severe_tachycardia(self, processor):
        """Test classification of severe tachycardia (>150 bpm)"""
        samples = [
            {"bpm": 175, "timestamp": datetime.now(UTC), "epoch_millis": 1700000000000}
        ]

        classifications = processor._classify_heart_rate(samples)

        assert classifications[0]["category"] == "severe_tachycardia"
        assert classifications[0]["severity"] == "critical"


class TestPatternIdentification:
    """Test heart rate pattern identification"""

    @pytest.mark.asyncio
    async def test_identify_sleep_periods(self, processor):
        """Test identification of sleep periods (nighttime, low HR)"""
        base_time = datetime(2024, 1, 1, 2, 0, 0)  # 2 AM
        samples = [
            {
                "bpm": 60,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            }
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)

        assert len(patterns["sleep_periods"]) == 1
        assert patterns["sleep_periods"][0]["bpm"] == 60

    @pytest.mark.asyncio
    async def test_identify_resting_heart_rate(self, processor):
        """Test calculation of resting heart rate from sleep periods"""
        base_time = datetime(2024, 1, 1, 2, 0, 0)  # 2 AM
        samples = []

        # Create sleep period with varying HR
        for i in range(10):
            samples.append(
                {
                    "bpm": 55 + i,  # 55-64 bpm
                    "timestamp": base_time + timedelta(minutes=i),
                    "epoch_millis": int(
                        (base_time + timedelta(minutes=i)).timestamp() * 1000
                    ),
                }
            )

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)

        # RHR should be mean of lowest 20% (55-56)
        assert "resting_heart_rate" in patterns
        assert 54 <= patterns["resting_heart_rate"] <= 57

    @pytest.mark.asyncio
    async def test_identify_elevated_events(self, processor):
        """Test identification of elevated heart rate events"""
        base_time = datetime.now(UTC)
        samples = [
            {
                "bpm": 140,  # Tachycardia
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
            {
                "bpm": 160,  # Severe tachycardia
                "timestamp": base_time + timedelta(minutes=1),
                "epoch_millis": int(
                    (base_time + timedelta(minutes=1)).timestamp() * 1000
                ),
            },
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)

        assert len(patterns["elevated_events"]) == 2
        assert patterns["elevated_events"][0]["bpm"] == 140
        assert patterns["elevated_events"][1]["bpm"] == 160

    @pytest.mark.asyncio
    async def test_identify_bradycardia_daytime_only(self, processor):
        """Test bradycardia detection excludes nighttime"""
        # Daytime bradycardia (should be detected)
        daytime = datetime(2024, 1, 1, 14, 0, 0)  # 2 PM
        nighttime = datetime(2024, 1, 1, 2, 0, 0)  # 2 AM

        samples = [
            {
                "bpm": 45,
                "timestamp": daytime,
                "epoch_millis": int(daytime.timestamp() * 1000),
            },
            {
                "bpm": 45,
                "timestamp": nighttime,
                "epoch_millis": int(nighttime.timestamp() * 1000),
            },
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)

        # Only daytime bradycardia should be flagged
        assert len(patterns["bradycardia_events"]) == 1
        assert patterns["bradycardia_events"][0]["timestamp"].hour == 14


class TestExerciseSessionDetection:
    """Test exercise session detection"""

    @pytest.mark.asyncio
    async def test_detect_exercise_session(self, processor):
        """Test detection of exercise from sustained elevated HR"""
        base_time = datetime.now(UTC)
        samples = []

        # Create 15-minute exercise session
        for i in range(15):
            samples.append(
                {
                    "bpm": 130 + (i % 10),  # 130-140 bpm
                    "timestamp": base_time + timedelta(minutes=i),
                    "epoch_millis": int(
                        (base_time + timedelta(minutes=i)).timestamp() * 1000
                    ),
                }
            )

        # Add recovery
        samples.append(
            {
                "bpm": 100,
                "timestamp": base_time + timedelta(minutes=16),
                "epoch_millis": int(
                    (base_time + timedelta(minutes=16)).timestamp() * 1000
                ),
            }
        )

        sessions = processor._detect_exercise_sessions(samples)

        assert len(sessions) >= 1
        assert sessions[0]["duration_minutes"] >= 10
        assert sessions[0]["max_bpm"] >= 130

    @pytest.mark.asyncio
    async def test_exercise_session_recovery(self, processor):
        """Test heart rate recovery calculation"""
        base_time = datetime.now(UTC)
        samples = []

        # Create exercise session
        for i in range(15):
            samples.append(
                {
                    "bpm": 140,
                    "timestamp": base_time + timedelta(minutes=i),
                    "epoch_millis": int(
                        (base_time + timedelta(minutes=i)).timestamp() * 1000
                    ),
                }
            )

        # Add recovery sample (41 bpm drop) - must be < 100 to trigger session end
        samples.append(
            {
                "bpm": 99,
                "timestamp": base_time + timedelta(minutes=15),
                "epoch_millis": int(
                    (base_time + timedelta(minutes=15)).timestamp() * 1000
                ),
            }
        )

        sessions = processor._detect_exercise_sessions(samples)

        assert len(sessions) >= 1
        assert "recovery_bpm_1min" in sessions[0]
        assert sessions[0]["recovery_bpm_1min"] == 41

    @pytest.mark.asyncio
    async def test_skip_short_exercise_sessions(self, processor):
        """Test that short elevated HR periods are not detected as exercise"""
        base_time = datetime.now(UTC)
        samples = []

        # Create 5-minute elevated HR (too short)
        for i in range(5):
            samples.append(
                {
                    "bpm": 130,
                    "timestamp": base_time + timedelta(minutes=i),
                    "epoch_millis": int(
                        (base_time + timedelta(minutes=i)).timestamp() * 1000
                    ),
                }
            )

        # Add recovery
        samples.append(
            {
                "bpm": 70,
                "timestamp": base_time + timedelta(minutes=5),
                "epoch_millis": int(
                    (base_time + timedelta(minutes=5)).timestamp() * 1000
                ),
            }
        )

        sessions = processor._detect_exercise_sessions(samples)

        assert len(sessions) == 0  # Too short to count


class TestMetricsCalculation:
    """Test heart rate metrics calculation"""

    @pytest.mark.asyncio
    async def test_calculate_basic_metrics(self, processor):
        """Test calculation of basic HR metrics"""
        base_time = datetime.now(UTC)
        samples = [
            {
                "bpm": 60,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
            {
                "bpm": 70,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
            {
                "bpm": 80,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
        ]

        patterns = {"resting_heart_rate": 60}
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)

        assert metrics["mean_heart_rate"] == 70.0
        assert metrics["min_heart_rate"] == 60
        assert metrics["max_heart_rate"] == 80
        assert metrics["resting_heart_rate"] == 60
        assert metrics["total_samples"] == 3

    @pytest.mark.asyncio
    async def test_calculate_zone_distribution(self, processor):
        """Test calculation of heart rate zone distribution"""
        # Test with max_hr = 180
        hr_values = [
            90,  # 50% = very_light
            108,  # 60% = light
            126,  # 70% = moderate
            144,  # 80% = hard
            162,  # 90% = maximum
        ]

        zone_dist = processor._calculate_zone_distribution(hr_values, 180)

        assert zone_dist["very_light"] == 20.0
        assert zone_dist["light"] == 20.0
        assert zone_dist["moderate"] == 20.0
        assert zone_dist["hard"] == 20.0
        assert zone_dist["maximum"] == 20.0

    @pytest.mark.asyncio
    async def test_empty_samples_returns_insufficient_data(self, processor):
        """Test that empty samples return insufficient_data flag"""
        metrics = processor._calculate_heart_rate_metrics([], {})

        assert "insufficient_data" in metrics
        assert metrics["insufficient_data"] is True


class TestNarrativeGeneration:
    """Test clinical narrative generation"""

    @pytest.mark.asyncio
    async def test_generate_narrative_basic(self, processor):
        """Test generation of basic narrative"""
        base_time = datetime.now(UTC)
        samples = [
            {
                "bpm": 72,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
            {
                "bpm": 75,
                "timestamp": base_time + timedelta(hours=1),
                "epoch_millis": int(
                    (base_time + timedelta(hours=1)).timestamp() * 1000
                ),
            },
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)

        narrative = processor._generate_narrative(
            samples, classifications, patterns, metrics
        )

        assert "Heart rate data shows 2 measurements" in narrative
        assert "bpm" in narrative

    @pytest.mark.asyncio
    async def test_narrative_includes_resting_assessment(self, processor):
        """Test narrative includes resting HR assessment"""
        base_time = datetime.now(UTC)
        samples = [
            {
                "bpm": 55,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            }
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)

        narrative = processor._generate_narrative(
            samples, classifications, patterns, metrics
        )

        assert "Resting heart rate" in narrative

    @pytest.mark.asyncio
    async def test_narrative_includes_exercise_sessions(self, processor):
        """Test narrative includes exercise session descriptions"""
        base_time = datetime.now(UTC)
        samples = []

        # Create exercise session
        for i in range(15):
            samples.append(
                {
                    "bpm": 140,
                    "timestamp": base_time + timedelta(minutes=i),
                    "epoch_millis": int(
                        (base_time + timedelta(minutes=i)).timestamp() * 1000
                    ),
                }
            )

        # Add recovery
        samples.append(
            {
                "bpm": 100,
                "timestamp": base_time + timedelta(minutes=15),
                "epoch_millis": int(
                    (base_time + timedelta(minutes=15)).timestamp() * 1000
                ),
            }
        )

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)

        narrative = processor._generate_narrative(
            samples, classifications, patterns, metrics
        )

        assert "exercise session" in narrative.lower()


class TestClinicalInsights:
    """Test clinical insights extraction"""

    @pytest.mark.asyncio
    async def test_extract_clinical_insights(self, processor):
        """Test extraction of structured clinical insights"""
        base_time = datetime.now(UTC)
        samples = [
            {
                "bpm": 60,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
            {
                "bpm": 140,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            },
        ]

        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)

        insights = processor._extract_clinical_insights(
            classifications, patterns, metrics
        )

        assert insights["record_type"] == "HeartRateRecord"
        assert insights["total_samples"] == 2
        assert "fitness_level" in insights
        assert "heart_rate_metrics" in insights

    @pytest.mark.asyncio
    async def test_fitness_level_assessment(self, processor):
        """Test cardiovascular fitness level assessment"""
        base_time = datetime.now(UTC)

        # Excellent fitness (RHR < 60)
        samples = [
            {
                "bpm": 55,
                "timestamp": base_time,
                "epoch_millis": int(base_time.timestamp() * 1000),
            }
        ]
        classifications = processor._classify_heart_rate(samples)
        patterns = processor._identify_patterns(samples, classifications)
        metrics = processor._calculate_heart_rate_metrics(samples, patterns)
        insights = processor._extract_clinical_insights(
            classifications, patterns, metrics
        )

        assert insights["fitness_level"] == "excellent"


class TestEndToEndProcessing:
    """Test end-to-end processing workflow"""

    @pytest.mark.asyncio
    async def test_process_with_clinical_insights_success(
        self, processor, validation_result
    ):
        """Test successful end-to-end processing"""
        records = [
            {
                "samples": [
                    {"beatsPerMinute": 72, "time": {"epochMillis": 1700000000000}},
                    {"beatsPerMinute": 75, "time": {"epochMillis": 1700000060000}},
                ],
                "time": {"epochMillis": 1700000000000},
                "metadata": {},
            }
        ]

        message_data = {}

        result = await processor.process_with_clinical_insights(
            records, message_data, validation_result
        )

        assert result.success is True
        assert result.narrative is not None
        assert "Heart rate data" in result.narrative
        assert result.records_processed == 1
        assert result.quality_score == 0.95
        assert result.clinical_insights is not None
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_process_empty_records(self, processor, validation_result):
        """Test processing with no valid samples"""
        records = [
            {"samples": [], "time": {"epochMillis": 1700000000000}, "metadata": {}}
        ]

        message_data = {}

        result = await processor.process_with_clinical_insights(
            records, message_data, validation_result
        )

        assert result.success is False
        assert result.error_message == "No valid heart rate samples found"

    @pytest.mark.asyncio
    async def test_process_handles_exceptions(self, processor, validation_result):
        """Test processing handles exceptions gracefully"""
        # Invalid records structure
        records = None

        message_data = {}

        result = await processor.process_with_clinical_insights(
            records, message_data, validation_result
        )

        assert result.success is False
        assert result.error_message is not None
        assert "Heart rate processing failed" in result.error_message
