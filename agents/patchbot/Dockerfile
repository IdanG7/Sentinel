FROM python:3.11-slim

# Install git
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy agent SDK first (dependency)
COPY libs/agent-sdk /app/libs/agent-sdk

# Install agent SDK
RUN pip install --no-cache-dir -e /app/libs/agent-sdk

# Copy patchbot files
COPY agents/patchbot/pyproject.toml /app/
COPY agents/patchbot/patchbot /app/patchbot/

# Install patchbot
RUN pip install --no-cache-dir -e .

# Create workspace directory
RUN mkdir -p /tmp/patchbot-workspace

# Create non-root user
RUN useradd -m -u 1000 patchbot && chown -R patchbot:patchbot /app /tmp/patchbot-workspace
USER patchbot

# Run patchbot
CMD ["python", "-m", "patchbot.agent"]
