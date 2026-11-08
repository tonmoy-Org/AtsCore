FROM python:3.12-slim

# Prevent Python from writing .pyc and enable buffer-free logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg2 and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

EXPOSE 8000

# Initialize schema and run with Gunicorn multi-worker WSGI server
CMD ["sh", "-c", "python manage.py init-db && gunicorn --bind 0.0.0.0:8000 --workers 4 --threads 2 --timeout 120 manage:app"]

