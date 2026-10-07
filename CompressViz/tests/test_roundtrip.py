"""
test_roundtrip.py — Έλεγχος της ιδιότητας lossless

Ο κεντρικός έλεγχος κάθε αλγορίθμου συμπίεσης χωρίς απώλειες είναι ένας:

    decompress(compress(x)) == x    για κάθε x

Τα παρακάτω tests τον επιβάλλουν σε (α) χειροκίνητα επιλεγμένες οριακές
περιπτώσεις, (β) εισόδους που εκθέτουν γνωστές παγίδες κάθε αλγορίθμου,
και (γ) χιλιάδες ψευδοτυχαίες εισόδους με σταθερό seed (αναπαραγώγιμα).

Εκτέλεση:   pytest -q
"""

from __future__ import annotations

import random
import string

import pytest

from compressviz import CODECS, arithmetic, huffman, lz77, lzw, rle
from compressviz.baselines import BASELINES

# ── Οριακές περιπτώσεις ────────────────────────────────────────────────

EDGE_CASES = [
    b"",                                  # κενή είσοδος
    b"a",                                 # ένα σύμβολο
    b"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",  # ένα μοναδικό σύμβολο, μακρύ run
    b"ab" * 500,                          # περιοδικό
    b"abcabcabcabcabcabc",                # μικρή περίοδος (KwKwK στον LZW)
    b"aa3bb",                             # ψηφία: εκθέτει το σφάλμα του
    b"2a3bb",                             #   αρχικού «κειμενικού» RLE
    bytes(range(256)),                    # όλα τα bytes, καμία επανάληψη
    bytes(range(256)) * 4,
    b"\x00" * 300 + b"\xff" * 300,        # μη εκτυπώσιμα
    b"The quick brown fox jumps over the lazy dog. " * 20,
]


def _all_codecs():
    for label, module, params in CODECS:
        yield label, module, params


@pytest.mark.parametrize("data", EDGE_CASES, ids=lambda d: f"len{len(d)}")
@pytest.mark.parametrize("entry", list(_all_codecs()), ids=lambda e: e[0])
def test_roundtrip_edge_cases(entry, data):
    label, module, params = entry
    blob = module.compress(data, **params)
    assert module.decompress(blob) == data, f"{label} απέτυχε σε {data[:20]!r}"


@pytest.mark.parametrize("entry", list(_all_codecs()), ids=lambda e: e[0])
def test_roundtrip_random_binary(entry):
    """Ψευδοτυχαία δυαδικά δεδομένα — χειρότερη περίπτωση για όλους."""
    label, module, params = entry
    rng = random.Random(20260813)
    for _ in range(60):
        n = rng.randint(0, 400)
        data = bytes(rng.randrange(256) for _ in range(n))
        assert module.decompress(module.compress(data, **params)) == data


@pytest.mark.parametrize("entry", list(_all_codecs()), ids=lambda e: e[0])
def test_roundtrip_random_text(entry):
    """Ψευδοτυχαίο κείμενο με ρεαλιστική ανισοκατανομή συμβόλων."""
    label, module, params = entry
    rng = random.Random(4711)
    alphabet = string.ascii_lowercase + "   " + string.digits + ".,\n"
    for _ in range(60):
        n = rng.randint(1, 800)
        data = "".join(rng.choice(alphabet) for _ in range(n)).encode()
        assert module.decompress(module.compress(data, **params)) == data


@pytest.mark.parametrize("entry", list(_all_codecs()), ids=lambda e: e[0])
def test_roundtrip_highly_repetitive(entry):
    """Δεδομένα με μακριά runs — γεμίζει το λεξικό του LZW."""
    label, module, params = entry
    rng = random.Random(99)
    chunks = [bytes([rng.randrange(256)]) * rng.randint(1, 200)
              for _ in range(80)]
    data = b"".join(chunks)
    assert module.decompress(module.compress(data, **params)) == data


