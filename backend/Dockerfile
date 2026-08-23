FROM python:3.12-slim AS base

# Create a non-root user matching docker-compose user: "1000:1000"
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid 1000 --no-create-home --shell /bin/bash appuser

WORKDIR /app

# Install dependencies as root (needed to write to /usr/local)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create receipts directory and set ownership
RUN mkdir -p /app/receipts && chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
