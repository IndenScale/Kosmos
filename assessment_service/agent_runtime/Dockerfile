# Agent Runtime Dockerfile
FROM python:3.13.5-slim

# Change APT sources to Alibaba Cloud mirror and install system dependencies
RUN echo "Updating APT sources to Alibaba Cloud mirror..." && \
    echo "deb [trusted=yes] http://mirrors.aliyun.com/debian/ bookworm main non-free-firmware" > /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://mirrors.aliyun.com/debian/ bookworm-updates main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://mirrors.aliyun.com/debian/ bookworm-backports main non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb [trusted=yes] http://mirrors.aliyun.com/debian-security/ bookworm-security main non-free-firmware" >> /etc/apt/sources.list && \
    apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    gcc \
    jq \
    vim \
    nano \
    unzip \
    zip \
    tree \
    htop \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nodejs

# Install qwen CLI tool
RUN npm install -g @qwen-code/qwen-code

# Set working directory
WORKDIR /app

# Copy requirements files from the correct paths relative to build context
# Build context is ./, so we use paths relative to the project root
COPY requirements.txt .
COPY assessment_service/requirements.txt assessment_service/requirements.txt

# Install Python dependencies with Alibaba Cloud mirror
RUN pip install --no-cache-dir --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    pip install --no-cache-dir -r assessment_service/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# Copy application code
COPY . .

# Make shell scripts executable
RUN chmod +x /app/assessment_service/start_agent_runtime.sh

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

# Create kosmos CLI entry point using the new binary script
RUN mkdir -p /home/appuser/.local/bin && \
    cp /app/bin/kosmos /home/appuser/.local/bin/kosmos && \
    chmod +x /home/appuser/.local/bin/kosmos && \
    echo 'export PATH="/home/appuser/.local/bin:$PATH"' >> /home/appuser/.bashrc

# Create Qwen Code configuration directory and copy settings
COPY .qwen/settings.json /tmp/qwen-settings.json
RUN mkdir -p /home/appuser/.qwen && \
    cp /tmp/qwen-settings.json /home/appuser/.qwen/settings.json

# Set Python environment variables
ENV PYTHONPATH=/app