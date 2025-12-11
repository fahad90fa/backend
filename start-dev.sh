#!/bin/bash

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
fi

# Start the server
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
