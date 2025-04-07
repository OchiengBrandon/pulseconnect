#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --no-input

# Run database migrations
python manage.py migrate

# Check if the superuser should be created
if [[ $CREATE_SUPERUSER ]]; then
  # Check if the superuser already exists
  if ! python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(email='$DJANGO_SUPERUSER_EMAIL').exists())" | grep -q "True"; then
    python manage.py createsuperuser --no-input --email "$DJANGO_SUPERUSER_EMAIL" --username "$DJANGO_SUPERUSER_USERNAME"
  else
    echo "Superuser already exists."
  fi
fi

# Start the application with Gunicorn
exec gunicorn pulseconnect.wsgi:application --bind 0.0.0.0