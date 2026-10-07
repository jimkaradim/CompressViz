/**
 * huffman.js — Canonical Huffman Coding
 *
 * ΔΙΟΡΘΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ computeHuffman
 * --------------------------------------------
 * 1. Υπάρχει αποκωδικοποιητής.
 * 2. Η έξοδος είναι πραγματικά bytes. Η αρχική παρήγαγε συμβολοσειρά
 *    από '0'/'1' και μετρούσε το μήκος της· αυτό αγνοεί το padding.
 * 3. Μετράται το κόστος της κεφαλίδας. Ο αποκωδικοποιητής δεν γνωρίζει
 *    το δέντρο, άρα αυτό πρέπει να μεταδοθεί. Αγνοώντας το, η σύγκριση
 *    με τον LZW (που δεν χρειάζεται κεφαλίδα) ήταν άνιση.
 * 4. Η ουρά προτεραιότητας σπάει τις ισοβαθμίες ντετερμινιστικά, ώστε
 *    το αποτέλεσμα να είναι αναπαραγώγιμο και ίδιο με την Python.
 *
 * Χρησιμοποιείται κανονικός (canonical) κώδικας: μεταδίδονται μόνο τα
 * μήκη κωδικών, όπως στο DEFLATE (RFC 1951).
 *
 * Μορφή αρχείου:
 *     uint32 N, uint16 K, K x {uint8 σύμβολο, uint8 μήκος}, payload
 */

import { BitReader, BitWriter, bytesToInt, concatBytes, intToBytes } from "./bitio.js";

/** Υπολογισμός μηκών κωδικών με τον κλασικό αλγόριθμο Huffman. */
export function codeLengths(data) {
  const freq = new Map();
  for (const b of data) freq.set(b, (freq.get(b) || 0) + 1);
  if (freq.size === 0) return new Map();
  if (freq.size === 1) return new Map([[[...freq.keys()][0], 1]]);

  const lengths = new Map([...freq.keys()].map(k => [k, 0]));

  // Κόμβος: { freq, order, group: [σύμβολα] }. Το πεδίο order σπάει τις
  // ισοβαθμίες ώστε το δέντρο να μην εξαρτάται από τη σειρά εισαγωγής.
  let order = 0;
  const heap = [...freq.keys()].sort((a, b) => a - b)
    .map(sym => ({ freq: freq.get(sym), order: order++, group: [sym] }));

  const popMin = () => {
    let bi = 0;
    for (let i = 1; i < heap.length; i++) {
      if (heap[i].freq < heap[bi].freq ||
         (heap[i].freq === heap[bi].freq && heap[i].order < heap[bi].order)) bi = i;
    }
    return heap.splice(bi, 1)[0];
  };

  while (heap.length > 1) {
    const a = popMin();
    const b = popMin();
    for (const s of a.group) lengths.set(s, lengths.get(s) + 1);
    for (const s of b.group) lengths.set(s, lengths.get(s) + 1);
    heap.push({ freq: a.freq + b.freq, order: order++, group: [...a.group, ...b.group] });
  }
  return lengths;
}

/** Μετατροπή μηκών σε canonical κωδικούς: Map<σύμβολο, {code, len}>. */
export function canonicalCodes(lengths) {
  const entries = [...lengths.entries()].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const codes = new Map();
  let code = 0;
  let prevLen = null;
  for (const [sym, len] of entries) {
    if (prevLen === null) prevLen = len;
    else if (len > prevLen) { code <<= (len - prevLen); prevLen = len; }
    codes.set(sym, { code, len });
    code++;
  }
  return codes;
}

export function headerBits(data) {
  const k = new Set(data).size;
  return (4 + 2 + 2 * k) * 8;
}

export function compress(data) {
  if (data.length === 0) return concatBytes(intToBytes(0, 4), intToBytes(0, 2));

  const lengths = codeLengths(data);
  const codes = canonicalCodes(lengths);

  const bw = new BitWriter();
  for (const b of data) {
    const { code, len } = codes.get(b);
    bw.writeBits(code, len);
  }

  const syms = [...lengths.keys()].sort((a, b) => a - b);
  const table = new Uint8Array(syms.length * 2);
  syms.forEach((s, i) => { table[i * 2] = s; table[i * 2 + 1] = lengths.get(s); });

  return concatBytes(
    intToBytes(data.length, 4),
    intToBytes(syms.length === 256 ? 0 : syms.length, 2),
    table,
    bw.finish()
  );
}

