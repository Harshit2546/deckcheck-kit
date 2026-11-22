/* DeckCheck motion components: the Streamlit component protocol, hand-written (no npm, no build, no CDN).
   Called by: index.html. Calls: window.parent.postMessage only.
   Every piece of data text is inserted with textContent, never innerHTML. */
"use strict";

const DC = {
  renderers: {},
  reduced: window.matchMedia("(prefers-reduced-motion: reduce)").matches,

  send(type, data) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: type }, data || {}), "*");
  },
  ready() { DC.send("streamlit:componentReady", { apiVersion: 1 }); },
  height() {
    const h = Math.ceil(document.getElementById("root").getBoundingClientRect().height) + 4;
    if (h !== DC._lastHeight) { DC._lastHeight = h; DC.send("streamlit:setFrameHeight", { height: h }); }
  },
  value(v) { DC.send("streamlit:setComponentValue", { value: v, dataType: "json" }); },

  el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  },
  svg(tag, attrs) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.keys(attrs || {}).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    return node;
  },
  /* sessionStorage survives reruns and reloads of this tab, so a moment plays once per run, not on every rerun */
  load(key) { try { return JSON.parse(window.sessionStorage.getItem("dc:" + key)); } catch (e) { return null; } },
  save(key, v) { try { window.sessionStorage.setItem("dc:" + key, JSON.stringify(v)); } catch (e) { /* private mode */ } },
  /* Web Animations API helper; under reduced motion it jumps to the end state */
  animate(node, frames, opts) {
    if (DC.reduced || !node.animate) {
      const last = frames[frames.length - 1];
      Object.keys(last).forEach(function (k) { if (k !== "offset" && k !== "easing") node.style[k] = last[k]; });
      return Promise.resolve();
    }
    const anim = node.animate(frames, Object.assign({ fill: "forwards", easing: "cubic-bezier(.2,.7,.2,1)" }, opts));
    return anim.finished.then(function () {
      const last = frames[frames.length - 1];
      Object.keys(last).forEach(function (k) { if (k !== "offset" && k !== "easing") node.style[k] = last[k]; });
      anim.cancel();
    }).catch(function () {});
  },
  colour(args, label) { return (args.colours && args.colours[label || "PENDING"]) || "#7A8594"; },
  name(args, label) { return (args.names && args.names[label || "PENDING"]) || label || ""; },
};

window.addEventListener("message", function (event) {
  const msg = event.data;
  if (!msg || msg.type !== "streamlit:render") return;
  const args = msg.args || {};
  const theme = msg.theme || {};
  document.documentElement.classList.toggle("dark", theme.base === "dark");
  const root = document.getElementById("root");
  const render = DC.renderers[args.kind];
  if (!render) { root.textContent = "Unknown component: " + args.kind; DC.height(); return; }
  try { render(root, args); } catch (err) { root.textContent = "This view could not be drawn: " + err.message; }
  DC.height();
  window.setTimeout(DC.height, 60);
});

window.addEventListener("resize", function () { DC.height(); });
