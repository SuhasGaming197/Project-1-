"""
pipeline/generate_tb.py
-----------------------
Generates C testbenches using three strategies:
  A) Random   — uniform random inputs
  B) Manual   — corner-case values hand-crafted per benchmark type
  C) LLM      — Claude via OpenRouter API (drop-in for Anthropic)

Usage:
  python pipeline/generate_tb.py --benchmark adpcm --strategy random
  python pipeline/generate_tb.py --benchmark adpcm --strategy llm
"""

import os
import random
import argparse
import yaml
from openai import OpenAI   # OpenRouter is OpenAI-compatible

# ─────────────────────────────────────────────────────────────
# Load config
# ─────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config():
    with open(os.path.join(ROOT, "config.yaml")) as f:
        return yaml.safe_load(f)

def get_openrouter_client(cfg):
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=cfg["openrouter_api_key"],
    )

# ─────────────────────────────────────────────────────────────
# Read benchmark source
# ─────────────────────────────────────────────────────────────
def read_benchmark_source(benchmark: str) -> str:
    path = os.path.join(ROOT, "benchmarks", benchmark, f"{benchmark}.c")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Benchmark source not found: {path}")
    with open(path) as f:
        return f.read()

def read_benchmark_header(benchmark: str) -> str:
    path = os.path.join(ROOT, "benchmarks", benchmark, f"{benchmark}.h")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""

# ─────────────────────────────────────────────────────────────
# Strategy A — Random Testbench
# ─────────────────────────────────────────────────────────────

# Benchmark-specific input spec: (function_name, [(arg_name, c_type, lo, hi), ...])
BENCHMARK_SPECS = {
    "adpcm": {
        "encode_fn": "adpcm_encode",
        "decode_fn": "adpcm_decode",
        "reset_fn":  "adpcm_reset",
        "pcm_range": (-32768, 32767),
        "nibble_range": (0, 15),
    },
    "aes": {
        "fn": "aes256_encrypt_ecb",
    },
    "dfmul": {
        "fn": "dfmul",
    },
    "gsm": {
        "fn": "gsm_encode",
    },
}

ADPCM_RANDOM_TB_TEMPLATE = """\
/*
 * AUTO-GENERATED RANDOM TESTBENCH for ADPCM
 * Strategy: Random — {n_tests} random PCM samples
 * Seed: {seed}
 */
#include <stdio.h>
#include "adpcm.h"

int main(void) {{
    int encoded, decoded;
    int pass = 1;
    adpcm_reset();

{test_vectors}

    printf("Random TB done. Pass=%d\\n", pass);
    return pass ? 0 : 1;
}}
"""

ADPCM_LLM_TB_TEMPLATE_BASE = """\
/*
 * AUTO-GENERATED TESTBENCH for ADPCM
 * Strategy: {strategy}
 */
#include <stdio.h>
#include "adpcm.h"

int main(void) {{
{body}
    return 0;
}}
"""

def generate_random_tb_adpcm(n_tests: int, seed: int) -> str:
    random.seed(seed)
    lines = []
    for i in range(n_tests):
        sample = random.randint(-32768, 32767)
        lines.append(f"    /* test {i+1} */")
        lines.append(f"    adpcm_reset();")
        lines.append(f"    encoded = adpcm_encode({sample});")
        lines.append(f"    decoded = adpcm_decode(encoded);")
        lines.append(f"    printf(\"in=%6d enc=%2d dec=%6d\\n\", {sample}, encoded, decoded);")
        lines.append("")
    test_vectors = "\n".join(lines)
    return ADPCM_RANDOM_TB_TEMPLATE.format(
        n_tests=n_tests, seed=seed, test_vectors=test_vectors
    )

def generate_random_tb(benchmark: str, n_tests: int = 100, seed: int = 42) -> str:
    if benchmark == "adpcm":
        return generate_random_tb_adpcm(n_tests, seed)
    else:
        # Generic random TB stub for other benchmarks
        return f"/* TODO: random TB for {benchmark} */\nint main(void) {{ return 0; }}\n"

# ─────────────────────────────────────────────────────────────
# Strategy B — Manual Corner-Case Testbench
# ─────────────────────────────────────────────────────────────

ADPCM_MANUAL_TB = """\
/*
 * MANUAL CORNER-CASE TESTBENCH for ADPCM
 * Hand-crafted to hit every branch in adpcm_encode / adpcm_decode
 */
#include <stdio.h>
#include "adpcm.h"

static void test_sample(int sample, const char *label) {
    int enc, dec;
    adpcm_reset();
    enc = adpcm_encode(sample);
    dec = adpcm_decode(enc);
    printf("%-20s in=%7d  enc=%2d  dec=%7d\\n", label, sample, enc, dec);
}

int main(void) {
    /* --- Boundary values --- */
    test_sample(0,       "zero");
    test_sample(32767,   "INT16_MAX");
    test_sample(-32768,  "INT16_MIN");
    test_sample(1,       "one");
    test_sample(-1,      "neg_one");

    /* --- Alternating extremes (stress toggle coverage) --- */
    int i;
    adpcm_reset();
    for (i = 0; i < 10; i++) {
        int s = (i % 2 == 0) ? 32767 : -32768;
        int enc = adpcm_encode(s);
        int dec = adpcm_decode(enc);
        printf("alt[%d] in=%7d enc=%2d dec=%7d\\n", i, s, enc, dec);
    }

    /* --- Powers of two --- */
    int pw;
    for (pw = 0; pw < 15; pw++) {
        int v = (1 << pw);
        test_sample(v,  "pow2+");
        test_sample(-v, "pow2-");
    }

    /* --- Step through all nibble values (decoder branch coverage) --- */
    adpcm_reset();
    int nib;
    for (nib = 0; nib < 16; nib++) {
        int dec = adpcm_decode(nib);
        printf("nibble %2d -> dec=%7d\\n", nib, dec);
    }

    /* --- Repeated identical input (state retention test) --- */
    adpcm_reset();
    for (i = 0; i < 20; i++) {
        int enc = adpcm_encode(1000);
        int dec = adpcm_decode(enc);
        printf("repeat[%d] enc=%2d dec=%7d\\n", i, enc, dec);
    }

    /* --- Ramp up / ramp down --- */
    adpcm_reset();
    for (i = -32768; i <= 32767; i += 2048) {
        int enc = adpcm_encode(i);
        int dec = adpcm_decode(enc);
        printf("ramp in=%7d enc=%2d dec=%7d\\n", i, enc, dec);
    }

    printf("\\nManual TB done.\\n");
    return 0;
}
"""

