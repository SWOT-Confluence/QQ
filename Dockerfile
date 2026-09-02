# SWOT-Confluence QQ FLPE algorithm — Docker image
#
# Build:
#   docker build -t qq:latest .
#
# Run (production):
#   docker run --rm \
#     -e AWS_BATCH_JOB_ARRAY_INDEX=0 \
#     -v /path/to/mnt/input:/mnt/data/input:ro \
#     -v /path/to/mnt/flpe/qq:/mnt/data/flpe/qq \
#     qq:latest /mnt/data/input/reaches.json
#
# Run (local test, single reach):
#   docker run --rm \
#     -v /path/to/mnt/input:/mnt/data/input:ro \
#     -v /path/to/mnt/flpe/qq:/mnt/data/flpe/qq \
#     qq:latest /mnt/data/input/reaches.json --index 0

# FROM python:3.11-slim AS base
FROM python:3.11-slim


WORKDIR /app

# Install Python dependencies first (layer cached independently of source)
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# Copy package metadata and source
COPY pyproject.toml ./
COPY README.md ./
COPY qq/ ./qq/
COPY run_qq.py ./

# Install QQ itself so Python package metadata is available at runtime.
RUN pip install --no-cache-dir --no-deps .




# Default production paths are baked into config.py as constants;
# they can be overridden at runtime via --input_dir / --output_dir.
ENV PYTHONUNBUFFERED=1


# Git provenance is injected by the release workflow.
ARG GIT_COMMIT=unknown
ARG GIT_DESCRIBE=unknown

ENV QQ_GIT_COMMIT=${GIT_COMMIT}
ENV QQ_GIT_DESCRIBE=${GIT_DESCRIBE}

LABEL maintainer="SWOT-Confluence"
LABEL description="SWOT-Confluence QQ discharge estimation algorithm: reach-based quantile-quantile mapping"

LABEL org.opencontainers.image.revision=${GIT_COMMIT}
LABEL org.opencontainers.image.version=${GIT_DESCRIBE}



ENTRYPOINT ["python", "run_qq.py"]
CMD ["--help"]
