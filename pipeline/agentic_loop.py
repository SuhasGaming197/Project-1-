"""
pipeline/agentic_loop.py
------------------------
Implements the agentic feedback loop from the PDF:
  1. Generate LLM testbench
  2. Run C + RTL simulation → get coverage
  3. Find uncovered signals/lines
  4. Feed them back to LLM → refined testbench
  5. Repeat until toggle_coverage >= target or max_iterations reached

Usage:
  python pipeline/agentic_loop.py --benchmark adpcm
  python pipeline/agentic_loop.py --benchmark adpcm --max-iter 5 --target 90
"""

import os
import sys
import json
import argparse
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))

from generate_tb import generate_llm_tb, save_tb, read_benchmark_source, get_openrouter_client
from run_pipeline import (
    run_c_simulation_with_coverage,
    run_hls_synthesis,
    run_rtl_simulation_with_coverage,
)
from extract_coverage import get_uncovered_signals, parse_lcov

from openai import OpenAI


def load_config():
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)


# ─────────────────────────────────────────────────────────────
# LLM refinement call
# ─────────────────────────────────────────────────────────────

REFINE_SYSTEM = """\
You are an expert HLS verification engineer.
Given a C testbench and a list of RTL signals that were never toggled
(0→1 or 1→0) during the last simulation, your job is to add new test
vectors to the testbench that will force those signals to change state.
Output ONLY valid C code. No markdown fences, no explanations.
"""