def generate_manual_tb(benchmark: str) -> str:
    if benchmark == "adpcm":
        return ADPCM_MANUAL_TB
    else:
        return f"/* TODO: manual TB for {benchmark} */\nint main(void) {{ return 0; }}\n"

# ─────────────────────────────────────────────────────────────
# Strategy C — LLM Testbench via OpenRouter
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert in High-Level Synthesis (HLS) verification.
You generate C testbenches designed to maximize both software coverage AND
RTL toggle coverage after HLS synthesis. Focus on:
- Boundary values (0, max int, min int, -1)
- Overflow and underflow conditions
- All-zeros and all-ones bit patterns
- Values that force every conditional branch to be taken
- Repeated identical inputs (to test state retention)
- Rapidly alternating min/max values (to stress toggle coverage)
- Sequential ramps (both up and down)

Always output ONLY valid C code that compiles with gcc. Include <stdio.h> and
the benchmark header. The testbench must have a main() function.
"""

def generate_llm_tb(benchmark: str, cfg: dict, coverage_feedback: str = None) -> str:
    """
    Ask the LLM to generate a corner-case testbench for the given benchmark.
    If coverage_feedback is provided, ask the LLM to *refine* the testbench.
    """
    client = get_openrouter_client(cfg)
    source = read_benchmark_source(benchmark)
    header = read_benchmark_header(benchmark)

    if coverage_feedback:
        user_msg = f"""\
The following lines/branches were NOT covered in the last simulation run:

{coverage_feedback}

Here is the current C testbench:

```c
{coverage_feedback}
```

Here is the benchmark source:

```c
{source}
```

Modify the testbench to add new test vectors that will cover the missing lines/branches.
Output ONLY the updated C testbench code (no explanation)."""
    else:
        user_msg = f"""\
Here is a C function intended for HLS synthesis:

```c
{header}

{source}
```

Generate a complete C testbench with at least 60 carefully chosen test vectors specifically designed to:
1. Achieve 100% line and branch coverage in C (gcov)
2. Maximize toggle coverage in the RTL generated by Bambu HLS / Verilator
3. Include corner cases: zero inputs, max values (32767, -32768), alternating patterns, power-of-two values
4. Exercise every conditional branch with both true and false outcomes

Output ONLY the C testbench code. No explanation. The file must compile with:
  gcc -fprofile-arcs -ftest-coverage benchmarks/{benchmark}/{benchmark}.c <this_file> -o sim
"""

    response = client.chat.completions.create(
        model=cfg["openrouter_model"],
        max_tokens=4096,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        extra_headers={
            "HTTP-Referer": "https://github.com/cs5291/project1",
            "X-Title": "CS5291 Project 1 - HLS Testbench Generation",
        },
    )
    return response.choices[0].message.content.strip()

# ─────────────────────────────────────────────────────────────
# Save testbench to disk
# ─────────────────────────────────────────────────────────────

def save_tb(benchmark: str, strategy: str, code: str, iteration: int = None) -> str:
    """Write testbench code to testbenches/<strategy>/<benchmark>_tb.c"""
    out_dir = os.path.join(ROOT, "testbenches", strategy)
    os.makedirs(out_dir, exist_ok=True)
    suffix = f"_iter{iteration}" if iteration is not None else ""
    filename = f"{benchmark}_tb{suffix}.c"
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write(code)
    print(f"[generate_tb] Saved: {path}")
    return path

# ─────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate testbenches for CS5291 Project 1")
    parser.add_argument("--benchmark", required=True, choices=["adpcm", "aes", "dfmul", "gsm"])
    parser.add_argument("--strategy",  required=True, choices=["random", "manual", "llm", "all"])
    parser.add_argument("--n-tests",   type=int, default=100, help="Number of random tests")
    parser.add_argument("--seed",      type=int, default=42)
    args = parser.parse_args()

    cfg = load_config()
    bm  = args.benchmark

    strategies = ["random", "manual", "llm"] if args.strategy == "all" else [args.strategy]

    for strategy in strategies:
        print(f"\n[generate_tb] Generating {strategy} testbench for {bm}...")
        if strategy == "random":
            code = generate_random_tb(bm, n_tests=args.n_tests, seed=args.seed)
        elif strategy == "manual":
            code = generate_manual_tb(bm)
        elif strategy == "llm":
            code = generate_llm_tb(bm, cfg)
        save_tb(bm, strategy, code)

if __name__ == "__main__":
    main()
