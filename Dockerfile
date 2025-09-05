# Single-stage build for GoodWe Dynamic Price Optimiser
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies globally
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd -m -u 1000 goodwe && \
    mkdir -p /app/data /app/logs /app/out /app/config && \
    chown -R goodwe:goodwe /app

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY README.md .
COPY LICENSE .

# Copy optional directories
COPY scripts/ ./scripts/
COPY systemd/ ./systemd/
COPY docs/ ./docs/

# Copy entrypoint script
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Set ownership
RUN chown -R goodwe:goodwe /app

# Switch to non-root user
USER goodwe

# Expose port for health checks
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Set entrypoint
ENTRYPOINT ["./docker-entrypoint.sh"]

# Default command
CMD ["python", "src/master_coordinator.py"]
