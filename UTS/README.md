# Estimasi π Monte Carlo — Pthreads vs OpenMP

Tugas Pemrograman Paralel · **Opsi C: Monte Carlo π (N = 10⁹)**
Repositori: `paralel-[NIM]-[Nama]`

Tiga implementasi yang memakai kernel yang sama (`src/common.h`):

| Berkas | Isi |
|---|---|
| `src/mc_serial.c`   | baseline serial |
| `src/mc_pthreads.c` | POSIX Threads (manual; slot hasil ber-padding 64 B, tanpa mutex) |
| `src/mc_omp.c`      | OpenMP (`parallel for` + `reduction`) |
| `src/rng.h`         | xoshiro256** + SplitMix64, tanpa state global |
| `src/accuracy.c`    | eksperimen akurasi: seed independen vs seed sama |
| `scripts/`          | `test.sh`, `bench.sh`, `make_report.py` |
| `results/`          | data mentah benchmark (CSV) + info mesin |
| `report/laporan.pdf`| laporan (dibuat otomatis dari `results/`) |

## Prasyarat
`gcc` (dukungan `-fopenmp`), `make`, `bash`, dan untuk laporan: Python 3 dengan `matplotlib` dan `reportlab`.
Linux/macOS (POSIX). Di Windows gunakan WSL.

## Compile
```bash
make            # build semua ke ./bin
make clean
```

## Menjalankan
```bash
./bin/mc_serial   -n 1000000000
./bin/mc_pthreads -n 1000000000 -t 8
./bin/mc_omp      -n 1000000000 -t 8
```
Opsi: `-n` jumlah sampel (default 10⁹), `-t` jumlah thread, `-s` seed (default 42), `-c` keluaran CSV satu baris.

## Verifikasi correctness
```bash
make test
```
Membandingkan jumlah *hit* Pthreads/OpenMP dengan serial (perbandingan integer eksak) untuk
T = 1,2,3,4,8 dan beberapa N (termasuk N yang tidak habis dibagi 256), lalu uji statistik π dalam 5σ.
Hasil identik pada semua T karena **stream RNG dimiliki blok kerja (256 blok tetap), bukan thread**.

## Benchmark & laporan
```bash
make bench                                  # ± 4–5 menit; hasil di results/*.csv
make report NIM=2301234 NAMA="Budi Santoso" # menulis report/laporan.pdf
```
Opsi benchmark: `N=… REPS=… THREADS="1 2 4 8" STAGES="main overhead fs accuracy" bash scripts/bench.sh`.

> **PENTING:** angka di `results/` yang disertakan diukur pada mesin **1 core**, sehingga speedup ≈ 1.0 (lihat
> bagian 4.4 laporan). Jalankan `make bench && make report …` pada mesin ≥ 8 core untuk memperoleh kurva speedup
> yang sebenarnya. Laporan otomatis menyesuaikan tabel, grafik, dan paragraf analisis kuantitatif dengan data baru.

## Eksperimen false sharing
`make` juga membangun `bin/mc_pthreads_fs` (`-DFALSE_SHARING`), yaitu versi Pthreads yang sengaja memakai slot rapat
8 byte dan menulis ke memori pada setiap hit. Dibandingkan dengan versi ber-padding di `results/fs.csv`.
