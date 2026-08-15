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

# Install Python dependencies (cached separately from Playwright)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

EXPOSE 4567

CMD ["python", "app.py"]
