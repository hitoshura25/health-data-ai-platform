# Module 3c: Sleep Clinical Processor

**Module ID:** ETL-M3c
**Priority:** P1 (MEDIUM - Complex Clinical Processor)
**Estimated Effort:** 1 week
**Dependencies:** Module 1 (BaseClinicalProcessor interface), Module 2 (ValidationResult)
**Team Assignment:** Backend Developer with Sleep/Wellness Domain Knowledge

---

## Module Overview

This module implements specialized clinical processing for sleep data from Android Health Connect. It analyzes sleep sessions to assess sleep quality, duration patterns, consistency, and generates clinical narratives for AI model training.

### Key Responsibilities
- Parse SleepSessionRecord Avro files
- Extract sleep duration and timing
- Analyze sleep stages (light, deep, REM, awake)
- Calculate sleep quality metrics
- Identify sleep patterns and consistency
- Generate clinical narratives
- Extract structured clinical insights

### What This Module Does NOT Include
- ❌ Message consumption (Module 1)
- ❌ Data validation (Module 2)
- ❌ Training data formatting (Module 4)
- ❌ Metrics collection (Module 5)

---

## Clinical Background

### Sleep Duration Recommendations (Adults 18-64 years)

```python
# Sleep duration ranges (hours)
SLEEP_DURATION_RANGES = {
    'insufficient': (0, 6),          # Too little sleep
    'short': (6, 7),                 # Below optimal
    'optimal': (7, 9),               # Recommended range
    'long': (9, 10),                 # Above optimal
    'excessive': (10, 16),           # Too much sleep
}

# Sleep timing
OPTIMAL_BEDTIME_START = 21  # 9 PM
OPTIMAL_BEDTIME_END = 23    # 11 PM
OPTIMAL_WAKETIME_START = 6  # 6 AM
OPTIMAL_WAKETIME_END = 8    # 8 AM
```

### Sleep Stages

```python
# Sleep stage types from Health Connect
SLEEP_STAGES = {
    'AWAKE': 'Time awake during sleep session',
    'LIGHT': 'Light sleep (stages N1, N2)',
    'DEEP': 'Deep sleep (stage N3, slow-wave sleep)',
    'REM': 'REM (Rapid Eye Movement) sleep',
    'UNKNOWN': 'Unclassified sleep stage',
}

# Optimal stage distribution (percentage of total sleep time)
OPTIMAL_STAGE_DISTRIBUTION = {
    'LIGHT': (45, 55),    # 45-55% light sleep
    'DEEP': (15, 25),     # 15-25% deep sleep (restorative)
    'REM': (20, 25),      # 20-25% REM sleep (cognitive)
    'AWAKE': (0, 5),      # <5% awake (sleep fragmentation)
}
```

### Sleep Quality Metrics

**Sleep Efficiency:**
- `(Total Sleep Time / Time in Bed) × 100`
- Excellent: >90%
- Good: 85-90%
- Fair: 80-85%
- Poor: <80%

**Sleep Latency:**
- Time to fall asleep
- Good: <15 minutes
- Fair: 15-30 minutes
- Poor: >30 minutes

**Wake After Sleep Onset (WASO):**
- Time awake after initially falling asleep
- Good: <20 minutes
- Fair: 20-40 minutes
- Poor: >40 minutes

---

## Interface Implementation

### **1. Processor Interface**

