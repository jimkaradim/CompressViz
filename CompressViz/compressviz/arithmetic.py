"""
arithmetic.py — Arithmetic Coding (πραγματική υλοποίηση)

Η ΣΗΜΑΝΤΙΚΟΤΕΡΗ ΔΙΟΡΘΩΣΗ ΤΗΣ ΕΡΓΑΣΙΑΣ
--------------------------------------
Η αρχική «υλοποίηση» δεν κωδικοποιούσε τίποτε: επέστρεφε απλώς
`ceil(H(X) * n) + 2`, δηλαδή το ίδιο το φράγμα Shannon. Συνεπώς το
συμπέρασμα «το Arithmetic Coding πλησιάζει το θεωρητικό όριο» ήταν
κυκλικό — το αποτέλεσμα είχε οριστεί ίσο με το όριο.

Εδώ υλοποιείται πλήρης ακέραιος κωδικοποιητής με κλιμάκωση (rescaling)
κατά Witten–Neal–Cleary, με στατικό μοντέλο συχνοτήτων. Το μετρούμενο
μέγεθος περιλαμβάνει την κεφαλίδα του μοντέλου, άρα το αποτέλεσμα βγαίνει
*ελαφρώς πάνω* από το όριο Shannon — όπως πρέπει.

Αριθμητική ακρίβεια
-------------------
Χρησιμοποιούνται ακέραιοι 32 bits για τα low/high. Οι τρεις περιπτώσεις
κλιμάκωσης είναι:
    E1: high < half            -> εκπομπή 0, ολίσθηση
    E2: low  >= half           -> εκπομπή 1, ολίσθηση
    E3: quarter <= low, high < 3*quarter  -> underflow, μετρητής pending

Η περίπτωση E3 (underflow) είναι αυτή που λύνει το πρόβλημα ακρίβειας που
περιγράφεται στην §3.5.4 της εργασίας: το διάστημα δεν αφήνεται ποτέ να
συρρικνωθεί κάτω από το ένα τέταρτο του εύρους.

Μορφή αρχείου
-------------
    uint32  N            μήκος αρχικών δεδομένων
    uint16  K            πλήθος διακριτών συμβόλων (0 -> 256)
    K x {uint8 σύμβολο, uint32 συχνότητα}
    payload

Το N γράφεται πρώτο ώστε η κενή είσοδος (N = 0) να αναγνωρίζεται χωρίς
να συγχέεται με την περίπτωση K = 256, που κωδικοποιείται ως 0.
"""

from __future__ import annotations

import math
from collections import Counter

from .bitio import BitReader, BitWriter

# 24 bits αντί για 32: επιτρέπει bit-πανομοιότυπη υλοποίηση σε JavaScript,
# όπου οι αριθμοί είναι IEEE 754 doubles και τα ενδιάμεσα γινόμενα
# rng * total πρέπει να μένουν κάτω από 2^53. Με NBITS = 24 και μηνύματα
# έως ~4 εκατ. συμβόλων το γινόμενο φράσσεται από 2^46. Η απώλεια
# συμπίεσης έναντι των 32 bits είναι αμελητέα (< 1 bit συνολικά).
NBITS = 24
FULL = 1 << NBITS
HALF = FULL >> 1
QUARTER = FULL >> 2
THREE_Q = 3 * QUARTER
MASK = FULL - 1


# ─────────────────────────────────────────────────────────────────────────
# Μοντέλο συχνοτήτων
# ─────────────────────────────────────────────────────────────────────────

class Model:
    """Στατικό μοντέλο: αθροιστικές συχνότητες ανά σύμβολο."""

    __slots__ = ("symbols", "cum", "total")

    def __init__(self, freq: dict[int, int]) -> None:
        self.symbols = sorted(freq)
        self.cum: dict[int, tuple[int, int]] = {}
        running = 0
        for sym in self.symbols:
            self.cum[sym] = (running, running + freq[sym])
            running += freq[sym]
        self.total = running

    def symbol_for(self, target: int) -> int:
        """Βρίσκει το σύμβολο του οποίου το διάστημα περιέχει το target."""
        for sym in self.symbols:
            lo, hi = self.cum[sym]
            if lo <= target < hi:
                return sym
        raise ValueError("Το target είναι εκτός εύρους μοντέλου")


def _pack_model(freq: dict[int, int], n: int) -> bytes:
    k = len(freq)
    out = bytearray()
    out += n.to_bytes(4, "big")
    out += (0 if k == 256 else k).to_bytes(2, "big")
    for sym in sorted(freq):
        out.append(sym)
        out += freq[sym].to_bytes(4, "big")
    return bytes(out)


