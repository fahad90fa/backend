#!/bin/bash

echo "========================================="
echo "CyberScholar AI - Backend Startup Script"
echo "========================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found!"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your GOOGLE_API_KEY"
fi

# Initialize database
echo "Initializing database..."
python3 -c "from app.database import init_db; init_db()"

# Start the server
echo "Starting FastAPI server..."
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

deactivate
