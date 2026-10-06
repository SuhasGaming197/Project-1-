/*
 * dfmul.h — Double-precision floating-point multiply
 * Adapted from CHStone HLS benchmark suite
 * Edge cases: overflow, underflow, NaN, denormals
 */
#ifndef DFMUL_H
#define DFMUL_H

typedef unsigned long long uint64_t_bm;

/* Multiply two IEEE-754 doubles represented as raw uint64 bit patterns */
uint64_t_bm dfmul(uint64_t_bm a, uint64_t_bm b);

#endif
