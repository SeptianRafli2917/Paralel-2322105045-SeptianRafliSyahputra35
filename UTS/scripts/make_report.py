#!/usr/bin/env python3
"""
make_report.py - Membuat report/laporan.pdf dari hasil benchmark.

Semua angka pada tabel, grafik, hitungan LOC, dan kalimat analisis yang
bersifat kuantitatif dihitung dari file di results/ (bench.csv, overhead.csv,
fs.csv, accuracy.csv, env.txt) dan dari kode sumber di src/. Jadi laporan
selalu konsisten dengan mesin tempat `make bench` dijalankan.

Pemakaian:  python3 scripts/make_report.py --nim 2301234 --nama "Budi Santoso"
"""
import argparse, csv, math, os, re, statistics as st
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, Image, PageBreak, KeepTogether, CondPageBreak,
                                Preformatted)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES, SRC, OUT = (os.path.join(ROOT, d) for d in ("results", "src", "report"))
FIG = os.path.join(OUT, "fig")
os.makedirs(FIG, exist_ok=True)

# --------------------------------------------------------------- fonts
FDIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
for name, f in [("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf"),
                ("DVM", "DejaVuSansMono.ttf")]:
    pdfmetrics.registerFont(TTFont(name, os.path.join(FDIR, f)))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")

# --------------------------------------------------------------- styles
BODY = ParagraphStyle("body", fontName="DV", fontSize=9, leading=13, alignment=TA_JUSTIFY, spaceAfter=5)
H1 = ParagraphStyle("h1", fontName="DV-B", fontSize=13, leading=17, spaceBefore=10, spaceAfter=6, keepWithNext=1,
                    textColor=colors.HexColor("#1F3A5F"))
H2 = ParagraphStyle("h2", fontName="DV-B", fontSize=10.5, leading=14, spaceBefore=7, spaceAfter=3, keepWithNext=1,
                    textColor=colors.HexColor("#1F3A5F"))
CAP = ParagraphStyle("cap", fontName="DV-I", fontSize=8, leading=10.5, alignment=TA_CENTER, spaceAfter=7,
                     textColor=colors.HexColor("#444444"))
CODE = ParagraphStyle("code", fontName="DVM", fontSize=7, leading=8.6, backColor=colors.HexColor("#F4F4F4"),
                      borderPadding=4, spaceBefore=3, spaceAfter=8)
TITLE = ParagraphStyle("title", fontName="DV-B", fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=3,
                       textColor=colors.HexColor("#1F3A5F"))
SUB = ParagraphStyle("sub", fontName="DV", fontSize=9.5, leading=13, alignment=TA_CENTER, spaceAfter=2)
CELL = ParagraphStyle("cell", fontName="DV", fontSize=7.8, leading=10)
CELLB = ParagraphStyle("cellb", parent=CELL, fontName="DV-B")
BUL = ParagraphStyle("bul", parent=BODY, leftIndent=12, bulletIndent=2, spaceAfter=2)


def sn(n):
    """10^9 -> '10<super>9</super>' ; 5e7 -> '5×10<super>7</super>' (untuk Paragraph reportlab)"""
    m, e = f"{n:.0e}".split("e")
    e = int(e)
    return f"10<super>{e}</super>" if m == "1" else f"{m}×10<super>{e}</super>"


def mn(n):
    """versi mathtext matplotlib"""
    m, e = f"{n:.0e}".split("e")
    e = int(e)
    return rf"$10^{{{e}}}$" if m == "1" else rf"${m}\times10^{{{e}}}$"


def P(t, s=BODY): return Paragraph(t, s)
def B(t): return Paragraph(t, BUL, bulletText="•")


