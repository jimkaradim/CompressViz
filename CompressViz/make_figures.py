#!/usr/bin/env python3
"""
make_figures.py — Παραγωγή σχημάτων για το Κεφάλαιο 5

Διαβάζει ΜΟΝΟ τα CSV που παρήγαγαν τα benchmark.py και sweep.py. Καμία
τιμή δεν πληκτρολογείται εδώ: αν αλλάξει το πείραμα, αλλάζουν αυτόματα
και τα σχήματα, όπως ακριβώς και οι πίνακες.

Παράγονται πέντε σχήματα σε PNG (300 dpi, για το Word) και PDF
(διανυσματικό, για LaTeX):

    fig1_ratio_by_algorithm   Λόγος συμπίεσης ανά αλγόριθμο και αρχείο
    fig2_lz77_sweep           Λόγος ως προς log2(W), LZ77 έναντι LZSS
    fig3_header_overhead      Κεφαλίδα ως ποσοστό συνόλου, ανά μέγεθος
    fig4_encode_decode_time   Ασυμμετρία συμπίεσης και αποσυμπίεσης
    fig5_vs_shannon           Απόσταση εντροπικών κωδικοποιητών από το όριο

Χρήση
-----
    python3 make_figures.py                          # results/ -> figures/
    python3 make_figures.py --results results --outdir figures
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# ── Στυλ ────────────────────────────────────────────────────────────────
#
# Επιλογές σχεδίασης για έντυπη πτυχιακή: χωρίς σκούρο φόντο, με γκρι
# πλέγμα χαμηλής αντίθεσης, και παλέτα που παραμένει διακριτή σε
# ασπρόμαυρη εκτύπωση (μεταβάλλεται και ο φωτεινότητα, όχι μόνο η απόχρωση).

plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "legend.fontsize": 8,
})

COLORS = {
    "RLE (pairs)": "#8C8C8C",
    "RLE (PackBits)": "#4D4D4D",
    "Huffman": "#1F6FB4",
    "LZ77 (W=4K)": "#E07B39",
    "LZSS (W=4K)": "#B5361B",
    "LZW (12-bit)": "#7B52AB",
    "LZW (16-bit)": "#B08BD4",
    "Arithmetic": "#C9A227",
    "Adaptive AC": "#2E8B57",
    "gzip -9": "#B0B0B0",
    "bzip2 -9": "#909090",
    "xz -9e": "#707070",
}

PCT = FuncFormatter(lambda v, _: f"{v:.0f}%")


def pct_axis(ax, axis: str = "y") -> None:
    """
    Μορφοποίηση άξονα ως ποσοστό, με πλήθος δεκαδικών ανάλογο του εύρους.

    Με σταθερό `.0f`, ένας άξονας που καλύπτει 0–2% εμφανίζει τη σειρά
    ετικετών «2%, 2%, 1%, 0%, 0%», δηλαδή διαφορετικές τιμές με ίδια
    ετικέτα. Οι δεκαδικοί επιλέγονται εδώ από το πραγματικό εύρος.
    """
    target = ax.yaxis if axis == "y" else ax.xaxis
    lo, hi = (ax.get_ylim() if axis == "y" else ax.get_xlim())
    span = abs(hi - lo)
    decimals = 0 if span >= 20 else 1 if span >= 4 else 2
    target.set_major_formatter(
        FuncFormatter(lambda v, _: f"{v:.{decimals}f}%")
    )


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("original_bits", "header_bits", "payload_bits", "total_bits"):
            if k in r:
                r[k] = int(r[k])
        for k in ("ratio_pct", "bits_per_symbol", "encode_ms", "decode_ms",
                  "entropy_bits_per_symbol", "shannon_bound_bits"):
            if k in r:
                r[k] = float(r[k])
        if "lossless_verified" in r:
            r["lossless_verified"] = r["lossless_verified"] in ("True", "true", "1")
    return rows


def save(fig, outdir: Path, name: str) -> None:
    for ext in ("png", "pdf"):
        fig.savefig(outdir / f"{name}.{ext}")
    plt.close(fig)
    print(f"    {name}.png / .pdf")


# ── Σχήμα 1: λόγος συμπίεσης ανά αλγόριθμο και αρχείο ──────────────────

def fig_ratio_by_algorithm(rows: list[dict], outdir: Path) -> None:
    files = sorted({r["file"] for r in rows})
    algos = [a for a in COLORS if any(r["algorithm"] == a for r in rows)]
    own = [a for a in algos if a not in ("gzip -9", "bzip2 -9", "xz -9e")]

    n_files = len(files)
    fig, axes = plt.subplots(
        math.ceil(n_files / 2), 2,
        figsize=(10, 2.5 * math.ceil(n_files / 2)),
        squeeze=False,
    )

    for idx, fname in enumerate(files):
        ax = axes[idx // 2][idx % 2]
        sub = {r["algorithm"]: r for r in rows if r["file"] == fname}
        labels, values, colors = [], [], []
        for a in own:
            if a in sub:
                labels.append(a)
                values.append(sub[a]["ratio_pct"])
                colors.append(COLORS[a])

        bars = ax.bar(range(len(values)), values, color=colors, width=0.68)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=38, ha="right", fontsize=7)
        ax.axhline(100, color="#C0392B", lw=0.9, ls="--", zorder=0)

        if "gzip -9" in sub:
            ax.axhline(sub["gzip -9"]["ratio_pct"], color="#555", lw=0.9,
                       ls=":", zorder=0)
            ax.text(len(values) - 0.4, sub["gzip -9"]["ratio_pct"], " gzip",
                    fontsize=7, va="center", color="#555")

        for b, v in zip(bars, values):
            ax.text(b.get_x() + b.get_width() / 2, v + 2, f"{v:.0f}",
                    ha="center", fontsize=6.5, color="#333")

        ax.set_title(fname, fontsize=9)
        ax.set_ylim(0, max(max(values) * 1.18, 115))
        pct_axis(ax)
        if idx % 2 == 0:
            ax.set_ylabel("λόγος συμπίεσης")

    for idx in range(n_files, len(axes) * 2):
        axes[idx // 2][idx % 2].axis("off")

    fig.suptitle("Λόγος συμπίεσης ανά αλγόριθμο και αρχείο εισόδου\n"
                 "(διακεκομμένη κόκκινη: 100% = καμία συμπίεση· "
                 "στικτή γκρι: gzip -9)", fontsize=10, y=1.0)
    fig.tight_layout()
    save(fig, outdir, "fig1_ratio_by_algorithm")


# ── Σχήμα 2: σάρωση παραμέτρων LZ77 ────────────────────────────────────

def fig_lz77_sweep(rows: list[dict], outdir: Path, stem: str) -> None:
    by_mode = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_mode[r["mode"]][int(r["lookahead"])].append(
            (int(r["window_size"]), float(r["ratio_pct"]))
        )

    fig, ax = plt.subplots(figsize=(7, 4.4))
    styles = {"lz77": ("-", "o", "#B5361B"), "lzss": ("-", "s", "#1F6FB4")}

    for mode, per_la in by_mode.items():
        ls, marker, color = styles.get(mode, ("-", "^", "#555"))
        for i, (la, pts) in enumerate(sorted(per_la.items())):
            pts.sort()
            xs = [math.log2(w) for w, _ in pts]
            ys = [r for _, r in pts]
            ax.plot(xs, ys, ls, marker=marker, color=color,
                    alpha=1.0 - 0.16 * i, ms=4, lw=1.4,
                    label=f"{mode.upper()}, L={la}")

    ax.axhline(100, color="#C0392B", lw=1.0, ls="--")
    ax.text(ax.get_xlim()[1], 100, " επέκταση ↑", fontsize=7.5,
            color="#C0392B", va="bottom", ha="right")

    ax.set_xlabel("log₂(μέγεθος παραθύρου W)")
    ax.set_ylabel("λόγος συμπίεσης")
    pct_axis(ax)
    ax.set_title(f"Επίδραση του παραθύρου αναζήτησης — {stem}\n"
                 "Η μορφή token καθορίζει το σημείο παύσης της επέκτασης",
                 fontsize=10)
    ax.legend(ncol=2, loc="upper right")
    fig.tight_layout()
    save(fig, outdir, "fig2_lz77_sweep")


# ── Σχήμα 3: κόστος κεφαλίδας ──────────────────────────────────────────

def fig_header_overhead(rows: list[dict], outdir: Path) -> None:
    """
    Το επιχείρημα σε ένα σχήμα: το κόστος του μοντέλου είναι καθοριστικό
    στα μικρά αρχεία και αμελητέο στα μεγάλα. Ο LZW και το προσαρμοστικό
    Arithmetic Coding δεν το πληρώνουν καθόλου.
    """
    targets = ["Huffman", "Arithmetic", "Adaptive AC", "LZW (12-bit)"]
    present = [a for a in targets if any(r["algorithm"] == a for r in rows)]

    fig, ax = plt.subplots(figsize=(7, 4.4))
    single_file = len({r["file"] for r in rows}) == 1
    for algo in present:
        pts = [(r["original_bits"] / 8, r["header_bits"] / r["total_bits"] * 100)
               for r in rows if r["algorithm"] == algo and r["total_bits"] > 0]
        pts.sort()
        if not pts:
            continue
        if single_file:
            ax.bar(algo, pts[0][1], color=COLORS.get(algo, "#555"))
        else:
            ax.plot([p[0] for p in pts], [p[1] for p in pts],
                    marker="o", ms=4, lw=1.4, color=COLORS.get(algo, "#555"),
                    label=algo)

    if not single_file:
        ax.set_xscale("log")
        ax.set_xlabel("μέγεθος αρχείου (bytes, λογαριθμική κλίμακα)")
        ax.legend()
    else:
        ax.tick_params(axis="x", rotation=25)
    ax.set_ylabel("κεφαλίδα ως ποσοστό του συνόλου")
    pct_axis(ax)
    ax.set_title("Κόστος κεφαλίδας ως ποσοστό του συμπιεσμένου stream",
                  fontsize=10)
    fig.tight_layout()
    save(fig, outdir, "fig3_header_overhead")


# ── Σχήμα 4: ασυμμετρία χρόνων ─────────────────────────────────────────

def fig_encode_decode_time(rows: list[dict], outdir: Path) -> None:
    own = [r for r in rows if r["kind"] == "CompressViz"]
    by_algo = defaultdict(lambda: [0.0, 0.0, 0])
    for r in own:
        mb = r["original_bits"] / 8 / 1e6
        if mb <= 0:
            continue
        by_algo[r["algorithm"]][0] += r["encode_ms"] / mb
        by_algo[r["algorithm"]][1] += r["decode_ms"] / mb
        by_algo[r["algorithm"]][2] += 1

    algos = [a for a in COLORS if a in by_algo]
    enc = [by_algo[a][0] / by_algo[a][2] for a in algos]
    dec = [by_algo[a][1] / by_algo[a][2] for a in algos]

    x = range(len(algos))
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar([i - 0.2 for i in x], enc, width=0.38, color="#1F6FB4",
           label="συμπίεση")
    ax.bar([i + 0.2 for i in x], dec, width=0.38, color="#E07B39",
           label="αποσυμπίεση")
    ax.set_xticks(list(x))
    ax.set_xticklabels(algos, rotation=38, ha="right", fontsize=7.5)
    ax.set_ylabel("ms ανά MB")
    ax.set_yscale("log")
    ax.set_title("Χρόνος συμπίεσης και αποσυμπίεσης ανά αλγόριθμο",
                 fontsize=10)
    ax.legend()
    fig.tight_layout()
    save(fig, outdir, "fig4_encode_decode_time")


# ── Σχήμα 5: απόσταση από το φράγμα Shannon ────────────────────────────

def fig_vs_shannon(rows: list[dict], outdir: Path) -> None:
    """
    Ο πυρήνας του θεωρητικού επιχειρήματος. Συγκρίνονται ΜΟΝΟ τα ωφέλιμα
    φορτία των εντροπικών κωδικοποιητών: τα σύνολα δεν είναι συγκρίσιμα
    γιατί οι κεφαλίδες τους έχουν διαφορετικό μέγεθος.
    """
    entropy_of = {}
    for r in rows:
        if r.get("entropy_bits_per_symbol"):
            entropy_of[r["file"]] = float(r["entropy_bits_per_symbol"])

    targets = ["Huffman", "Arithmetic", "Adaptive AC"]
    files = sorted(entropy_of)
    fig, ax = plt.subplots(figsize=(8, 4.4))

    width = 0.26
    for i, algo in enumerate(targets):
        xs, ys = [], []
        for j, f in enumerate(files):
            row = next((r for r in rows
                        if r["file"] == f and r["algorithm"] == algo), None)
            if not row:
                continue
            n = row["original_bits"] / 8
            bps = row["payload_bits"] / n if n else 0
            xs.append(j + (i - 1) * width)
            ys.append((bps - entropy_of[f]) / entropy_of[f] * 100
                      if entropy_of[f] else 0)
        ax.bar(xs, ys, width=width, color=COLORS.get(algo, "#555"), label=algo)

    ax.axhline(0, color="#333", lw=0.9)
    ax.set_xticks(range(len(files)))
    ax.set_xticklabels(files, rotation=38, ha="right", fontsize=7.5)
    ax.set_ylabel("υπέρβαση φορτίου έναντι φράγματος Shannon")
    pct_axis(ax)
    ax.set_title("Απόσταση των εντροπικών κωδικοποιητών από το θεωρητικό όριο\n"
                 "Συγκρίνονται ωφέλιμα φορτία, χωρίς τις κεφαλίδες",
                 fontsize=10)
    ax.legend()
    fig.tight_layout()
    save(fig, outdir, "fig5_vs_shannon")


# ── Main ────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Παραγωγή σχημάτων από τα CSV")
    ap.add_argument("--results", type=Path, default=Path("results"))
    ap.add_argument("--outdir", type=Path, default=Path("figures"))
    args = ap.parse_args()

    bench = args.results / "benchmark_results.csv"
    if not bench.is_file():
        print(f"  Δεν βρέθηκε {bench}. Τρέξε πρώτα το benchmark.py.")
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(bench)
    print(f"\n  Φορτώθηκαν {len(rows)} γραμμές από {bench}\n")

    invalid = [r for r in rows if not r.get("lossless_verified", True)]
    if invalid:
        print(f"  ΠΡΟΣΟΧΗ: {len(invalid)} γραμμές απέτυχαν στον έλεγχο lossless "
              f"και δεν πρέπει να σχεδιαστούν.\n")
        rows = [r for r in rows if r.get("lossless_verified", True)]

    fig_ratio_by_algorithm(rows, args.outdir)
    fig_header_overhead(rows, args.outdir)
    fig_encode_decode_time(rows, args.outdir)
    fig_vs_shannon(rows, args.outdir)

    for sweep in sorted(args.results.glob("sweep_*.csv")):
        fig_lz77_sweep(load_rows(sweep), args.outdir,
                       sweep.stem.replace("sweep_", ""))

    print(f"\n  Τα σχήματα γράφτηκαν στο {args.outdir}/")
    print("  PNG για Word (300 dpi), PDF για LaTeX (διανυσματικό).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
