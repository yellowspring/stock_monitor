#!/bin/bash
# Setup script for Crash Probability Index system

echo "=========================================="
echo "Crash Probability Index - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "[1/5] Checking Python version..."
python3 --version

if [ $? -ne 0 ]; then
    echo "Error: Python 3 not found. Please install Python 3.8 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "[2/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo ""
echo "[3/5] Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "[4/5] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies."
    exit 1
fi

# Create necessary directories
echo ""
echo "[5/5] Creating directories..."
mkdir -p models reports visualizations data

# Make scripts executable
chmod +x main.py example.py

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate"
echo "  2. Run quick example: python example.py"
echo "  3. Train model: python main.py --mode train"
echo "  4. Get prediction: python main.py --mode predict"
echo ""
echo "For more information, see README.md"
