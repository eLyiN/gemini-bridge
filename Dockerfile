FROM node:18-slim

# Set working directory
WORKDIR /app

# Install Python and pip
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Gemini CLI globally
RUN npm install -g @google/gemini-cli

# Copy Python project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip3 install .

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080
ENV GEMINI_BRIDGE_TIMEOUT=60

# Health check to verify Gemini CLI is available
RUN gemini --version

# Expose port
EXPOSE $PORT

# Run the MCP server
CMD ["python3", "-m", "src"]