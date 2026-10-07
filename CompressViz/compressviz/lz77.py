"""
lz77.py — LZ77 (sliding window) και LZSS

ΔΙΟΡΘΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ ΥΛΟΠΟΙΗΣΗΣ
------------------------------------------
1. Υπάρχει αποκωδικοποιητής.
2. Διορθώνεται σφάλμα πλάτους πεδίου: η αρχική υλοποίηση χρέωνε 3 bits
   για το πεδίο μήκους, ενώ με lookahead = 8 το μήκος φτάνει την τιμή 8,
   που απαιτεί 4 bits. Τα πλάτη υπολογίζονται πλέον από τις παραμέτρους.
3. Το μέγεθος προκύπτει από πραγματικό bitstream αντί να εκτιμάται.
4. Προστίθεται η παραλλαγή LZSS (Storer & Szymanski, 1982): ένα flag bit
   ανά token επιτρέπει την εκπομπή σκέτου literal όταν δεν υπάρχει
   ωφέλιμη αντιστοίχιση, αντί του σπάταλου token (0, 0, c). Αυτό εξηγεί
   και θεραπεύει την επέκταση δεδομένων που παρατηρήθηκε αρχικά.
5. Η αναζήτηση αντιστοιχίσεων γίνεται με hash chains επί τριάδων bytes
   (η τεχνική του zlib) αντί για γραμμική σάρωση του παραθύρου, ώστε να
   είναι εφικτά πειράματα με παράθυρα 32 KB.

Μορφή αρχείου
-------------
    uint8   mode            0 = LZ77 (τριάδες), 1 = LZSS
    uint32  window_size
    uint16  lookahead_size
    uint32  N               μήκος αρχικών δεδομένων
    payload                 tokens σε επίπεδο bit
"""

from __future__ import annotations

from .bitio import BitReader, BitWriter

MIN_MATCH = 3           # ελάχιστο ωφέλιμο μήκος αντιστοίχισης (LZSS)
MAX_CHAIN = 64          # όριο βημάτων ανά αλυσίδα (χρόνος vs ποιότητα)
HEADER_BYTES = 11


class _Matcher:
    """Ευρετήριο θέσεων ανά τριάδα bytes (hash chain)."""

    __slots__ = ("data", "window_size", "table")

    def __init__(self, data: bytes, window_size: int) -> None:
        self.data = data
        self.window_size = window_size
        self.table: dict[bytes, list[int]] = {}

    def insert(self, pos: int) -> None:
        if pos + MIN_MATCH <= len(self.data):
            key = self.data[pos:pos + MIN_MATCH]
            self.table.setdefault(key, []).append(pos)

    def find(self, pos: int, lookahead: int) -> tuple[int, int]:
        """Επιστρέφει (offset, length) της καλύτερης αντιστοίχισης."""
        data = self.data
        max_len = min(lookahead, len(data) - pos)
        if max_len < MIN_MATCH:
            return 0, 0

        chain = self.table.get(data[pos:pos + MIN_MATCH])
        if not chain:
            return 0, 0

        limit = pos - self.window_size
        best_off, best_len = 0, 0

        # Οι πιο πρόσφατες θέσεις πρώτα: μικρότερα offsets, γρήγορη έξοδος
        for cand in reversed(chain[-MAX_CHAIN:]):
            if cand < limit:
                break
            ln = MIN_MATCH
            while ln < max_len and data[cand + ln] == data[pos + ln]:
                ln += 1
            if ln > best_len:
                best_len, best_off = ln, pos - cand
                if best_len == max_len:
                    break
        return best_off, best_len


