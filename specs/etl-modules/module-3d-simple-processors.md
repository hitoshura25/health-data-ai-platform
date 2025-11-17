# Module 3d: Simple Health Data Processors

**Module ID:** ETL-M3d
**Priority:** P1 (LOWER - Simpler Clinical Processors)
**Estimated Effort:** 1 week
**Dependencies:** Module 1 (BaseClinicalProcessor interface), Module 2 (ValidationResult)
**Team Assignment:** Backend Developer

---

## Module Overview

This module implements three simpler clinical processors for health data types that require less complex analysis:
1. **Steps Processor** - Daily activity and step count analysis
2. **Active Calories Processor** - Energy expenditure tracking
3. **HRV RMSSD Processor** - Heart rate variability analysis

These processors follow the same `BaseClinicalProcessor` interface but have simpler clinical logic compared to glucose, heart rate, and sleep processors.

### Key Responsibilities
- Parse Avro files for Steps, ActiveCaloriesBurned, and HRV records
- Calculate daily/weekly activity metrics
- Generate clinical narratives
- Extract structured clinical insights

### What This Module Does NOT Include
- ❌ Message consumption (Module 1)
- ❌ Data validation (Module 2)
- ❌ Training data formatting (Module 4)
- ❌ Metrics collection (Module 5)

---

## Processor 1: Steps Processor

### Clinical Background

```python
# Daily step count targets
STEP_TARGETS = {
    'sedentary': (0, 5000),           # Inactive lifestyle
    'lightly_active': (5000, 7500),   # Some activity
    'moderately_active': (7500, 10000),  # Good activity level
    'active': (10000, 12500),         # Very active
    'highly_active': (12500, 50000),  # Athlete level
}

# WHO recommendation: 10,000 steps/day for adults
WHO_RECOMMENDED_STEPS = 10000
MINIMUM_RECOMMENDED_STEPS = 7500
```

### Implementation

```python
# src/processors/steps_processor.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult

class StepsProcessor(BaseClinicalProcessor):
    """Clinical processor for step count data"""

    async def initialize(self):
        """Initialize steps processor"""
        self.daily_target = 10000
        self.weekly_target = 70000  # 10k × 7 days

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any]],
        validation_result: Any
    ) -> ProcessingResult:
        """Process step count records"""

        try:
            # Extract step records
            step_records = self._extract_step_records(records)

            if not step_records:
                return ProcessingResult(
                    success=False,
                    error_message="No valid step records found"
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
                'daily_steps': daily_steps,
                'metrics': metrics,
            }

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=0.5,
                records_processed=len(records),
                clinical_insights=clinical_insights
            )

        except Exception as e:
            return ProcessingResult(
                success=False,
                error_message=f"Steps processing failed: {str(e)}"
            )

    def _extract_step_records(
        self,
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                        'start_time': datetime.fromtimestamp(start_time / 1000),
                        'end_time': datetime.fromtimestamp(end_time / 1000),
                    })

            except (KeyError, TypeError):
                continue

        return step_records

    def _aggregate_daily_steps(
        self,
        step_records: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Aggregate steps by day"""

        daily_totals = {}

        for record in step_records:
            date = record['start_time'].date()
            daily_totals[date] = daily_totals.get(date, 0) + record['count']

        return daily_totals

    def _calculate_step_metrics(
        self,
        daily_steps: Dict[str, int]
    ) -> Dict[str, Any]:
        """Calculate step count metrics"""

        if not daily_steps:
            return {'insufficient_data': True}

        step_counts = list(daily_steps.values())

        return {
            'total_days': len(daily_steps),
            'avg_daily_steps': round(statistics.mean(step_counts)),
            'max_daily_steps': max(step_counts),
            'min_daily_steps': min(step_counts),
            'days_meeting_target': sum(1 for s in step_counts if s >= 10000),
            'total_steps': sum(step_counts),
        }

    def _generate_steps_narrative(
        self,
        daily_steps: Dict[str, int],
        metrics: Dict[str, Any]
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
        if avg_steps >= 10000:
            activity_text = (
                f"Activity level is excellent, meeting WHO recommendation "
                f"of 10,000 steps daily."
            )
        elif avg_steps >= 7500:
            activity_text = (
                f"Activity level is good ({avg_steps:,} steps), approaching "
                f"recommended 10,000 steps."
            )
        else:
            activity_text = (
                f"Activity level is below recommended ({avg_steps:,} steps). "
                f"Aim for 10,000 steps daily for optimal health."
            )
        parts.append(activity_text)

        # Target achievement
        if total_days >= 7:
            target_pct = (days_meeting_target / total_days) * 100
            target_text = (
                f"{days_meeting_target} of {total_days} days ({target_pct:.0f}%) "
                f"met the 10,000-step target."
            )
            parts.append(target_text)

        return " ".join(parts)
```

