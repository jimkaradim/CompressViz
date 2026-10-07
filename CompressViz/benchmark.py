#!/usr/bin/env python3
"""
benchmark.py — Πειραματική αξιολόγηση CompressViz

ΤΙ ΑΛΛΑΖΕΙ ΕΝΑΝΤΙ ΤΟΥ ΑΡΧΙΚΟΥ BENCHMARK
----------------------------------------
1. Κάθε μέτρηση επαληθεύεται με round-trip. Αν κάποιος codec δεν
   ανακτήσει ακριβώς την είσοδο, η γραμμή σημειώνεται ως ΑΠΟΤΥΧΙΑ και
   δεν προσμετράται. Δεν αναφέρονται ποτέ αποτελέσματα από κώδικα που
   δεν αποδεδειγμένα αποσυμπιέζει.

2. Μετράται το ΣΥΝΟΛΙΚΟ μέγεθος αρχείου (κεφαλίδα + ωφέλιμο φορτίο),
   και αναφέρονται χωριστά. Η αρχική μέτρηση αγνοούσε την κεφαλίδα του
   Huffman και του Arithmetic, ευνοώντας τους αθέμιτα έναντι του LZW.

3. Ο χρόνος μετριέται με επαναλήψεις και αναφέρεται ως διάμεσος με
   ενδοτεταρτημοριακό εύρος, όχι ως μία μεμονωμένη μέτρηση. Μετρώνται
   χωριστά συμπίεση και αποσυμπίεση.

4. Προστίθενται baselines (gzip, bzip2, xz) που δίνουν το σημείο
   αναφοράς, και η γραμμή «φράγμα Shannon» ως θεωρητικό όριο.

5. Οι πίνακες της εργασίας παράγονται αυτόματα (Markdown + LaTeX) από
   τα ίδια δεδομένα με το CSV, ώστε να μην μπορούν να αποκλίνουν.

Χρήση
-----
    python3 benchmark.py corpus/*.txt
    python3 benchmark.py --repeats 5 --outdir results corpus/
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import statistics
import sys
import time
from pathlib import Path

from compressviz import CODECS, arithmetic
from compressviz.baselines import BASELINES


# ─────────────────────────────────────────────────────────────────────────
# Μέτρηση
# ─────────────────────────────────────────────────────────────────────────

def timed(fn, *args, repeats: int = 5, **kwargs):
    """
    Εκτελεί fn πολλές φορές και επιστρέφει (αποτέλεσμα, διάμεσος_ms, IQR_ms).

    Η πρώτη εκτέλεση αγνοείται ως προθέρμανση (warm-up): οι caches της CPU
    και οι εσωτερικές δομές της Python δεν είναι «ζεστές» στην πρώτη κλήση
    και η μέτρηση θα ήταν συστηματικά υπερεκτιμημένη.
    """
    result = fn(*args, **kwargs)          # δοκιμαστική εκτέλεση πριν από τη μέτρηση
    samples = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    med = statistics.median(samples)
    iqr = (samples[int(len(samples) * 0.75)] - samples[int(len(samples) * 0.25)]
           if len(samples) >= 4 else 0.0)
    return result, med, iqr


def measure_codec(label, module, params, data, repeats):
    """Μετρά έναν codec του CompressViz με πλήρη επαλήθευση."""
    blob, enc_ms, enc_iqr = timed(module.compress, data,
                                  repeats=repeats, **params)
    restored, dec_ms, dec_iqr = timed(module.decompress, blob, repeats=repeats)

    lossless = (restored == data)
    hdr = module.header_bits(data, **params)
    total = len(blob) * 8

    return {
        "algorithm": label,
        "kind": "CompressViz",
        "original_bits": len(data) * 8,
        "header_bits": hdr,
        "payload_bits": total - hdr,
        "total_bits": total,
        "ratio_pct": round(total / (len(data) * 8) * 100, 2) if data else 0.0,
        "bits_per_symbol": round(total / len(data), 4) if data else 0.0,
        "encode_ms": round(enc_ms, 3),
        "encode_iqr_ms": round(enc_iqr, 3),
        "decode_ms": round(dec_ms, 3),
        "decode_iqr_ms": round(dec_iqr, 3),
        "lossless_verified": lossless,
    }


def measure_baseline(name, comp, decomp, data, repeats):
    blob, enc_ms, enc_iqr = timed(comp, data, repeats=repeats)
    restored, dec_ms, dec_iqr = timed(decomp, blob, repeats=repeats)
    total = len(blob) * 8
    return {
        "algorithm": name,
        "kind": "baseline",
        "original_bits": len(data) * 8,
        "header_bits": 0,
        "payload_bits": total,
        "total_bits": total,
        "ratio_pct": round(total / (len(data) * 8) * 100, 2) if data else 0.0,
        "bits_per_symbol": round(total / len(data), 4) if data else 0.0,
        "encode_ms": round(enc_ms, 3),
        "encode_iqr_ms": round(enc_iqr, 3),
        "decode_ms": round(dec_ms, 3),
        "decode_iqr_ms": round(dec_iqr, 3),
        "lossless_verified": restored == data,
    }


def run_file(path: Path, repeats: int) -> tuple[dict, list[dict]]:
    data = path.read_bytes()
    if not data:
        raise ValueError(f"Κενό αρχείο: {path}")

    h = arithmetic.entropy(data)
    info = {
        "file": path.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "unique_symbols": len(set(data)),
        "entropy_bits_per_symbol": round(h, 4),
        "shannon_bound_bits": round(h * len(data), 1),
        "shannon_bound_ratio_pct": round(h / 8 * 100, 2),
    }

    rows = []
    for label, module, params in CODECS:
        row = measure_codec(label, module, params, data, repeats)
        row["file"] = path.name
        row["entropy_bits_per_symbol"] = info["entropy_bits_per_symbol"]
        row["shannon_bound_bits"] = info["shannon_bound_bits"]
        rows.append(row)
        flag = "✓" if row["lossless_verified"] else "✗ ΑΠΟΤΥΧΙΑ"
        print(f"    {label:<18} {row['ratio_pct']:>7.2f}%  "
              f"{row['encode_ms']:>9.2f} ms enc  "
              f"{row['decode_ms']:>9.2f} ms dec  {flag}")

    for name, comp, decomp in BASELINES:
        row = measure_baseline(name, comp, decomp, data, repeats)
        row["file"] = path.name
        row["entropy_bits_per_symbol"] = info["entropy_bits_per_symbol"]
        row["shannon_bound_bits"] = info["shannon_bound_bits"]
        rows.append(row)
        print(f"    {name:<18} {row['ratio_pct']:>7.2f}%  "
              f"{row['encode_ms']:>9.2f} ms enc  "
              f"{row['decode_ms']:>9.2f} ms dec  ✓  [baseline]")

    return info, rows


# ─────────────────────────────────────────────────────────────────────────
# Έξοδος
# ─────────────────────────────────────────────────────────────────────────

CSV_FIELDS = ["file", "algorithm", "kind", "original_bits", "header_bits",
              "payload_bits", "total_bits", "ratio_pct", "bits_per_symbol",
              "encode_ms", "encode_iqr_ms", "decode_ms", "decode_iqr_ms",
              "lossless_verified", "entropy_bits_per_symbol",
              "shannon_bound_bits"]


def write_csv(rows, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def markdown_table(rows, info) -> str:
    """
    Παράγει τον πίνακα αποτελεσμάτων σε Markdown.

    ΑΥΤΗ η συνάρτηση είναι η μοναδική πηγή των πινάκων της εργασίας.
    Η χειροκίνητη αντιγραφή αριθμών στο κείμενο είναι ο λόγος που στην
    αρχική έκδοση καμία τιμή του Πίνακα 5.1 δεν συμφωνούσε με το CSV.
    """
    out = [
        f"### {info['file']}",
        "",
        f"- Μέγεθος: {info['bytes']:,} bytes "
        f"({info['bytes'] * 8:,} bits)",
        f"- SHA-256: `{info['sha256']}`",
        f"- Διακριτά σύμβολα: {info['unique_symbols']}",
        f"- Εντροπία H(X) = {info['entropy_bits_per_symbol']} bits/σύμβολο",
        f"- Φράγμα Shannon: {info['shannon_bound_bits']:,.0f} bits "
        f"({info['shannon_bound_ratio_pct']}% του αρχικού)",
        "",
        "| Αλγόριθμος | Κεφαλίδα (bits) | Φορτίο (bits) | Σύνολο (bits) "
        "| Ratio | bits/σύμβολο | Enc (ms) | Dec (ms) | Lossless |",
        "|---|---:|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        out.append(
            f"| {r['algorithm']} | {r['header_bits']:,} | "
            f"{r['payload_bits']:,} | {r['total_bits']:,} | "
            f"{r['ratio_pct']:.2f}% | {r['bits_per_symbol']:.3f} | "
            f"{r['encode_ms']:.2f} | {r['decode_ms']:.2f} | "
            f"{'✓' if r['lossless_verified'] else '✗'} |"
        )
    out.append(
        f"| *(φράγμα Shannon)* | – | – | "
        f"{info['shannon_bound_bits']:,.0f} | "
        f"{info['shannon_bound_ratio_pct']:.2f}% | "
        f"{info['entropy_bits_per_symbol']:.3f} | – | – | – |"
    )
    out.append("")
    return "\n".join(out)


def latex_table(rows, info) -> str:
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{Αποτελέσματα συμπίεσης για {info['file']} "
        rf"({info['bytes']:,} bytes, $H(X)="
        rf"{info['entropy_bits_per_symbol']}$ bits/σύμβολο).}}",
        r"\begin{tabular}{lrrrrr}",
        r"\hline",
        r"Αλγόριθμος & Κεφαλίδα & Σύνολο (bits) & Ratio & bits/σύμβ. "
        r"& Enc (ms) \\",
        r"\hline",
    ]
    for r in rows:
        lines.append(
            f"{r['algorithm']} & {r['header_bits']:,} & {r['total_bits']:,} & "
            f"{r['ratio_pct']:.2f}\\% & {r['bits_per_symbol']:.3f} & "
            f"{r['encode_ms']:.2f} \\\\"
        )
    lines += [
        r"\hline",
        rf"Φράγμα Shannon & -- & {info['shannon_bound_bits']:,.0f} & "
        rf"{info['shannon_bound_ratio_pct']:.2f}\% & "
        rf"{info['entropy_bits_per_symbol']:.3f} & -- \\",
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
        "",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="CompressViz benchmark")
    ap.add_argument("inputs", nargs="+", type=Path,
                    help="αρχεία ή κατάλογοι προς αξιολόγηση")
    ap.add_argument("--repeats", type=int, default=5,
                    help="επαναλήψεις χρονομέτρησης ανά μέτρηση (default 5)")
    ap.add_argument("--outdir", type=Path, default=Path("results"),
                    help="κατάλογος εξόδου (default: results/)")
    args = ap.parse_args()

    files: list[Path] = []
    for p in args.inputs:
        if p.is_dir():
            files.extend(sorted(q for q in p.iterdir() if q.is_file()))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  Παραλείπεται (δεν βρέθηκε): {p}", file=sys.stderr)

    if not files:
        print("  Δεν δόθηκαν έγκυρα αρχεία εισόδου.", file=sys.stderr)
        return 1

    args.outdir.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    md_parts: list[str] = ["# Αποτελέσματα Benchmark CompressViz", ""]
    tex_parts: list[str] = []
    failures = 0

    for path in files:
        print(f"\n  {path.name}  ({path.stat().st_size:,} bytes)")
        info, rows = run_file(path, args.repeats)
        all_rows.extend(rows)
        md_parts.append(markdown_table(rows, info))
        tex_parts.append(latex_table(rows, info))
        failures += sum(1 for r in rows if not r["lossless_verified"])

    write_csv(all_rows, args.outdir / "benchmark_results.csv")
    (args.outdir / "tables.md").write_text("\n".join(md_parts),
                                           encoding="utf-8")
    (args.outdir / "tables.tex").write_text("\n".join(tex_parts),
                                            encoding="utf-8")

    print(f"\n  Γράφτηκαν: {args.outdir}/benchmark_results.csv, "
          f"tables.md, tables.tex")

    if failures:
        print(f"\n  ΠΡΟΣΟΧΗ: {failures} μετρήσεις απέτυχαν στον έλεγχο "
              f"lossless και δεν πρέπει να αναφερθούν.")
        return 1
    print("  Όλες οι μετρήσεις επαληθεύτηκαν ως lossless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
