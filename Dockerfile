# Dockerfile

FROM python:3.10-slim

# Install required packages
RUN apt-get update && apt-get install -y chromium ffmpeg wget unzip

WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt

# Copy the project files
COPY . .

# Expose the API port
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