```python
# src/processors/sleep_processor.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
import statistics
from src.processors.base_processor import BaseClinicalProcessor, ProcessingResult
from src.validation.data_quality import ValidationResult

class SleepProcessor(BaseClinicalProcessor):
    """Clinical processor for sleep data"""

    async def initialize(self):
        """Initialize sleep processor with clinical ranges"""
        self.duration_ranges = {
            'insufficient': (0, 6),
            'short': (6, 7),
            'optimal': (7, 9),
            'long': (9, 10),
            'excessive': (10, 16),
        }

        self.optimal_stage_distribution = {
            'LIGHT': (45, 55),
            'DEEP': (15, 25),
            'REM': (20, 25),
            'AWAKE': (0, 5),
        }

    async def process_with_clinical_insights(
        self,
        records: List[Dict[str, Any]],
        message_data: Dict[str, Any],
        validation_result: ValidationResult
    ) -> ProcessingResult:
        """
        Process sleep records and generate clinical narrative

        Args:
            records: Parsed SleepSessionRecord Avro records
            message_data: Metadata from RabbitMQ message
            validation_result: Result from Module 2 validation

        Returns:
            ProcessingResult with narrative and clinical insights
        """
        start_time = datetime.utcnow()

        try:
            # Extract sleep sessions
            sessions = self._extract_sleep_sessions(records)

            if not sessions:
                return ProcessingResult(
                    success=False,
                    error_message="No valid sleep sessions found",
                    processing_time_seconds=0.0
                )

            # Analyze each session
            analyzed_sessions = self._analyze_sleep_sessions(sessions)

            # Calculate aggregate metrics
            metrics = self._calculate_sleep_metrics(analyzed_sessions)

            # Identify patterns
            patterns = self._identify_sleep_patterns(analyzed_sessions)

            # Generate clinical narrative
            narrative = self._generate_narrative(
                analyzed_sessions, patterns, metrics
            )

            # Extract structured clinical insights
            clinical_insights = self._extract_clinical_insights(
                analyzed_sessions, patterns, metrics
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
                error_message=f"Sleep processing failed: {str(e)}",
                processing_time_seconds=processing_time
            )
```

---

## Technical Implementation

### 1. Sleep Session Extraction

```python
def _extract_sleep_sessions(
    self,
    records: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extract sleep sessions from Avro records"""

    sessions = []

    for record in records:
        try:
            # Extract session timing
            start_time_data = record.get('startTime', {})
            end_time_data = record.get('endTime', {})

            start_epoch = start_time_data.get('epochMillis')
            end_epoch = end_time_data.get('epochMillis')

            if not start_epoch or not end_epoch:
                continue

            start_time = datetime.fromtimestamp(start_epoch / 1000)
            end_time = datetime.fromtimestamp(end_epoch / 1000)

            # Calculate duration
            duration_hours = (end_epoch - start_epoch) / (1000 * 3600)

            # Extract sleep stages if available
            stages = record.get('stages', [])

            # Extract metadata
            metadata = record.get('metadata', {})
            title = record.get('title', '')
            notes = record.get('notes', '')

            sessions.append({
                'start_time': start_time,
                'end_time': end_time,
                'duration_hours': duration_hours,
                'stages': stages,
                'metadata': metadata,
                'title': title,
                'notes': notes,
            })

        except (KeyError, TypeError, ValueError):
            continue

    # Sort by start time
    sessions.sort(key=lambda x: x['start_time'])

    return sessions
```

### 2. Sleep Session Analysis

```python
def _analyze_sleep_sessions(
    self,
    sessions: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Analyze each sleep session"""

    analyzed = []

    for session in sessions:
        analysis = {
            'session': session,
            'duration_hours': session['duration_hours'],
            'start_time': session['start_time'],
            'end_time': session['end_time'],
        }

        # Classify duration
        duration = session['duration_hours']
        if duration < 6:
            analysis['duration_category'] = 'insufficient'
            analysis['duration_quality'] = 'poor'
        elif duration < 7:
            analysis['duration_category'] = 'short'
            analysis['duration_quality'] = 'fair'
        elif duration <= 9:
            analysis['duration_category'] = 'optimal'
            analysis['duration_quality'] = 'good'
        elif duration <= 10:
            analysis['duration_category'] = 'long'
            analysis['duration_quality'] = 'fair'
        else:
            analysis['duration_category'] = 'excessive'
            analysis['duration_quality'] = 'poor'

        # Analyze sleep stages if available
        if session['stages']:
            stage_analysis = self._analyze_sleep_stages(session['stages'])
            analysis['stage_analysis'] = stage_analysis
            analysis['sleep_efficiency'] = stage_analysis['sleep_efficiency']
        else:
            analysis['stage_analysis'] = None
            # Estimate efficiency based on duration
            if duration >= 7:
                analysis['sleep_efficiency'] = 85.0
            else:
                analysis['sleep_efficiency'] = 75.0

        # Analyze timing
        bedtime_hour = session['start_time'].hour
        waketime_hour = session['end_time'].hour

        if 21 <= bedtime_hour <= 23:
            analysis['bedtime_quality'] = 'optimal'
        elif 20 <= bedtime_hour < 21 or 23 < bedtime_hour <= 24:
            analysis['bedtime_quality'] = 'acceptable'
        else:
            analysis['bedtime_quality'] = 'poor'

        if 6 <= waketime_hour <= 8:
            analysis['waketime_quality'] = 'optimal'
        elif 5 <= waketime_hour < 6 or 8 < waketime_hour <= 9:
            analysis['waketime_quality'] = 'acceptable'
        else:
            analysis['waketime_quality'] = 'poor'

        analyzed.append(analysis)

    return analyzed
```

