/**
 * lzw.js — Lempel-Ziv-Welch
 *
 * ΔΙΟΡΘΩΣΕΙΣ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ computeLZW
 * -----------------------------------------
 * 1. Υπάρχει αποκωδικοποιητής, μαζί με την ειδική περίπτωση «KwKwK»:
 *    ο κωδικός που λαμβάνεται μπορεί να μην υπάρχει ακόμη στο λεξικό
 *    του αποκωδικοποιητή, επειδή αυτός βρίσκεται ένα βήμα πίσω.
 * 2. Κωδικοί μεταβλητού πλάτους (9 -> maxBits) αντί για σταθερά 12.
 *    Έτσι οι πρώτες εκατοντάδες εκπομπές δεν σπαταλούν bits, όπως
 *    ακριβώς κάνουν το GIF και το Unix compress.
 * 3. Πραγματικό bit packing αντί για εκτίμηση codes.length * 12.
 *
 * ΠΡΟΣΟΧΗ ΣΤΟΝ ΣΥΓΧΡΟΝΙΣΜΟ ΠΛΑΤΟΥΣ: ο κωδικοποιητής αυξάνει το πλάτος
 * όταν nextCode === 2^width, ενώ ο αποκωδικοποιητής όταν
 * nextCode + 1 === 2^width, ακριβώς λόγω της καθυστέρησης ενός βήματος.
 *
 * Μορφή αρχείου:
 *     uint8 maxBits, uint32 N, payload
 */

import { BitReader, BitWriter, bytesToInt, concatBytes, intToBytes } from "./bitio.js";

const HEADER_BYTES = 5;

export function compress(data, { maxBits = 12 } = {}) {
  const header = concatBytes(Uint8Array.from([maxBits]), intToBytes(data.length, 4));
  if (data.length === 0) return header;

  const maxDict = 1 << maxBits;
  const table = new Map();
  for (let i = 0; i < 256; i++) table.set(String.fromCharCode(i), i);

  let nextCode = 256;
  let width = 9;
  const bw = new BitWriter();
  let w = "";

  for (const byte of data) {
    const c = String.fromCharCode(byte);
    const wc = w + c;
    if (table.has(wc)) { w = wc; continue; }

    bw.writeBits(table.get(w), width);

    if (nextCode < maxDict) {
      table.set(wc, nextCode);
      nextCode++;
      if (nextCode === (1 << width) && width < maxBits) width++;
    }
    w = c;
  }
  if (w !== "") bw.writeBits(table.get(w), width);

  return concatBytes(header, bw.finish());
}

export function decompress(blob) {
  const maxBits = blob[0];
  const n = bytesToInt(blob, 1, 4);
  if (n === 0) return new Uint8Array(0);

  const maxDict = 1 << maxBits;
  const table = new Map();
  for (let i = 0; i < 256; i++) table.set(i, [i]);

  let nextCode = 256;
  let width = 9;
  const br = new BitReader(blob.subarray(HEADER_BYTES));
  const out = [];

  let w = table.get(br.readBits(width));
  out.push(...w);

  while (out.length < n) {
    const code = br.readBits(width);
    let entry;
    if (table.has(code)) entry = table.get(code);
    else if (code === nextCode) entry = [...w, w[0]];      // περίπτωση KwKwK
    else throw new Error(`Μη έγκυρος κωδικός LZW: ${code}`);

    out.push(...entry);

    if (nextCode < maxDict) {
      table.set(nextCode, [...w, entry[0]]);
      nextCode++;
      // Ο αποκωδικοποιητής είναι ένα βήμα πίσω -> +1
      if (nextCode + 1 === (1 << width) && width < maxBits) width++;
    }
    w = entry;
  }
  return Uint8Array.from(out.slice(0, n));
}

export function headerBits() { return HEADER_BYTES * 8; }

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

export function trace(data, { maxBits = 12 } = {}) {
  const maxDict = 1 << maxBits;
  const table = new Map();
  for (let i = 0; i < 256; i++) table.set(String.fromCharCode(i), i);

  let nextCode = 256;
  let width = 9;
  let w = "";
  let bitsSoFar = 0;
  const steps = [];
  const newEntries = [];

  data.forEach((byte, i) => {
    const c = String.fromCharCode(byte);
    const wc = w + c;

    if (table.has(wc)) {
      steps.push({
        phase: "extend",
        title: `Θέση ${i}: '${c}'`,
        char: c, pos: i, buffer: wc,
        emitted: null,
        desc: `Η ακολουθία "${wc}" υπάρχει ήδη — επέκταση του buffer`,
        width, dictSize: nextCode, bitsSoFar,
      });
      w = wc;
      return;
    }

    const emittedCode = table.get(w);
    bitsSoFar += width;
    let added = null;

    if (nextCode < maxDict) {
      table.set(wc, nextCode);
      added = { seq: wc, code: nextCode };
      newEntries.push(added);
      nextCode++;
      if (nextCode === (1 << width) && width < maxBits) width++;
    }

    steps.push({
      phase: "emit",
      title: `Θέση ${i}: '${c}'`,
      char: c, pos: i, buffer: w,
      emitted: { seq: w, code: emittedCode, bits: width },
      added,
      desc: added
        ? `"${wc}" δεν υπάρχει — εκπομπή ${emittedCode}, προσθήκη "${wc}" ως ${added.code}`
        : `"${wc}" δεν υπάρχει — εκπομπή ${emittedCode} (λεξικό γεμάτο)`,
      width, dictSize: nextCode, bitsSoFar,
      recentEntries: newEntries.slice(-8),
    });

    w = c;
  });

  if (w !== "") {
    bitsSoFar += width;
    steps.push({
      phase: "flush",
      title: "Τελική εκπομπή",
      emitted: { seq: w, code: table.get(w), bits: width },
      desc: "Εκπομπή του υπολοίπου του buffer",
      width, dictSize: nextCode, bitsSoFar,
    });
  }

  const blob = compress(data, { maxBits });
  return {
    steps, blob,
    totalBits: blob.length * 8,
    headerBits: headerBits(),
    originalBits: data.length * 8,
    ratio: data.length ? (blob.length * 8) / (data.length * 8) * 100 : 0,
  };
}
