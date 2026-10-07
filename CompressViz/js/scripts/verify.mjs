#!/usr/bin/env node
/**
 * verify.mjs — Έλεγχοι ορθότητας για τις JavaScript υλοποιήσεις
 *
 * Ισοδύναμο του run_tests.py. Ελέγχει την ιδιότητα
 *
 *     decompress(compress(x)) === x
 *
 * σε οριακές περιπτώσεις, ψευδοτυχαία δυαδικά δεδομένα, ψευδοτυχαίο
 * κείμενο και δεδομένα με μακριά runs, με σταθερό seed ώστε τα
 * αποτελέσματα να είναι αναπαραγώγιμα.
 *
 *     node scripts/verify.mjs
 */

import { ALGORITHMS, arithmetic, huffman, lz77 } from "../src/algorithms/index.js";

let passed = 0;
const failed = [];

function check(name, ok) {
  if (ok) passed++;
  else { failed.push(name); console.log(`  ✗ ${name}`); }
}

/** Γεννήτρια ψευδοτυχαίων με σταθερό seed (mulberry32). */
function rng(seed) {
  return function () {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const enc = new TextEncoder();

const EDGE_CASES = [
  enc.encode(""),
  enc.encode("a"),
  enc.encode("a".repeat(32)),
  enc.encode("ab".repeat(500)),
  enc.encode("abcabcabcabcabcabc"),
  enc.encode("aa3bb"),
  enc.encode("2a3bb"),
  Uint8Array.from({ length: 256 }, (_, i) => i),
  Uint8Array.from({ length: 1024 }, (_, i) => i % 256),
  Uint8Array.from({ length: 600 }, (_, i) => (i < 300 ? 0 : 255)),
  enc.encode("The quick brown fox jumps over the lazy dog. ".repeat(20)),
];

function equal(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

function testRoundTrips() {
  console.log("\n[1] Round-trip: decompress(compress(x)) === x");
  for (const [id, meta] of Object.entries(ALGORITHMS)) {
    const { module, params } = meta;
    let ok = true;

    for (const data of EDGE_CASES) {
      try {
        if (!equal(module.decompress(module.compress(data, params)), data)) {
          ok = false;
          console.log(`      διαφορά σε μήκος ${data.length}`);
        }
      } catch (e) { ok = false; console.log(`      σφάλμα: ${e.message}`); }
    }

    const r = rng(20260813);
    for (let t = 0; t < 40; t++) {
      const n = Math.floor(r() * 400);
      const data = Uint8Array.from({ length: n }, () => Math.floor(r() * 256));
      try { if (!equal(module.decompress(module.compress(data, params)), data)) ok = false; }
      catch { ok = false; }
    }

    const alphabet = "abcdefghijklmnopqrstuvwxyz   0123456789.,\n";
    for (let t = 0; t < 40; t++) {
      const n = 1 + Math.floor(r() * 800);
      let s = "";
      for (let i = 0; i < n; i++) s += alphabet[Math.floor(r() * alphabet.length)];
      const data = enc.encode(s);
      try { if (!equal(module.decompress(module.compress(data, params)), data)) ok = false; }
      catch { ok = false; }
    }

    const chunks = [];
    for (let t = 0; t < 60; t++) {
      const b = Math.floor(r() * 256);
      const len = 1 + Math.floor(r() * 200);
      for (let i = 0; i < len; i++) chunks.push(b);
    }
    const rep = Uint8Array.from(chunks);
    try { if (!equal(module.decompress(module.compress(rep, params)), rep)) ok = false; }
    catch { ok = false; }

    console.log(`  ${ok ? "✓" : "✗"} ${meta.full}`);
    check(`roundtrip ${id}`, ok);
  }
}

function testNaiveRleAmbiguous() {
  console.log("\n[2] Τεκμηρίωση σφάλματος αρχικού RLE");
  const naive = (text) => {
    let out = "", i = 0;
    while (i < text.length) {
      const c = text[i]; let run = 1;
      while (i + run < text.length && text[i + run] === c) run++;
      out += run > 1 ? `${run}${c}` : c;
      i += run;
    }
    return out;
  };
  const same = naive("aa3bb") === naive("2a3bb");
  console.log(`  ${same ? "✓" : "✗"} 'aa3bb' και '2a3bb' -> '${naive("aa3bb")}' (μη αντιστρέψιμο)`);
  check("naive RLE ambiguity", same);
}

function testHuffmanProperties() {
  console.log("\n[3] Θεωρητικές ιδιότητες Huffman");
  const data = enc.encode("abracadabra".repeat(30) + "xyzwvu".repeat(5));
  const lengths = huffman.codeLengths(data);
  let kraft = 0;
  for (const l of lengths.values()) kraft += Math.pow(2, -l);
  console.log(`  ${kraft <= 1 + 1e-9 ? "✓" : "✗"} Ανισότητα Kraft: Σ2^-l = ${kraft.toFixed(6)} ≤ 1`);
  check("kraft", kraft <= 1 + 1e-9);

  const d2 = enc.encode("the rain in spain falls mainly on the plain. ".repeat(200));
  const len2 = huffman.codeLengths(d2);
  const freq = new Map();
  for (const b of d2) freq.set(b, (freq.get(b) || 0) + 1);
  let total = 0;
  for (const [s, f] of freq) total += f * len2.get(s);
  const avg = total / d2.length;
  const h = huffman.entropy(d2);
  const ok = h <= avg && avg < h + 1;
  console.log(`  ${ok ? "✓" : "✗"} H = ${h.toFixed(4)} ≤ L = ${avg.toFixed(4)} < H+1`);
  check("huffman within 1 bit", ok);
}

function testArithmeticProperties() {
  console.log("\n[4] Ιδιότητες Arithmetic Coding");
  const d1 = enc.encode("aaaaaaaaaabbbbbccccdde".repeat(400));
  const ar = arithmetic.compress(d1).length * 8 - arithmetic.headerBits(d1);
  const hu = huffman.compress(d1).length * 8 - huffman.headerBits(d1);
  console.log(`  ${ar <= hu ? "✓" : "✗"} payload: arithmetic ${ar} ≤ huffman ${hu} bits`);
  check("arith <= huffman", ar <= hu);

  const d2 = enc.encode("the quick brown fox ".repeat(500));
  const payload = arithmetic.compress(d2).length * 8 - arithmetic.headerBits(d2);
  const bound = arithmetic.shannonBoundBits(d2);
  const ok = payload >= bound - 8 && payload < bound + 64;
  console.log(`  ${ok ? "✓" : "✗"} payload ${payload} bits vs φράγμα ${bound.toFixed(1)} (${(payload - bound >= 0 ? "+" : "") + (payload - bound).toFixed(1)})`);
  check("arith near bound", ok);
}

function testLzssExpansion() {
  console.log("\n[5] Φραγμένη επέκταση LZSS σε ασυμπίεστα δεδομένα");
  const r = rng(7);
  const data = Uint8Array.from({ length: 5000 }, () => Math.floor(r() * 256));
  const a = lz77.compress(data, { windowSize: 4096, lookaheadSize: 18, mode: "lzss" }).length;
  const b = lz77.compress(data, { windowSize: 4096, lookaheadSize: 18, mode: "lz77" }).length;
  console.log(`  LZSS : ${a} bytes (${(a / data.length * 100).toFixed(1)}%)`);
  console.log(`  LZ77 : ${b} bytes (${(b / data.length * 100).toFixed(1)}%)`);
  const ok = a < data.length * 1.15 && a < b;
  console.log(`  ${ok ? "✓" : "✗"} LZSS φραγμένο και καλύτερο του LZ77`);
  check("lzss bounded", ok);
}

console.log("=".repeat(62));
console.log("  CompressViz (JavaScript) — Έλεγχοι ορθότητας");
console.log("=".repeat(62));

testRoundTrips();
testNaiveRleAmbiguous();
testHuffmanProperties();
testArithmeticProperties();
testLzssExpansion();

console.log("\n" + "=".repeat(62));
if (failed.length) {
  console.log(`  ΑΠΟΤΥΧΙΑ: ${failed.length} έλεγχοι απέτυχαν, ${passed} πέρασαν`);
  for (const f of failed) console.log(`    - ${f}`);
  process.exit(1);
}
console.log(`  ΟΛΟΙ ΟΙ ΕΛΕΓΧΟΙ ΠΕΡΑΣΑΝ (${passed})`);
