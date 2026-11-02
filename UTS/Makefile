# Makefile - Monte Carlo pi: serial vs Pthreads vs OpenMP
CC      ?= gcc
CFLAGS  := -O2 -Wall -Wextra -std=gnu11
LDLIBS  := -lm
BIN     := bin

all: $(BIN)/mc_serial $(BIN)/mc_pthreads $(BIN)/mc_pthreads_fs $(BIN)/mc_omp $(BIN)/accuracy

$(BIN):
	mkdir -p $(BIN)

$(BIN)/mc_serial: src/mc_serial.c src/common.h src/rng.h | $(BIN)
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)

$(BIN)/mc_pthreads: src/mc_pthreads.c src/common.h src/rng.h | $(BIN)
	$(CC) $(CFLAGS) -pthread $< -o $@ $(LDLIBS)

# varian dengan false sharing sengaja (eksperimen anomali)
$(BIN)/mc_pthreads_fs: src/mc_pthreads.c src/common.h src/rng.h | $(BIN)
	$(CC) $(CFLAGS) -DFALSE_SHARING -pthread $< -o $@ $(LDLIBS)

$(BIN)/mc_omp: src/mc_omp.c src/common.h src/rng.h | $(BIN)
	$(CC) $(CFLAGS) -fopenmp $< -o $@ $(LDLIBS)

$(BIN)/accuracy: src/accuracy.c src/common.h src/rng.h | $(BIN)
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)

test: all
	bash scripts/test.sh

bench: all
	bash scripts/bench.sh

report:
	python3 scripts/make_report.py --nim "$(NIM)" --nama "$(NAMA)"

loc:
	@wc -l src/*.c src/*.h

clean:
	rm -rf $(BIN)

.PHONY: all test bench report loc clean
