"""
bitio.py — Στοιχειώδης είσοδος/έξοδος σε επίπεδο bit.

Όλοι οι κωδικοποιητές του CompressViz παράγουν *πραγματικά bytes*, όχι
συμβολοσειρές από '0'/'1'. Αυτό είναι απαραίτητο ώστε οι μετρήσεις
μεγέθους να είναι ειλικρινείς: μετράμε το αρχείο που θα γραφόταν στον
δίσκο, όχι μια αναπαράσταση του.

Η κλάση BitWriter συσσωρεύει bits και τα «γεμίζει» (padding) στο τέλος
ώστε να συμπληρωθεί ακέραιος αριθμός bytes. Το αρχικό πλήθος συμβόλων
αποθηκεύεται από κάθε codec στην κεφαλίδα του, ώστε ο αποκωδικοποιητής
να ξέρει πότε να σταματήσει και να αγνοήσει τα padding bits.
"""

from __future__ import annotations


class BitWriter:
    """Γράφει bits διαδοχικά και τα επιστρέφει ως bytes (MSB-first)."""

    __slots__ = ("_buf", "_cur", "_nbits", "count")

    def __init__(self) -> None:
        self._buf: bytearray = bytearray()
        self._cur: int = 0      # τρέχον byte υπό κατασκευή
        self._nbits: int = 0    # πόσα bits έχουν μπει στο _cur
        self.count: int = 0     # συνολικά bits που γράφτηκαν

    def write_bit(self, bit: int) -> None:
        self._cur = (self._cur << 1) | (bit & 1)
        self._nbits += 1
        self.count += 1
        if self._nbits == 8:
            self._buf.append(self._cur)
            self._cur = 0
            self._nbits = 0

    def write_bits(self, value: int, n: int) -> None:
        """Γράφει τα n λιγότερο σημαντικά bits του value, MSB-first."""
        for i in range(n - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def getvalue(self) -> bytes:
        """Κλείνει το τελευταίο byte με μηδενικά padding bits."""
        if self._nbits == 0:
            return bytes(self._buf)
        out = bytearray(self._buf)
        out.append(self._cur << (8 - self._nbits))
        return bytes(out)


class BitReader:
    """Διαβάζει bits από bytes (MSB-first)."""

    __slots__ = ("_data", "_pos")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0           # θέση σε bits

    def read_bit(self) -> int:
        byte_i, bit_i = divmod(self._pos, 8)
        if byte_i >= len(self._data):
            raise EOFError("Τέλος bitstream")
        self._pos += 1
        return (self._data[byte_i] >> (7 - bit_i)) & 1

    def read_bits(self, n: int) -> int:
        v = 0
        for _ in range(n):
            v = (v << 1) | self.read_bit()
        return v
