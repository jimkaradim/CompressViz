/**
 * StepViews.jsx — Βήμα-βήμα οπτικοποίηση ανά αλγόριθμο
 *
 * Κάθε view δέχεται ένα βήμα από το trace() του αντίστοιχου αρθρώματος.
 * Τα views ΔΕΝ υπολογίζουν μετρικές — αυτές προέρχονται πάντα από την
 * compress() και επαληθεύονται με round-trip.
 */

import { MONO, SC, SEG_COLORS } from "../theme.js";
import { Card, SectionTitle, displayChar } from "./ui.jsx";

const cell = {
  display: "inline-block", padding: "3px 1px", fontFamily: MONO,
  fontSize: 13, borderRadius: 2, minWidth: 9, textAlign: "center",
};

function Legend({ items }) {
  return (
    <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 10 }}>
      {items.map(({ color, label }) => (
        <span key={label} style={{ fontSize: 11, color: SC.textDim,
          display: "inline-flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2,
            background: color + "55", border: `1px solid ${color}` }} />
          {label}
        </span>
      ))}
    </div>
  );
}

// ── RLE ─────────────────────────────────────────────────────────────

export function RLEView({ step, text, color }) {
  if (!step) return null;
  return (
    <Card color={color}>
      <SectionTitle note={`Token: ${step.token}`}>{step.title}</SectionTitle>
      <Legend items={[{ color, label: "τρέχον run" }]} />
      <div style={{ lineHeight: 1.9, wordBreak: "break-all" }}>
        {text.split("").map((c, i) => {
          const inRun = i >= step.pos && i <= step.runEnd;
          return (
            <span key={i} style={{
              ...cell,
              background: inRun ? color + "44" : "transparent",
              color: inRun ? color : SC.textDim,
              fontWeight: inRun ? 700 : 400,
            }}>{displayChar(c)}</span>
          );
        })}
      </div>
      <div style={{ marginTop: 12, fontSize: 12, color: SC.textDim }}>
        Μήκος run: <b style={{ color }}>{step.count}</b> · runs μέχρι τώρα:{" "}
        <b style={{ color: SC.text }}>{step.runsCount}</b>
      </div>
    </Card>
  );
}

// ── Huffman ─────────────────────────────────────────────────────────

