"""
Tests for SleepProcessor clinical processor.

This test module covers:
- Sleep session extraction
- Sleep stage analysis
- Sleep metrics calculation
- Pattern identification
- Narrative generation
- Clinical insights extraction
"""

from datetime import UTC, datetime, timedelta

import pytest

from src.processors.sleep_processor import SleepProcessor
from src.validation.data_quality import ValidationResult


@pytest.fixture
def sleep_processor():
    """Create a SleepProcessor instance"""
    processor = SleepProcessor()
    return processor


@pytest.fixture
async def initialized_processor(sleep_processor):
    """Create and initialize a SleepProcessor"""
    await sleep_processor.initialize()
    return sleep_processor


@pytest.fixture
def validation_result():
    """Create a mock validation result"""
    return ValidationResult(
        is_valid=True, quality_score=0.95, metadata={"record_count": 10}
    )


@pytest.fixture
def sample_sleep_record():
    """Create a sample sleep session record"""
    start_time = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)  # 10 PM
    end_time = datetime(2024, 1, 16, 6, 30, 0, tzinfo=UTC)  # 6:30 AM

    return {
        "startTime": {"epochMillis": int(start_time.timestamp() * 1000)},
        "endTime": {"epochMillis": int(end_time.timestamp() * 1000)},
        "stages": [
            {
                "stage": "LIGHT",
                "startTime": {"epochMillis": int(start_time.timestamp() * 1000)},
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=3)).timestamp() * 1000
                    )
                },
            },
            {
                "stage": "DEEP",
                "startTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=3)).timestamp() * 1000
                    )
                },
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=5)).timestamp() * 1000
                    )
                },
            },
            {
                "stage": "REM",
                "startTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=5)).timestamp() * 1000
                    )
                },
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=7)).timestamp() * 1000
                    )
                },
            },
            {
                "stage": "LIGHT",
                "startTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=7)).timestamp() * 1000
                    )
                },
                "endTime": {"epochMillis": int(end_time.timestamp() * 1000)},
            },
        ],
        "metadata": {},
        "title": "Night sleep",
        "notes": "",
    }


@pytest.fixture
def multiple_sleep_records():
    """Create multiple sleep records for testing patterns"""
    records = []
    base_date = datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)

    for i in range(14):  # 2 weeks of data
        start_time = base_date + timedelta(days=i)
        # Weekends: sleep 1.5 hours longer (to make diff > 1.0 for sleep debt detection)
        duration = 8.5 if start_time.weekday() >= 5 else 7.0
        end_time = start_time + timedelta(hours=duration)

        record = {
            "startTime": {"epochMillis": int(start_time.timestamp() * 1000)},
            "endTime": {"epochMillis": int(end_time.timestamp() * 1000)},
            "stages": [],
            "metadata": {},
            "title": "",
            "notes": "",
        }
        records.append(record)

    return records


class TestSleepProcessorInitialization:
    """Test sleep processor initialization"""

    @pytest.mark.asyncio
    async def test_initialize(self, sleep_processor):
        """Test processor initialization"""
        await sleep_processor.initialize()

        assert sleep_processor.duration_ranges is not None
        assert "optimal" in sleep_processor.duration_ranges
        assert sleep_processor.optimal_stage_distribution is not None

    @pytest.mark.asyncio
    async def test_duration_ranges(self, initialized_processor):
        """Test duration ranges are correctly configured"""
        ranges = initialized_processor.duration_ranges

        assert ranges["insufficient"] == (0, 6)
        assert ranges["short"] == (6, 7)
        assert ranges["optimal"] == (7, 9)
        assert ranges["long"] == (9, 10)
        assert ranges["excessive"] == (10, 16)


class TestSessionExtraction:
    """Test sleep session extraction"""

    @pytest.mark.asyncio
    async def test_extract_single_session(
        self, initialized_processor, sample_sleep_record
    ):
        """Test extracting a single sleep session"""
        sessions = initialized_processor._extract_sleep_sessions([sample_sleep_record])

        assert len(sessions) == 1
        session = sessions[0]
        assert "start_time" in session
        assert "end_time" in session
        assert "duration_hours" in session
        assert session["duration_hours"] > 0

    @pytest.mark.asyncio
    async def test_extract_multiple_sessions(
        self, initialized_processor, multiple_sleep_records
    ):
        """Test extracting multiple sleep sessions"""
        sessions = initialized_processor._extract_sleep_sessions(multiple_sleep_records)

        assert len(sessions) == 14
        # Verify sessions are sorted by start time
        for i in range(len(sessions) - 1):
            assert sessions[i]["start_time"] <= sessions[i + 1]["start_time"]

    @pytest.mark.asyncio
    async def test_extract_with_missing_fields(self, initialized_processor):
        """Test extraction handles missing fields gracefully"""
        invalid_record = {"metadata": {}}
        sessions = initialized_processor._extract_sleep_sessions([invalid_record])

        assert len(sessions) == 0

    @pytest.mark.asyncio
    async def test_extract_stages(self, initialized_processor, sample_sleep_record):
        """Test sleep stage extraction"""
        sessions = initialized_processor._extract_sleep_sessions([sample_sleep_record])

        assert len(sessions) == 1
        assert len(sessions[0]["stages"]) == 4


