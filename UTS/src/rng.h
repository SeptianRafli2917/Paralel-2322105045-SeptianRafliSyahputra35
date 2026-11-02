/*
 * rng.h - Generator bilangan acak modern, thread-safe karena TANPA state global.
 *
 *  - splitmix64   : dipakai hanya untuk menurunkan (seeding) state awal.
 *  - xoshiro256** : generator utama (periode 2^256-1, lulus BigCrush;
 *                   Blackman & Vigna, 2018). State 32 byte hidup di stack
 *                   milik worker, jadi tidak ada RNG yang di-share antar thread.
 */
#ifndef RNG_H
#define RNG_H
#include <stdint.h>

typedef struct { uint64_t s[4]; } xoshiro_t;

static inline uint64_t splitmix64(uint64_t *state)
{
    uint64_t z = (*state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

static inline uint64_t rotl64(uint64_t x, int k) { return (x << k) | (x >> (64 - k)); }

static inline void xoshiro_seed(xoshiro_t *r, uint64_t seed)
{
    uint64_t sm = seed;
    for (int i = 0; i < 4; i++) r->s[i] = splitmix64(&sm);
}

static inline uint64_t xoshiro_next(xoshiro_t *r)
{
    uint64_t *s = r->s;
    const uint64_t result = rotl64(s[1] * 5, 7) * 9;
    const uint64_t t = s[1] << 17;
    s[2] ^= s[0]; s[3] ^= s[1]; s[1] ^= s[2]; s[0] ^= s[3];
    s[2] ^= t;
    s[3] = rotl64(s[3], 45);
    return result;
}

/* double seragam di [0,1) dengan 53 bit mantissa penuh */
static inline double xoshiro_unit(xoshiro_t *r)
{
    return (double)(xoshiro_next(r) >> 11) * (1.0 / 9007199254740992.0);
}
#endif
