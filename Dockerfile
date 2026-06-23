# Use a lightweight Python base image instead of the massive Playwright image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy requirements first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install ONLY Chromium and its specific system dependencies
# This avoids downloading Firefox, WebKit, and unnecessary OS libraries
RUN playwright install --with-deps chromium

# Copy the rest of the application
COPY . .

# Expose the Flask port
EXPOSE 5000

# Start the Flask app
CMD ["python", "app.py"]