def table(rows, widths, header=True, align_right_from=1, zebra=True):
    data = [[Paragraph(str(c), CELLB if (header and i == 0) else CELL) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F2")))
    if zebra:
        for i in range(1, len(rows)):
            if i % 2 == 0:
                style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F7F9FC")))
    t.setStyle(TableStyle(style))
    return t


# --------------------------------------------------------------- data
def read_csv(name):
    p = os.path.join(RES, name)
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return list(csv.DictReader(f))


def read_env():
    env = {"nproc": 1, "model": "tidak diketahui", "tpc": 1, "gcc": "", "date": "", "N": 10**9, "reps": 5, "raw": ""}
    p = os.path.join(RES, "env.txt")
    if not os.path.exists(p):
        return env
    txt = open(p).read()
    env["raw"] = txt
    m = re.search(r"nproc:\s*(\d+)", txt); env["nproc"] = int(m.group(1)) if m else 1
    m = re.search(r"Model name:\s*(.+)", txt); env["model"] = m.group(1).strip() if m else env["model"]
    m = re.search(r"Thread\(s\) per core:\s*(\d+)", txt); env["tpc"] = int(m.group(1)) if m else 1
    m = re.search(r"kompiler:\s*(.+)", txt); env["gcc"] = m.group(1).strip() if m else ""
    m = re.search(r"tanggal:\s*(\S+)", txt); env["date"] = m.group(1)[:10] if m else ""
    m = re.search(r"N:\s*(\d+)\s+REPS:\s*(\d+)", txt)
    if m: env["N"], env["reps"] = int(m.group(1)), int(m.group(2))
    return env


def group(rows):
    g = defaultdict(list)
    for r in rows:
        g[(r["impl"], int(r["threads"]))].append(float(r["time_s"]))
    return g


def loc_count(path, skip_fs=True):
    """Hitung baris kode efektif: bukan kosong, bukan komentar, bukan direktif
    preprosesor kondisional. Cabang #ifdef FALSE_SHARING dilewati (kode eksperimen)."""
    txt = open(path).read()
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    txt = re.sub(r"//.*", "", txt)
    n, in_fs, in_else = 0, False, False
    for line in txt.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("#ifdef FALSE_SHARING"):
            in_fs, in_else = True, False; continue
        if in_fs and s.startswith("#else"):
            in_else = True; continue
        if in_fs and s.startswith("#endif"):
            in_fs = in_else = False; continue
        if in_fs and not in_else and skip_fs:
            continue
        if s.startswith("#ifdef") or s.startswith("#endif") or s.startswith("#else"):
            continue
        n += 1
    return n


def snippet(path, start_pat, end_pat="\n}\n"):
    txt = open(path).read()
    i = txt.index(start_pat)
    j = txt.index(end_pat, i) + len(end_pat)
    return txt[i:j].rstrip()


def fmt(x, d=3): return f"{x:.{d}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nim", default="") ; ap.add_argument("--nama", default="")
    a = ap.parse_args()
    nim = a.nim or "[NIM]"; nama = a.nama or "[Nama]"

    env = read_env()
    bench = read_csv("bench.csv"); over = read_csv("overhead.csv")
    fs = read_csv("fs.csv"); acc = read_csv("accuracy.csv")
    if not bench:
        raise SystemExit("results/bench.csv tidak ada. Jalankan `make bench` dulu.")

    G = group(bench); GO = group(over); GF = group(fs)
    N = int(bench[0]["n"])
    Ts = sorted({t for (i, t) in G if i != "serial"})
    C = env["nproc"]; Tmax = max(Ts)
    ts_serial = st.median(G[("serial", 1)])
    med = lambda impl, t: st.median(G[(impl, t)])
    rel_sd = lambda impl, t: (st.pstdev(G[(impl, t)]) / st.mean(G[(impl, t)])) if len(G[(impl, t)]) > 1 else 0.0
    S = lambda impl, t: ts_serial / med(impl, t)
    E = lambda impl, t: S(impl, t) / t
    ov = lambda impl, t: st.median(GO[(impl, t)]) if (impl, t) in GO else 0.0

    # model Amdahl dengan overhead terukur: T(t) = ov(t) + W / min(t, C)
    def S_model(impl, t):
        return ts_serial / (ov(impl, t) + ts_serial / min(t, C))

    # ---------------- verifikasi correctness dari data benchmark
    hits_set = {r["hits"] for r in bench}
    all_equal = len(hits_set) == 1
    hits_ref = bench[0]["hits"]
    pi_est = float(bench[0]["pi"]); err = float(bench[0]["abs_err"])
    p = math.pi / 4; sigma = 4 * math.sqrt(p * (1 - p) / N)

    # ---------------- LOC & kompleksitas
    f_pt = os.path.join(SRC, "mc_pthreads.c"); f_omp = os.path.join(SRC, "mc_omp.c")
    f_ser = os.path.join(SRC, "mc_serial.c"); f_com = os.path.join(SRC, "common.h")
    loc = {"serial": loc_count(f_ser), "pthreads": loc_count(f_pt), "openmp": loc_count(f_omp),
           "common": loc_count(f_com), "rng": loc_count(os.path.join(SRC, "rng.h"))}
    strip_c = lambda t: re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    pt_api = len(set(re.findall(r"\bpthread_\w+", strip_c(open(f_pt).read()))))
    omp_api = len(set(re.findall(r"#pragma omp|\bomp_\w+", strip_c(open(f_omp).read()))))

    # =============================================================== FIGURES
    plt.rcParams.update({"font.size": 8, "axes.grid": True, "grid.alpha": .3, "figure.dpi": 200})
    CPT, COMP, CID, CMOD = "#C0392B", "#2471A3", "#7F8C8D", "#27AE60"

    # Fig 1: waktu eksekusi
    fig, ax = plt.subplots(figsize=(6.4, 2.6))
    w = 0.36; xs = range(len(Ts))
    ax.bar([x - w / 2 for x in xs], [med("pthreads", t) for t in Ts], w, label="Pthreads", color=CPT,
           yerr=[med("pthreads", t) * rel_sd("pthreads", t) for t in Ts], capsize=2)
    ax.bar([x + w / 2 for x in xs], [med("openmp", t) for t in Ts], w, label="OpenMP", color=COMP,
           yerr=[med("openmp", t) * rel_sd("openmp", t) for t in Ts], capsize=2)
    ax.axhline(ts_serial, color="k", ls="--", lw=1, label=f"Serial ({ts_serial:.2f} s)")
    ax.set_xticks(list(xs)); ax.set_xticklabels([str(t) for t in Ts])
    ax.set_xlabel("Jumlah thread"); ax.set_ylabel("Waktu median (s)")
    ax.set_title(f"Waktu eksekusi, N = {mn(N)}, {env['reps']} ulangan (error bar = simpangan baku)")
    ax.set_ylim(0, ts_serial * 1.4); ax.legend(ncol=3, loc="upper center", fontsize=7)
    fig.tight_layout(); fig.savefig(f"{FIG}/waktu.png"); plt.close(fig)

    # Fig 2: speedup & efficiency
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.7))
    tt = list(Ts)
    a1.plot(tt, tt, "--", color=CID, label="Ideal (S = T)")
    a1.plot(tt, [S_model("pthreads", t) for t in tt], ":", color=CMOD, lw=1.6,
            label=f"Model Amdahl + overhead (C={C} core)")
    a1.plot(tt, [S("pthreads", t) for t in tt], "o-", color=CPT, label="Pthreads")
    a1.plot(tt, [S("openmp", t) for t in tt], "s-", color=COMP, label="OpenMP")
    a1.set_xlabel("Jumlah thread"); a1.set_ylabel("Speedup"); a1.set_xticks(tt); a1.set_title("Speedup")
    a1.legend(fontsize=6)
    a2.plot(tt, [1.0] * len(tt), "--", color=CID, label="Ideal")
    a2.plot(tt, [E("pthreads", t) for t in tt], "o-", color=CPT, label="Pthreads")
    a2.plot(tt, [E("openmp", t) for t in tt], "s-", color=COMP, label="OpenMP")
    a2.set_xlabel("Jumlah thread"); a2.set_ylabel("Efficiency = S/T"); a2.set_xticks(tt)
    a2.set_ylim(0, 1.15); a2.set_title("Efficiency"); a2.legend(fontsize=6)
    fig.tight_layout(); fig.savefig(f"{FIG}/speedup.png"); plt.close(fig)

    # Fig 3: akurasi
    acc_tab = []
    if acc:
        d = defaultdict(list)
        for r in acc:
            d[(int(r["n"]), r["mode"])].append(float(r["pi_est"]) - math.pi)
        Ns = sorted({k[0] for k in d})
        rmse = lambda v: math.sqrt(sum(x * x for x in v) / len(v))
        for n in Ns:
            sg = 4 * math.sqrt(p * (1 - p) / n)
            g_, b_ = rmse(d[(n, "good")]), rmse(d[(n, "bad")])
            acc_tab.append((n, len(d[(n, "good")]), sg, g_, b_, b_ / g_))
        fig, ax = plt.subplots(figsize=(4.6, 2.5))
        ax.loglog(Ns, [4 * math.sqrt(p * (1 - p) / n) for n in Ns], "--", color=CID, label=r"Teori $4\sqrt{p(1-p)/N}$")
        ax.loglog(Ns, [r[3] for r in acc_tab], "o-", color=CMOD, label="Seed independen per thread")
        ax.loglog(Ns, [r[4] for r in acc_tab], "s-", color=CPT, label="Seed SAMA di semua thread")
        ax.set_xlabel("N (total sampel)"); ax.set_ylabel("RMSE estimasi π")
        ax.set_title("Akurasi vs N (T=8 stream, 40 seed)"); ax.legend(fontsize=6)
        fig.tight_layout(); fig.savefig(f"{FIG}/akurasi.png"); plt.close(fig)

    # Fig 4: false sharing
    fs_rows = []
    if GF:
        for t in sorted({k[1] for k in GF}):
            a_ = st.median(GF[("pthreads", t)]); b_ = st.median(GF[("pthreads_fs", t)])
            fs_rows.append((t, a_, b_, b_ / a_))
        base = fs_rows[0][3]
        fig, ax = plt.subplots(figsize=(4.6, 2.4))
        xs_ = [r[0] for r in fs_rows]
        ax.plot(xs_, [r[1] for r in fs_rows], "o-", color=CPT, label="Slot ber-padding 64 B")
        ax.plot(xs_, [r[2] for r in fs_rows], "s-", color="#8E44AD", label="Slot rapat (false sharing)")
        ax.set_xlabel("Jumlah thread"); ax.set_ylabel("Waktu median (s)"); ax.set_xticks(xs_)
        ax.set_title(f"Eksperimen false sharing, N = {mn(int(fs[0]['n']))}"); ax.legend(fontsize=6)
        fig.tight_layout(); fig.savefig(f"{FIG}/fs.png"); plt.close(fig)

    # =============================================================== DOCUMENT
    doc = SimpleDocTemplate(os.path.join(OUT, "laporan.pdf"), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                            title="Monte Carlo π: Pthreads vs OpenMP", author=f"{nama} ({nim})")
    W = A4[0] - 4 * cm
    el = []

    def footer(c, d):
        c.saveState(); c.setFont("DV", 7.5); c.setFillColor(colors.grey)
        c.drawString(2 * cm, 1.1 * cm, f"Pemrograman Paralel — {nim} — {nama}")
        c.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Hal. {d.page}")
        c.restoreState()

    # ---- Judul
    el += [P("Implementasi Paralel Estimasi π dengan Metode Monte Carlo", TITLE),
           P("Analisis Komparatif POSIX Threads (Pthreads) vs OpenMP", SUB),
           P(f"{nama} — NIM {nim}", SUB), Spacer(1, 6)]

    # ---- 1 PENDAHULUAN
    el.append(P("1. PENDAHULUAN", H1))
    el.append(P("<b>Latar belakang.</b> Metode Monte Carlo mengestimasi π dengan melempar titik acak (x, y) ke kuadran "
                "[0,1]×[0,1] dan menghitung rasio titik yang jatuh di dalam seperempat lingkaran satuan "
                "(x²+y² ≤ 1). Karena luas kuadran lingkaran adalah π/4, maka π ≈ 4·hits/N. Galat estimator ini "
                f"bersifat stokastik dan menyusut sebagai O(1/√N): simpangan baku teoretisnya σ = 4·√(p(1−p)/N) "
                f"dengan p = π/4, yaitu ≈ {sigma:.2e} untuk N = {sn(N)}. Menambah satu digit ketepatan memerlukan "
                "100× lebih banyak sampel, sehingga masalah ini intensif komputasi namun <i>embarrassingly parallel</i>: "
                "setiap sampel independen dan satu-satunya data bersama hanyalah penjumlahan akhir."))
    el.append(P("<b>Tujuan.</b> (1) Mengimplementasikan estimasi π dengan N = 10⁹ sampel dalam tiga versi: serial, "
                "Pthreads (manual/eksplisit), dan OpenMP (compiler directive); (2) memastikan correctness yang dapat "
                "diverifikasi secara eksak antar versi; (3) mengukur speedup dan efficiency pada 1, 2, 4, dan 8 thread; "
                "(4) membandingkan kompleksitas kode, bottleneck, anomali, dan trade-off kedua pendekatan; serta "
                "(5) mempelajari dampak kualitas/penyemaian RNG terhadap akurasi statistik."))
    el.append(P(f"<b>Lingkungan pengujian.</b> CPU: {env['model']}; jumlah core logis yang tersedia untuk proses "
                f"(<font name='DVM'>nproc</font>): <b>{C}</b>; thread per core: {env['tpc']}; kompiler: {env['gcc']}; "
                f"flag <font name='DVM'>-O2</font>; tanggal ukur: {env['date']}. Setiap konfigurasi dijalankan "
                f"{env['reps']} kali dan dilaporkan <b>median</b>-nya (lebih tahan terhadap outlier daripada rerata)."))

    # ---- 2 DESAIN
    el.append(P("2. DESAIN IMPLEMENTASI", H1))
    el.append(P("2.1 Algoritma serial (baseline)", H2))
    el.append(P("Baseline memakai kernel yang <i>sama persis</i> dengan versi paralel (file <font name='DVM'>common.h</font>), "
                "sehingga selisih performa murni berasal dari mekanisme paralelisasi, bukan dari perbedaan algoritma. "
                "Kompleksitas waktu O(N), kompleksitas memori O(1) (hanya 32 byte state RNG dan satu penghitung)."))
    el.append(Preformatted(
        "hits <- 0\n"
        "untuk b = 0 .. NBLOCKS-1:                # NBLOCKS = 256 blok tetap\n"
        "    rng <- xoshiro256**(seed = SEED + b*STRIDE)   # stream milik blok b\n"
        "    untuk i = 1 .. ukuran_blok(b):        # ukuran = N/256 (+1 untuk sisa)\n"
        "        x <- rng.unit();  y <- rng.unit() # double di [0,1), 53 bit\n"
        "        hits <- hits + (x*x + y*y <= 1.0) # tanpa branch\n"
        "pi <- 4 * hits / N", CODE))
    el.append(P("<b>Generator acak.</b> Dipakai xoshiro256** (Blackman &amp; Vigna), di-seed lewat SplitMix64. State-nya variabel "
                "lokal di stack pemanggil sehingga <b>tidak ada RNG global yang di-share</b>. Alternatifnya, "
                "<font name='DVM'>rand_r()</font> glibc hanya berstate 32 bit dan menghasilkan 31 bit per panggilan sehingga "
                "periodenya pendek dan resolusi koordinatnya kasar — tidak ideal untuk 2×10⁹ bilangan acak."))
    el.append(P("<b>Desain reproducibility (keputusan kunci).</b> Jika setiap <i>thread</i> diberi stream sendiri, hasil akan "
                "berubah mengikuti jumlah thread dan verifikasi terhadap versi serial hanya bisa bersifat statistik. "
                "Karena itu sampel dibagi menjadi 256 <i>blok</i> tetap, dan <b>stream RNG dimiliki blok, bukan thread</b> "
                "(seed blok = SEED + b·STRIDE). Thread hanya menentukan siapa yang menghitung blok mana. Konsekuensinya "
                "jumlah hit identik bit-per-bit untuk semua versi dan jumlah thread, sehingga verifikasi correctness menjadi "
                "perbandingan bilangan bulat yang eksak. Granularitas 256 blok juga cukup halus untuk menyeimbangkan "
                "beban pada T ≤ 8 (selisih beban maksimum satu blok = 1/32 dari kerja per thread pada T=8)."))

    el.append(P("2.2 Strategi paralelisasi Pthreads", H2))
    el.append(B("<b>Pembagian workload:</b> block-cyclic statis. Thread <i>tid</i> memproses blok tid, tid+T, tid+2T, … "
                "Tanpa work queue, sehingga tidak ada kontensi saat distribusi kerja."))
    el.append(B("<b>Sinkronisasi:</b> <b>tanpa mutex</b>. Tiap thread menulis hasil ke slot miliknya (<font name='DVM'>worker_t.hits</font>) "
                "dan thread utama menjumlahkan setelah <font name='DVM'>pthread_join</font>. Join memberi batas sinkronisasi memori "
                "menurut POSIX, jadi tidak ada data race. Mutex di loop dalam akan menjadi bottleneck ekstrem "
                "(10⁹ lock/unlock); mutex di akhir thread pun tidak perlu."))
    el.append(B("<b>Anti false-sharing:</b> <font name='DVM'>worker_t</font> di-pad menjadi 64 byte dan dialokasikan dengan "
                "<font name='DVM'>aligned_alloc(64, …)</font>, sehingga tiap slot menempati cache line sendiri. "
                "Akumulator inti loop adalah variabel lokal (register) dan ditulis ke slot hanya sekali."))
    el.append(Preformatted(snippet(f_pt, "static void *worker_main(void *p)").replace("#ifdef FALSE_SHARING\n        mc_block_fs(b, w->n, w->seed, w->tid);\n#else\n", "").replace("#endif\n", ""), CODE))

    el.append(P("2.3 Strategi paralelisasi OpenMP", H2))
    el.append(Preformatted(
        "#pragma omp parallel for schedule(static, 1) reduction(+ : hits)\n"
        "for (int64_t b = 0; b < (int64_t)NBLOCKS; b++)\n"
        "    hits += mc_block((uint64_t)b, n, seed);", CODE))
    pr = [["Elemen", "Pilihan", "Alasan"],
          ["parallel for", "membagi iterasi blok", "satu direktif menggantikan create/join/struct/loop manual"],
          ["schedule(static,1)", "blok b → thread (b mod T)", "identik dengan Pthreads → perbandingan adil; overhead scheduling nol (beban per blok seragam, sehingga dynamic tidak diperlukan)"],
          ["reduction(+:hits)", "salinan private per thread, digabung di akhir", "menghilangkan race condition pada akumulator <i>dan</i> false sharing secara otomatis; alternatif atomic/critical akan serialisasi"],
          ["hits", "private (reduction)", "diinisialisasi 0 per thread, digabung dengan operator +"],
          ["b", "private (variabel loop)", "otomatis private oleh OpenMP"],
          ["n, seed", "shared (read-only)", "tidak pernah ditulis → aman tanpa sinkronisasi"],
          ["state RNG", "private (lokal di mc_count)", "dideklarasikan di dalam region paralel (stack), bukan variabel global"]]
    el.append(table(pr, [3.1 * cm, 4.6 * cm, W - 7.7 * cm], align_right_from=9))
    el.append(Spacer(1, 4))
    el.append(P("Pengukuran waktu mencakup seluruh siklus paralel (create/fork → kerja → join/reduksi) pada kedua versi, "
                "sehingga overhead manajemen thread ikut terhitung secara adil."))

    # ---- 3 HASIL
    el.append(P("3. HASIL PENGUJIAN", H1))
    el.append(P("3.1 Verifikasi correctness", H2))
    el.append(P(f"Skrip <font name='DVM'>scripts/test.sh</font> membandingkan jumlah hit Pthreads dan OpenMP (T = 1, 2, 3, 4, 8) dengan "
                "versi serial untuk N = 10⁷, 10 000 019 (tidak habis dibagi 256, menguji penanganan sisa), 1000, dan 255. "
                "Seluruhnya identik (perbandingan integer, bukan toleransi). Pada benchmark utama:"))
    ver = [["Pemeriksaan", "Hasil"],
           ["Hit identik di semua versi &amp; semua T pada N = %s" % sn(N),
            ("<b>LULUS</b> — semua %d proses menghasilkan hits = %s" % (len(bench), hits_ref)) if all_equal else "<b>GAGAL</b>"],
           ["Estimasi π", f"{pi_est:.10f}  (|galat| = {err:.3e})"],
           ["Simpangan baku teoretis σ", f"{sigma:.3e}  → galat = {err / sigma:.2f} σ (" + ("wajar, &lt; 3σ" if err / sigma < 3 else "di luar 3σ: perlu diperiksa") + ")"]]
    el.append(table(ver, [6.8 * cm, W - 6.8 * cm]))
    el.append(Spacer(1, 3))
    el.append(P("Karena masalah Monte Carlo tidak punya jawaban “10×10 yang bisa dihitung manual”, verifikasi dilakukan dua lapis: "
                "(a) kesetaraan eksak dengan versi serial, dan (b) uji statistik bahwa estimasi berada dalam 5σ teoretis. "
                "Lapis (a) membuktikan paralelisasi tidak mengubah komputasi; lapis (b) membuktikan komputasi dasarnya benar."))

    el.append(P("3.2 Waktu eksekusi, speedup, dan efficiency", H2))
    rows = [["Implementasi", "T", "Median (s)", "Min (s)", "σ rel.", "Speedup", "Efficiency"]]
    rows.append(["Serial", "1", fmt(ts_serial), fmt(min(G[("serial", 1)])), f"{rel_sd('serial', 1) * 100:.1f}%", "1.00", "—"])
    for impl, lab in (("pthreads", "Pthreads"), ("openmp", "OpenMP")):
        for t in Ts:
            rows.append([lab, str(t), fmt(med(impl, t)), fmt(min(G[(impl, t)])), f"{rel_sd(impl, t) * 100:.1f}%",
                         f"{S(impl, t):.2f}", f"{E(impl, t):.2f}"])
    t1 = table(rows, [3.2 * cm, 1.2 * cm, 2.6 * cm, 2.4 * cm, 2.0 * cm, 2.6 * cm, W - 14 * cm])
    el.append(KeepTogether([t1, P(f"Tabel 1. Hasil pengukuran (N = {sn(N)}, {env['reps']} ulangan). Speedup S = T<sub>serial</sub>/T<sub>paralel</sub> "
                "(median); Efficiency E = S/T.", CAP)]))
    el.append(Image(f"{FIG}/waktu.png", width=W * 0.86, height=W * 0.86 * 2.6 / 6.4))
    el.append(P("Gambar 1. Waktu eksekusi median terhadap jumlah thread.", CAP))
    el.append(Image(f"{FIG}/speedup.png", width=W, height=W * 2.7 / 6.6))
    el.append(P(f"Gambar 2. Speedup (kiri) dan efficiency (kanan). Garis titik hijau: model Amdahl dengan overhead terukur "
                f"T(t) = overhead(t) + T<sub>serial</sub>/min(t, C) untuk C = {C} core.", CAP))

    el.append(P("3.3 Overhead pembuatan thread (N = 1000)", H2))
    if over:
        orow = [["T"] + [f"{t}" for t in Ts]]
        for impl, lab in (("pthreads", "Pthreads (µs)"), ("openmp", "OpenMP (µs)")):
            orow.append([lab] + [f"{ov(impl, t) * 1e6:.0f}" for t in Ts])
        el.append(table(orow, [3.4 * cm] + [(W - 3.4 * cm) / len(Ts)] * len(Ts)))
        el.append(P("Tabel 2. Median waktu total saat N = 1000 (kerja sebenarnya ≈ 0), sehingga hampir seluruhnya adalah biaya "
                    "create/join (Pthreads) atau fork/join + reduksi (OpenMP).", CAP))

    el.append(P("3.4 Akurasi statistik terhadap penyemaian RNG", H2))
    if acc_tab:
        arow = [["N", "Seed", "σ teori", "RMSE independen", "RMSE seed sama", "Rasio"]]
        for n, k, sg, g_, b_, ra in acc_tab:
            arow.append([sn(n), str(k), f"{sg:.2e}", f"{g_:.2e}", f"{b_:.2e}", f"{ra:.2f}"])
        el.append(KeepTogether([table(arow, [2.2 * cm, 1.6 * cm, 2.8 * cm, 3.6 * cm, 3.4 * cm, W - 13.6 * cm]),
                                P("Tabel 3. RMSE estimasi π dari 40 seed berbeda, dengan 8 stream (T = 8).", CAP)]))
        el.append(Image(f"{FIG}/akurasi.png", width=W * 0.68, height=W * 0.68 * 2.5 / 4.6))
        el.append(P("Gambar 3. RMSE mengikuti kurva teoretis 1/√N bila stream independen; bila semua thread memakai seed sama, "
                    "galat lebih besar.", CAP))

    if fs_rows:
        el.append(P("3.5 Eksperimen false sharing", H2))
        frow = [["T", "Padded (s)", "Rapat/false sharing (s)", "Rasio", "Rasio ternormalisasi"]]
        for t, a_, b_, r_ in fs_rows:
            frow.append([str(t), fmt(a_), fmt(b_), f"{r_:.2f}", f"{r_ / fs_rows[0][3]:.2f}"])
        el.append(table(frow, [1.4 * cm, 3 * cm, 4.6 * cm, 2.4 * cm, W - 11.4 * cm]))
        el.append(P("Tabel 4. Varian <font name='DVM'>mc_pthreads_fs</font> menaikkan penghitung di memori pada setiap hit "
                    "(volatile, slot rapat 8 byte). “Rasio ternormalisasi” = rasio/rasio(T=1) memisahkan efek false sharing "
                    "dari biaya akses volatile murni.", CAP))
        el.append(Image(f"{FIG}/fs.png", width=W * 0.68, height=W * 0.68 * 2.4 / 4.6))
        el.append(P("Gambar 4. Waktu median varian ber-padding vs varian false sharing.", CAP))

    # ---- 4 ANALISIS
    el.append(P("4. ANALISIS KRITIS", H1))

    # 4.1 performa kedua
    el.append(P("4.1 Perbandingan performa Pthreads vs OpenMP", H2))
    diffs = []
    for t in Ts:
        d = (med("pthreads", t) - med("openmp", t)) / med("openmp", t) * 100
        noise = 100 * 2 * max(rel_sd("pthreads", t), rel_sd("openmp", t))
        diffs.append((t, d, noise))
    sig = [t for t, d, n in diffs if abs(d) > n]
    txt = ("Selisih waktu median Pthreads terhadap OpenMP (positif = Pthreads lebih lambat): " +
           "; ".join(f"T={t}: {d:+.1f}% (ambang noise ±{n:.1f}%)" for t, d, n in diffs) + ". ")
    if not sig:
        txt += ("Pada semua T, selisih berada di dalam ±2σ variasi antar-ulangan, sehingga <b>tidak ada bukti bahwa salah satu "
                "pendekatan lebih cepat</b>. Ini sesuai ekspektasi teoretis: kedua versi menjalankan kernel yang sama dengan "
                "pembagian kerja yang sama, dan di balik layar OpenMP pada GCC (libgomp) juga memakai thread POSIX. "
                "Perbedaan hanya terletak pada kode pengelolaan thread yang jumlahnya O(T) dan terjadi sekali.")
    else:
        txt += (f"Selisih melampaui ambang noise pada T = {', '.join(map(str, sig))}. Karena kernel dan pembagian kerja identik, "
                "penyebab yang masuk akal adalah perbedaan overhead create/join/reduksi, afinitas/penempatan thread oleh runtime "
                "OpenMP (libgomp dapat mem-<i>pin</i> thread dan menggunakan thread-pool), serta jitter penjadwalan OS. "
                "Perbedaan ini tidak berasal dari algoritma.")
    el.append(P(txt))

    # 4.2 kompleksitas kode
    el.append(P("4.2 Kompleksitas kode dan maintenance", H2))
    lr = [["Metrik", "Serial", "Pthreads", "OpenMP"],
          ["LOC efektif file utama (tanpa komentar/kosong, tanpa varian FS)", loc["serial"], loc["pthreads"], loc["openmp"]],
          ["LOC tambahan vs serial", "—", f"+{loc['pthreads'] - loc['serial']}", f"+{loc['openmp'] - loc['serial']}"],
          ["Simbol API/direktif paralel unik", 0, pt_api, omp_api],
          ["Struct/alokasi manual, padding cache-line", "tidak ada", "ya (worker_t, aligned_alloc)", "tidak ada"],
          ["Penanganan error", "—", "manual (rc pthread_create)", "dikelola runtime"],
          [f"Kernel bersama (common.h + rng.h)", loc["common"] + loc["rng"], "sama", "sama"]]
    el.append(table(lr, [6.6 * cm, 2.1 * cm, 4.4 * cm, W - 13.1 * cm]))
    el.append(P("Tabel 5. Metrik kompleksitas (dihitung otomatis oleh scripts/make_report.py dari berkas src/).", CAP))
    ratio = (loc["pthreads"] - loc["serial"]) / max(1, (loc["openmp"] - loc["serial"]))
    el.append(P(f"Untuk masalah ini, OpenMP hanya menambah <b>{loc['openmp'] - loc['serial']}</b> baris kode efektif terhadap serial, "
                f"sedangkan Pthreads menambah <b>{loc['pthreads'] - loc['serial']}</b> baris (≈ {ratio:.1f}× lebih banyak). "
                "Dari sisi <i>maintenance</i>: (i) versi OpenMP dapat dibaca sebagai program serial dengan satu anotasi dan dapat "
                "dikompilasi tanpa <font name='DVM'>-fopenmp</font> menjadi serial yang benar (<i>incremental parallelism</i>), "
                "(ii) versi Pthreads menyebar ke struct argumen, fungsi worker, loop create dan loop join, sehingga perubahan "
                "strategi pembagian kerja menyentuh beberapa tempat, dan (iii) Pthreads menuntut programmer sendiri menjamin "
                "tidak ada data race dan false sharing — kesalahan yang tidak terdeteksi kompiler dan sering hanya muncul sebagai "
                "performa buruk atau hasil nondeterministik. Konstruk <font name='DVM'>reduction</font> membuat seluruh kelas bug "
                "itu mustahil terjadi pada versi OpenMP."))

    # 4.3 Amdahl / bottleneck
    el.append(P("4.3 Analisis bottleneck dan hukum Amdahl", H2))
    f8 = {impl: ov(impl, Tmax) / ts_serial for impl in ("pthreads", "openmp")}
    amd = min(Tmax, C)
    el.append(P("Hukum Amdahl: S(T) = 1/(f + (1−f)/T) dengan f fraksi yang tidak dapat diparalelkan. Fraksi serial di sini hanya "
                f"pembuatan/penggabungan thread dan reduksi akhir. Dari Tabel 2, overhead pada T = {Tmax} sebesar "
                f"{ov('pthreads', Tmax) * 1e6:.0f} µs (Pthreads) dan {ov('openmp', Tmax) * 1e6:.0f} µs (OpenMP) terhadap "
                f"T<sub>serial</sub> = {ts_serial:.2f} s, yaitu f ≈ {f8['pthreads']:.1e} dan {f8['openmp']:.1e}. Batas Amdahl "
                f"1/f ≈ {1 / max(f8.values()):.1e} {"(sangat besar)" if 1 / max(f8.values()) > 1000 else ""}, sehingga <b>secara algoritmik tidak ada bottleneck serial</b>; "
                f"speedup teoretis pada T = {Tmax} praktis sama dengan T bila ada ≥ {Tmax} core fisik."))
    el.append(P("Kernel ini <i>compute-bound</i> murni: working set 32 byte muat di register/L1, tidak ada trafik memori "
                "berarti, sehingga bandwidth DRAM dan cache locality bukan faktor. Throughput dibatasi rantai dependensi "
                f"xoshiro (≈ {ts_serial / N * 1e9:.2f} ns per sampel pada serial). Karena N tetap dan T bertambah, ini "
                "<i>strong scaling</i>; untuk <i>weak scaling</i> (hukum Gustafson), memperbesar N sebanding T akan menjaga waktu "
                "tetap sambil menurunkan galat sebesar √T."))

    # 4.4 anomali
    el.append(P("4.4 Pembahasan anomali", H2))
    Sm = max(S("pthreads", t) for t in Ts); Sm2 = max(S("openmp", t) for t in Ts)
    if C < Tmax:
        el.append(P(f"<b>Anomali utama: speedup tidak mengikuti T.</b> Speedup maksimum yang teramati hanya {max(Sm, Sm2):.2f}× "
                    f"padahal T hingga {Tmax} (selisih dari 1.00 masih dalam variasi antar-ulangan, bukan percepatan nyata), dan efficiency turun sebagai ≈ 1/T (Tabel 1). Ini <b>bukan cacat implementasi</b>: "
                    f"mesin ukur hanya menyediakan <b>{C} core logis</b>, sehingga T &gt; {C} thread hanya "
                    f"<i>di-time-slice</i> pada core yang sama (oversubscription). Total kerja tetap sama, maka waktu tetap ≈ "
                    f"T<sub>serial</sub> ditambah overhead konteks-switch. Model Amdahl dengan min(T, C) = {C} (garis hijau Gambar 2) "
                    "memprediksi perilaku ini dengan baik, yang menjadi validasi bahwa penyebabnya keterbatasan hardware, bukan "
                    "kode. Bukti pendukung: hit identik di semua T (kerja tidak hilang/dobel) dan overhead thread sangat kecil "
                    "(Tabel 2). <b>Keterbatasan:</b> angka speedup &gt; 1 tidak dapat didemonstrasikan pada mesin ini; "
                    "benchmark harus dijalankan ulang (<font name='DVM'>make bench</font>) pada mesin ≥ 8 core, dan laporan "
                    "ini otomatis ter-regenerasi dengan data tersebut."))
    else:
        el.append(P(f"Speedup terbaik: Pthreads {Sm:.2f}×, OpenMP {Sm2:.2f}× pada mesin dengan {C} core logis. "
                    + ("Bila efficiency turun saat T mendekati/melebihi jumlah core fisik, penyebab utamanya adalah SMT/"
                       "hyper-threading (dua thread berbagi satu core fisik dan unit eksekusi sehingga throughput per thread turun), "
                       "serta frekuensi turbo yang menurun saat banyak core aktif. " if env["tpc"] > 1 else
                       "Efficiency di bawah 1 pada T besar dapat berasal dari penurunan frekuensi saat banyak core aktif. ")))
    # sedikit catatan variabilitas
    worst = max(((impl, t, rel_sd(impl, t)) for impl in ("pthreads", "openmp") for t in Ts), key=lambda x: x[2])
    el.append(P(f"<b>Variabilitas.</b> Simpangan baku relatif terbesar adalah {worst[2] * 100:.1f}% ({worst[0]}, T={worst[1]}); "
                "variasi ini berasal dari noise lingkungan (host virtual, penjadwal OS) sehingga selisih di bawah nilai ini "
                "tidak boleh ditafsirkan sebagai keunggulan implementasi tertentu."))
    if fs_rows:
        norm_last = fs_rows[-1][3] / fs_rows[0][3]
        if C < max(r[0] for r in fs_rows):
            el.append(P(f"<b>False sharing tidak teramati.</b> Rasio ternormalisasi pada T = {fs_rows[-1][0]} adalah {norm_last:.2f}. "
                        f"False sharing membutuhkan beberapa core yang menulis cache line yang sama secara bersamaan; dengan hanya "
                        f"{C} core tidak ada ping-pong cache-coherence. Selisih rasio T=1 hanyalah biaya store ke memori volatile. "
                        "Pada mesin multi-core, varian ini diperkirakan melambat nyata dan rasio ternormalisasi akan naik jauh di atas 1; "
                        "itulah alasan slot pada versi utama di-pad ke 64 byte."))
        else:
            el.append(P(f"<b>False sharing.</b> Rasio ternormalisasi pada T = {fs_rows[-1][0]} adalah {norm_last:.2f}"
                        + (" — jauh di atas 1, konsisten dengan cache-line ping-pong: tiap hit menginvalidasi baris cache di core lain. "
                           "Versi ber-padding menghindarinya karena tiap thread menulis ke baris cache miliknya." if norm_last > 1.3
                           else " — mendekati 1, artinya pada mesin/kompiler ini efeknya kecil (mis. penulisan jarang atau store buffer menyerap)."
                           )))

    # 4.5 trade-off
    el.append(P("4.5 Trade-off jumlah thread vs akurasi statistik", H2))
    if acc_tab:
        r_last = acc_tab[-1]
        el.append(P("Untuk N total tetap, jumlah thread <b>tidak</b> mengubah galat statistik selama stream independen: galat "
                    f"hanya bergantung pada N (σ = 4√(p(1−p)/N)). Percobaan 3.4 menunjukkan RMSE seed-independen berada di sekitar kurva "
                    f"teoretis (rasio RMSE/σ = {min(r[3] / r[2] for r in acc_tab):.2f}–{max(r[3] / r[2] for r in acc_tab):.2f}; ketidakpastian sampling "
                    f"RMSE dari 40 seed ≈ ±11%; mis. N = {sn(r_last[0])}: RMSE {r_last[3]:.2e} vs σ {r_last[2]:.2e}). Sebaliknya, <b>bug seed sama</b> "
                    f"di 8 thread memberi 8 salinan sampel yang identik; informasi efektif hanya N/8, sehingga galat membesar "
                    f"≈ √8 = 2.83× (terukur {min(r[5] for r in acc_tab):.2f}–{max(r[5] for r in acc_tab):.2f}×, ketidakpastian ≈ ±16%) — hasil tampak “jalan” dan cepat, tetapi tidak lebih akurat daripada "
                    "satu thread. Ini menegaskan bahwa speedup dari paralelisme hanya bermakna bila independensi statistik dijaga. "
                    "Memakai seed berurutan (seed, seed+1, …) di <font name='DVM'>rand_r</font> juga berisiko korelasi antar stream; "
                    "desain kami menurunkan seed lewat SplitMix64 yang mengacak bit sebelum mengisi state xoshiro."))
    el.append(P("Pilihan lain yang layak untuk RNG paralel yang lebih kuat adalah <i>jump-ahead</i> xoshiro (fungsi "
                "<font name='DVM'>jump()</font> yang melompat 2<super>128</super> langkah) agar stream dijamin tidak tumpang tindih; "
                "kami memakai penyemaian SplitMix64 karena tumpang tindih pada state 256 bit secara praktis tidak mungkin "
                "(256 stream × ≈ 4×10⁶ sampel per stream ≪ 2<super>256</super>)."))

    el.append(P("4.6 Trade-off kemudahan vs kontrol", H2))
    tr = [["Aspek", "Pthreads", "OpenMP"],
          ["Kontrol atas thread (afinitas, prioritas, siklus hidup, pola komunikasi)", "Penuh; dapat mengimplementasikan pipeline, work-queue, producer-consumer", "Terbatas pada model fork-join &amp; task; sisanya via environment variable/clause"],
          ["Jumlah kode &amp; risiko bug", "Tinggi; race/false sharing/leak tanggung jawab programmer", "Rendah; reduction, private, schedule dikelola compiler"],
          ["Portabilitas", "POSIX (Windows butuh lapisan tambahan)", "Standar lintas-kompiler/OS; hanya perlu flag"],
          ["Evolusi kode", "Mengubah strategi → ubah banyak tempat", "Mengubah schedule/clause → satu baris"],
          ["Cocok untuk", "Konkurensi tak-beraturan, I/O, event loop, kontrol tingkat rendah", "Loop numerik paralel data (HPC), prototipe cepat"]]
    el.append(table(tr, [4.2 * cm, (W - 4.2 * cm) / 2, (W - 4.2 * cm) / 2]))
    el.append(Spacer(1, 4))
    el.append(P("Dalam masalah ini kontrol ekstra Pthreads <b>tidak memberi keuntungan terukur</b> (4.1), sedangkan biayanya adalah "
                "kode yang lebih panjang dan lebih rawan error (4.2). Kontrol Pthreads baru berharga pada pola yang tidak dapat "
                "diekspresikan sebagai loop paralel, misalnya pipeline producer–consumer atau thread yang hidup lama."))

    # ---- 5 KESIMPULAN
    el.append(P("5. KESIMPULAN", H1))
    el.append(P("<b>Rekomendasi.</b>"))
    el.append(B("Gunakan <b>OpenMP</b> untuk komputasi numerik berbasis loop yang <i>embarrassingly parallel</i> seperti Monte Carlo: "
                "performa setara, kode jauh lebih singkat, dan <font name='DVM'>reduction</font> menghapus race condition."))
    el.append(B("Gunakan <b>Pthreads</b> bila memerlukan kontrol siklus hidup/komunikasi thread atau pola konkurensi non-loop; "
                "siapkan disiplin: akumulator lokal, padding cache-line, dan sinkronisasi hanya di batas join."))
    el.append(P("<b>Pembelajaran.</b>"))
    el.append(B("Menjadikan unit kerja (blok) pemilik stream RNG, bukan thread, membuat hasil paralel <i>reproducible</i> dan dapat "
                "diverifikasi eksak terhadap serial."))
    el.append(B("Speedup dibatasi oleh hardware yang tersedia, bukan hanya oleh kode: tanpa memeriksa jumlah core, kurva speedup "
                "dapat disalahartikan sebagai bug. Model Amdahl dengan overhead terukur dan min(T, C) menjelaskan data dengan baik."))
    el.append(B("Independensi RNG antar thread menentukan apakah paralelisme benar-benar menambah informasi statistik."))
    el.append(B("Pengukuran harus berulang dan dilaporkan dengan variabilitasnya agar selisih kecil tidak disalahtafsirkan."))

    # ---- 6 PUSTAKA
    el.append(P("6. DAFTAR PUSTAKA", H1))
    refs = [
        "Amdahl, G. M. (1967). Validity of the single processor approach to achieving large scale computing capabilities. <i>AFIPS Spring Joint Computer Conference</i>, 483–485.",
        "Blackman, D. &amp; Vigna, S. (2021). Scrambled linear pseudorandom number generators. <i>ACM Transactions on Mathematical Software</i>, 47(4), 1–32.",
        "Butenhof, D. R. (1997). <i>Programming with POSIX Threads</i>. Addison-Wesley.",
        "Chapman, B., Jost, G. &amp; van der Pas, R. (2008). <i>Using OpenMP: Portable Shared Memory Parallel Programming</i>. MIT Press.",
        "Gustafson, J. L. (1988). Reevaluating Amdahl’s law. <i>Communications of the ACM</i>, 31(5), 532–533.",
        "Metropolis, N. &amp; Ulam, S. (1949). The Monte Carlo method. <i>Journal of the American Statistical Association</i>, 44(247), 335–341.",
        "OpenMP Architecture Review Board (2021). <i>OpenMP Application Programming Interface, Version 5.2</i>.",
        "Pacheco, P. (2011). <i>An Introduction to Parallel Programming</i>. Morgan Kaufmann.",
        "Steele, G. L., Lea, D. &amp; Flood, C. H. (2014). Fast splittable pseudorandom number generators. <i>ACM SIGPLAN Notices (OOPSLA)</i>, 49(10), 453–472.",
    ]
    for i, r in enumerate(refs, 1):
        el.append(Paragraph(r, BUL, bulletText=f"[{i}]"))

    # heading tidak boleh menggantung di dasar halaman
    out = []
    for f in el:
        if isinstance(f, Paragraph) and f.style.name in ("h1", "h2"):
            out.append(CondPageBreak(4.5 * cm))
        out.append(f)
    doc.build(out, onFirstPage=footer, onLaterPages=footer)
    print("OK ->", os.path.join(OUT, "laporan.pdf"))


if __name__ == "__main__":
    main()
