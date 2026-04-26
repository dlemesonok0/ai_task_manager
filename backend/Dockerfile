FROM python:3.11-slim

WORKDIR /app

# Install dependencies (using uv for faster install if we wanted to, but standard pip is fine in official images)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY . .

# We don't define CMD or ENTRYPOINT here because docker-compose will define 
# different commands for the API and the Bot containers.
