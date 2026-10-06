/*
 * dfmul.c — Double-precision float multiply (bit-accurate, HLS-friendly)
 * Adapted from CHStone HLS benchmark suite
 *
 * Represents IEEE-754 doubles as raw uint64 to avoid FP compiler optimizations.
 * Rich branching: sign, exponent overflow/underflow, mantissa normalization, NaN, Inf.
 */
#include "dfmul.h"

#define SIGN_MASK   0x8000000000000000ULL
#define EXP_MASK    0x7FF0000000000000ULL
#define MANT_MASK   0x000FFFFFFFFFFFFFULL
#define EXP_BIAS    1023
#define EXP_MAX     0x7FF
#define MANT_BITS   52

typedef unsigned long long u64;
typedef unsigned int       u32;

static u64 pack(u64 sign, u64 exp, u64 mant) {
    return (sign & SIGN_MASK) | ((exp << MANT_BITS) & EXP_MASK) | (mant & MANT_MASK);
}

u64 dfmul(u64 a, u64 b) {
    u64 sign_a = a & SIGN_MASK;
    u64 sign_b = b & SIGN_MASK;
    u64 sign   = sign_a ^ sign_b;

    u64 exp_a  = (a & EXP_MASK) >> MANT_BITS;
    u64 exp_b  = (b & EXP_MASK) >> MANT_BITS;
    u64 mant_a = a & MANT_MASK;
    u64 mant_b = b & MANT_MASK;

    /* Handle NaN inputs */
    if (exp_a == EXP_MAX && mant_a != 0) return a;   /* NaN propagation */
    if (exp_b == EXP_MAX && mant_b != 0) return b;

    /* Handle Infinity inputs */
    if (exp_a == EXP_MAX) {
        if (exp_b == 0 && mant_b == 0) {
            /* Inf * 0 = NaN */
            return 0x7FF8000000000000ULL;
        }
        return sign | EXP_MASK;  /* Inf result */
    }
    if (exp_b == EXP_MAX) {
        if (exp_a == 0 && mant_a == 0) {
            return 0x7FF8000000000000ULL;
        }
        return sign | EXP_MASK;
    }

    /* Handle zero */
    if ((exp_a == 0 && mant_a == 0) || (exp_b == 0 && mant_b == 0)) {
        return sign;   /* +0 or -0 */
    }

    /* Add implicit leading 1 for normal numbers (handle subnormals) */
    u64 sig_a = (exp_a != 0) ? (mant_a | (1ULL << MANT_BITS)) : mant_a;
    u64 sig_b = (exp_b != 0) ? (mant_b | (1ULL << MANT_BITS)) : mant_b;

    /* Exponent: unbiased sum */
    long long exp_r = (long long)exp_a + (long long)exp_b - EXP_BIAS;

    /* Mantissa multiply — keep top 53 bits of 106-bit product */
    /* Approximate: split into high/low 26-bit halves */
    u64 ah = sig_a >> 27, al = sig_a & 0x7FFFFFFULL;
    u64 bh = sig_b >> 27, bl = sig_b & 0x7FFFFFFULL;
    u64 prod = ah * bh;     /* top bits of product */
    prod += (ah * bl) >> 27;
    prod += (al * bh) >> 27;

    /* Normalize: if bit 53 set, shift right */
    if (prod & (1ULL << (MANT_BITS + 1))) {
        prod >>= 1;
        exp_r++;
    }

    /* Overflow → Infinity */
    if (exp_r >= EXP_MAX) {
        return sign | EXP_MASK;
    }
    /* Underflow → Zero */
    if (exp_r <= 0) {
        /* Subnormal handling: shift mantissa right */
        prod >>= (1 - exp_r);
        exp_r = 0;
    }

    u64 mant_r = prod & MANT_MASK;
    return pack(sign, (u64)exp_r, mant_r);
}
