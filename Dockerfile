# SovereignSwarm — Dockerfile
# AI agent swarm for freelance automation
FROM python:3.12-slim-bookworm

LABEL maintainer="morningstar"
LABEL org.opencontainers.image.title="SovereignSwarm"

ARG UID=1000 GID=1000

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl wget python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u $UID -g $GID -s /bin/bash agent \
    && mkdir -p /workspace /home/agent/.config \
    && chown -R $UID:$GID /workspace

WORKDIR /workspace
COPY --chown=$UID:$GID SovereignSwarm/ /workspace/SovereignSwarm/

USER agent
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/SovereignSwarm

CMD ["python3", "super_agent.py"]
