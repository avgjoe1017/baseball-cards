# Use a multi-stage build to reduce the final image size
# Stage 1: Build stage
FROM python:3.12-slim AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime stage
FROM python:3.12-slim

# Set environment variables to prevent interactive prompts during build
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies (like cron and curl)
RUN apt-get update && apt-get install -y --no-install-recommends cron curl && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Reorder the commands to ensure the file is created before setting permissions
RUN touch /var/log/cron.log && \
    echo "0 * * * * cd /app && make crawl >> /var/log/cron.log 2>&1" > /etc/cron.d/cardfinder-cron && \
    chmod 0644 /etc/cron.d/cardfinder-cron && \
    crontab /etc/cron.d/cardfinder-cron && \
    touch /var/log/cron.log

# Add a health check to monitor the container's health
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run cron in the foreground and tail the log file
# CMD cron && tail -f /var/log/cron.log
# Using just cron -f based on common practice
CMD ["cron", "-f"]