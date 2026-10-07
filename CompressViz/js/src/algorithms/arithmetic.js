/**
 * arithmetic.js — Arithmetic Coding (πραγματική υλοποίηση)
 *
 * Η ΣΗΜΑΝΤΙΚΟΤΕΡΗ ΔΙΟΡΘΩΣΗ
 * -------------------------
 * Η αρχική computeArithmetic ΔΕΝ κωδικοποιούσε: υπολόγιζε το μέγεθος ως
 * Math.ceil(entropy * total) + 2, δηλαδή το ίδιο το φράγμα Shannon. Έτσι
 * το συμπέρασμα «το Arithmetic Coding πλησιάζει το θεωρητικό όριο» ήταν
 * κυκλικό: το αποτέλεσμα είχε οριστεί ίσο με το όριο.
 *
 * Επιπλέον, η κωδικοποίηση σταματούσε στους 25 χαρακτήρες επειδή τα
 * διαστήματα κινητής υποδιαστολής κατέρρεαν. Αυτό ακριβώς λύνει η
 * κλιμάκωση (rescaling): εδώ υλοποιείται πλήρης ακέραιος κωδικοποιητής
 * κατά Witten-Neal-Cleary, χωρίς όριο μήκους.
 *
 * Οι τρεις περιπτώσεις κλιμάκωσης:
 *     E1: high < HALF                      -> εκπομπή 0
 *     E2: low >= HALF                      -> εκπομπή 1
 *     E3: QUARTER <= low, high < 3*QUARTER  -> underflow, μετρητής pending
 *
 * ΑΡΙΘΜΗΤΙΚΗ ΑΚΡΙΒΕΙΑ ΣΤΗ JAVASCRIPT: χρησιμοποιούνται 24 bits (όχι 32)
 * ώστε τα ενδιάμεσα γινόμενα rng * total να μένουν κάτω από 2^53, το
 * όριο ακέραιας ακρίβειας των IEEE 754 doubles. Η Python υλοποίηση
 * χρησιμοποιεί τα ίδια 24 bits, ώστε οι δύο να παράγουν ταυτόσημα bytes.
 *
 * Μορφή αρχείου:
 *     uint32 N, uint16 K, K x {uint8 σύμβολο, uint32 συχνότητα}, payload
 */

import { BitReader, BitWriter, bytesToInt, concatBytes, intToBytes } from "./bitio.js";

const NBITS = 24;
const FULL = 1 << NBITS;          // 16.777.216
const HALF = FULL >>> 1;
const QUARTER = FULL >>> 2;
const THREE_Q = 3 * QUARTER;
const MASK = FULL - 1;

/** Στατικό μοντέλο αθροιστικών συχνοτήτων. */
function buildModel(freq) {
  const symbols = [...freq.keys()].sort((a, b) => a - b);
  const cum = new Map();
  let running = 0;
  for (const sym of symbols) {
    cum.set(sym, { low: running, high: running + freq.get(sym) });
    running += freq.get(sym);
  }
  return { symbols, cum, total: running };
}

function symbolFor(model, target) {
  for (const sym of model.symbols) {
    const { low, high } = model.cum.get(sym);
    if (target >= low && target < high) return sym;
  }
  throw new Error("Το target είναι εκτός εύρους μοντέλου");
}

function countFreq(data) {
  const freq = new Map();
  for (const b of data) freq.set(b, (freq.get(b) || 0) + 1);
  return freq;
}