def compress(data: bytes, window_size: int = 4096,
             lookahead_size: int = 18, mode: str = "lzss") -> bytes:
    if mode not in {"lz77", "lzss"}:
        raise ValueError("Το mode πρέπει να είναι 'lz77' ή 'lzss'")
    if not 1 <= window_size <= 0xFFFFFFFF:
        raise ValueError("Το window_size πρέπει να είναι μεταξύ 1 και 2^32-1")
    if not 1 <= lookahead_size <= 0xFFFF:
        raise ValueError("Το lookahead_size πρέπει να είναι μεταξύ 1 και 65535")
    off_bits = max(1, window_size.bit_length())
    len_bits = max(1, lookahead_size.bit_length())
    is_lzss = (mode == "lzss")

    matcher = _Matcher(data, window_size)
    bw = BitWriter()
    pos, n = 0, len(data)

    while pos < n:
        # Στο κλασικό LZ77 κάθε token κλείνει με literal, άρα η
        # αντιστοίχιση δεν επιτρέπεται να καταναλώσει το τελευταίο byte.
        cap = lookahead_size if is_lzss else min(lookahead_size, n - pos - 1)
        off, ln = matcher.find(pos, cap) if cap >= MIN_MATCH else (0, 0)

        if is_lzss and ln >= MIN_MATCH:
            bw.write_bit(1)
            bw.write_bits(off, off_bits)
            bw.write_bits(ln, len_bits)
            step = ln
        elif is_lzss:
            bw.write_bit(0)
            bw.write_bits(data[pos], 8)
            step = 1
        else:
            nxt = data[pos + ln] if pos + ln < n else 0
            bw.write_bits(off, off_bits)
            bw.write_bits(ln, len_bits)
            bw.write_bits(nxt, 8)
            step = ln + 1

        for k in range(pos, min(pos + step, n)):
            matcher.insert(k)
        pos += step

    header = bytearray()
    header.append(1 if is_lzss else 0)
    header += window_size.to_bytes(4, "big")
    header += lookahead_size.to_bytes(2, "big")
    header += n.to_bytes(4, "big")
    return bytes(header) + bw.getvalue()


def decompress(blob: bytes) -> bytes:
    if len(blob) < HEADER_BYTES:
        raise ValueError("Κομμένη κεφαλίδα LZ77/LZSS")
    if blob[0] not in (0, 1):
        raise ValueError(f"Άγνωστο mode LZ77/LZSS: {blob[0]}")
    is_lzss = blob[0] == 1
    window_size = int.from_bytes(blob[1:5], "big")
    lookahead_size = int.from_bytes(blob[5:7], "big")
    n = int.from_bytes(blob[7:11], "big")
    if window_size == 0 or lookahead_size == 0:
        raise ValueError("Μη έγκυρες μηδενικές παράμετροι LZ77/LZSS")

    off_bits = max(1, window_size.bit_length())
    len_bits = max(1, lookahead_size.bit_length())

    br = BitReader(blob[HEADER_BYTES:])
    out = bytearray()

    try:
        while len(out) < n:
            if is_lzss and br.read_bit() == 1:
                off = br.read_bits(off_bits)
                ln = br.read_bits(len_bits)
                if off == 0 or off > len(out) or ln < MIN_MATCH or ln > lookahead_size:
                    raise ValueError("Μη έγκυρο LZSS match token")
                start = len(out) - off
                for i in range(ln):
                    # Η αντιγραφή μπορεί να χρησιμοποιεί bytes που μόλις γράφτηκαν.
                    out.append(out[start + i])
                    if len(out) > n:
                        raise ValueError("Το LZSS token υπερβαίνει το δηλωμένο μήκος")
            elif is_lzss:
                out.append(br.read_bits(8))
            else:
                off = br.read_bits(off_bits)
                ln = br.read_bits(len_bits)
                nxt = br.read_bits(8)
                if ln > lookahead_size or (ln and (off == 0 or off > len(out))):
                    raise ValueError("Μη έγκυρο LZ77 token")
                if ln == 0 and off != 0:
                    raise ValueError("Μη έγκυρο κενό LZ77 match")
                start = len(out) - off
                for i in range(ln):
                    out.append(out[start + i])
                    if len(out) > n:
                        raise ValueError("Το LZ77 token υπερβαίνει το δηλωμένο μήκος")
                if len(out) < n:
                    out.append(nxt)
    except EOFError as exc:
        raise ValueError("Κομμένο LZ77/LZSS payload") from exc

    return bytes(out[:n])


def header_bits(data: bytes, **kwargs) -> int:
    """Ο LZ77 δεν μεταδίδει μοντέλο· μόνο τις παραμέτρους."""
    return HEADER_BYTES * 8
