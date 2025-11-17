# Module 3b: Heart Rate Clinical Processor

**Module ID:** ETL-M3b
**Priority:** P1 (HIGH - Complex Clinical Processor)
**Estimated Effort:** 1 week
**Dependencies:** Module 1 (BaseClinicalProcessor interface), Module 2 (ValidationResult)
**Team Assignment:** Backend Developer with Clinical/Fitness Domain Knowledge

---

## Module Overview

This module implements specialized clinical processing for heart rate data from Android Health Connect. It analyzes heart rate patterns to identify cardiovascular insights, exercise patterns, recovery metrics, and generates human-readable narratives for AI model training.

### Key Responsibilities
- Parse HeartRateRecord Avro files
- Classify heart rate readings (bradycardia, normal, tachycardia)
- Identify resting heart rate and active patterns
- Calculate heart rate zones and exercise intensity
- Detect heart rate trends and variability
- Generate clinical narratives
- Extract structured clinical insights

### What This Module Does NOT Include
- ❌ Message consumption (Module 1)
- ❌ Data validation (Module 2)
- ❌ Training data formatting (Module 4)
- ❌ Metrics collection (Module 5)
- ❌ HRV (Heart Rate Variability) processing - handled by separate module

---

## Clinical Background

### Heart Rate Classification (bpm - beats per minute)

```python
# Clinical ranges for adults (18+ years)
HEART_RATE_RANGES = {
    'severe_bradycardia': (0, 40),       # Dangerously low, medical attention
    'bradycardia': (40, 60),             # Low but can be normal for athletes
    'normal_resting': (60, 100),         # Healthy resting range
    'elevated': (100, 120),              # Slightly elevated
    'tachycardia': (120, 150),           # High, medical review suggested
    'severe_tachycardia': (150, 220),    # Very high, immediate attention
}

# Context-specific ranges
RESTING_HR_RANGE = (60, 100)           # At rest or minimal activity
ATHLETE_RESTING_HR = (40, 60)          # Well-trained athletes
MAX_HR_AGE_FORMULA = 220                # Max HR = 220 - age

# Heart Rate Zones (for exercise)
ZONE_1_VERY_LIGHT = (0.50, 0.60)       # 50-60% of max HR (warm-up)
ZONE_2_LIGHT = (0.60, 0.70)            # 60-70% (fat burning)
ZONE_3_MODERATE = (0.70, 0.80)         # 70-80% (aerobic)
ZONE_4_HARD = (0.80, 0.90)             # 80-90% (anaerobic)
ZONE_5_MAXIMUM = (0.90, 1.00)          # 90-100% (max effort)
```

### Heart Rate Metrics

**Resting Heart Rate (RHR):**
- Lowest sustained heart rate during rest/sleep
- Excellent: <60 bpm (athletes)
- Good: 60-70 bpm
- Average: 70-80 bpm
- Poor: >80 bpm

**Heart Rate Recovery (HRR):**
- Drop in HR 1 minute after exercise
- Excellent: >25 bpm drop
- Good: 15-25 bpm drop
- Fair: 10-15 bpm drop
- Poor: <10 bpm drop

**Average Heart Rate:**
- Context-dependent (resting vs active)
- Used for overall cardiovascular health assessment

---

## Interface Implementation

### **1. Processor Interface**

```python
# src/processors/heart_rate_processor.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult
from src.validation.data_quality import ValidationResult

class HeartRateProcessor(BaseClinicalProcessor):
    """Clinical processor for heart rate data"""

    async def initialize(self):
        """Initialize heart rate processor with clinical ranges"""
        self.ranges = {
            'severe_bradycardia': (0, 40),
            'bradycardia': (40, 60),
            'normal_resting': (60, 100),
            'elevated': (100, 120),
            'tachycardia': (120, 150),
            'severe_tachycardia': (150, 220),
        }

        self.hr_zones = [
            ('very_light', 0.50, 0.60),
            ('light', 0.60, 0.70),
            ('moderate', 0.70, 0.80),
            ('hard', 0.80, 0.90),
            ('maximum', 0.90, 1.00),
        ]

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: ValidationResult
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
        start_time = datetime.utcnow()

        try:
            # Extract heart rate samples
            samples = self._extract_heart_rate_samples(records)

            if not samples:
                return ProcessingResult(
                    success=False,
                    error_message="No valid heart rate samples found",
                    processing_time_seconds=0.0
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

            processing_time = (datetime.utcnow() - start_time).total_seconds()

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
            return ProcessingResult(
                success=False,
                error_message=f"Heart rate processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )
```

