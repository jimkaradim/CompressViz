/**
 * bitio.js — Είσοδος/έξοδος σε επίπεδο bit
 *
 * Αντίστοιχο του compressviz/bitio.py. Οι δύο υλοποιήσεις πρέπει να
 * παράγουν ταυτόσημα bytes για την ίδια είσοδο· αυτό ελέγχεται από το
 * scripts/crossvalidate.mjs.
 *
 * ΓΙΑΤΙ ΥΠΑΡΧΕΙ: η αρχική υλοποίηση παρήγαγε συμβολοσειρές από '0'/'1'
 * και μετρούσε το μήκος τους ως πλήθος bits. Αυτό είναι εντάξει για
 * οπτικοποίηση αλλά όχι για μέτρηση: το πραγματικό αρχείο έχει padding
 * στο τελευταίο byte και κεφαλίδα, που η αρχική μέτρηση αγνοούσε.
 */

export class BitWriter {
  constructor() {
    this.bytes = [];
    this.cur = 0;
    this.nbits = 0;
    this.count = 0;
  }

  writeBit(bit) {
    this.cur = ((this.cur << 1) | (bit & 1)) & 0xff;
    this.nbits++;
    this.count++;
    if (this.nbits === 8) {
      this.bytes.push(this.cur);
      this.cur = 0;
      this.nbits = 0;
    }
  }

  /** Γράφει τα n λιγότερο σημαντικά bits του value, MSB-first. */
  writeBits(value, n) {
    for (let i = n - 1; i >= 0; i--) this.writeBit((value >>> i) & 1);
  }

  writeByte(b) { this.writeBits(b & 0xff, 8); }

  /** Κλείνει το τελευταίο byte με μηδενικά padding bits. */
  finish() {
    const out = this.bytes.slice();
    if (this.nbits > 0) out.push((this.cur << (8 - this.nbits)) & 0xff);
    return Uint8Array.from(out);
  }
}

export class BitReader {
  constructor(data) {
    this.data = data;
    this.pos = 0;
  }

  readBit() {
    const byteI = this.pos >> 3;
    const bitI = this.pos & 7;
    if (byteI >= this.data.length) throw new Error("Τέλος bitstream");
    this.pos++;
    return (this.data[byteI] >> (7 - bitI)) & 1;
  }

  readBits(n) {
    let v = 0;
    for (let i = 0; i < n; i++) v = v * 2 + this.readBit();
    return v;
  }
}

/** Μετατροπή συμβολοσειράς σε bytes (UTF-8). */
export function toBytes(str) {
  return new TextEncoder().encode(str);
}

/** Μετατροπή bytes σε συμβολοσειρά (UTF-8). */
export function fromBytes(bytes) {
  return new TextDecoder().decode(bytes);
}

/** Σύγκριση δύο Uint8Array. */
export function bytesEqual(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

export function concatBytes(...parts) {
  const total = parts.reduce((s, p) => s + p.length, 0);
  const out = new Uint8Array(total);
  let off = 0;
  for (const p of parts) { out.set(p, off); off += p.length; }
  return out;
}

/** Big-endian ακέραιος σε bytes. */
export function intToBytes(value, nbytes) {
  const out = new Uint8Array(nbytes);
  for (let i = nbytes - 1; i >= 0; i--) { out[i] = value % 256; value = Math.floor(value / 256); }
  return out;
}

export function bytesToInt(bytes, offset, nbytes) {
  let v = 0;
  for (let i = 0; i < nbytes; i++) v = v * 256 + bytes[offset + i];
  return v;
}
