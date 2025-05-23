# This script is used to set up the environment for the Django application
# and wait for PostgreSQL to be ready before running migrations and starting the server.
# It is executed when the Docker container starts.
# Make sure to give execute permissions to this script
# before building the Docker image.
# Usage: chmod +x entrypoint.sh

#!/bin/sh

# Print the environment variables to verify if they are being set properly
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"

echo "Waiting for PostgreSQL to start..."

# Wait until PostgreSQL is ready
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done

echo "PostgreSQL started!"

# Run migrations
python manage.py migrate

# Start the server
exec python manage.py runserver 0.0.0.0:8000
