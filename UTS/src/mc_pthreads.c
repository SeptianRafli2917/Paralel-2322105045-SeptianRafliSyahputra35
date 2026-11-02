/*
 * mc_pthreads.c - Versi POSIX Threads (pendekatan eksplisit/manual).
 *
 * Pembagian workload : block-cyclic statis. Thread `tid` mengerjakan blok
 *                      tid, tid+T, tid+2T, ... (sama dengan schedule(static,1)).
 * Sinkronisasi       : TANPA mutex. Tiap thread menulis ke slot hasil miliknya
 *                      sendiri; thread utama menjumlahkan setelah pthread_join
 *                      (join = barrier + memory fence). Tidak ada data race.
 * Anti false-sharing : tiap slot di-pad menjadi 64 byte (1 cache line).
 *
 * Kompilasi dengan -DFALSE_SHARING untuk eksperimen anomali: slot hit dibuat
 * rapat (8 byte) dan di-increment langsung di loop terdalam.
 */
#include <pthread.h>
#include "common.h"

#define CACHE_LINE 64

typedef struct {
    int      tid;
    int      nthreads;
    uint64_t n;
    uint64_t seed;
    uint64_t hits;                       /* hasil thread ini */
    char     pad[CACHE_LINE - 2 * sizeof(int) - 3 * sizeof(uint64_t)];
} worker_t;                              /* sizeof == 64 */

#ifdef FALSE_SHARING
/* Array rapat: 8 slot berbagi satu cache line -> cache-line ping-pong. */
static volatile uint64_t packed_hits[64];

static void mc_block_fs(uint64_t b, uint64_t n, uint64_t seed, int tid)
{
    xoshiro_t rng;
    xoshiro_seed(&rng, block_seed(seed, b));
    uint64_t cnt = block_size(b, n);
    for (uint64_t i = 0; i < cnt; i++) {
        double x = xoshiro_unit(&rng), y = xoshiro_unit(&rng);
        if (x * x + y * y <= 1.0) packed_hits[tid]++;   /* tulis ke memori tiap hit */
    }
}
#endif

static void *worker_main(void *p)
{
    worker_t *w = (worker_t *)p;
    uint64_t local = 0;                  /* akumulator di register/stack */
    for (uint64_t b = (uint64_t)w->tid; b < NBLOCKS; b += (uint64_t)w->nthreads) {
#ifdef FALSE_SHARING
        mc_block_fs(b, w->n, w->seed, w->tid);
#else
        local += mc_block(b, w->n, w->seed);
#endif
    }
    w->hits = local;
    return NULL;
}

int main(int argc, char **argv)
{
    config_t cfg = parse_args(argc, argv);
    const int T = cfg.threads;

    pthread_t *th = malloc((size_t)T * sizeof *th);
    worker_t  *w  = aligned_alloc(CACHE_LINE, (size_t)T * sizeof *w);
    if (!th || !w) { perror("alloc"); return 1; }

    double t0 = now_sec();
    for (int i = 0; i < T; i++) {
        w[i] = (worker_t){ .tid = i, .nthreads = T, .n = cfg.n, .seed = cfg.seed, .hits = 0 };
        int rc = pthread_create(&th[i], NULL, worker_main, &w[i]);
        if (rc) { fprintf(stderr, "pthread_create gagal: %d\n", rc); return 1; }
    }
    uint64_t hits = 0;
    for (int i = 0; i < T; i++) {
        pthread_join(th[i], NULL);
#ifdef FALSE_SHARING
        hits += packed_hits[i];
#else
        hits += w[i].hits;
#endif
    }
    double t1 = now_sec();

    print_result(
#ifdef FALSE_SHARING
        "pthreads_fs",
#else
        "pthreads",
#endif
        &cfg, hits, t1 - t0);
    free(th); free(w);
    return 0;
}
