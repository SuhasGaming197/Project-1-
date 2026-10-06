/*
 * ADPCM (Adaptive Differential Pulse Code Modulation) encoder/decoder
 * Adapted from CHStone HLS benchmark suite
 * Source: https://github.com/CHSTONE/chstone
 *
 * This benchmark implements ADPCM audio compression.
 * It has rich branching logic (step table lookups, clamping, state updates)
 * making it ideal for coverage experiments.
 */

#include "adpcm.h"
#include <stdio.h>

/* Intel/DVI ADPCM step table */
static const int step_table[89] = {
    7,     8,     9,     10,    11,    12,    13,    14,    16,    17,
    19,    21,    23,    25,    28,    31,    34,    37,    41,    45,
    50,    55,    60,    66,    73,    80,    88,    97,    107,   118,
    130,   143,   157,   173,   190,   209,   230,   253,   279,   307,
    337,   371,   408,   449,   494,   544,   598,   658,   724,   796,
    876,   963,   1060,  1166,  1282,  1411,  1552,  1707,  1878,  2066,
    2272,  2499,  2749,  3024,  3327,  3660,  4026,  4428,  4871,  5358,
    5894,  6484,  7132,  7845,  8630,  9493,  10442, 11487, 12635, 13899,
    15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767
};

/* Intel/DVI ADPCM index table */
static const int index_table[16] = {
    -1, -1, -1, -1, 2, 4, 6, 8,
    -1, -1, -1, -1, 2, 4, 6, 8
};

/* ADPCM state */
static int pred_val = 0;
static int step_idx = 0;

/* Clamp a value to a range */
static int clamp(int val, int lo, int hi) {
    if (val < lo) return lo;
    if (val > hi) return hi;
    return val;
}

/*
 * adpcm_encode: encode a 16-bit PCM sample to a 4-bit ADPCM nibble
 */
int adpcm_encode(int pcm_sample) {
    int step      = step_table[step_idx];
    int diff      = pcm_sample - pred_val;
    int nibble    = 0;

    /* sign bit */
    if (diff < 0) {
        nibble = 8;
        diff   = -diff;
    }

    /* magnitude bits */
    if (diff >= step) {
        nibble |= 4;
        diff   -= step;
    }
    step >>= 1;
    if (diff >= step) {
        nibble |= 2;
        diff   -= step;
    }
    step >>= 1;
    if (diff >= step) {
        nibble |= 1;
    }

    /* update predictor */
    step = step_table[step_idx];
    int delta = step >> 3;
    if (nibble & 4) delta += step;
    if (nibble & 2) delta += (step >> 1);
    if (nibble & 1) delta += (step >> 2);

    if (nibble & 8)
        pred_val -= delta;
    else
        pred_val += delta;

    pred_val = clamp(pred_val, -32768, 32767);

    /* update step index */
    step_idx += index_table[nibble & 0x0f];
    step_idx  = clamp(step_idx, 0, 88);

    return (nibble & 0x0f);
}

/*
 * adpcm_decode: decode a 4-bit ADPCM nibble back to a 16-bit PCM sample
 */
int adpcm_decode(int nibble) {
    nibble &= 0x0f;
    int step  = step_table[step_idx];
    int delta = step >> 3;

    if (nibble & 4) delta += step;
    if (nibble & 2) delta += (step >> 1);
    if (nibble & 1) delta += (step >> 2);

    if (nibble & 8)
        pred_val -= delta;
    else
        pred_val += delta;

    pred_val = clamp(pred_val, -32768, 32767);

    step_idx += index_table[nibble];
    step_idx  = clamp(step_idx, 0, 88);

    return pred_val;
}

/* Reset the codec state (important for testbench isolation) */
void adpcm_reset(void) {
    pred_val = 0;
    step_idx = 0;
}