---

## Technical Implementation

### 1. Heart Rate Sample Extraction

```python
def _extract_heart_rate_samples(
    self,
    records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extract heart rate samples from Avro records"""

    all_samples = []

    for record in records:
        try:
            # Extract samples array
            samples = record.get('samples', [])

            # Extract record-level timestamp
            time_data = record.get('time', {})
            record_epoch = time_data.get('epochMillis')

            # Extract metadata
            metadata = record.get('metadata', {})

            for sample in samples:
                # Each sample has beatsPerMinute and time
                bpm = sample.get('beatsPerMinute')
                sample_time = sample.get('time', {})
                sample_epoch = sample_time.get('epochMillis')

                # Use sample time if available, otherwise record time
                timestamp_millis = sample_epoch if sample_epoch else record_epoch

                if bpm is not None and timestamp_millis is not None:
                    all_samples.append({
                        'bpm': bpm,
                        'timestamp': datetime.fromtimestamp(timestamp_millis / 1000),
                        'epoch_millis': timestamp_millis,
                        'metadata': metadata
                    })

        except (KeyError, TypeError, ValueError):
            continue

    # Sort by timestamp
    all_samples.sort(key=lambda x: x['timestamp'])

    return all_samples
```

### 2. Heart Rate Classification

```python
def _classify_heart_rate(
    self,
    samples: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Classify each heart rate sample"""

    classifications = []

    for sample in samples:
        bpm = sample['bpm']

        # Determine classification
        if bpm < 40:
            category = 'severe_bradycardia'
            severity = 'critical'
        elif bpm < 60:
            category = 'bradycardia'
            severity = 'warning'  # Can be normal for athletes
        elif bpm <= 100:
            category = 'normal_resting'
            severity = 'normal'
        elif bpm <= 120:
            category = 'elevated'
            severity = 'info'
        elif bpm <= 150:
            category = 'tachycardia'
            severity = 'warning'
        else:
            category = 'severe_tachycardia'
            severity = 'critical'

        classifications.append({
            'sample': sample,
            'category': category,
            'severity': severity,
            'bpm': bpm,
            'timestamp': sample['timestamp']
        })

    return classifications
```

### 3. Pattern Identification

```python
def _identify_patterns(
    self,
    samples: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Identify heart rate patterns"""

    patterns = {
        'resting_periods': [],
        'active_periods': [],
        'sleep_periods': [],
        'elevated_events': [],
        'bradycardia_events': [],
        'exercise_sessions': [],
    }

    # Identify resting periods (nighttime, low HR)
    for i, sample in enumerate(samples):
        hour = sample['timestamp'].hour
        bpm = sample['bpm']

        # Sleep/rest detection (10 PM - 6 AM, low HR)
        if (hour >= 22 or hour <= 6) and bpm < 80:
            patterns['sleep_periods'].append({
                'timestamp': sample['timestamp'],
                'bpm': bpm
            })

    # Find resting heart rate (lowest 20th percentile during sleep)
    if patterns['sleep_periods']:
        sleep_hrs = sorted([p['bpm'] for p in patterns['sleep_periods']])
        rhr_samples = sleep_hrs[:max(1, len(sleep_hrs) // 5)]  # Bottom 20%
        patterns['resting_heart_rate'] = statistics.mean(rhr_samples)
    else:
        # Fallback: lowest HR overall
        if samples:
            patterns['resting_heart_rate'] = min(s['bpm'] for s in samples)

    # Identify elevated heart rate events
    for classification in classifications:
        if classification['category'] in ['tachycardia', 'severe_tachycardia']:
            patterns['elevated_events'].append({
                'timestamp': classification['timestamp'],
                'bpm': classification['bpm'],
                'severity': classification['category']
            })

    # Identify bradycardia events (excluding sleep)
    for sample in samples:
        hour = sample['timestamp'].hour
        if sample['bpm'] < 50 and not (hour >= 22 or hour <= 6):
            patterns['bradycardia_events'].append({
                'timestamp': sample['timestamp'],
                'bpm': sample['bpm']
            })

    # Identify potential exercise sessions (sustained elevated HR)
    patterns['exercise_sessions'] = self._detect_exercise_sessions(samples)

    return patterns
```

