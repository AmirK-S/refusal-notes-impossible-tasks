FROM python:3.12-slim
RUN apt-get update && apt-get install -y git curl ca-certificates bubblewrap util-linux procps && rm -rf /var/lib/apt/lists/*
# Node 22 (Debian's nodejs is too old for current CLIs)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*
RUN pip install pytest==8.4.2
# Pinned to the versions used on the host (2026-10-26)
RUN npm install -g @anthropic-ai/claude-code@2.1.302 @openai/codex@0.164.0 @google/gemini-cli@0.65.0
# Banc 2026-11: the agent runs as this unprivileged user (uid 1000, no sudo). Setup, check and
# secrets never enter the agent container (see ../CORRECTIONS.md).
RUN useradd -m -u 1000 -s /bin/bash agent && chmod 700 /root
WORKDIR /work