### 3. Sleep Stage Analysis

```python
def _analyze_sleep_stages(
    self,
    stages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze sleep stage distribution"""

    stage_durations = {
        'AWAKE': 0,
        'LIGHT': 0,
        'DEEP': 0,
        'REM': 0,
        'UNKNOWN': 0,
    }

    total_duration = 0

    for stage in stages:
        try:
            stage_type = stage.get('stage')
            start_epoch = stage.get('startTime', {}).get('epochMillis')
            end_epoch = stage.get('endTime', {}).get('epochMillis')

            if start_epoch and end_epoch and stage_type:
                duration_hours = (end_epoch - start_epoch) / (1000 * 3600)
                stage_durations[stage_type] = stage_durations.get(stage_type, 0) + duration_hours
                total_duration += duration_hours

        except (KeyError, TypeError):
            continue

    # Calculate percentages
    stage_percentages = {}
    if total_duration > 0:
        for stage, duration in stage_durations.items():
            stage_percentages[stage] = (duration / total_duration) * 100

    # Calculate sleep efficiency
    total_sleep = stage_durations.get('LIGHT', 0) + stage_durations.get('DEEP', 0) + stage_durations.get('REM', 0)
    sleep_efficiency = (total_sleep / total_duration * 100) if total_duration > 0 else 0

    # Assess stage distribution quality
    distribution_quality = self._assess_stage_distribution(stage_percentages)

    return {
        'stage_durations_hours': stage_durations,
        'stage_percentages': stage_percentages,
        'total_duration_hours': total_duration,
        'total_sleep_hours': total_sleep,
        'sleep_efficiency': round(sleep_efficiency, 1),
        'distribution_quality': distribution_quality,
    }

def _assess_stage_distribution(
    self,
    stage_percentages: Dict[str, float]
) -> str:
    """Assess quality of sleep stage distribution"""

    # Check if stages are within optimal ranges
    issues = []

    deep_pct = stage_percentages.get('DEEP', 0)
    if deep_pct < 15:
        issues.append('insufficient_deep_sleep')
    elif deep_pct > 25:
        issues.append('excessive_deep_sleep')

    rem_pct = stage_percentages.get('REM', 0)
    if rem_pct < 20:
        issues.append('insufficient_rem')
    elif rem_pct > 25:
        issues.append('excessive_rem')

    awake_pct = stage_percentages.get('AWAKE', 0)
    if awake_pct > 5:
        issues.append('fragmented_sleep')

    if not issues:
        return 'optimal'
    elif len(issues) == 1:
        return 'good'
    else:
        return 'poor'
```

### 4. Sleep Metrics Calculation

```python
def _calculate_sleep_metrics(
    self,
    analyzed_sessions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Calculate aggregate sleep metrics"""

    if not analyzed_sessions:
        return {'insufficient_data': True}

    # Average sleep duration
    durations = [s['duration_hours'] for s in analyzed_sessions]
    avg_duration = statistics.mean(durations)

    # Sleep consistency (standard deviation of durations)
    duration_std = statistics.stdev(durations) if len(durations) > 1 else 0

    # Average sleep efficiency
    efficiencies = [s['sleep_efficiency'] for s in analyzed_sessions]
    avg_efficiency = statistics.mean(efficiencies)

    # Count sessions by quality
    optimal_count = sum(1 for s in analyzed_sessions if s['duration_quality'] == 'good')
    poor_count = sum(1 for s in analyzed_sessions if s['duration_quality'] == 'poor')

    # Assess overall sleep health
    if avg_duration >= 7 and avg_duration <= 9 and duration_std < 1:
        sleep_health = 'excellent'
    elif avg_duration >= 6.5 and avg_duration <= 9.5 and duration_std < 1.5:
        sleep_health = 'good'
    elif avg_duration >= 6:
        sleep_health = 'fair'
    else:
        sleep_health = 'poor'

    return {
        'total_sessions': len(analyzed_sessions),
        'avg_duration_hours': round(avg_duration, 1),
        'duration_std_hours': round(duration_std, 2),
        'avg_sleep_efficiency': round(avg_efficiency, 1),
        'optimal_sessions_count': optimal_count,
        'poor_sessions_count': poor_count,
        'sleep_health_status': sleep_health,
    }
```

