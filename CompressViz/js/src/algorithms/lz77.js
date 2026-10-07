/**
 * lz77.js — LZ77 (sliding window) και LZSS
 *
 * ΔΙΟΡΘΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ computeLZ77
 * ------------------------------------------
 * 1. Υπάρχει αποκωδικοποιητής.
 * 2. Διορθώνεται σφάλμα πλάτους πεδίου: η αρχική χρέωνε 16 bits ανά
 *    token ως 5 (offset) + 3 (length) + 8 (char), αλλά με lookahead = 8
 *    το μήκος φτάνει την τιμή 8, που απαιτεί 4 bits. Τα πλάτη
 *    υπολογίζονται πλέον από τις παραμέτρους.
 * 3. Το μέγεθος μετριέται από πραγματικό bitstream αντί να εκτιμάται
 *    ως tokens x 16.
 * 4. Προστίθεται LZSS (Storer & Szymanski, 1982): ένα flag bit ανά
 *    token επιτρέπει σκέτο literal αντί για token (0, 0, c). Αυτό
 *    εξαλείφει την επέκταση δεδομένων που παρατηρήθηκε αρχικά.
 *
 * Μορφή αρχείου:
 *     uint8 mode, uint32 W, uint16 L, uint32 N, payload
 */

import { BitReader, BitWriter, bytesToInt, concatBytes, intToBytes } from "./bitio.js";

export const MIN_MATCH = 3;
const MAX_CHAIN = 64;
const HEADER_BYTES = 11;

/** Ευρετήριο θέσεων ανά τριάδα bytes (hash chain, όπως στο zlib). */
class Matcher {
  constructor(data, windowSize) {
    this.data = data;
    this.windowSize = windowSize;
    this.table = new Map();
  }

  key(pos) {
    return this.data[pos] * 65536 + this.data[pos + 1] * 256 + this.data[pos + 2];
  }

  insert(pos) {
    if (pos + MIN_MATCH > this.data.length) return;
    const k = this.key(pos);
    let chain = this.table.get(k);
    if (!chain) { chain = []; this.table.set(k, chain); }
    chain.push(pos);
    if (chain.length > MAX_CHAIN * 4) chain.splice(0, chain.length - MAX_CHAIN);
  }

  find(pos, lookahead) {
    const { data } = this;
    const maxLen = Math.min(lookahead, data.length - pos);
    if (maxLen < MIN_MATCH) return { off: 0, len: 0 };

    const chain = this.table.get(this.key(pos));
    if (!chain) return { off: 0, len: 0 };

    const limit = pos - this.windowSize;
    let bestOff = 0, bestLen = 0;

    for (let ci = chain.length - 1, seen = 0; ci >= 0 && seen < MAX_CHAIN; ci--, seen++) {
      const cand = chain[ci];
      if (cand < limit) break;
      let len = MIN_MATCH;
      while (len < maxLen && data[cand + len] === data[pos + len]) len++;
      if (len > bestLen) {
        bestLen = len;
        bestOff = pos - cand;
        if (bestLen === maxLen) break;
      }
    }
    return { off: bestOff, len: bestLen };
  }
}

export function compress(data, { windowSize = 4096, lookaheadSize = 18, mode = "lzss" } = {}) {
  const offBits = Math.max(1, 32 - Math.clz32(windowSize));
  const lenBits = Math.max(1, 32 - Math.clz32(lookaheadSize));
  const isLzss = mode === "lzss";

  const matcher = new Matcher(data, windowSize);
  const bw = new BitWriter();
  let pos = 0;
  const n = data.length;

  while (pos < n) {
    // Στο κλασικό LZ77 κάθε token κλείνει με literal, άρα η αντιστοίχιση
    // δεν επιτρέπεται να καταναλώσει το τελευταίο byte.
    const cap = isLzss ? lookaheadSize : Math.min(lookaheadSize, n - pos - 1);
    const { off, len } = cap >= MIN_MATCH ? matcher.find(pos, cap) : { off: 0, len: 0 };

    let step;
    if (isLzss && len >= MIN_MATCH) {
      bw.writeBit(1);
      bw.writeBits(off, offBits);
      bw.writeBits(len, lenBits);
      step = len;
    } else if (isLzss) {
      bw.writeBit(0);
      bw.writeBits(data[pos], 8);
      step = 1;
    } else {
      const next = pos + len < n ? data[pos + len] : 0;
      bw.writeBits(off, offBits);
      bw.writeBits(len, lenBits);
      bw.writeBits(next, 8);
      step = len + 1;
    }

    for (let k = pos; k < Math.min(pos + step, n); k++) matcher.insert(k);
    pos += step;
  }

  return concatBytes(
    Uint8Array.from([isLzss ? 1 : 0]),
    intToBytes(windowSize, 4),
    intToBytes(lookaheadSize, 2),
    intToBytes(n, 4),
    bw.finish()
  );
}

