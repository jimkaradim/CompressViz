/**
 * BitstreamView.jsx — Προβολή των πραγματικών bytes εξόδου
 *
 * Ζητούμενο της εκφώνησης («Bitstream view») που έλειπε από την αρχική
 * έκδοση. Δείχνει τι γράφεται πραγματικά στο αρχείο, με τα bytes της
 * κεφαλίδας χρωματισμένα χωριστά από το ωφέλιμο φορτίο.
 *
 * Έχει και διαγνωστική αξία: η αρχική υλοποίηση παρήγαγε συμβολοσειρές
 * από '0'/'1' και δεν υπήρχε κανένα σημείο όπου να φαίνεται ότι το
 * τελικό αρχείο έχει κεφαλίδα και padding.
 */

import { useState } from "react";

import { MONO, SC } from "../theme.js";
import { Button, Card, SectionTitle } from "./ui.jsx";

const PAGE = 512;

export default function BitstreamView({ blob, headerBits, color, algorithmLabel }) {
  const [page, setPage] = useState(0);
  const [mode, setMode] = useState("hex");

  const headerBytes = Math.ceil(headerBits / 8);
  const pages = Math.max(1, Math.ceil(blob.length / PAGE));
  const start = page * PAGE;
  const slice = Array.from(blob.slice(start, start + PAGE));

  const render = (b) =>
    mode === "hex"
      ? b.toString(16).padStart(2, "0")
      : b.toString(2).padStart(8, "0");

  return (
    <Card color={color}>
      <SectionTitle note={
        `${algorithmLabel}: ${blob.length.toLocaleString()} bytes συνολικά — ` +
        `${headerBytes.toLocaleString()} κεφαλίδα, ` +
        `${(blob.length - headerBytes).toLocaleString()} ωφέλιμο φορτίο`
      }>
        Έξοδος σε επίπεδο byte
      </SectionTitle>

      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap",
        alignItems: "center" }}>
        <Button active={mode === "hex"} onClick={() => setMode("hex")} color={color}>
          Δεκαεξαδικό
        </Button>
        <Button active={mode === "bin"} onClick={() => setMode("bin")} color={color}>
          Δυαδικό
        </Button>
        {pages > 1 && (
          <>
            <Button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
              ←
            </Button>
            <span style={{ fontSize: 11, color: SC.textDim, fontFamily: MONO }}>
              bytes {start.toLocaleString()}–
              {Math.min(start + PAGE, blob.length).toLocaleString()}
            </span>
            <Button onClick={() => setPage(p => Math.min(pages - 1, p + 1))}
              disabled={page >= pages - 1}>
              →
            </Button>
          </>
        )}
        <span style={{ fontSize: 11, color: SC.warn, marginLeft: "auto" }}>
          ▉ κεφαλίδα
        </span>
      </div>

      <div style={{ fontFamily: MONO, fontSize: mode === "hex" ? 12 : 10,
        lineHeight: 1.7, wordBreak: "break-all", color: SC.textDim,
        maxHeight: 300, overflowY: "auto" }}>
        {slice.map((b, i) => {
          const isHeader = start + i < headerBytes;
          return (
            <span key={i} style={{
              marginRight: 5,
              color: isHeader ? SC.warn : color,
              background: isHeader ? SC.warn + "18" : "transparent",
              padding: "1px 2px", borderRadius: 2,
            }}>
              {render(b)}
            </span>
          );
        })}
      </div>
    </Card>
  );
}
