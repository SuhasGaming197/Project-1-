# CS5291 Project 1: LLM-Based HLS Testbench Generation

This repository contains the implementation for **Project 1: LLM-Based HLS Testbench Generation and Coverage Evaluation**. The goal is to evaluate if LLMs can generate corner-case-oriented testbenches that achieve higher RTL coverage than random or manual tests, and to measure the gap between C-level coverage and RTL-level coverage after High-Level Synthesis (HLS).

## Features
- **3 Testbench Strategies**: Random generation, Manual corner-cases, and LLM-generated (via OpenRouter/Claude/Gemini).
- **C-Level Coverage**: Uses GCC + gcov + lcov to measure line and branch coverage on the C sources.
- **RTL-Level Coverage**: Uses Bambu HLS to synthesize C to Verilog, and Verilator/Icarus Verilog to measure RTL toggle and line coverage.
- **Agentic Feedback Loop**: Feeds RTL coverage gaps (untoggled signals) back to the LLM to iteratively improve the testbench.
- **Mock Mode**: Can run the entire pipeline and generate reports even without an HLS tool installed.

## Directory Structure
```
project1/
├── benchmarks/           # CHStone source files (adpcm, dfmul, aes, gsm)
├── testbenches/          # Generated testbenches (random, manual, llm)
├── results/              # Coverage outputs (.info, .dat, .json)
├── pipeline/             # Python automation scripts
│   ├── generate_tb.py    # Generates C testbenches
│   ├── run_pipeline.py   # Master orchestration script
│   ├── agentic_loop.py   # LLM refinement loop
│   ├── extract_coverage.py # Parsers for lcov and verilator
│   └── plot_results.py   # Generates charts and HTML report
├── report/               # Final plots, CSVs, and HTML summary
├── config.yaml           # API keys and pipeline configuration
└── setup.sh              # Ubuntu/WSL installation script
```

## Quick Start (Ubuntu / WSL)

**1. Install Prerequisites**
Run the setup script to install `gcc`, `lcov`, `verilator`, and `bambu`:
```bash
bash setup.sh
```

**2. Configure API Key**
Open `config.yaml` and paste your OpenRouter API key. The project is currently configured to use `google/gemini-flash-1.5` (free tier).

**3. Run the Pipeline**
Run the full experiment across all benchmarks and strategies:
```bash
python3 pipeline/run_pipeline.py
```
*(If you don't have Bambu HLS installed, run with `--hls mock` to simulate the synthesis step).*

**4. Generate Reports**
```bash
python3 pipeline/plot_results.py
```
This will generate the coverage comparison charts and an HTML report in the `report/` directory.

## Agentic Loop
To run the iterative LLM improvement loop on a specific benchmark (e.g., ADPCM) until it reaches 90% toggle coverage:
```bash
python3 pipeline/agentic_loop.py --benchmark adpcm --target 90.0
```