class TestSleepAnalysis:
    """Test sleep session analysis"""

    @pytest.mark.asyncio
    async def test_analyze_optimal_duration(self, initialized_processor):
        """Test analyzing optimal sleep duration"""
        start_time = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)
        end_time = datetime(2024, 1, 16, 6, 0, 0, tzinfo=UTC)  # 8 hours

        session = {
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": 8.0,
            "stages": [],
            "metadata": {},
            "title": "",
            "notes": "",
        }

        analyzed = initialized_processor._analyze_sleep_sessions([session])

        assert len(analyzed) == 1
        assert analyzed[0]["duration_category"] == "optimal"
        assert analyzed[0]["duration_quality"] == "good"

    @pytest.mark.asyncio
    async def test_analyze_insufficient_duration(self, initialized_processor):
        """Test analyzing insufficient sleep duration"""
        start_time = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)
        end_time = datetime(2024, 1, 16, 3, 0, 0, tzinfo=UTC)  # 5 hours

        session = {
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": 5.0,
            "stages": [],
            "metadata": {},
            "title": "",
            "notes": "",
        }

        analyzed = initialized_processor._analyze_sleep_sessions([session])

        assert analyzed[0]["duration_category"] == "insufficient"
        assert analyzed[0]["duration_quality"] == "poor"

    @pytest.mark.asyncio
    async def test_analyze_bedtime_quality(self, initialized_processor):
        """Test bedtime quality assessment"""
        # Optimal bedtime (10 PM)
        start_time = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)
        end_time = datetime(2024, 1, 16, 6, 0, 0, tzinfo=UTC)

        session = {
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": 8.0,
            "stages": [],
            "metadata": {},
            "title": "",
            "notes": "",
        }

        analyzed = initialized_processor._analyze_sleep_sessions([session])

        assert analyzed[0]["bedtime_quality"] == "optimal"
        assert analyzed[0]["waketime_quality"] == "optimal"


class TestStageAnalysis:
    """Test sleep stage analysis"""

    @pytest.mark.asyncio
    async def test_analyze_sleep_stages(
        self, initialized_processor, sample_sleep_record
    ):
        """Test sleep stage distribution analysis"""
        sessions = initialized_processor._extract_sleep_sessions([sample_sleep_record])
        stage_analysis = initialized_processor._analyze_sleep_stages(
            sessions[0]["stages"]
        )

        assert "stage_durations_hours" in stage_analysis
        assert "stage_percentages" in stage_analysis
        assert "sleep_efficiency" in stage_analysis
        assert "distribution_quality" in stage_analysis

    @pytest.mark.asyncio
    async def test_sleep_efficiency_calculation(self, initialized_processor):
        """Test sleep efficiency calculation"""
        start_time = datetime(2024, 1, 15, 22, 0, 0, tzinfo=UTC)

        stages = [
            {
                "stage": "LIGHT",
                "startTime": {"epochMillis": int(start_time.timestamp() * 1000)},
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=4)).timestamp() * 1000
                    )
                },
            },
            {
                "stage": "DEEP",
                "startTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=4)).timestamp() * 1000
                    )
                },
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=6)).timestamp() * 1000
                    )
                },
            },
            {
                "stage": "REM",
                "startTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=6)).timestamp() * 1000
                    )
                },
                "endTime": {
                    "epochMillis": int(
                        (start_time + timedelta(hours=8)).timestamp() * 1000
                    )
                },
            },
        ]

        stage_analysis = initialized_processor._analyze_sleep_stages(stages)

        # All stages are sleep (no awake), so efficiency should be 100%
        assert stage_analysis["sleep_efficiency"] == 100.0

    @pytest.mark.asyncio
    async def test_assess_optimal_stage_distribution(self, initialized_processor):
        """Test optimal stage distribution assessment"""
        # Optimal distribution: LIGHT 50%, DEEP 20%, REM 22%, AWAKE 3%
        stage_percentages = {
            "LIGHT": 50.0,
            "DEEP": 20.0,
            "REM": 22.0,
            "AWAKE": 3.0,
            "UNKNOWN": 5.0,
        }

        quality = initialized_processor._assess_stage_distribution(stage_percentages)

        assert quality == "optimal"

    @pytest.mark.asyncio
    async def test_assess_poor_stage_distribution(self, initialized_processor):
        """Test poor stage distribution assessment"""
        # Poor distribution: low deep sleep, low REM, high awake
        stage_percentages = {"LIGHT": 70.0, "DEEP": 10.0, "REM": 10.0, "AWAKE": 10.0}

        quality = initialized_processor._assess_stage_distribution(stage_percentages)

        assert quality == "poor"


