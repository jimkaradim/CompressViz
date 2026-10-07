"""
baselines.py — Σημεία αναφοράς από την τυπική βιβλιοθήκη

Χωρίς baseline, ένας λόγος συμπίεσης «48,3%» δεν λέει τίποτε στον
αναγνώστη: δεν φαίνεται αν είναι καλό ή κακό αποτέλεσμα. Τα παρακάτω
είναι υλοποιήσεις παραγωγής και ορίζουν το ρεαλιστικό ταβάνι:

    gzip  — DEFLATE = LZ77 (32 KB) + Huffman
    bzip2 — BWT + MTF + Huffman
    lzma  — LZ77 με τεράστιο παράθυρο + range coder

Η σύγκριση είναι διδακτικά χρήσιμη: δείχνει πόσο κερδίζει ο συνδυασμός
λεξικογραφικής και εντροπικής κωδικοποίησης έναντι καθεμιάς χωριστά.
"""

from __future__ import annotations

import bz2
import gzip
import lzma
import zlib


def gzip_compress(data: bytes, level: int = 9) -> bytes:
    return gzip.compress(data, compresslevel=level, mtime=0)


def gzip_decompress(blob: bytes) -> bytes:
    return gzip.decompress(blob)


def bzip2_compress(data: bytes, level: int = 9) -> bytes:
    return bz2.compress(data, compresslevel=level)


def bzip2_decompress(blob: bytes) -> bytes:
    return bz2.decompress(blob)


def lzma_compress(data: bytes) -> bytes:
    return lzma.compress(data, preset=9 | lzma.PRESET_EXTREME)


def lzma_decompress(blob: bytes) -> bytes:
    return lzma.decompress(blob)


def zlib_compress(data: bytes, level: int = 9) -> bytes:
    return zlib.compress(data, level)


def zlib_decompress(blob: bytes) -> bytes:
    return zlib.decompress(blob)


BASELINES = [
    ("gzip -9",  gzip_compress,  gzip_decompress),
    ("bzip2 -9", bzip2_compress, bzip2_decompress),
    ("xz -9e",   lzma_compress,  lzma_decompress),
]
