FROM python:3.12

# Install git for cloning the repository
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Set Poetry configuration
ENV POETRY_NO_INTERACTION=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Set working directory
WORKDIR /f3-data-models

# Add cache-busting argument to force fresh git clone
ARG CACHEBUST=1

# Cache bust and clone F3-Data-Models repository (always get latest)
RUN echo "🔄 Cache bust: $CACHEBUST" && \
    rm -rf F3-Data-Models || true && \
    git clone https://github.com/F3-Nation/F3-Data-Models.git .

# Display F3-Data-Models repository information
RUN echo "======================================="
RUN echo "🏗️  F3-DATA-MODELS REPOSITORY INFO:"
RUN echo "======================================="
RUN echo "📦 Repository: $(git remote get-url origin)"
RUN echo "🏷️  Branch: $(git branch --show-current || echo 'main')"
RUN echo "📝 Latest commit:"
RUN git log --oneline -n 1
RUN echo "🔑 Full commit hash: $(git rev-parse HEAD)"
RUN echo "📅 Commit date: $(git log -1 --format=%cd --date=iso)"
RUN echo "👤 Author: $(git log -1 --format='%an <%ae>')"
RUN echo "======================================="

# Install dependencies
RUN poetry env use python3.12 && \
    poetry install && \
    rm -rf $POETRY_CACHE_DIR

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"] 