def _unpack_model(blob: bytes) -> tuple[dict[int, int], int, int]:
    if len(blob) < 6:
        raise ValueError("Κομμένη κεφαλίδα arithmetic coding")
    n = int.from_bytes(blob[0:4], "big")
    if n == 0:
        return {}, 0, 6
    k = int.from_bytes(blob[4:6], "big")
    if k == 0:
        k = 256
    freq: dict[int, int] = {}
    pos = 6
    if len(blob) < pos + 5 * k:
        raise ValueError("Κομμένος πίνακας συχνοτήτων arithmetic coding")
    for _ in range(k):
        sym = blob[pos]
        value = int.from_bytes(blob[pos + 1:pos + 5], "big")
        if sym in freq or value == 0:
            raise ValueError("Μη έγκυρος πίνακας συχνοτήτων arithmetic coding")
        freq[sym] = value
        pos += 5
    if sum(freq.values()) != n:
        raise ValueError("Οι συχνότητες arithmetic coding δεν αθροίζουν στο μήκος")
    return freq, n, pos


# ─────────────────────────────────────────────────────────────────────────
# Κωδικοποίηση
# ─────────────────────────────────────────────────────────────────────────

def compress(data: bytes) -> bytes:
    if not data:
        return (0).to_bytes(4, "big") + (0).to_bytes(2, "big")
    if len(data) >= QUARTER:
        raise ValueError(
            f"Το static arithmetic coding υποστηρίζει έως {QUARTER - 1:,} bytes")

    freq = dict(Counter(data))
    model = Model(freq)
    header = _pack_model(freq, len(data))

    bw = BitWriter()
    low, high, pending = 0, MASK, 0

    def emit(bit: int) -> None:
        nonlocal pending
        bw.write_bit(bit)
        for _ in range(pending):
            bw.write_bit(1 - bit)
        pending = 0

    for byte in data:
        cum_lo, cum_hi = model.cum[byte]
        rng = high - low + 1
        high = low + (rng * cum_hi) // model.total - 1
        low = low + (rng * cum_lo) // model.total

        while True:
            if high < HALF:
                emit(0)
            elif low >= HALF:
                emit(1)
                low -= HALF
                high -= HALF
            elif low >= QUARTER and high < THREE_Q:
                pending += 1
                low -= QUARTER
                high -= QUARTER
            else:
                break
            low = (low << 1) & MASK
            high = ((high << 1) | 1) & MASK

    # Τερματισμός: αρκούν 2 bits για να προσδιοριστεί σημείο στο [low, high]
    pending += 1
    emit(0 if low < QUARTER else 1)

    return header + bw.getvalue()


def decompress(blob: bytes) -> bytes:
    freq, n, offset = _unpack_model(blob)
    if n == 0:
        return b""

    model = Model(freq)
    br = BitReader(blob[offset:] + b"\x00" * 8)   # padding ασφαλείας

    low, high = 0, MASK
    value = br.read_bits(NBITS)
    out = bytearray()

    for _ in range(n):
        rng = high - low + 1
        target = ((value - low + 1) * model.total - 1) // rng
        sym = model.symbol_for(target)
        out.append(sym)

        cum_lo, cum_hi = model.cum[sym]
        high = low + (rng * cum_hi) // model.total - 1
        low = low + (rng * cum_lo) // model.total

        while True:
            if high < HALF:
                pass
            elif low >= HALF:
                low -= HALF
                high -= HALF
                value -= HALF
            elif low >= QUARTER and high < THREE_Q:
                low -= QUARTER
                high -= QUARTER
                value -= QUARTER
            else:
                break
            low = (low << 1) & MASK
            high = ((high << 1) | 1) & MASK
            value = ((value << 1) | br.read_bit()) & MASK

    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────
# Βοηθητικά
# ─────────────────────────────────────────────────────────────────────────

def entropy(data: bytes) -> float:
    """Shannon entropy σε bits ανά σύμβολο (μηδενικής τάξης μοντέλο)."""
    if not data:
        return 0.0
    n = len(data)
    return -sum((f / n) * math.log2(f / n) for f in Counter(data).values())


def shannon_bound_bits(data: bytes) -> float:
    """Το θεωρητικό κάτω όριο H(X) * n, ΧΩΡΙΣ το κόστος του μοντέλου."""
    return entropy(data) * len(data)


def header_bits(data: bytes) -> int:
    """Κόστος μετάδοσης του μοντέλου συχνοτήτων, σε bits."""
    k = len(set(data))
    return (4 + 2 + 5 * k) * 8
