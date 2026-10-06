"""
pipeline/extract_coverage.py
----------------------------
Parses coverage reports from:
  - lcov  (.info file) → C line + branch coverage
  - verilator_coverage (.dat file) → RTL line + toggle coverage

Usage:
  python pipeline/extract_coverage.py --type lcov   --file results/c_coverage/adpcm_random/coverage.info
  python pipeline/extract_coverage.py --type verilator --file results/rtl_coverage/adpcm_random/coverage.dat
"""

import re
import os
import json
import argparse


# ─────────────────────────────────────────────────────────────
# LCOV parser  (C-level: line + branch coverage)
# ─────────────────────────────────────────────────────────────

def parse_lcov(info_file: str) -> dict:
    """
    Parse an lcov .info file and return aggregate coverage metrics.
    Returns:
      {
        "line_hit": int, "line_total": int, "line_pct": float,
        "branch_hit": int, "branch_total": int, "branch_pct": float,
        "files": { filename: { "line_pct": float, "branch_pct": float } }
      }
    """
    if not os.path.exists(info_file):
        return _empty_c_coverage()

    line_hit = line_total = branch_hit = branch_total = 0
    files = {}
    current_file = None
    f_lh = f_lt = f_bh = f_bt = 0

    with open(info_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("SF:"):
                current_file = os.path.basename(line[3:])
                f_lh = f_lt = f_bh = f_bt = 0
            elif line.startswith("LH:"):
                f_lh = int(line[3:])
                line_hit += f_lh
            elif line.startswith("LF:"):
                f_lt = int(line[3:])
                line_total += f_lt
            elif line.startswith("BRH:"):
                f_bh = int(line[4:])
                branch_hit += f_bh
            elif line.startswith("BRF:"):
                f_bt = int(line[4:])
                branch_total += f_bt
            elif line == "end_of_record" and current_file:
                files[current_file] = {
                    "line_pct":   _pct(f_lh, f_lt),
                    "branch_pct": _pct(f_bh, f_bt),
                }

    return {
        "line_hit":     line_hit,
        "line_total":   line_total,
        "line_pct":     _pct(line_hit, line_total),
        "branch_hit":   branch_hit,
        "branch_total": branch_total,
        "branch_pct":   _pct(branch_hit, branch_total),
        "files":        files,
    }


def _empty_c_coverage():
    return {
        "line_hit": 0, "line_total": 0, "line_pct": 0.0,
        "branch_hit": 0, "branch_total": 0, "branch_pct": 0.0,
        "files": {},
    }


# ─────────────────────────────────────────────────────────────
# Verilator coverage parser  (RTL: line + toggle)
# ─────────────────────────────────────────────────────────────

def parse_verilator_coverage(dat_file: str) -> dict:
    """
    Parse verilator coverage.dat and return RTL coverage metrics.
    Verilator .dat format:
      C '<count>' '<filename>' '<lineno>' '<column>' '<hier>' '<comment>'
    Toggle lines have comment starting with "toggle".

    Returns:
      {
        "line_hit": int, "line_total": int, "line_pct": float,
        "toggle_hit": int, "toggle_total": int, "toggle_pct": float,
      }
    """
    if not os.path.exists(dat_file):
        return _empty_rtl_coverage()

    line_hit = line_total = 0
    toggle_hit = toggle_total = 0

    with open(dat_file) as f:
        for raw in f:
            raw = raw.strip()
            if not raw.startswith("C "):
                continue
            # Parse: C '<count>' '<file>' '<line>' '<col>' '<hier>' '<comment>'
            parts = re.findall(r"'([^']*)'", raw)
            if len(parts) < 6:
                continue
            count   = int(parts[0]) if parts[0].isdigit() else 0
            comment = parts[5] if len(parts) > 5 else ""

            if "toggle" in comment.lower():
                toggle_total += 1
                if count > 0:
                    toggle_hit += 1
            else:
                line_total += 1
                if count > 0:
                    line_hit += 1

    return {
        "line_hit":     line_hit,
        "line_total":   line_total,
        "line_pct":     _pct(line_hit, line_total),
        "toggle_hit":   toggle_hit,
        "toggle_total": toggle_total,
        "toggle_pct":   _pct(toggle_hit, toggle_total),
    }


def get_uncovered_signals(dat_file: str) -> list:
    """Return list of signal names with zero toggle count — feed back to LLM."""
    if not os.path.exists(dat_file):
        return []
    uncovered = []
    with open(dat_file) as f:
        for raw in f:
            raw = raw.strip()
            if not raw.startswith("C "):
                continue
            parts = re.findall(r"'([^']*)'", raw)
            if len(parts) < 6:
                continue
            count   = int(parts[0]) if parts[0].isdigit() else 0
            hier    = parts[4] if len(parts) > 4 else ""
            comment = parts[5] if len(parts) > 5 else ""
            if "toggle" in comment.lower() and count == 0:
                uncovered.append(f"{hier} ({comment})")
    return uncovered


def _empty_rtl_coverage():
    return {
        "line_hit": 0, "line_total": 0, "line_pct": 0.0,
        "toggle_hit": 0, "toggle_total": 0, "toggle_pct": 0.0,
    }


def _pct(hit: int, total: int) -> float:
    return round(100.0 * hit / total, 2) if total > 0 else 0.0


# ─────────────────────────────────────────────────────────────
# Convenience: save coverage dict to JSON
# ─────────────────────────────────────────────────────────────

def save_coverage_json(data: dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[extract_coverage] Saved: {path}")


def load_coverage_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["lcov", "verilator"], required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    if args.type == "lcov":
        result = parse_lcov(args.file)
        print(f"Line   coverage: {result['line_pct']:6.2f}%  ({result['line_hit']}/{result['line_total']})")
        print(f"Branch coverage: {result['branch_pct']:6.2f}%  ({result['branch_hit']}/{result['branch_total']})")
    else:
        result = parse_verilator_coverage(args.file)
        print(f"RTL Line   coverage: {result['line_pct']:6.2f}%  ({result['line_hit']}/{result['line_total']})")
        print(f"RTL Toggle coverage: {result['toggle_pct']:6.2f}%  ({result['toggle_hit']}/{result['toggle_total']})")

    if args.json_out:
        save_coverage_json(result, args.json_out)


if __name__ == "__main__":
    main()