export function HuffmanView({ step, color }) {
  if (!step) return null;

  if (step.phase === "frequency") {
    const max = Math.max(...step.freqTable.map(r => r.freq));
    return (
      <Card color={color}>
        <SectionTitle note={step.desc}>{step.title}</SectionTitle>
        <div style={{ display: "grid", gap: 3 }}>
          {step.freqTable.slice(0, 18).map(r => (
            <div key={r.sym} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ ...cell, width: 22, background: SC.bg, color: SC.text }}>
                {displayChar(r.char)}
              </span>
              <div style={{ flex: 1, height: 14, background: SC.bg, borderRadius: 3 }}>
                <div style={{ width: `${r.freq / max * 100}%`, height: "100%",
                  background: color + "88", borderRadius: 3 }} />
              </div>
              <span style={{ fontFamily: MONO, fontSize: 11, color: SC.textDim, width: 68 }}>
                {r.freq} · {(r.prob * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: SC.textDim }}>
          Εντροπία H(X) = <b style={{ color }}>{step.entropy.toFixed(4)}</b> bits/σύμβολο
        </div>
      </Card>
    );
  }

  if (step.phase === "tree") {
    return (
      <Card color={color}>
        <SectionTitle note={step.desc}>{step.title}</SectionTitle>
        <div style={{ display: "flex", alignItems: "center", gap: 10,
          justifyContent: "center", flexWrap: "wrap", padding: "10px 0" }}>
          {[step.left, step.right].map((n, i) => (
            <span key={i} style={{ fontFamily: MONO, fontSize: 12, padding: "6px 10px",
              background: SC.bg, border: `1px solid ${SC.border}`, borderRadius: 6,
              color: SC.text }}>
              {n.label} <span style={{ color: SC.muted }}>({n.freq})</span>
            </span>
          ))}
          <span style={{ color: SC.muted }}>→</span>
          <span style={{ fontFamily: MONO, fontSize: 12, padding: "6px 10px",
            background: color + "22", border: `1px solid ${color}55`, borderRadius: 6,
            color }}>
            {step.merged.label} <span style={{ opacity: 0.7 }}>({step.merged.freq})</span>
          </span>
        </div>
        <div style={{ marginTop: 8, fontSize: 11, color: SC.muted }}>
          Ουρά προτεραιότητας: {step.heapState.map(h => `${h.label}:${h.freq}`).join(" · ")}
        </div>
      </Card>
    );
  }

  if (step.phase === "codes") {
    return (
      <Card color={color}>
        <SectionTitle note={step.desc}>{step.title}</SectionTitle>
        <div style={{ display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 6 }}>
          {step.codeTable.slice(0, 32).map(r => (
            <div key={r.sym} style={{ display: "flex", gap: 7, alignItems: "center",
              background: SC.bg, padding: "5px 8px", borderRadius: 5 }}>
              <span style={{ ...cell, background: color + "22", color, minWidth: 18 }}>
                {displayChar(r.char)}
              </span>
              <span style={{ fontFamily: MONO, fontSize: 11, color: SC.textDim }}>{r.bits}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: SC.textDim }}>
          Μέσο μήκος L = <b style={{ color }}>{step.avgCodeLength.toFixed(4)}</b>{" "}
          bits/σύμβολο · H = <b style={{ color: SC.text }}>{step.entropy.toFixed(4)}</b>{" "}
          <span style={{ color: SC.muted }}>
            (εγγύηση: H ≤ L &lt; H+1 · απόκλιση {(step.avgCodeLength - step.entropy).toFixed(4)})
          </span>
        </div>
      </Card>
    );
  }

  return (
    <Card color={color}>
      <SectionTitle note={step.desc}>{step.title}</SectionTitle>
      <div style={{ fontSize: 12, color: SC.textDim, lineHeight: 1.9 }}>
        Κεφαλίδα (μήκη κωδικών): <b style={{ color: SC.warn }}>{step.headerBits.toLocaleString()}</b> bits<br />
        Ωφέλιμο φορτίο: <b style={{ color }}>{step.payloadBits.toLocaleString()}</b> bits<br />
        Σύνολο: <b style={{ color: SC.text }}>{step.totalBits.toLocaleString()}</b> bits
        {" "}από {step.originalBits.toLocaleString()}
      </div>
    </Card>
  );
}

// ── LZ77 / LZSS ─────────────────────────────────────────────────────

export function LZ77View({ step, text, color }) {
  if (!step) return null;
  return (
    <Card color={color}>
      <SectionTitle note={step.desc}>{step.title}</SectionTitle>
      <Legend items={[
        { color: "#F87171", label: "παράθυρο αναζήτησης" },
        { color: "#10B981", label: "αντιστοίχιση" },
        { color: "#60A5FA", label: "lookahead" },
      ]} />
      <div style={{ lineHeight: 1.9, wordBreak: "break-all" }}>
        {text.split("").map((c, i) => {
          let bg = "transparent", fg = SC.muted;
          if (i >= step.windowStart && i <= step.windowEnd) { bg = "#F8717122"; fg = "#F87171"; }
          if (step.matchStart !== null && i >= step.matchStart && i <= step.matchEnd) {
            bg = "#10B98144"; fg = "#10B981";
          }
          if (i >= step.pos && i <= step.lookaheadEnd) { bg = "#60A5FA33"; fg = "#60A5FA"; }
          return <span key={i} style={{ ...cell, background: bg, color: fg }}>{displayChar(c)}</span>;
        })}
      </div>
      <div style={{ marginTop: 12, display: "flex", gap: 16, flexWrap: "wrap",
        fontSize: 12, color: SC.textDim }}>
        <span>Token: <b style={{ color, fontFamily: MONO }}>{step.token}</b></span>
        <span>Κόστος: <b style={{ color: SC.text }}>{step.tokenBits}</b> bits</span>
        <span>Σύνολο: <b style={{ color: SC.text }}>{step.bitsSoFar.toLocaleString()}</b> bits</span>
      </div>
    </Card>
  );
}

// ── LZW ─────────────────────────────────────────────────────────────

export function LZWView({ step, color }) {
  if (!step) return null;
  return (
    <Card color={color}>
      <SectionTitle note={step.desc}>{step.title}</SectionTitle>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 }}>
        <div style={{ background: SC.bg, padding: "8px 12px", borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: SC.muted, marginBottom: 3 }}>BUFFER</div>
          <div style={{ fontFamily: MONO, fontSize: 13, color: SC.text }}>
            {step.buffer ? `"${step.buffer}"` : "—"}
          </div>
        </div>
        <div style={{ background: SC.bg, padding: "8px 12px", borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: SC.muted, marginBottom: 3 }}>ΕΚΠΟΜΠΗ</div>
          <div style={{ fontFamily: MONO, fontSize: 13, color: step.emitted ? color : SC.muted }}>
            {step.emitted ? `${step.emitted.code} (${step.emitted.bits} bits)` : "—"}
          </div>
        </div>
        <div style={{ background: SC.bg, padding: "8px 12px", borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: SC.muted, marginBottom: 3 }}>ΠΛΑΤΟΣ ΚΩΔΙΚΟΥ</div>
          <div style={{ fontFamily: MONO, fontSize: 13, color: SC.warn }}>
            {step.width} bits
          </div>
        </div>
        <div style={{ background: SC.bg, padding: "8px 12px", borderRadius: 6 }}>
          <div style={{ fontSize: 10, color: SC.muted, marginBottom: 3 }}>ΜΕΓΕΘΟΣ ΛΕΞΙΚΟΥ</div>
          <div style={{ fontFamily: MONO, fontSize: 13, color: SC.text }}>{step.dictSize}</div>
        </div>
      </div>
      {step.recentEntries?.length > 0 && (
        <>
          <div style={{ fontSize: 10, color: SC.muted, marginBottom: 5 }}>
            ΠΡΟΣΦΑΤΕΣ ΕΓΓΡΑΦΕΣ ΛΕΞΙΚΟΥ
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {step.recentEntries.map(e => (
              <span key={e.code} style={{ fontFamily: MONO, fontSize: 11,
                padding: "3px 8px", borderRadius: 4,
                background: e === step.added ? color + "33" : SC.bg,
                color: e === step.added ? color : SC.textDim }}>
                {e.code}: "{e.seq}"
              </span>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

// ── Arithmetic ──────────────────────────────────────────────────────

export function ArithmeticView({ step, color }) {
  if (!step) return null;

  if (step.phase === "probabilities") {
    return (
      <Card color={color}>
        <SectionTitle note={step.desc}>{step.title}</SectionTitle>
        <div style={{ display: "flex", height: 34, borderRadius: 5,
          overflow: "hidden", border: `1px solid ${SC.border}` }}>
          {step.probTable.map((r, i) => (
            <div key={r.sym} title={`${r.char}: ${(r.prob * 100).toFixed(2)}%`}
              style={{ width: `${r.prob * 100}%`,
                background: SEG_COLORS[i % SEG_COLORS.length] + "88",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 10, fontFamily: MONO, color: "#060D1F", overflow: "hidden" }}>
              {r.prob > 0.03 ? displayChar(r.char) : ""}
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: SC.textDim }}>
          Εντροπία H(X) = <b style={{ color }}>{step.entropy.toFixed(4)}</b> bits/σύμβολο
        </div>
      </Card>
    );
  }

  if (step.phase === "encode") {
    return (
      <Card color={color}>
        <SectionTitle note={step.desc}>{step.title}</SectionTitle>
        <div style={{ position: "relative", height: 30, background: SC.bg,
          borderRadius: 5, marginBottom: 12, overflow: "hidden" }}>
          <div style={{
            position: "absolute",
            left: `${step.normalizedLow * 100}%`,
            width: `${Math.max((step.normalizedHigh - step.normalizedLow) * 100, 0.4)}%`,
            height: "100%", background: color + "77",
          }} />
        </div>
        <div style={{ fontFamily: MONO, fontSize: 11, color: SC.textDim, lineHeight: 1.9 }}>
          Ακέραιο διάστημα: [{step.intervalInt.low.toLocaleString()},{" "}
          {step.intervalInt.high.toLocaleString()}]<br />
          Κανονικοποιημένο: [{step.normalizedLow.toFixed(8)},{" "}
          {step.normalizedHigh.toFixed(8)})<br />
          Bits που έχουν εκπεμφθεί: <b style={{ color: SC.text }}>{step.bitsEmitted}</b>
          {step.pendingBits > 0 && (
            <span style={{ color: SC.warn }}> · εκκρεμή (underflow): {step.pendingBits}</span>
          )}
        </div>
        {step.rescalings.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
            {step.rescalings.map((r, i) => (
              <span key={i} style={{ fontSize: 10, fontFamily: MONO, padding: "3px 8px",
                borderRadius: 4, background: SC.warn + "22", color: SC.warn }}>{r}</span>
            ))}
          </div>
        )}
      </Card>
    );
  }

  const over = step.overheadVsBound;
  return (
    <Card color={color}>
      <SectionTitle note={step.desc}>{step.title}</SectionTitle>
      <div style={{ fontSize: 12, color: SC.textDim, lineHeight: 1.9 }}>
        Κεφαλίδα (μοντέλο συχνοτήτων):{" "}
        <b style={{ color: SC.warn }}>{step.headerBits.toLocaleString()}</b> bits<br />
        Ωφέλιμο φορτίο: <b style={{ color }}>{step.payloadBits.toLocaleString()}</b> bits<br />
        Φράγμα Shannon H(X)·n:{" "}
        <b style={{ color: SC.text }}>{step.shannonBoundBits.toFixed(1)}</b> bits<br />
        Υπέρβαση φορτίου έναντι φράγματος:{" "}
        <b style={{ color: over >= 0 ? SC.good : SC.bad }}>
          {over >= 0 ? "+" : ""}{over.toFixed(1)} bits
        </b>
      </div>
      <div style={{ marginTop: 10, fontSize: 11, color: SC.muted, lineHeight: 1.6 }}>
        Η μικρή θετική υπέρβαση είναι το αναμενόμενο αποτέλεσμα. Αν το φορτίο
        έβγαινε ακριβώς ίσο με το φράγμα, αυτό θα σήμαινε ότι δεν κωδικοποιείται
        τίποτα και ότι απλώς αναφέρεται ο τύπος της εντροπίας.
      </div>
      <div style={{ marginTop: 8, fontSize: 11, color: SC.muted }}>
        Οπτικοποιήθηκαν τα πρώτα {step.visualizedSteps} από {step.totalSymbols.toLocaleString()}{" "}
        σύμβολα · η κωδικοποίηση εκτελείται πλήρης, χωρίς όριο μήκους.
      </div>
    </Card>
  );
}