### 4. Exercise Session Detection

```python
def _detect_exercise_sessions(
    self,
    samples: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Detect exercise sessions from sustained elevated heart rate"""

    sessions = []
    current_session = None
    EXERCISE_THRESHOLD = 100  # bpm
    MIN_DURATION_MINUTES = 10

    for i, sample in enumerate(samples):
        if sample['bpm'] >= EXERCISE_THRESHOLD:
            if current_session is None:
                # Start new session
                current_session = {
                    'start_time': sample['timestamp'],
                    'start_bpm': sample['bpm'],
                    'max_bpm': sample['bpm'],
                    'samples': [sample]
                }
            else:
                # Continue session
                current_session['samples'].append(sample)
                current_session['max_bpm'] = max(
                    current_session['max_bpm'],
                    sample['bpm']
                )
        else:
            # End session if exists
            if current_session is not None:
                duration = (
                    current_session['samples'][-1]['timestamp'] -
                    current_session['start_time']
                ).total_seconds() / 60

                if duration >= MIN_DURATION_MINUTES:
                    current_session['end_time'] = current_session['samples'][-1]['timestamp']
                    current_session['duration_minutes'] = duration
                    current_session['avg_bpm'] = statistics.mean(
                        [s['bpm'] for s in current_session['samples']]
                    )

                    # Calculate recovery if next sample exists
                    if i < len(samples) - 1:
                        recovery_sample = samples[i]
                        current_session['recovery_bpm_1min'] = (
                            current_session['samples'][-1]['bpm'] -
                            recovery_sample['bpm']
                        )

                    sessions.append(current_session)

                current_session = None

    return sessions
```

### 5. Heart Rate Metrics Calculation

```python
def _calculate_heart_rate_metrics(
    self,
    samples: List[Dict[str, Any]],
    patterns: Dict[str, Any]
) -> Dict[str, float]:
    """Calculate heart rate metrics"""

    if not samples:
        return {'insufficient_data': True}

    hr_values = [s['bpm'] for s in samples]

    # Basic statistics
    mean_hr = statistics.mean(hr_values)
    min_hr = min(hr_values)
    max_hr = max(hr_values)
    std_dev = statistics.stdev(hr_values) if len(hr_values) > 1 else 0

    # Resting heart rate
    resting_hr = patterns.get('resting_heart_rate', min_hr)

    # Time in zones (if we know approximate max HR)
    # Assume average adult, max HR ≈ 180 for calculations
    assumed_max_hr = 180

    zone_distribution = self._calculate_zone_distribution(
        hr_values, assumed_max_hr
    )

    # Heart rate variability (SDNN - standard deviation of normal-to-normal)
    # This is a simple approximation, not true HRV
    hr_variability = std_dev

    return {
        'mean_heart_rate': round(mean_hr, 1),
        'min_heart_rate': min_hr,
        'max_heart_rate': max_hr,
        'resting_heart_rate': round(resting_hr, 1),
        'std_dev': round(std_dev, 1),
        'hr_variability_sdnn': round(hr_variability, 1),
        'zone_distribution': zone_distribution,
        'total_samples': len(samples),
    }

def _calculate_zone_distribution(
    self,
    hr_values: List[float],
    max_hr: float
) -> Dict[str, float]:
    """Calculate time distribution across heart rate zones"""

    zone_counts = {
        'very_light': 0,
        'light': 0,
        'moderate': 0,
        'hard': 0,
        'maximum': 0,
    }

    for hr in hr_values:
        hr_percent = hr / max_hr

        if hr_percent < 0.60:
            zone_counts['very_light'] += 1
        elif hr_percent < 0.70:
            zone_counts['light'] += 1
        elif hr_percent < 0.80:
            zone_counts['moderate'] += 1
        elif hr_percent < 0.90:
            zone_counts['hard'] += 1
        else:
            zone_counts['maximum'] += 1

    total = len(hr_values)
    return {
        zone: round((count / total) * 100, 1)
        for zone, count in zone_counts.items()
    }
```