def refine_tb_with_llm(current_tb: str, uncovered_signals: list,
                        uncovered_lines: list, benchmark: str, cfg: dict) -> str:
    """Feed coverage gaps back to the LLM to refine the testbench."""
    client = get_openrouter_client(cfg)

    signal_report = "\n".join(
        [f"  - RTL signal '{s}' was NEVER toggled 0→1 or 1→0" for s in uncovered_signals[:20]]
    ) or "  (no specific signal data — improve overall branch coverage)"

    line_report = "\n".join(
        [f"  - C line not executed: {l}" for l in uncovered_lines[:20]]
    ) or "  (no specific uncovered lines)"

    source = read_benchmark_source(benchmark)

    user_msg = f"""\
Benchmark: {benchmark}

=== UNCOVERED RTL SIGNALS (must be toggled) ===
{signal_report}

=== UNCOVERED C LINES (must be executed) ===
{line_report}

=== CURRENT TESTBENCH ===
{current_tb}

=== BENCHMARK SOURCE ===
{source}

Please modify the testbench to add NEW test vectors that will:
1. Force the uncovered RTL signals to toggle
2. Execute the uncovered C lines/branches
Keep all existing test vectors and APPEND new ones.
Output ONLY the complete, updated C testbench code.
"""

    response = client.chat.completions.create(
        model=cfg["openrouter_model"],
        max_tokens=4096,
        messages=[
            {"role": "system", "content": REFINE_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/cs5291/project1",
            "X-Title": "CS5291 Project 1 - Agentic Coverage Loop",
        },
    )
    return response.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────
# Helper: extract uncovered C lines from lcov info
# ─────────────────────────────────────────────────────────────

def get_uncovered_c_lines(benchmark: str, tb_type: str) -> list:
    info_file = os.path.join(
        ROOT, "results", "c_coverage", f"{benchmark}_{tb_type}", "coverage.info"
    )
    if not os.path.exists(info_file):
        return []

    uncovered = []
    current_file = None
    with open(info_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SF:"):
                current_file = os.path.basename(line[3:])
            elif line.startswith("DA:"):
                # DA:<line_number>,<execution_count>
                parts = line[3:].split(",")
                if len(parts) == 2 and parts[1].strip() == "0":
                    uncovered.append(f"{current_file}:{parts[0]}")
    return uncovered


# ─────────────────────────────────────────────────────────────
# Main agentic loop
# ─────────────────────────────────────────────────────────────

def agentic_coverage_improvement(benchmark: str, max_iterations: int = 5,
                                  target_pct: float = 90.0) -> list:
    """
    Iteratively improve testbench until RTL toggle coverage >= target_pct%.
    Returns: list of dicts with per-iteration metrics.
    """
    cfg      = load_config()
    history  = []
    tb_code  = None

    print(f"\n{'='*60}")
    print(f" AGENTIC LOOP — {benchmark.upper()}")
    print(f" Target: RTL toggle coverage >= {target_pct:.0f}%")
    print(f" Max iterations: {max_iterations}")
    print(f"{'='*60}")

    # Synthesize RTL once (shared across iterations)
    run_hls_synthesis(benchmark)

    for iteration in range(max_iterations):
        print(f"\n{'─'*50}")
        print(f" Iteration {iteration + 1} / {max_iterations}")
        print(f"{'─'*50}")

        # ── 1. Generate / refine testbench ──────────────────
        if iteration == 0:
            print(" [LLM] Generating initial corner-case testbench...")
            tb_code = generate_llm_tb(benchmark, cfg)
        else:
            print(" [LLM] Refining testbench based on coverage gaps...")
            dat_file = os.path.join(
                ROOT, "results", "rtl_coverage",
                f"{benchmark}_llm_iter", "coverage.dat"
            )
            uncovered_signals = get_uncovered_signals(dat_file)
            uncovered_lines   = get_uncovered_c_lines(benchmark, "llm_iter")
            print(f"   Uncovered RTL signals: {len(uncovered_signals)}")
            print(f"   Uncovered C lines:     {len(uncovered_lines)}")
            tb_code = refine_tb_with_llm(
                tb_code, uncovered_signals, uncovered_lines, benchmark, cfg
            )

        # Save testbench
        save_tb(benchmark, "llm", tb_code, iteration=iteration)
        # Also save as "llm_iter" so run_pipeline picks it up
        save_tb(benchmark, "llm_iter", tb_code)

        # ── 2. Run C + RTL simulation ────────────────────────
        print(" [SIM] Running C coverage simulation...")
        c_cov = run_c_simulation_with_coverage(benchmark, "llm_iter")

        print(" [SIM] Running RTL coverage simulation...")
        rtl_cov = run_rtl_simulation_with_coverage(benchmark, "llm_iter")

        toggle_pct = rtl_cov.get("toggle_pct", 0.0)
        line_pct   = c_cov.get("line_pct",     0.0)

        record = {
            "iteration":      iteration + 1,
            "c_line_pct":     line_pct,
            "c_branch_pct":   c_cov.get("branch_pct", 0.0),
            "rtl_line_pct":   rtl_cov.get("line_pct",  0.0),
            "rtl_toggle_pct": toggle_pct,
        }
        history.append(record)

        print(f"\n  ✔  C line={line_pct:.1f}%  RTL toggle={toggle_pct:.1f}%")

        if toggle_pct >= target_pct:
            print(f"\n  🎯 Target reached ({toggle_pct:.1f}% >= {target_pct:.0f}%)!")
            break

    # Save history JSON
    hist_path = os.path.join(ROOT, "results", "rtl_coverage", f"{benchmark}_agentic_history.json")
    os.makedirs(os.path.dirname(hist_path), exist_ok=True)
    with open(hist_path, "w") as f:
        json.dump(history, f, indent=2)
    print(f"\n[agentic_loop] History saved: {hist_path}")

    # Print summary
    print(f"\n{'─'*50}")
    print(f" {'Iter':>4}  {'C Line%':>8}  {'C Branch%':>10}  {'RTL Line%':>10}  {'RTL Toggle%':>12}")
    for h in history:
        print(f"  {h['iteration']:>3}   {h['c_line_pct']:>7.1f}%   "
              f"{h['c_branch_pct']:>9.1f}%   {h['rtl_line_pct']:>9.1f}%   "
              f"{h['rtl_toggle_pct']:>10.1f}%")
    print(f"{'─'*50}")

    return history


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agentic LLM testbench improvement loop")
    parser.add_argument("--benchmark", required=True, choices=["adpcm", "aes", "dfmul", "gsm"])
    parser.add_argument("--max-iter",  type=int,   default=5)
    parser.add_argument("--target",    type=float, default=90.0,
                        help="Stop when RTL toggle coverage exceeds this %%")
    args = parser.parse_args()

    agentic_coverage_improvement(args.benchmark, args.max_iter, args.target)
