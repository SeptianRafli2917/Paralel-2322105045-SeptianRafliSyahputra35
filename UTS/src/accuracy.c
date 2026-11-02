/*
 * accuracy.c - Eksperimen trade-off jumlah thread vs akurasi statistik.
 *
 * Untuk setiap N dan setiap seed (1..RUNS) dua skenario dengan T=8 "thread"
 * disimulasikan secara serial (yang diuji adalah RNG, bukan kecepatan):
 *   good : tiap thread punya stream independen (seed berbeda)   -> N sampel efektif
 *   bad  : semua thread memakai seed SAMA (bug umum)            -> hanya N/T efektif
 * Keluaran CSV: n,mode,seed,pi_est
 */
#include "common.h"

int main(int argc, char **argv)
{
    int runs = argc > 1 ? atoi(argv[1]) : 40;
    const int T = 8;
    const uint64_t Ns[] = { 100000ULL, 1000000ULL, 10000000ULL, 50000000ULL };
    printf("n,mode,seed,pi_est\n");
    for (size_t k = 0; k < sizeof Ns / sizeof *Ns; k++) {
        uint64_t n = Ns[k], per = n / T;
        for (int r = 1; r <= runs; r++) {
            uint64_t good = 0, bad = 0;
            for (int t = 0; t < T; t++) {
                good += mc_count(block_seed((uint64_t)r, (uint64_t)t), per);
                bad  += mc_count((uint64_t)r, per);          /* seed sama */
            }
            printf("%llu,good,%d,%.10f\n", (unsigned long long)n, r, 4.0 * good / (per * T));
            printf("%llu,bad,%d,%.10f\n",  (unsigned long long)n, r, 4.0 * bad  / (per * T));
        }
    }
    return 0;
}