class TestMetricsCalculation:
    """Test sleep metrics calculation"""

    @pytest.mark.asyncio
    async def test_calculate_metrics_single_session(self, initialized_processor):
        """Test metrics calculation with single session"""
        analyzed_sessions = [
            {
                "duration_hours": 8.0,
                "duration_quality": "good",
                "sleep_efficiency": 90.0,
            }
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)

        assert metrics["total_sessions"] == 1
        assert metrics["avg_duration_hours"] == 8.0
        assert metrics["avg_sleep_efficiency"] == 90.0

    @pytest.mark.asyncio
    async def test_calculate_metrics_multiple_sessions(
        self, initialized_processor, multiple_sleep_records
    ):
        """Test metrics calculation with multiple sessions"""
        sessions = initialized_processor._extract_sleep_sessions(multiple_sleep_records)
        analyzed = initialized_processor._analyze_sleep_sessions(sessions)
        metrics = initialized_processor._calculate_sleep_metrics(analyzed)

        assert metrics["total_sessions"] == 14
        assert "avg_duration_hours" in metrics
        assert "duration_std_hours" in metrics
        assert "sleep_health_status" in metrics

    @pytest.mark.asyncio
    async def test_sleep_health_excellent(self, initialized_processor):
        """Test excellent sleep health assessment"""
        # Consistent 8 hours
        analyzed_sessions = [
            {
                "duration_hours": 8.0,
                "duration_quality": "good",
                "sleep_efficiency": 90.0,
            }
            for _ in range(7)
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)

        assert metrics["sleep_health_status"] == "excellent"

    @pytest.mark.asyncio
    async def test_sleep_health_poor(self, initialized_processor):
        """Test poor sleep health assessment"""
        # Insufficient sleep
        analyzed_sessions = [
            {
                "duration_hours": 5.0,
                "duration_quality": "poor",
                "sleep_efficiency": 70.0,
            }
            for _ in range(7)
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)

        assert metrics["sleep_health_status"] == "poor"


class TestPatternIdentification:
    """Test sleep pattern identification"""

    @pytest.mark.asyncio
    async def test_identify_patterns_insufficient_data(self, initialized_processor):
        """Test pattern identification with insufficient data"""
        analyzed_sessions = [
            {
                "start_time": datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC),
                "duration_hours": 8.0,
            }
            for _ in range(3)
        ]

        patterns = initialized_processor._identify_sleep_patterns(analyzed_sessions)

        # Should return None for all patterns when < 7 sessions
        assert patterns["consistency"] is None
        assert patterns["bedtime_consistency"] is None

    @pytest.mark.asyncio
    async def test_identify_excellent_consistency(self, initialized_processor):
        """Test identifying excellent sleep consistency"""
        # Same bedtime and duration every day
        analyzed_sessions = []
        base_time = datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)

        for i in range(10):
            analyzed_sessions.append(
                {"start_time": base_time + timedelta(days=i), "duration_hours": 8.0}
            )

        patterns = initialized_processor._identify_sleep_patterns(analyzed_sessions)

        assert patterns["consistency"] == "excellent"
        assert patterns["bedtime_consistency"] == "excellent"

    @pytest.mark.asyncio
    async def test_identify_weekend_pattern(
        self, initialized_processor, multiple_sleep_records
    ):
        """Test identifying weekend vs weekday pattern"""
        sessions = initialized_processor._extract_sleep_sessions(multiple_sleep_records)
        analyzed = initialized_processor._analyze_sleep_sessions(sessions)
        patterns = initialized_processor._identify_sleep_patterns(analyzed)

        assert patterns["weekend_vs_weekday"] is not None
        assert "weekday_avg" in patterns["weekend_vs_weekday"]
        assert "weekend_avg" in patterns["weekend_vs_weekday"]
        assert patterns["weekend_vs_weekday"]["sleep_debt"] is True


