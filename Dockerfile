# Use the official Microsoft Playwright image as the base
# This image already contains the system dependencies required to run headless browsers
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Explicitly install the Chromium browser for Playwright
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Expose the Flask port
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
