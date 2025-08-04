ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}

ARG CACHEBUST=1
ENV PYTHONUNBUFFERED True

# Install Node.js for nodemon (development)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# Install nodemon globally (for development)
RUN npm install -g nodemon

# Set Python environment
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

ENV APP_HOME /app
WORKDIR $APP_HOME

# Copy requirements file first for better layer caching
COPY requirements.txt ./

# Verify Python version and install dependencies via pip
RUN python --version
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . ./

# Environment variables for Google Cloud Functions
ENV GOOGLE_FUNCTION_TARGET=handler
EXPOSE 3000

# Default command runs main.py directly
CMD ["python", "main.py"]