class TestNarrativeGeneration:
    """Test clinical narrative generation"""

    @pytest.mark.asyncio
    async def test_generate_narrative_optimal_sleep(self, initialized_processor):
        """Test narrative generation for optimal sleep"""
        analyzed_sessions = [
            {
                "duration_hours": 8.0,
                "duration_quality": "good",
                "sleep_efficiency": 92.0,
                "start_time": datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)
                + timedelta(days=i),
            }
            for i in range(10)
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)
        patterns = initialized_processor._identify_sleep_patterns(analyzed_sessions)
        narrative = initialized_processor._generate_narrative(
            analyzed_sessions, patterns, metrics
        )

        assert "optimal" in narrative.lower()
        assert "10 sleep session" in narrative
        assert "8" in narrative  # duration

    @pytest.mark.asyncio
    async def test_generate_narrative_with_recommendations(self, initialized_processor):
        """Test narrative generation includes recommendations"""
        analyzed_sessions = [
            {
                "duration_hours": 5.5,
                "duration_quality": "poor",
                "sleep_efficiency": 70.0,
                "start_time": datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)
                + timedelta(days=i, hours=i % 3),
            }
            for i in range(10)
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)
        patterns = initialized_processor._identify_sleep_patterns(analyzed_sessions)
        narrative = initialized_processor._generate_narrative(
            analyzed_sessions, patterns, metrics
        )

        assert "Recommendations:" in narrative
        assert "increase sleep duration" in narrative.lower()


class TestClinicalInsights:
    """Test clinical insights extraction"""

    @pytest.mark.asyncio
    async def test_extract_clinical_insights(self, initialized_processor):
        """Test clinical insights extraction"""
        base_time = datetime(2024, 1, 1, 22, 0, 0, tzinfo=UTC)
        analyzed_sessions = [
            {
                "duration_hours": 8.0,
                "duration_quality": "good",
                "sleep_efficiency": 90.0,
                "start_time": base_time + timedelta(days=i),
            }
            for i in range(5)
        ] + [
            {
                "duration_hours": 5.0,
                "duration_quality": "poor",
                "sleep_efficiency": 70.0,
                "start_time": base_time + timedelta(days=i + 5),
            }
            for i in range(2)
        ]

        metrics = initialized_processor._calculate_sleep_metrics(analyzed_sessions)
        patterns = initialized_processor._identify_sleep_patterns(analyzed_sessions)
        insights = initialized_processor._extract_clinical_insights(
            analyzed_sessions, patterns, metrics
        )

        assert insights["record_type"] == "SleepSessionRecord"
        assert insights["total_sessions"] == 7
        assert insights["optimal_sessions"] == 5
        assert insights["poor_sessions"] == 2
        assert "sleep_metrics" in insights
        assert "sleep_patterns" in insights


class TestProcessWithClinicalInsights:
    """Test the main processing method"""

    @pytest.mark.asyncio
    async def test_process_successful(
        self, initialized_processor, sample_sleep_record, validation_result
    ):
        """Test successful processing"""
        result = await initialized_processor.process_with_clinical_insights(
            [sample_sleep_record], {"user_id": "test_user"}, validation_result
        )

        assert result.success is True
        assert result.narrative is not None
        assert result.records_processed == 1
        assert result.clinical_insights is not None
        assert result.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_process_no_valid_sessions(
        self, initialized_processor, validation_result
    ):
        """Test processing with no valid sessions"""
        invalid_record = {"metadata": {}}

        result = await initialized_processor.process_with_clinical_insights(
            [invalid_record], {"user_id": "test_user"}, validation_result
        )

        assert result.success is False
        assert "No valid sleep sessions found" in result.error_message

    @pytest.mark.asyncio
    async def test_process_multiple_records(
        self, initialized_processor, multiple_sleep_records, validation_result
    ):
        """Test processing multiple sleep records"""
        result = await initialized_processor.process_with_clinical_insights(
            multiple_sleep_records, {"user_id": "test_user"}, validation_result
        )

        assert result.success is True
        assert result.records_processed == 14
        assert "14 sleep session" in result.narrative
        assert result.clinical_insights["total_sessions"] == 14

    @pytest.mark.asyncio
    async def test_process_with_exception(
        self, initialized_processor, validation_result
    ):
        """Test processing handles exceptions gracefully"""
        # Pass invalid data that will cause an exception
        result = await initialized_processor.process_with_clinical_insights(
            None, {}, validation_result  # This should cause an error
        )

        assert result.success is False
        assert "Sleep processing failed" in result.error_message
