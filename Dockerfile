# Planfile CI/CD Runner Docker Image
# uv 0.11.28 and Python 3.12.14 are selected by immutable multi-platform
# manifest digests. Keep the human-readable versions in this comment only.
FROM ghcr.io/astral-sh/uv@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa AS uv
FROM python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime

COPY --from=uv /uv /uvx /bin/

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install the local package and all runner integrations from the committed,
# hash-bearing lockfile. Frozen mode refuses to resolve or rewrite anything.
COPY pyproject.toml uv.lock README.md ./
COPY planfile/ ./planfile/
RUN uv sync --frozen --no-dev --extra all --no-editable

# Copy entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create directories
RUN mkdir -p /workspace /app/results

# Set environment variables
ENV PYTHONPATH=/app
ENV WORKSPACE=/workspace
ENV RESULTS_DIR=/app/results
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD planfile --version || exit 1

# Entry point
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["auto", "loop"]
