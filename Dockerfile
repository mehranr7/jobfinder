# Use Debian Slim (Alpine is not supported by Playwright Python)
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install ONLY Chromium and its system dependencies, then violently clean caches
RUN playwright install --with-deps chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache/pip \
    && rm -rf /root/.cache/ms-playwright/ffmpeg-* \
    && find / -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 5000

# Start command
CMD ["python", "app.py"]


