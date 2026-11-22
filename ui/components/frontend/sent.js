/* Moment 6: the founder email going into the test inbox exactly once.
   args: {kind: "sent", action_id, subject, recipient, key_prefix, sent_at, inbox_count, just_sent}
   The card moves into the inbox tray only when this browser session just approved it (just_sent) and has
   not shown it before; any later render (rerun, reload, a second click) shows the settled stamp, the same
   way the UNIQUE idempotency key makes a second send impossible. */
"use strict";

DC.renderers.sent = function (root, a) {
  root.textContent = "";
  const box = DC.el("div", "sent");
  const card = DC.el("div", "card");
  card.appendChild(DC.el("div", "subj", a.subject || "Founder email"));
  card.appendChild(DC.el("div", "to", "To " + (a.recipient || "the test inbox")));
  const tray = DC.el("div", "tray");
  const count = DC.el("span", "count", a.inbox_count);
  tray.appendChild(count);
  tray.appendChild(DC.el("span", "", "in the test inbox"));
  const stamp = DC.el("div", "stamp", "Sent once");
  stamp.appendChild(DC.el("small", "", "key " + (a.key_prefix || "") + "…" + (a.sent_at ? ", " + a.sent_at : "")));
  box.appendChild(card);
  box.appendChild(tray);
  box.appendChild(stamp);
  root.appendChild(box);

  const seenKey = "sent:" + a.action_id;
  const play = a.just_sent && !DC.load(seenKey) && !DC.reduced;
  DC.save(seenKey, true);
  if (!play) { card.style.opacity = "0.55"; return; }

  stamp.style.opacity = "0";
  count.textContent = String(Math.max(0, (a.inbox_count || 1) - 1));
  requestAnimationFrame(function () {
    const c = card.getBoundingClientRect(), t = tray.getBoundingClientRect();
    const dx = t.left + t.width / 2 - (c.left + c.width / 2);
    DC.animate(card, [{ transform: "translateX(0) scale(1)", opacity: 1 },
                      { transform: "translateX(" + dx + "px) scale(.35)", opacity: 0 }],
               { duration: 650, delay: 150, easing: "cubic-bezier(.5,0,.3,1)" }).then(function () {
      count.textContent = String(a.inbox_count);
      DC.animate(tray, [{ transform: "scale(1)" }, { transform: "scale(1.06)" }, { transform: "scale(1)" }], { duration: 260 });
      DC.animate(card, [{ transform: "none", opacity: 0 }, { transform: "none", opacity: 0.55 }], { duration: 300 });
      DC.animate(stamp, [{ opacity: 0, transform: "translateY(4px)" },
                         { opacity: 1, transform: "none" }], { duration: 200, easing: "ease-out" });
    });
  });
};