### 6. Narrative Generation

```python
def _generate_narrative(
    self,
    samples: List[Dict[str, Any]],
    classifications: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, float]
) -> str:
    """Generate clinical narrative from heart rate data"""

    narrative_parts = []

    # Summary statement
    total_samples = len(samples)
    duration_hours = (
        samples[-1]['timestamp'] - samples[0]['timestamp']
    ).total_seconds() / 3600

    summary = (
        f"Heart rate data shows {total_samples} measurements over "
        f"{duration_hours:.1f} hours with mean heart rate of "
        f"{metrics['mean_heart_rate']} bpm."
    )
    narrative_parts.append(summary)

    # Resting heart rate assessment
    rhr = metrics.get('resting_heart_rate')
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
    exercise_sessions = patterns.get('exercise_sessions', [])
    if exercise_sessions:
        total_exercise_time = sum(s['duration_minutes'] for s in exercise_sessions)
        avg_exercise_hr = statistics.mean([s['avg_bpm'] for s in exercise_sessions])

        exercise_text = (
            f"Detected {len(exercise_sessions)} exercise session(s) "
            f"totaling {total_exercise_time:.0f} minutes with average "
            f"exercise heart rate of {avg_exercise_hr:.0f} bpm."
        )
        narrative_parts.append(exercise_text)

        # Recovery assessment
        sessions_with_recovery = [
            s for s in exercise_sessions
            if 'recovery_bpm_1min' in s
        ]
        if sessions_with_recovery:
            avg_recovery = statistics.mean([
                s['recovery_bpm_1min'] for s in sessions_with_recovery
            ])

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
    elevated_events = patterns.get('elevated_events', [])
    if elevated_events:
        severe_events = [
            e for e in elevated_events
            if e['severity'] == 'severe_tachycardia'
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
    brady_events = patterns.get('bradycardia_events', [])
    if brady_events:
        narrative_parts.append(
            f"{len(brady_events)} bradycardia reading(s) detected during waking hours "
            f"(<50 bpm). This may be normal for well-trained athletes."
        )

    # Zone distribution
    zone_dist = metrics.get('zone_distribution', {})
    if zone_dist:
        moderate_plus = (
            zone_dist.get('moderate', 0) +
            zone_dist.get('hard', 0) +
            zone_dist.get('maximum', 0)
        )

        if moderate_plus > 20:
            zone_text = (
                f"{moderate_plus:.0f}% of time spent in moderate to vigorous "
                f"intensity zones, indicating active cardiovascular exercise."
            )
            narrative_parts.append(zone_text)

    return " ".join(narrative_parts)
```

### 7. Clinical Insights Extraction

```python
def _extract_clinical_insights(
    self,
    classifications: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, float]
) -> Dict[str, Any]:
    """Extract structured clinical insights for AI training"""

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

    # Assess cardiovascular fitness based on resting HR
    rhr = metrics.get('resting_heart_rate', 100)
    if rhr < 60:
        fitness_level = 'excellent'
    elif rhr <= 70:
        fitness_level = 'good'
    elif rhr <= 80:
        fitness_level = 'average'
    else:
        fitness_level = 'below_average'

    return {
        'record_type': 'HeartRateRecord',
        'total_samples': len(classifications),
        'critical_events': critical_events,
        'warning_events': warning_events,
        'normal_events': normal_events,
        'elevated_hr_events': len(patterns.get('elevated_events', [])),
        'bradycardia_events': len(patterns.get('bradycardia_events', [])),
        'exercise_sessions': len(patterns.get('exercise_sessions', [])),
        'heart_rate_metrics': metrics,
        'fitness_level': fitness_level,
        'resting_heart_rate': metrics.get('resting_heart_rate'),
    }
```

---

## Sample Narrative Output

**Input**: 2,500 heart rate samples over 7 days

**Generated Narrative**:
```
Heart rate data shows 2,500 measurements over 168.0 hours with mean heart rate
of 78.3 bpm. Resting heart rate is good at 58 bpm. Detected 5 exercise session(s)
totaling 210 minutes with average exercise heart rate of 142 bpm. Heart rate
recovery is excellent (avg 28 bpm drop), indicating strong cardiovascular fitness.
35% of time spent in moderate to vigorous intensity zones, indicating active
cardiovascular exercise.
```

