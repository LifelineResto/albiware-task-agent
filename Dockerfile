FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Playwright requirements
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and its browsers
RUN playwright install-deps chromium
RUN playwright install chromium

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]
