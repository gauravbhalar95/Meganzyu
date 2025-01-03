# Use a Python base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements.txt file to the container
COPY requirements.txt /app/

# Install the required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . /app/

# Set environment variables (you can pass these at runtime if needed)
ENV API_TOKEN=""
ENV WEBHOOK_URL=""

# Expose port 8080 for Flask
EXPOSE 8080

# Command to run the Flask app
CMD python Bot.py
