/* Moments 1 and 2: the run drawn like a tracked shipment, and claims filling in as verdicts land.
   args: {kind: "route", run_id, order: [state...], index, failed, finished, status,
          claims: [{claim_id, slide, label}], colours, names}
   First sight of a run shows its current state with no motion (a resumed run's finished stops are
   simply lit: skipped, not redone). Motion plays only for changes seen while the page is open. */
"use strict";

DC.renderers.route = function (root, a) {
  const n = a.order.length;
  const pct = function (i) { return n > 1 ? (Math.max(0, i) / (n - 1)) * 100 : 0; };
  const key = "route:" + a.run_id;
  const prev = DC.load(key);                       // {index, labels: {claim_id: label}} or null

  let view = root.querySelector(".route-view");
  if (!view || view.dataset.run !== a.run_id) {
    root.textContent = "";
    view = DC.el("div", "route-view");
    view.dataset.run = a.run_id;
    const route = DC.el("div", "route");
    const track = DC.el("div", "track");
    track.appendChild(DC.el("div", "fill"));
    const marker = DC.el("div", "marker");
    marker.setAttribute("role", "img");
    track.appendChild(marker);
    route.appendChild(track);
    const stops = DC.el("ol", "stops");
    a.order.forEach(function (name) {
      const li = DC.el("li", "stop");
      li.appendChild(DC.el("span", "dot"));
      li.appendChild(DC.el("span", "name", name));
      stops.appendChild(li);
    });
    route.appendChild(stops);
    view.appendChild(route);
    view.appendChild(DC.el("div", "landing"));
    view.appendChild(DC.el("p", "status"));
    root.appendChild(view);
  }

  // ---- checkpoints and marker ----
  const fill = view.querySelector(".fill");
  const marker = view.querySelector(".marker");
  const idx = a.failed && a.index < 0 ? 0 : a.index;
  view.querySelectorAll(".stop").forEach(function (li, i) {
    li.classList.toggle("passed", a.finished || i < idx);
    li.classList.toggle("current", !a.failed && i === idx);
    li.classList.toggle("failed", a.failed && i === idx);
  });
  marker.classList.toggle("failed", !!a.failed);
  marker.setAttribute("aria-label", a.failed ? "Run stopped with an error at " + a.order[idx]
                                             : "Run is at " + (a.order[idx] || "unknown"));
  const from = prev && typeof prev.index === "number" ? prev.index : idx;
  const steps = Math.max(1, Math.abs(idx - from));
  const duration = Math.min(1200, 380 * steps);
  if (from !== idx) {
    DC.animate(fill, [{ width: pct(from) + "%" }, { width: pct(idx) + "%" }], { duration: duration });
    DC.animate(marker, [{ left: pct(from) + "%" }, { left: pct(idx) + "%" }], { duration: duration });
  } else {
    fill.style.width = pct(idx) + "%";
    marker.style.left = pct(idx) + "%";
  }

  // ---- claims landing ----
  const landing = view.querySelector(".landing");
  const known = (prev && prev.labels) || null;
  const byId = {};
  landing.querySelectorAll(".blk").forEach(function (b) { byId[b.dataset.id] = b; });
  const claims = (a.claims || []).slice().sort(function (x, y) { return (x.slide || 0) - (y.slide || 0); });
  const labels = {};
  claims.forEach(function (c) {
    labels[c.claim_id] = c.label;
    let blk = byId[c.claim_id];
    const isNew = !blk;
    if (isNew) {
      blk = DC.el("div", "blk", c.slide);
      blk.dataset.id = c.claim_id;
      landing.appendChild(blk);
      if (known) DC.animate(blk, [{ opacity: 0 }, { opacity: 1 }], { duration: 220 });
    }
    blk.title = "Slide " + c.slide + ": " + DC.name(a, c.label);
    const decided = c.label && c.label !== "PENDING";
    const was = known ? known[c.claim_id] : c.label;   // first sight: no motion
    if (decided) {
      const colour = DC.colour(a, c.label);
      blk.style.color = "#FFFFFF";
      blk.style.borderColor = colour;
      if (was !== c.label) {
        DC.animate(blk, [{ backgroundColor: "transparent", transform: "scale(.86)" },
                         { backgroundColor: colour, transform: "scale(1.06)", offset: .7 },
                         { backgroundColor: colour, transform: "scale(1)" }], { duration: 420 });
      } else {
        blk.style.backgroundColor = colour;
      }
    }
  });
  landing.style.display = claims.length ? "flex" : "none";
  view.querySelector(".status").textContent = a.status || "";
  DC.save(key, { index: idx, labels: labels });
};
