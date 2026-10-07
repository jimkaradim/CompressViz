"""
huffman.py — Huffman Coding (canonical, με πραγματική κεφαλίδα)

ΔΙΟΡΘΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ ΥΛΟΠΟΙΗΣΗΣ
------------------------------------------
1. Υπάρχει αποκωδικοποιητής (η αρχική υλοποίηση δεν είχε).
2. Η έξοδος είναι πραγματικά bytes, όχι string από '0'/'1'.
3. Μετράται το ΚΟΣΤΟΣ ΤΗΣ ΚΕΦΑΛΙΔΑΣ. Ο αποκωδικοποιητής δεν γνωρίζει το
   δέντρο, άρα αυτό πρέπει να μεταδοθεί. Αγνοώντας το, η αρχική μέτρηση
   ευνοούσε αθέμιτα τον Huffman έναντι του LZW (που δεν χρειάζεται
   κεφαλίδα).

Χρησιμοποιείται *κανονικός* (canonical) κώδικας Huffman: αντί για το ίδιο
το δέντρο μεταδίδονται μόνο τα μήκη κωδικών ανά σύμβολο, από τα οποία ο
αποκωδικοποιητής ανακατασκευάζει μονοσήμαντα τους κωδικούς. Αυτή είναι η
τεχνική που χρησιμοποιεί το DEFLATE (RFC 1951).

Μορφή αρχείου
-------------
    uint32  N       πλήθος συμβόλων του αρχικού μηνύματος
    uint16  K       πλήθος διακριτών συμβόλων (1..256· το 0 σημαίνει 256)
    K x {uint8 σύμβολο, uint8 μήκος κωδικού}
    payload         τα κωδικοποιημένα bits (padding στο τελευταίο byte)
"""

from __future__ import annotations

import heapq
from collections import Counter

from .bitio import BitReader, BitWriter


# ─────────────────────────────────────────────────────────────────────────
# Κατασκευή μηκών κωδικών
# ─────────────────────────────────────────────────────────────────────────

def code_lengths(data: bytes) -> dict[int, int]:
    """
    Επιστρέφει {σύμβολο: μήκος κωδικού} με τον κλασικό αλγόριθμο Huffman.

    Το heap περιέχει πλειάδες (συχνότητα, αύξων_αριθμός, κόμβος) ώστε οι
    συγκρίσεις να είναι ντετερμινιστικές: χωρίς τον αύξοντα αριθμό, η
    σειρά ισοβαθμιών εξαρτάται από τη σειρά εισαγωγής και η υλοποίηση
    παύει να είναι αναπαραγώγιμη.
    """
    freq = Counter(data)
    if not freq:
        return {}
    if len(freq) == 1:
        # Ειδική περίπτωση: ένα μόνο σύμβολο -> κωδικός μήκους 1
        return {next(iter(freq)): 1}

    counter = 0
    heap: list = []
    for sym, f in sorted(freq.items()):
        heap.append((f, counter, (sym,)))
        counter += 1
    heapq.heapify(heap)

    lengths: dict[int, int] = {s: 0 for s in freq}
    while len(heap) > 1:
        f1, _, g1 = heapq.heappop(heap)
        f2, _, g2 = heapq.heappop(heap)
        for s in g1 + g2:
            lengths[s] += 1          # κάθε συγχώνευση προσθέτει 1 bit
        heapq.heappush(heap, (f1 + f2, counter, g1 + g2))
        counter += 1

    return lengths


def canonical_codes(lengths: dict[int, int]) -> dict[int, tuple[int, int]]:
    """
    Μετατρέπει μήκη κωδικών σε canonical κωδικούς.

    Επιστρέφει {σύμβολο: (τιμή_κωδικού, μήκος)}. Τα σύμβολα ταξινομούνται
    κατά (μήκος, σύμβολο) και οι κωδικοί ανατίθενται αύξοντα, με ολίσθηση
    σε κάθε αύξηση μήκους.
    """
    codes: dict[int, tuple[int, int]] = {}
    code = 0
    prev_len = None
    for sym, ln in sorted(lengths.items(), key=lambda kv: (kv[1], kv[0])):
        if prev_len is None:
            prev_len = ln
        elif ln > prev_len:
            code <<= (ln - prev_len)
            prev_len = ln
        codes[sym] = (code, ln)
        code += 1
    return codes


# ─────────────────────────────────────────────────────────────────────────
# Κωδικοποίηση / Αποκωδικοποίηση
# ─────────────────────────────────────────────────────────────────────────

def _pack_header(lengths: dict[int, int], n: int) -> bytes:
    k = len(lengths)
    out = bytearray()
    out += n.to_bytes(4, "big")
    out += (0 if k == 256 else k).to_bytes(2, "big")
    for sym in sorted(lengths):
        out.append(sym)
        out.append(lengths[sym])
    return bytes(out)


def header_bits(data: bytes) -> int:
    """Κόστος μετάδοσης των μηκών κωδικών, σε bits (4 + 2 + 2K bytes)."""
    k = len(set(data))
    return (4 + 2 + 2 * k) * 8


def compress(data: bytes) -> bytes:
    if not data:
        return (0).to_bytes(4, "big") + (0).to_bytes(2, "big")

    lengths = code_lengths(data)
    codes = canonical_codes(lengths)

    bw = BitWriter()
    for byte in data:
        value, ln = codes[byte]
        bw.write_bits(value, ln)

    return _pack_header(lengths, len(data)) + bw.getvalue()


def decompress(blob: bytes) -> bytes:
    if len(blob) < 6:
        raise ValueError("Κομμένη κεφαλίδα Huffman")
    n = int.from_bytes(blob[0:4], "big")
    if n == 0:
        return b""
    k = int.from_bytes(blob[4:6], "big")
    if k == 0:
        k = 256

    lengths: dict[int, int] = {}
    pos = 6
    if len(blob) < pos + 2 * k:
        raise ValueError("Κομμένος πίνακας μηκών Huffman")
    for _ in range(k):
        sym, length = blob[pos], blob[pos + 1]
        if sym in lengths or length == 0:
            raise ValueError("Μη έγκυρος πίνακας μηκών Huffman")
        lengths[sym] = length
        pos += 2

    codes = canonical_codes(lengths)
    lookup = {(v, ln): sym for sym, (v, ln) in codes.items()}

    br = BitReader(blob[pos:])
    out = bytearray()
    value, length = 0, 0
    try:
        while len(out) < n:
            value = (value << 1) | br.read_bit()
            length += 1
            sym = lookup.get((value, length))
            if sym is not None:
                out.append(sym)
                value, length = 0, 0
    except EOFError as exc:
        raise ValueError("Κομμένο Huffman payload") from exc
    return bytes(out)
