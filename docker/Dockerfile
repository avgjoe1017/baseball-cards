# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables to prevent interactive prompts during build
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies (like cron)
RUN apt-get update && apt-get install -y --no-install-recommends cron && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /app
COPY . .

# Create log file and set permissions for cron
RUN touch /var/log/cron.log && \
	chmod 0644 /etc/cron.d/cardfinder-cron && \
	echo "0 * * * * cd /app && make crawl >> /var/log/cron.log 2>&1" > /etc/cron.d/cardfinder-cron && \
	crontab /etc/cron.d/cardfinder-cron && \
	touch /var/log/cron.log

# Run cron in the foreground and tail the log file
# CMD cron && tail -f /var/log/cron.log
# Using just cron -f based on common practice
CMD ["cron", "-f"]