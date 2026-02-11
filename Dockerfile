FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Playwright on Debian
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    wget \
    gnupg \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (skip system dependencies since we installed them manually)
RUN playwright install chromium --with-deps || playwright install chromium

# Copy application code
COPY . .

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]
