"""
adaptive.py — Προσαρμοστικό (adaptive) Arithmetic Coding

ΓΙΑΤΙ ΥΠΑΡΧΕΙ
-------------
Η εργασία υποστηρίζει ότι το κόστος μετάδοσης του μοντέλου είναι
καθοριστικός παράγοντας στη σύγκριση αλγορίθμων: ο Huffman και το
στατικό Arithmetic Coding πληρώνουν κεφαλίδα, ο LZW όχι. Το επιχείρημα
μένει μισό χωρίς την προφανή συνέχειά του — τι γίνεται αν ο εντροπικός
κωδικοποιητής *δεν* μεταδώσει καθόλου μοντέλο;

Στο προσαρμοστικό σχήμα, κωδικοποιητής και αποκωδικοποιητής ξεκινούν από
ταυτόσημο αρχικό μοντέλο (όλα τα σύμβολα με συχνότητα 1) και το
ενημερώνουν παράλληλα μετά από κάθε σύμβολο. Επειδή ο αποκωδικοποιητής
έχει ήδη αποκωδικοποιήσει το σύμβολο πριν το χρησιμοποιήσει για
ενημέρωση, οι δύο πλευρές παραμένουν συγχρονισμένες χωρίς καμία
επικοινωνία. Η κεφαλίδα περιορίζεται στο μήκος του μηνύματος.

Έτσι προκύπτουν τρεις παραλλαγές του ίδιου αλγορίθμου, που απομονώνουν
ακριβώς πού πάει το κόστος:

    στατικό + κεφαλίδα   : φορτίο ≈ H(X)·n, συν 5 bytes ανά σύμβολο
    προσαρμοστικό        : καμία κεφαλίδα, φορτίο ελαφρώς μεγαλύτερο
                           λόγω του «κόστους εκμάθησης» στην αρχή

Το εύρημα είναι μετρήσιμο και διαφορετικό ανά μέγεθος αρχείου: σε μικρά
αρχεία το προσαρμοστικό κερδίζει καθαρά, σε μεγάλα η διαφορά εξαφανίζεται.

ΥΛΟΠΟΙΗΣΗ
---------
Χρησιμοποιείται ο ίδιος πυρήνας κλιμάκωσης με το arithmetic.py (24 bits,
τρεις περιπτώσεις E1/E2/E3). Η μόνη διαφορά είναι ότι το μοντέλο
ενημερώνεται.

Δύο λεπτομέρειες που είναι εύκολο να αστοχήσουν:

1. **Αρχικοποίηση με 1 (Laplace smoothing).** Κάθε σύμβολο ξεκινά με
   συχνότητα 1, όχι 0. Διαφορετικά ένα σύμβολο που δεν έχει εμφανιστεί
   έχει μηδενικό διάστημα και δεν μπορεί να κωδικοποιηθεί.

2. **Κλιμάκωση συχνοτήτων (halving).** Το άθροισμα των συχνοτήτων δεν
   επιτρέπεται να ξεπεράσει το QUARTER του εύρους, αλλιώς η ακέραιη
   αριθμητική του κωδικοποιητή καταρρέει. Όταν πλησιάσει, όλες οι
   συχνότητες υποδιπλασιάζονται (με ελάχιστο 1). Ο αποκωδικοποιητής κάνει
   την ίδια ενέργεια στο ίδιο σημείο, αλλιώς αποσυγχρονίζονται.

Μορφή αρχείου
-------------
    uint32  N       μήκος αρχικών δεδομένων
    payload

Δηλαδή 4 bytes κεφαλίδα συνολικά, ανεξάρτητα από το αλφάβητο.
"""

from __future__ import annotations

from .bitio import BitReader, BitWriter

NBITS = 24
FULL = 1 << NBITS
HALF = FULL >> 1
QUARTER = FULL >> 2
THREE_Q = 3 * QUARTER
MASK = FULL - 1

ALPHABET = 256
MAX_TOTAL = QUARTER - 1      # ανώτατο άθροισμα συχνοτήτων

HEADER_BYTES = 4