export function decompress(blob) {
  const n = bytesToInt(blob, 0, 4);
  if (n === 0) return new Uint8Array(0);
  let k = bytesToInt(blob, 4, 2);
  if (k === 0) k = 256;

  const lengths = new Map();
  let pos = 6;
  for (let i = 0; i < k; i++) { lengths.set(blob[pos], blob[pos + 1]); pos += 2; }

  const codes = canonicalCodes(lengths);
  const lookup = new Map();
  for (const [sym, { code, len }] of codes) lookup.set(`${len}:${code}`, sym);

  const br = new BitReader(blob.subarray(pos));
  const out = new Uint8Array(n);
  let written = 0, code = 0, len = 0;

  while (written < n) {
    code = (code << 1) | br.readBit();
    len++;
    const sym = lookup.get(`${len}:${code}`);
    if (sym !== undefined) { out[written++] = sym; code = 0; len = 0; }
  }
  return out;
}

/** Shannon entropy σε bits ανά σύμβολο. */
export function entropy(data) {
  if (data.length === 0) return 0;
  const freq = new Map();
  for (const b of data) freq.set(b, (freq.get(b) || 0) + 1);
  let h = 0;
  for (const f of freq.values()) { const p = f / data.length; h -= p * Math.log2(p); }
  return h;
}

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

export function trace(data) {
  const steps = [];
  const freq = new Map();
  for (const b of data) freq.set(b, (freq.get(b) || 0) + 1);

  const freqTable = [...freq.entries()]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .map(([sym, f]) => ({
      char: String.fromCharCode(sym), sym, freq: f, prob: f / data.length,
    }));

  steps.push({
    phase: "frequency",
    title: "Φάση 1 — Συχνότητες συμβόλων",
    desc: "Καταμέτρηση εμφανίσεων κάθε συμβόλου στην είσοδο",
    freqTable,
    entropy: entropy(data),
  });

  // Αναπαραγωγή των συγχωνεύσεων για την οπτικοποίηση του δέντρου
  let order = 0;
  let heap = [...freq.keys()].sort((a, b) => a - b)
    .map(sym => ({ freq: freq.get(sym), order: order++, label: String.fromCharCode(sym), group: [sym] }));

  const popMin = () => {
    let bi = 0;
    for (let i = 1; i < heap.length; i++) {
      if (heap[i].freq < heap[bi].freq ||
         (heap[i].freq === heap[bi].freq && heap[i].order < heap[bi].order)) bi = i;
    }
    return heap.splice(bi, 1)[0];
  };

  let mergeNo = 0;
  while (heap.length > 1) {
    const a = popMin();
    const b = popMin();
    const merged = {
      freq: a.freq + b.freq, order: order++,
      label: `(${a.label}${b.label})`, group: [...a.group, ...b.group],
    };
    heap.push(merged);
    steps.push({
      phase: "tree",
      title: `Φάση 2 — Συγχώνευση ${++mergeNo}`,
      desc: `Ενώνονται οι δύο κόμβοι με τις μικρότερες συχνότητες`,
      left: { label: a.label, freq: a.freq },
      right: { label: b.label, freq: b.freq },
      merged: { label: merged.label, freq: merged.freq },
      heapState: heap.map(h => ({ label: h.label, freq: h.freq }))
                     .sort((x, y) => x.freq - y.freq),
    });
  }

  const lengths = codeLengths(data);
  const codes = canonicalCodes(lengths);
  const codeTable = [...codes.entries()]
    .sort((a, b) => a[1].len - b[1].len || a[0] - b[0])
    .map(([sym, { code, len }]) => ({
      char: String.fromCharCode(sym), sym, len,
      bits: code.toString(2).padStart(len, "0"),
      freq: freq.get(sym),
    }));

  const avgLen = [...freq.entries()]
    .reduce((acc, [sym, f]) => acc + f * lengths.get(sym), 0) / data.length;

  steps.push({
    phase: "codes",
    title: "Φάση 3 — Πίνακας κωδικών (canonical)",
    desc: "Τα μήκη κωδικών είναι αυτά που μεταδίδονται στην κεφαλίδα",
    codeTable,
    avgCodeLength: avgLen,
    entropy: entropy(data),
  });

  const blob = compress(data);
  const hdr = headerBits(data);

  steps.push({
    phase: "result",
    title: "Φάση 4 — Αποτέλεσμα",
    desc: "Το τελικό μέγεθος περιλαμβάνει την κεφαλίδα με τα μήκη κωδικών",
    headerBits: hdr,
    payloadBits: blob.length * 8 - hdr,
    totalBits: blob.length * 8,
    originalBits: data.length * 8,
    avgCodeLength: avgLen,
    entropy: entropy(data),
  });

  return {
    steps, blob,
    totalBits: blob.length * 8,
    headerBits: hdr,
    originalBits: data.length * 8,
    ratio: data.length ? (blob.length * 8) / (data.length * 8) * 100 : 0,
  };
}