---

## Implementation Checklist

### Week 1: Heart Rate Processor
- [ ] Create processor module structure
- [ ] Implement `HeartRateProcessor` class
- [ ] Implement sample extraction
  - [ ] Parse HeartRateRecord samples array
  - [ ] Extract BPM and timestamps
  - [ ] Handle metadata
- [ ] Implement heart rate classification
  - [ ] Define clinical ranges
  - [ ] Classify samples (bradycardia, normal, tachycardia)
- [ ] Implement pattern identification
  - [ ] Resting heart rate calculation
  - [ ] Sleep period detection
  - [ ] Exercise session detection
  - [ ] Elevated event detection
- [ ] Implement exercise session detection
  - [ ] Sustained elevated HR detection
  - [ ] Session duration calculation
  - [ ] Heart rate recovery calculation
- [ ] Implement metrics calculation
  - [ ] Mean, min, max, std dev
  - [ ] Zone distribution
  - [ ] HR variability approximation
- [ ] Implement narrative generation
  - [ ] Summary statement
  - [ ] Resting HR assessment
  - [ ] Exercise session descriptions
  - [ ] Recovery assessment
  - [ ] Event descriptions
- [ ] Implement clinical insights extraction
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests with sample files
- [ ] Document clinical logic

---

## Testing Strategy

### Unit Tests

```python
# tests/test_heart_rate_processor.py
import pytest
from datetime import datetime, timedelta
from src.processors.heart_rate_processor import HeartRateProcessor

@pytest.fixture
async def processor():
    proc = HeartRateProcessor()
    await proc.initialize()
    return proc

@pytest.mark.asyncio
async def test_extract_heart_rate_samples(processor):
    """Test extraction of HR samples from Avro records"""

    records = [
        {
            'samples': [
                {'beatsPerMinute': 72, 'time': {'epochMillis': 1700000000000}},
                {'beatsPerMinute': 75, 'time': {'epochMillis': 1700000060000}},
            ],
            'time': {'epochMillis': 1700000000000},
            'metadata': {}
        }
    ]

    samples = processor._extract_heart_rate_samples(records)

    assert len(samples) == 2
    assert samples[0]['bpm'] == 72
    assert samples[1]['bpm'] == 75

@pytest.mark.asyncio
async def test_classify_tachycardia(processor):
    """Test classification of high heart rate"""

    samples = [{'bpm': 135, 'timestamp': datetime.utcnow(), 'epoch_millis': 1700000000000}]
    classifications = processor._classify_heart_rate(samples)

    assert classifications[0]['category'] == 'tachycardia'
    assert classifications[0]['severity'] == 'warning'

@pytest.mark.asyncio
async def test_exercise_session_detection(processor):
    """Test detection of exercise from sustained elevated HR"""

    # Create 15-minute exercise session
    base_time = datetime.utcnow()
    samples = []

    for i in range(15):
        samples.append({
            'bpm': 130 + (i % 10),  # 130-140 bpm
            'timestamp': base_time + timedelta(minutes=i),
            'epoch_millis': int((base_time + timedelta(minutes=i)).timestamp() * 1000)
        })

    # Add recovery
    samples.append({
        'bpm': 100,
        'timestamp': base_time + timedelta(minutes=16),
        'epoch_millis': int((base_time + timedelta(minutes=16)).timestamp() * 1000)
    })

    sessions = processor._detect_exercise_sessions(samples)

    assert len(sessions) >= 1
    assert sessions[0]['duration_minutes'] >= 10
```

---

## Success Criteria

**Module Complete When:**
- ✅ Implements `BaseClinicalProcessor` interface
- ✅ Processes HeartRateRecord Avro files correctly
- ✅ Classifies heart rate samples accurately
- ✅ Detects exercise sessions reliably
- ✅ Calculates resting heart rate
- ✅ Calculates heart rate recovery
- ✅ Generates clinically accurate narratives
- ✅ Unit tests: >80% coverage
- ✅ Integration tests passing

---

**End of Module 3b Specification**
