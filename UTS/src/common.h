/*
 * common.h - Kernel Monte Carlo + utilitas yang DIPAKAI BERSAMA oleh
 *            versi serial, Pthreads, dan OpenMP.
 *
 * DESAIN REPRODUCIBILITY
 * ----------------------
 * Total N titik dipecah menjadi NBLOCKS blok tetap (konstanta, tidak
 * bergantung jumlah thread). Blok b memakai stream RNG-nya sendiri,
 * di-seed dari (SEED, b). Thread hanya menentukan SIAPA yang menghitung
 * blok mana. Akibatnya jumlah hit identik bit-per-bit untuk serial,
 * Pthreads, dan OpenMP pada jumlah thread berapa pun -> verifikasi
 * correctness menjadi perbandingan integer yang eksak.
 * RNG tetap per-worker: state-nya variabel lokal di mc_count(), tidak
 * pernah di-share.
 */
#ifndef COMMON_H
#define COMMON_H
#define _GNU_SOURCE
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <unistd.h>
#include "rng.h"

#define NBLOCKS       256ULL
#define DEFAULT_N     1000000000ULL   /* 10^9 titik sesuai spesifikasi */
#define DEFAULT_SEED  42ULL
#define STREAM_STRIDE 0xD1B54A32D192ED03ULL

/* Hitung berapa titik jatuh di dalam lingkaran satuan dari `cnt` sampel
 * memakai stream RNG lokal yang di-seed dengan `stream_seed`. */
static inline uint64_t mc_count(uint64_t stream_seed, uint64_t cnt)
{
    xoshiro_t rng;
    xoshiro_seed(&rng, stream_seed);
    uint64_t hits = 0;
    for (uint64_t i = 0; i < cnt; i++) {
        double x = xoshiro_unit(&rng);
        double y = xoshiro_unit(&rng);
        hits += (x * x + y * y <= 1.0);   /* branchless */
    }
    return hits;
}

static inline uint64_t block_size(uint64_t b, uint64_t n)
{
    return n / NBLOCKS + (b < n % NBLOCKS ? 1 : 0);
}

static inline uint64_t block_seed(uint64_t seed, uint64_t b)
{
    return seed + b * STREAM_STRIDE;
}

/* Satu blok = satu unit kerja yang bisa diberikan ke thread mana pun. */
static inline uint64_t mc_block(uint64_t b, uint64_t n, uint64_t seed)
{
    return mc_count(block_seed(seed, b), block_size(b, n));
}

static inline double now_sec(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

typedef struct { uint64_t n, seed; int threads, csv; } config_t;

/* Opsi: -n N  -t THREADS  -s SEED  -c (keluaran CSV satu baris) */
static inline config_t parse_args(int argc, char **argv)
{
    config_t c = { DEFAULT_N, DEFAULT_SEED, 1, 0 };
    int opt;
    while ((opt = getopt(argc, argv, "n:t:s:c")) != -1) {
        switch (opt) {
        case 'n': c.n = strtoull(optarg, NULL, 10); break;
        case 't': c.threads = atoi(optarg); break;
        case 's': c.seed = strtoull(optarg, NULL, 10); break;
        case 'c': c.csv = 1; break;
        default:
            fprintf(stderr, "Pemakaian: %s [-n N] [-t THREAD] [-s SEED] [-c]\n", argv[0]);
            exit(2);
        }
    }
    if (c.threads < 1) c.threads = 1;
    if (c.n == 0) { fprintf(stderr, "N harus > 0\n"); exit(2); }
    return c;
}

static inline void print_result(const char *impl, const config_t *c,
                                uint64_t hits, double secs)
{
    double pi_est = 4.0 * (double)hits / (double)c->n;
    double err = fabs(pi_est - M_PI);
    if (c->csv)
        printf("%s,%d,%llu,%llu,%.10f,%.3e,%.6f\n", impl, c->threads,
               (unsigned long long)c->n, (unsigned long long)hits,
               pi_est, err, secs);
    else
        printf("[%s] threads=%d N=%llu hits=%llu pi=%.10f |err|=%.3e waktu=%.4f s\n",
               impl, c->threads, (unsigned long long)c->n,
               (unsigned long long)hits, pi_est, err, secs);
}
#endif
