#!/usr/bin/env python3
"""
run_tests.py — Εκτέλεση ελέγχων χωρίς εξωτερικές εξαρτήσεις.

Ισοδύναμο του `pytest -q` για περιβάλλοντα όπου το pytest δεν είναι
εγκατεστημένο. Χρησιμοποιεί μόνο την τυπική βιβλιοθήκη.

    python3 run_tests.py
"""

from __future__ import annotations

import random
import string
import sys
import traceback
from collections import Counter

from compressviz import CODECS, arithmetic, huffman, lz77, lzw
from compressviz.baselines import BASELINES

PASSED = 0
FAILED: list[str] = []


def check(name: str, condition: bool) -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(name)
        print(f"  ✗ {name}")


EDGE_CASES = [
    b"",
    b"a",
    b"a" * 32,
    b"ab" * 500,
    b"abcabcabcabcabcabc",
    b"aa3bb",
    b"2a3bb",
    bytes(range(256)),
    bytes(range(256)) * 4,
    b"\x00" * 300 + b"\xff" * 300,
    b"The quick brown fox jumps over the lazy dog. " * 20,
]


def test_roundtrips() -> None:
    print("\n[1] Round-trip: decompress(compress(x)) == x")
    for label, module, params in CODECS:
        ok = True
        for data in EDGE_CASES:
            try:
                if module.decompress(module.compress(data, **params)) != data:
                    ok = False
                    print(f"      διαφορά σε {data[:16]!r}")
            except Exception:
                ok = False
                traceback.print_exc()

        rng = random.Random(20260813)
        for _ in range(40):
            data = bytes(rng.randrange(256) for _ in range(rng.randint(0, 400)))
            try:
                if module.decompress(module.compress(data, **params)) != data:
                    ok = False
            except Exception:
                ok = False
                traceback.print_exc()

        alphabet = string.ascii_lowercase + "   " + string.digits + ".,\n"
        for _ in range(40):
            n = rng.randint(1, 800)
            data = "".join(rng.choice(alphabet) for _ in range(n)).encode()
            try:
                if module.decompress(module.compress(data, **params)) != data:
                    ok = False
            except Exception:
                ok = False
                traceback.print_exc()

        chunks = [bytes([rng.randrange(256)]) * rng.randint(1, 200)
                  for _ in range(60)]
        data = b"".join(chunks)
        try:
            if module.decompress(module.compress(data, **params)) != data:
                ok = False
        except Exception:
            ok = False
            traceback.print_exc()

        print(f"  {'✓' if ok else '✗'} {label}")
        check(f"roundtrip {label}", ok)


def test_naive_rle_ambiguous() -> None:
    print("\n[2] Τεκμηρίωση σφάλματος αρχικού RLE")

    def naive(text: str) -> str:
        out, i = [], 0
        while i < len(text):
            c, run = text[i], 1
            while i + run < len(text) and text[i + run] == c:
                run += 1
            out.append(f"{run}{c}" if run > 1 else c)
            i += run
        return "".join(out)

    same = naive("aa3bb") == naive("2a3bb")
    print(f"  {'✓' if same else '✗'} 'aa3bb' και '2a3bb' -> {naive('aa3bb')!r} "
          f"(μη αντιστρέψιμο, όπως αναμένεται)")
    check("naive RLE ambiguity documented", same)


def test_huffman_properties() -> None:
    print("\n[3] Θεωρητικές ιδιότητες Huffman")
    data = b"abracadabra" * 30 + bytes(range(64))
    lengths = huffman.code_lengths(data)
    kraft = sum(2.0 ** -ln for ln in lengths.values())
    print(f"  {'✓' if kraft <= 1 + 1e-9 else '✗'} Ανισότητα Kraft: "
          f"Σ2^-l = {kraft:.6f} ≤ 1")
    check("kraft", kraft <= 1 + 1e-9)

    data = b"the rain in spain falls mainly on the plain. " * 200
    lengths = huffman.code_lengths(data)
    freq = Counter(data)
    avg = sum(freq[s] * lengths[s] for s in freq) / len(data)
    h = arithmetic.entropy(data)
    ok = h <= avg < h + 1.0
    print(f"  {'✓' if ok else '✗'} H = {h:.4f} ≤ L = {avg:.4f} < H+1")
    check("huffman within 1 bit", ok)


def test_arithmetic_properties() -> None:
    print("\n[4] Ιδιότητες Arithmetic Coding")
    data = b"aaaaaaaaaabbbbbccccdde" * 400
    ar = len(arithmetic.compress(data)) * 8 - arithmetic.header_bits(data)
    hu = len(huffman.compress(data)) * 8 - huffman.header_bits(data)
    print(f"  {'✓' if ar <= hu else '✗'} payload: arithmetic {ar} bits "
          f"≤ huffman {hu} bits")
    check("arith <= huffman payload", ar <= hu)

    data = b"the quick brown fox " * 500
    payload = len(arithmetic.compress(data)) * 8 - arithmetic.header_bits(data)
    bound = arithmetic.shannon_bound_bits(data)
    ok = bound - 8 <= payload < bound + 64
    print(f"  {'✓' if ok else '✗'} payload {payload} bits vs φράγμα Shannon "
          f"{bound:.1f} bits (απόκλιση {payload - bound:+.1f})")
    check("arith near shannon bound", ok)


def test_lzss_expansion() -> None:
    print("\n[5] Φραγμένη επέκταση LZSS σε ασυμπίεστα δεδομένα")
    rng = random.Random(7)
    data = bytes(rng.randrange(256) for _ in range(5000))
    lzss = len(lz77.compress(data, 4096, 18, "lzss"))
    classic = len(lz77.compress(data, 4096, 18, "lz77"))
    print(f"  LZSS   : {lzss:>6} bytes ({lzss / len(data) * 100:.1f}%)")
    print(f"  LZ77   : {classic:>6} bytes ({classic / len(data) * 100:.1f}%)")
    ok = lzss < len(data) * 1.15 and lzss < classic
    print(f"  {'✓' if ok else '✗'} LZSS φραγμένο και καλύτερο του LZ77")
    check("lzss bounded expansion", ok)


def test_baselines() -> None:
    print("\n[6] Baselines")
    data = b"baseline sanity check " * 100
    for name, comp, decomp in BASELINES:
        ok = decomp(comp(data)) == data
        print(f"  {'✓' if ok else '✗'} {name}")
        check(f"baseline {name}", ok)


def main() -> int:
    print("=" * 62)
    print("  CompressViz — Έλεγχοι ορθότητας")
    print("=" * 62)

    test_roundtrips()
    test_naive_rle_ambiguous()
    test_huffman_properties()
    test_arithmetic_properties()
    test_lzss_expansion()
    test_baselines()

    print("\n" + "=" * 62)
    if FAILED:
        print(f"  ΑΠΟΤΥΧΙΑ: {len(FAILED)} έλεγχοι απέτυχαν, {PASSED} πέρασαν")
        for f in FAILED:
            print(f"    - {f}")
        return 1
    print(f"  ΟΛΟΙ ΟΙ ΕΛΕΓΧΟΙ ΠΕΡΑΣΑΝ ({PASSED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