### 5. Pattern Identification

```python
def _identify_sleep_patterns(
    self,
    analyzed_sessions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Identify sleep patterns and consistency"""

    patterns = {
        'consistency': None,
        'bedtime_consistency': None,
        'weekend_vs_weekday': None,
        'sleep_debt': None,
    }

    if len(analyzed_sessions) < 7:
        return patterns

    # Bedtime consistency
    bedtimes = [s['start_time'].hour + s['start_time'].minute/60 for s in analyzed_sessions]
    bedtime_std = statistics.stdev(bedtimes) if len(bedtimes) > 1 else 0

    if bedtime_std < 0.5:  # Within 30 minutes
        patterns['bedtime_consistency'] = 'excellent'
    elif bedtime_std < 1.0:  # Within 1 hour
        patterns['bedtime_consistency'] = 'good'
    else:
        patterns['bedtime_consistency'] = 'poor'

    # Sleep duration consistency
    durations = [s['duration_hours'] for s in analyzed_sessions]
    duration_std = statistics.stdev(durations) if len(durations) > 1 else 0

    if duration_std < 0.5:
        patterns['consistency'] = 'excellent'
    elif duration_std < 1.0:
        patterns['consistency'] = 'good'
    else:
        patterns['consistency'] = 'poor'

    # Weekday vs weekend (if we have enough data)
    if len(analyzed_sessions) >= 14:
        weekday_sessions = [
            s for s in analyzed_sessions
            if s['start_time'].weekday() < 5
        ]
        weekend_sessions = [
            s for s in analyzed_sessions
            if s['start_time'].weekday() >= 5
        ]

        if weekday_sessions and weekend_sessions:
            weekday_avg = statistics.mean([s['duration_hours'] for s in weekday_sessions])
            weekend_avg = statistics.mean([s['duration_hours'] for s in weekend_sessions])

            diff = abs(weekend_avg - weekday_avg)

            patterns['weekend_vs_weekday'] = {
                'weekday_avg': round(weekday_avg, 1),
                'weekend_avg': round(weekend_avg, 1),
                'difference_hours': round(diff, 1),
                'sleep_debt': diff > 1.0  # Significant difference suggests weekday sleep debt
            }

    return patterns
```

### 6. Narrative Generation

