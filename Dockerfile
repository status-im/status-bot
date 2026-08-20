# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app

# Copy dependency metadata first (better cache invalidation)
COPY pyproject.toml ./

RUN apt update && apt install git -y
# Install package and dependencies
RUN pip install --no-cache-dir -e .

# Copy source code
COPY . ./

CMD ["python", "main.py"]