export function compress(data) {
  if (data.length === 0) return concatBytes(intToBytes(0, 4), intToBytes(0, 2));

  const freq = countFreq(data);
  const model = buildModel(freq);

  const syms = [...freq.keys()].sort((a, b) => a - b);
  const table = new Uint8Array(syms.length * 5);
  syms.forEach((s, i) => {
    table[i * 5] = s;
    table.set(intToBytes(freq.get(s), 4), i * 5 + 1);
  });

  const bw = new BitWriter();
  let low = 0, high = MASK, pending = 0;

  const emit = (bit) => {
    bw.writeBit(bit);
    for (let i = 0; i < pending; i++) bw.writeBit(1 - bit);
    pending = 0;
  };

  for (const byte of data) {
    const { low: cumLo, high: cumHi } = model.cum.get(byte);
    const rng = high - low + 1;
    high = low + Math.floor((rng * cumHi) / model.total) - 1;
    low = low + Math.floor((rng * cumLo) / model.total);

    for (;;) {
      if (high < HALF) emit(0);
      else if (low >= HALF) { emit(1); low -= HALF; high -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { pending++; low -= QUARTER; high -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
    }
  }

  pending++;
  emit(low < QUARTER ? 0 : 1);

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

  const freq = new Map();
  let pos = 6;
  for (let i = 0; i < k; i++) {
    freq.set(blob[pos], bytesToInt(blob, pos + 1, 4));
    pos += 5;
  }

  const model = buildModel(freq);
  const padded = concatBytes(blob.subarray(pos), new Uint8Array(8));
  const br = new BitReader(padded);

  let low = 0, high = MASK;
  let value = br.readBits(NBITS);
  const out = new Uint8Array(n);

  for (let i = 0; i < n; i++) {
    const rng = high - low + 1;
    const target = Math.floor(((value - low + 1) * model.total - 1) / rng);
    const sym = symbolFor(model, target);
    out[i] = sym;

    const { low: cumLo, high: cumHi } = model.cum.get(sym);
    high = low + Math.floor((rng * cumHi) / model.total) - 1;
    low = low + Math.floor((rng * cumLo) / model.total);

    for (;;) {
      if (high < HALF) { /* E1 */ }
      else if (low >= HALF) { low -= HALF; high -= HALF; value -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { low -= QUARTER; high -= QUARTER; value -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
      value = ((value * 2) + br.readBit()) & MASK;
    }
  }
  return out;
}

export function headerBits(data) {
  const k = new Set(data).size;
  return (4 + 2 + 5 * k) * 8;
}

export function entropy(data) {
  if (data.length === 0) return 0;
  let h = 0;
  for (const f of countFreq(data).values()) {
    const p = f / data.length;
    h -= p * Math.log2(p);
  }
  return h;
}

/** Θεωρητικό κάτω όριο H(X) * n, ΧΩΡΙΣ το κόστος του μοντέλου. */
export function shannonBoundBits(data) {
  return entropy(data) * data.length;
}

// ── Ίχνος για την οπτικοποίηση ──────────────────────────────────────

/**
 * Παράγει βήματα οπτικοποίησης.
 *
 * Η οπτικοποίηση δείχνει το *λογικό* διάστημα [low, high) σε κινητή
 * υποδιαστολή, γιατί αυτό είναι που κατανοεί ο χρήστης. Παράλληλα
 * καταγράφει το ακέραιο διάστημα και τα γεγονότα κλιμάκωσης, ώστε να
 * φαίνεται *πώς* αποφεύγεται η κατάρρευση ακρίβειας — που ήταν ακριβώς
 * ο λόγος που η αρχική έκδοση σταματούσε στους 25 χαρακτήρες.
 */
export function trace(data, { maxSteps = 60 } = {}) {
  const steps = [];
  if (data.length === 0) return { steps, blob: compress(data), totalBits: 0, headerBits: 0, originalBits: 0, ratio: 0 };

  const freq = countFreq(data);
  const model = buildModel(freq);

  const probTable = model.symbols.map(sym => ({
    char: String.fromCharCode(sym), sym,
    freq: freq.get(sym),
    prob: freq.get(sym) / data.length,
    low: model.cum.get(sym).low / model.total,
    high: model.cum.get(sym).high / model.total,
  }));

  steps.push({
    phase: "probabilities",
    title: "Φάση 1 — Διαμέριση του [0, 1)",
    desc: "Κάθε σύμβολο καταλαμβάνει υποδιάστημα ανάλογο της πιθανότητάς του",
    probTable,
    entropy: entropy(data),
  });

  let low = 0, high = MASK, pending = 0, emitted = 0;
  const limit = Math.min(data.length, maxSteps);

  for (let i = 0; i < limit; i++) {
    const byte = data[i];
    const { low: cumLo, high: cumHi } = model.cum.get(byte);
    const prevLow = low, prevHigh = high;
    const rng = high - low + 1;
    high = low + Math.floor((rng * cumHi) / model.total) - 1;
    low = low + Math.floor((rng * cumLo) / model.total);

    const rescalings = [];
    for (;;) {
      if (high < HALF) { rescalings.push("E1 (εκπομπή 0)"); emitted += 1 + pending; pending = 0; }
      else if (low >= HALF) { rescalings.push("E2 (εκπομπή 1)"); emitted += 1 + pending; pending = 0; low -= HALF; high -= HALF; }
      else if (low >= QUARTER && high < THREE_Q) { rescalings.push("E3 (underflow)"); pending++; low -= QUARTER; high -= QUARTER; }
      else break;
      low = (low * 2) & MASK;
      high = ((high * 2) + 1) & MASK;
    }

    steps.push({
      phase: "encode",
      title: `Θέση ${i + 1}: '${String.fromCharCode(byte) === " " ? "␣" : String.fromCharCode(byte)}'`,
      char: String.fromCharCode(byte),
      pos: i,
      symbolLow: cumLo / model.total,
      symbolHigh: cumHi / model.total,
      prevIntervalInt: { low: prevLow, high: prevHigh },
      intervalInt: { low, high },
      normalizedLow: low / FULL,
      normalizedHigh: (high + 1) / FULL,
      rescalings,
      pendingBits: pending,
      bitsEmitted: emitted,
      desc: rescalings.length
        ? `Κλιμάκωση: ${rescalings.join(", ")} — το διάστημα ξαναμεγαλώνει`
        : "Το διάστημα στενεύει χωρίς να χρειαστεί κλιμάκωση",
    });
  }

  const blob = compress(data);
  const hdr = headerBits(data);
  const bound = shannonBoundBits(data);

  steps.push({
    phase: "result",
    title: "Φάση 3 — Αποτέλεσμα",
    desc: "Το φορτίο συγκρίνεται με το φράγμα Shannon· η υπέρβαση είναι λίγα bits",
    headerBits: hdr,
    payloadBits: blob.length * 8 - hdr,
    totalBits: blob.length * 8,
    originalBits: data.length * 8,
    shannonBoundBits: bound,
    overheadVsBound: blob.length * 8 - hdr - bound,
    entropy: entropy(data),
    visualizedSteps: limit,
    totalSymbols: data.length,
  });

  return {
    steps, blob,
    totalBits: blob.length * 8,
    headerBits: hdr,
    originalBits: data.length * 8,
    ratio: (blob.length * 8) / (data.length * 8) * 100,
  };
}
