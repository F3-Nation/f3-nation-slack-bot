FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 APP_HOME=/app
WORKDIR $APP_HOME

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates gnupg && \
    rm -rf /var/lib/apt/lists/*

# Install scripts superset deps
COPY requirements-scripts.txt ./requirements-scripts.txt
RUN pip install --no-cache-dir -r requirements-scripts.txt

# Playwright for dataframe_image export
RUN pip install --no-cache-dir playwright
RUN python -m playwright install chromium && python -m playwright install-deps

COPY . ./

# Default command for a Job; can be overridden by Job args
CMD ["python", "-m", "scripts.hourly_runner"]