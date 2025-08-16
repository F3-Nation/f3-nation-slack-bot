FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    GOOGLE_FUNCTION_TARGET=handler

# Install base deps and Python 3.12 from deadsnakes (no distutils package in 3.12)
RUN apt-get update && apt-get install -y --no-install-recommends \
      software-properties-common curl ca-certificates gnupg wget \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y --no-install-recommends \
      python3.12 python3.12-venv python3.12-dev build-essential \
    && curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3.12 get-pip.py \
    && ln -s /usr/bin/python3.12 /usr/local/bin/python \
    && rm get-pip.py \
    && apt-get purge -y software-properties-common \
    && apt-get autoremove -y && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR $APP_HOME

# Copy and install Python deps first
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser + system deps (runs apt internally)
RUN python -m playwright install chromium && \
    python -m playwright install-deps

# Copy application code
COPY . ./

EXPOSE 8080
CMD ["functions-framework", "--target", "handler", "--port", "8080"]