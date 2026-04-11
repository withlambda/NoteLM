# Copyright (C) 2026 withLambda
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

# 1. BASE IMAGE
FROM vllm/vllm-openai:v0.18.0

# 3. ENVIRONMENT SETTINGS
# -- Redirect caches so non-root user can read models downloaded by root --
#
# XDG_CACHE_HOME=/app/cache
# TORCH_HOME=/app/cache/torch
#
# --- Ensure Python always sees the GPU in the same order as the system, to avoid "device not found" errors
#
# CUDA_DEVICE_ORDER=PCI_BUS_ID
#
# --- Prevent CPU Thread Overload ---
# --- Keeps the CPU from choking while the GPU does the heavy lifting ---
#
# TORCH_NUM_THREADS=1
# OMP_NUM_THREADS=1
# MKL_NUM_THREADS=1
# OPENBLAS_NUM_THREADS=1
# VECLIB_MAXIMUM_THREADS=1
# NUMEXPR_NUM_THREADS=1
#
# --- Ensure Predictable CPU Performance ---
#
# MKL_DYNAMIC=FALSE
# OMP_DYNAMIC=FALSE
#
# --- Fix for Sequential GPU Workflows (MinerU -> vLLM) ---
#
# PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
#
# --- vLLM Engine Optimization ---
#
# NCCL_P2P_DISABLE=1

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_INPUT=1 \
    XDG_CACHE_HOME=/app/cache \
    TORCH_HOME=/app/cache/torch \
    CUDA_DEVICE_ORDER=PCI_BUS_ID \
    MKL_DYNAMIC=FALSE \
    TORCH_NUM_THREADS=1 \
    OMP_DYNAMIC=FALSE \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    CC=/usr/bin/gcc \
    PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
    NCCL_P2P_DISABLE=1 \
    MINERU_TOOLS_CONFIG_JSON="/app/mineru.json" \
    MINERU_TOOLS_CONFIG_PATH="/app/mineru.json" \
    DEBUG=false \
    HANDLER_FILE_NAME="handler.py"

# 5. APPLICATION SETUP
WORKDIR /app
COPY requirements.txt ./

RUN mkdir -p ${XDG_CACHE_HOME} && \
    apt-get update \
    && apt-get install -y \
        fonts-noto-core \
        fonts-noto-cjk \
        fontconfig \
        libgl1 \
    && pip install --no-cache-dir --break-system-packages --use-deprecated=legacy-resolver -r requirements.txt \
    && huggingface-cli download opendatalab/MinerU2.5-2509-1.2B --local-dir /app/models/mineru/vlm \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*


COPY *.py block_correction_prompts.json mineru.json ./

# 8. Create Non-Root User (UID 1001) with the name appuser
# Ensure appuser owns the app and cache
RUN groupadd -r appgroup && useradd -r -g appgroup -u 1001 -m -d /home/appuser appuser && \
    chown -R appuser:appgroup /app /home/appuser

# 9. Run as non-root user
USER appuser

# 10. START COMMAND
ENTRYPOINT []
CMD ["sh", "-c", "python3 -u \"${HANDLER_FILE_NAME}\""]
