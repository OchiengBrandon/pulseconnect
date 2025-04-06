#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Start Gunicorn
gunicorn pulseconnect.wsgi:application --bind 0.0.0.0:8000