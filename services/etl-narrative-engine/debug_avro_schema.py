#!/usr/bin/env python3
"""
Debug script to examine actual Avro file structure.
Helps understand the real field names in sample files.
"""

import json
from pathlib import Path

from fastavro import reader

# Sample files to examine
SAMPLE_FILES = {
    'BloodGlucoseRecord': 'BloodGlucoseRecord_1758407139312.avro',
    'HeartRateRecord': 'HeartRateRecord_1758407139312.avro',
    'SleepSessionRecord': 'SleepSessionRecord_1758407139312.avro',
    'StepsRecord': 'StepsRecord_1758407139312.avro',
    'ActiveCaloriesBurnedRecord': 'ActiveCaloriesBurnedRecord_1758407139312.avro',
    'HeartRateVariabilityRmssdRecord': 'HeartRateVariabilityRmssdRecord_1758407139312.avro',
}

SAMPLE_DIR = Path(__file__).parent.parent.parent.parent / 'docs' / 'sample-avro-files'

for record_type, filename in SAMPLE_FILES.items():
    file_path = SAMPLE_DIR / filename

    if not file_path.exists():
        print(f"⚠️  {record_type}: File not found")
        continue

    with open(file_path, 'rb') as f:
        records = list(reader(f))

    if not records:
        print(f"⚠️  {record_type}: No records found")
        continue

    print(f"\n{'='*60}")
    print(f"{record_type}")
    print(f"{'='*60}")
    print(f"Record count: {len(records)}")
    print(f"\nTop-level fields: {list(records[0].keys())}")
    print("\nFirst record sample:")
    print(json.dumps(records[0], indent=2, default=str)[:500])
    print("...")