---

## Processor 2: Active Calories Processor

### Clinical Background

```python
# Daily calorie burn targets (active calories, not including BMR)
ACTIVE_CALORIE_TARGETS = {
    'sedentary': (0, 200),          # Minimal activity
    'lightly_active': (200, 400),   # Some exercise
    'moderately_active': (400, 600),  # Regular exercise
    'very_active': (600, 800),      # Intensive training
    'athlete': (800, 3000),         # Professional athlete
}

# General recommendation: 300-600 active calories/day for health
RECOMMENDED_ACTIVE_CALORIES = 500
```

### Implementation

```python
# src/processors/active_calories_processor.py
from typing import List, Dict, Any
from datetime import datetime
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult

class ActiveCaloriesProcessor(BaseClinicalProcessor):
    """Clinical processor for active calories burned data"""

    async def initialize(self):
        """Initialize active calories processor"""
        self.daily_target = 500  # Active calories
        self.weekly_target = 3500

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: Any
    ) -> ProcessingResult:
        """Process active calories records"""

        try:
            # Extract calorie records
            calorie_records = self._extract_calorie_records(records)

            if not calorie_records:
                return ProcessingResult(
                    success=False,
                    error_message="No valid calorie records found"
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

            return ProcessingResult(
                success=True,
                narrative=narrative,
                processing_time_seconds=0.5,
                records_processed=len(records),
                clinical_insights=clinical_insights
            )

        except Exception as e:
            return ProcessingResult(
                success=False,
                error_message=f"Calories processing failed: {str(e)}"
            )

    def _extract_calorie_records(
        self,
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
                        'start_time': datetime.fromtimestamp(start_time / 1000),
                        'end_time': datetime.fromtimestamp(end_time / 1000),
                    })

            except (KeyError, TypeError):
                continue

        return calorie_records

    def _aggregate_daily_calories(
        self,
        calorie_records: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """Aggregate calories by day"""

        daily_totals = {}

        for record in calorie_records:
            date = record['start_time'].date()
            daily_totals[date] = daily_totals.get(date, 0) + record['calories']

        return daily_totals

    def _calculate_calorie_metrics(
        self,
        daily_calories: Dict[str, float]
    ) -> Dict[str, Any]:
        """Calculate calorie burn metrics"""

        if not daily_calories:
            return {'insufficient_data': True}

        calorie_values = list(daily_calories.values())

        return {
            'total_days': len(daily_calories),
            'avg_daily_calories': round(statistics.mean(calorie_values)),
            'max_daily_calories': round(max(calorie_values)),
            'min_daily_calories': round(min(calorie_values)),
            'days_meeting_target': sum(1 for c in calorie_values if c >= 500),
            'total_calories': round(sum(calorie_values)),
        }

    def _generate_calories_narrative(
        self,
        daily_calories: Dict[str, float],
        metrics: Dict[str, Any]
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
```

---

## Processor 3: HRV RMSSD Processor

### Clinical Background

```python
# Heart Rate Variability RMSSD (Root Mean Square of Successive Differences)
# Higher HRV generally indicates better cardiovascular fitness and recovery

HRV_RANGES = {
    'very_low': (0, 20),       # Poor recovery, high stress
    'low': (20, 40),           # Below average
    'average': (40, 60),       # Normal range
    'good': (60, 80),          # Good cardiovascular health
    'excellent': (80, 300),    # Elite athletes
}

# RMSSD is measured in milliseconds
# Values vary significantly by age, fitness, and individual baseline
```

### Implementation

