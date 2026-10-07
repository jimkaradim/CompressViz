"""
CompressViz — υλοποιήσεις αλγορίθμων lossless συμπίεσης.

Κάθε άρθρωμα εκθέτει την ίδια διεπαφή:

    compress(data: bytes, **params) -> bytes
    decompress(blob: bytes)         -> bytes
    header_bits(data: bytes, **params) -> int

Η ιδιότητα που πρέπει να ισχύει για κάθε codec και κάθε είσοδο είναι

    decompress(compress(x)) == x

και ελέγχεται αυτόματα από το tests/test_roundtrip.py.
"""

from . import adaptive, arithmetic, baselines, huffman, lz77, lzw, rle, trace

__all__ = ["rle", "huffman", "lz77", "lzw", "arithmetic", "adaptive",
           "baselines", "trace", "CODECS"]

__version__ = "2.0.0"


# Το μητρώο που χρησιμοποιεί το benchmark. Κάθε εγγραφή είναι
# (ετικέτα, άρθρωμα, παράμετροι κωδικοποίησης).
CODECS = [
    ("RLE (pairs)",     rle,        {"variant": "pairs"}),
    ("RLE (PackBits)",  rle,        {"variant": "packbits"}),
    ("Huffman",         huffman,    {}),
    ("LZ77 (W=4K)",     lz77,       {"window_size": 4096,
                                     "lookahead_size": 18,
                                     "mode": "lz77"}),
    ("LZSS (W=4K)",     lz77,       {"window_size": 4096,
                                     "lookahead_size": 18,
                                     "mode": "lzss"}),
    ("LZW (12-bit)",    lzw,        {"max_bits": 12}),
    ("LZW (16-bit)",    lzw,        {"max_bits": 16}),
    ("Arithmetic",      arithmetic, {}),
    ("Adaptive AC",     adaptive,   {}),
]
