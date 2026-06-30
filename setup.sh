#!/bin/bash

# Real-Time Online Interview System - Quick Setup Script
# This script helps set up the development environment quickly

echo "🚀 Setting up Real-Time Online Interview System..."
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.12."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
REQUIRED_VERSION="3.12"

if [ "$PYTHON_VERSION" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION is required. You have Python $PYTHON_VERSION."
    echo "Please install Python 3.12 and rerun this script."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv-1" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv .venv-1
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source .venv-1/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip, setuptools, and wheel..."
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check if YOLO model exists
if [ ! -f "yolov8n.pt" ]; then
    echo "🤖 Downloading YOLO model..."
    curl -L -o yolov8n.pt https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
fi

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p instance
mkdir -p static/resumes
mkdir -p static/faces

echo ""
echo "🎉 Setup complete!"
echo ""
echo "To run the application:"
echo "1. Activate the virtual environment: source .venv-1/bin/activate"
echo "2. Start the app: python app.py"
echo "3. Open your browser: http://localhost:5000"
echo ""
echo "Admin access: http://localhost:5000/admin"
echo "Admin credentials: admin@example.com / admin123"
echo ""
echo "Happy interviewing! 🎯"