class AdaptiveModel:
    """
    Προσαρμοστικό μοντέλο συχνοτήτων για αλφάβητο 256 συμβόλων.

    Οι αθροιστικές συχνότητες κρατούνται σε δέντρο Fenwick (binary indexed
    tree). Η αφελής υλοποίηση με γραμμική σάρωση του πίνακα συχνοτήτων
    κοστίζει O(|Σ|) ανά σύμβολο, δηλαδή 256 προσθέσεις για κάθε byte της
    εισόδου· σε αρχείο 150 KB αυτό είναι περίπου 38 εκατομμύρια πράξεις.
    Το δέντρο Fenwick μειώνει το κόστος σε O(log|Σ|) = 8 βήματα τόσο για
    την ανάκτηση αθροιστικής συχνότητας όσο και για την ενημέρωση, και
    επιπλέον επιτρέπει αναζήτηση συμβόλου σε O(log|Σ|).

    Η δομή αυτή είναι ο λόγος που ο προσαρμοστικός κωδικοποιητής είναι
    πρακτικά χρησιμοποιήσιμος σε Python πάνω σε ολόκληρο το corpus.
    """

    __slots__ = ("tree", "total")

    def __init__(self) -> None:
        # tree[i] κρατά άθροισμα διαστήματος κατά τη σύμβαση Fenwick,
        # με δεικτοδότηση 1..ALPHABET. Αρχική συχνότητα 1 για κάθε σύμβολο
        # (Laplace smoothing): σύμβολο με μηδενική συχνότητα θα είχε κενό
        # διάστημα και δεν θα μπορούσε να κωδικοποιηθεί.
        self.tree = [0] * (ALPHABET + 1)
        for i in range(1, ALPHABET + 1):
            self.tree[i] += 1
            j = i + (i & -i)
            if j <= ALPHABET:
                self.tree[j] += self.tree[i]
        self.total = ALPHABET

    def _prefix(self, i: int) -> int:
        """Άθροισμα συχνοτήτων των συμβόλων 0..i-1."""
        s = 0
        while i > 0:
            s += self.tree[i]
            i -= i & -i
        return s

    def cum(self, sym: int) -> tuple[int, int]:
        """Αθροιστικό διάστημα [low, high) του συμβόλου."""
        low = self._prefix(sym)
        return low, low + self._freq(sym)

    def _freq(self, sym: int) -> int:
        return self._prefix(sym + 1) - self._prefix(sym)

    def symbol_for(self, target: int) -> tuple[int, int, int]:
        """
        Σύμβολο του οποίου το διάστημα περιέχει το target, σε O(log|Σ|).

        Κατεβαίνει το δέντρο Fenwick ξεκινώντας από τη μεγαλύτερη δύναμη
        του 2 που δεν υπερβαίνει το μέγεθος του αλφαβήτου.
        """
        idx, remaining = 0, target
        bit = 1 << (ALPHABET.bit_length() - 1)
        while bit:
            nxt = idx + bit
            if nxt <= ALPHABET and self.tree[nxt] <= remaining:
                idx = nxt
                remaining -= self.tree[nxt]
            bit >>= 1
        low = target - remaining
        return idx, low, low + self._freq(idx)

    def update(self, sym: int, increment: int = 32) -> None:
        """
        Ενημερώνει το μοντέλο μετά την κωδικοποίηση/αποκωδικοποίηση.

        Το increment ελέγχει πόσο γρήγορα προσαρμόζεται το μοντέλο· τιμή
        μεγαλύτερη του 1 μειώνει το «κόστος εκμάθησης» στην αρχή του
        αρχείου, εις βάρος της ευελιξίας σε μεταβολές της κατανομής.
        """
        i = sym + 1
        while i <= ALPHABET:
            self.tree[i] += increment
            i += i & -i
        self.total += increment
        if self.total > MAX_TOTAL:
            self._rescale()

    def _rescale(self) -> None:
        """
        Υποδιπλασιασμός όλων των συχνοτήτων, με ελάχιστο 1.

        Απαραίτητο ώστε το άθροισμα να μην ξεπεράσει το QUARTER του εύρους
        του κωδικοποιητή. Ο αποκωδικοποιητής εκτελεί την ίδια ενέργεια στο
        ίδιο ακριβώς σημείο· διαφορετικά τα δύο μοντέλα αποσυγχρονίζονται
        και η αποκωδικοποίηση καταρρέει.
        """
        freqs = [max(1, (self._freq(s) + 1) >> 1) for s in range(ALPHABET)]
        self.tree = [0] * (ALPHABET + 1)
        for i in range(1, ALPHABET + 1):
            self.tree[i] += freqs[i - 1]
            j = i + (i & -i)
            if j <= ALPHABET:
                self.tree[j] += self.tree[i]
        self.total = sum(freqs)


def compress(data: bytes, increment: int = 32) -> bytes:
    if not isinstance(increment, int) or isinstance(increment, bool) or increment < 1:
        raise ValueError("Το increment πρέπει να είναι θετικός ακέραιος")
    header = len(data).to_bytes(4, "big")
    if not data:
        return header

    model = AdaptiveModel()
    bw = BitWriter()
    low, high, pending = 0, MASK, 0

    def emit(bit: int) -> None:
        nonlocal pending
        bw.write_bit(bit)
        for _ in range(pending):
            bw.write_bit(1 - bit)
        pending = 0

    for byte in data:
        cum_lo, cum_hi = model.cum(byte)
        total = model.total
        rng = high - low + 1
        high = low + (rng * cum_hi) // total - 1
        low = low + (rng * cum_lo) // total

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

        model.update(byte, increment)

    pending += 1
    emit(0 if low < QUARTER else 1)

    return header + bw.getvalue()


def decompress(blob: bytes, increment: int = 32) -> bytes:
    if len(blob) < HEADER_BYTES:
        raise ValueError("Κομμένη κεφαλίδα adaptive arithmetic")
    if not isinstance(increment, int) or isinstance(increment, bool) or increment < 1:
        raise ValueError("Το increment πρέπει να είναι θετικός ακέραιος")
    n = int.from_bytes(blob[0:4], "big")
    if n == 0:
        return b""

    model = AdaptiveModel()
    br = BitReader(blob[HEADER_BYTES:] + b"\x00" * 8)

    low, high = 0, MASK
    value = br.read_bits(NBITS)
    out = bytearray()

    for _ in range(n):
        total = model.total
        rng = high - low + 1
        target = ((value - low + 1) * total - 1) // rng
        sym, cum_lo, cum_hi = model.symbol_for(target)
        out.append(sym)

        high = low + (rng * cum_hi) // total - 1
        low = low + (rng * cum_lo) // total

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

        model.update(sym, increment)

    return bytes(out)


def header_bits(data: bytes, **kwargs) -> int:
    """Μόνο το μήκος του μηνύματος. Κανένα μοντέλο δεν μεταδίδεται."""
    return HEADER_BYTES * 8
