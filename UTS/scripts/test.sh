#!/usr/bin/env bash
# test.sh - Verifikasi correctness:
#  (1) jumlah hit Pthreads/OpenMP == serial (perbandingan integer eksak)
#      untuk beberapa N, termasuk N yang TIDAK habis dibagi NBLOCKS=256
#  (2) estimasi pi berada dalam 5 sigma teoretis: 4*sqrt(p(1-p)/N)
set -u
cd "$(dirname "$0")/.."
fail=0
for N in 10000000 10000019 1000 255; do
  ref=$(./bin/mc_serial -n "$N" -c | cut -d, -f4)
  for T in 1 2 3 4 8; do
    for impl in mc_pthreads mc_omp; do
      got=$(./bin/$impl -n "$N" -t "$T" -c | cut -d, -f4)
      if [ "$got" != "$ref" ]; then
        echo "GAGAL  N=$N T=$T $impl: hits=$got (serial=$ref)"; fail=1
      fi
    done
  done
  echo "OK     N=$N  semua versi/thread -> hits=$ref"
done

# Uji statistik pada N besar
N=100000000
line=$(./bin/mc_serial -n $N -c)
python3 - "$line" << 'PY'
import sys, math
f = sys.argv[1].split(',')
n, pi_est = int(f[2]), float(f[4])
p = math.pi/4
sigma = 4*math.sqrt(p*(1-p)/n)
dev = abs(pi_est-math.pi)/sigma
print(f"UJI STATISTIK  N={n}: pi={pi_est:.8f}  sigma_teoretis={sigma:.2e}  deviasi={dev:.2f} sigma")
sys.exit(0 if dev < 5 else 1)
PY
[ $? -ne 0 ] && { echo "GAGAL uji statistik"; fail=1; }

[ $fail -eq 0 ] && echo "== SEMUA TEST LULUS ==" || echo "== ADA TEST GAGAL =="
exit $fail
