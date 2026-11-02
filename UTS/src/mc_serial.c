/* mc_serial.c - Baseline serial: satu thread memproses semua blok. */
#include "common.h"

int main(int argc, char **argv)
{
    config_t cfg = parse_args(argc, argv);
    cfg.threads = 1;

    double t0 = now_sec();
    uint64_t hits = 0;
    for (uint64_t b = 0; b < NBLOCKS; b++)
        hits += mc_block(b, cfg.n, cfg.seed);
    double t1 = now_sec();

    print_result("serial", &cfg, hits, t1 - t0);
    return 0;
}
