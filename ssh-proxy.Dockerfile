# SSH Proxy Dockerfile
# Linus says: "Don't run apt-get update on every container start. That's just wasteful."

FROM python:3.11-slim

LABEL maintainer="Schema Diff Pro"
LABEL description="SSH Proxy Service for database tunnel connections"

# Install openssh-client at build time, not runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN useradd -m -s /bin/bash sshproxy

# Copy the proxy script
COPY ssh_proxy.py /app/ssh_proxy.py

# Set ownership
RUN chown -R sshproxy:sshproxy /app

# Switch to non-root user
USER sshproxy

WORKDIR /app

# Expose proxy port
EXPOSE 9999

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.settimeout(5); s.connect(('127.0.0.1', 9999)); s.close()" || exit 1

# Run the proxy
CMD ["python", "/app/ssh_proxy.py"]
