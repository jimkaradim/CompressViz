"""Checks that invalid parameters and visibly truncated streams are rejected."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compressviz import adaptive, arithmetic, huffman, lz77, lzw, rle


def must_fail(label, operation) -> None:
    try:
        operation()
    except (ValueError, EOFError):
        return
    raise AssertionError(f"{label} should have rejected invalid input")


def main() -> None:
    invalid = [
        ("empty RLE", lambda: rle.decompress(b"")),
        ("unknown RLE tag", lambda: rle.decompress(b"\x02")),
        ("zero RLE run", lambda: rle.decompress(b"\x00\x00A")),
        ("truncated PackBits literal", lambda: rle.decompress(b"\x01\x03A")),
        ("truncated PackBits repeat", lambda: rle.decompress(b"\x01\xff")),
        ("truncated Huffman header", lambda: huffman.decompress(b"\x00")),
        ("truncated arithmetic header", lambda: arithmetic.decompress(b"\x00")),
        ("truncated LZ header", lambda: lz77.decompress(b"\x01")),
        ("truncated LZW header", lambda: lzw.decompress(b"\x0c")),
        ("truncated adaptive header", lambda: adaptive.decompress(b"\x00")),
        ("bad LZ mode", lambda: lz77.compress(b"x", mode="bad")),
        ("zero LZ window", lambda: lz77.compress(b"x", window_size=0)),
        ("zero LZ lookahead", lambda: lz77.compress(b"x", lookahead_size=0)),
        ("small LZW width", lambda: lzw.compress(b"x", max_bits=8)),
        ("large LZW width", lambda: lzw.compress(b"x", max_bits=17)),
        ("non-integer LZW width", lambda: lzw.compress(b"x", max_bits=12.5)),
        ("zero adaptive increment", lambda: adaptive.compress(b"x", increment=0)),
        ("non-integer adaptive increment", lambda: adaptive.compress(b"x", increment=1.5)),
        ("oversized static arithmetic input",
         lambda: arithmetic.compress(b"x" * arithmetic.QUARTER)),
    ]
    for label, operation in invalid:
        must_fail(label, operation)
    print(f"Invalid-input checks passed: {len(invalid)}")


if __name__ == "__main__":
    main()
