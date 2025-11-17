#!/bin/bash
# Run linting and tests for ETL Narrative Engine

set -e  # Exit on error

echo "================================"
echo "Running Ruff Linter..."
echo "================================"
python3 -m ruff check src/ tests/

echo ""
echo "================================"
echo "Running Tests with Coverage..."
echo "================================"
python3 -m pytest

echo ""
echo "✅ All checks passed!"