```python
# src/processors/hrv_rmssd_processor.py
from typing import List, Dict, Any
from datetime import datetime
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult

class HRVRmssdProcessor(BaseClinicalProcessor):
    """Clinical processor for HRV RMSSD data"""

    async def initialize(self):
        """Initialize HRV processor"""
        self.optimal_hrv_threshold = 60  # ms

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
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
            return ProcessingResult(
                success=False,
                error_message=f"HRV processing failed: {str(e)}"
            )

    def _extract_hrv_readings(
        self,
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
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
        hrv_readings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
        hrv_readings: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
        hrv_readings: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        trends: Dict[str, Any]
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
```

---

## Processor Factory Integration

```python
# src/processors/processor_factory.py
from src.processors.steps_processor import StepsProcessor
from src.processors.active_calories_processor import ActiveCaloriesProcessor
from src.processors.hrv_rmssd_processor import HRVRmssdProcessor

class ProcessorFactory:
    """Factory for creating processors"""

    def __init__(self):
        self.processors = {
            'BloodGlucoseRecord': BloodGlucoseProcessor(),
            'HeartRateRecord': HeartRateProcessor(),
            'SleepSessionRecord': SleepProcessor(),
            'StepsRecord': StepsProcessor(),  # Module 3d
            'ActiveCaloriesBurnedRecord': ActiveCaloriesProcessor(),  # Module 3d
            'HeartRateVariabilityRmssdRecord': HRVRmssdProcessor(),  # Module 3d
        }

    async def initialize_all(self):
        """Initialize all processors"""
        for processor in self.processors.values():
            await processor.initialize()

    def get_processor(self, record_type: str):
        """Get processor for record type"""
        return self.processors.get(record_type, GenericProcessor())
```

---

## Implementation Checklist

### Week 1: Simple Processors
- [ ] Create processor module structure
- [ ] Implement `StepsProcessor`
  - [ ] Step count extraction
  - [ ] Daily aggregation
  - [ ] Target achievement calculation
  - [ ] Narrative generation
- [ ] Implement `ActiveCaloriesProcessor`
  - [ ] Calorie extraction
  - [ ] Daily aggregation
  - [ ] Activity level assessment
  - [ ] Narrative generation
- [ ] Implement `HRVRmssdProcessor`
  - [ ] HRV reading extraction
  - [ ] Metrics calculation
  - [ ] Trend analysis
  - [ ] Narrative generation
- [ ] Update `ProcessorFactory` to include all three
- [ ] Write unit tests for all three processors (>80% coverage)
- [ ] Write integration tests with sample files
- [ ] Document clinical ranges and targets

---

## Testing Strategy

### Unit Tests

```python
# tests/test_simple_processors.py
import pytest
from src.processors.steps_processor import StepsProcessor
from src.processors.active_calories_processor import ActiveCaloriesProcessor
from src.processors.hrv_rmssd_processor import HRVRmssdProcessor

@pytest.mark.asyncio
async def test_steps_processor():
    """Test steps processor"""
    processor = StepsProcessor()
    await processor.initialize()

    records = create_sample_steps_records()  # Helper function
    result = await processor.process_with_clinical_insights(records, {}, None)

    assert result.success is True
    assert result.narrative is not None
    assert 'steps' in result.narrative.lower()

@pytest.mark.asyncio
async def test_active_calories_processor():
    """Test active calories processor"""
    processor = ActiveCaloriesProcessor()
    await processor.initialize()

    records = create_sample_calorie_records()
    result = await processor.process_with_clinical_insights(records, {}, None)

    assert result.success is True
    assert 'calories' in result.narrative.lower()

@pytest.mark.asyncio
async def test_hrv_processor():
    """Test HRV processor"""
    processor = HRVRmssdProcessor()
    await processor.initialize()

    records = create_sample_hrv_records()
    result = await processor.process_with_clinical_insights(records, {}, None)

    assert result.success is True
    assert 'hrv' in result.narrative.lower() or 'variability' in result.narrative.lower()
```

---

## Success Criteria

**Module Complete When:**
- ✅ All three processors implement `BaseClinicalProcessor` interface
- ✅ Each processor handles its respective Avro record type
- ✅ Narratives are clinically appropriate
- ✅ `ProcessorFactory` integrates all three processors
- ✅ Unit tests: >80% coverage
- ✅ Integration tests passing with sample files

---

**End of Module 3d Specification**
