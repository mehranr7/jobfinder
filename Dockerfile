# Use Debian Bookworm Slim (Trixie has missing font packages that break Playwright)
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install Playwright first to heavily cache the Chromium binary download
RUN pip install --no-cache-dir playwright==1.42.0

# Set explicit path for Playwright browsers so Docker doesn't strip /root/.cache
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install ONLY Chromium and its system dependencies
RUN playwright install --with-deps chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /ms-playwright/ffmpeg-* \
    && (find / -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true)

# Now copy requirements and install other dependencies
# This way, if you modify requirements.txt, you won't have to redownload Playwright!
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 5000

# Start command
CMD ["python", "app.py"]