```python
def _generate_narrative(
    self,
    analyzed_sessions: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, Any]
) -> str:
    """Generate clinical narrative from sleep data"""

    narrative_parts = []

    # Summary statement
    total_sessions = metrics['total_sessions']
    avg_duration = metrics['avg_duration_hours']

    summary = (
        f"Sleep data shows {total_sessions} sleep session(s) with average "
        f"duration of {avg_duration} hours."
    )
    narrative_parts.append(summary)

    # Duration assessment
    if 7 <= avg_duration <= 9:
        duration_text = (
            f"Sleep duration is optimal ({avg_duration} hours), "
            f"meeting recommended 7-9 hours for adults."
        )
    elif avg_duration < 7:
        duration_text = (
            f"Sleep duration is below optimal ({avg_duration} hours). "
            f"Aim for 7-9 hours to support health and cognitive function."
        )
    else:
        duration_text = (
            f"Sleep duration is above optimal ({avg_duration} hours). "
            f"Excessive sleep may indicate underlying health issues."
        )
    narrative_parts.append(duration_text)

    # Consistency assessment
    consistency = patterns.get('consistency')
    if consistency == 'excellent':
        consistency_text = (
            "Sleep schedule is very consistent, which supports healthy "
            "circadian rhythm."
        )
        narrative_parts.append(consistency_text)
    elif consistency == 'poor':
        consistency_text = (
            "Sleep schedule shows high variability. Improving consistency "
            "can enhance sleep quality and daytime alertness."
        )
        narrative_parts.append(consistency_text)

    # Sleep efficiency
    avg_efficiency = metrics.get('avg_sleep_efficiency', 0)
    if avg_efficiency >= 90:
        efficiency_text = f"Sleep efficiency is excellent ({avg_efficiency}%)."
    elif avg_efficiency >= 85:
        efficiency_text = f"Sleep efficiency is good ({avg_efficiency}%)."
    else:
        efficiency_text = (
            f"Sleep efficiency is below optimal ({avg_efficiency}%). "
            f"Consider sleep hygiene improvements."
        )
    narrative_parts.append(efficiency_text)

    # Weekend vs weekday pattern
    weekend_pattern = patterns.get('weekend_vs_weekday')
    if weekend_pattern:
        diff = weekend_pattern['difference_hours']
        if diff > 1.0:
            weekend_text = (
                f"Weekend sleep is {diff} hours longer than weekday sleep, "
                f"suggesting weekday sleep debt. Aim for consistent sleep "
                f"throughout the week."
            )
            narrative_parts.append(weekend_text)

    # Recommendations
    recommendations = []

    if avg_duration < 7:
        recommendations.append("increase sleep duration to 7-9 hours")

    if consistency == 'poor':
        recommendations.append("establish consistent bedtime and wake time")

    if avg_efficiency < 85:
        recommendations.append("practice sleep hygiene (dark room, cool temperature, no screens)")

    if recommendations:
        rec_text = f"Recommendations: {'; '.join(recommendations)}."
        narrative_parts.append(rec_text)

    return " ".join(narrative_parts)
```

### 7. Clinical Insights Extraction

```python
def _extract_clinical_insights(
    self,
    analyzed_sessions: List[Dict[str, Any]],
    patterns: Dict[str, Any],
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """Extract structured clinical insights for AI training"""

    # Count sessions by quality
    optimal_sessions = sum(
        1 for s in analyzed_sessions if s['duration_quality'] == 'good'
    )
    poor_sessions = sum(
        1 for s in analyzed_sessions if s['duration_quality'] == 'poor'
    )

    return {
        'record_type': 'SleepSessionRecord',
        'total_sessions': len(analyzed_sessions),
        'optimal_sessions': optimal_sessions,
        'poor_sessions': poor_sessions,
        'sleep_metrics': metrics,
        'sleep_patterns': patterns,
        'sleep_health_status': metrics.get('sleep_health_status', 'unknown'),
    }
```

---

## Sample Narrative Output

**Input**: 30 sleep sessions over 30 days

**Generated Narrative**:
```
Sleep data shows 30 sleep session(s) with average duration of 7.2 hours. Sleep
duration is optimal (7.2 hours), meeting recommended 7-9 hours for adults. Sleep
schedule is very consistent, which supports healthy circadian rhythm. Sleep
efficiency is excellent (92%). Weekend sleep is 1.5 hours longer than weekday
sleep, suggesting weekday sleep debt. Aim for consistent sleep throughout the week.
Recommendations: establish consistent bedtime and wake time.
```

---

## Implementation Checklist

### Week 1: Sleep Processor
- [ ] Create processor module structure
- [ ] Implement `SleepProcessor` class
- [ ] Implement session extraction
- [ ] Implement session analysis (duration, timing, quality)
- [ ] Implement sleep stage analysis
- [ ] Implement metrics calculation
- [ ] Implement pattern identification
- [ ] Implement narrative generation
- [ ] Implement clinical insights extraction
- [ ] Write unit tests (>80% coverage)
- [ ] Write integration tests
- [ ] Document clinical logic

---

## Success Criteria

**Module Complete When:**
- ✅ Implements `BaseClinicalProcessor` interface
- ✅ Processes SleepSessionRecord Avro files correctly
- ✅ Analyzes sleep duration and quality
- ✅ Calculates sleep efficiency
- ✅ Identifies sleep patterns
- ✅ Generates clinically accurate narratives
- ✅ Unit tests: >80% coverage
- ✅ Integration tests passing

---

**End of Module 3c Specification**
