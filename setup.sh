#!/bin/bash

# Real-Time Online Interview System - Quick Setup Script
# This script helps set up the development environment quickly

echo "🚀 Setting up Real-Time Online Interview System..."
echo ""

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "❌ Python is not installed. Please install Python 3.8 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required. You have Python $PYTHON_VERSION."
    exit 1
fi

echo "✅ Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # macOS/Linux

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

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
echo "1. Activate the virtual environment: venv\Scripts\activate (Windows) or source venv/bin/activate (macOS/Linux)"
echo "2. Start the app: python app.py"
echo "3. Open your browser: http://localhost:5000"
echo ""
echo "Admin access: http://localhost:5000/admin"
echo "Admin credentials: admin@example.com / admin123"
echo ""
echo "Happy interviewing! 🎯"