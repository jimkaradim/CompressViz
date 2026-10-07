/**
 * App.jsx — CompressViz
 *
 * Διαδραστικό εργαλείο οπτικοποίησης αλγορίθμων lossless συμπίεσης.
 *
 * ΔΟΜΙΚΗ ΑΛΛΑΓΗ ΕΝΑΝΤΙ ΤΗΣ ΑΡΧΙΚΗΣ ΕΚΔΟΣΗΣ
 * ------------------------------------------
 * Στο αρχικό αρχείο των 1.001 γραμμών, οι αλγόριθμοι, τα components και
 * η κατάσταση της εφαρμογής ήταν όλα μαζί. Κρίσιμα, οι *μετρικές*
 * παράγονταν από τον ίδιο κώδικα που παρήγαγε την *οπτικοποίηση*: δεν
 * υπήρχε αποκωδικοποιητής, άρα κανένα σφάλμα δεν μπορούσε να εντοπιστεί.
 *
 * Πλέον:
 *   - οι αλγόριθμοι ζουν στο src/algorithms/ και ελέγχονται χωριστά,
 *   - κάθε μετρική περνά από runVerified(), που εκτελεί round-trip,
 *   - το trace() αφορά μόνο την οπτικοποίηση.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { ALGORITHMS, runTrace, runVerified } from "./algorithms/index.js";
import { arithmetic } from "./algorithms/index.js";
import BitstreamView from "./components/BitstreamView.jsx";
import ComparativeView from "./components/ComparativeView.jsx";
import {
  ArithmeticView, HuffmanView, LZ77View, LZWView, RLEView,
} from "./components/StepViews.jsx";
import { Button, Card, LosslessBadge, SectionTitle, StatCard } from "./components/ui.jsx";
import { MONO, SAMPLES, SC } from "./theme.js";

const TABS = [
  { id: "step", label: "Βήμα-βήμα" },
  { id: "compare", label: "Σύγκριση" },
  { id: "bitstream", label: "Bitstream" },
  { id: "about", label: "Αλγόριθμοι" },
];

const SPEEDS = [
  { label: "0.5×", ms: 1600 },
  { label: "1×", ms: 800 },
  { label: "2×", ms: 400 },
  { label: "5×", ms: 160 },
];

export default function App() {
  const [text, setText] = useState(SAMPLES.alice);
  const [algoId, setAlgoId] = useState("huffman");
  const [tab, setTab] = useState("step");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(800);
  const timer = useRef(null);

  const data = useMemo(() => new TextEncoder().encode(text), [text]);

  // Μετρικές για ΟΛΟΥΣ τους αλγορίθμους, πάντα επαληθευμένες.
  const results = useMemo(
    () => (data.length ? Object.keys(ALGORITHMS).map(id => runVerified(id, data)) : []),
    [data]
  );

  const trace = useMemo(
    () => (data.length ? runTrace(algoId, data) : { steps: [], blob: new Uint8Array(0) }),
    [data, algoId]
  );

  const current = results.find(r => r.id === algoId);
  const meta = ALGORITHMS[algoId];
  const entropy = useMemo(() => arithmetic.entropy(data), [data]);
  const shannonRatio = (entropy / 8) * 100;
  const anyLoss = results.some(r => !r.lossless);

  useEffect(() => { setStep(0); setPlaying(false); }, [algoId, text]);

  useEffect(() => {
    clearInterval(timer.current);
    if (playing && trace.steps.length) {
      timer.current = setInterval(() => {
        setStep(s => {
          if (s >= trace.steps.length - 1) { setPlaying(false); return s; }
          return s + 1;
        });
      }, speed);
    }
    return () => clearInterval(timer.current);
  }, [playing, speed, trace.steps.length]);

  const exportJSON = () => {
    const payload = {
      generatedAt: new Date().toISOString(),
      input: { text, bytes: data.length, entropyBitsPerSymbol: entropy },
      results: results.map(r => ({
        algorithm: ALGORITHMS[r.id].full,
        family: ALGORITHMS[r.id].family,
        headerBits: r.headerBits,
        payloadBits: r.payloadBits,
        totalBits: r.totalBits,
        originalBits: r.originalBits,
        ratioPct: Number(r.ratio.toFixed(4)),
        bitsPerSymbol: Number(r.bitsPerSymbol.toFixed(4)),
        losslessVerified: r.lossless,
      })),
      shannonBoundBits: arithmetic.shannonBoundBits(data),
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" })
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "compressviz-results.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const stepData = trace.steps[Math.min(step, trace.steps.length - 1)];

  const renderStepView = () => {
    if (!stepData) return null;
    const props = { step: stepData, text, color: meta.color };
    if (algoId === "rle") return <RLEView {...props} />;
    if (algoId === "huffman") return <HuffmanView {...props} />;
    if (algoId === "lz77" || algoId === "lzss") return <LZ77View {...props} />;
    if (algoId === "lzw") return <LZWView {...props} />;
    return <ArithmeticView {...props} />;
  };

  return (
    <div style={{
      minHeight: "100vh", background: SC.bg, color: SC.text,
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      padding: "20px 16px 48px",
    }}>
      <div style={{ maxWidth: 1120, margin: "0 auto" }}>

        <header style={{ marginBottom: 20 }}>
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, letterSpacing: -0.3 }}>
            CompressViz
          </h1>
          <p style={{ fontSize: 12, color: SC.textDim, margin: "5px 0 0" }}>
            Βήμα-βήμα οπτικοποίηση αλγορίθμων lossless συμπίεσης.
            Κάθε μετρική επαληθεύεται με αποσυμπίεση.
          </p>
        </header>

        {anyLoss && (
          <div style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 8,
            background: SC.bad + "1A", border: `1px solid ${SC.bad}44`,
            fontSize: 12, color: SC.bad }}>
            Ένας ή περισσότεροι αλγόριθμοι απέτυχαν στον έλεγχο round-trip για
            αυτή την είσοδο. Οι αντίστοιχες μετρικές δεν είναι έγκυρες.
          </div>
        )}

        <Card style={{ marginBottom: 14 }}>
          <SectionTitle note={`${data.length.toLocaleString()} bytes · H(X) = ${entropy.toFixed(4)} bits/σύμβολο`}>
            Κείμενο εισόδου
          </SectionTitle>
          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            spellCheck={false}
            style={{
              width: "100%", minHeight: 80, background: SC.bg, color: SC.text,
              border: `1px solid ${SC.border}`, borderRadius: 8, padding: 11,
              fontFamily: MONO, fontSize: 12, resize: "vertical", boxSizing: "border-box",
            }}
          />
          <div style={{ display: "flex", gap: 7, marginTop: 9, flexWrap: "wrap" }}>
            {Object.entries(SAMPLES).map(([k, v]) => (
              <Button key={k} onClick={() => setText(v)}>{k}</Button>
            ))}
            <Button onClick={exportJSON} color={SC.good} active>
              Εξαγωγή αποτελεσμάτων (JSON)
            </Button>
          </div>
        </Card>

        <div style={{ display: "flex", gap: 7, marginBottom: 14, flexWrap: "wrap" }}>
          {Object.entries(ALGORITHMS).map(([id, m]) => (
            <Button key={id} active={algoId === id} color={m.color}
              onClick={() => setAlgoId(id)} title={m.full}>
              {m.label}
            </Button>
          ))}
        </div>

        {current && (
          <div style={{
            display: "grid", gap: 10, marginBottom: 14,
            gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          }}>
            <StatCard label="Λόγος συμπίεσης" color={current.ratio < 100 ? SC.good : SC.bad}
              value={`${current.ratio.toFixed(2)}%`}
              sub={current.ratio < 100
                ? `${(100 - current.ratio).toFixed(1)}% μικρότερο`
                : `${(current.ratio - 100).toFixed(1)}% μεγαλύτερο`} />
            <StatCard label="Σύνολο" value={current.totalBits.toLocaleString()}
              sub={`από ${current.originalBits.toLocaleString()} bits`} />
            <StatCard label="Κεφαλίδα" value={current.headerBits.toLocaleString()}
              color={SC.warn} sub="μοντέλο/παράμετροι" />
            <StatCard label="bits/σύμβολο" value={current.bitsPerSymbol.toFixed(3)}
              sub={`φράγμα: ${entropy.toFixed(3)}`} />
            <StatCard label="Επαλήθευση" value={<LosslessBadge ok={current.lossless} />}
              sub="decompress(compress(x)) == x" small />
          </div>
        )}

        <div style={{ display: "flex", gap: 7, marginBottom: 14, flexWrap: "wrap" }}>
          {TABS.map(t => (
            <Button key={t.id} active={tab === t.id} onClick={() => setTab(t.id)}>
              {t.label}
            </Button>
          ))}
        </div>

        {tab === "step" && (
          <div style={{ display: "grid", gap: 14 }}>
            <Card>
              <div style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
                <Button onClick={() => { setPlaying(false); setStep(s => Math.max(0, s - 1)); }}
                  disabled={step === 0}>← Πίσω</Button>
                <Button active={playing} color={meta.color}
                  onClick={() => setPlaying(p => !p)}>
                  {playing ? "Παύση" : "Αναπαραγωγή"}
                </Button>
                <Button onClick={() => { setPlaying(false); setStep(s => Math.min(trace.steps.length - 1, s + 1)); }}
                  disabled={step >= trace.steps.length - 1}>Μπροστά →</Button>
                <Button onClick={() => { setPlaying(false); setStep(0); }}>Αρχή</Button>
                <span style={{ fontSize: 11, color: SC.textDim, fontFamily: MONO,
                  marginLeft: 6 }}>
                  {trace.steps.length ? step + 1 : 0} / {trace.steps.length}
                </span>
                <div style={{ marginLeft: "auto", display: "flex", gap: 5 }}>
                  {SPEEDS.map(s => (
                    <Button key={s.ms} active={speed === s.ms} color={meta.color}
                      onClick={() => setSpeed(s.ms)}>{s.label}</Button>
                  ))}
                </div>
              </div>
              <input
                type="range" min={0} max={Math.max(0, trace.steps.length - 1)} value={step}
                onChange={e => { setPlaying(false); setStep(Number(e.target.value)); }}
                style={{ width: "100%", marginTop: 12, accentColor: meta.color }}
              />
            </Card>
            {renderStepView()}
          </div>
        )}

        {tab === "compare" && results.length > 0 && (
          <ComparativeView results={results} shannonRatio={shannonRatio} entropy={entropy} />
        )}

        {tab === "bitstream" && current && (
          <BitstreamView blob={current.blob} headerBits={current.headerBits}
            color={meta.color} algorithmLabel={meta.full} />
        )}

        {tab === "about" && (
          <div style={{ display: "grid", gap: 10 }}>
            {Object.entries(ALGORITHMS).map(([id, m]) => (
              <Card key={id} color={m.color}>
                <div style={{ display: "flex", gap: 10, alignItems: "baseline",
                  flexWrap: "wrap", marginBottom: 6 }}>
                  <span style={{ color: m.color, fontWeight: 700, fontSize: 14 }}>{m.full}</span>
                  <span style={{ fontSize: 11, color: SC.muted }}>{m.family}</span>
                </div>
                <p style={{ fontSize: 12, color: SC.textDim, margin: "0 0 7px", lineHeight: 1.6 }}>
                  {m.description}
                </p>
                <div style={{ fontSize: 11, color: SC.muted }}>Τυπική χρήση: {m.ideal}</div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
