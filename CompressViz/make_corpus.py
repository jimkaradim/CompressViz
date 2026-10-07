#!/usr/bin/env python3
"""
make_corpus.py — Δημιουργία συνθετικού corpus για δοκιμή του pipeline

ΠΡΟΣΟΧΗ: τα αρχεία αυτά είναι ΓΙΑ ΕΛΕΓΧΟ ΤΟΥ ΚΩΔΙΚΑ, όχι για τα
πειράματα της εργασίας. Τα πειραματικά αποτελέσματα πρέπει να
προέρχονται από το πρότυπο Canterbury Corpus:

    https://corpus.canterbury.ac.nz/descriptions/

Κατέβασε το `cantrbry.tar.gz`, αποσυμπίεσέ το σε `corpus/` και τρέξε:

    python3 benchmark.py corpus/

Τα 11 αρχεία του Canterbury Corpus καλύπτουν αγγλικό κείμενο
(alice29.txt), Shakespeare (asyoulik.txt), πηγαίο κώδικα C (fields.c),
HTML, τεχνικό εγχειρίδιο, spreadsheet, δυαδικό εκτελέσιμο, εικόνα και
ακολουθία DNA. Αυτή η ποικιλία είναι που κάνει τα συμπεράσματα ανά τύπο
δεδομένων υπερασπίσιμα — ένα μόνο αρχείο δεν αρκεί.

Ονοματολογία εξόδου: κάθε αρχείο έχει διαφορετικό «προφίλ πλεονασμού»,
ώστε να φαίνεται πού υπερέχει κάθε οικογένεια αλγορίθμων.
"""

from __future__ import annotations

import random
from pathlib import Path

OUT = Path("corpus_synthetic")

WORDS = ("the of and to in a is that it was for on are as with his they be "
         "at one have this from or had by hot but some what there we can out "
         "other were all your when up use word how said an each she which do "
         "their time if will way about many then them would write like so "
         "these her long make thing see him two has look more day could go "
         "come did number sound no most people my over know water than call "
         "first who may down side been now find any new work part take get "
         "place made live where after back little only round man year came "
         "show every good me give our under name very through just form much "
         "great think say help low line before turn cause same mean differ").split()


def natural_text(n_words: int, seed: int = 1) -> bytes:
    """Κείμενο με ζιπφιανή κατανομή λέξεων — ευνοεί LZ77/LZW."""
    rng = random.Random(seed)
    weights = [1.0 / (i + 1) for i in range(len(WORDS))]
    out, line = [], []
    for i in range(n_words):
        line.append(rng.choices(WORDS, weights=weights, k=1)[0])
        if len(line) >= rng.randint(8, 14):
            out.append(" ".join(line))
            line = []
        if i % 700 == 699:
            out.append("")
    if line:
        out.append(" ".join(line))
    return ("\n".join(out) + "\n").encode("ascii")


def source_code(n_funcs: int, seed: int = 2) -> bytes:
    """Ψευδο-πηγαίος κώδικας: πολύ δομημένος, μακριά επαναλαμβανόμενα μοτίβα."""
    rng = random.Random(seed)
    parts = ["#include <stdio.h>\n#include <stdlib.h>\n\n"]
    for i in range(n_funcs):
        parts.append(
            f"int process_{i}(int *buffer, size_t length)\n"
            f"{{\n"
            f"    size_t index = 0;\n"
            f"    int accumulator = {rng.randint(0, 99)};\n"
            f"    for (index = 0; index < length; index++) {{\n"
            f"        accumulator += buffer[index] * {rng.randint(2, 9)};\n"
            f"        if (accumulator > {rng.randint(1000, 9999)}) {{\n"
            f"            accumulator = 0;\n"
            f"        }}\n"
            f"    }}\n"
            f"    return accumulator;\n"
            f"}}\n\n"
        )
    return "".join(parts).encode("ascii")


def bitmap_like(width: int, height: int, seed: int = 3) -> bytes:
    """Συνθετική εικόνα με μεγάλες ομοιόμορφες περιοχές — ευνοεί RLE."""
    rng = random.Random(seed)
    rows = []
    for y in range(height):
        row = bytearray()
        x = 0
        while x < width:
            run = min(rng.randint(4, 60), width - x)
            row += bytes([rng.choice((0, 0, 0, 255, 128))]) * run
            x += run
        rows.append(bytes(row))
    return b"".join(rows)


def dna_like(n: int, seed: int = 4) -> bytes:
    """Ακολουθία DNA: 4 σύμβολα, εντροπία ≈ 2 bits — ευνοεί entropy coding."""
    rng = random.Random(seed)
    return "".join(rng.choice("ACGT") for _ in range(n)).encode("ascii")


def incompressible(n: int, seed: int = 5) -> bytes:
    """Ψευδοτυχαία bytes: H ≈ 8 bits. Κανείς δεν πρέπει να συμπιέσει."""
    rng = random.Random(seed)
    return bytes(rng.randrange(256) for _ in range(n))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    files = {
        "text_natural.txt": natural_text(25_000),
        "source_code.c": source_code(400),
        "bitmap_like.raw": bitmap_like(400, 300),
        "dna_like.txt": dna_like(120_000),
        "incompressible.bin": incompressible(60_000),
    }
    for name, blob in files.items():
        (OUT / name).write_bytes(blob)
        print(f"  {name:<22} {len(blob):>9,} bytes")
    print(f"\n  Γράφτηκαν στο {OUT}/")
    print("  Για τα πειράματα της εργασίας χρησιμοποίησε το Canterbury Corpus.")


if __name__ == "__main__":
    main()
