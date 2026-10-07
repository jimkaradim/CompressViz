"""
lzw.py — Lempel-Ziv-Welch

ΔΙΟΡΘΩΣΕΙΣ / ΒΕΛΤΙΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ ΥΛΟΠΟΙΗΣΗΣ
------------------------------------------------------
1. Υπάρχει αποκωδικοποιητής, συμπεριλαμβανομένης της ειδικής περίπτωσης
   «KwKwK» (ο κωδικός που λαμβάνεται δεν υπάρχει ακόμη στο λεξικό του
   αποκωδικοποιητή, επειδή αυτός βρίσκεται ένα βήμα πίσω).
2. Κωδικοί μεταβλητού πλάτους (9 -> max_bits) αντί για σταθερά 12 bits.
   Έτσι οι πρώτες εκατοντάδες εκπομπές δεν σπαταλούν bits, όπως στην
   πραγματική υλοποίηση των GIF και Unix compress.
3. Πραγματικό bit packing αντί για εκτίμηση `len(codes) * 12`.

Ο συγχρονισμός πλάτους μεταξύ κωδικοποιητή και αποκωδικοποιητή απαιτεί
προσοχή: ο αποκωδικοποιητής προσθέτει εγγραφές με καθυστέρηση ενός
βήματος, οπότε αυξάνει το πλάτος όταν `next_code + 1 == 2^width`, ενώ ο
κωδικοποιητής όταν `next_code == 2^width`.

Μορφή αρχείου
-------------
    uint8   max_bits
    uint32  N          πλήθος bytes της αρχικής εισόδου
    payload            κωδικοί μεταβλητού πλάτους
"""

from __future__ import annotations

from .bitio import BitReader, BitWriter

HEADER_BYTES = 5


def compress(data: bytes, max_bits: int = 12) -> bytes:
    if not isinstance(max_bits, int) or isinstance(max_bits, bool) or not 9 <= max_bits <= 16:
        raise ValueError("Το max_bits του LZW πρέπει να είναι μεταξύ 9 και 16")
    header = bytes([max_bits]) + len(data).to_bytes(4, "big")
    if not data:
        return header

    max_dict = 1 << max_bits
    table: dict[bytes, int] = {bytes([i]): i for i in range(256)}
    next_code = 256
    width = 9

    bw = BitWriter()
    w = b""

    for byte in data:
        wc = w + bytes([byte])
        if wc in table:
            w = wc
            continue

        bw.write_bits(table[w], width)

        if next_code < max_dict:
            table[wc] = next_code
            next_code += 1
            if next_code == (1 << width) and width < max_bits:
                width += 1

        w = bytes([byte])

    if w:
        bw.write_bits(table[w], width)

    return header + bw.getvalue()


def decompress(blob: bytes) -> bytes:
    if len(blob) < HEADER_BYTES:
        raise ValueError("Κομμένη κεφαλίδα LZW")
    max_bits = blob[0]
    if not 9 <= max_bits <= 16:
        raise ValueError("Μη έγκυρο max_bits στην κεφαλίδα LZW")
    n = int.from_bytes(blob[1:5], "big")
    if n == 0:
        return b""

    max_dict = 1 << max_bits
    table: dict[int, bytes] = {i: bytes([i]) for i in range(256)}
    next_code = 256
    width = 9

    br = BitReader(blob[HEADER_BYTES:])
    out = bytearray()

    try:
        first = br.read_bits(width)
    except EOFError as exc:
        raise ValueError("Κομμένο LZW payload") from exc
    if first not in table:
        raise ValueError(f"Μη έγκυρος πρώτος κωδικός LZW: {first}")
    w = table[first]
    out += w

    while len(out) < n:
        try:
            code = br.read_bits(width)
        except EOFError as exc:
            raise ValueError("Κομμένο LZW payload") from exc

        if code in table:
            entry = table[code]
        elif code == next_code:
            entry = w + w[:1]          # περίπτωση KwKwK
        else:
            raise ValueError(f"Μη έγκυρος κωδικός LZW: {code}")

        out += entry
        if len(out) > n:
            raise ValueError("Το LZW payload υπερβαίνει το δηλωμένο μήκος")

        if next_code < max_dict:
            table[next_code] = w + entry[:1]
            next_code += 1
            # Ο αποκωδικοποιητής είναι ένα βήμα πίσω -> +1
            if next_code + 1 == (1 << width) and width < max_bits:
                width += 1

        w = entry

    return bytes(out[:n])


def header_bits(data: bytes, **kwargs) -> int:
    """Το λεξικό δεν μεταδίδεται — ανακατασκευάζεται από τον δέκτη."""
    return HEADER_BYTES * 8
