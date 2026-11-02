/*
 * mc_omp.c - Versi OpenMP (pendekatan compiler directive).
 *
 *  - parallel for : membagi iterasi blok ke thread.
 *  - schedule(static,1) : blok b -> thread (b mod T), pembagian yang sama
 *                         persis dengan versi Pthreads (perbandingan adil).
 *  - reduction(+:hits)  : tiap thread punya salinan private `hits`;
 *                         runtime menjumlahkannya di akhir -> TIDAK ADA
 *                         race condition dan TIDAK ADA false sharing.
 *  - Scope: hits = reduction(private+combine); b = private (loop var);
 *           n, seed = shared read-only (default shared).
 *  - RNG: state xoshiro lokal di dalam mc_count() => private per iterasi.
 *  - Tanpa -fopenmp pragma diabaikan -> program tetap valid sebagai serial.
 */
#ifdef _OPENMP
#include <omp.h>
#endif
#include "common.h"

int main(int argc, char **argv)
{
    config_t cfg = parse_args(argc, argv);
#ifdef _OPENMP
    omp_set_num_threads(cfg.threads);
#endif
    const uint64_t n = cfg.n, seed = cfg.seed;
    uint64_t hits = 0;

    double t0 = now_sec();
    #pragma omp parallel for schedule(static, 1) reduction(+ : hits)
    for (int64_t b = 0; b < (int64_t)NBLOCKS; b++)
        hits += mc_block((uint64_t)b, n, seed);
    double t1 = now_sec();

    print_result("openmp", &cfg, hits, t1 - t0);
    return 0;
}
