/* Moments 3 and 4: the deck scan and the clickable slide strip.
   args: {kind: "strip", run_id, animate, claims: [{claim_id, slide, type, label, quote}], counts, colours, names}
   The scan (a line passing over the deck, each block filling as it is passed, then the counts counting up)
   plays once per run in this browser tab. Clicking a block returns {claim_id, nonce} to Streamlit. */
"use strict";

DC.renderers.strip = function (root, a) {
  const claims = (a.claims || []).slice().sort(function (x, y) {
    return (x.slide || 0) - (y.slide || 0) || String(x.claim_id).localeCompare(String(y.claim_id));
  });
  root.textContent = "";
  const wrap = DC.el("div", "strip");
  wrap.setAttribute("role", "group");
  wrap.setAttribute("aria-label", "Claims by slide. Each block is one claim; press it to open the claim.");
  const detail = DC.el("div", "detail");
  const hint = "Point at a block to read the claim. Press it to open the claim with its evidence.";
  detail.textContent = hint;

  const segs = claims.map(function (c) {
    const label = c.label || "PENDING";
    const seg = DC.el("button", "seg" + (label === "PENDING" ? " pending" : ""), c.slide);
    seg.type = "button";
    seg.setAttribute("aria-label", "Slide " + c.slide + ", " + String(c.type || "").replace(/_/g, " ") + ": " +
                     DC.name(a, label) + ". " + (c.quote || ""));
    seg.dataset.colour = DC.colour(a, label);
    seg.style.borderColor = seg.dataset.colour;
    const show = function () {
      detail.textContent = "";
      detail.appendChild(document.createTextNode("Slide " + c.slide + ", " + String(c.type || "").replace(/_/g, " ") +
                                                 ". " + DC.name(a, label) + ". "));
      detail.appendChild(DC.el("span", "q", "“" + (c.quote || "") + "”"));
    };
    seg.addEventListener("mouseenter", show);
    seg.addEventListener("focus", show);
    seg.addEventListener("mouseleave", function () { if (document.activeElement !== seg) detail.textContent = hint; });
    seg.addEventListener("blur", function () { detail.textContent = hint; });
    seg.addEventListener("click", function () {
      segs.forEach(function (s) { s.setAttribute("aria-pressed", "false"); });
      seg.setAttribute("aria-pressed", "true");
      DC.value({ claim_id: c.claim_id, nonce: Date.now() });
    });
    wrap.appendChild(seg);
    return seg;
  });
  const scanner = DC.el("div", "scanner");
  wrap.appendChild(scanner);
  root.appendChild(wrap);

  // legend with counts
  const legend = DC.el("div", "legend");
  const counters = [];
  Object.keys(a.names || {}).forEach(function (label) {
    const count = (a.counts || {})[label] || 0;
    if (!count) return;
    const item = DC.el("span", "item");
    const sq = DC.el("i", "sq");
    sq.style.background = DC.colour(a, label);
    item.appendChild(sq);
    item.appendChild(document.createTextNode(DC.name(a, label) + " "));
    const num = DC.el("span", "n", count);
    item.appendChild(num);
    legend.appendChild(item);
    counters.push([num, count]);
  });
  root.appendChild(legend);
  root.appendChild(detail);

  const seenKey = "scan:" + a.run_id;
  const play = a.animate && !DC.reduced && !DC.load(seenKey) && segs.length > 0;
  if (!play) {
    segs.forEach(function (s) { s.style.background = s.dataset.colour; });
    return;
  }
  DC.save(seenKey, true);
  const SCAN_MS = 900;
  counters.forEach(function (c) { c[0].textContent = "0"; });
  requestAnimationFrame(function () {
    const width = wrap.getBoundingClientRect().width || 1;
    scanner.style.opacity = "1";
    DC.animate(scanner, [{ transform: "translateX(0)" }, { transform: "translateX(" + width + "px)" }],
               { duration: SCAN_MS, easing: "linear" }).then(function () {
      DC.animate(scanner, [{ opacity: 1 }, { opacity: 0 }], { duration: 200 });
    });
    segs.forEach(function (s) {
      const box = s.getBoundingClientRect();
      const at = ((box.left - wrap.getBoundingClientRect().left + box.width / 2) / width) * SCAN_MS;
      DC.animate(s, [{ backgroundColor: "transparent" }, { backgroundColor: s.dataset.colour }],
                 { duration: 180, delay: at, easing: "ease-out" });
    });
    const start = performance.now() + SCAN_MS;
    const tick = function (now) {
      const t = Math.min(1, Math.max(0, (now - start) / 450));
      counters.forEach(function (c) { c[0].textContent = String(Math.round(c[1] * t)); });
      if (t < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });
};
