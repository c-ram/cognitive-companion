FROM python:3.10-slim

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose ports: 8000 for API, 7860 for Gradio (if running in same container for test)
EXPOSE 8100
EXPOSE 7860

# Command to run the API
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8100"]
