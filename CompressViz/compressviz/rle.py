"""
rle.py — Run-Length Encoding (δύο ορθές παραλλαγές)

ΣΗΜΑΝΤΙΚΗ ΔΙΟΡΘΩΣΗ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ ΥΛΟΠΟΙΗΣΗΣ
---------------------------------------------------
Η «κειμενική» μορφή RLE που γράφει τον μετρητή ως ψηφία μέσα στο ίδιο
ρεύμα με τα δεδομένα (π.χ. "AAABB" -> "3A2B") ΔΕΝ είναι αντιστρέψιμη
όταν η είσοδος περιέχει ψηφία:

    "aa3bb" -> "2a32b"
    "2a3bb" -> "2a32b"      <-- ίδια έξοδος, διαφορετική είσοδος

Επομένως δεν αποτελεί lossless κωδικοποίηση. Παρακάτω υλοποιούνται δύο
παραλλαγές που είναι αποδεδειγμένα αντιστρέψιμες:

1. `pairs`    — κάθε run κωδικοποιείται πάντα ως 2 bytes (πλήθος, σύμβολο).
                Αντιστοιχεί ακριβώς στο σχήμα (πλήθος, σύμβολο) της
                θεωρητικής περιγραφής. Σε δεδομένα χωρίς runs διπλασιάζει
                το μέγεθος — αυτό είναι πραγματικό αποτέλεσμα, όχι σφάλμα.

2. `packbits` — η πρότυπη βιομηχανική παραλλαγή (TIFF, PDF, BMP, Apple
                PackBits). Χρησιμοποιεί control byte που διακρίνει
                «literal run» από «repeat run», ώστε η χειρότερη περίπτωση
                επέκτασης να περιορίζεται σε ~1/128 ≈ 0,8%.

Και οι δύο δουλεύουν σε bytes, όχι σε str, ώστε να καλύπτουν και δυαδικά
αρχεία του corpus.
"""

from __future__ import annotations

MAX_RUN_PAIRS = 255      # ο μετρητής χωράει σε 1 byte


# ─────────────────────────────────────────────────────────────────────────
# Παραλλαγή 1: (count, symbol) ζεύγη
# ─────────────────────────────────────────────────────────────────────────

def encode_pairs(data: bytes) -> bytes:
    """Κωδικοποιεί κάθε run ως ζεύγος (πλήθος, σύμβολο) των 2 bytes."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        sym = data[i]
        run = 1
        while i + run < n and data[i + run] == sym and run < MAX_RUN_PAIRS:
            run += 1
        out.append(run)
        out.append(sym)
        i += run
    return bytes(out)


def decode_pairs(blob: bytes) -> bytes:
    """Αντίστροφη της encode_pairs."""
    if len(blob) % 2 != 0:
        raise ValueError("Μη έγκυρο RLE-pairs stream (περιττό πλήθος bytes)")
    out = bytearray()
    for i in range(0, len(blob), 2):
        if blob[i] == 0:
            raise ValueError("Μη έγκυρο RLE-pairs stream (μηδενικό run)")
        out.extend(bytes([blob[i + 1]]) * blob[i])
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────
# Παραλλαγή 2: PackBits
# ─────────────────────────────────────────────────────────────────────────
#
# Το byte ελέγχου c δηλώνει τι ακολουθεί:
#   0   <= c <= 127  ->  ακολουθούν (c + 1) κυριολεκτικά bytes
#   129 <= c <= 255  ->  το επόμενο byte επαναλαμβάνεται (257 - c) φορές
#   c   == 128       ->  δεν χρησιμοποιείται (no-op)

def encode_packbits(data: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(data)

    while i < n:
        # Μήκος του run που ξεκινά στη θέση i
        run = 1
        while i + run < n and data[i + run] == data[i] and run < 128:
            run += 1

        if run >= 2:
            # Επανάληψη: γράφουμε μία φορά το σύμβολο και πόσες φορές εμφανίζεται.
            out.append(257 - run)
            out.append(data[i])
            i += run
        else:
            # Απλά bytes: τα αντιγράφουμε μέχρι να βρεθεί επανάληψη τουλάχιστον 3 φορές.
            start = i
            i += 1
            while i < n and (i - start) < 128:
                if i + 2 < n and data[i] == data[i + 1] == data[i + 2]:
                    break
                i += 1
            length = i - start
            out.append(length - 1)
            out.extend(data[start:i])

    return bytes(out)


def decode_packbits(blob: bytes) -> bytes:
    out = bytearray()
    i, n = 0, len(blob)
    while i < n:
        c = blob[i]
        i += 1
        if c == 128:
            continue
        if c < 128:
            count = c + 1
            if i + count > n:
                raise ValueError("Κομμένο PackBits literal block")
            out.extend(blob[i:i + count])
            i += count
        else:
            count = 257 - c
            if i >= n:
                raise ValueError("Κομμένο PackBits repeat block")
            out.extend(bytes([blob[i]]) * count)
            i += 1
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────
# Ενιαία διεπαφή
# ─────────────────────────────────────────────────────────────────────────

# Το ρεύμα είναι αυτοπεριγραφόμενο: 1 byte ετικέτας παραλλαγής στην αρχή.
# Έτσι ο αποκωδικοποιητής δεν χρειάζεται εξωτερική παράμετρο και η
# διεπαφή είναι κοινή με τους υπόλοιπους codecs.
_TAG = {"pairs": 0, "packbits": 1}


def compress(data: bytes, variant: str = "packbits") -> bytes:
    if variant not in _TAG:
        raise ValueError(f"Άγνωστη παραλλαγή RLE: {variant}")
    body = encode_packbits(data) if variant == "packbits" else encode_pairs(data)
    return bytes([_TAG[variant]]) + body


def decompress(blob: bytes) -> bytes:
    if not blob:
        raise ValueError("Κενό RLE stream")
    if blob[0] == _TAG["packbits"]:
        return decode_packbits(blob[1:])
    if blob[0] == _TAG["pairs"]:
        return decode_pairs(blob[1:])
    raise ValueError(f"Άγνωστη ετικέτα RLE stream: {blob[0]}")


def header_bits(data: bytes, variant: str = "packbits") -> int:
    """Ο RLE δεν μεταδίδει μοντέλο· μόνο την ετικέτα παραλλαγής."""
    return 8
