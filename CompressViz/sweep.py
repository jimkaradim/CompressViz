#!/usr/bin/env python3
"""
sweep.py — Μελέτη της επίδρασης των παραμέτρων του LZ77/LZSS

ΓΙΑΤΙ ΥΠΑΡΧΕΙ ΑΥΤΟ ΤΟ ΠΕΙΡΑΜΑ
------------------------------
Στην αρχική εργασία ο LZ77 επέκτεινε τα δεδομένα στο 113% και αυτό
δικαιολογήθηκε ως «επιλογή για λόγους επίδειξης». Μια τέτοια δικαιολογία
δεν στέκει σε πειραματικό κεφάλαιο: το αποτέλεσμα φαίνεται σαν σφάλμα
υλοποίησης αντί για ιδιότητα του αλγορίθμου.

Η συστηματική σάρωση παραμέτρων μετατρέπει την αδυναμία σε εύρημα. Δείχνει
ποσοτικά ότι:

  (α) ο λόγος συμπίεσης βελτιώνεται περίπου γραμμικά ως προς log2(W),
  (β) υπάρχει κρίσιμο μέγεθος παραθύρου κάτω από το οποίο ο κλασικός LZ77
      επεκτείνει τα δεδομένα, και
  (γ) η παραλλαγή LZSS εξαλείφει το φαινόμενο ανεξαρτήτως W, γιατί δεν
      πληρώνει πλήρες token για κάθε literal.

Έξοδος: CSV + Markdown, κατάλληλα για γράφημα ratio ως προς log2(W).

Χρήση
-----
    python3 sweep.py corpus/alice29.txt
    python3 sweep.py corpus/alice29.txt --modes lz77 lzss --outdir results
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from compressviz import lz77

WINDOWS = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192, 16384, 32768]
LOOKAHEADS = [8, 18, 34, 66]


def sweep(data: bytes, modes: list[str], windows: list[int],
          lookaheads: list[int], verify: bool) -> list[dict]:
    rows = []
    total_bits = len(data) * 8

    for mode in modes:
        for w in windows:
            for la in lookaheads:
                blob = lz77.compress(data, window_size=w,
                                     lookahead_size=la, mode=mode)
                ok = True
                if verify:
                    ok = lz77.decompress(blob) == data

                ratio = len(blob) * 8 / total_bits * 100
                rows.append({
                    "mode": mode,
                    "window_size": w,
                    "log2_window": w.bit_length() - 1,
                    "lookahead": la,
                    "offset_bits": max(1, w.bit_length()),
                    "length_bits": max(1, la.bit_length()),
                    "total_bits": len(blob) * 8,
                    "ratio_pct": round(ratio, 2),
                    "expands": ratio > 100,
                    "lossless_verified": ok,
                })
                mark = "✓" if ok else "✗"
                warn = "  <- ΕΠΕΚΤΑΣΗ" if ratio > 100 else ""
                print(f"    {mode:<5} W={w:<6} L={la:<3} "
                      f"ratio={ratio:6.2f}%  {mark}{warn}")
    return rows


def write_outputs(rows: list[dict], outdir: Path, stem: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / f"sweep_{stem}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Πίνακας ratio ανά (mode, W) για το προτεινόμενο lookahead
    md = ["# Σάρωση παραμέτρων LZ77 / LZSS", ""]
    for mode in sorted({r["mode"] for r in rows}):
        md += [f"## {mode.upper()}", "",
               "| Παράθυρο W | log₂W | offset bits | " +
               " | ".join(f"L={la}" for la in
                          sorted({r['lookahead'] for r in rows})) + " |",
               "|---:|---:|---:|" + "---:|" * len({r["lookahead"]
                                                   for r in rows})]
        for w_size in sorted({r["window_size"] for r in rows}):
            cells = []
            for la in sorted({r["lookahead"] for r in rows}):
                match = [r for r in rows if r["mode"] == mode
                         and r["window_size"] == w_size
                         and r["lookahead"] == la]
                cells.append(f"{match[0]['ratio_pct']:.2f}%" if match else "–")
            ob = max(1, w_size.bit_length())
            md.append(f"| {w_size:,} | {w_size.bit_length() - 1} | {ob} | "
                      + " | ".join(cells) + " |")
        md.append("")

    (outdir / f"sweep_{stem}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n  Γράφτηκαν: {csv_path} και {outdir / f'sweep_{stem}.md'}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Σάρωση παραμέτρων LZ77/LZSS")
    ap.add_argument("input", type=Path)
    ap.add_argument("--modes", nargs="+", default=["lz77", "lzss"],
                    choices=["lz77", "lzss"])
    ap.add_argument("--windows", nargs="+", type=int, default=WINDOWS)
    ap.add_argument("--lookaheads", nargs="+", type=int, default=LOOKAHEADS)
    ap.add_argument("--outdir", type=Path, default=Path("results"))
    ap.add_argument("--no-verify", action="store_true",
                    help="παράλειψη round-trip (ταχύτερο, μη συνιστώμενο)")
    args = ap.parse_args()

    if not args.input.is_file():
        print(f"  Δεν βρέθηκε: {args.input}", file=sys.stderr)
        return 1

    data = args.input.read_bytes()
    print(f"\n  {args.input.name}  ({len(data):,} bytes)\n")

    rows = sweep(data, args.modes, args.windows, args.lookaheads,
                 not args.no_verify)
    write_outputs(rows, args.outdir, args.input.stem)

    if any(not r["lossless_verified"] for r in rows):
        print("  ΠΡΟΣΟΧΗ: κάποιες ρυθμίσεις απέτυχαν στον έλεγχο lossless.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
