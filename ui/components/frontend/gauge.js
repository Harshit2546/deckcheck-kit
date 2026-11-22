/* Moment 5: claimed vs found on one scale, with the tolerance band from config/rules.yaml.
   args: {kind: "gauge", key, claimed, found, tol_pct, unit, metric, label, colours, names}
   Display only: the verdict label comes from verdict/engine.py; this draws the numbers it was given.
   The found marker slides from the claimed value to the found value once per claim in this tab. */
"use strict";

(function () {
  function fmt(v, unit) {
    const abs = Math.abs(v);
    const money = unit && /^[A-Z]{3}$/.test(unit);
    let text;
    if (abs >= 1e9) text = (v / 1e9).toFixed(abs >= 1e10 ? 0 : 1) + "B";
    else if (abs >= 1e6) text = (v / 1e6).toFixed(abs >= 1e7 ? 0 : 1) + "M";
    else if (abs >= 1e4) text = Math.round(v / 1e3) + "K";
    else text = Math.round(v).toLocaleString("en-IN");
    text = text.replace(".0M", "M").replace(".0B", "B");
    if (money) return (unit === "USD" ? "$" : unit === "INR" ? "₹" : unit + " ") + text;
    return text + (unit && unit !== "people" ? " " + unit : "");
  }

  DC.renderers.gauge = function (root, a) {
    const claimed = Number(a.claimed), found = Number(a.found), tol = Number(a.tol_pct) / 100;
    root.textContent = "";
    const box = DC.el("div", "gauge");
    const W = 600, H = 92, L = 24, R = 576, Y = 46;
    const lowBand = claimed * (1 - tol), highBand = claimed * (1 + tol);
    let lo = Math.min(found, lowBand), hi = Math.max(found, highBand);
    const pad = (hi - lo) * 0.18 || claimed * 0.2 || 1;
    lo = Math.max(0, lo - pad); hi = hi + pad;
    const x = function (v) { return L + ((v - lo) / (hi - lo)) * (R - L); };
    const colour = DC.colour(a, a.label);

    const svg = DC.svg("svg", { viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "Claimed " + fmt(claimed, a.unit) + ", found " + fmt(found, a.unit) +
                    ", allowed range " + fmt(lowBand, a.unit) + " to " + fmt(highBand, a.unit) });
    svg.appendChild(DC.svg("line", { x1: L, x2: R, y1: Y, y2: Y, stroke: "var(--rule)", "stroke-width": 2 }));
    svg.appendChild(DC.svg("rect", { x: x(lowBand), y: Y - 9, width: Math.max(2, x(highBand) - x(lowBand)), height: 18,
                                     rx: 3, fill: "var(--band)" }));
    const bandText = DC.svg("text", { x: (x(lowBand) + x(highBand)) / 2, y: Y + 30, "text-anchor": "middle" });
    bandText.textContent = "allowed ±" + a.tol_pct + "%";
    svg.appendChild(bandText);
    svg.appendChild(DC.svg("line", { x1: x(claimed), x2: x(claimed), y1: Y - 14, y2: Y + 14, stroke: "var(--ink)",
                                     "stroke-width": 2 }));
    const claimedText = DC.svg("text", { x: x(claimed), y: Y - 20, "text-anchor": "middle", class: "strong" });
    claimedText.textContent = "Claimed " + fmt(claimed, a.unit);
    svg.appendChild(claimedText);

    const g = DC.svg("g", {});
    g.appendChild(DC.svg("circle", { cx: 0, cy: Y, r: 8, fill: colour, stroke: "var(--card)", "stroke-width": 2.5 }));
    const foundText = DC.svg("text", { x: 0, y: Y + 30, "text-anchor": "middle", class: "strong" });
    foundText.textContent = "Found " + fmt(found, a.unit);
    foundText.setAttribute("fill", colour);
    foundText.style.fill = colour;
    g.appendChild(foundText);
    svg.appendChild(g);
    box.appendChild(svg);

    const diff = claimed ? (found - claimed) / claimed : 0;
    const say = DC.el("p", "say");
    const direction = diff < 0 ? "below" : "above";
    say.textContent = Math.abs(diff) < 0.0005
      ? "The record matches the claimed " + fmt(claimed, a.unit) + " exactly. Verdict: " + DC.name(a, a.label) + "."
      : "The record shows " + fmt(found, a.unit) + ", " + Math.round(Math.abs(diff) * 100) + "% " + direction +
        " the " + fmt(claimed, a.unit) + " claimed; the allowed gap is " + a.tol_pct + "%. Verdict: " +
        DC.name(a, a.label) + ".";
    box.appendChild(say);
    root.appendChild(box);

    const seenKey = "gauge:" + a.key;
    const play = !DC.load(seenKey);
    DC.save(seenKey, true);
    if (play && !DC.reduced) {
      g.setAttribute("transform", "translate(" + x(claimed) + ",0)");
      const start = performance.now() + 250, ms = 750, from = x(claimed), to = x(found);
      const ease = function (t) { return 1 - Math.pow(1 - t, 3); };
      const tick = function (now) {
        const t = Math.min(1, Math.max(0, (now - start) / ms));
        g.setAttribute("transform", "translate(" + (from + (to - from) * ease(t)) + ",0)");
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    } else {
      g.setAttribute("transform", "translate(" + x(found) + ",0)");
    }
  };
})();
