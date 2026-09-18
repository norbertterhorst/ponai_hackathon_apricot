#!/bin/bash

# Quick setup script for Werkorder Expert Backend
# Usage: bash setup.sh

set -e  # Exit on error

echo "🚗 WERKORDER EXPERT - QUICK SETUP"
echo "=================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi
echo "✓ Python found"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Setup database
echo ""
echo "💾 Setting up DuckDB database..."
python backend/setup_duckdb.py

# Done
echo ""
echo "=================================="
echo "✅ SETUP COMPLETE!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Start server:  python backend/app.py"
echo "  2. In new terminal: python backend/test_api.py"
echo ""
echo "Or read README.md for more info"