export function decompress(blob) {
  const isLzss = blob[0] === 1;
  const windowSize = bytesToInt(blob, 1, 4);
  const lookaheadSize = bytesToInt(blob, 5, 2);
  const n = bytesToInt(blob, 7, 4);

  const offBits = Math.max(1, 32 - Math.clz32(windowSize));
  const lenBits = Math.max(1, 32 - Math.clz32(lookaheadSize));

  const br = new BitReader(blob.subarray(HEADER_BYTES));
  const out = new Uint8Array(n);
  let written = 0;

  while (written < n) {
    if (isLzss) {
      if (br.readBit() === 1) {
        const off = br.readBits(offBits);
        const len = br.readBits(lenBits);
        const start = written - off;
        // Επιτρέπεται να αντιγραφούν bytes που γράφτηκαν στο ίδιο match.
        for (let i = 0; i < len; i++) out[written++] = out[start + i];
      } else {
        out[written++] = br.readBits(8);
      }
    } else {
      const off = br.readBits(offBits);
      const len = br.readBits(lenBits);
      const next = br.readBits(8);
      const start = written - off;
      for (let i = 0; i < len; i++) out[written++] = out[start + i];
      if (written < n) out[written++] = next;
    }
  }
  return out;
}

export function headerBits() { return HEADER_BYTES * 8; }

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

export function trace(data, { windowSize = 64, lookaheadSize = 12, mode = "lzss" } = {}) {
  const offBits = Math.max(1, 32 - Math.clz32(windowSize));
  const lenBits = Math.max(1, 32 - Math.clz32(lookaheadSize));
  const isLzss = mode === "lzss";

  const matcher = new Matcher(data, windowSize);
  const steps = [];
  let pos = 0, bitsSoFar = 0;
  const n = data.length;

  while (pos < n) {
    const cap = isLzss ? lookaheadSize : Math.min(lookaheadSize, n - pos - 1);
    const { off, len } = cap >= MIN_MATCH ? matcher.find(pos, cap) : { off: 0, len: 0 };
    const winStart = Math.max(0, pos - windowSize);

    let token, tokenBits, step;
    if (isLzss && len >= MIN_MATCH) {
      token = `<1|${off},${len}>`;
      tokenBits = 1 + offBits + lenBits;
      step = len;
    } else if (isLzss) {
      token = `<0|'${String.fromCharCode(data[pos])}'>`;
      tokenBits = 1 + 8;
      step = 1;
    } else {
      const next = pos + len < n ? String.fromCharCode(data[pos + len]) : "";
      token = `(${off}, ${len}, '${next}')`;
      tokenBits = offBits + lenBits + 8;
      step = len + 1;
    }
    bitsSoFar += tokenBits;

    steps.push({
      phase: "encode",
      title: `Θέση ${pos}`,
      pos,
      windowStart: winStart,
      windowEnd: pos - 1,
      matchStart: len > 0 ? pos - off : null,
      matchEnd: len > 0 ? pos - off + len - 1 : null,
      lookaheadEnd: Math.min(pos + cap, n) - 1,
      offset: off,
      length: len,
      isMatch: isLzss ? len >= MIN_MATCH : len > 0,
      token,
      tokenBits,
      bitsSoFar,
      desc: isLzss && len < MIN_MATCH
        ? "Καμία ωφέλιμη αντιστοίχιση — εκπομπή literal (9 bits)"
        : `Αντιστοίχιση μήκους ${len} σε απόσταση ${off}`,
    });

    for (let k = pos; k < Math.min(pos + step, n); k++) matcher.insert(k);
    pos += step;
  }

  const blob = compress(data, { windowSize, lookaheadSize, mode });
  return {
    steps, blob,
    totalBits: blob.length * 8,
    headerBits: headerBits(),
    originalBits: data.length * 8,
    ratio: data.length ? (blob.length * 8) / (data.length * 8) * 100 : 0,
    params: { windowSize, lookaheadSize, mode, offBits, lenBits },
  };
}
