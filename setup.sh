#!/usr/bin/env bash
# setup.sh — Install all tools for CS5291 Project 1 on Ubuntu/WSL
# Run this inside WSL: bash setup.sh

set -e
echo "=== CS5291 Project 1 — Tool Setup ==="

# ── System packages ────────────────────────────────────────────────────────
echo "[1/4] Installing system packages..."
sudo apt-get update -qq
sudo apt-get install -y \
    gcc \
    lcov \
    verilator \
    iverilog \
    git \
    python3 \
    python3-pip \
    bambu-framework \
    2>/dev/null || true

# If bambu-framework not in apt, try PPA
if ! command -v bambu &>/dev/null; then
    echo "  bambu not in apt — trying PPA..."
    sudo apt-get install -y software-properties-common
    sudo add-apt-repository -y ppa:nicologhielmetti/bambu
    sudo apt-get update -qq
    sudo apt-get install -y bambu-framework || echo "  [WARN] bambu install failed — using mock HLS mode"
fi

# ── Python dependencies ────────────────────────────────────────────────────
echo "[2/4] Installing Python dependencies..."
pip3 install --quiet openai pyyaml pandas matplotlib tabulate

# ── Clone CHStone benchmarks ───────────────────────────────────────────────
echo "[3/4] Downloading CHStone benchmarks..."
if [ ! -d "chstone" ]; then
    git clone https://github.com/CHSTONE/chstone.git chstone
    echo "  Copying CHStone sources into benchmarks/..."
    cp chstone/adpcm/src/*.c  benchmarks/adpcm/ 2>/dev/null || true
    cp chstone/adpcm/src/*.h  benchmarks/adpcm/ 2>/dev/null || true
    cp chstone/aes/src/*.c    benchmarks/aes/   2>/dev/null || true
    cp chstone/aes/src/*.h    benchmarks/aes/   2>/dev/null || true
    cp chstone/dfmul/src/*.c  benchmarks/dfmul/ 2>/dev/null || true
    cp chstone/dfmul/src/*.h  benchmarks/dfmul/ 2>/dev/null || true
    cp chstone/gsm/src/*.c    benchmarks/gsm/   2>/dev/null || true
    cp chstone/gsm/src/*.h    benchmarks/gsm/   2>/dev/null || true
fi

# ── Version check ─────────────────────────────────────────────────────────
echo ""
echo "[4/4] Tool version check:"
gcc       --version | head -1 || echo "  gcc: NOT FOUND"
lcov      --version | head -1 || echo "  lcov: NOT FOUND"
verilator --version | head -1 || echo "  verilator: NOT FOUND"
iverilog  -V        2>&1 | head -1 || echo "  iverilog: NOT FOUND"
bambu     --version 2>&1 | head -1 || echo "  bambu: NOT FOUND (mock mode will be used)"
python3   --version        || echo "  python3: NOT FOUND"

echo ""
echo "=== Setup complete! ==="
echo "Next: set your OpenRouter key in config.yaml, then run:"
echo "  python3 pipeline/run_pipeline.py --hls mock"
