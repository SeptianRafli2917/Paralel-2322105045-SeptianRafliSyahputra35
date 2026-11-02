#!/usr/bin/env bash
# bench.sh - Mengumpulkan data untuk laporan.
#   results/bench.csv     : serial/pthreads/openmp, T=1,2,4,8, REPS ulangan
#   results/overhead.csv  : N=1000 -> hampir seluruhnya biaya create/join/fork
#   results/fs.csv        : pthreads (padded) vs pthreads_fs (false sharing)
#   results/accuracy.csv  : eksperimen RNG / akurasi
#   results/env.txt       : informasi mesin
# Variabel: N (default 1e9), REPS (default 5), STAGES (default "main overhead fs accuracy")
# STAGES berguna bila ingin menjalankan sebagian saja.
set -eu
cd "$(dirname "$0")/.."
N=${N:-1000000000}
REPS=${REPS:-5}
FS_N=${FS_N:-100000000}
THREADS=${THREADS:-"1 2 4 8"}
STAGES=${STAGES:-"main overhead fs accuracy"}
has() { case " $STAGES " in *" $1 "*) return 0;; *) return 1;; esac; }
mkdir -p results

{
  echo "tanggal: $(date -Is)"
  echo "kompiler: $(gcc --version | head -1)"
  echo "nproc: $(nproc)"
  lscpu | grep -E "Model name|^CPU\(s\)|Thread|Core|Socket|L1d|L2|L3" || true
  echo "N: $N  REPS: $REPS"
} > results/env.txt

if has main; then
echo "impl,threads,n,hits,pi,abs_err,time_s,rep" > results/bench.csv
for r in $(seq 1 "$REPS"); do
  echo "== ulangan $r/$REPS"
  echo "$(./bin/mc_serial -n "$N" -c),$r" | tee -a results/bench.csv
  for T in $THREADS; do
    echo "$(./bin/mc_pthreads -n "$N" -t "$T" -c),$r" | tee -a results/bench.csv
    echo "$(./bin/mc_omp      -n "$N" -t "$T" -c),$r" | tee -a results/bench.csv
  done
done
fi

if has overhead; then
echo "== overhead (N=1000)"
echo "impl,threads,n,hits,pi,abs_err,time_s,rep" > results/overhead.csv
for r in $(seq 1 50); do
  for T in $THREADS; do
    echo "$(./bin/mc_pthreads -n 1000 -t "$T" -c),$r" >> results/overhead.csv
    echo "$(./bin/mc_omp      -n 1000 -t "$T" -c),$r" >> results/overhead.csv
  done
done
fi

if has fs; then
echo "== false sharing (N=$FS_N)"
echo "impl,threads,n,hits,pi,abs_err,time_s,rep" > results/fs.csv
for r in $(seq 1 3); do
  for T in $THREADS; do
    echo "$(./bin/mc_pthreads    -n "$FS_N" -t "$T" -c),$r" | tee -a results/fs.csv
    echo "$(./bin/mc_pthreads_fs -n "$FS_N" -t "$T" -c),$r" | tee -a results/fs.csv
  done
done
fi

if has accuracy; then
echo "== akurasi RNG"
./bin/accuracy 40 > results/accuracy.csv
fi
echo "Selesai. Jalankan: make report NIM=... NAMA=..."
