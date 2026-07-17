#!/bin/bash
# Script to run tests for SynologyC2Password-to-Bitwarden

set -e

echo "=========================================="
echo "Running tests for SynologyC2Password-to-Bitwarden"
echo "=========================================="

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing..."
    pip install pytest pytest-cov
fi

# Run tests with coverage
pytest tests/ -v --cov=syno2bw --cov-report=html --cov-report=term

echo ""
echo "=========================================="
echo "Tests completed!"
echo "Coverage report: htmlcov/index.html"
echo "=========================================="
