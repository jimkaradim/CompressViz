#!/usr/bin/env python3
"""
crossvalidate.py — Διασταύρωση Python και JavaScript υλοποιήσεων

ΓΙΑΤΙ ΕΙΝΑΙ ΑΠΑΡΑΙΤΗΤΟ
----------------------
Η εργασία παραδίδει δύο ανεξάρτητες υλοποιήσεις των ίδιων αλγορίθμων:
μία σε Python (για τα πειράματα) και μία σε JavaScript (για το εργαλείο
οπτικοποίησης). Χωρίς έλεγχο, δεν υπάρχει καμία εγγύηση ότι συμφωνούν —
και τότε τα νούμερα του εργαλείου και τα νούμερα των πειραμάτων μπορεί
να λένε διαφορετικά πράγματα για τον ίδιο αλγόριθμο.

Ο έλεγχος είναι αυστηρός: συγκρίνεται το SHA-256 των συμπιεσμένων bytes,
όχι απλώς το μέγεθος. Δύο υλοποιήσεις μπορεί να δίνουν ίδιο μήκος με
διαφορετικό περιεχόμενο (π.χ. διαφορετική σειρά ισοβαθμιών στο δέντρο
Huffman), και αυτό θα σήμαινε ότι η μία δεν αποκωδικοποιεί την άλλη.

Χρήση
-----
    python3 crossvalidate.py            # γράφει vectors.json
    node js/scripts/crossvalidate.mjs   # συγκρίνει
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from compressviz import adaptive, arithmetic, huffman, lz77, lzw, rle

OUT = Path("vectors.json")


def build_vectors() -> list[dict]:
    rng = random.Random(20260813)
    alphabet = "abcdefghijklmnopqrstuvwxyz   0123456789.,\n"

    cases: list[tuple[str, bytes]] = [
        ("empty", b""),
        ("single", b"a"),
        ("run32", b"a" * 32),
        ("alternating", b"ab" * 500),
        ("periodic3", b"abcabcabcabcabcabc"),
        ("digits_rle_trap", b"aa3bb"),
        ("digits_rle_trap2", b"2a3bb"),
        ("all_bytes", bytes(range(256))),
        ("all_bytes_x4", bytes(range(256)) * 4),
        ("two_blocks", b"\x00" * 300 + b"\xff" * 300),
        ("pangram", b"The quick brown fox jumps over the lazy dog. " * 20),
        ("kwkwk", b"TOBEORNOTTOBEORTOBEORNOT"),
    ]

    for i in range(6):
        n = rng.randint(1, 900)
        cases.append((f"random_bin_{i}",
                      bytes(rng.randrange(256) for _ in range(n))))

    for i in range(6):
        n = rng.randint(1, 1200)
        text = "".join(rng.choice(alphabet) for _ in range(n))
        cases.append((f"random_text_{i}", text.encode()))

    codecs = [
        ("rle_pairs", rle, {"variant": "pairs"}),
        ("rle_packbits", rle, {"variant": "packbits"}),
        ("huffman", huffman, {}),
        ("lz77", lz77, {"window_size": 4096, "lookahead_size": 18,
                        "mode": "lz77"}),
        ("lzss", lz77, {"window_size": 4096, "lookahead_size": 18,
                        "mode": "lzss"}),
        ("lzw12", lzw, {"max_bits": 12}),
        ("arithmetic", arithmetic, {}),
        ("adaptive", adaptive, {}),
    ]

    vectors = []
    for name, data in cases:
        entry = {
            "name": name,
            "input_hex": data.hex(),
            "input_sha256": hashlib.sha256(data).hexdigest(),
            "expected": {},
        }
        for codec_id, module, params in codecs:
            blob = module.compress(data, **params)
            assert module.decompress(blob) == data, \
                f"Round-trip απέτυχε: {codec_id} / {name}"
            entry["expected"][codec_id] = {
                "sha256": hashlib.sha256(blob).hexdigest(),
                "length": len(blob),
            }
        vectors.append(entry)
    return vectors


def main() -> None:
    vectors = build_vectors()
    OUT.write_text(json.dumps({"vectors": vectors}, indent=1),
                   encoding="utf-8")
    n_checks = len(vectors) * len(vectors[0]["expected"])
    print(f"  Γράφτηκαν {len(vectors)} διανύσματα × "
          f"{len(vectors[0]['expected'])} codecs = {n_checks} έλεγχοι")
    print(f"  Αρχείο: {OUT}")
    print("  Τώρα τρέξε: node js/scripts/crossvalidate.mjs")


if __name__ == "__main__":
    main()