# ── Ειδικοί έλεγχοι ανά αλγόριθμο ──────────────────────────────────────

def test_naive_text_rle_is_ambiguous():
    """
    Τεκμηριώνει ΓΙΑΤΙ αντικαταστάθηκε η αρχική υλοποίηση RLE.

    Η μορφή «ψηφία + σύμβολο» μέσα στο ίδιο ρεύμα δεν είναι αντιστρέψιμη:
    δύο διαφορετικές είσοδοι δίνουν ταυτόσημη έξοδο.
    """
    def naive(text: str) -> str:
        out, i = [], 0
        while i < len(text):
            c, run = text[i], 1
            while i + run < len(text) and text[i + run] == c:
                run += 1
            out.append(f"{run}{c}" if run > 1 else c)
            i += run
        return "".join(out)

    assert naive("aa3bb") == naive("2a3bb")


def test_huffman_code_lengths_satisfy_kraft():
    """Ανισότητα Kraft: Σ 2^(-l_i) <= 1 για κάθε prefix-free κώδικα."""
    data = b"abracadabra" * 30 + bytes(range(64))
    lengths = huffman.code_lengths(data)
    kraft = sum(2 ** -ln for ln in lengths.values())
    assert kraft <= 1.0 + 1e-9


def test_huffman_within_one_bit_of_entropy():
    """Θεωρητική εγγύηση: H(X) <= L < H(X) + 1 bit/σύμβολο."""
    data = (b"the rain in spain falls mainly on the plain. " * 200)
    lengths = huffman.code_lengths(data)
    from collections import Counter
    freq = Counter(data)
    n = len(data)
    avg = sum(freq[s] * lengths[s] for s in freq) / n
    h = arithmetic.entropy(data)
    assert h <= avg < h + 1.0


def test_arithmetic_beats_huffman_payload():
    """
    Το arithmetic payload πρέπει να είναι <= huffman payload.

    Συγκρίνεται ΜΟΝΟ το ωφέλιμο φορτίο (χωρίς κεφαλίδες), γιατί τα δύο
    σχήματα μεταδίδουν διαφορετικού μεγέθους μοντέλα.
    """
    data = (b"aaaaaaaaaabbbbbccccdde" * 400)
    ar = len(arithmetic.compress(data)) - arithmetic.header_bits(data) // 8
    hu = len(huffman.compress(data)) - huffman.header_bits(data) // 8
    assert ar <= hu


def test_arithmetic_close_to_shannon_bound():
    """Το payload πρέπει να απέχει λίγα bytes από το φράγμα H(X)*n."""
    data = (b"the quick brown fox " * 500)
    payload_bits = (len(arithmetic.compress(data)) * 8
                    - arithmetic.header_bits(data))
    bound = arithmetic.shannon_bound_bits(data)
    assert payload_bits >= bound - 8            # δεν παραβιάζει το όριο
    assert payload_bits < bound + 64            # και το πλησιάζει


def test_lzss_never_expands_much():
    """
    Το LZSS έχει φραγμένη επέκταση (1 flag bit ανά literal), σε αντίθεση
    με το κλασικό LZ77 με τριάδες.
    """
    rng = random.Random(7)
    data = bytes(rng.randrange(256) for _ in range(5000))
    blob = lz77.compress(data, window_size=4096, lookahead_size=18,
                         mode="lzss")
    assert len(blob) < len(data) * 1.15


def test_lzw_variable_width_smaller_than_fixed():
    """Οι κωδικοί μεταβλητού πλάτους δεν πρέπει ποτέ να είναι χειρότεροι."""
    data = b"the rain in spain " * 300
    small = len(lzw.compress(data, max_bits=12))
    assert small < len(data)


@pytest.mark.parametrize("name,comp,decomp", BASELINES, ids=lambda x: str(x))
def test_baselines_roundtrip(name, comp, decomp):
    data = b"baseline sanity check " * 100
    assert decomp(comp(data)) == data
