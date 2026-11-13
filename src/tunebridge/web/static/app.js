/* SH-Tunebridge – Frontend (ohne Build-Schritt, ohne Framework) */
"use strict";

/* ================================================================= Helpers */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const enc = encodeURIComponent;
const fmtTime = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function api(path, opts = {}) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts,
    body: opts.body && typeof opts.body !== "string" ? JSON.stringify(opts.body) : opts.body });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || r.statusText);
  return j;
}

function relTime(ts) {
  const d = Date.now() / 1000 - ts;
  if (d < 60) return "gerade eben";
  if (d < 3600) return `vor ${Math.floor(d / 60)} Min.`;
  if (d < 86400) return `vor ${Math.floor(d / 3600)} Std.`;
  if (d < 86400 * 7) return `vor ${Math.floor(d / 86400)} T.`;
  return new Date(ts * 1000).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "2-digit" });
}

const store = {
  get(k, d) { try { const v = localStorage.getItem("tb:" + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("tb:" + k, JSON.stringify(v)); } catch {} },
};

/* ================================================================= Icons */
const P = (...d) => d.map(x => `<path d="${x}"/>`).join("");
const ICONS = {
  chart: P("M4 20V11", "M10 20V5", "M16 20v-8", "M21 20H3"),
  dupe: `<rect x="8" y="8" width="12" height="12" rx="2"/>` + P("M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"),
  wave: P("M3 10v4", "M7 6v12", "M11 3v18", "M15 8v8", "M19 5v14"),
  inbox: P("M3 13h5l1.5 3h5l1.5-3h5", "M5.5 5h13L21 13v6H3v-6Z"),
  clock: `<circle cx="12" cy="12" r="9"/>` + P("M12 7v5l3 2"),
  stack: P("M21 15V6", "M18.5 18a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z", "M12 12H3", "M16 6H3", "M12 18H3"),
  compass: `<circle cx="12" cy="12" r="9"/>` + P("m16.2 7.8-2.1 6.3-6.3 2.1 2.1-6.3z"),
  globe: `<circle cx="12" cy="12" r="9"/>` + P("M3 12h18", "M12 3c2.5 2.7 3.8 5.7 3.8 9s-1.3 6.3-3.8 9c-2.5-2.7-3.8-5.7-3.8-9S9.5 5.7 12 3Z"),
  flag: P("M5 21V4", "M5 4h11l-2 4 2 4H5"),
  prev: P("M6 5v14", "M19 5 9 12l10 7Z"),
  sort: P("M7 4v16", "m3 8 4-4 4 4", "M17 20V4", "m13 16 4 4 4-4"),
  dot: "",
  next: P("M18 5v14", "M5 5l10 7-10 7Z"),
  split: P("M16 3h5v5", "M8 3H3v5", "M12 22v-8.3a4 4 0 0 0-1.17-2.87L3 3", "m15 9 6-6"),
  transfer: P("M8 3 4 7l4 4", "M4 7h16", "m16 21 4-4-4-4", "M20 17H4"),
  panel: P("M3 4h18v16H3z", "M9 4v16"),
  palette: P("M12 3a9 9 0 1 0 0 18c1.4 0 1.9-1.3 1.1-2.3-.9-1.1-.2-2.7 1.2-2.7H17a4 4 0 0 0 4-4c0-5-4-9-9-9z") + `<circle cx="7.5" cy="11" r="1.2"/><circle cx="10.5" cy="7" r="1.2"/><circle cx="15" cy="8" r="1.2"/>`,
  grid: P("M3 3h7v7H3z", "M14 3h7v7h-7z", "M14 14h7v7h-7z", "M3 14h7v7H3z"),
  layers: P("m12 2 10 5-10 5L2 7z", "m2 17 10 5 10-5", "m2 12 10 5 10-5"),
  sliders: P("M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M2 14h4", "M10 8h4", "M18 16h4"),
  play: `<path d="M7 4.6v14.8a1 1 0 0 0 1.52.85l12-7.4a1 1 0 0 0 0-1.7l-12-7.4A1 1 0 0 0 7 4.6Z" fill="currentColor" stroke="none"/>`,
  pause: `<rect x="6" y="4" width="4" height="16" rx="1.2" fill="currentColor" stroke="none"/><rect x="14" y="4" width="4" height="16" rx="1.2" fill="currentColor" stroke="none"/>`,
  plus: P("M12 5v14", "M5 12h14"),
  check: P("M20 6 9 17l-5-5"),
  x: P("M18 6 6 18", "m6 6 12 12"),
  trash: P("M3 6h18", "M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6", "m19 6-.8 13.2a2 2 0 0 1-2 1.8H7.8a2 2 0 0 1-2-1.8L5 6"),
  pencil: P("M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"),
  external: P("M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"),
  search: `<circle cx="11" cy="11" r="7"/>` + P("m20 20-3.5-3.5"),
  monitor: `<rect x="2" y="3" width="20" height="14" rx="2"/>` + P("M8 21h8", "M12 17v4"),
  phone: `<rect x="6" y="2" width="12" height="20" rx="2.5"/>` + P("M11 18h2"),
  mic: `<rect x="9" y="2" width="6" height="12" rx="3"/>` + P("M19 10v1a7 7 0 0 1-14 0v-1", "M12 18v4"),
  volume: P("M11 5 6 9H2v6h4l5 4z", "M15.5 8.5a5 5 0 0 1 0 7", "M19 5a10 10 0 0 1 0 14"),
  disc: `<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/>`,
  info: `<circle cx="12" cy="12" r="9"/>` + P("M12 8v4", "M12 16h.01"),
  arrow: P("M5 12h14", "m13 6 6 6-6 6"),
  sparkle: P("M12 3v4", "M12 17v4", "M3 12h4", "M17 12h4", "m6 6 2 2", "m16 16 2 2", "m6 18 2-2", "m16 8 2-2"),
  archive: `<rect x="3" y="4" width="18" height="5" rx="1.5"/>` + P("M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9", "M10 13h4"),
  download: P("M12 4v12", "m7 11 5 5 5-5", "M5 20h14"),
  upload: P("M12 20V8", "m7 13 5-5 5 5", "M5 4h14"),
  folder: P("M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"),
  restore: P("M3 12a9 9 0 1 0 3-6.7L3 8", "M3 3v5h5", "M12 8v4l3 2"),
  key: `<circle cx="8" cy="15" r="4"/>` + P("m10.8 12.2 9.2-9.2", "m17 6 3 3", "m14 9 2 2"),
  chevron: P("m9 6 6 6-6 6"),
  chat: P("M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z", "M8.5 12h.01", "M12 12h.01", "M15.5 12h.01"),
  shuffle: P("m18 14 4 4-4 4", "m18 2 4 4-4 4", "M2 18h1.4a4 4 0 0 0 3.3-1.7l6.6-9.6A4 4 0 0 1 16.6 5H22", "M2 6h1.4a4 4 0 0 1 3.1 1.5", "M22 19h-5.4a4 4 0 0 1-3.1-1.5"),
  repeat: P("m17 2 4 4-4 4", "M3 11v-1a4 4 0 0 1 4-4h14", "m7 22-4-4 4-4", "M21 13v1a4 4 0 0 1-4 4H3"),
  tag: P("M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9Z", "M7.5 7.5h.01"),
  copy: P("M9 9h11v11H9z", "M5 15H4V4h11v1"),
  share: P("M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "m8.6 13.5 6.8 4", "m15.4 6.5-6.8 4"),
};
const icon = (n, cls = "") => `<i data-icon="${n}" class="${cls}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${ICONS[n] || ""}</svg></i>`;
function hydrateIcons(root = document) {
  $$("i[data-icon]:not(:has(svg))", root).forEach(el => { el.outerHTML = icon(el.dataset.icon, el.className); });
}

/* ================================================================= Genre-Farben */
const GENRE_COLORS = {
  "Drum & Bass": "#d9a65e", "Dubstep": "#a495ef", "House": "#5fbccb", "Techno": "#91a2bb",
  "UK Garage / Bass": "#df93ae", "Trance": "#7aa9ea", "Hardstyle / Hardcore": "#e3826f",
  "Trap / Future Bass": "#e6c56d", "Breakbeat": "#9ec97b", "Hip-Hop": "#cfb18c", "Pop": "#e99acb",
  "Rock / Metal": "#c97676", "Ambient / Chill": "#86cdd3",
  "Breakcore": "#e07ab8", "Phonk": "#b07de0", "Hyperpop": "#f08fd9", "Synthwave": "#d47cf0", "IDM / Experimental": "#a8b46f",
  "R&B / Soul": "#d99a7a", "Indie / Alternative": "#9bb7a0", "Latin": "#efa25f", "Reggae / Dancehall": "#7fc27a",
  "Jazz / Funk": "#c9a86a", "Country / Folk": "#b9a079", "Classical / Cinematic": "#a7b8d8", "Electronic": "#8fa3b3",
};
function hexToHsl(hex) {
  const n = parseInt(hex.slice(1), 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2;
  if (mx === mn) return [0, 0, l * 100];
  const d = mx - mn, s = l > .5 ? d / (2 - mx - mn) : d / (mx + mn);
  const h = mx === r ? (g - b) / d + (g < b ? 6 : 0) : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
  return [h * 60, s * 100, l * 100];
}
function strHash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h); }
let TAXONOMY = {};
function genreColor(genre, sub) {
  const base = GENRE_COLORS[genre];
  if (!base) return genre ? `hsl(${strHash(genre) % 360} 35% 62%)` : "#6b717c";
  if (!sub) return base;
  // Subgenres: gleiche Farbfamilie, aber klar unterscheidbar (Fächer von ±40° um den Grundton)
  const subs = TAXONOMY[genre] || [];
  let i = subs.indexOf(sub), n = subs.length;
  if (i < 0) { i = strHash(sub) % 5; n = 5; }
  const [h, s, l] = hexToHsl(base);
  const t = n > 1 ? i / (n - 1) - 0.5 : 0;        // -0.5..0.5
  return `hsl(${(h + t * 44 + 360) % 360} ${Math.max(30, s - (i % 3) * 10)}% ${l + [0, 9, -6][i % 3]}%)`;
}
const genreChip = (g, s) => g ? `<span class="chip chip--genre" style="--g:${genreColor(g, s)}"><span class="dot" style="background:var(--g)"></span>${esc(s ? s : g)}</span>` : `<span class="chip">Genre unbekannt</span>`;

/* ================================================================= State */
const S = {
  status: null, sources: [], playlists: [],
  prefs: null,
  listen: {
    source: "desktop", mode: "desktop", seconds: 10,
    auto: false, running: false, busy: false, started: 0, msg: null, lastKey: null, current: null, similar: null,
  },
};

/* ================================================================= Toasts */
function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = "toast" + (kind === "err" ? " err" : "");
  el.innerHTML = icon(kind === "err" ? "info" : "check") + `<span>${esc(msg)}</span>`;
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 250); }, kind === "err" ? 5000 : 2600);
}


/* ================================================================= Neue Oberfläche erkennen
   Läuft die App weiter, während die Oberfläche (app.js/app.css) aktualisiert wurde, zeigt das Fenster sonst
   bis zum Neustart die alte Version. Prüft beim Zurückholen des Fensters und alle 2 Minuten – nur lokal. */
const AssetWatch = {
  mine: (document.querySelector('script[src*="app.js"]')?.src.match(/[?&]v=([\w]+)/) || [])[1],
  shown: false,
  start() {
    if (!this.mine) return;
    const check = () => this.check();
    document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
    window.addEventListener("focus", check);
    setInterval(check, 120000);
  },
  async check() {
    if (this.shown) return;
    const r = await api("/api/asset-version").catch(() => null);
    if (!r?.v || r.v === this.mine) return;
    this.shown = true;
    const el = document.createElement("div");
    el.className = "toast asset-toast";
    el.innerHTML = `${icon("info")}<span>Neue Version der Oberfläche</span><button class="btn btn--sm btn--primary">Neu laden</button>`;
    $("button", el).onclick = () => location.reload();
    $("#toasts").append(el);
  },
};

/* ================================================================= Zwischenablage & Rechtsklick-Menü
   Das App-Fenster (pywebview) hat kein eigenes Rechtsklick-Menü – deshalb ein eigenes für Eingabefelder,
   markierten Text und Links. Gelesen wird die Zwischenablage nur auf Klick („Einfügen“). */
const Clip = {
  async read() {
    try { const r = await api("/api/clipboard/read", { method: "POST" }); if (r.text) return r.text; } catch { /* weiter */ }
    try { if (navigator.clipboard?.readText) return await navigator.clipboard.readText(); } catch { /* keine Erlaubnis */ }
    return "";
  },
  async write(text) {
    try { if ((await api("/api/clipboard/write", { method: "POST", body: { text } })).ok) return true; } catch { /* weiter */ }
    try { await navigator.clipboard.writeText(text); return true; } catch { /* weiter */ }
    const ta = document.createElement("textarea"); ta.value = text; document.body.append(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  },
  insert(el, text) {
    el.focus();
    const a = el.selectionStart ?? el.value.length, b = el.selectionEnd ?? a;
    el.setRangeText(text, a, b, "end");
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new CustomEvent("tb-paste", { bubbles: true }));
  },
};
const firstUrl = t => (String(t).match(/https?:\/\/[^\s<>"']+/) || [String(t).trim()])[0];
const CtxMenu = {
  el: null,
  close() { this.el?.remove(); this.el = null; },
  open(x, y, items) {
    this.close();
    if (!items.length) return;
    const m = document.createElement("div");
    m.className = "ctx";
    m.innerHTML = items.map((it, i) => it === "-" ? `<div class="ctx-sep"></div>`
      : `<button data-i="${i}" ${it.off ? "disabled" : ""}>${icon(it.icon)}<span>${esc(it.label)}</span>${it.key ? `<kbd>${it.key}</kbd>` : ""}</button>`).join("");
    document.body.append(m);
    const r = m.getBoundingClientRect();
    m.style.left = `${Math.min(x, innerWidth - r.width - 6)}px`;
    m.style.top = `${Math.min(y, innerHeight - r.height - 6)}px`;
    m.onmousedown = e => e.preventDefault();           // Fokus/Markierung im Feld behalten
    $$("button[data-i]", m).forEach(b => b.onclick = async () => { const it = items[+b.dataset.i]; this.close(); await it.run(); });
    this.el = m;
  },
};
if (window.pywebview || /QtWebEngine/.test(navigator.userAgent)) {
  document.addEventListener("contextmenu", e => {
    const ed = e.target.closest("input:not([type=checkbox]):not([type=range]):not([type=file]):not([type=radio]), textarea, [contenteditable=true]");
    const link = e.target.closest("a[href^='http']");
    const sel = String(getSelection() || "");
    const items = [];
    if (ed && !ed.isContentEditable) {
      const has = ed.selectionStart !== ed.selectionEnd, ro = ed.readOnly || ed.disabled;
      const part = () => ed.value.slice(ed.selectionStart, ed.selectionEnd);
      items.push({ label: "Ausschneiden", icon: "x", key: "Strg+X", off: !has || ro, run: async () => { await Clip.write(part()); ed.setRangeText("", ed.selectionStart, ed.selectionEnd, "end"); ed.dispatchEvent(new Event("input", { bubbles: true })); } },
        { label: "Kopieren", icon: "stack", key: "Strg+C", off: !has, run: () => Clip.write(part()) },
        { label: "Einfügen", icon: "download", key: "Strg+V", off: ro, run: async () => { const t = await Clip.read(); t ? Clip.insert(ed, t) : toast("Zwischenablage ist leer", "err"); } },
        "-", { label: "Alles markieren", icon: "check", key: "Strg+A", run: () => { ed.focus(); ed.select(); } });
    } else {
      if (sel.trim()) items.push({ label: "Kopieren", icon: "stack", key: "Strg+C", run: () => Clip.write(sel) });
      if (link) items.push({ label: "Link öffnen", icon: "external", run: () => IN_APP_WINDOW() ? openExternal(link.href) : window.open(link.href, "_blank", "noopener") },
        { label: "Link kopieren", icon: "stack", run: async () => { await Clip.write(link.href); toast("Link kopiert"); } });
    }
    e.preventDefault();
    CtxMenu.open(e.clientX, e.clientY, items);
  });
  ["mousedown", "scroll", "blur", "resize"].forEach(ev => window.addEventListener(ev, e => { if (!e.target?.closest?.(".ctx")) CtxMenu.close(); }, true));
  document.addEventListener("keydown", e => { if (e.key === "Escape") CtxMenu.close(); });
  // Strg+R / F5: Das Qt-Fenster lädt sonst nie neu (z. B. nach einem Update der Oberfläche)
  document.addEventListener("keydown", e => {
    if (e.key === "F5" || ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "r")) { e.preventDefault(); location.reload(); }
  });
  AssetWatch.start();
  // Strg+V / Umschalt+Einfg: Das Qt-Fenster fügt nicht immer selbst ein – kommt kein „paste“, holt die App den Text
  let pasted = false;
  document.addEventListener("paste", () => { pasted = true; }, true);
  document.addEventListener("keydown", e => {
    const ed = e.target.closest?.("input:not([type=checkbox]):not([type=range]):not([type=file]), textarea");
    const combo = ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === "v") || (e.shiftKey && e.key === "Insert");
    if (!ed || !combo || ed.readOnly || ed.disabled) return;
    pasted = false;
    setTimeout(async () => { if (pasted) return; const t = await Clip.read(); if (t) Clip.insert(ed, t); }, 120);
  }, true);
}

/* ================================================================= Player */
const Player = {
  audio: null, track: null, queue: [], qi: -1,
  init() {
    this.audio = $("#audio");
    const vol = store.get("volume", 0.8);
    this.audio.volume = vol; $("#pVol").value = vol;
    $("#pVol").oninput = e => { this.audio.volume = +e.target.value; store.set("volume", +e.target.value); };
    $("#pPlay").onclick = () => this.toggle();
    $("#pPrev").onclick = () => this.prev();
    $("#pNext").onclick = () => this.skip();
    $("#pBar").onclick = e => {
      if (!this.audio.duration) return;
      const r = e.currentTarget.getBoundingClientRect();
      this.audio.currentTime = ((e.clientX - r.left) / r.width) * this.audio.duration;
    };
    this.audio.ontimeupdate = () => {
      const d = this.audio.duration || 30;
      $("#pFill").style.width = `${(this.audio.currentTime / d) * 100}%`;
      $("#pCur").textContent = fmtTime(this.audio.currentTime);
      $("#pDur").textContent = fmtTime(d);
    };
    ["play", "pause", "ended"].forEach(ev => this.audio.addEventListener(ev, () => this.sync()));
    this.audio.addEventListener("ended", () => this.next());
    this.audio.addEventListener("playing", () => DiscordUI.preview(this.track));
    this.audio.addEventListener("pause", () => { if (!this.audio.ended || this.qi < 0) DiscordUI.preview(null); });
    this.audio.onerror = () => {
      if (!this.track) return;
      if (this.qi >= 0) return this.next();
      if (Fallback.offerFor(this.track)) return;
      toast("Für diesen Song gibt es gerade keine Hörprobe", "err");
      $("#pTitle").textContent = this.track.title;
    };
  },
  // Hörproben nacheinander (Playlist „Abspielen“/„Zufall“) – jede wird einzeln frisch vom Anbieter gestreamt
  playList(list, shuffle = false) {
    const l = list.filter(t => t?.preview_url);
    if (!l.length) return toast("Keine Hörproben in dieser Liste", "err");
    if (shuffle) for (let i = l.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [l[i], l[j]] = [l[j], l[i]]; }
    this.queue = l; this.qi = 0; this.track = null;
    this.play(l[0], true);
  },
  // Ende einer Hörprobe: nächster Song der Liste; am Listenende stoppen (Liste bleibt für Zurück erhalten)
  next() {
    if (this.qi < 0 || this.qi + 1 >= this.queue.length) { DiscordUI.preview(null); return this.nav(); }
    this.qi++; this.track = null;
    this.play(this.queue[this.qi], true);
  },
  skip() {
    if (this.qi < 0 || this.qi + 1 >= this.queue.length) return toast("Kein weiterer Song in dieser Liste");
    this.next();
  },
  prev() {
    if (!this.track) return;
    if (this.audio.currentTime > 3 || this.qi <= 0) { this.audio.currentTime = 0; return this.audio.play().catch(() => {}); }
    this.qi--; this.track = null;
    this.play(this.queue[this.qi], true);
  },
  nav() {
    $("#pPrev").disabled = !this.track;
    $("#pNext").disabled = !(this.qi >= 0 && this.qi + 1 < this.queue.length);
  },
  play(t, fromQueue = false, context = null) {
    if (!t?.preview_url) return toast("Für diesen Song gibt es keine Hörprobe", "err");
    if (this.track?.preview_url === t.preview_url) return this.toggle();
    if (!fromQueue) {   // einzelner Klick: Liste = alle Songs dieser Ansicht (für Vor/Zurück), sonst laufende Liste
      if (context?.length > 1) { this.queue = context; }
      const i = this.queue.findIndex(x => x.preview_url === t.preview_url);
      this.qi = i; if (i < 0) this.queue = [];
    }
    this.countAudio();
    this.track = t;
    const q = new URLSearchParams({ a: (t.artists || [])[0] || "", t: t.title || "" });
    if (!t.preview_url.startsWith("deezer:")) q.set("u", t.preview_url);   // sonst: Hörprobe bei Deezer suchen
    if (t.isrc) q.set("isrc", t.isrc);
    if (t.ids?.deezer) q.set("dz", t.ids.deezer);
    // AAC (Apple-Hörproben) kann nicht jedes Fenster abspielen – dann sucht der Server die Deezer-Hörprobe
    if (this.audio.canPlayType('audio/mp4; codecs="mp4a.40.2"')) q.set("aac", "1");
    $("#pTitle").textContent = "Lade Hörprobe …";
    const src = $("#pSrc"); src.classList.add("hidden");
    api(`/api/preview?${q}`).then(r => {
      if (this.track !== t) return;
      this.audio.src = r.url;                 // direkt vom Anbieter streamen – nichts wird gespeichert
      this.audio.play().catch(() => {});
      const s = PREVIEW_SRC[r.source];
      if (s) { src.textContent = s.text; src.href = s.link(t); src.classList.remove("hidden"); }
    }).catch(() => {
      if (this.track !== t) return;
      if (this.qi >= 0) return this.next();
      $("#pTitle").textContent = t.title;
      if (Fallback.offerFor(t)) return;
      toast("Für diesen Song gibt es gerade keine Hörprobe", "err");
    });
    this.audio.addEventListener("playing", () => { $("#pTitle").textContent = t.title; }, { once: true });
    $("#pArtist").textContent = (t.artists || []).join(", ");
    $("#pCover").style.backgroundImage = t.cover ? `url("${t.cover}")` : "";
    $("#pPlay").disabled = false;
    this.nav();
  },
  // Datenverbrauch: geladene Sekunden × 128 kbit/s (Hörproben sind MP3/AAC um 128–256 kbit/s) – Schätzung
  countAudio() {
    try {
      const a = this.audio, b = a.buffered;
      if (a.src && b.length) Traffic.note(new URL(a.src).host, b.end(b.length - 1) * 16000, true);
    } catch { /* nichts geladen */ }
  },
  toggle() { if (!this.track) return; this.audio.paused ? this.audio.play().catch(() => {}) : this.audio.pause(); },
  isPlaying(url) { return url && this.track?.preview_url === url && !this.audio.paused; },
  sync() {
    $("#pPlay").innerHTML = icon(this.audio.paused ? "play" : "pause");
    $$("[data-play-url]").forEach(b => {
      const on = this.isPlaying(b.dataset.playUrl);
      b.classList.toggle("playing", on);
      const i = b.querySelector("i[data-icon]");
      if (i && i.dataset.icon !== (on ? "pause" : "play")) i.outerHTML = icon(on ? "pause" : "play");
    });
  },
};
// Pflicht-Hinweise der Anbieter (Apple: „provided courtesy of iTunes“ + Link in den Store; Deezer/Spotify: Quelle + Link)
const _q = t => encodeURIComponent(`${(t.artists || [])[0] || ""} ${t.title || ""}`.trim());
const PREVIEW_SRC = {
  deezer: { text: "Hörprobe: Deezer", link: t => t.ids?.deezer ? `https://www.deezer.com/track/${t.ids.deezer}` : `https://www.deezer.com/search/${_q(t)}` },
  apple: { text: "Hörprobe provided courtesy of iTunes", link: t => `https://music.apple.com/search?term=${_q(t)}` },
  spotify: { text: "Hörprobe: Spotify", link: t => t.ids?.spotify ? `https://open.spotify.com/track/${t.ids.spotify}` : `https://open.spotify.com/search/${_q(t)}` },
};
// Quelle eines Covers aus der Bildadresse (die App lädt Cover nur direkt beim Anbieter, speichert keine Bilder)
const COVER_HOSTS = [[/scdn\.co|spotifycdn/, "Spotify", t => t.ids?.spotify ? `https://open.spotify.com/track/${t.ids.spotify}` : `https://open.spotify.com/search/${_q(t)}`],
  [/dzcdn|deezer/, "Deezer", t => t.ids?.deezer ? `https://www.deezer.com/track/${t.ids.deezer}` : `https://www.deezer.com/search/${_q(t)}`],
  [/mzstatic|apple/, "Apple Music", t => `https://music.apple.com/search?term=${_q(t)}`],
  [/ytimg|youtube|ggpht/, "YouTube", t => t.ids?.youtube ? `https://www.youtube.com/watch?v=${t.ids.youtube}` : `https://www.youtube.com/results?search_query=${_q(t)}`],
  [/tidal/, "TIDAL", t => `https://tidal.com/search?q=${_q(t)}`],
  [/coverartarchive|musicbrainz/, "Cover Art Archive", () => "https://coverartarchive.org/"],
  [/lastfm|last\.fm|fastly/, "Last.fm", t => `https://www.last.fm/search?q=${_q(t)}`],
  [/sndcdn|soundcloud/, "SoundCloud", t => `https://soundcloud.com/search?q=${_q(t)}`]];
function coverSrc(t) {
  const hit = t?.cover && COVER_HOSTS.find(([re]) => re.test(t.cover));
  return hit ? `<a class="cover-src" href="${esc(hit[2](t))}" target="_blank" rel="noopener noreferrer" title="Bild vom Anbieter geladen, nicht gespeichert">Cover: ${hit[1]}</a>` : "";
}
// Externe Links im Desktop-Fenster: selbst im Standard-Browser öffnen (Qt/pywebview verschluckt sie je nach System)
const IN_APP_WINDOW = () => !!window.pywebview || navigator.userAgent.includes("QtWebEngine");
async function openExternal(url) {
  try {
    const r = await fetch("/api/open", { method: "POST", headers: { "Content-Type": "application/json", "X-Tunebridge": "1" }, body: JSON.stringify({ url }) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  } catch (e) {
    toast(`Browser ließ sich nicht öffnen – Link kopiert`, "err");
    Clip?.write?.(url);
  }
}
document.addEventListener("click", e => {
  const a = e.target.closest("a[href]");
  if (!a || e.defaultPrevented || !IN_APP_WINDOW()) return;
  const href = a.getAttribute("href");
  if (!/^https?:\/\//i.test(href)) return;
  e.preventDefault();
  openExternal(a.href);
}, true);
// Play-Buttons überall: data-play='{"preview_url":…}' – Delegation
document.addEventListener("click", e => {
  const b = e.target.closest("[data-play]");
  if (!b) return;
  e.stopPropagation();
  // Warteschlange für Vor/Zurück: alle Play-Knöpfe im selben Bereich (Dialog oder Seite), in Reihenfolge, ohne Doppelte
  const scope = b.closest("#modalBox, #drawerBody, #main") || document;
  const seen = new Set(), ctx = [];
  $$("[data-play]", scope).forEach(x => { try { const t = JSON.parse(x.dataset.play); if (t.preview_url && !seen.has(t.preview_url)) { seen.add(t.preview_url); ctx.push(t); } } catch { /* kaputt */ } });
  Player.play(JSON.parse(b.dataset.play), false, ctx);
});
const playAttr = t => t.preview_url
  ? `data-play="${esc(JSON.stringify({ title: t.title, artists: t.artists, cover: t.cover, preview_url: t.preview_url, isrc: t.isrc || null, ids: t.ids || {} }))}" data-play-url="${esc(t.preview_url)}"`
  : "disabled";

/* ================================================================= Sidebar */
async function loadPrefs() {
  const p = await api("/api/prefs").catch(() => null);
  if (!p) return;
  S.prefs = p;
  const L = S.listen;
  L.mode = p.mode; L.seconds = p.seconds;
  L.source = p[`device_${p.mode}`] || p.mode;
  if (p.missing.includes(`device_${p.mode}`)) {
    toast("Gespeichertes Gerät ist gerade nicht angeschlossen – nutze Standard", "err");
    L.source = p.mode;
  }
}
function savePrefs(patch) {
  if (S.prefs) Object.assign(S.prefs, patch);
  api("/api/prefs", { method: "POST", body: patch }).catch(e => toast(e.message, "err"));
}

async function refreshMeta() {
  const [st, pls] = await Promise.all([api("/api/status"), api("/api/playlists")]);
  S.status = st; S.playlists = pls; TAXONOMY = st.taxonomy || {};
  $("#cntHistory").textContent = st.stats.recognitions || "";
  $("#cntPlaylists").textContent = pls.length || "";
  Inbox.badge();
  const sideBy = store.get("sideSort", "");
  if ($("#sideSort")) $("#sideSort").title = `Playlists sortieren – jetzt: ${PL_SORTS.find(x => x[0] === sideBy)?.[1] || "A–Z"}`;
  const local = sortPlaylists(pls.filter(p => p.origin === "lokal"), sideBy);
  $("#sidePlaylists").innerHTML = local.length ? local.map(p => {
    const top = p.top?.[0];
    return `<a href="#/playlists/${enc(p.name)}" data-pl="${esc(p.name)}"><span class="dot" style="background:${top ? genreColor(top[2], top[3]) : "var(--bg-4)"}"></span>
      <span>${esc(p.name)}</span><em>${p.count}</em></a>`;
  }).join("") : `<div class="side-empty">Noch keine Playlists. Sie entstehen, sobald du einen Song einsortierst.</div>`;
  $("#plnames").innerHTML = pls.map(p => `<option value="${esc(p.name)}">`).join("");
  const engs = ["shazam", "audd", "acrcloud"];
  $("#machine").innerHTML = `<span>${esc(st.host)}</span><span class="engines" title="Erkennungsdienste: ${engs.map(e => e + (st.engines.includes(e) ? " ✓" : " –")).join(", ")}">
    ${engs.map(e => `<span class="eng ${st.engines.includes(e) ? "on" : ""}"></span>`).join("")}</span>`;
  markNav();
}

/* Playlists sortieren: "" = A–Z, za, count (Größe), updated (zuletzt geändert), created (neueste zuerst) */
function sortPlaylists(list, by) {
  const l = [...list], abc = (a, b) => a.name.localeCompare(b.name, "de", { sensitivity: "base", numeric: true });
  const f = { za: (a, b) => -abc(a, b), count: (a, b) => (b.count || 0) - (a.count || 0) || abc(a, b),
    updated: (a, b) => (b.updated || 0) - (a.updated || 0) || abc(a, b), created: (a, b) => (b.created || 0) - (a.created || 0) || abc(a, b) }[by] || abc;
  return l.sort(f);
}
const PL_SORTS = [["", "Name A–Z"], ["za", "Name Z–A"], ["count", "Größe"], ["updated", "Zuletzt geändert"], ["created", "Neueste zuerst"]];
$("#sideSort")?.addEventListener("click", e => {
  e.stopPropagation();
  const cur = store.get("sideSort", ""), r = e.currentTarget.getBoundingClientRect();
  CtxMenu.open(r.left, r.bottom + 4, PL_SORTS.map(([v, l]) => ({ icon: v === cur ? "check" : "dot", label: l, run: () => { store.set("sideSort", v); refreshMeta(); } })));
});

function markNav() {
  const h = location.hash || "#/listen";
  const base = /[?&]svc=friend-/.test(h) ? "#/share" : h.split("?")[0];
  $$(".nav a, .foot-link").forEach(a => a.classList.toggle("active", base === a.getAttribute("href")));
  $$("#sidePlaylists a").forEach(a => a.classList.toggle("active", base === a.getAttribute("href")));
  $$("#sideServices a").forEach(a => a.classList.toggle("active", h === a.getAttribute("href")));
}

/* Seitenleiste „Deine Dienste“: verbundene Konten/Profile untereinander, aufklappbar bis zu den Playlists */
const SideSvc = {
  list: [], pls: {}, loaded: false, open: store.get("sideSvcOpen", {}),
  async load(list) {
    try { list = list || await api("/api/services"); } catch { list = []; }
    this.list = list.filter(s => s.ready && s.account && s.kind !== "file");
    this.loaded = true;
    this.render();
    this.list.filter(s => this.open[s.id]).forEach(s => this.fetch(s.id));
  },
  async fetch(sid, fresh = false) {
    if (Array.isArray(this.pls[sid]) && !fresh) return this.pls[sid];
    if (this.pls[sid] instanceof Promise) return this.pls[sid];
    const job = api(`/api/services/${sid}/playlists${fresh ? "?refresh=1" : ""}`);
    this.pls[sid] = job; this.render();
    try { this.pls[sid] = await job; } catch (e) { this.pls[sid] = { error: e.message }; }
    this.render();
    return this.pls[sid];
  },
  render() {
    const box = $("#sideServices"); if (!box) return;
    $("#sideSvcLabel").classList.toggle("hidden", !this.list.length);
    box.innerHTML = this.list.map(s => {
      const [m, c] = svcStyle(s.id), open = !!this.open[s.id], pl = this.pls[s.id];
      const inner = !open ? "" : !pl || pl instanceof Promise ? `<div class="ss-hint">Lade Playlists …</div>`
        : pl.error ? `<div class="ss-hint">${esc(pl.error)}</div>`
        : pl.length ? pl.map(p => `<a href="${svcPlHref(s.id, p)}" title="${esc(p.name)}"><span>${esc(p.name)}</span>${p.count != null ? `<em>${p.count}</em>` : ""}</a>`).join("")
        : `<div class="ss-hint">Keine Playlists</div>`;
      return `<div class="ss ${open ? "open" : ""}" style="--pc:${c}"><div class="ss-row">
        <a class="ss-main" href="#/services?svc=${s.id}" title="${esc(s.name)} · ${esc(s.account)}"><span class="ss-badge">${m}</span><span class="ss-name">${esc(s.name)}</span></a>
        <button class="ss-caret" data-ss="${s.id}" aria-label="Playlists auf-/zuklappen" title="Playlists">${icon("chevron")}</button></div>
        <div class="ss-pls">${inner}</div></div>`;
    }).join("");
    $$("[data-ss]", box).forEach(b => b.onclick = () => {
      const id = b.dataset.ss; this.open[id] = !this.open[id]; store.set("sideSvcOpen", this.open);
      if (this.open[id]) this.fetch(id); else this.render();
    });
    markNav();
  },
};
const svcPlHref = (sid, p) => `#/services?svc=${sid}&view=${encodeURIComponent(p.id)}&name=${encodeURIComponent(p.name)}`;

/* ================================================================= Track-Detail (wiederverwendbar) */
function coverHtml(t, size = "") {
  const img = t.cover ? `<img class="cover" src="${esc(t.cover)}" alt="">` : `<div class="cover cover--ph">${icon("disc")}</div>`;
  return `<div class="cover-col"><div class="cover-wrap ${size}">${img}${t.preview_url ? `<button class="cover-play" ${playAttr(t)} aria-label="Hörprobe">${icon("play")}</button>` : ""}</div>${coverSrc(t)}</div>`;
}

/* Hinweis nur als Icon – der Text erscheint beim Drüberfahren (oder per Tastatur-Fokus) */
const tip = (text, ic = "info") => `<span class="tip" tabindex="0" role="note" aria-label="${esc(text)}" data-tip="${esc(text)}">${icon(ic)}</span>`;
const Tip = {
  el: null,
  show(t) {
    if (!this.el) { this.el = document.createElement("div"); this.el.className = "tip-pop"; document.body.append(this.el); }
    this.el.textContent = t.dataset.tip; this.el.classList.add("on");
    const r = t.getBoundingClientRect(), w = this.el.offsetWidth, h = this.el.offsetHeight;
    const x = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2));
    const y = r.top - h - 8 < 8 ? r.bottom + 8 : r.top - h - 8;
    this.el.style.left = `${x}px`; this.el.style.top = `${y}px`;
  },
  hide() { this.el?.classList.remove("on"); },
};
document.addEventListener("mouseover", e => { const t = e.target.closest?.(".tip"); if (t) Tip.show(t); });
document.addEventListener("mouseout", e => { if (e.target.closest?.(".tip")) Tip.hide(); });
document.addEventListener("focusin", e => { const t = e.target.closest?.(".tip"); if (t) Tip.show(t); });
document.addEventListener("focusout", e => { if (e.target.closest?.(".tip")) Tip.hide(); });

/* Song-Ansicht (Erkennen & Song-Details): Reihenfolge der Bereiche und ausgeblendete Bereiche – gemerkt pro Rechner */
const SongLayout = {
  SECS: [["links", "Anhören & öffnen", "external"], ["buy", "Kaufen", "download"], ["player", "Offizieller Player", "play"],
    ["artist", "Mehr vom Künstler", "disc"], ["ai", "KI-Musik-Hinweis", "sparkle"], ["sort", "Einsortieren", "stack"],
    ["similar", "Ähnliche Songs", "compass"], ["versions", "Remixe & Versionen", "disc"], ["mix", "Passt dazu – zum Mixen", "shuffle"]],
  get() {
    const d = store.get("songLayout", {}) || {}, ids = this.SECS.map(x => x[0]);
    const order = (Array.isArray(d.order) ? d.order : []).filter(id => ids.includes(id));
    return { order: [...order, ...ids.filter(id => !order.includes(id))], hidden: (Array.isArray(d.hidden) ? d.hidden : []).filter(id => ids.includes(id)) };
  },
  render(parts) {
    const l = this.get();
    // ausgeblendet = nicht sichtbar, bleibt aber im Dokument (die Knöpfe darin werden weiter verdrahtet)
    return l.order.filter(id => parts[id]).map(id => `<div class="lsec" data-sec="${id}" ${l.hidden.includes(id) ? "hidden" : ""}>${parts[id]}</div>`).join("");
  },
  dialog(onSave) {
    let l = this.get();
    const draw = box => {
      const name = id => this.SECS.find(x => x[0] === id);
      $("#slList", box).innerHTML = l.order.map((id, i) => `<li class="sl-row ${l.hidden.includes(id) ? "off" : ""}">
        ${icon(name(id)[2])}<span>${esc(name(id)[1])}</span>
        <button class="icon-btn" data-up="${i}" ${i === 0 ? "disabled" : ""} aria-label="Nach oben" title="Nach oben">${icon("chevron")}</button>
        <button class="icon-btn sl-down" data-down="${i}" ${i === l.order.length - 1 ? "disabled" : ""} aria-label="Nach unten" title="Nach unten">${icon("chevron")}</button>
        <label class="switch" title="Anzeigen"><input type="checkbox" data-show="${id}" ${l.hidden.includes(id) ? "" : "checked"}><span class="track"></span></label></li>`).join("");
      hydrateIcons(box);
      const mv = (i, d) => { const o = l.order; [o[i], o[i + d]] = [o[i + d], o[i]]; draw(box); };
      $$("[data-up]", box).forEach(b => b.onclick = () => mv(+b.dataset.up, -1));
      $$("[data-down]", box).forEach(b => b.onclick = () => mv(+b.dataset.down, 1));
      $$("[data-show]", box).forEach(c => c.onchange = () => {
        l.hidden = c.checked ? l.hidden.filter(x => x !== c.dataset.show) : [...l.hidden, c.dataset.show]; draw(box);
      });
    };
    modal({ title: "Ansicht anpassen", confirm: "Speichern",
      body: `<p class="cell-sub sl-intro" style="margin:0 0 10px">Reihenfolge der Bereiche unter dem Song (Erkennen und Song-Details). Was du ausschaltest, wird nicht angezeigt.</p>
        <ul class="sl-list" id="slList"></ul><button class="btn btn--sm btn--ghost" id="slReset" style="margin-top:10px">${icon("repeat")}Standard wiederherstellen</button>`,
      onConfirm: () => { store.set("songLayout", l); toast("Ansicht gespeichert"); onSave?.(); } });
    const box = $("#modalBox"); draw(box);
    $("#slReset", box).onclick = () => { l = { order: this.SECS.map(x => x[0]), hidden: [] }; draw(box); };
  },
};

function detailHtml(r) {
  const t = r.track, x = r.extra || {};
  const meta = [t.album, x.label, x.year].filter(Boolean).map(esc).join("  ·  ");
  const chips = [t.genre || !t.niche ? genreChip(t.genre, null) : "", t.subgenre ? genreChip(t.genre, t.subgenre) : "",
    t.niche ? `<span class="chip chip--niche" title="Spezifischstes Genre (Katalog mit ~6 400 Genres)" style="--g:${genreColor(t.genre, t.subgenre || t.niche)}"><span class="dot" style="background:var(--g)"></span>${esc(t.niche)}</span>` : "",
    x.bpm ? `<span class="chip num">${Math.round(x.bpm)} BPM</span>` : "",
    x.genre_source === "bpm" ? `<span class="chip chip--warn">Genre über BPM geschätzt</span>` : "",
    x.genre_source === "llm" ? `<span class="chip chip--warn">Subgenre vom LLM</span>` : "",
    x.genre_source === "llm_genre" ? `<span class="chip chip--warn">Genre vom LLM geschätzt</span>` : "",
    t.genre === "Electronic" ? `<span class="chip chip--warn">nur grob bekannt</span>` : "",
    x.genre_source === "eigene Einordnung" ? `<span class="chip chip--own" title="Von dir festgelegt – gilt vor allem anderen">${icon("check")}deine Einordnung</span>` : "",
    x.genre_source === "Gemeinschafts-Datenbank" ? `<span class="chip chip--own" title="Aus der Gemeinschafts-Datenbank (signiert, ${x.genredb?.votes || "mehrere"} Stimmen)">${icon("stack")}Gemeinschaft</span>` : "",
    aiChip(x.ai),
    x.version ? `<span class="chip chip--version" title="${x.speed ? "Erst nach Tempo-Korrektur erkannt – angezeigt wird das Original" : "Version laut Titel – Genre & Empfehlungen vom Original"}">${icon("wave")}${esc(x.version)}</span>` : ""].join("");
  const links = x.links?.shazam ? `<a class="btn btn--sm btn--ghost" href="${esc(x.links.shazam)}" target="_blank" rel="noopener">${icon("external")}Shazam</a>` : "";
  const engines = x.engines?.length ? `Erkannt von ${x.engines.map(linkName).join(", ")}${x.agreement > 1 ? ` · ${x.agreement} Dienste einig` : ""}` : "";
  const origin = x.local ? `Lokal wiedererkannt – keine Online-Abfrage` : x.cached ? `Infos aus dem Song-Speicher (Stand ${new Date(x.cached * 1000).toLocaleDateString("de-DE")}) – keine Online-Abfrage` : "";

  const sugs = (r.suggestions || []).map(s => sugRow(s, r.in_playlists.includes(s.playlist))).join("");
  const extra = r.in_playlists.filter(p => !(r.suggestions || []).some(s => s.playlist === p))
    .map(p => sugRow({ playlist: p, score: null, reason: "bereits einsortiert" }, true)).join("");

  const fresh = r.id != null && location.hash.startsWith("#/listen") && !x.confirmed;
  const unsure = r.id != null && x.unsure ? `<div class="notice unsure-box">${icon("info")}<div><b>Unsicherer Treffer.</b> Nur Shazam hat ihn gefunden – und nur mit Tempo-Abweichung. Das passiert bei Slowed-/Sped-up-Versionen oder wenn ein ähnlicher Song gemeint ist. Stimmt das?
      <div class="btn-row"><button class="btn btn--sm btn--primary" data-verdict="1" title="Merkt sich diese Stelle lokal – nächstes Mal ohne Shazam-Anfrage">${icon("check")}Stimmt</button><button class="btn btn--sm btn--ghost" data-verdict="0" title="Aus dem Verlauf entfernen">Falsch</button></div></div></div>` : "";
  return `${unsure}
  <div class="track-hero">
    ${coverHtml(t)}
    <div style="min-width:0">
      ${engines || origin || x.alternatives?.length ? `<div class="track-kicker">${esc(engines)}${origin ? tip(origin, "check") : ""}${x.alternatives?.length ? tip(`Andere Dienste meinten: ${x.alternatives.join("; ")}`, "info") : ""}</div>` : ""}
      <h2 class="track-title">${esc(t.title)}</h2>
      <p class="track-artist">${esc(t.artists.join(", "))}</p>
      ${meta ? `<div class="track-meta">${meta}</div>` : ""}
      <div class="track-chips">${chips}</div>
      <div class="track-actions">
        ${t.preview_url ? `<button class="btn btn--primary btn--sm" ${playAttr(t)}>${icon("play")}Reinhören</button>`
          : `<button class="btn btn--primary btn--sm" data-role="fbplay" title="Keine Hörprobe bei Deezer/Apple – offizieller YouTube- bzw. Spotify-Player als Ersatz">${icon("play")}Reinhören</button>`}
        ${links}
        ${r.id != null && (x.cached || x.local) ? `<button class="btn btn--sm btn--ghost" data-role="refresh" title="Genre, Cover, Hörprobe und Links frisch online nachschlagen">${icon("repeat")}Infos neu laden</button>` : ""}
        <button class="btn btn--sm btn--ghost" data-role="aianalyze" title="Song von der gewählten KI einschätzen lassen">${icon("sparkle")}KI-Analyse</button>
        ${r.id != null || r.key ? `<button class="btn btn--sm btn--ghost" data-role="setgenre" title="Genre selbst festlegen – gilt sofort für diesen Song und verbessert die Erkennung">${icon("pencil")}Genre festlegen</button>` : ""}
        ${x.local && location.hash.startsWith("#/listen") ? `<button class="btn btn--sm btn--ghost" data-role="recheck" title="Nochmal aufnehmen und bei Shazam prüfen">${icon("wave")}Online prüfen</button>` : ""}
        ${fresh && !x.unsure ? `<button class="btn btn--sm btn--ghost" data-verdict="0" title="Falsch erkannt: aus dem Verlauf entfernen">Falsch erkannt?</button>` : ""}
      </div>
    </div>
  </div>
  ${SongLayout.render({
    links: `<section class="det-card">
      <div class="det-h">${icon("external")}<b>Anhören & öffnen</b><span class="det-legend">${tip("Ausgefüllter Punkt: direkter Link zum Song · Ring: Suche beim Dienst")}</span></div>
      <div class="open-grid" data-role="links">${PLATFORM_IDS.map(() => `<span class="otile otile--sk"></span>`).join("")}</div>
    </section>`,
    buy: `<details class="det-card det-fold" ${store.get("buyOpen", false) ? "open" : ""}>
      <summary class="det-h">${icon("download")}<b>Kaufen</b><span class="det-legend">${tip("Beste Qualität zuerst – ohne Provision.")}</span><i class="det-chev">${icon("chevron")}</i></summary>
      <div data-role="buy">${skelBuy()}</div>
    </details>`,
    player: `<section class="det-card det-player hidden" data-role="embeds">
      <div class="det-h">${icon("play")}<b>Offizieller Player</b><span class="det-legend">${tip("Lädt erst nach deinem Klick. Die Hörprobe oben kommt ohne Drittanbieter aus.")}</span></div>
      <div class="emb-tabs" data-role="embtabs"></div><div class="emb-box" data-role="embbox"></div>
    </section>`,
    artist: `<div data-role="artist"></div>`,
    ai: `<div class="ai-mark det-ai" data-role="aimark">${aiMarkHtml(x.ai)}</div>`,
    sort: `<div class="section-title">Einsortieren</div>
    <div class="sug-list">${sugs}${extra}${!sugs && !extra ? `<div class="cell-sub" style="padding:4px 12px">Noch keine passende Playlist – leg einfach eine an.</div>` : ""}</div>
    <div class="add-row">
      <input class="input" data-role="newpl" list="plnames" placeholder="In andere oder neue Playlist …">
      <button class="btn" data-role="addpl">${icon("plus")}Hinzufügen</button>
    </div>`,
    similar: `<div class="section-title">Ähnliche Songs</div>
    <div data-role="similar"><button class="btn btn--sm" data-role="loadsim">${icon("compass")}Ähnliche Songs laden</button></div>`,
    versions: `<div class="section-title">Remixe, Covers & andere Versionen</div>
    <div data-role="versions"><button class="btn btn--sm" data-role="loadver" title="Sucht bei Deezer Aufnahmen mit demselben Titel: Remixe, Live, Akustik, Covers …">${icon("disc")}Remixe & Versionen suchen</button></div>`,
    mix: r.id != null || r.key ? `<div class="section-title">Passt dazu – zum Mixen</div>
    <div data-role="mix"><button class="btn btn--sm" data-role="loadmix" title="Songs aus deinen Playlists mit passendem Tempo und passender Tonart">${icon("disc")}Mixbare Songs aus deiner Bibliothek</button></div>` : "",
  })}`;
}

function sugRow(s, inside) {
  const [g, sub] = guessGenreFromName(s.playlist);
  const col = g ? genreColor(g, sub) : null;
  return `<div class="sug">
    <div class="sug-ico" ${col ? `style="--g:${col}"` : ""}>${icon(s.new ? "sparkle" : "stack")}</div>
    <div style="min-width:0"><div class="sug-name">${s.new ? "Neu: " : ""}${esc(s.playlist)}</div>
      <div class="sug-why">${esc(s.reason || (s.new ? "passende Genre-Playlist anlegen" : ""))}${s.origin && s.origin !== "lokal" ? " · " + esc(s.origin) : ""}</div></div>
    ${s.score != null && !s.new ? `<div class="meter-wrap"><div class="meter"><b style="width:${Math.round(s.score * 100)}%"></b></div>${Math.round(s.score * 100)} % passend</div>` : "<div></div>"}
    ${inside ? `<button class="btn btn--sm btn--added" data-un="${esc(s.playlist)}" title="Wieder entfernen">${icon("check")}Drin</button>`
             : `<button class="btn btn--sm" data-add="${esc(s.playlist)}">${icon("plus")}Hinzufügen</button>`}
  </div>`;
}

function guessGenreFromName(name) {
  const n = name.toLowerCase();
  for (const g of Object.keys(GENRE_COLORS)) {
    if (n.startsWith(g.toLowerCase())) { const sub = name.split(" – ")[1]; return [g, sub || null]; }
  }
  const aliases = { "dnb": "Drum & Bass", "drum": "Drum & Bass", "liquid": "Drum & Bass", "neuro": "Drum & Bass", "jungle": "Drum & Bass",
    "dubstep": "Dubstep", "riddim": "Dubstep", "house": "House", "techno": "Techno", "trance": "Trance", "hardstyle": "Hardstyle / Hardcore", "garage": "UK Garage / Bass" };
  for (const [a, g] of Object.entries(aliases)) if (n.includes(a)) return [g, null];
  return [null, null];
}

const PLATFORM_IDS = ["spotify", "applemusic", "youtubemusic", "youtube", "tidal", "soundcloud", "deezer", "beatport", "bandcamp"];
const PLATFORM_COLORS = { spotify: "#1ed760", applemusic: "#fa5a6e", youtubemusic: "#ff4e45", youtube: "#ff4e45", tidal: "#e8e8e8",
  soundcloud: "#ff7a2f", deezer: "#a238ff", beatport: "#01ff95", bandcamp: "#41a6c3" };
const PLATFORM_BADGE = { spotify: "S", applemusic: "♪", youtubemusic: "YM", youtube: "YT", tidal: "T", soundcloud: "SC", deezer: "D", beatport: "BP", bandcamp: "BC" };
const _linkCache = new Map();
async function loadLinks(root, r) {
  const box = $("[data-role=links]", root);
  if (!box) return;
  const q = r.id != null ? `id=${r.id}` : `key=${encodeURIComponent(r.key)}`;
  try {
    if (!_linkCache.has(q)) _linkCache.set(q, api(`/api/links?${q}`));
    const list = await _linkCache.get(q);
    if (!box.classList.contains("open-grid")) {   // kompakte Variante (z. B. ähnliche Songs)
      box.innerHTML = `<span class="open-lbl">Öffnen in</span>` + list.map(l => `<a class="plat ${l.direct ? "" : "plat--search"}" style="--pc:${PLATFORM_COLORS[l.id] || "#888"}"
        href="${esc(l.url)}" target="_blank" rel="noopener"><span class="plat-dot"></span>${esc(l.name)}${l.direct ? "" : icon("search")}</a>`).join("");
      return;
    }
    const sorted = [...list].sort((a, b) => (b.direct ? 1 : 0) - (a.direct ? 1 : 0));
    box.innerHTML = sorted.map(l => `<a class="otile ${l.direct ? "" : "otile--search"}" style="--pc:${PLATFORM_COLORS[l.id] || "#888"}"
      href="${esc(l.url)}" target="_blank" rel="noopener" title="${l.direct ? `Direkt in ${esc(l.name)} öffnen` : `Auf ${esc(l.name)} suchen – kein direkter Link bekannt`}">
      <span class="otile-badge">${PLATFORM_BADGE[l.id] || esc(l.name[0])}</span>
      <span class="otile-txt"><span class="otile-name">${esc(l.name)}</span><span class="otile-kind">${l.direct ? "Direkt zum Song" : "Suche"}</span></span>
      ${icon(l.direct ? "external" : "search", "otile-ico")}</a>`).join("");
    Embeds.setup(root, list);
    Fallback.bind(root, r, list);
  } catch { _linkCache.delete(q); box.remove(); }
}

/* ---------- Offizielle Player (iframe) – erst nach Klick und Hinweis, Einwilligung je Anbieter widerrufbar */
const Embeds = {
  NAMES: { spotify: "Spotify", applemusic: "Apple Music", youtube: "YouTube", youtubemusic: "YouTube", tidal: "TIDAL", soundcloud: "SoundCloud", deezer: "Deezer" },
  WHO: { spotify: "Spotify AB (Schweden)", applemusic: "Apple Inc. (USA)", youtube: "Google LLC (USA)", tidal: "TIDAL Music AS (Norwegen) / Block Inc. (USA)",
         soundcloud: "SoundCloud Global Ltd. (Deutschland/UK)", deezer: "Deezer S.A. (Frankreich)" },
  PRIVACY: { spotify: "https://www.spotify.com/de/legal/privacy-policy/", applemusic: "https://www.apple.com/de/legal/privacy/", youtube: "https://policies.google.com/privacy?hl=de",
             tidal: "https://tidal.com/privacy", soundcloud: "https://soundcloud.com/pages/privacy", deezer: "https://www.deezer.com/legal/personal-datas" },
  ok() { return store.get("embedOk", {}); },
  allow(id, on) { const o = this.ok(); if (on) o[id] = Date.now(); else delete o[id]; store.set("embedOk", o); },
  // Nur offizielle Einbettungs-Adressen der Anbieter – abgeleitet aus dem direkten Song-Link
  from(l) {
    if (!l.direct) return null;
    let u; try { u = new URL(l.url); } catch { return null; }
    const h = u.hostname, p = u.pathname;
    let m;
    if (/(^|\.)spotify\.com$/.test(h) && (m = p.match(/\/track\/([A-Za-z0-9]{22})/)))
      return { id: "spotify", src: `https://open.spotify.com/embed/track/${m[1]}?utm_source=generator&theme=0`, h: 152 };
    if (h === "music.apple.com" && /\/album\//.test(p))
      return { id: "applemusic", src: `https://embed.music.apple.com${p}${u.search}`, h: 175 };
    if (/(^|\.)youtube\.com$/.test(h) && (m = u.searchParams.get("v")) && /^[\w-]{11}$/.test(m))
      return { id: "youtube", src: `https://www.youtube-nocookie.com/embed/${m}?rel=0`, h: 0 };
    if (h === "youtu.be" && (m = p.match(/^\/([\w-]{11})/)))
      return { id: "youtube", src: `https://www.youtube-nocookie.com/embed/${m[1]}?rel=0`, h: 0 };
    if (/(^|\.)tidal\.com$/.test(h) && (m = p.match(/\/track\/(\d+)/)))
      return { id: "tidal", src: `https://embed.tidal.com/tracks/${m[1]}`, h: 120 };
    if (h === "soundcloud.com" && p.split("/").filter(Boolean).length >= 2)
      return { id: "soundcloud", src: `https://w.soundcloud.com/player/?url=${encodeURIComponent(u.origin + p)}&color=%23ff7a2f&visual=false&show_comments=false`, h: 166 };
    if (/(^|\.)deezer\.com$/.test(h) && (m = p.match(/\/track\/(\d+)/)))
      return { id: "deezer", src: `https://widget.deezer.com/widget/dark/track/${m[1]}`, h: 150 };
    return null;
  },
  // YouTube lässt manche Videos (z. B. von „Topic“-Kanälen) unter einer reinen IP-Adresse wie 127.0.0.1 nicht
  // einbetten (Fehler 150) – dann den Player über den App-eigenen Rahmen auf localhost laden (/embed/player).
  frameSrc(src) {
    const m = src.match(/^https:\/\/www\.youtube-nocookie\.com\/embed\/([\w-]{11})\?(.*)$/);
    if (!m || !/^\d+\.\d+\.\d+\.\d+$|^\[/.test(location.hostname)) return src;
    const auto = /(^|&)autoplay=1(&|$)/.test(m[2]) ? "&autoplay=1" : "";
    return `${location.protocol}//localhost:${location.port}/embed/player?yt=${m[1]}${auto}`;
  },
  setup(root, links) {
    const card = $("[data-role=embeds]", root); if (!card) return;
    const list = [...new Map(links.map(l => this.from(l)).filter(Boolean).map(e => [e.id, e])).values()];
    if (!list.length) return;
    card.classList.remove("hidden");
    const tabs = $("[data-role=embtabs]", card), box = $("[data-role=embbox]", card);
    tabs.innerHTML = list.map(e => `<button class="seg-btn" data-emb="${e.id}" style="--pc:${PLATFORM_COLORS[e.id] || "#888"}"><span class="plat-dot"></span>${esc(this.NAMES[e.id])}</button>`).join("");
    const show = e => {
      $$("[data-emb]", tabs).forEach(b => b.classList.toggle("on", b.dataset.emb === e.id));
      store.set("embedLast", e.id);
      if (this.ok()[e.id]) return this.load(box, e);
      const n = this.NAMES[e.id];
      box.innerHTML = `<div class="emb-gate">
        <div class="emb-gate-ico" style="--pc:${PLATFORM_COLORS[e.id] || "#888"}">${PLATFORM_BADGE[e.id] || "▶"}</div>
        <div><b>Offiziellen ${esc(n)}-Player laden?</b>
          <p>Erst nach deinem Klick lädt das Fenster den Player direkt von ${esc(this.WHO[e.id] || n)}. Dabei werden u. a. deine IP-Adresse und Geräteinfos übertragen; ${esc(n)} kann Cookies setzen${["applemusic", "youtube"].includes(e.id) ? " und Daten in die USA übermitteln" : ""}. Es gelten die <a href="${this.PRIVACY[e.id]}" target="_blank" rel="noopener">Datenschutzhinweise von ${esc(n)}</a>.${e.id === "spotify" ? " Ohne Spotify-Login spielt der Player nur eine Vorschau." : ""}</p>
          <div class="btn-row"><button class="btn btn--sm btn--primary" data-load>${icon("play")}Player laden</button>
            <label class="switch-row"><input type="checkbox" data-always> <span>Für ${esc(n)} immer laden (widerrufbar unter Einstellungen › Datenschutz)</span></label></div></div></div>`;
      hydrateIcons(box);
      $("[data-load]", box).onclick = () => { if ($("[data-always]", box).checked) this.allow(e.id, true); this.load(box, e); };
    };
    $$("[data-emb]", tabs).forEach(b => b.onclick = () => show(list.find(e => e.id === b.dataset.emb)));
    show(list.find(e => e.id === store.get("embedLast", "")) || list[0]);
  },
  load(box, e) {
    Player.audio?.pause?.();
    const style = e.h ? `height:${e.h}px` : "aspect-ratio:16/9;height:auto";
    box.innerHTML = `<iframe class="emb-frame" src="${esc(this.frameSrc(e.src))}" style="${style}" loading="lazy" allowfullscreen
      allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" referrerpolicy="strict-origin-when-cross-origin"
      title="${esc(this.NAMES[e.id])}-Player"></iframe>
      <div class="emb-foot"><span>Offizieller Player von ${esc(this.NAMES[e.id])} – gespielt wird direkt beim Anbieter.</span><button class="btn btn--sm btn--ghost" data-unload>${icon("x")}Player schließen</button></div>`;
    hydrateIcons(box);
    $("[data-unload]", box).onclick = () => { box.innerHTML = ""; $$(".seg-btn", box.parentElement).forEach(b => b.classList.remove("on")); };
  },
};

/* ---------- Ersatz-Hörprobe: offizieller YouTube-/Spotify-Player, wenn Deezer/Apple keine Hörprobe haben.
   Nur sichtbar eingebettet (YouTube-Richtlinien: kein Ton ohne Bild, nichts im Hintergrund), nur nach Einwilligung
   je Anbieter – die prüft auch der Server (/api/fallback antwortet sonst 403). */
const Fallback = {
  s: null,
  cur: null,                      // gerade offene Song-Ansicht {root, r, links}
  TERMS: { youtube: "https://www.youtube.com/t/terms", google: "https://policies.google.com/privacy?hl=de", spotify: "https://www.spotify.com/de/legal/privacy-policy/" },
  async get(force = false) {
    if (!this.s || force) this.s = await api("/api/fallback/settings").catch(() => null);
    return this.s;
  },
  bind(root, r, links) {
    this.cur = { root, r, links };
    const t = r.track || {};
    const btn = $("[data-role=fbplay]", root);
    if (btn) btn.onclick = () => this.run(root, r, links, true);
    if (!t.preview_url) this.run(root, r, links, false);
  },
  // Hörprobe ließ sich nicht laden: Ersatz in der offenen Song-Ansicht anbieten. true = übernommen.
  offerFor(t) {
    const c = this.cur;
    if (!c || !c.root.isConnected || (c.r.track || {}).title !== t.title) return false;
    this.run(c.root, c.r, c.links, true);
    return true;
  },
  vid(links, kind) {
    for (const l of links || []) {
      const e = Embeds.from(l);
      if (!e || e.id !== kind) continue;
      const m = kind === "youtube" ? e.src.match(/embed\/([\w-]{11})/) : e.src.match(/track\/([A-Za-z0-9]{22})/);
      if (m) return m[1];
    }
    return "";
  },
  async run(root, r, links, autoplay) {
    const card = $("[data-role=embeds]", root);
    if (!card) return;
    const s = await this.get();
    if (!s) return;
    const sec = card.closest(".lsec"); if (sec) sec.hidden = false;
    card.classList.remove("hidden");
    const tabs = $("[data-role=embtabs]", card), box = $("[data-role=embbox]", card);
    if (autoplay) card.scrollIntoView({ behavior: "smooth", block: "center" });
    if (!s.youtube && !s.spotify) return this.gate(box, () => this.run(root, r, links, autoplay));
    box.innerHTML = `<div class="cell-sub" style="padding:10px 2px">${icon("search")} Suche den offiziellen Player als Ersatz …</div>`;
    const t = r.track || {};
    const q = new URLSearchParams(r.id != null ? { id: r.id } : r.key ? { key: r.key } : { artist: (t.artists || [])[0] || "", title: t.title || "" });
    if (t.isrc) q.set("isrc", t.isrc);
    if (t.ids?.deezer) q.set("dz", t.ids.deezer);
    const yt = this.vid(links, "youtube"), sp = this.vid(links, "spotify");
    if (yt) q.set("yt", yt); if (sp) q.set("sp", sp);
    let res;
    try { res = await api(`/api/fallback?${q}`); }
    catch (e) { box.innerHTML = `<div class="cell-sub" style="padding:10px 2px">${esc(e.message)}</div>`; hydrateIcons(box); return; }
    const list = [];
    if (res.youtube) list.push({ id: "youtube", src: `https://www.youtube-nocookie.com/embed/${res.youtube}?rel=0${autoplay ? "&autoplay=1" : ""}`, h: 0 });
    if (res.spotify) list.push({ id: "spotify", src: `https://open.spotify.com/embed/track/${res.spotify}?utm_source=generator&theme=0`, h: 152 });
    if (!list.length) {
      const hint = s.youtube && !s.youtube_key && !s.youtube_app ? " Tipp: Mit einem eigenen YouTube-API-Schlüssel (Einstellungen) sucht die App auch direkt bei YouTube." : "";
      box.innerHTML = `<div class="cell-sub" style="padding:10px 2px;white-space:normal">Auch bei ${[s.youtube && "YouTube", s.spotify && "Spotify"].filter(Boolean).join(" und ")} kein passender Player gefunden.${hint}</div>`;
      return;
    }
    tabs.innerHTML = list.map(e => `<button class="seg-btn" data-fb="${e.id}" style="--pc:${PLATFORM_COLORS[e.id]}"><span class="plat-dot"></span>${Embeds.NAMES[e.id]}</button>`).join("");
    const show = e => {
      $$("[data-fb]", tabs).forEach(b => b.classList.toggle("on", b.dataset.fb === e.id));
      Embeds.load(box, e);
      const foot = $(".emb-foot span", box);
      if (foot) foot.textContent = `Ersatz-Hörprobe: offizieller ${Embeds.NAMES[e.id]}-Player (Deezer/Apple haben keine) – gespielt wird direkt bei ${Embeds.NAMES[e.id]}${res.via?.[e.id] ? ` · gefunden über ${res.via[e.id]}` : ""}.`;
    };
    $$("[data-fb]", tabs).forEach(b => b.onclick = () => show(list.find(e => e.id === b.dataset.fb)));
    show(list[0]);
  },
  gate(box, then) {
    if (store.get("fbNoAsk", false)) { box.innerHTML = `<div class="cell-sub" style="padding:10px 2px">Keine Hörprobe bei Deezer/Apple. Ersatz-Player kannst du unter Einstellungen › Datenschutz erlauben.</div>`; return; }
    box.innerHTML = `<div class="emb-gate">
      <div class="emb-gate-ico" style="--pc:${PLATFORM_COLORS.youtube}">▶</div>
      <div><b>Keine Hörprobe bei Deezer oder Apple</b>
        <p>Als Ersatz kann die App den offiziellen YouTube- oder Spotify-Player einbetten – sichtbar, direkt beim Anbieter. Das musst du einmal ausdrücklich erlauben.</p>
        <div class="btn-row"><button class="btn btn--sm btn--primary" data-fb-ok>${icon("play")}Ersatz-Player einrichten …</button>
          <button class="btn btn--sm btn--ghost" data-fb-no>Nicht mehr fragen</button></div></div></div>`;
    hydrateIcons(box);
    $("[data-fb-ok]", box).onclick = () => this.dialog(then);
    $("[data-fb-no]", box).onclick = () => { store.set("fbNoAsk", true); this.gate(box, then); };
  },
  async dialog(then) {
    const s = await this.get(true) || {};
    modal({
      title: "Ersatz-Hörprobe über YouTube / Spotify",
      text: "Gibt es bei Deezer und Apple keine Hörprobe, zeigt die App den offiziellen Player des Anbieters – automatisch in der Song-Ansicht, nur sichtbar und nur dort (kein Ton im Hintergrund, nichts wird heruntergeladen).",
      body: `<div class="set-group" style="display:grid;gap:12px">
        <label class="switch-row"><input type="checkbox" id="fbYt" ${s.youtube ? "checked" : ""}> <span><b>YouTube</b> (Google LLC, USA): Beim Laden des Players gehen deine IP-Adresse und Geräteinfos an Google, Daten können in die USA gehen; beim Abspielen kann YouTube Cookies setzen. Das Video kommt aus schon bekannten Links des Songs oder – falls eingerichtet – aus der offiziellen YouTube-Suche mit deinem eigenen YouTube-Schlüssel bzw. deiner YouTube-Verbindung (dafür gehen Titel und Künstler an Google).
          Es gelten die <a href="${this.TERMS.youtube}" target="_blank" rel="noopener">YouTube-Nutzungsbedingungen</a> und die <a href="${this.TERMS.google}" target="_blank" rel="noopener">Datenschutzerklärung von Google</a>.</span></label>
        <label class="switch-row"><input type="checkbox" id="fbSp" ${s.spotify ? "checked" : ""}> <span><b>Spotify</b> (Spotify AB, Schweden): Der Player spielt ohne Anmeldung eine Vorschau; Spotify sieht IP-Adresse und Geräteinfos und kann Cookies setzen. Der Song kommt aus schon bekannten Links oder – falls verbunden – aus der Suche über deine Spotify-App (Titel/Künstler bzw. ISRC an Spotify). <a href="${this.TERMS.spotify}" target="_blank" rel="noopener">Datenschutzhinweise von Spotify</a>.</span></label>
        <div class="cell-sub" style="white-space:normal">Gefundene Kennungen merkt sich die App höchstens 30 Tage. Jederzeit widerrufbar unter Einstellungen › Datenschutz.</div></div>`,
      confirm: "Speichern",
      onConfirm: async box => {
        this.s = await api("/api/fallback/settings", { method: "POST", body: { youtube: $("#fbYt", box).checked, spotify: $("#fbSp", box).checked } });
        toast(this.s.youtube || this.s.spotify ? "Ersatz-Player erlaubt" : "Ersatz-Player aus");
        if (then) setTimeout(then, 50);
      },
    });
  },
};

const fmtDur = ms => `${Math.floor(ms / 60000)}:${String(Math.round(ms / 1000) % 60).padStart(2, "0")}`;
/* ---------- Mehr vom Künstler: Solo-Songs und Zusammenarbeiten getrennt (Deezer, Künstler über den geprüften Song) */
const ArtistMore = {
  async load(root, r) {
    const box = $("[data-role=artist]", root); if (!box) return;
    const dz = r.track?.ids?.deezer || (r.extra?.links?.deezer || "").match(/track\/(\d+)/)?.[1];
    if (!dz) return;
    let artists;
    try { artists = await api(`/api/artists?dz=${encodeURIComponent(dz)}`); } catch { return; }
    if (!artists.length || !document.body.contains(box)) return;
    box.innerHTML = `<div class="section-title">Mehr vom Künstler</div>
      ${artists.length > 1 ? `<div class="am-pick">${artists.map((a, i) => `<button class="am-chip ${i ? "" : "on"}" data-aid="${a.id}">${a.picture ? `<img src="${esc(a.picture)}" alt="" loading="lazy">` : ""}${esc(a.name)}</button>`).join("")}</div>` : ""}
      <div data-role="amout">${skeletonRows(3)}</div>`;
    const show = async aid => {
      $$(".am-chip", box).forEach(b => b.classList.toggle("on", +b.dataset.aid === aid));
      const out = $("[data-role=amout]", box);
      out.innerHTML = skeletonRows(3);
      let d;
      try { d = await api(`/api/artist/${aid}`); } catch (e) { out.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; return; }
      const cur = (r.track.title || "").toLowerCase();
      const row = t => { const tt = { ...t, preview_url: t.preview_url ? `deezer:${t.artists[0] || ""}|${t.title}` : null };
        return `<div class="am-row ${t.title.toLowerCase() === cur ? "am-cur" : ""}">
          <button class="icon-btn" ${playAttr(tt)} title="Hörprobe (30 s)">${icon("play")}</button>
          ${t.cover ? `<img class="li-cover" src="${esc(t.cover)}" alt="" loading="lazy">` : `<div class="li-cover"></div>`}
          <div style="min-width:0"><div class="li-title">${esc(t.title)}${t.version ? ` <span class="cell-sub">${esc(t.version)}</span>` : ""}</div>
            <div class="cell-sub">${t.with.length ? `mit ${esc(t.with.join(", "))}` : t.album && t.album.toLowerCase() !== t.title.toLowerCase() ? esc(t.album) : "Single"}${t.duration_ms ? ` · ${fmtDur(t.duration_ms)}` : ""}</div></div>
          <a class="icon-btn" href="https://www.deezer.com/track/${esc(t.ids.deezer)}" target="_blank" rel="noopener" title="Bei Deezer öffnen">${icon("external")}</a></div>`; };
      const col = (title, sub, list) => `<section class="det-card am-col"><div class="det-h">${icon(title === "solo" ? "disc" : "stack")}<b>${sub}</b><span class="det-legend">${list.length} Songs</span></div>
        <div class="am-list">${list.slice(0, 25).map(row).join("") || `<div class="cell-sub" style="padding:8px">Keine gefunden.</div>`}</div></section>`;
      out.innerHTML = `<div class="am-head">${d.artist.picture ? `<img src="${esc(d.artist.picture)}" alt="">` : ""}<div><b><a class="dc-a" href="#/discover?artist=${d.artist.id}" title="Künstlerseite öffnen">${esc(d.artist.name)}</a></b>
          <span class="cell-sub">${d.artist.fans ? `${d.artist.fans.toLocaleString("de-DE")} Fans bei Deezer · ` : ""}${d.artist.albums || 0} Veröffentlichungen · beliebteste zuerst</span></div>
          <a class="btn btn--sm btn--ghost" style="margin-left:auto" href="#/discover?artist=${d.artist.id}">${icon("compass")}Künstlerseite</a></div>
        <div class="det-grid am-grid">${col("solo", `Nur ${esc(d.artist.name)}`, d.solo)}${col("collab", "Zusammen mit anderen", d.collab)}</div>`;
      hydrateIcons(out); Player.sync();
    };
    $$(".am-chip", box).forEach(b => b.onclick = () => show(+b.dataset.aid));
    show(artists[0].id);
  },
};

function linkName(k) {
  return ({ shazam: "Shazam", spotify: "Spotify", deezer: "Deezer", apple: "Apple Music", applemusic: "Apple Music", youtube: "YouTube",
    "song.link": "song.link", audd: "AudD", acrcloud: "ACRCloud", itunes: "iTunes", lokal: "lokalem Fingerabdruck" })[k] || k;
}

function bindDetail(root, r, onChange) {
  loadLinks(root, r);
  const fold = $(".det-fold", root);
  if (fold) fold.ontoggle = () => store.set("buyOpen", fold.open);   // aufgeklappt lassen, wenn man es so mag
  ArtistMore.load(root, r);
  const ident = r.id != null ? { id: r.id } : { key: r.key };
  const update = async (path, playlist, msg) => {
    try {
      const nr = await api(path, { method: "POST", body: { ...ident, playlist } });
      if (msg) toast(msg.replace("%s", playlist));
      onChange({ ...r, ...nr, extra: nr.extra || r.extra });
      refreshMeta();
    } catch (e) { toast(e.message, "err"); }
  };
  $$("[data-add]", root).forEach(b => b.onclick = () => update("/api/assign", b.dataset.add, "Zu „%s“ hinzugefügt"));
  $$("[data-un]", root).forEach(b => b.onclick = () => update("/api/unassign", b.dataset.un, "Aus „%s“ entfernt"));
  const inp = $("[data-role=newpl]", root);
  $("[data-role=addpl]", root).onclick = () => inp.value.trim() && update("/api/assign", inp.value.trim(), "Zu „%s“ hinzugefügt");
  inp.onkeydown = e => { if (e.key === "Enter") $("[data-role=addpl]", root).click(); };
  $("[data-role=loadsim]", root).onclick = () => loadSimilar($("[data-role=similar]", root), r);
  const lv = $("[data-role=loadver]", root); if (lv) lv.onclick = () => loadVersions($("[data-role=versions]", root), r);
  const lm = $("[data-role=loadmix]", root); if (lm) lm.onclick = () => loadMix($("[data-role=mix]", root), r);
  const rf = $("[data-role=refresh]", root);
  if (rf) rf.onclick = async () => {
    rf.disabled = true; rf.textContent = "Lädt …";
    try { const nr = await api(`/api/recognition/${r.id}/refresh`, { method: "POST" }); toast("Infos neu geladen"); onChange(nr); }
    catch (e) { toast(e.message, "err"); rf.disabled = false; rf.textContent = "Infos neu laden"; }
  };
  const rc = $("[data-role=recheck]", root);
  if (rc) rc.onclick = () => listenOnce({ force: true });
  $$("[data-verdict]", root).forEach(b => b.onclick = async () => {
    const ok = b.dataset.verdict === "1";
    try {
      const nr = await api(`/api/recognition/${r.id}/verdict`, { method: "POST", body: { ok } });
      if (ok) { toast(nr.learned ? "Gemerkt – nächstes Mal erkennt die App diese Stelle ohne Shazam" : "Bestätigt"); onChange(nr); return; }
      toast("Verworfen – aus dem Verlauf entfernt");
      const L = S.listen;
      if (L.current?.id === r.id) {
        L.current = null; L.lastKey = null;
        L.msg = ["Falsch erkannt – verworfen", "Nochmal versuchen, gern an einer anderen Stelle des Songs"];
        L.tempoOffer = true; L.longOffer = L.seconds < 20;
        renderListenResult(); renderListenState();
      } else closeDrawer();
      refreshMeta();
    } catch (e) { toast(e.message, "err"); }
  });
  const bb = $("[data-role=buy]", root);
  if (bb) {   // Kauf-Links entstehen lokal (keine Online-Abfrage) – deshalb gleich anzeigen
    const q = r.id != null ? `id=${r.id}` : new URLSearchParams({ artist: r.track.artists[0] || "", title: r.track.title });
    api(`/api/buy?${q}`).then(shops => { bb.innerHTML = buyHtml(shops); hydrateIcons(bb); }).catch(e => { bb.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; });
  }
  $$("[data-aimark]", root).forEach(b => b.onclick = async () => {
    const ident = r.id != null ? { id: r.id } : { track: { title: r.track.title, artists: r.track.artists } };
    const mark = b.dataset.aimark || null;
    try { const st = await api("/api/ai-mark", { method: "POST", body: { ...ident, mark } }); onChange({ ...r, extra: { ...r.extra, ai: st } }); toast(mark ? "Markierung gespeichert" : "Markierung entfernt"); }
    catch (e) { toast(e.message, "err"); }
  });
  const sg = $("[data-role=setgenre]", root);
  if (sg) sg.onclick = () => GenreDB.pick(r.track.genre, r.track.subgenre, `${r.track.artists.join(", ")} – ${r.track.title}`, async (g, sub) => {
    const v = await api("/api/genredb/vote", { method: "POST", body: { id: r.id ?? null, key: r.id == null ? r.key : null, genre: g, subgenre: sub } });
    toast(`Gespeichert: ${v.subgenre || v.genre}`);
    onChange({ ...r, track: { ...r.track, genre: v.genre, subgenre: v.subgenre, niche: v.genre === r.track.genre ? r.track.niche : null },
      extra: { ...r.extra, genre_source: "eigene Einordnung" } });
  });
  const ai = $("[data-role=aianalyze]", root);
  if (ai) ai.onclick = () => AI.analyzeTrack(r.id != null ? { id: r.id } : { track: { artist: r.track.artists.join(", "), title: r.track.title, album: r.track.album, tags: Object.keys(r.track.tags || {}), genre: r.track.genre, subgenre: r.track.subgenre } }, ai);
  Player.sync();
}

async function loadMix(box, r) {
  box.innerHTML = skeletonRows(3);
  try {
    const d = await api(r.id != null ? `/api/mixmatch?id=${r.id}` : `/api/mixmatch?key=${encodeURIComponent(r.key)}`);
    if (d.error) { box.innerHTML = `<div class="cell-sub">${esc(d.error)}</div>`; return; }
    const me = d.song, kd = m => m.key_d == null ? "Tonart unbekannt" : m.key_d === 0 ? "gleiche Tonart" : "Camelot-Nachbar";
    const hint = d.unmeasured ? `<div class="cell-sub mx-hint">${d.unmeasured} von ${d.total} Songs deiner Playlists sind noch nicht gemessen – der <a href="#/setplan">Set-Planer</a> oder das Sortieren misst sie mit.</div>` : "";
    box.innerHTML = `<div class="cell-sub mx-me">Dieser Song: <b>${me.bpm ? Math.round(me.bpm) + " BPM" : "Tempo unbekannt"}</b>${me.camelot ? ` · <b>${esc(me.camelot)}</b>${me.key ? ` (${esc(me.key)})` : ""}` : ""} · passend: ±6 % Tempo (auch halb/doppelt), gleiche Tonart oder Camelot-Nachbar</div>
      ${d.matches.length ? `<div class="mx-list">${d.matches.map((m, i) => { const t = withPreview({ ...m });
        return `<div class="mx-row" data-i="${i}"><button class="icon-btn thumb-play" ${playAttr(t)} title="Reinhören">${icon("play")}</button>
          ${m.cover ? `<img class="thumb" src="${esc(m.cover)}" alt="" loading="lazy">` : `<span class="thumb ph"></span>`}
          <div class="sl"><span>${esc(m.artists.join(", "))} – ${esc(m.title)}</span><em>${m.tempo < 0.5 ? "gleiches Tempo" : String(m.tempo).replace(".", ",") + " % Tempo"} · ${kd(m)} · in ${m.playlists.map(esc).join(", ")}</em></div>
          <span class="chip num">${Math.round(m.bpm)} BPM</span><span class="chip" title="${kd(m)}">${esc(m.camelot || "–")}</span></div>`; }).join("")}</div>`
      : `<div class="cell-sub">Keine passenden Songs unter den gemessenen.</div>`}${hint}`;
    hydrateIcons(box); Player.sync();
    lazyCovers(box, d.matches, i => `.mx-row[data-i="${i}"]`);
  } catch (e) { box.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; }
}

async function loadSimilar(box, r) {
  box.innerHTML = skeletonRows(4);
  try {
    const list = await api(r.id != null ? `/api/similar/${r.id}` : `/api/similar?key=${encodeURIComponent(r.key)}`);
    box.innerHTML = similarRows(list);
    bindSimilar(box, list);
    lazyCovers(box, list);
    if (list.length) measureSimilar(box, list, r.id != null ? `/api/audiofeat?id=${r.id}` : `/api/audiofeat?key=${encodeURIComponent(r.key)}`);
  } catch (e) { box.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; }
}

/* Remixe, Covers & andere Versionen: gruppiert, mit Hörprobe, Links und „In Playlist“ */
async function loadVersions(box, r) {
  box.innerHTML = skeletonRows(4);
  let d;
  try { d = await api(r.id != null ? `/api/versions?id=${r.id}` : r.key ? `/api/versions?key=${encodeURIComponent(r.key)}`
    : `/api/versions?${new URLSearchParams({ artist: (r.track?.artists || [])[0] || "", title: r.track?.title || "" })}`); }
  catch (e) { box.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; return; }
  const list = d.items || [];
  if (!list.length) { box.innerHTML = `<div class="cell-sub">Keine anderen Versionen von „${esc(d.core || "")}“ gefunden.</div>`; return; }
  const count = Object.fromEntries(d.kinds.map(k => [k.id, list.filter(v => v.kind === k.id).length]));
  let filter = d.kinds.find(k => k.id === "remix" && count.remix) ? "remix" : "";
  const draw = () => {
    const shown = list.map((v, i) => [v, i]).filter(([v]) => !filter || v.kind === filter);
    let last = null;
    box.innerHTML = `<div class="ver-chips">
        <button class="chip ${!filter ? "chip--on" : ""}" data-vf="">Alle <b class="num">${list.length}</b></button>
        ${d.kinds.filter(k => count[k.id]).map(k => `<button class="chip ${filter === k.id ? "chip--on" : ""}" data-vf="${k.id}">${esc(k.name)} <b class="num">${count[k.id]}</b></button>`).join("")}
      </div>
      ${filter === "andere" || (!filter && count.andere) ? `<div class="cell-sub ver-note">${icon("info")}„Andere Künstler“: Covers und Versionen anderer Künstler mit gleichem Titel – bei sehr häufigen Titeln kann auch ein ganz anderer Song dabei sein.</div>` : ""}
      <div class="rows">${shown.map(([v, i]) => {
        const head = !filter && v.kind !== last ? `<div class="ver-head">${esc(d.kinds.find(k => k.id === v.kind)?.name || v.kind)}</div>` : "";
        last = v.kind;
        return `${head}<div class="row row--ver" data-i="${i}" title="Klicken: auf Spotify, YouTube & Co. öffnen">
          <div class="thumb-wrap">${v.cover ? `<img class="thumb" src="${esc(v.cover)}" alt="" loading="lazy">` : `<div class="thumb" style="display:grid;place-items:center;color:var(--text-3)">${icon("disc")}</div>`}
            <button class="thumb-play" ${playAttr(v)} aria-label="Hörprobe">${icon("play")}</button></div>
          <div class="cell-main"><div class="cell-title">${esc(v.title)}</div><div class="cell-sub">${esc(v.artists.join(", "))}${v.album && v.album !== v.title ? ` · ${esc(v.album)}` : ""}</div></div>
          <div><span class="chip ver-lbl" title="${esc(v.label)}">${esc(v.label)}</span></div>
          <div class="cell-muted num">${v.duration_ms ? fmtDur(v.duration_ms) : ""}</div>
          <div class="row-act"><button class="icon-btn" data-vadd="${i}" title="In eine Playlist legen" aria-label="In Playlist">${icon("plus")}</button></div>
        </div>`;
      }).join("")}</div>`;
    $$("[data-vf]", box).forEach(b => b.onclick = () => { filter = b.dataset.vf; draw(); });
    $$("[data-vadd]", box).forEach(b => b.onclick = () => addFoundToPlaylist(list[+b.dataset.vadd]));
    bindSimilar(box, list, ".row--ver");
  };
  draw();
}

/* Cover für Listen nachladen, wenn die Liste schon steht (Adresse vom Server, Bild direkt vom Anbieter) */
async function lazyCovers(box, list, rowSel = i => `.row--sim[data-i="${i}"]`) {
  const need = list.map((s, i) => [s, i]).filter(([s]) => !s.cover);
  if (!need.length) return;
  const res = await api("/api/covers", { method: "POST", body: { items: need.map(([s]) => ({ a: (s.artists || [])[0], t: s.title, isrc: s.isrc })) } }).catch(() => []);
  res.forEach((c, n) => {
    const [s, i] = need[n];
    if (!c?.cover) return;
    s.cover = c.cover; s.ids = { ...(s.ids || {}), deezer: c.dz };
    const row = $(rowSel(i), box);
    const th = row && $(".thumb", row);
    if (th) th.outerHTML = `<img class="thumb" src="${esc(c.cover)}" alt="" loading="lazy" style="opacity:0;transition:opacity .25s" onload="this.style.opacity=1">`;
    const pb = row && $(".thumb-play", row);
    if (pb) pb.dataset.play = JSON.stringify({ title: s.title, artists: s.artists, cover: s.cover, preview_url: s.preview_url, isrc: s.isrc || null, ids: s.ids });
  });
}

function bindSimilar(box, list, rowSel = ".row--sim") {
  hydrateIcons(box);
  $$(rowSel, box).forEach(row => row.onclick = e => {
    if (e.target.closest("button, a")) return;
    const open = row.nextElementSibling?.classList.contains("sim-links");
    $$(".sim-links", box).forEach(x => x.remove());
    $$(`${rowSel}.open`, box).forEach(x => x.classList.remove("open"));
    if (open) return;
    const s = list[+row.dataset.i];
    row.classList.add("open");
    row.insertAdjacentHTML("afterend", `<div class="sim-links">${s.cover ? `<div class="sim-cover"><img src="${esc(s.cover)}" alt="">${coverSrc(s)}</div>` : ""}<div class="open-on"><span class="open-lbl">Öffnen in</span>${s.links.map(l => `<a class="plat ${l.direct ? "" : "plat--search"}" style="--pc:${PLATFORM_COLORS[l.id] || "#888"}"
      href="${esc(l.url)}" target="_blank" rel="noopener" title="${l.direct ? `Direkt in ${esc(l.name)} öffnen` : `Auf ${esc(l.name)} suchen`}">
      <span class="plat-dot"></span>${esc(l.name)}${l.direct ? "" : icon("search")}</a>`).join("")}</div></div>`);
    hydrateIcons(row.nextElementSibling);
  });
  Player.sync();
}

/* Ähnliche Songs: Tempo, Tonart, Energie nacheinander messen (Hörprobe, wie „Passt dazu“; Gemessenes kommt aus dem Speicher) */
const camelotDist = (a, b) => {
  if (!a || !b) return null;
  const na = parseInt(a), nb = parseInt(b), d = Math.min((na - nb + 12) % 12, (nb - na + 12) % 12);
  return d + (a.slice(-1) === b.slice(-1) ? 0 : 1);             // wie audiofeat.camelot_distance
};
const tempoJump = (a, b) => a && b ? Math.min(...[b, b * 2, b / 2].map(c => Math.abs(a - c) / a * 100)) : null;
const featQuery = t => new URLSearchParams({ artist: (t.artists || [])[0] || "", title: t.title || "", ...(t.isrc ? { isrc: t.isrc } : {}), ...(t.ids?.deezer ? { dz: t.ids.deezer } : {}) });
async function measureSimilar(box, list, base) {
  const head = $(".sim-me", box);
  let me = null;
  try { me = await api(base); } catch { /* ohne Vergleich */ }
  if (head) head.innerHTML = me?.bpm || me?.camelot
    ? `Dieser Song: <b>${me.bpm ? Math.round(me.bpm) + " BPM" : "Tempo unbekannt"}</b>${me.camelot ? ` · <b>${esc(me.camelot)}</b>${me.key ? ` (${esc(me.key)})` : ""}` : ""}${me.energy != null ? ` · Energie ${Math.round(me.energy * 100)} %` : ""} – „mixbar“ = ±6 % Tempo (auch halb/doppelt) und gleiche Tonart oder Camelot-Nachbar`
    : `Tempo und Tonart dieses Songs sind unbekannt (keine Hörprobe) – Werte der Treffer zum Vergleich.`;
  let i = 0;
  const one = async () => {
    while (i < list.length) {
      const k = i++, cell = $(`[data-feat="${k}"]`, box);
      if (!cell || !box.isConnected) return;
      let f = null;
      try { f = await api(`/api/audiofeat?${featQuery(list[k])}`); } catch { /* bleibt leer */ }
      if (!cell.isConnected) return;
      if (!f || !(f.bpm || f.camelot)) { cell.innerHTML = `<span class="cell-muted" title="Keine Hörprobe gefunden">Tempo unbekannt</span>`; continue; }
      Object.assign(list[k], { bpm: f.bpm, camelot: f.camelot, energy: f.energy });
      const tj = tempoJump(me?.bpm, f.bpm), kd = camelotDist(me?.camelot, f.camelot);
      const mix = tj != null && tj <= 6 && (kd == null || kd <= 1);
      cell.innerHTML = `${f.bpm ? `<span class="chip num" title="Tempo${tj != null ? ` – ${tj < 0.5 ? "gleich" : String(Math.round(tj * 10) / 10).replace(".", ",") + " % Abstand"}` : ""}">${Math.round(f.bpm)} BPM</span>` : ""}
        ${f.camelot ? `<span class="chip" title="Tonart ${esc(f.key || "")}${kd != null ? ` – ${kd === 0 ? "gleiche Tonart" : kd === 1 ? "Camelot-Nachbar" : kd + " Schritte entfernt"}` : ""}">${esc(f.camelot)}</span>` : ""}
        ${f.energy != null ? `<span class="chip num" title="Energie (Lautheit/Dichte der Hörprobe)">E ${Math.round(f.energy * 100)}</span>` : ""}
        ${mix ? `<span class="chip chip--mix" title="Passt zum Mixen mit diesem Song">mixbar</span>` : ""}`;
    }
  };
  await Promise.all([one(), one()]);           // höchstens 2 gleichzeitig – schont Deezer
}

function similarRows(list) {
  if (!list.length) return `<div class="cell-sub">Keine ähnlichen Songs gefunden.</div>`;
  return `<div class="cell-sub sim-me">Tempo und Tonart werden gemessen …</div><div class="rows">${list.map((s, i) => `
    <div class="row row--sim" data-i="${i}" title="Klicken: auf Spotify, YouTube & Co. öffnen">
      <div class="thumb-wrap"><div class="thumb" style="display:grid;place-items:center;color:var(--text-3)">${icon("disc")}</div>
        <button class="thumb-play" ${playAttr(s)} aria-label="Hörprobe">${icon("play")}</button></div>
      <div class="cell-main"><div class="cell-title">${esc(s.title)}</div><div class="cell-sub">${esc(s.artists.join(", "))}</div></div>
      <div>${s.genre ? genreChip(s.genre, s.subgenre) : `<span class="cell-muted">–</span>`}</div>
      <div class="sim-feat" data-feat="${i}"><span class="cell-muted">Tempo …</span></div>
      <div class="meter-wrap"><div class="meter"><b style="width:${Math.round(s.match * 100)}%"></b></div>${Math.round(s.match * 100)} % ähnlich</div>
      <div class="row-act"><span class="icon-btn" aria-hidden="true">${icon("external")}</span></div>
    </div>`).join("")}</div>`;
}

const skeletonRows = n => `<div class="rows">${Array.from({ length: n }, () => `<div class="row" style="grid-template-columns:40px 1fr;cursor:default"><div class="skeleton" style="width:40px;height:40px"></div><div><div class="skeleton" style="height:12px;width:45%;margin-bottom:6px"></div><div class="skeleton" style="height:10px;width:28%"></div></div></div>`).join("")}</div>`;

/* ================================================================= Drawer */
async function openDrawer(loader) {
  $("#drawerBody").innerHTML = skeletonRows(3);
  $("#drawer").classList.add("open"); $("#drawerBackdrop").classList.add("open");
  $("#drawer").setAttribute("aria-hidden", "false");
  try {
    const r = await loader();
    const render = rr => { $("#drawerBody").innerHTML = detailHtml(rr); bindDetail($("#drawerBody"), rr, render); };
    render(r);
  } catch (e) { $("#drawerBody").innerHTML = `<div class="empty"><p>${esc(e.message)}</p></div>`; }
}
function closeDrawer() {
  $("#drawer").classList.remove("open"); $("#drawerBackdrop").classList.remove("open");
  $("#drawer").setAttribute("aria-hidden", "true");
}
$("#drawerClose").onclick = closeDrawer;
$("#drawerBackdrop").onclick = closeDrawer;

/* ================================================================= Pegel / Spektrum */
const VIZ = [["bars", "Spektrum", "Frequenzbalken"], ["wave", "Welle 3-Band", "Lauf-Wellenform wie am DJ-Player: Bass blau, Mitten orange, Höhen weiß"],
  ["rgb", "Welle RGB", "Lauf-Wellenform, Farbe nach Klang: Bass rot, Mitten grün, Höhen blau"]];
const Meter = {
  ws: null, source: null, active: false, frame: null, last: 0, raf: 0, quietSince: 0,
  bands: new Float32Array(32), peak: -90, peakT: 0, scanList: null,
  viz: store.get("viz", "bars"), cols: [], total: 0, colAt: 0, wpeak: .2,
  setViz(v) {
    this.viz = v; store.set("viz", v);
    api("/api/companion", { method: "POST", body: { viz: v } }).catch(() => {});   // Schwebe-Icon zeigt dasselbe
  },
  start(source) {
    if (this.active && this.source === source && this.ws?.readyState <= 1) return;
    this.stop();
    this.active = true; this.source = source; this.frame = null; this.quietSince = Date.now(); this.loudAt = Date.now();
    if (document.hidden) { this.suspended = true; return; }      // Fenster versteckt: erst beim Wiederzeigen öffnen
    this.suspended = false;
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/level?source=${enc(source)}`);
    this.ws = ws;
    ws.onmessage = e => {
      const f = JSON.parse(e.data); if (f.error) { this.err = f.error; this.kick(); return; }
      this.err = null; this.frame = f; this.last = Date.now();
      if (f.rms > -60) this.loudAt = this.last;
      if (f.wv) { for (const c of f.wv) this.cols.push(c); this.total += f.wv.length; this.colAt = performance.now(); if (this.cols.length > 720) this.cols.splice(0, this.cols.length - 600); }
      if (!this.silent()) this.kick();
      else if (!this.pausedDrawn) { this.pausedDrawn = true; this.kick(); }   // Stille: ein letztes Bild, dann Pause
    };
    ws.onclose = () => { if (this.active && this.ws === ws) setTimeout(() => this.active && this.ws === ws && this.start(source, true), 1200); };
    // Kommen keine Daten mehr, muss die Anzeige trotzdem auf „Verbinde …“ wechseln
    clearInterval(this._watch); this._watch = setInterval(() => { if (Date.now() - this.last > 1500) this.kick(); }, 700);
    this.kick();
  },
  // Stille: so lange nichts mehr zu hören ist, dass auch die Welle durchgelaufen ist → Zeichnen pausiert
  silent() { return Date.now() - this.loudAt > (this.viz === "bars" ? 1500 : 4000); },
  // Ein Bild anfordern – höchstens ~30 je Sekunde (Daten kommen mit 25/s; mehr zeichnet ohne GPU nur Last)
  kick() {
    if (!this.active || this.raf || document.hidden) return;
    this.raf = requestAnimationFrame(t => {
      this.raf = 0;
      if (t - this.drawnAt < 30) { this.kick(); return; }
      this.drawnAt = t; this.draw();
      if (!this.silent()) this.pausedDrawn = false;
      // Glätten/Einschieben noch nicht fertig → weiterzeichnen, sonst warten bis neue Daten kommen
      if (this.settling() && !this.silent()) this.kick();
    });
  },
  settling() {
    if (this.viz !== "bars") return performance.now() - this.colAt < 45;
    return this.bands.some(v => v > .004);
  },
  suspend() {   // Fenster versteckt/minimiert: Verbindung und Aufnahme (parec) beenden
    if (!this.active || this.suspended) return;
    const src = this.source; this.stop(); this.active = true; this.source = src; this.suspended = true;
  },
  resume() {
    if (!this.suspended) return;
    this.suspended = false; const src = this.source; this.active = false; this.start(src);
  },
  drawnAt: 0, loudAt: 0, pausedDrawn: false, suspended: false,
  restart(source) { this.stop(); this.start(source); },
  testing: false,
  test(source) {  // Mikrofon-Pegel kurz prüfen – nur lokal, nichts wird gesendet
    clearTimeout(this._testT); this.testing = true; this.start(source);
    this._testT = setTimeout(() => { this.testing = false; if (!S.listen.busy) this.stop(); }, 10000);
  },
  stop() {
    this.active = false; this.suspended = false; this.frame = null; cancelAnimationFrame(this.raf); this.raf = 0; clearInterval(this._watch);
    if (this.ws) { const w = this.ws; this.ws = null; try { w.close(); } catch {} }
    this.idle();
  },
  idle() {  // Anzeige „aus“ (z. B. Mikrofon geschlossen)
    const sig = $("#signal"), cv = $("#spec");
    if (!sig) return;
    this.bands.fill(0); this._vw = this._vl = this._vc = null;
    this.cols = []; this.total = 0; this.wpeak = .2;
    sig.dataset.state = "off"; $("#orb")?.removeAttribute("data-sig");
    $("#sigText").textContent = S.listen.mode === "mic" ? "Mikrofon aus – öffnet sich erst beim Erkennen" : "Pegel aus";
    $("#sigDb").textContent = ""; const vf = $("#vuFill"), vp = $("#vuPeak"); if (vf) vf.style.transform = ""; if (vp) vp.style.transform = "";
    cv?.getContext("2d").clearRect(0, 0, cv.width, cv.height);
  },
  state() {
    const f = this.frame, stale = Date.now() - this.last > 1500;
    if (!f || stale) return this.err ? ["none", this.err, null] : ["wait", "Verbinde mit Gerät …", null];
    if (f.rms > -50) { this.quietSince = Date.now(); return ["ok", "Signal kommt an", f.rms]; }
    if (f.rms > -60) { this.quietSince = Date.now(); return ["low", "Leise, aber da", f.rms]; }
    return Date.now() - this.quietSince > 1200 ? ["none", "Kein Signal – falsches Gerät?", f.rms] : ["ok", "Signal kommt an", f.rms];
  },
  drawBars(g, w, h, col) {
    // Spektrum mitten im Kreis: gespiegelte Balken, Mitte = Bässe, außen = Höhen; außen flacher (Kreisform)
    const n = 17, gap = 4, span = w * .7, bw = (span - gap * (n - 1)) / n, x0 = (w - span) / 2, mid = h / 2;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(i - (n - 1) / 2) / ((n - 1) / 2);            // 0 Mitte .. 1 Rand
      const band = Math.min(31, Math.round(d * 26 + 1));
      const v = this.bands[band];
      const room = Math.sqrt(Math.max(0, 1 - d * d)) * h * .36;       // Platz im Kreis
      const bh = Math.max(3, v * room * 2);
      g.globalAlpha = .35 + v * .65; g.fillStyle = col;
      const x = x0 + i * (bw + gap), r = bw / 2;
      g.beginPath(); g.roundRect ? g.roundRect(x, mid - bh / 2, bw, bh, r) : g.rect(x, mid - bh / 2, bw, bh); g.fill();
    }
    g.globalAlpha = 1;
  },
  // Lauf-Wellenform wie an DJ-Playern: neueste Spalte rechts, wandert nach links.
  // "wave" = 3-Band (Bass blau, Mitten orange, Höhen weiß übereinander), "rgb" = eine Hülle, Farbe aus Bass/Mitten/Höhen.
  drawWave(g, w, h, st) {
    const cols = this.cols, n = cols.length;
    if (!n) return;
    const cw = 1, now = performance.now();
    const slide = Math.min(4, (now - this.colAt) / 10);                 // 4 Spalten je 40-ms-Frame weich einschieben
    const pos = this.total - 4 + slide, head = w * .86, mid = h / 2;
    const fresh = cols.slice(-4);
    const mx = Math.max(...fresh.map(c => Math.max(c[0], c[1] * 1.4, c[2] * 2.2)));
    this.wpeak = Math.max(this.wpeak * .997, mx, .06);                  // automatische Verstärkung
    const gain = .95 / this.wpeak, off = st === "none";
    const room = x => { const d = (x - w / 2) / (w / 2); return Math.sqrt(Math.max(0, 1 - d * d)) * h * .44; };
    for (let i = n - 1; i >= 0; i--) {
      const x = head - (pos - (this.total - n + i)) * cw;
      if (x < 0) break;
      if (x > head) continue;
      const c = cols[i], lim = room(x), fade = Math.min(1, x / (w * .3));
      const lo = Math.min(1, c[0] * gain), md = Math.min(1, c[1] * 1.4 * gain), hi = Math.min(1, c[2] * 2.2 * gain);
      g.globalAlpha = (off ? .35 : 1) * (.35 + .65 * fade);
      if (this.viz === "rgb") {
        const a = Math.max(lo, md, hi), m = a || 1;
        g.fillStyle = off ? "#777" : `rgb(${Math.round(60 + 195 * lo / m)},${Math.round(40 + 215 * md / m * .9)},${Math.round(60 + 195 * hi / m)})`;
        const y = Math.max(1, a * lim); g.fillRect(x, mid - y, cw + .4, y * 2);
      } else {
        for (const [v, col] of [[lo, "#2b6ef2"], [md, "#e8952c"], [hi, "#f4f4f4"]]) {
          const y = Math.max(.5, v * lim * (col === "#f4f4f4" ? .6 : col === "#e8952c" ? .8 : 1));
          g.fillStyle = off ? "#777" : col; g.fillRect(x, mid - y, cw + .4, y * 2);
        }
      }
    }
    g.globalAlpha = .9; g.fillStyle = "#fff"; g.fillRect(head + 1, mid - h * .3, 1.5, h * .6);   // Abspielposition
    g.globalAlpha = 1;
  },
  draw() {
    const cv = $("#spec");
    if (!cv) return;
    const f = this.frame, alive = f && Date.now() - this.last < 1500;
    // Glätten: schnell hoch, langsam runter – zeitbasiert, damit es bei jeder Bildrate gleich wirkt (Basis 60 Hz)
    const now = performance.now(), k = Math.min(6, Math.max(1, (now - (this._smT || now - 16.7)) / 16.7));
    this._smT = now;
    const up = .3 ** k, down = .86 ** k;
    for (let i = 0; i < 32; i++) {
      const t = alive ? f.bands[i] : 0, b = this.bands[i];
      this.bands[i] = t > b ? t - (t - b) * up : t + (b - t) * down;
    }
    const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    if (!w) return;
    if (cv.width !== w * dpr) { cv.width = w * dpr; cv.height = h * dpr; }
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    const [st, text] = this.state();
    const col = st === "none" ? "#e2786e" : st === "low" ? "#e0b46a" : "#6cc8a8";
    if (this.viz !== "bars") this.drawWave(g, w, h, st);
    else this.drawBars(g, w, h, col);
    const rms = alive ? f.rms : -90;
    const orb = $("#orb"), sig = $("#signal");
    if (orb && orb.dataset.sig !== st) orb.dataset.sig = st;
    if (sig && (sig.dataset.state !== st || $("#sigText").textContent !== text)) { sig.dataset.state = st; $("#sigText").textContent = text; }
    // dB-Zahl nur ~4× je Sekunde – schneller ist sie ohnehin nicht lesbar, jede Änderung kostet Layout
    const db = $("#sigDb"), dbt = alive ? `${Math.round(rms)} dB` : "";
    if (db && db.textContent !== dbt && (!dbt || now - (this._dbT || 0) > 250)) { this._dbT = now; db.textContent = dbt; }
    // Pegelbalken unter der Statuszeile (−60..0 dB) mit kurzem Spitzenwert-Halter
    const pk = alive ? f.peak : -90, pct = v => Math.max(0, Math.min(100, (v + 60) / 60 * 100));
    if (pk > this.peak || Date.now() - this.peakT > 1200) { this.peak = pk; this.peakT = Date.now(); }
    const vf = $("#vuFill"), vp = $("#vuPeak");
    const vw = `translateX(${(pct(rms) - 100).toFixed(1)}%)`, vl = `translateX(${(pct(this.peak) - 100).toFixed(1)}%)`;
    if (vf && this._vw !== vw) { this._vw = vw; vf.style.transform = vw; }
    if (vf && this._vc !== col) { this._vc = col; vf.style.background = col; }
    if (vp && this._vl !== vl) { this._vl = vl; vp.style.transform = vl; }
  },
};

// Fenster versteckt, minimiert oder im Tray: Pegel (WebSocket + Aufnahme) anhalten, beim Zeigen weiter
document.addEventListener("visibilitychange", () => document.hidden ? Meter.suspend() : Meter.resume());

async function scanDevices(kind, onPick) {
  const box = $("#scanOut");
  box.innerHTML = `<div class="scan-wait">${icon("search")}Höre kurz in alle Geräte hinein …</div>`;
  try {
    const list = await api(`/api/sources/scan?kind=${kind}`);
    const pct = db => Math.max(0, Math.min(100, (db + 70) / 70 * 100));
    box.innerHTML = `<div class="scan-list">${list.map(d => `
      <button class="scan-item ${d.signal ? "has" : ""}" data-name="${esc(d.name)}">
        <span class="scan-name">${esc(d.description.replace(/^Monitor of /, ""))}</span>
        <span class="scan-bar"><b style="width:${pct(d.db)}%"></b></span>
        <span class="scan-db">${d.db <= -89 ? "stumm" : Math.round(d.db) + " dB"}</span>
      </button>`).join("")}</div>`;
    $$(".scan-item", box).forEach(b => b.onclick = () => { box.innerHTML = ""; onPick(b.dataset.name); });
    const best = list.find(d => d.signal);
    if (!best) toast(kind === "desktop" ? "Kein Ausgabegerät spielt gerade Ton – läuft Musik?" : "Kein Mikrofon empfängt gerade Ton", "err");
  } catch (e) { box.innerHTML = ""; toast(e.message, "err"); }
}

/* ================================================================= Modal */
// onConfirm fehlt (reine Info-Dialoge wie „Fertig“) -> OK schließt nur
function modal({ title, text = "", body = "", confirm = "OK", cancel = "Abbrechen", danger = false, onConfirm = () => {}, onCancel, sticky = false, wide = false }) {
  const m = $("#modal");
  $("#modalBox").classList.toggle("modal--wide", !!wide);
  m.dataset.sticky = sticky ? "1" : "";
  $("#modalBox").innerHTML = `<div class="modal-head"><h3>${esc(title)}</h3>${text ? `<p>${text}</p>` : ""}</div>
    ${body ? `<div class="modal-body">${body}</div>` : ""}
    <div class="modal-foot">${cancel === null ? "" : `<button class="btn btn--ghost" data-m="cancel">${esc(cancel)}</button>`}
    <button class="btn ${danger ? "btn--danger-solid" : "btn--primary"}" data-m="ok">${esc(confirm)}</button></div>`;
  m.classList.add("open");
  const close = () => m.classList.remove("open");
  const cb = $("[data-m=cancel]", m); if (cb) cb.onclick = () => { close(); onCancel?.(); };
  m.onclick = e => { if (e.target === m && !sticky) { close(); onCancel?.(); } };
  $("[data-m=ok]", m).onclick = async () => {
    const b = $("[data-m=ok]", m); b.disabled = true;
    try { await onConfirm($("#modalBox")); close(); } catch (e) { if (!e.silent) toast(e.message, "err"); b.disabled = false; }
  };
  $("[data-m=ok]", m).focus();
}

/* ================================================================= Views */
const Views = {};

/* ---------- Erkennen */
Views.listen = async (main, _, params) => {
  const L = S.listen;
  if (S.status?.llm) api("/api/llm/warm", { method: "POST" }).catch(() => {});  // Modell schon mal laden
  if (params?.get("id")) L.current = await api(`/api/recognition/${params.get("id")}`).catch(() => L.current);
  // jedes Mal neu: Anwendungen tauchen nur auf, solange sie gerade etwas abspielen
  S.sources = await api("/api/sources").catch(() => S.sources || []);
  const devices = S.sources.filter(s => s.kind === L.mode);
  const appSrcs = L.mode === "desktop" ? S.sources.filter(s => s.kind === "app") : [];
  const savedApp = L.source.startsWith("app:") && !appSrcs.some(a => a.name === L.source) ? L.source : null;
  main.innerHTML = `<div class="page">
    <div class="listen">
      <div class="card listen-panel">
        <div class="orb ${L.busy ? "busy" : ""}" id="orb">
          <svg class="ring" viewBox="0 0 196 196"><circle class="ring-bg" cx="98" cy="98" r="92" fill="none" stroke-width="3"/>
            <circle class="ring-fg" id="ringFg" cx="98" cy="98" r="92" fill="none" stroke-width="3" stroke-dasharray="578" stroke-dashoffset="578"/></svg>
          <button class="orb-btn" id="orbBtn" aria-label="Song erkennen"><canvas id="spec"></canvas></button>
        </div>
        <div class="orb-state" id="orbState"></div>
        <div id="limitBox" class="limit-box"></div>
        <div class="signal" id="signal" data-state="${L.mode === "mic" ? "off" : "wait"}">
          <div class="signal-line"><span class="sig-dot"></span><span id="sigText">${L.mode === "mic" ? "Mikrofon aus – öffnet sich erst beim Erkennen" : "Verbinde mit Gerät …"}</span><span class="sig-db num" id="sigDb"></span></div>
          <div class="vu" title="Pegel (−60 bis 0 dB)"><span class="vu-t"><b id="vuFill"></b></span><i id="vuPeak"></i></div>
          ${L.mode === "mic" ? `<button class="link-btn mic-test" id="micTest">${icon("mic")}Pegel testen (10 s, bleibt auf dem PC)</button>` : ""}
        </div>
        <div class="listen-opts">
          <div><div class="opt-label">Quelle</div>
            <div class="segmented" id="modeSeg">
              <button data-mode="desktop" class="${L.mode === "desktop" ? "on" : ""}">${icon("monitor")}Desktop</button>
              <button data-mode="mic" class="${L.mode === "mic" ? "on" : ""}">${icon("mic")}Mikrofon</button>
            </div></div>
          <div><div class="opt-label">Gerät${L.mode === "desktop" ? tip("Anwendung wählen, um nur z. B. den Browser oder Spotify zu hören – Sprachchats (Discord, Teams …) werden nie angeboten.") : ""}</div>
            <select class="select" id="device">
              <option value="${L.mode}">Standard${L.mode === "desktop" ? "-Ausgabe" : "-Mikrofon"}</option>
              <optgroup label="Geräte">${devices.map(d => `<option value="${esc(d.name)}" ${L.source === d.name ? "selected" : ""}>${esc(d.description.replace(/^Monitor of /, ""))}</option>`).join("")}</optgroup>
              ${L.mode === "desktop" ? `<optgroup label="Nur eine Anwendung (optional)">
                ${appSrcs.map(a => `<option value="${esc(a.name)}" ${L.source === a.name ? "selected" : ""}>${esc(a.description)}</option>`).join("")}
                ${savedApp ? `<option value="${esc(savedApp)}" selected>${esc(savedApp.slice(4))} – spielt gerade nichts</option>` : ""}
                ${!appSrcs.length && !savedApp ? `<option disabled>${S.status?.apps === false ? "nur mit PipeWire" : "keine Anwendung spielt gerade Ton ab"}</option>` : ""}
              </optgroup>` : ""}
            </select>
</div>
          <div class="scan-wrap"><button class="link-btn" id="scanBtn">${icon("search")}Gerät mit Signal finden</button><div id="scanOut"></div></div>
          <div><div class="opt-label">Aufnahmedauer</div>
            <div class="segmented" id="secSeg">${[6, 10, 15, 20].map(s => `<button data-s="${s}" class="${L.seconds === s ? "on" : ""}">${s} s</button>`).join("")}</div></div>
          <div class="opt-row"><label class="switch"><input type="checkbox" id="autoSw" ${L.auto ? "checked" : ""}><span class="track"></span>Dauer-Modus – erkennt jeden neuen Song</label>
            ${tip("Gesendet wird erst, wenn du auf den Kreis klickst – im Dauer-Modus bis zum nächsten Klick.")}</div>
          <a class="link-btn" href="#/settings?tab=erkennung">${icon("sliders")}Anzeige im Kreis: ${esc((VIZ.find(x => x[0] === Meter.viz) || VIZ[0])[1])} – ändern</a>
        </div>
      </div>
      <div class="listen-main">
        <div id="listenResult"></div>
      </div>
    </div></div>`;

  $$("#modeSeg button").forEach(b => b.onclick = () => {
    L.mode = b.dataset.mode; L.running = false; stopHold();
    // gespeichertes Gerät dieses Modus wiederherstellen (nicht auf Standard zurückfallen)
    const saved = S.prefs?.[`device_${L.mode}`];
    L.source = saved && !S.prefs.missing?.includes(`device_${L.mode}`) ? saved : L.mode;
    savePrefs({ mode: L.mode });
    Views.listen(main, null, new URLSearchParams());
  });
  $("#device").onchange = e => {
    L.source = e.target.value; savePrefs({ [`device_${L.mode}`]: L.source });
    if (S.prefs) S.prefs.missing = (S.prefs.missing || []).filter(k => k !== `device_${L.mode}`);
    if (L.mode !== "mic") Meter.restart(L.source); toast("Gerät gespeichert");
  };
  $("#scanBtn").onclick = () => scanDevices(L.mode, name => {
    L.source = name; savePrefs({ [`device_${L.mode}`]: name });
    if (![...$("#device").options].some(o => o.value === name)) $("#device").add(new Option(name, name));
    $("#device").value = name; if (L.mode !== "mic") Meter.restart(name); toast("Gerät gewählt und gespeichert");
  });
  // Desktop-Pegel läuft live (bleibt lokal). Das Mikrofon wird nur beim Erkennen oder per „Pegel testen“ geöffnet.
  if (L.mode === "mic") Meter.stop(); else Meter.start(L.source);
  $$("#secSeg button").forEach(b => b.onclick = () => { L.seconds = +b.dataset.s; savePrefs({ seconds: L.seconds }); $$("#secSeg button").forEach(x => x.classList.toggle("on", x === b)); });
  // Datenschutz: Der Schalter startet nichts. Gesendet wird erst nach Klick auf den Kreis.
  $("#autoSw").onchange = e => { L.auto = e.target.checked; if (!L.auto) { L.running = false; stopHold(); } renderListenState(); };
  $("#orbBtn").onclick = () => {
    if (L.auto && L.running) { L.running = false; stopHold(); L.msg = ["Dauer-Modus gestoppt", "Zum erneuten Start klicken"]; renderListenState(); return; }
    if (L.auto) L.running = true;
    listenOnce();
  };
  $("#micTest")?.addEventListener("click", () => Meter.test(L.source));
  renderListenState();
  renderListenResult();
  Limits.refresh();
};

function renderListenState() {
  const L = S.listen, st = $("#orbState");
  $("#liveDot").classList.toggle("on", L.busy || (L.auto && L.running));
  if (!st) return;
  $("#orb").classList.toggle("busy", L.busy);
  if (L.busy) st.innerHTML = `<strong>${L.phase === "rec" ? "Höre zu …" : "Erkenne …"}</strong><span>${
    L.phase === "rec3" && L.tempoRun ? "prüfe auch Slowed/Sped-up-Version (max. 25 s)" : L.auto && L.running ? "Dauer-Modus aktiv – Klick stoppt" : "einen Moment"}</span>`;
  else if (L.auto && L.running) st.innerHTML = `<strong>Dauer-Modus aktiv</strong><span>${esc(L.msg ? L.msg[0] + (L.msg[1] ? " · " + L.msg[1] : "") : "")} · Klick stoppt</span>`;
  else if (L.msg) {
    st.innerHTML = `<strong>${esc(L.msg[0])}</strong><span>${esc(L.msg[1] || "")}</span>${L.tempoOffer || L.longOffer ? `<div class="btn-row" style="margin-top:10px;justify-content:center">
      ${L.longOffer ? `<button class="btn btn--sm" id="longBtn" title="Nimmt 20 Sekunden auf und schickt Shazam den mittleren Abschnitt – hilft, wenn der Anfang ein leises Intro oder Gerede war. Weiterhin nur eine Shazam-Anfrage.">Länger aufnehmen (20 s)</button>` : ""}
      ${L.tempoOffer ? `<button class="btn btn--sm btn--ghost" id="tempoBtn" title="Nimmt neu auf und fragt Shazam zusätzlich mit 2–3 umgerechneten Tempi – kostet mehr Anfragen">Als Slowed/Sped-up suchen</button>` : ""}</div>` : ""}`;
    const tb = $("#tempoBtn", st);
    if (tb) tb.onclick = () => listenOnce({ tempo: true });
    const lb = $("#longBtn", st);
    if (lb) lb.onclick = () => listenOnce({ seconds: 20 });
  }
  else st.innerHTML = `<strong>Bereit</strong><span>${L.auto ? "Klicken startet den Dauer-Modus" : "Zum Erkennen klicken"}</span>`;
}

function renderListenResult() {
  const box = $("#listenResult");
  if (!box) return;
  const r = S.listen.current;
  if (!r) {
    box.innerHTML = `<div class="empty" style="padding:40px 24px 28px">${icon("wave")}<h3>Bereit zum Zuhören</h3><p>Der erkannte Song erscheint hier – mit Hörprobe, Genre und Vorschlag, in welche Playlist er passt.</p></div>`;
    api("/api/history?limit=6").then(items => {
      if (!items.length || S.listen.current || !$("#listenResult")) return;
      box.insertAdjacentHTML("beforeend", `<div class="section-title">Zuletzt erkannt</div><div class="rows">${items.map(i => `
        <div class="row row--history" data-id="${i.id}">
          <div class="thumb-wrap">${i.cover ? `<img class="thumb" src="${esc(i.cover)}" alt="" loading="lazy">` : `<div class="thumb"></div>`}
            ${i.preview_url ? `<button class="thumb-play" ${playAttr(i)} aria-label="Hörprobe">${icon("play")}</button>` : ""}</div>
          <div class="cell-main"><div class="cell-title">${esc(i.title)}</div><div class="cell-sub">${esc(i.artists.join(", "))}</div></div>
          <div>${genreChip(i.genre, i.subgenre)}</div><div class="cell-muted">${i.bpm ? Math.round(i.bpm) : ""}</div>
          <div class="cell-muted">${relTime(i.ts)}</div>
          <div class="row-act"><button class="icon-btn" aria-label="Details">${icon("arrow")}</button></div></div>`).join("")}</div>`);
      $$("#listenResult .row[data-id]").forEach(row => row.onclick = async () => {
        S.listen.current = await api(`/api/recognition/${row.dataset.id}`); renderListenResult();
      });
      Player.sync();
    }).catch(() => {});
    return;
  }
  const render = rr => {
    S.listen.current = rr;
    box.innerHTML = `<div class="view-enter"><div class="song-tools"><button class="btn btn--xs btn--ghost" data-role="layout" title="Reihenfolge der Bereiche ändern oder Bereiche ausblenden">${icon("sliders")}Ansicht anpassen</button></div>${detailHtml(rr)}</div>`;
    $("[data-role=layout]", box).onclick = () => SongLayout.dialog(() => render(S.listen.current));
    bindDetail(box, rr, render);
  };
  render(r);
}

function ringProgress() {
  const L = S.listen, fg = $("#ringFg");
  if (fg) {
    const total = L.seconds * 1000 + 1500;
    const p = L.busy ? (L.phase === "rec" ? Math.min(1, (Date.now() - L.started) / total) : 1) : 0;
    fg.style.strokeDashoffset = String(578 * (1 - p));
  }
  if (L.busy) requestAnimationFrame(ringProgress);
}

// modal() als Frage mit Ergebnis (true/Wert bei OK, false bei Abbrechen)
const ask = opts => new Promise(res => modal({ ...opts, sticky: true,
  onConfirm: async box => res(opts.value ? opts.value(box) : true), onCancel: () => res(false) }));

const RAW_ENGINES = { audd: "AudD", acrcloud: "ACRCloud" };
async function ensureListenConsent(mode) {
  const P = S.prefs || {};
  if (mode === "mic" && !P.mic_ack) {
    const ok = await ask({ title: "Mikrofon – kurzer Hinweis", confirm: "Verstanden", cancel: "Abbrechen",
      text: "Bitte lesen, bevor du das Mikrofon nutzt:",
      body: `<div class="privacy-note">
        <p>Das Mikrofon nimmt <b>alles</b> im Raum auf – auch Gespräche. In Deutschland ist es strafbar, das nicht öffentlich gesprochene Wort anderer ohne ihr Einverständnis aufzunehmen (§ 201 StGB).</p>
        <p>Nutze das Mikrofon deshalb nur für Musik und nur, wenn niemand ungewollt mit aufgenommen wird. Sag Anwesenden kurz Bescheid.</p>
        <p class="muted">SH-Tunebridge speichert keine Aufnahmen: Der Ausschnitt wird direkt nach der Erkennung gelöscht.</p></div>` });
    if (!ok) return false;
    savePrefs({ mic_ack: true });
  }
  const raw = (S.status?.engines || []).filter(e => RAW_ENGINES[e]);
  if (raw.length && (P[`send_audio_${mode}`] ?? null) === null) {
    const names = raw.map(e => RAW_ENGINES[e]).join(" und ");
    const v = await ask({ title: "Welche Erkennungsdienste?", confirm: "Speichern", cancel: "Abbrechen",
      text: `Gilt für ${mode === "mic" ? "das Mikrofon" : "Desktop-Audio"} – jederzeit in den Einstellungen unter „Datenschutz“ änderbar.`,
      body: `<label class="choice"><input type="radio" name="sa" value="0" checked><div><b>Nur Shazam${mode === "mic" ? " (empfohlen)" : ""}</b>
          <span>Es verlässt nur ein auf deinem Rechner berechneter Fingerabdruck den PC – kein hörbares Audio.</span></div></label>
        <label class="choice"><input type="radio" name="sa" value="1"><div><b>Zusätzlich ${esc(names)}</b>
          <span>Der Aufnahme-Ausschnitt (${S.listen.seconds} s Audio) wird an ${esc(names)} gesendet. Findet mehr Songs, aber ${mode === "mic" ? "Gespräche im Raum würden mitgeschickt." : "auch laufende Sprach-/Videoanrufe würden mitgeschickt."}</span></div></label>`,
      value: box => $("input[name=sa]:checked", box).value });   // "0" | "1"; Abbrechen = false
    if (v === false) return false;
    savePrefs({ [`send_audio_${mode}`]: v === "1" });
  }
  return true;
}

function stopHold() { try { S.listen.holdWs?.close(); } catch { } S.listen.holdWs = null; }

const fmtClock = s => `${Math.floor(s / 60)}:${String(Math.max(0, Math.round(s % 60))).padStart(2, "0")}`;
const HOLD_WHY = { player: "Player meldet neuen Titel", stille: "Pause erkannt", klang: "Klang hat sich geändert", zeit: "Song müsste zu Ende sein" };

/* Dauer-Modus: lokal warten, bis der Song wechselt – statt alle paar Sekunden Shazam zu fragen */
function holdForChange(r) {
  const L = S.listen;
  const known = r.found && r.left != null;
  if (known && r.left < 6) return Promise.resolve("zeit");
  const limit = known ? Math.min(r.left + 2, 240) : r.found ? 90 : 30;
  const head = r.found ? (r.local ? "Derselbe Song läuft (lokal erkannt)" : "Derselbe Song läuft") : "Nicht erkannt – Dauer-Modus wartet";
  return new Promise(res => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/hold?source=${enc(L.source)}&limit=${Math.round(limit)}`);
    L.holdWs = ws;
    let done = false;
    const finish = why => { if (done) return; done = true; if (L.holdWs === ws) L.holdWs = null; try { ws.close(); } catch { } res(why); };
    ws.onmessage = e => {
      const d = JSON.parse(e.data);
      if (d.done) return finish(d.why);
      if (!(L.auto && L.running)) return finish("stop");
      L.msg = [head, `nächste Prüfung in ${fmtClock(d.left)} oder sofort bei Songwechsel – ohne Online-Abfrage`];
      renderListenState();
    };
    ws.onerror = () => finish("fehler");
    ws.onclose = () => finish("zu");
  });
}

async function listenOnce(opts = {}) {
  const L = S.listen;
  stopHold();
  if (L.busy) return;
  if (!(await ensureListenConsent(L.mode))) { L.running = false; renderListenState(); return; }
  await Limits.refresh();
  if (Limits.wait("shazam") > 0) {
    if (L.auto && L.running) {   // Dauer-Modus: Pause abwarten, dann weiter
      L.msg = ["Shazam-Limit – Dauer-Modus wartet", `geht in ${Limits.wait("shazam")} s automatisch weiter`]; renderListenState();
      await sleep(Math.min(Limits.wait("shazam"), 5) * 1000 + 300);
      if (L.auto && L.running) listenOnce();
      return;
    }
    L.msg = ["Shazam-Limit erreicht", `Nichts aufgenommen – wieder frei in ${Limits.wait("shazam")} s`]; renderListenState();
    return;
  }
  L.busy = true; L.phase = "rec"; L.started = Date.now(); L.msg = null; L.tempoOffer = false; L.longOffer = false;
  const secs = opts.seconds || L.seconds;
  L.tempoRun = !!opts.tempo;
  let last = null;
  renderListenState(); ringProgress();
  const micMeter = L.mode === "mic";
  if (micMeter) Meter.start(L.source);
  const t = setTimeout(() => { L.phase = "rec2"; renderListenState(); }, secs * 1000 + 1500);
  const t2 = setTimeout(() => { L.phase = "rec3"; renderListenState(); }, secs * 1000 + 6500);
  try {
    const r = await api("/api/listen", { method: "POST", body: { mode: L.mode, source: L.source, seconds: secs, skip_key: L.auto ? L.lastKey : null, force: !!opts.force, auto: !!L.auto, tempo: !!opts.tempo } });
    last = r;
    L.tempoOffer = !L.auto && !r.same && !!r.tempo_offer;
    L.longOffer = !L.auto && !r.found && !r.silent && !r.limited && secs < 20;
    if (!r.found && r.silent) L.msg = ["Kein Ton angekommen", `Pegel ${Math.round(r.level_db)} dB – anderes Gerät wählen oder „Gerät mit Signal finden“`];
    else if (r.limited || (!r.found && /Limit|antwortet nicht/.test(r.errors?.shazam || ""))) {
      L.msg = ["Shazam-Limit erreicht", (r.errors?.shazam || "").replace(/^\w+: /, "")];
    }
    else if (!r.found) L.msg = ["Nichts erkannt", `Ton kam an (${Math.round(r.level_db)} dB) – länger aufnehmen oder anderen Teil probieren${r.notice ? " · " + r.notice : ""}${r.missed ? " · unter Einstellungen › Nicht erkannt gemerkt" : ""}`];
    else if (r.same) L.msg = ["Läuft noch", L.current ? `${L.current.track.artists[0]} – ${L.current.track.title}` : ""];
    else {
      L.current = r; L.lastKey = r.key;
      L.msg = [r.local ? "Lokal erkannt" : r.extra?.unsure ? "Erkannt – aber unsicher" : "Erkannt", `${r.track.artists.join(", ")} – ${r.track.title}${r.local ? " · keine Shazam-Anfrage" : r.cached ? " · Infos aus dem Speicher" : ""}`];
      renderListenResult(); refreshMeta();
      if (r.notice) toast(r.notice);
      if (location.hash !== "#/listen" && location.hash !== "") toast(`Erkannt: ${r.track.artists[0]} – ${r.track.title}`);
    }
  } catch (e) { L.msg = ["Fehler", e.message]; L.running = false; }
  clearTimeout(t); clearTimeout(t2);
  Limits.refresh();
  if (micMeter && !Meter.testing) Meter.stop();
  L.busy = false; renderListenState(); ringProgress();
  if (L.auto && L.running) {
    const why = last && !last.silent && !last.limited ? await holdForChange(last) : (await sleep(1500), null);
    if (why === "fehler" || why === "zu") await sleep(3000);
    if (L.auto && L.running) { if (HOLD_WHY[why]) L.msg = [HOLD_WHY[why], "prüfe neu …"]; listenOnce(); }
    else renderListenState();
  }
}

/* ---------- Verlauf */
Views.history = async (main) => {
  main.innerHTML = `<div class="page"><div class="page-head"><div><h1>Verlauf</h1><p>Alles, was erkannt wurde – auf allen Rechnern, die diese Daten nutzen.</p></div></div>${skeletonRows(6)}</div>`;
  const items = await api("/api/history?limit=3000");
  const multiHost = new Set(items.map(i => i.host)).size > 1;
  let q = "", gf = null, of = "";
  const origin = i => i.source === "shazam-app" ? "shazam" : (i.host || "").startsWith("Handy") ? "handy" : "pc";
  const nOrig = k => items.filter(i => origin(i) === k).length;
  const origins = [["", "Alle"], ["pc", "Am PC"], ["handy", "Am Handy erkannt"], ["shazam", "Aus der Shazam-App"]].filter(([k]) => !k || nOrig(k));
  const genres = [...new Map(items.filter(i => i.genre).map(i => [i.genre, i])).keys()];
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Verlauf</h1><p>${items.length} erkannte Songs</p></div>
      ${items.length > 1 ? `<button class="btn btn--sm btn--ghost" id="hMix" title="Erkennungen am Stück (z. B. ein DJ-Mix im Dauer-Modus) als Tracklist mit Zeitstempeln">${icon("clock")}Mix-Tracklists</button>` : ""}</div>
    <div id="hMixBox"></div>
    ${items.length ? `<div class="toolbar">
      <div class="input-icon">${icon("search")}<input class="input" id="hq" placeholder="Suchen …"></div>
      ${origins.length > 2 ? `<div class="filter-chips" id="ho">${origins.map(([k, l]) => `<button class="${k === of ? "on" : ""}" data-o="${k}">${l}${k ? ` <span class="num">${nOrig(k)}</span>` : ""}</button>`).join("")}</div>` : ""}
      <div class="filter-chips" id="hf"><button class="on" data-g="">Alle</button>${genres.map(g => `<button data-g="${esc(g)}"><span class="dot" style="background:${genreColor(g)}"></span>${esc(g)}</button>`).join("")}</div>
    </div>
    <div id="hShz"></div>
    <div class="rows" id="hrows"></div>` : `<div class="empty">${icon("clock")}<h3>Noch leer</h3><p>Erkannte Songs landen automatisch hier.</p></div>`}
  </div>`;
  if (!items.length) return;
  const draw = () => {
    const f = items.filter(i => (!gf || i.genre === gf) && (!of || origin(i) === of) && (!q || `${i.title} ${i.artists.join(" ")}`.toLowerCase().includes(q)));
    const sh = $("#hShz");
    if (sh) {
      sh.innerHTML = of === "shazam" ? `<div class="dc-note">${icon("info")}<span>Diese Shazams hat dein Handy aus der Shazam-App übernommen. Sie stehen auch als Playlist
        <b>„Shazams vom Handy“</b> unter Dienste › Shazam – zum Einsortieren nach Genre und Übertragen wie jede andere Playlist.</span>
        <button class="btn btn--sm btn--primary" id="hShzGo">${icon("split")}Einsortieren</button></div>` : "";
      hydrateIcons(sh);
      $("#hShzGo")?.addEventListener("click", () => { location.hash = `#/services?svc=shazam&pl=h0&name=${enc("Shazams vom Handy")}`; });
    }
    $("#hrows").innerHTML = `<div class="row row--history head"><div></div><div>Titel</div><div>Genre</div><div>BPM</div><div>Wann</div><div></div></div>` +
      f.map(i => `<div class="row row--history" data-id="${i.id}">
        <div class="thumb-wrap">${i.cover ? `<img class="thumb" src="${esc(i.cover)}" alt="" loading="lazy">` : `<div class="thumb"></div>`}
          ${i.preview_url ? `<button class="thumb-play" ${playAttr(i)} aria-label="Hörprobe">${icon("play")}</button>` : ""}</div>
        <div class="cell-main"><div class="cell-title">${esc(i.title)}</div><div class="cell-sub">${esc(i.artists.join(", "))}</div></div>
        <div>${genreChip(i.genre, i.subgenre)}</div>
        <div class="cell-muted">${i.bpm ? Math.round(i.bpm) : "–"}</div>
        <div class="cell-muted" title="${esc(i.host)}">${relTime(i.ts)}${multiHost ? " · " + esc(i.host) : ""}</div>
        <div class="row-act"><button class="icon-btn" aria-label="Details">${icon("arrow")}</button></div>
      </div>`).join("") + (f.length ? "" : `<div class="cell-sub" style="padding:16px 12px">Keine Treffer.</div>`);
    $$("#hrows .row[data-id]").forEach(row => row.onclick = () => openDrawer(() => api(`/api/recognition/${row.dataset.id}`)));
    Player.sync();
  };
  $("#hq").oninput = e => { q = e.target.value.toLowerCase(); draw(); };
  $("#hMix")?.addEventListener("click", () => mixSessions($("#hMixBox")));
  $$("#ho button").forEach(b => b.onclick = () => { of = b.dataset.o; $$("#ho button").forEach(x => x.classList.toggle("on", x === b)); draw(); });
  $$("#hf button").forEach(b => b.onclick = () => { gf = b.dataset.g || null; $$("#hf button").forEach(x => x.classList.toggle("on", x === b)); draw(); });
  draw();
};

// Mix-Tracklists: Sitzungen = Erkennungen mit < 15 min Abstand
async function mixSessions(box) {
  if (box.innerHTML) { box.innerHTML = ""; return; }
  box.innerHTML = skeletonRows(2);
  const list = await api("/api/mixlog").catch(e => (toast(e.message, "err"), []));
  box.innerHTML = `<div class="card mx-sess"><div class="mx-sess-head"><b>Mix-Tracklists</b><span class="cell-sub">Erkennungen am Stück (weniger als 15 Minuten Pause) – z. B. ein DJ-Mix im Dauer-Modus</span></div>
    ${list.length ? list.map(s => `<div class="mx-srow"><div class="sl"><span>${esc(s.label)} · ${s.count} Songs</span><em>${s.first.map(esc).join(" · ")}${s.count > 3 ? " …" : ""}</em></div>
      <button class="btn btn--sm" data-sess="${s.id}">${icon("copy")}Tracklist</button></div>`).join("")
      : `<div class="cell-sub">Noch keine Sitzung mit mehreren Songs. Tipp: beim Mix den Dauer-Modus einschalten.</div>`}</div>`;
  hydrateIcons(box);
  $$("[data-sess]", box).forEach(b => b.onclick = () => mixTracklist(+b.dataset.sess));
}
async function mixTracklist(sid) {
  let fmt = store.get("mixFmt", "offset"), genre = store.get("mixGenre", false), d;
  const load = async () => { d = await api(`/api/mixlog/${sid}?fmt=${fmt}&genre=${genre}`); const ta = $("#mxText"); if (ta) ta.value = d.text; return d; };
  try { await load(); } catch (e) { return toast(e.message, "err"); }
  modal({ title: "Tracklist", text: esc(`${d.label} · ${d.count} Songs`), wide: true, confirm: "Kopieren", cancel: "Schließen",
    body: `<div class="segmented" id="mxFmt">${[["offset", "Zeit ab Start (00:00)"], ["clock", "Uhrzeit"], ["plain", "Nur nummeriert"]].map(([v, l]) => `<button data-f="${v}" class="${v === fmt ? "on" : ""}">${l}</button>`).join("")}</div>
      <label class="check" style="display:flex;gap:8px;margin:10px 0"><input type="checkbox" id="mxGenre" ${genre ? "checked" : ""}><span>Genre dazuschreiben</span></label>
      <textarea class="input mx-text" id="mxText" spellcheck="false" readonly>${esc(d.text)}</textarea>
      <div class="cell-sub" style="margin-top:6px;white-space:normal">Zeitstempel = Zeitpunkt der Erkennung (ein paar Sekunden nach Songbeginn). „Zeit ab Start“ passt z. B. als YouTube-Kapitel oder SoundCloud-Beschreibung.</div>
      <div class="mx-save"><input class="input" id="mxName" value="${esc(`Mix ${d.label.split(",")[0]}`)}" aria-label="Name der Playlist">
        <button class="btn btn--sm" id="mxSave">${icon("plus")}Als Playlist speichern</button></div>`,
    onConfirm: async () => { toast(await Clip.write($("#mxText").value) ? "Tracklist kopiert" : "Kopieren nicht möglich"); throw { silent: true }; } });
  hydrateIcons($("#modalBox"));
  $$("#mxFmt button").forEach(b => b.onclick = async () => { fmt = b.dataset.f; store.set("mixFmt", fmt); $$("#mxFmt button").forEach(x => x.classList.toggle("on", x === b)); await load(); });
  $("#mxGenre").onchange = async e => { genre = e.target.checked; store.set("mixGenre", genre); await load(); };
  $("#mxSave").onclick = async () => {
    const name = $("#mxName").value.trim(); if (!name) return toast("Bitte einen Namen eingeben", "err");
    try { const r = await api(`/api/mixlog/${sid}/save`, { method: "POST", body: { name } }); toast(`„${r.name}“: ${r.added} Songs`); refreshMeta(); } catch (e) { toast(e.message, "err"); }
  };
}

/* ---------- Playlists */
function mosaic(p) {
  const covers = (p.covers || []).filter(Boolean);
  const top = p.top?.[0];
  const col = top ? genreColor(top[2], top[3]) : null;
  if (covers.length >= 4) return `<div class="mosaic">${covers.slice(-4).map(c => `<img src="${esc(c)}" alt="" loading="lazy">`).join("")}</div>`;
  if (covers.length) return `<div class="mosaic single"><img src="${esc(covers[covers.length - 1])}" alt="" loading="lazy"></div>`;
  return `<div class="mosaic"><div class="mosaic-ph" ${col ? `style="--g:${col}"` : ""}>${icon("stack")}</div></div>`;
}

/* Gemeinsame Bausteine für Playlist-Seiten (lokal + Dienste) */
const durText = ms => { const m = Math.round(ms / 60000); return m >= 60 ? `${Math.floor(m / 60)} Std. ${m % 60} Min.` : `${m} Min.`; };
const withPreview = t => ({ ...t, artists: t.artists?.length ? t.artists : (t.artist ? [t.artist] : []),
  preview_url: t.preview_url || `deezer:${(t.artists || [])[0] || t.artist || ""}|${t.title}` });
const distBar = (dist, total) => dist?.length ? `<div class="dist">${dist.map(g => `<b title="${esc(g.label)} · ${g.count}" style="flex:${g.count};background:${genreColor(g.genre, g.subgenre)}"></b>`).join("")}</div>
  <div class="dist-legend">${dist.slice(0, 6).map(g => `<span><span class="dot" style="background:${genreColor(g.genre, g.subgenre)}"></span>${esc(g.label)} <span class="muted num">${Math.round(g.count / (total || 1) * 100)} %</span></span>`).join("")}</div>` : "";

function plHero(o) {
  const stats = [`${o.count} ${o.count === 1 ? "Song" : "Songs"}`, o.ms ? durText(o.ms) : "", ...(o.extra || [])].filter(Boolean);
  return `<section class="ph" style="--hc:${o.color || "var(--accent)"}">
    <div class="ph-art">${o.art || mosaic({ covers: o.covers || [], top: o.dist?.[0] ? [[0, 0, o.dist[0].genre, o.dist[0].subgenre]] : [] })}</div>
    <div class="ph-info">${o.back ? `<a class="ph-back" href="${o.back[0]}">← ${esc(o.back[1])}</a>` : ""}
      <div class="ph-kicker">${o.kicker}</div>
      <h1 ${o.titleId ? `id="${o.titleId}"` : ""} spellcheck="false">${esc(o.title)}</h1>
      <div class="ph-meta">${stats.join(`<span class="sep">·</span>`)}</div>
      ${distBar(o.dist, o.count)}</div></section>
  <div class="ph-bar">
    <button class="ph-play" id="plPlay" title="Hörproben nacheinander abspielen" aria-label="Abspielen">${icon("play")}</button>
    <button class="icon-btn ph-btn" id="plShuffle" title="Zufällige Reihenfolge" aria-label="Zufällig">${icon("shuffle")}</button>
    <div class="ph-actions">${o.actions || ""}</div>
    <div class="ph-tools">
      <label class="ph-search">${icon("search")}<input id="plQ" placeholder="In Playlist suchen" autocomplete="off" spellcheck="false"></label>
      <select class="select select--sm" id="plSort" aria-label="Sortieren">${o.sorts.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
    </div></div>`;
}

/* Trackliste mit Suche & Sortierung. items: [{t, c3, c4, act, key}] – t = Track (mit artists) */
function plList(main, items, o) {
  const box = $("#plList", main);
  let q = "", by = "";
  const key = { title: x => x.t.title || "", artist: x => (x.t.artists || [])[0] || "", genre: x => x.t.subgenre || x.t.genre || "~",
    album: x => x.t.album || "~", dur: x => x.t.duration_ms || 0 };
  const draw = () => {
    let view = items.map((x, i) => ({ ...x, i }));
    if (q) view = view.filter(x => `${x.t.title} ${(x.t.artists || []).join(" ")} ${x.t.album || ""} ${x.t.genre || ""} ${x.t.subgenre || ""}`.toLowerCase().includes(q));
    if (by) view.sort((a, b) => { const A = key[by](a), B = key[by](b); return typeof A === "number" ? A - B : A.localeCompare(B, "de"); });
    box.innerHTML = view.length ? `<div class="tl-head"><div class="tl-idx">#</div><div>Titel</div><div>${o.h3}</div><div>${o.h4}</div><div></div></div>
      ${view.map(x => `<div class="tl-row" data-i="${x.i}" ${x.key ? `data-key="${esc(x.key)}"` : ""}>
        <div class="tl-idx"><span class="num">${x.i + 1}</span><button class="tl-play" ${playAttr(x.t)} aria-label="Hörprobe">${icon("play")}</button></div>
        <div class="tl-main">${x.t.cover ? `<img class="thumb" src="${esc(x.t.cover)}" alt="" loading="lazy">` : `<div class="thumb"></div>`}
          <div class="cell-main"><div class="cell-title">${esc(x.t.title)}</div><div class="cell-sub">${esc((x.t.artists || []).join(", "))}</div></div></div>
        <div class="tl-c3">${x.c3 || ""}</div><div class="tl-c4 cell-muted">${x.c4 || ""}</div><div class="tl-act">${x.act || ""}</div></div>`).join("")}`
      : `<div class="empty">${icon("search")}<h3>${q ? "Nichts gefunden" : "Leer"}</h3><p>${q ? "Anderen Suchbegriff versuchen." : esc(o.empty || "")}</p></div>`;
    hydrateIcons(box); Player.sync(); o.bind?.(box);
    if (!o.coversAsked) {
      o.coversAsked = true;
      const heroEmpty = !$(".ph-art img", main);
      lazyCovers(box, items.map(x => x.t).slice(0, 60), i => `.tl-row[data-i="${i}"]`).then(() => {
        const cv = [...new Set(items.map(x => x.t.cover).filter(Boolean))].slice(0, 4), art = $(".ph-art", main);
        if (heroEmpty && cv.length && art) art.innerHTML = mosaic({ covers: cv, top: [] });   // Cover-Bild vom Anbieter, nicht gespeichert
      });
    }
  };
  $("#plQ", main).oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  $("#plSort", main).onchange = e => { by = e.target.value; draw(); };
  $("#plPlay", main).onclick = () => Player.playList(items.map(x => x.t));
  $("#plShuffle", main).onclick = () => Player.playList(items.map(x => x.t), true);
  draw();
}

/* ---------- Playlists (Übersicht) */
function plCard(p) {
  const top = p.top?.[0], col = top ? genreColor(top[2], top[3]) : "var(--accent)";
  const tot = (p.top || []).reduce((a, t) => a + t[1], 0) || 1;
  return `<a class="pl-card" href="#/playlists/${enc(p.name)}" style="--g:${col}" data-name="${esc(p.name.toLowerCase())}">
    <div class="pl-art">${mosaic(p)}<button class="pl-fab" data-plplay="${esc(p.name)}" aria-label="Abspielen" title="Hörproben abspielen">${icon("play")}</button></div>
    <div class="pl-name">${esc(p.name)}</div>
    <div class="pl-sub">${p.count} ${p.count === 1 ? "Song" : "Songs"}${top ? ` · ${esc(top[0])}` : ""}</div>
    ${p.top?.length ? `<div class="pl-dist">${p.top.map(t => `<b style="flex:${t[1] / tot};background:${genreColor(t[2], t[3])}"></b>`).join("")}</div>` : ""}</a>`;
}
function svcCard(sid, p) {
  const [m, c] = svcStyle(sid);
  const art = p.cover ? `<div class="mosaic single"><img src="${esc(p.cover)}" alt="" loading="lazy"></div>`
    : `<div class="mosaic"><div class="mosaic-ph svc-ph" style="--g:${c}"><span>${p.id === "__liked__" ? "♥" : m}</span></div></div>`;
  return `<a class="pl-card" href="${svcPlHref(sid, p)}" style="--g:${c}" data-name="${esc(p.name.toLowerCase())}">
    <div class="pl-art">${art}<button class="pl-fab" data-svcplay="${esc(p.id)}" data-sid="${sid}" aria-label="Abspielen" title="Hörproben abspielen">${icon("play")}</button></div>
    <div class="pl-name">${esc(p.name)}</div>
    <div class="pl-sub">${p.count != null ? `${p.count} Songs` : "Playlist"}${p.own === false ? " · gefolgt" : ""}</div></a>`;
}
async function svcTracks(sid, pid, fresh = false) {
  const r = await api(`/api/services/${sid}/playlists/${encodeURIComponent(pid)}/tracks${fresh ? "?refresh=1" : ""}`);
  return r.tracks.map(withPreview);
}
function bindCardPlay(root) {
  $$("[data-plplay]", root).forEach(b => b.onclick = async e => {
    e.preventDefault(); e.stopPropagation();
    const d = await api(`/api/playlists/${enc(b.dataset.plplay)}`).catch(() => null);
    if (d) Player.playList(d.entries.map(x => withPreview(x.track)));
  });
  $$("[data-svcplay]", root).forEach(b => b.onclick = async e => {
    e.preventDefault(); e.stopPropagation();
    b.classList.add("busy");
    try { Player.playList(await svcTracks(b.dataset.sid, b.dataset.svcplay)); } catch (err) { toast(err.message, "err"); }
    b.classList.remove("busy");
  });
}

Views.playlists = async (main) => {
  await refreshMeta();
  if (!SideSvc.loaded) await SideSvc.load();
  const local = S.playlists.filter(p => p.origin === "lokal"), ext = S.playlists.filter(p => p.origin !== "lokal");
  const songs = local.reduce((a, p) => a + p.count, 0);
  const genres = new Set(local.flatMap(p => (p.top || []).map(t => t[2]).filter(Boolean))).size;
  const svcs = SideSvc.list;
  let tab = store.get("plTab", "lokal");
  if (tab !== "lokal" && !svcs.some(s => s.id === tab)) tab = "lokal";
  main.innerHTML = `<div class="page view-enter">
    <section class="pls-hero">
      <div><div class="ph-kicker">Bibliothek</div><h1>Playlists</h1>
        <p>Deine Sammel-Playlists – und die Listen deiner verbundenen Dienste an einem Ort.</p></div>
      <div class="pls-stats"><div><b class="num">${local.length}</b><span>Playlists</span></div><div><b class="num">${songs}</b><span>Songs</span></div><div><b class="num">${genres}</b><span>Genres</span></div></div>
    </section>
    <div class="pls-bar">
      <div class="seg" id="plTabs"><button data-tab="lokal">${icon("stack")}Lokal</button>${svcs.map(s => { const [m, c] = SVC_STYLE[s.id] || ["?", "#888"];
        return `<button data-tab="${s.id}"><span class="ss-badge sm" style="--pc:${c}">${m}</span>${esc(s.name)}</button>`; }).join("")}</div>
      <div class="ph-tools">
        <label class="ph-search">${icon("search")}<input id="plsQ" placeholder="Playlist suchen" autocomplete="off" spellcheck="false"></label>
        <select class="select select--sm" id="plsSort" aria-label="Sortieren"><option value="">Name A–Z</option><option value="za">Name Z–A</option><option value="count">Größe</option><option value="updated">Zuletzt geändert</option><option value="created">Neueste zuerst</option></select>
      </div></div>
    <div id="plsOut"></div></div>`;
  hydrateIcons(main);
  let q = "", by = store.get("plSort", "");
  if (by === "name") by = "";                      // alte Einstellung
  $("#plsSort").value = by;
  const sorted = list => sortPlaylists(list.filter(p => !q || p.name.toLowerCase().includes(q)), by);
  const draw = async () => {
    $$("#plTabs button").forEach(b => b.classList.toggle("on", b.dataset.tab === tab));
    const out = $("#plsOut");
    if (tab === "lokal") {
      const l = sorted(local), e = sorted(ext);
      out.innerHTML = local.length ? `${l.length ? `<div class="pl-grid">${l.map(plCard).join("")}</div>` : `<div class="empty"><h3>Nichts gefunden</h3></div>`}
        ${e.length ? `<div class="section-title">Von Plattformen importiert</div><div class="pl-grid">${e.map(plCard).join("")}</div>` : ""}`
        : `<div class="empty">${icon("stack")}<h3>Noch keine Playlists</h3><p>Erkenne einen Song und sortiere ihn ein – die Playlist wird dabei automatisch angelegt.</p></div>`;
    } else {
      const s = svcs.find(x => x.id === tab);
      if (!Array.isArray(SideSvc.pls[tab])) out.innerHTML = `<div class="pl-grid">${Array.from({ length: 6 }, () => `<div class="pl-card"><div class="mosaic skeleton"></div><div class="skeleton" style="height:12px;width:70%;margin-top:12px"></div></div>`).join("")}</div>`;
      const pls = await SideSvc.fetch(tab);
      if (tab !== s.id || !document.body.contains(out)) return;
      out.innerHTML = pls?.error ? `<div class="notice">${icon("info")}<div>${esc(pls.error)}</div></div>`
        : `<div class="pls-src">${icon("info")}Gelesen über die offizielle Schnittstelle von ${esc(s.name)} (${esc(s.account)}) – nur angezeigt, nichts gespeichert.</div>
           <div class="pl-grid">${sorted(pls || []).map(p => svcCard(tab, p)).join("")}</div>`;
    }
    hydrateIcons(out); bindCardPlay(out);
  };
  $$("#plTabs button").forEach(b => b.onclick = () => { tab = b.dataset.tab; store.set("plTab", tab); draw(); });
  $("#plsQ").oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  $("#plsSort").onchange = e => { by = e.target.value; store.set("plSort", by); draw(); };
  draw();
};

/* ---------- Playlists zusammenführen: Songs einer Playlist (lokal, Export, Dienst, Freund) in eine bestehende oder neue lokale übernehmen */
async function plMerge(target, src, srcId) {
  const r = await api(`/api/playlists/${enc(target)}/merge`, { method: "POST", body: { src, src_id: srcId } });
  toast(r.added ? `${r.added} Songs zu „${r.name}“ hinzugefügt${r.dupes ? ` · ${r.dupes} ${r.dupes === 1 ? "war" : "waren"} schon drin` : ""}` : `Alle ${r.total} Songs waren schon in „${r.name}“`);
  await refreshMeta();
  return r;
}
// Schieben: Quelle steht fest, Ziel wählen (bestehende lokale Playlist oder neue)
function plMergeTo(src, srcId, srcName) {
  const locals = S.playlists.filter(p => p.origin === "lokal" && !(src === "local" && p.name === srcId));
  modal({ title: "In Playlist übernehmen", text: `Die Songs aus „${esc(srcName)}“ kommen zusätzlich in die gewählte Playlist. Doppelte werden übersprungen, „${esc(srcName)}“ bleibt unverändert.`,
    confirm: "Übernehmen",
    body: `<div class="mg-form"><div class="field"><label>Ziel</label><select class="select" id="mgDst">
        <option value="">＋ Neue Playlist …</option>${locals.map(p => `<option value="${esc(p.name)}">${esc(p.name)} (${p.count})</option>`).join("")}</select></div>
      <div class="field" id="mgNewF"><label>Name der neuen Playlist</label><input class="input" id="mgNew" value="${esc(srcName)}" maxlength="200"></div></div>`,
    onConfirm: async box => {
      const dst = $("#mgDst", box).value || $("#mgNew", box).value.trim();
      if (!dst) { toast("Bitte einen Namen eingeben", "err"); throw { silent: true }; }
      const r = await plMerge(dst, src, srcId);
      location.hash = `#/playlists/${enc(r.name)}`;
    } });
  const dst = $("#mgDst"), nf = $("#mgNewF");
  if (locals.length) dst.value = locals[0].name;
  const sync = () => nf.classList.toggle("hidden", !!dst.value);
  dst.onchange = sync; sync();
}
// Holen: Ziel steht fest, Quelle wählen (eigene Playlists, Exporte, verbundene Dienste)
async function plMergeFrom(target, onDone) {
  if (!SideSvc.loaded) await SideSvc.load();
  const srcs = [{ id: "local", name: "Deine Playlists" }, ...SideSvc.list];
  modal({ title: "Songs aus anderer Playlist holen", text: `Die Songs kommen zusätzlich in „${esc(target)}“. Doppelte werden übersprungen, die Quelle bleibt unverändert.`,
    confirm: "Hinzufügen",
    body: `<div class="mg-form"><div class="field"><label>Von</label><select class="select" id="mgSrc">${srcs.map(s => `<option value="${esc(s.id)}">${esc(s.name)}</option>`).join("")}</select></div>
      <div class="field"><label>Playlist</label><select class="select" id="mgPl"></select></div></div>`,
    onConfirm: async box => {
      const pl = $("#mgPl", box);
      if (!pl.value) { toast("Bitte eine Playlist wählen", "err"); throw { silent: true }; }
      await plMerge(target, $("#mgSrc", box).value, pl.value);
      onDone?.();
    } });
  const srcSel = $("#mgSrc"), plSel = $("#mgPl");
  const fill = async () => {
    plSel.disabled = true; plSel.innerHTML = `<option value="">Lade …</option>`;
    let list;
    if (srcSel.value === "local") list = S.playlists.filter(p => p.name !== target || p.origin !== "lokal")
      .map(p => ({ id: p.name, name: p.origin === "lokal" ? p.name : `${p.name} · ${p.origin}`, count: p.count }));
    else { const r = await SideSvc.fetch(srcSel.value); list = Array.isArray(r) ? r : []; if (r?.error) toast(r.error, "err"); }
    if (!document.body.contains(plSel)) return;
    plSel.innerHTML = list.length ? list.map(p => `<option value="${esc(p.id)}">${esc(p.name)}${p.count != null ? ` (${p.count})` : ""}</option>`).join("")
      : `<option value="">– keine Playlists –</option>`;
    plSel.disabled = !list.length;
  };
  srcSel.onchange = fill; fill();
}

Views.playlist = async (main, name) => {
  const d = await api(`/api/playlists/${enc(name)}`);
  const tracks = d.entries.map(e => withPreview(e.track));
  const ms = tracks.reduce((a, t) => a + (t.duration_ms || 0), 0);
  const top = d.dist[0];
  main.innerHTML = `<div class="page page--pl view-enter">
    ${plHero({ kicker: "Playlist · lokal", title: name, titleId: "plTitle", count: tracks.length, ms, dist: d.dist,
      covers: tracks.map(t => t.cover).filter(Boolean).slice(0, 4), color: top ? genreColor(top.genre, top.subgenre) : null,
      back: ["#/playlists", "Playlists"], extra: top ? [`meist ${esc(top.label)}`] : [],
      sorts: [["", "Reihenfolge"], ["title", "Titel"], ["artist", "Künstler"], ["genre", "Genre"]],
      actions: `<button class="btn btn--sm btn--ghost" id="plRename">${icon("pencil")}Umbenennen</button>
        <button class="btn btn--sm btn--ghost" id="plMergeTo" title="Diese Songs zusätzlich in eine andere Playlist übernehmen">${icon("copy")}In andere Playlist</button>
        <button class="btn btn--sm btn--ghost" id="plMergeFrom" title="Songs aus einer anderen Playlist oder einem Dienst hierher holen">${icon("plus")}Songs holen</button>
        <a class="btn btn--sm btn--ghost" href="#/split?pl=${enc(name)}">${icon("split")}Nach Genre aufteilen</a>
        <button class="btn btn--sm btn--ghost btn--danger" id="plDelete">${icon("trash")}Löschen</button>` })}
    <div class="tl" id="plList"></div></div>`;
  hydrateIcons(main);
  plList(main, d.entries.map((e, i) => ({ t: tracks[i], key: e.key, c3: genreChip(e.track.genre, e.track.subgenre), c4: relTime(e.ts),
    act: `<button class="icon-btn" data-remove="${esc(e.key)}" aria-label="Entfernen" title="Aus Playlist entfernen">${icon("x")}</button>` })),
  { h3: "Genre", h4: "Hinzugefügt", empty: "Füge Songs über „Erkennen“ oder den Verlauf hinzu.", bind: box => {
    $$("[data-remove]", box).forEach(b => b.onclick = async ev => {
      ev.stopPropagation();
      await api("/api/unassign", { method: "POST", body: { key: b.dataset.remove, playlist: name } });
      toast("Entfernt"); refreshMeta(); Views.playlist(main, name);
    });
    $$(".tl-row[data-key]", box).forEach(row => row.onclick = e => {
      if (e.target.closest("button, a")) return;
      openDrawer(() => api(`/api/track`, { method: "POST", body: { key: row.dataset.key } }));
    });
  } });
  // App-eigener Dialog statt confirm(): der native Dialog kann das App-Fenster (pywebview) blockieren
  $("#plMergeTo").onclick = () => plMergeTo("local", name, name);
  $("#plMergeFrom").onclick = () => plMergeFrom(name, () => Views.playlist(main, name));
  $("#plDelete").onclick = () => modal({
    title: "Playlist löschen?", text: `„${esc(name)}“ wird gelöscht. Die Songs bleiben im Verlauf.`, confirm: "Löschen", danger: true,
    onConfirm: async () => {
      await api(`/api/playlists/${enc(name)}`, { method: "DELETE" });
      toast("Playlist gelöscht"); await refreshMeta(); location.hash = "#/playlists";
    },
  });
  $("#plRename").onclick = () => {
    const h = $("#plTitle");
    h.contentEditable = "true"; h.focus();
    document.getSelection().selectAllChildren(h);
    const done = async save => {
      h.contentEditable = "false"; h.onblur = h.onkeydown = null;
      const nn = h.textContent.trim();
      if (save && nn && nn !== name) {
        await api(`/api/playlists/${enc(name)}/rename`, { method: "POST", body: { new: nn } });
        toast("Umbenannt"); await refreshMeta(); location.hash = `#/playlists/${enc(nn)}`;
      } else h.textContent = name;
    };
    h.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); done(true); } if (e.key === "Escape") done(false); };
    h.onblur = () => done(true);
  };
};

/* ---------- Statistik & Jahresrückblick (nur lokale Daten) */
const StatsUI = { year: null, source: "alle" };
// Säulendiagramm (eine Reihe): Säulen mit 2px Abstand, Hover-Tooltip, Zahlen zusätzlich als Tabelle
function colChart(id, rows, { label, value = r => r.n, tip, color = "var(--accent)", unit = "" }) {
  const max = Math.max(1, ...rows.map(value));
  return `<div class="st-chart-wrap"><div class="st-chart" data-chart="${id}">
      <span class="st-max num">${max}${unit}</span><div class="sp-grid"><i style="bottom:50%"></i><i style="bottom:100%"></i></div>
      <div class="st-cols">${rows.map((r, i) => `<b data-i="${i}" style="height:${value(r) ? Math.max(2, value(r) / max * 100) : 0}%;background:${color}"></b>`).join("")}</div>
      <div class="sp-tip hidden"></div></div>
    <div class="st-xl">${rows.map(r => `<span>${esc(label(r))}</span>`).join("")}</div>
    <details class="st-table"><summary>Als Tabelle</summary><table>${rows.map(r => `<tr><td>${esc(label(r))}</td><td class="num">${value(r)}${unit}</td></tr>`).join("")}</table></details></div>`;
}
function bindColChart(root, id, rows, tip) {
  const c = $(`[data-chart="${id}"]`, root); if (!c) return;
  const tt = $(".sp-tip", c);
  $$(".st-cols b", c).forEach(b => {
    b.onmouseenter = () => { tt.innerHTML = tip(rows[+b.dataset.i]); tt.classList.remove("hidden");
      const r = b.getBoundingClientRect(), cr = c.getBoundingClientRect();
      tt.style.left = `${Math.min(cr.width - tt.offsetWidth, Math.max(0, r.left - cr.left + r.width / 2 - tt.offsetWidth / 2))}px`; };
    b.onmouseleave = () => tt.classList.add("hidden");
  });
}
// Rangliste: Name | Balken | Zahl (Zahlen stehen als Text daneben, nicht im Balken)
const rankList = (rows, name, color) => { const max = Math.max(1, ...rows.map(r => r.n));
  return rows.length ? `<div class="st-rank">${rows.map(r => `<div class="st-rrow"><span class="st-rn" title="${esc(name(r))}">${esc(name(r))}</span>
    <span class="st-rb"><b style="width:${r.n / max * 100}%;background:${color(r)}"></b></span><span class="st-rv num">${r.n}</span></div>`).join("")}</div>`
    : `<div class="cell-sub">Noch keine Daten.</div>`; };

Views.stats = async (main) => {
  main.innerHTML = `<div class="page view-enter">${skeletonRows(4)}</div>`;
  const q = new URLSearchParams({ source: StatsUI.source, year: StatsUI.year ?? "" });
  const d = await api(`/api/stats?${q}`);
  if (StatsUI.year == null && d.years.length) { StatsUI.year = d.years[0]; return Views.stats(main); }
  const z = d.zahlen, src = [["alle", "Alles"], ["erkannt", "Erkannt"], ["playlists", "In Playlists"]];
  const yr = d.year ? `${d.year}` : "insgesamt";
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>${d.year ? `Dein Jahr ${d.year}` : "Statistik"}</h1><p>Was du erkannt und gesammelt hast – ausgewertet nur auf diesem Rechner.</p></div></div>
    <div class="st-bar"><div class="segmented" id="stSrc">${src.map(([v, l]) => `<button data-v="${v}" class="${d.source === v ? "on" : ""}">${l}</button>`).join("")}</div>
      <div class="segmented" id="stYear">${d.years.map(y => `<button data-y="${y}" class="${d.year === y ? "on" : ""}">${y}</button>`).join("")}<button data-y="" class="${d.year ? "" : "on"}">Alle Jahre</button></div></div>
    ${!z.eintraege ? `<div class="empty">${icon("chart")}<h3>Noch keine Daten ${d.year ? `für ${d.year}` : ""}</h3><p>Erkenne Songs oder sortiere sie in Playlists – dann füllt sich diese Seite.</p></div>` : `
    <div class="pls-stats st-tiles"><div><b class="num">${z.songs}</b><span>Songs</span></div><div><b class="num">${z.kuenstler}</b><span>Künstler</span></div>
      <div><b class="num">${z.neue_kuenstler}</b><span>neu entdeckte Künstler</span></div><div><b class="num">${z.genres}</b><span>Genres</span></div></div>
    <div class="st-grid">
      <section class="card st-card"><h3>Top-Genres ${esc(yr)}</h3>${rankList(d.genres, r => r.genre, r => genreColor(r.genre, null))}
        ${d.unsortiert ? `<div class="cell-sub st-foot">${d.unsortiert} ohne Genre</div>` : ""}</section>
      <section class="card st-card"><h3>Top-Mikro-Genres</h3>${rankList(d.subgenres, r => r.subgenre, r => genreColor(r.genre, r.subgenre))}</section>
      <section class="card st-card"><h3>Meiste Songs von</h3>${rankList(d.kuenstler, r => r.name, () => "var(--accent)")}</section>
      <section class="card st-card"><h3>Tempo</h3>${d.tempo.length ? colChart("tempo", d.tempo, { label: r => r.von })
        + `<div class="cell-sub st-foot">${z.mit_tempo} von ${z.eintraege} mit bekanntem Tempo (BPM)</div>` : `<div class="cell-sub">Noch kein Tempo gemessen – der <a href="#/setplan">Set-Planer</a> und das Sortieren messen es mit.</div>`}</section>
      ${d.monate ? `<section class="card st-card st-wide"><h3>Pro Monat</h3><div class="st-two">
        <div><div class="st-sub">Songs</div>${colChart("monat", d.monate, { label: r => r.monat })}</div>
        <div><div class="st-sub">Neu entdeckte Künstler</div>${colChart("neu", d.monate, { label: r => r.monat, value: r => r.neu })}</div></div></section>` : ""}
    </div>`}</div>`;
  hydrateIcons(main);
  if (z.eintraege) {
    bindColChart(main, "tempo", d.tempo, r => `<b>${r.von}–${r.von + 9} BPM</b><span>${r.n} Songs</span>`);
    if (d.monate) { bindColChart(main, "monat", d.monate, r => `<b>${r.monat} ${d.year}</b><span>${r.n} Songs</span>`);
      bindColChart(main, "neu", d.monate, r => `<b>${r.monat} ${d.year}</b><span>${r.neu} neue Künstler</span>`); }
  }
  $$("#stSrc button").forEach(b => b.onclick = () => { StatsUI.source = b.dataset.v; StatsUI.year = d.year; Views.stats(main); });
  $$("#stYear button").forEach(b => b.onclick = () => { StatsUI.year = b.dataset.y ? +b.dataset.y : ""; Views.stats(main); });
};

/* ---------- Set-Planer: Reihenfolge nach Tempo, Tonart (Camelot) und Energie-Kurve */
const SetPlan = { job: null, curve: "peak", order: null, desc: null, items: null };
Views.setplan = async (main, _, params) => {
  await refreshMeta();
  const local = S.playlists.filter(p => p.origin === "lokal" && p.count);
  const curves = await api("/api/setplan/curves");
  const pre = params?.get("pl") || SetPlan.playlist || local[0]?.name;
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Set-Planer</h1><p>Baut aus einer Playlist eine DJ-Reihenfolge: passende Tonarten (Camelot), kleine Tempo-Sprünge und der Energie-Verlauf, den du willst.</p></div></div>
    ${local.length ? `<div class="card sp-form">
      <div class="field"><label>Playlist</label><select class="select" id="spPl">${local.map(p => `<option ${p.name === pre ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>
      <div class="field grow"><label>Energie-Verlauf</label><div class="segmented" id="spCurve">${curves.map(c => `<button data-c="${c.id}" title="${esc(c.hint)}" class="${c.id === SetPlan.curve ? "on" : ""}">${esc(c.name)}</button>`).join("")}</div>
        <div class="cell-sub" id="spHint">${esc(curves.find(c => c.id === SetPlan.curve)?.hint || "")}</div></div>
      <button class="btn btn--primary" id="spGo">${icon("sparkle")}Set planen</button></div>
      <div id="spJob"></div><div id="spOut"></div>`
    : `<div class="empty">${icon("stack")}<h3>Keine Playlist</h3><p>Lege zuerst eine lokale Playlist an (z. B. über „Erkennen“ oder „Aufteilen“).</p></div>`}</div>`;
  hydrateIcons(main);
  if (!local.length) return;
  $$("#spCurve button").forEach(b => b.onclick = () => {
    SetPlan.curve = b.dataset.c; $$("#spCurve button").forEach(x => x.classList.toggle("on", x === b));
    $("#spHint").textContent = curves.find(c => c.id === SetPlan.curve).hint;
    if (SetPlan.items && SetPlan.playlist === $("#spPl").value) spOrder();
  });
  $("#spGo").onclick = async () => {
    try { SetPlan.playlist = $("#spPl").value; SetPlan.job = (await api("/api/setplan/start", { method: "POST", body: { playlist: SetPlan.playlist } })).job; SetPlan.items = null; spPoll(); }
    catch (e) { toast(e.message, "err"); }
  };
  if (SetPlan.items && SetPlan.desc && SetPlan.playlist === $("#spPl").value) spRender();
};
async function spPoll() {
  const jid = SetPlan.job, box = $("#spJob"); $("#spOut").innerHTML = "";
  while (SetPlan.job === jid && document.body.contains(box)) {
    let j; try { j = await api(`/api/setplan/${jid}`); } catch (e) { return toast(e.message, "err"); }
    if (j.state === "done") { box.innerHTML = j.cut ? `<div class="notice">${icon("info")}<div>Nur die ersten ${j.total} Songs – ${j.cut} weitere passen nicht in ein Set.</div></div>` : ""; hydrateIcons(box); SetPlan.items = j.items; return spOrder(); }
    if (j.state !== "analysing") { box.innerHTML = `<div class="notice">${icon("info")}<div>${j.state === "error" ? esc(j.error) : "Abgebrochen."}</div></div>`; return hydrateIcons(box); }
    box.innerHTML = `<div class="card t-job"><div class="t-job-head"><b>Messe Tempo, Tonart und Energie …</b><span class="cell-sub">${j.done}/${j.total}</span>
      <button class="btn btn--xs btn--ghost" id="spCancel">Abbrechen</button></div><div class="llm-bar"><div style="width:${Math.round(j.done / (j.total || 1) * 100)}%"></div></div>
      <div class="cell-sub" style="margin-top:6px">Aus der offiziellen 30-s-Hörprobe – bekannte Songs kommen sofort aus dem Speicher.</div></div>`;
    $("#spCancel").onclick = () => api(`/api/setplan/${jid}/cancel`, { method: "POST" });
    await new Promise(r => setTimeout(r, 1000));
  }
}
async function spOrder() {
  try { SetPlan.desc = await api(`/api/setplan/${SetPlan.job}/order`, { method: "POST", body: { curve: SetPlan.curve } }); SetPlan.order = SetPlan.desc.order; spRender(); }
  catch (e) { toast(e.message, "err"); }
}
async function spMove(k, dir) {
  const o = [...SetPlan.order], m = k + dir; if (m < 0 || m >= o.length) return;
  [o[k], o[m]] = [o[m], o[k]];
  SetPlan.desc = await api(`/api/setplan/${SetPlan.job}/describe?curve=${SetPlan.curve}`, { method: "POST", body: { order: o } });
  SetPlan.order = SetPlan.desc.order; spRender();
}
function spChart(d) {
  const st = d.steps, hasT = st.some(s => s.target != null), n = st.length;
  const line = hasT ? st.map((s, k) => `${n === 1 ? 50 : (k + .5) / n * 100},${100 - s.target * 100}`).join(" ") : "";
  return `<div class="sp-chart-wrap"><div class="sp-legend"><span><i class="sw sw-bar"></i>Energie je Song</span>${hasT ? `<span><i class="sw sw-line"></i>gewünschter Verlauf</span>` : ""}</div>
    <div class="sp-chart" id="spChart" role="img" aria-label="Energie je Song in Set-Reihenfolge">
      <div class="sp-grid"><i style="bottom:25%"></i><i style="bottom:50%"></i><i style="bottom:75%"></i></div>
      <div class="sp-bars">${st.map((s, k) => `<b data-k="${k}" style="height:${Math.max(3, s.energy * 100)}%"></b>`).join("")}</div>
      ${hasT ? `<svg class="sp-line" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points="${line}" fill="none" vector-effect="non-scaling-stroke"/></svg>` : ""}
      <div class="sp-tip hidden" id="spTip"></div></div>
    <div class="sp-axis"><span>Anfang</span><span>${d.minuten ? `~${d.minuten} Min.` : ""}</span><span>Ende</span></div></div>`;
}
function spRender() {
  const d = SetPlan.desc, it = SetPlan.items, out = $("#spOut"); if (!out || !d) return;
  const chip = s => s.key_d == null ? "" : `<span class="sp-tr ${s.key_d <= 1 ? "ok" : s.key_d === 2 ? "mid" : "bad"}">${esc(s.key)}${s.tempo != null ? ` · ${s.tempo < 0.5 ? "gleiches Tempo" : `${String(s.tempo).replace(".", ",")} % Tempo`}` : ""}</span>`;
  out.innerHTML = `<div class="sp-stats cell-sub">${d.order.length} Songs${d.minuten ? ` · ~${d.minuten} Min.` : ""} · ${d.bekannt ? `${d.harmonisch} von ${d.bekannt} Übergängen harmonisch` : "Tonarten unbekannt"} · mit ▲▼ von Hand umstellen</div>
    ${spChart(d)}
    <div class="sp-actions">
      <button class="btn btn--sm btn--primary" id="spSave">${icon("plus")}Als Playlist speichern</button>
      <button class="btn btn--sm btn--ghost" data-exp="m3u8">${icon("download")}M3U8</button>
      <button class="btn btn--sm btn--ghost" data-exp="csv">${icon("download")}CSV (BPM, Tonart)</button>
      <button class="btn btn--sm btn--ghost" id="spCopy">${icon("copy")}Tracklist kopieren</button>
      <button class="btn btn--sm btn--ghost" id="spPlay">${icon("play")}Alles anhören</button></div>
    <div class="card sp-list">${d.steps.map((s, k) => { const t = it[s.i]; const pv = withPreview({ ...t });
      return `${k ? `<div class="sp-step">${chip(s)}</div>` : ""}<div class="sp-row" data-k="${k}"><span class="sp-n num">${k + 1}</span>
        <button class="icon-btn" ${playAttr(pv)} title="Reinhören">${icon("play")}</button>
        ${t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : `<span class="ph"></span>`}
        <div class="sl"><span>${esc(t.artist)} – ${esc(t.title)}</span><em>${esc(t.subgenre || t.genre || "")}</em></div>
        <span class="sp-v num">${t.bpm ? Math.round(t.bpm) + " BPM" : "– BPM"}</span><span class="sp-v sp-cam">${esc(t.camelot || "–")}</span>
        <span class="sp-v num" title="Energie">${Math.round(s.energy * 100)} %</span>
        <span class="sp-mv"><button class="icon-btn" data-up="${k}" ${k ? "" : "disabled"} title="Nach oben">▲</button><button class="icon-btn" data-dn="${k}" ${k < d.steps.length - 1 ? "" : "disabled"} title="Nach unten">▼</button></span></div>`; }).join("")}</div>`;
  hydrateIcons(out); Player.sync();
  $$("[data-up]", out).forEach(b => b.onclick = () => spMove(+b.dataset.up, -1));
  $$("[data-dn]", out).forEach(b => b.onclick = () => spMove(+b.dataset.dn, 1));
  const tip = $("#spTip");
  $$(".sp-bars b", out).forEach(b => {
    b.onmouseenter = () => { const k = +b.dataset.k, s = d.steps[k], t = it[s.i];
      tip.innerHTML = `<b>${k + 1}. ${esc(t.artist)} – ${esc(t.title)}</b><span>Energie ${Math.round(s.energy * 100)} %${s.target != null ? ` · Ziel ${Math.round(s.target * 100)} %` : ""}${t.bpm ? ` · ${Math.round(t.bpm)} BPM` : ""}${t.camelot ? ` · ${esc(t.camelot)}` : ""}</span>`;
      tip.classList.remove("hidden"); const r = b.getBoundingClientRect(), c = $("#spChart").getBoundingClientRect();
      tip.style.left = `${Math.min(c.width - tip.offsetWidth, Math.max(0, r.left - c.left + r.width / 2 - tip.offsetWidth / 2))}px`;
      $$(".sp-row", out).forEach(x => x.classList.toggle("hl", +x.dataset.k === k)); };
    b.onmouseleave = () => { tip.classList.add("hidden"); $$(".sp-row.hl", out).forEach(x => x.classList.remove("hl")); };
    b.onclick = () => $(`.sp-row[data-k="${b.dataset.k}"]`, out)?.scrollIntoView({ block: "center", behavior: "smooth" });
  });
  const order = () => ({ order: SetPlan.order });
  $$("[data-exp]", out).forEach(b => b.onclick = async () => {
    try { const r = await api(`/api/setplan/${SetPlan.job}/export`, { method: "POST", body: { ...order(), fmt: b.dataset.exp } });
      toast(`Gespeichert: ${r.name}`); modal({ title: "Exportiert", text: `${esc(r.name)} liegt in ${esc(r.folder)}.<br>Enthält Titel, Künstler, Tempo, Tonart und Links – keine Musikdateien.`, confirm: "Ordner öffnen", cancel: "Schließen",
        onConfirm: () => api("/api/debug/open-folder", { method: "POST", body: { folder: r.folder } }) }); }
    catch (e) { toast(e.message, "err"); }
  });
  $("#spCopy").onclick = async () => { const r = await api(`/api/setplan/${SetPlan.job}/export`, { method: "POST", body: { ...order(), fmt: "txt", name: "clipboard" } });
    toast(await Clip.write(r.text) ? "Tracklist kopiert" : "Kopieren nicht möglich", "ok"); };
  $("#spPlay").onclick = () => { Player.playList(SetPlan.order.map(i => withPreview({ ...it[i] }))); toast("Alle Hörproben in Set-Reihenfolge – unten im Player weiter/stoppen"); };
  $("#spSave").onclick = () => modal({ title: "Als Playlist speichern", body: `<input class="input" id="spName" value="${esc(SetPlan.playlist)} – Set" style="width:100%">`, confirm: "Speichern",
    onConfirm: async box => { const r = await api(`/api/setplan/${SetPlan.job}/save`, { method: "POST", body: { ...order(), name: $("#spName", box).value } });
      toast(`„${r.name}“ mit ${r.count} Songs angelegt`); refreshMeta(); } });
}

/* ---------- Mix erstellen: aus Künstlern oder einem Genre eine neue Playlist – „Wie passend?“ von locker bis DJ-genau */
const MIX_DEFAULTS = { level: "passend", count: 30, per_artist: 2, popularity: "mix", versions: true, include_seeds: true,
  skip_library: false, bpm_min: "", bpm_max: "", camelot: "", energy_min: "", energy_max: "", curve: "gleich" };
const Mix = { seeds: store.get("mixSeeds", []), opts: { ...MIX_DEFAULTS, ...store.get("mixOpts", {}) }, job: null, data: null, order: [], reserve: [],
  mode: store.get("mixMode", "artists"), genre: store.get("mixGenreSel", null), gOpen: null };
const CAMELOT_ALL = Array.from({ length: 12 }, (_, i) => [`${i + 1}A`, `${i + 1}B`]).flat();
// Stufen: Anzeige (Stärke 1–4, Kurzinfo, Dauer) – die Regeln selbst stehen in mixgen.LEVELS
const MIX_LEVEL_UI = {
  locker: { n: 1, what: "Nur Ähnlichkeit", time: "in Sekunden" },
  passend: { n: 2, what: "±15 % Tempo · ähnliche Energie", time: "~30 Sekunden" },
  mixbar: { n: 3, what: "±6 % Tempo · harmonisch gereiht", time: "~1 Minute" },
  genau: { n: 4, what: "±3 % Tempo · Energie-Verlauf", time: "~1 Minute" },
};
const genreLabel = (g, sub) => sub ? `${g} › ${sub}` : g;
const mixGenreOk = g => g && TAXONOMY?.[g.genre] && (!g.sub || TAXONOMY[g.genre].includes(g.sub));

Views.mix = async (main) => {
  const meta = await api("/api/mix/levels");
  Mix.max = meta.max_seeds || 15;
  if (!mixGenreOk(Mix.genre)) Mix.genre = null;
  Mix.gOpen = Mix.genre?.genre || Mix.gOpen;
  const o = Mix.opts;
  const seg = (id, items, cur) => `<div class="segmented" id="${id}">${items.map(([v, l]) => `<button type="button" data-v="${v}" class="${String(v) === String(cur) ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
  const step = (n, title, extra = "") => `<div class="mx-step"><span class="mx-num">${n}</span><h2>${title}</h2>${extra}</div>`;
  main.innerHTML = `<div class="page view-enter mx-page">
    <div class="page-head"><div><h1>Mix erstellen</h1><p>Neue Playlist aus Künstlern oder einem Genre – du bestimmst, wie genau Tempo, Tonart und Energie zusammenpassen, und hörst sofort rein.</p></div></div>
    <div class="card mx-form">
      <section class="mx-sec">${step(1, "Womit starten?")}
        <div class="mx-modes" role="radiogroup">
          <button type="button" class="mx-mode" data-mode="artists" role="radio">${icon("mic")}<b>Künstler</b><span>Ähnliche Songs zu bis zu ${meta.max_seeds} Künstlern</span></button>
          <button type="button" class="mx-mode" data-mode="genre" role="radio">${icon("tag")}<b>Genre</b><span>Ein Genre oder Subgenre – z. B. Liquid, Riddim, Deep House</span></button>
        </div>
        <div class="mx-pick" id="mxArtistF">
          <div class="mix-search"><div class="input-icon">${icon("search")}<input class="input" id="mxQ" placeholder="Künstler suchen – z. B. Netsky, Calibre, Hybrid Minds" autocomplete="off"></div>
            <div class="mix-sugg hidden" id="mxSugg" role="listbox"></div></div>
          <div class="mix-seeds" id="mxSeeds"></div>
        </div>
        <div class="mx-pick" id="mxGenreF">
          <div class="mix-search"><div class="input-icon">${icon("search")}<input class="input" id="mxGQ" placeholder="Genre suchen – z. B. liquid, riddim, deep" autocomplete="off"></div></div>
          <div id="mxGenres"></div>
          <div class="cell-sub mx-fine">Künstler kommen aus deiner Bibliothek, deinen Einordnungen, der Gemeinschafts-Genre-Datenbank (falls geladen), MusicBrainz und – mit eigenem Key – Last.fm. Gesendet wird nur der Genre-Name.</div>
        </div>
      </section>
      <section class="mx-sec">${step(2, "Wie passend?")}
        <div class="mx-levels" role="radiogroup">${meta.levels.map(l => { const u = MIX_LEVEL_UI[l.id] || { n: 1, what: "", time: "" };
          return `<button type="button" class="mx-level" data-v="${l.id}" role="radio" title="${esc(l.hint)}">
            <span class="mx-meter" aria-hidden="true">${[1, 2, 3, 4].map(k => `<i class="${k <= u.n ? "on" : ""}"></i>`).join("")}</span>
            <b>${esc(l.name)}</b><span>${esc(u.what)}</span><em>${esc(u.time)}</em></button>`; }).join("")}</div>
        <div class="cell-sub mx-fine" id="mxHint"></div>
      </section>
      <section class="mx-sec">${step(3, "Umfang", `<span class="mx-count"><b class="num" id="mxCountV">${esc(o.count)}</b> Songs</span>`)}
        <input type="range" class="mx-range" id="mxCount" min="5" max="${meta.count_max}" step="5" value="${esc(o.count)}" aria-label="Anzahl Songs">
        <div class="mx-row3">
          <div class="field"><label>Pro Künstler höchstens</label>${seg("mxPer", [[1, "1"], [2, "2"], [3, "3"], [5, "5"], [10, "10"]], o.per_artist)}</div>
          <div class="field"><label>Bekanntheit</label>${seg("mxPop", [["hits", "Eher Hits"], ["mix", "Gemischt"], ["unbekannt", "Eher unbekannt"]], o.popularity)}</div>
        </div>
        <details class="mx-more" ${o.bpm_min || o.bpm_max || o.camelot || o.energy_min !== "" || o.energy_max !== "" ? "open" : ""}><summary>${icon("sliders")}Feineinstellungen<span class="cell-sub" id="mxMoreSum"></span>${icon("chevron")}</summary>
          <div class="mx-grid">
            <div class="field"><label>Tempo (BPM)</label><div class="mix-range"><input class="input num" type="number" id="mxBpmMin" placeholder="von" min="40" max="250" value="${esc(o.bpm_min)}"><span>–</span><input class="input num" type="number" id="mxBpmMax" placeholder="bis" min="40" max="250" value="${esc(o.bpm_max)}"></div></div>
            <div class="field"><label>Tonart (Camelot)</label><select class="select" id="mxCam"><option value="">egal</option>${CAMELOT_ALL.map(c => `<option ${o.camelot === c ? "selected" : ""}>${c}</option>`).join("")}</select></div>
            <div class="field"><label>Energie (%)</label><div class="mix-range"><input class="input num" type="number" id="mxEMin" placeholder="von" min="0" max="100" value="${o.energy_min === "" ? "" : Math.round(o.energy_min * 100)}"><span>–</span><input class="input num" type="number" id="mxEMax" placeholder="bis" min="0" max="100" value="${o.energy_max === "" ? "" : Math.round(o.energy_max * 100)}"></div></div>
            <div class="field" id="mxCurveF"><label>Energie-Verlauf</label><select class="select" id="mxCurve">${[["gleich", "Gleichmäßig"], ["aufbau", "Aufbauen"], ["peak", "Peak in der Mitte"], ["runter", "Runterfahren"]].map(([v, l]) => `<option value="${v}" ${o.curve === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          </div>
          <div class="mix-switches">
            <label class="switch"><input type="checkbox" id="mxVer" ${o.versions ? "checked" : ""}><span class="track"></span>Remixe, VIPs und andere Fassungen</label>
            <label class="switch" id="mxSeedsInF"><input type="checkbox" id="mxSeedsIn" ${o.include_seeds ? "checked" : ""}><span class="track"></span>Songs der gewählten Künstler selbst</label>
            <label class="switch"><input type="checkbox" id="mxSkip" ${o.skip_library ? "checked" : ""}><span class="track"></span>Songs aus meinen Playlists weglassen</label>
          </div>
          <div class="cell-sub mx-fine">Eigene Angaben gelten immer streng. Tempo zählt auch halb/doppelt (87 ↔ 174 BPM). Gemessen wird aus der offiziellen 30-s-Hörprobe – nur so viele Songs wie nötig, Bekanntes kommt aus dem Speicher.</div>
        </details>
      </section>
      <div class="mx-foot"><div class="mx-sum"><b id="mxSum"></b><span class="cell-sub" id="mxSrc"></span></div>
        <button class="btn btn--primary mx-go" id="mxGo">${icon("shuffle")}Mix erstellen</button></div>
    </div>
    <div id="mxJob"></div><div id="mxOut"></div></div>`;
  hydrateIcons(main);

  const readOpts = () => {
    const num = (id, scale = 1) => { const v = $(id).value.trim(); return v === "" ? "" : +v / scale; };
    Object.assign(Mix.opts, { count: +$("#mxCount").value, bpm_min: num("#mxBpmMin"), bpm_max: num("#mxBpmMax"), camelot: $("#mxCam").value,
      energy_min: num("#mxEMin", 100), energy_max: num("#mxEMax", 100), curve: $("#mxCurve").value,
      versions: $("#mxVer").checked, include_seeds: $("#mxSeedsIn").checked, skip_library: $("#mxSkip").checked });
    store.set("mixOpts", Mix.opts);
  };
  const refresh = () => {
    const lv = meta.levels.find(x => x.id === Mix.opts.level), genre = Mix.mode === "genre";
    $$(".mx-mode").forEach(b => { const on = b.dataset.mode === Mix.mode; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
    $$(".mx-level").forEach(b => { const on = b.dataset.v === Mix.opts.level; b.classList.toggle("on", on); b.setAttribute("aria-checked", on); });
    $("#mxArtistF").classList.toggle("hidden", genre); $("#mxGenreF").classList.toggle("hidden", !genre);
    $("#mxSeedsInF").classList.toggle("hidden", genre);
    $("#mxHint").textContent = lv?.hint || "";
    $("#mxCurveF").classList.toggle("hidden", !["mixbar", "genau"].includes(Mix.opts.level));
    $("#mxCountV").textContent = Mix.opts.count;
    const r = $("#mxCount"); r.style.setProperty("--p", `${(Mix.opts.count - r.min) / (r.max - r.min) * 100}%`);
    const o2 = Mix.opts, fine = [o2.bpm_min || o2.bpm_max ? `${o2.bpm_min || "…"}–${o2.bpm_max || "…"} BPM` : "", o2.camelot ? `Tonart ${o2.camelot}` : "",
      o2.energy_min !== "" || o2.energy_max !== "" ? "Energie" : "", !o2.versions ? "ohne Remixe" : "", o2.skip_library ? "ohne Bibliothek" : ""].filter(Boolean);
    $("#mxMoreSum").textContent = fine.length ? fine.join(" · ") : "";
    const start = genre ? (Mix.genre ? genreLabel(Mix.genre.genre, Mix.genre.sub) : "Genre wählen")
      : (Mix.seeds.length ? Mix.seeds.map(s => s.name).join(", ") : "Künstler wählen");
    $("#mxSum").textContent = `${start} · ${lv?.name || ""} · ${Mix.opts.count} Songs`;
    $("#mxSrc").textContent = (genre ? "Quellen: MusicBrainz, Last.fm (mit Key), Deezer – ohne Login." : "Quelle: Deezer – öffentlich, ohne Login.")
      + " Gespeichert wird erst, wenn du die Playlist speicherst.";
    $("#mxGo").disabled = genre ? !Mix.genre : !Mix.seeds.length;
  };
  Mix.refresh = refresh;
  $$(".mx-mode").forEach(b => b.onclick = () => { Mix.mode = b.dataset.mode; store.set("mixMode", Mix.mode); refresh(); (Mix.mode === "genre" ? $("#mxGQ") : $("#mxQ")).focus(); });
  $$(".mx-level").forEach(b => b.onclick = () => { Mix.opts.level = b.dataset.v; store.set("mixOpts", Mix.opts); refresh(); });
  const bindSeg = (id, key, cast = String) => $$(`#${id} button`).forEach(b => b.onclick = () => {
    Mix.opts[key] = cast(b.dataset.v); $$(`#${id} button`).forEach(x => x.classList.toggle("on", x === b)); store.set("mixOpts", Mix.opts); });
  bindSeg("mxPer", "per_artist", Number); bindSeg("mxPop", "popularity");
  $("#mxCount").oninput = () => { Mix.opts.count = +$("#mxCount").value; refresh(); };
  $$(".mx-form .mx-more input, .mx-form .mx-more select, #mxCount").forEach(el => el.addEventListener("change", () => { readOpts(); refresh(); }));

  // Künstlersuche (Deezer) – kurz warten, bis fertig getippt ist
  let tmr = 0, seq = 0;
  const q = $("#mxQ"), sugg = $("#mxSugg");
  q.oninput = () => { clearTimeout(tmr); const v = q.value.trim(); if (v.length < 2) return sugg.classList.add("hidden");
    tmr = setTimeout(async () => { const my = ++seq; let r = [];
      try { r = await api(`/api/mix/artists?q=${enc(v)}`); } catch (e) { if (my === seq) { sugg.innerHTML = `<div class="cell-sub" style="padding:8px">${esc(e.message)}</div>`; sugg.classList.remove("hidden"); } return; }
      if (my !== seq) return;
      sugg.innerHTML = r.length ? r.map((a, i) => `<button type="button" class="mix-sg" data-i="${i}" role="option">${a.picture ? `<img src="${esc(a.picture)}" alt="" loading="lazy">` : `<span class="ph"></span>`}
        <span>${esc(a.name)}</span><em class="num">${a.fans ? `${a.fans.toLocaleString("de-DE")} Fans` : ""}</em></button>`).join("") : `<div class="cell-sub" style="padding:8px">Kein Künstler gefunden.</div>`;
      sugg.classList.remove("hidden");
      $$(".mix-sg", sugg).forEach(b => b.onclick = () => { mixAddSeed(r[+b.dataset.i]); q.value = ""; sugg.classList.add("hidden"); q.focus(); });
    }, 300); };
  q.onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); $(".mix-sg", sugg)?.click(); } if (e.key === "Escape") sugg.classList.add("hidden"); };
  q.onblur = () => setTimeout(() => sugg.classList.add("hidden"), 200);
  $("#mxGQ").oninput = () => mixGenresDraw();
  $("#mxGQ").onkeydown = e => { if (e.key === "Enter") { e.preventDefault(); $("#mxGenres .mx-g")?.click(); } if (e.key === "Escape") { e.target.value = ""; mixGenresDraw(); } };

  $("#mxGo").onclick = async () => {
    readOpts();
    const opts = Object.fromEntries(Object.entries(Mix.opts).map(([k, v]) => [k, v === "" ? null : v]));
    const body = Mix.mode === "genre" ? { genre: Mix.genre, opts } : { seeds: Mix.seeds.map(s => ({ id: s.id, name: s.name })), opts };
    if (Mix.mode === "genre" ? !Mix.genre : !Mix.seeds.length) return toast(Mix.mode === "genre" ? "Bitte ein Genre wählen" : "Bitte zuerst einen Künstler auswählen", "err");
    try { Mix.job = (await api("/api/mix/start", { method: "POST", body })).job; Mix.data = null; mixPoll(); $("#mxJob").scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    catch (e) { toast(e.message, "err"); }
  };
  mixSeedsDraw(); mixGenresDraw(); refresh();
  if (Mix.data) mixRender();
};

/* Genre-Auswahl: Hauptgenres als Kacheln, darunter die Subgenres des gewählten; Suche filtert über alles (max. 12) */
function mixGenresDraw() {
  const box = $("#mxGenres"); if (!box) return;
  const tax = TAXONOMY || {}, term = ($("#mxGQ")?.value || "").trim().toLowerCase(), sel = Mix.genre;
  const chip = (g, sub, label = genreLabel(g, sub), extra = "") => { const on = sel && sel.genre === g && (sel.sub || null) === (sub || null);
    return `<button type="button" class="mx-g ${on ? "on" : ""} ${extra}" data-g="${esc(g)}" data-s="${esc(sub || "")}" style="--g:${genreColor(g, sub)}"><i class="dot"></i>${esc(label)}</button>`; };
  if (term) {
    const hits = Object.entries(tax).flatMap(([g, subs]) => [[g, null], ...subs.map(s => [g, s])])
      .filter(([g, s]) => genreLabel(g, s).toLowerCase().includes(term)).slice(0, 12);
    box.innerHTML = hits.length ? `<div class="mx-gchips">${hits.map(([g, s]) => chip(g, s)).join("")}</div>` : `<div class="cell-sub mx-fine">Kein Genre gefunden – im Genre-Baum gibt es „${esc(term)}“ nicht.</div>`;
  } else {
    const open = Mix.gOpen && tax[Mix.gOpen] ? Mix.gOpen : null;
    box.innerHTML = `<div class="mx-gchips mx-gmain">${Object.keys(tax).map(g => `<button type="button" class="mx-g mx-gm ${open === g ? "open" : ""} ${sel?.genre === g ? "on" : ""}" data-open="${esc(g)}" style="--g:${genreColor(g)}"><i class="dot"></i>${esc(g)}</button>`).join("")}</div>
      ${open ? `<div class="mx-subs"><div class="mx-subs-head">Subgenre von <b>${esc(open)}</b> – oder das ganze Genre</div>
        <div class="mx-gchips">${chip(open, null, `Alle: ${open}`, "mx-gall")}${tax[open].map(s => chip(open, s, s)).join("")}</div></div>` : `<div class="cell-sub mx-fine">Wähle ein Hauptgenre – danach kannst du ein Subgenre aussuchen.</div>`}`;
  }
  $$("[data-open]", box).forEach(b => b.onclick = () => { Mix.gOpen = Mix.gOpen === b.dataset.open && !Mix.genre ? null : b.dataset.open; mixGenresDraw(); });
  $$(".mx-g[data-g]", box).forEach(b => b.onclick = () => {
    Mix.genre = { genre: b.dataset.g, sub: b.dataset.s || null }; Mix.gOpen = b.dataset.g; store.set("mixGenreSel", Mix.genre);
    const gq = $("#mxGQ"); if (gq) gq.value = "";
    mixGenresDraw(); Mix.refresh?.();
  });
}
function mixAddSeed(a) {
  if (!a || Mix.seeds.some(s => s.id === a.id)) return;
  const max = Mix.max || 15;
  if (Mix.seeds.length >= max) return toast(`Höchstens ${max} Künstler – entferne erst einen`, "err");
  Mix.seeds.push({ id: a.id, name: a.name, picture: a.picture }); store.set("mixSeeds", Mix.seeds); mixSeedsDraw(); Mix.refresh?.();
}
function mixSeedsDraw() {
  const box = $("#mxSeeds"); if (!box) return;
  box.innerHTML = Mix.seeds.length ? Mix.seeds.map((s, i) => `<span class="mix-seed">${s.picture ? `<img src="${esc(s.picture)}" alt="">` : `<span class="ph"></span>`}${esc(s.name)}
    <button type="button" class="icon-btn" data-rm="${i}" aria-label="${esc(s.name)} entfernen">${icon("x")}</button></span>`).join("") : `<span class="cell-sub mx-fine">Noch kein Künstler gewählt – oben suchen und aus der Liste wählen.</span>`;
  hydrateIcons(box);
  $$("[data-rm]", box).forEach(b => b.onclick = () => { Mix.seeds.splice(+b.dataset.rm, 1); store.set("mixSeeds", Mix.seeds); mixSeedsDraw(); Mix.refresh?.(); });
}
async function mixPoll() {
  const jid = Mix.job, box = $("#mxJob"); $("#mxOut").innerHTML = "";
  while (Mix.job === jid && document.body.contains(box)) {
    let j; try { j = await api(`/api/mix/${jid}`); } catch (e) { box.innerHTML = ""; return toast(e.message, "err"); }
    if (j.state === "done") { box.innerHTML = ""; Mix.data = j; Mix.order = [...j.order]; Mix.reserve = [...j.reserve]; return mixRender(); }
    if (j.state !== "running") { box.innerHTML = `<div class="notice">${icon("info")}<div>${j.state === "error" ? esc(j.error) : "Abgebrochen."}</div></div>`; return hydrateIcons(box); }
    const measuring = j.phase === "measuring";
    const what = measuring ? "Messe Tempo, Tonart und Energie …" : j.genre ? `Suche Künstler für ${esc(genreLabel(j.genre.genre, j.genre.sub))} …` : "Suche ähnliche Künstler und Songs …";
    box.innerHTML = `<div class="card mx-job"><div class="mx-job-head"><span class="mx-spin" aria-hidden="true"></span><b>${what}</b><span class="cell-sub num">${j.done}/${j.total}</span>
      <button class="btn btn--xs btn--ghost" id="mxCancel">Abbrechen</button></div><div class="llm-bar"><div style="width:${Math.round(j.done / (j.total || 1) * 100)}%"></div></div>
      <div class="cell-sub">${measuring ? "Aus der offiziellen 30-s-Hörprobe – nur so viele wie nötig, Bekanntes kommt sofort aus dem Speicher." : j.genre ? "Bibliothek, Gemeinschafts-DB, MusicBrainz (und Last.fm) – danach Top-Songs bei Deezer." : "Deezer: Top-Songs, Künstler-Radio und ähnliche Künstler."}</div></div>`;
    $("#mxCancel").onclick = () => api(`/api/mix/${jid}/cancel`, { method: "POST" });
    await new Promise(r => setTimeout(r, 900));
  }
}
async function mixRender() {
  const d = Mix.data, out = $("#mxOut"); if (!out || !d) return;
  const it = d.items, ref = d.ref || {};
  const title = d.genre ? genreLabel(d.genre.genre, d.genre.sub) : d.seeds.map(s => s.name).slice(0, 3).join(", ");
  if (!Mix.order.length) { out.innerHTML = `<div class="card mx-res"><div class="empty">${icon("info")}<h3>Kein passender Song</h3><p>${esc(d.note || "Mit diesen Einstellungen passt nichts – probiere „Locker“ oder „Passend“.")}</p></div></div>`; return hydrateIcons(out); }
  let st = null; try { st = await api(`/api/mix/${Mix.job}/describe`, { method: "POST", body: { order: Mix.order } }); } catch { /* ohne Statistik */ }
  const lv = { locker: "Locker", passend: "Passend", mixbar: "Mixbar", genau: "DJ-genau" }[d.opts.level] || "";
  const ordered = ["mixbar", "genau"].includes(d.opts.level);
  const tile = (v, l) => `<div class="mx-stat"><b class="num">${v}</b><span>${l}</span></div>`;
  const pct = n => Math.max(0, Math.min(100, Math.round(n * 100)));
  out.innerHTML = `<div class="card mx-res">
    <div class="mx-res-head"><div><div class="mx-kicker">${icon("shuffle")}Dein Mix · ${esc(lv)}${ordered ? " · DJ-Reihenfolge" : ""}</div><h2>${esc(title)}</h2></div>
      <div class="mx-res-act"><button class="btn btn--primary" id="mxPlay">${icon("play")}Alles anhören</button>
        <button class="btn" id="mxSave">${icon("plus")}Als Playlist speichern</button>
        <button class="btn btn--ghost" id="mxAgain" title="Mit denselben Einstellungen neu erstellen">${icon("repeat")}Neu</button></div></div>
    <div class="mx-stats">${tile(Mix.order.length, "Songs")}${st?.minuten ? tile(`~${st.minuten}`, "Minuten") : ""}
      ${st?.bekannt ? tile(`${st.harmonisch}/${st.bekannt}`, "harmonische Übergänge") : ""}${ref.bpm ? tile(Math.round(ref.bpm), "Ziel-BPM") : ""}
      ${ref.camelot ? tile(esc(ref.camelot), "Tonart") : ""}${tile(d.found, "Kandidaten geprüft")}</div>
    ${d.note ? `<div class="notice mx-note">${icon("info")}<div>${esc(d.note)}</div></div>` : ""}
    <div class="mx-list">${Mix.order.map((i, k) => { const t = it[i], pv = withPreview({ ...t }), r = (t.reasons || [])[0] || "";
      return `<div class="mx-item" data-k="${k}"><span class="mx-n num">${k + 1}</span>
        <button class="mx-cover" ${playAttr(pv)} aria-label="Reinhören: ${esc(t.title)}">${t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : `<span class="ph"></span>`}<span class="mx-play">${icon("play")}</span></button>
        <div class="mx-main"><b>${esc(t.title)}</b><span>${esc(t.artist)}</span><em title="${esc((t.reasons || []).join(" · "))}">${esc(r)}</em></div>
        <div class="mx-feat"><span class="mx-chip num">${t.bpm ? Math.round(t.bpm) : "–"}<small>BPM</small></span><span class="mx-chip">${esc(t.camelot || "–")}</span>
          <span class="mx-energy" title="Energie ${t.energy != null ? pct(t.energy) + " %" : "unbekannt"}"><i style="width:${t.energy != null ? pct(t.energy) : 0}%"></i></span></div>
        <div class="mx-act"><button class="icon-btn" data-sw="${k}" title="Durch einen anderen passenden Song ersetzen" ${Mix.reserve.length ? "" : "disabled"}>${icon("repeat")}</button>
          <button class="icon-btn" data-del="${k}" title="Aus dem Mix entfernen">${icon("x")}</button></div></div>`; }).join("")}</div>
    <div class="mx-res-foot cell-sub">${Mix.reserve.length ? `${Mix.reserve.length} weitere passende Songs in Reserve – ${icon("repeat")} tauscht einen aus.` : "Keine weiteren Songs in Reserve."} Energie = Lautheit und Dichte der Hörprobe.</div></div>`;
  hydrateIcons(out); Player.sync();
  $$("[data-del]", out).forEach(b => b.onclick = () => { Mix.order.splice(+b.dataset.del, 1); mixRender(); });
  $$("[data-sw]", out).forEach(b => b.onclick = () => { const k = +b.dataset.sw, nxt = Mix.reserve.shift(); if (nxt == null) return; Mix.order[k] = nxt; mixRender(); });
  $("#mxPlay").onclick = () => { Player.playList(Mix.order.map(i => withPreview({ ...it[i] }))); toast("Alle Hörproben nacheinander – unten im Player weiter/stoppen"); };
  $("#mxAgain").onclick = () => $("#mxGo")?.click();
  $("#mxSave").onclick = () => modal({ title: "Als Playlist speichern", body: `<input class="input" id="mxName" value="${esc(`Mix – ${title}`)}" style="width:100%">`, confirm: "Speichern",
    onConfirm: async box => { const r = await api(`/api/mix/${Mix.job}/save`, { method: "POST", body: { order: Mix.order, name: $("#mxName", box).value } });
      toast(`„${r.name}“ mit ${r.count} Songs angelegt`); refreshMeta();
      setTimeout(() => modal({ title: "Gespeichert", text: `„${esc(r.name)}“ liegt jetzt in deinen Playlists. Im Set-Planer kannst du die Reihenfolge noch feinschleifen und als M3U8/CSV exportieren.`,
        confirm: "Im Set-Planer öffnen", cancel: "Schließen", onConfirm: () => { location.hash = `#/setplan?pl=${enc(r.name)}`; } }), 50); } });
}

/* ---------- Doppelte Songs (nur lokale Playlists) */
Views.dupes = async (main) => {
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Doppelte Songs</h1><p>Findet Songs, die in deinen Playlists mehrfach stehen – und Remixe/Originale desselben Songs. Läuft nur auf deinem Rechner.</p></div></div>
    <div id="dpOut"><div class="empty">${icon("search")}<h3>Suche …</h3></div></div></div>`;
  hydrateIcons(main);
  const d = await api("/api/dupes");
  const z = d.zahlen;
  const row = (o, act = "") => { const t = withPreview({ ...o });
    return `<div class="dp-row"><button class="icon-btn" ${playAttr(t)} title="Reinhören">${icon("play")}</button>
      ${o.cover ? `<img src="${esc(o.cover)}" alt="" loading="lazy">` : `<span class="ph"></span>`}
      <div class="sl"><span>${esc((o.artists || []).join(", "))} – ${esc(o.title)}</span><em>${esc(o.playlist)}${o.genre ? " · " + esc(o.subgenre || o.genre) : ""} · ${relTime(o.ts)}</em></div>${act}</div>`; };
  const rm = (o, label = "Entfernen") => `<button class="btn btn--xs btn--ghost" data-rm='${esc(JSON.stringify({ playlist: o.playlist, key: o.key }))}'>${icon("x")}${label}</button>`;
  // Große Bibliotheken: Gruppen portionsweise zeigen (sonst hunderttausende Elemente auf einmal)
  const STEP = 150;
  const html = {
    doppelt: g => `<div class="dp-group">${row(g.keep, `<span class="chip">bleibt</span>`)}${g.remove.map(o => row(o, rm(o))).join("")}</div>`,
    mehrfach: g => `<div class="dp-group">${g.in.map(o => row(o, rm(o, "Hier entfernen"))).join("")}</div>`,
    versionen: g => `<div class="dp-group">${g.songs.map(o => row(o, rm(o))).join("")}</div>`,
  };
  const shown = { doppelt: 0, mehrfach: 0, versionen: 0 };
  const bindRows = host => $$("[data-rm]", host).forEach(b => { if (!b.onclick) b.onclick = () => remove([JSON.parse(b.dataset.rm)]); });
  const fill = id => {   // nächste Portion anhängen
    const host = $(`#dp-${id}`); if (!host) return;
    const list = d[id], from = shown[id], to = Math.min(list.length, from + STEP);
    host.querySelector(".dp-more")?.remove();
    host.insertAdjacentHTML("beforeend", list.slice(from, to).map(html[id]).join("") +
      (to < list.length ? `<button class="btn btn--sm btn--ghost dp-more" data-more="${id}">Weitere anzeigen (${list.length - to} übrig)</button>` : ""));
    shown[id] = to; hydrateIcons(host); bindRows(host);
    host.querySelector(".dp-more")?.addEventListener("click", () => fill(id));
  };
  $("#dpOut").innerHTML = !z.songs ? `<div class="empty">${icon("stack")}<h3>Noch keine Playlists</h3><p>Sobald du Songs in lokale Playlists einsortierst, kann hier aufgeräumt werden.</p></div>` : `
    <div class="pls-stats dp-stats"><div><b class="num">${z.doppelt}</b><span>doppelt in einer Playlist</span></div><div><b class="num">${z.mehrfach}</b><span>in mehreren Playlists</span></div><div><b class="num">${z.versionen}</b><span>andere Fassungen (kein Duplikat)</span></div></div>
    <div class="section-title">Doppelt in derselben Playlist</div>
    ${d.doppelt.length ? `<div class="card dp-card" id="dp-doppelt"><p class="cell-sub" style="margin:0 0 10px">Der älteste Eintrag bleibt, die Kopien sind überflüssig.</p>
      <button class="btn btn--sm" id="dpAll">${icon("trash")}${z.doppelt === 1 ? "Die Kopie entfernen" : `Alle ${z.doppelt} Kopien entfernen`}</button></div>`
      : `<div class="card dp-card cell-sub">${icon("check")} Keine – jede Playlist enthält jeden Song nur einmal.</div>`}
    <div class="section-title">In mehreren Playlists</div>
    ${d.mehrfach.length ? `<div class="card dp-card" id="dp-mehrfach"><p class="cell-sub" style="margin:0 0 10px">Kann gewollt sein. Entferne den Song nur dort, wo er nicht hingehört.</p></div>`
      : `<div class="card dp-card cell-sub">${icon("check")} Keine.</div>`}
    <div class="section-title">Andere Fassungen desselben Titels</div>
    ${d.versionen.length ? `<details class="card dp-card" id="dp-versionen"><summary class="cell-sub">${icon("info")} ${z.versionen} ${z.versionen === 1 ? "Titel" : "Titel"} in mehreren Fassungen (Remix, Flip, Bootleg, VIP, Cover, Live, Slowed …) – das sind <b>eigene Songs, keine Duplikate</b>. Aufklappen, falls du nur eine Fassung behalten willst.</summary></details>`
      : `<div class="card dp-card cell-sub">${icon("check")} Keine.</div>`}`;
  hydrateIcons(main);
  const remove = async items => {
    const r = await api("/api/dupes/remove", { method: "POST", body: { items } });
    toast(`${r.removed} ${r.removed === 1 ? "Eintrag" : "Einträge"} entfernt`); refreshMeta(); Views.dupes(main);
  };
  fill("doppelt"); fill("mehrfach");
  $("#dp-versionen")?.addEventListener("toggle", e => { if (e.target.open && !shown.versionen) fill("versionen"); });
  $("#dpAll")?.addEventListener("click", () => modal({
    title: `${z.doppelt} doppelte Einträge entfernen?`, text: "Von jedem Song bleibt der älteste Eintrag in der Playlist.", confirm: "Entfernen",
    onConfirm: () => remove(d.doppelt.flatMap(g => g.remove.map(o => ({ playlist: o.playlist, key: o.key })))),
  }));
};

/* ---------- Entdecken: im Deezer-Katalog stöbern (Suche, Künstler, Alben, Charts nach Genre) und „Ähnlich zu einem Song“.
   Quelle Deezer (ohne Login) – gesendet wird nur der Suchbegriff bzw. die angeklickte Kennung; nichts wird gespeichert. */
const Disc = { tab: store.get("discTab", "browse"), genre: store.get("discGenre", 0), chart: store.get("discChart", "tracks"), genres: null };

const discArtists = t => (t.artists || []).map((n, i) => { const id = (t.artist_ids || [])[i];
  return id ? `<a class="dc-a" href="#/discover?artist=${id}">${esc(n)}</a>` : esc(n); }).join(", ");

function discRows(list, { num = false, album = true } = {}) {
  if (!list.length) return `<div class="cell-sub" style="padding:10px 2px">Nichts gefunden.</div>`;
  return `<div class="rows">${list.map((v, i) => `<div class="row row--dc ${num ? "row--dcn" : ""}" data-i="${i}" title="Klicken: auf Spotify, YouTube & Co. öffnen">
      ${num ? `<div class="cell-muted num dc-num">${i + 1}</div>` : ""}
      <div class="thumb-wrap">${v.cover ? `<img class="thumb" src="${esc(v.cover)}" alt="" loading="lazy">` : `<div class="thumb" style="display:grid;place-items:center;color:var(--text-3)">${icon("disc")}</div>`}
        ${v.preview_url ? `<button class="thumb-play" ${playAttr(v)} aria-label="Hörprobe">${icon("play")}</button>` : ""}</div>
      <div class="cell-main"><div class="cell-title">${esc(v.title)}${v.explicit ? ` <span class="dc-e" title="Expliziter Text">E</span>` : ""}</div><div class="cell-sub">${discArtists(v)}</div></div>
      <div class="cell-sub dc-alb">${album ? (v.album_id ? `<a class="dc-a" href="#/discover?album=${v.album_id}">${esc(v.album || "")}</a>` : esc(v.album || "")) : ""}</div>
      <div class="cell-muted num">${v.duration_ms ? fmtDur(v.duration_ms) : ""}</div>
      <div class="row-act"><button class="icon-btn" data-dver="${i}" title="Remixe & Versionen" aria-label="Remixe & Versionen">${icon("layers")}</button><button class="icon-btn" data-dadd="${i}" title="In eine Playlist legen" aria-label="In Playlist">${icon("plus")}</button></div>
    </div>`).join("")}</div>`;
}
function bindDiscRows(box, list) {
  $$("[data-dadd]", box).forEach(b => b.onclick = () => addFoundToPlaylist(list[+b.dataset.dadd]));
  $$("[data-dver]", box).forEach(b => b.onclick = () => showVersionsOf(list[+b.dataset.dver]));
  bindSimilar(box, list, ".row--dc");
  Player.sync();
}
const discCards = (list, kind) => list.length ? `<div class="dc-grid">${list.map(x => kind === "artist"
  ? `<a class="dc-card" href="#/discover?artist=${x.id}">${x.picture ? `<img class="dc-pic dc-pic--round" src="${esc(x.picture)}" alt="" loading="lazy">` : `<div class="dc-pic dc-pic--round"></div>`}
      <b>${esc(x.name)}</b><span>${x.fans ? `${x.fans.toLocaleString("de-DE")} Fans` : "Künstler"}</span></a>`
  : `<a class="dc-card" href="#/discover?album=${x.id}">${x.cover ? `<img class="dc-pic" src="${esc(x.cover)}" alt="" loading="lazy">` : `<div class="dc-pic"></div>`}
      <b>${esc(x.title)}</b><span>${[x.artist, x.type, x.year].filter(Boolean).map(esc).join(" · ")}</span></a>`).join("")}</div>`
  : `<div class="cell-sub" style="padding:10px 2px">Nichts gefunden.</div>`;

function addFoundToPlaylist(v) {
  modal({ title: "In welche Playlist?", text: `${esc(v.title)} – ${esc((v.artists || []).join(", "))}`, body: `<input class="input" id="verPl" list="plnames" placeholder="Name einer Playlist (neu oder vorhanden)" style="width:100%" autocomplete="off">`, confirm: "Hinzufügen",
    onConfirm: async m => {
      const name = $("#verPl", m).value.trim();
      if (!name) { toast("Bitte einen Namen eingeben", "err"); throw { silent: true }; }
      const res = await api("/api/versions/add", { method: "POST", body: { playlist: name, track: v } });
      toast(res.added ? `Zu „${res.playlist}“ hinzugefügt` : `War schon in „${res.playlist}“`);
      refreshMeta();
    } });
}
function saveAllAsPlaylist(list, name) {
  if (!list.length) return;
  modal({ title: `${list.length} Songs als Playlist speichern`, text: "Neue Playlist oder an eine vorhandene anhängen – Songs, die schon drin sind, werden übersprungen.",
    body: `<input class="input" id="dcPl" list="plnames" value="${esc(name)}" style="width:100%" autocomplete="off">`, confirm: "Speichern",
    onConfirm: async m => {
      const pl = $("#dcPl", m).value.trim();
      if (!pl) { toast("Bitte einen Namen eingeben", "err"); throw { silent: true }; }
      const r = await api("/api/discover/save", { method: "POST", body: { playlist: pl, tracks: list } });
      toast(`${r.added} Songs in „${r.playlist}“${r.skipped ? ` (${r.skipped} waren schon drin)` : ""}`);
      refreshMeta();
    } });
}
function showVersionsOf(v) {
  modal({ title: "Remixe & Versionen", text: `${esc(v.title)} – ${esc((v.artists || []).join(", "))}`, body: `<div id="dcVer"></div>`, confirm: "Schließen", cancel: null, wide: true });
  loadVersions($("#dcVer"), { track: { title: v.title, artists: v.artists || [] } });
}

Views.discover = async (main, _, params) => {
  const p = params || new URLSearchParams();
  const deep = p.get("artist") || p.get("album");
  if (deep) Disc.tab = "browse";
  main.innerHTML = `<div class="page view-enter dc-page">
    <div class="page-head"><div><h1>Entdecken</h1><p>Stöbere im Katalog von Deezer: Songs, Künstler und Alben suchen, Charts nach Genre, reinhören und in Playlists legen.</p></div>
      <div class="segmented" id="dcTabs"><button data-t="browse" class="${Disc.tab === "browse" ? "on" : ""}">${icon("compass")}Stöbern</button><button data-t="similar" class="${Disc.tab === "similar" ? "on" : ""}">${icon("sparkle")}Ähnlich zu einem Song</button></div></div>
    <div id="dcBody"></div></div>`;
  hydrateIcons(main);
  $$("#dcTabs button").forEach(b => b.onclick = () => {
    Disc.tab = b.dataset.t; store.set("discTab", Disc.tab);
    if (location.hash !== "#/discover") location.hash = "#/discover"; else Views.discover(main, null, new URLSearchParams());
  });
  const body = $("#dcBody");
  if (Disc.tab === "similar") return discSimilar(body);
  if (p.get("artist")) return discArtist(body, p.get("artist"));
  if (p.get("album")) return discAlbum(body, p.get("album"));
  body.innerHTML = `<div class="card discover-bar"><div class="input-icon" style="flex:1">${icon("search")}<input class="input" id="dcQ" placeholder="Song, Künstler oder Album suchen …" value="${esc(p.get("q") || "")}" autocomplete="off"></div></div>
    <div id="dcOut"></div>
    <div class="cell-sub dc-foot">Quelle: Deezer (ohne Login) – gesendet wird nur dein Suchbegriff bzw. was du anklickst; Deezer sieht dabei deine IP-Adresse. Gespeichert wird nichts.</div>`;
  hydrateIcons(body);
  const q = $("#dcQ"), out = $("#dcOut");
  let tmo, seq = 0;
  const run = async () => {
    const term = q.value.trim(), my = ++seq;
    history.replaceState(null, "", term ? `#/discover?q=${encodeURIComponent(term)}` : "#/discover");
    if (!term) return discCharts(out);
    out.innerHTML = skeletonRows(6);
    let d;
    try { d = await api(`/api/discover/search?q=${encodeURIComponent(term)}`); } catch (e) { if (my === seq) out.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; return; }
    if (my !== seq || !document.body.contains(out)) return;
    out.innerHTML = `${d.artists.length ? `<div class="section-title">Künstler</div>${discCards(d.artists, "artist")}` : ""}
      <div class="section-title dc-st">Songs<button class="btn btn--sm btn--ghost" id="dcMore">Mehr Songs</button></div><div id="dcTr">${discRows(d.tracks)}</div>
      ${d.albums.length ? `<div class="section-title">Alben</div>${discCards(d.albums, "album")}` : ""}`;
    hydrateIcons(out); bindDiscRows($("#dcTr"), d.tracks);
    $("#dcMore").onclick = async e => {
      e.target.disabled = true;
      try { const m = await api(`/api/discover/search?kind=track&q=${encodeURIComponent(term)}`); $("#dcTr").innerHTML = discRows(m.items); bindDiscRows($("#dcTr"), m.items); e.target.remove(); }
      catch (err) { toast(err.message, "err"); e.target.disabled = false; }
    };
  };
  q.oninput = () => { clearTimeout(tmo); tmo = setTimeout(run, 400); };
  q.onkeydown = e => { if (e.key === "Enter") { clearTimeout(tmo); run(); } };
  run();
  if (!p.get("q")) q.focus();
};

async function discCharts(out) {
  out.innerHTML = skeletonRows(6);
  if (!Disc.genres) Disc.genres = await api("/api/discover/genres").catch(() => [{ id: 0, name: "Alle" }]);
  let d;
  try { d = await api(`/api/discover/charts?genre=${Disc.genre}`); } catch (e) { out.innerHTML = `<div class="cell-sub">${esc(e.message)}</div>`; return; }
  if (!document.body.contains(out)) return;
  const g = Disc.genres.find(x => x.id === Disc.genre)?.name || "Alle";
  out.innerHTML = `<div class="section-title dc-st">Charts${Disc.genre ? ` · ${esc(g)}` : ""}
      <div class="segmented segmented--sm" id="dcCk">${[["tracks", "Songs"], ["artists", "Künstler"], ["albums", "Alben"]].map(([k, l]) => `<button data-k="${k}" class="${Disc.chart === k ? "on" : ""}">${l}</button>`).join("")}</div>
      ${Disc.chart === "tracks" ? `<button class="btn btn--sm btn--ghost" id="dcSaveCh">${icon("plus")}Als Playlist</button>` : ""}</div>
    <div class="ver-chips">${Disc.genres.map(x => `<button class="chip ${x.id === Disc.genre ? "chip--on" : ""}" data-g="${x.id}">${esc(x.name)}</button>`).join("")}</div>
    <div id="dcCh">${Disc.chart === "tracks" ? discRows(d.tracks, { num: true }) : discCards(d[Disc.chart], Disc.chart === "artists" ? "artist" : "album")}</div>`;
  hydrateIcons(out);
  if (Disc.chart === "tracks") bindDiscRows($("#dcCh"), d.tracks);
  $$("[data-g]", out).forEach(b => b.onclick = () => { Disc.genre = +b.dataset.g; store.set("discGenre", Disc.genre); discCharts(out); });
  $$("#dcCk button", out).forEach(b => b.onclick = () => { Disc.chart = b.dataset.k; store.set("discChart", Disc.chart); discCharts(out); });
  const sv = $("#dcSaveCh", out); if (sv) sv.onclick = () => saveAllAsPlaylist(d.tracks, `Charts ${g} ${new Date().toLocaleDateString("de-DE")}`);
}

async function discArtist(body, aid) {
  body.innerHTML = skeletonRows(6);
  let d;
  try { d = await api(`/api/discover/artist/${encodeURIComponent(aid)}`); } catch (e) { body.innerHTML = `<div class="empty">${icon("info")}<h3>Geht gerade nicht</h3><p>${esc(e.message)}</p></div>`; return; }
  if (!document.body.contains(body)) return;
  const a = d.artist;
  let all = false;
  body.innerHTML = `<button class="btn btn--sm btn--ghost dc-back" id="dcBack">${icon("prev")}Zurück</button>
    <div class="card dc-hero">${a.picture_big || a.picture ? `<img class="dc-hero-pic dc-pic--round" src="${esc(a.picture_big || a.picture)}" alt="">` : ""}
      <div class="dc-hero-txt"><span class="cell-sub">Künstler</span><h2>${esc(a.name)}</h2>
        <div class="cell-sub">${[a.fans ? `${a.fans.toLocaleString("de-DE")} Fans bei Deezer` : "", a.albums ? `${a.albums} Veröffentlichungen` : ""].filter(Boolean).join(" · ")}</div>
        <div class="btn-row">${d.top.length ? `<button class="btn btn--primary btn--sm" id="dcPlay">${icon("play")}Reinhören</button>` : ""}
          <button class="btn btn--sm" id="dcMix">${icon("shuffle")}Mix mit ${esc(a.name)}</button>
          ${d.top.length ? `<button class="btn btn--sm" id="dcSaveTop">${icon("plus")}Top-Songs als Playlist</button>` : ""}
          ${a.link ? `<a class="btn btn--sm btn--ghost" href="${esc(a.link)}" target="_blank" rel="noopener">${icon("external")}Bei Deezer</a>` : ""}</div></div></div>
    <div class="section-title dc-st">Beliebteste Songs${d.top.length > 10 ? `<button class="btn btn--sm btn--ghost" id="dcAll">Alle ${d.top.length} zeigen</button>` : ""}</div><div id="dcTop"></div>
    ${d.albums.length ? `<div class="section-title">Alben</div>${discCards(d.albums, "album")}` : ""}
    ${d.singles.length ? `<div class="section-title">Singles & EPs</div>${discCards(d.singles, "album")}` : ""}
    ${d.related.length ? `<div class="section-title">Ähnliche Künstler</div>${discCards(d.related, "artist")}` : ""}`;
  hydrateIcons(body);
  const drawTop = () => { const l = all ? d.top : d.top.slice(0, 10); $("#dcTop").innerHTML = discRows(l, { num: true }); bindDiscRows($("#dcTop"), l); };
  drawTop();
  $("#dcBack").onclick = () => history.length > 1 ? history.back() : (location.hash = "#/discover");
  const al = $("#dcAll"); if (al) al.onclick = () => { all = true; al.remove(); drawTop(); };
  const pl = $("#dcPlay"); if (pl) pl.onclick = () => $("#dcTop .thumb-play")?.click();
  const st = $("#dcSaveTop"); if (st) st.onclick = () => saveAllAsPlaylist(d.top, `Best of ${a.name}`);
  $("#dcMix").onclick = () => { mixAddSeed({ id: a.id, name: a.name, picture: a.picture }); Mix.mode = "artists"; store.set("mixMode", "artists"); location.hash = "#/mix"; };
}

async function discAlbum(body, alid) {
  body.innerHTML = skeletonRows(6);
  let d;
  try { d = await api(`/api/discover/album/${encodeURIComponent(alid)}`); } catch (e) { body.innerHTML = `<div class="empty">${icon("info")}<h3>Geht gerade nicht</h3><p>${esc(e.message)}</p></div>`; return; }
  if (!document.body.contains(body)) return;
  const a = d.album;
  const who = a.artist_id ? `<a class="dc-a" href="#/discover?artist=${a.artist_id}">${esc(a.artist || "")}</a>` : esc((a.artists || []).join(", "));
  body.innerHTML = `<button class="btn btn--sm btn--ghost dc-back" id="dcBack">${icon("prev")}Zurück</button>
    <div class="card dc-hero">${a.cover_big || a.cover ? `<img class="dc-hero-pic" src="${esc(a.cover_big || a.cover)}" alt="">` : ""}
      <div class="dc-hero-txt"><span class="cell-sub">${esc(a.type || "Album")}</span><h2>${esc(a.title)}</h2><div>${who}</div>
        <div class="cell-sub">${[a.date ? new Date(a.date).toLocaleDateString("de-DE") : a.year, d.tracks.length ? `${d.tracks.length} Songs` : "", a.duration_ms ? `${Math.round(a.duration_ms / 60000)} Min.` : "", a.label, (a.genres || []).join(", ")].filter(Boolean).map(esc).join(" · ")}</div>
        <div class="btn-row">${d.tracks.some(t => t.preview_url) ? `<button class="btn btn--primary btn--sm" id="dcPlay">${icon("play")}Reinhören</button>` : ""}
          ${d.tracks.length ? `<button class="btn btn--sm" id="dcSave">${icon("plus")}Als Playlist speichern</button>` : ""}
          ${a.link ? `<a class="btn btn--sm btn--ghost" href="${esc(a.link)}" target="_blank" rel="noopener">${icon("external")}Bei Deezer</a>` : ""}</div></div></div>
    <div class="section-title">Songs</div><div id="dcTr">${discRows(d.tracks, { num: true, album: false })}</div>`;
  hydrateIcons(body); bindDiscRows($("#dcTr"), d.tracks);
  $("#dcBack").onclick = () => history.length > 1 ? history.back() : (location.hash = "#/discover");
  const pl = $("#dcPlay"); if (pl) pl.onclick = () => $("#dcTr .thumb-play")?.click();
  const sv = $("#dcSave"); if (sv) sv.onclick = () => saveAllAsPlaylist(d.tracks, `${a.artist ? `${a.artist} – ` : ""}${a.title}`);
}

/* „Ähnlich zu einem Song“: Genre, Subgenre und ähnliche Tracks über Last.fm (die bisherige Entdecken-Seite) */
function discSimilar(body) {
  body.innerHTML = `<div class="card discover-bar">
      <input class="input" id="dArtist" placeholder="Künstler, z. B. Netsky">
      <input class="input" id="dTitle" placeholder="Titel, z. B. Come Alive">
      <button class="btn btn--primary" id="dGo">${icon("compass")}Ähnliche finden</button>
    </div>
    <div class="toolbar hidden" id="dTools">
      <div class="seed" id="dSeed" style="margin:0"></div>
      <label class="switch" style="margin-left:auto"><input type="checkbox" id="dSame"><span class="track"></span>Nur gleiches Subgenre</label>
    </div>
    <div id="dOut"><div class="empty">${icon("compass")}<h3>Ähnliche Songs finden</h3><p>Gib einen Song ein – du bekommst Genre, Subgenre und ähnliche Tracks, basierend auf Last.fm-Hörerdaten.</p></div></div>`;
  hydrateIcons(body);
  let data = null;
  const draw = () => {
    if (!data) return;
    const same = $("#dSame").checked;
    const list = same ? data.similar.filter(s => s.subgenre && s.subgenre === data.subgenre) : data.similar;
    $("#dOut").innerHTML = similarRows(list); bindSimilar($("#dOut"), list); lazyCovers($("#dOut"), list);
    if (list.length) measureSimilar($("#dOut"), list, `/api/audiofeat?${featQuery({ artists: [$("#dArtist").value.trim()], title: $("#dTitle").value.trim() })}`);
  };
  const go = async () => {
    const a = $("#dArtist").value.trim(), t = $("#dTitle").value.trim();
    if (!a || !t) return toast("Bitte Künstler und Titel eingeben", "err");
    $("#dOut").innerHTML = skeletonRows(6);
    try {
      data = await api("/api/discover", { method: "POST", body: { artist: a, title: t } });
      $("#dTools").classList.remove("hidden");
      $("#dSeed").innerHTML = `<span>${esc(a)} – ${esc(t)}</span> ${genreChip(data.genre, data.subgenre)}`;
      draw();
    } catch (e) { $("#dOut").innerHTML = `<div class="empty">${icon("info")}<h3>Geht gerade nicht</h3><p>${esc(e.message)}</p>${/Last\.fm/.test(e.message) ? `<p style="margin-top:14px"><a class="btn" href="#/settings">${icon("sliders")}Zu den Einstellungen</a></p>` : ""}</div>`; }
  };
  $("#dGo").onclick = go;
  [$("#dArtist"), $("#dTitle")].forEach(i => i.onkeydown = e => e.key === "Enter" && go());
  $("#dSame").onchange = draw;
}

/* ---------- Aufteilen */
Views.split = async (main, _, params) => {
  await refreshMeta();
  const pls = S.playlists.filter(p => p.count > 0);
  let sel = params.get("pl") || pls[0]?.name || "", detail = "sub";
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Aufteilen</h1><p>Eine große Playlist automatisch in Genre-Playlists zerlegen – grob oder bis ins Subgenre.</p></div></div>
    ${pls.length ? `<div class="card" style="padding:16px;margin-bottom:22px"><div class="form-row">
      <div class="field"><label>Playlist</label><select class="select" id="sPl" style="min-width:240px">${pls.map(p => `<option ${p.name === sel ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select></div>
      <div class="field"><label>Genauigkeit</label><div class="segmented" id="sDet"><button data-d="main">Grob</button><button data-d="sub" class="on">Mit Subgenre</button></div></div>
      <div class="field"><label>Präfix (optional)</label><input class="input" id="sPre" placeholder="z. B. „Sorted · “"></div>
      <div class="field" style="margin-left:auto"><label>&nbsp;</label><button class="btn btn--primary" id="sApply">${icon("check")}Playlists anlegen</button></div>
    </div></div><div id="sOut"></div>`
    : `<div class="empty">${icon("split")}<h3>Keine Playlist zum Aufteilen</h3><p>Sobald eine Playlist Songs enthält (oder von einer Plattform importiert ist), kannst du sie hier zerlegen.</p></div>`}
  </div>`;
  if (!pls.length) return;
  const preview = async () => {
    $("#sOut").innerHTML = skeletonRows(3);
    const parts = await api("/api/split/preview", { method: "POST", body: { playlist: sel, detail, prefix: $("#sPre").value } });
    $("#sOut").innerHTML = `<div class="section-title" style="margin-top:0">Vorschau · ${parts.length} Playlists</div><div class="split-grid">${parts.map(p => `
      <div class="card split-card"><h4><span class="dot" style="background:${genreColor(p.genre, p.subgenre)}"></span>${esc(p.name)}</h4>
        <div class="cnt">${p.count} ${p.count === 1 ? "Song" : "Songs"}</div>
        <ul>${p.tracks.map(t => `<li>${t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : `<span class="ph"></span>`}<span>${esc(t.artists.join(", "))} – ${esc(t.title)}</span></li>`).join("")}
        ${p.count > p.tracks.length ? `<li class="muted">+ ${p.count - p.tracks.length} weitere</li>` : ""}</ul></div>`).join("")}</div>`;
  };
  $("#sPl").onchange = e => { sel = e.target.value; preview(); };
  $$("#sDet button").forEach(b => b.onclick = () => { detail = b.dataset.d; $$("#sDet button").forEach(x => x.classList.toggle("on", x === b)); preview(); });
  let tmo; $("#sPre").oninput = () => { clearTimeout(tmo); tmo = setTimeout(preview, 300); };
  $("#sApply").onclick = async () => {
    const r = await api("/api/split/apply", { method: "POST", body: { playlist: sel, detail, prefix: $("#sPre").value } });
    toast(`${r.added} Einträge auf Genre-Playlists verteilt`); refreshMeta();
  };
  preview();
};

/* ---------- Übertragen */
const PLATFORM_STYLE = {
  spotify: ["Spotify", "S", "#1ed760"], tidal: ["TIDAL", "T", "#d6dbe2"], ytmusic: ["YouTube Music", "YM", "#ff5a50"],
  youtube: ["YouTube", "YT", "#ff5a50"], soundcloud: ["SoundCloud", "SC", "#ff8a3d"], apple: ["Apple Music", "A", "#fa6a86"],
  shazam: ["Shazam", "Sh", "#0a8cff"],
};
const SVC_NAME = id => String(id).startsWith("friend-") ? (Share.nicks[id] || "Freund") : id === "local" ? "SH-Tunebridge" : id === "link" ? "Link" : (PLATFORM_STYLE[id]?.[0] || id);
const Transfer = { job: null };
/* ---------- Dienste einrichten: Schritt-für-Schritt-Assistent (eigene Entwickler-App) und Datei-Import
   Ziel: auch ohne Fachwissen. Jeder Schritt: was öffnen, was anklicken, was kopieren – mit Kopieren-Knöpfen,
   einer kleinen Skizze und typischen Fehlern. Wer keine Entwickler-App will (oder kein Premium hat), nimmt den
   offiziellen Datenexport des Dienstes (DSGVO-Auskunft) und zieht die Datei einfach rein. */
const REDIRECT = sid => `http://127.0.0.1:8765/api/${sid === "spotify" ? "spotify" : `oauth/${sid}`}/callback`;
const LFM_CB = "http://127.0.0.1:8765/api/lastfm/callback";
const sketch = (url, rows) => `<div class="wz-sketch" aria-hidden="true"><div class="wz-bar"><i></i><i></i><i></i><span>${esc(url)}</span></div>
  <div class="wz-page">${rows.map(r => `<div class="wz-row">${r}</div>`).join("")}</div></div>`;
const hl = t => `<span class="wz-hl">${esc(t)}</span>`, fake = t => `<span class="wz-fake">${esc(t)}</span>`;

const SETUP = {
  spotify: {
    name: "Spotify", needs: "Spotify Premium (für den App-Besitzer, also dich)", time: "ca. 5 Minuten",
    why: "Spotify lässt andere Programme nur über eine eigene, kostenlose „Entwickler-App“ an deine Playlists. Die legst du einmal an – wir zeigen dir jeden Klick.",
    steps: [
      { title: "Bevor es losgeht", html: `Spotify hat die Regeln 2026 verschärft. Damit es klappt, brauchst du:
          <ul class="wz-list"><li><b>Spotify Premium</b> – Spotify lässt Entwickler-Apps nur noch für Premium-Konten zu.</li>
          <li>Dein <b>normales Spotify-Konto</b> (Benutzername/Passwort) – kein neues Konto nötig.</li>
          <li>Pro Konto erlaubt Spotify <b>nur eine</b> Entwickler-App. Hast du schon eine, nimm die (Schritt 4 zeigt, was rein muss).</li></ul>
          Läuft alles nebenbei im Browser – dieses Fenster bleibt offen und führt dich.`,
        gate: ["Ich habe Spotify Premium"],
        alt: ["Kein Premium?", "Dann Datenexport importieren (geht immer)", () => importWizard("spotify", $("#main"))] },
      { title: "Spotify für Entwickler öffnen", link: ["https://developer.spotify.com/dashboard", "Spotify-Dashboard öffnen"],
        html: `Klicke auf den grünen Knopf. Es öffnet sich die Spotify-Seite für Entwickler.
          <ol class="wz-list"><li>Mit deinem <b>normalen Spotify-Konto</b> anmelden.</li>
          <li>Beim ersten Mal: Nutzungsbedingungen <b>„Accept the terms“</b> anhaken und bestätigen.</li>
          <li>Kommt eine Bestätigungs-Mail von Spotify: den Link darin anklicken, dann die Seite neu laden.</li></ol>`,
        sketch: sketch("developer.spotify.com/dashboard", [`<b>Dashboard</b>`, `${fake("Deine Apps")} ${hl("Create app")}`]),
        gate: ["Ich sehe das Dashboard mit dem Knopf „Create app“"] },
      { title: "Neue App anlegen", html: "Klicke auf <b>„Create app“</b>. Es öffnet sich ein Formular. Trage Name und Beschreibung ein (Kopieren-Knopf, dann im Formular einfügen):",
        copy: [["App name", "SH-Tunebridge"], ["App description", "Meine Playlists in SH-Tunebridge"]],
        after: "Noch <b>nicht</b> speichern – im selben Formular geht es weiter.",
        sketch: sketch("developer.spotify.com/create", [`App name ${fake("SH-Tunebridge")}`, `App description ${fake("Meine Playlists …")}`]) },
      { title: "Die wichtigste Zeile: Redirect URI", html: `Im selben Formular gibt es das Feld <b>„Redirect URIs“</b>. Genau diese Adresse kopieren und dort einfügen –
          <b>dann rechts daneben auf „Add“ klicken</b>. Erst dann steht sie <b>darunter als Eintrag in der Liste</b>.`,
        copy: [["Redirect URI", REDIRECT("spotify")]],
        after: `<div class="notice">${icon("info")}<div>Genau so – nicht <code>localhost</code>, nicht <code>https</code>, kein <code>/</code> am Ende. Fehlt sie oder ist ein Zeichen anders, zeigt Spotify später <b>„redirect_uri: Not matching configuration“</b>.</div></div>`,
        sketch: sketch("developer.spotify.com/create", [`Redirect URIs ${fake("http://127.0.0.1:8765/…")} ${hl("Add")}`, `${hl("✓ http://127.0.0.1:8765/api/spotify/callback")} ← steht jetzt in der Liste`]),
        gate: ["Ich habe auf „Add“ geklickt und die Adresse steht unter dem Feld in der Liste"] },
      { title: "Web API ankreuzen und speichern", html: `Weiter unten im Formular:
          <ol class="wz-list"><li>Bei „Which API/SDKs are you planning to use?“ <b>„Web API“</b> anhaken.</li>
          <li>Den Bedingungen zustimmen.</li><li>Ganz unten auf <b>„Save“</b> klicken.</li></ol>`,
        sketch: sketch("developer.spotify.com/create", [`☑ ${hl("Web API")}`, `☑ ${fake("I understand and agree …")}`, `${hl("Save")}`]),
        gate: ["Gespeichert – ich sehe jetzt die Seite meiner neuen App"] },
      { title: "Client ID kopieren", html: "Auf der Seite deiner App oben rechts auf <b>„Settings“</b> klicken. Ganz oben steht die <b>Client ID</b> – kopieren und hier einfügen.<br><span class=\"muted\">Nicht „View client secret“ – das Secret brauchen wir nicht.</span>",
        sketch: sketch("developer.spotify.com/dashboard/…/settings", [`Basic Information`, `Client ID ${hl("a1b2c3…  (kopieren)")}`, `${fake("View client secret")} ← nicht nötig`]),
        fields: [{ id: "SPOTIFY_CLIENT_ID", label: "Client ID", ph: "32 Zeichen, z. B. 1a2b3c4d…", re: /^[0-9a-f]{32}$/i,
          err: "Eine Client ID besteht aus genau 32 Zeichen (Ziffern und a–f). Bitte nur die ID kopieren, ohne Leerzeichen." }] },
      { title: "Letzte Kontrolle", html: `Auf derselben „Settings“-Seite steht weiter unten <b>„Redirect URIs“</b>. Dort muss genau das stehen:`,
        copy: [["Redirect URI", REDIRECT("spotify")]],
        after: "Steht dort nichts oder etwas anderes: oben auf <b>„Edit“</b>, Adresse einfügen, <b>„Add“</b>, ganz unten <b>„Save“</b>. Danach hier auf „Speichern &amp; verbinden“ – es öffnet sich die Spotify-Anmeldung.",
        gate: ["Unter „Redirect URIs“ steht genau diese Adresse"] },
    ],
    trouble: [
      ["„redirect_uri: Not matching configuration“", `Die Redirect-URI in deiner Spotify-App stimmt nicht genau. Bei der App › Settings › Edit › Redirect URIs genau diese Adresse eintragen, „Add“ und unten „Save“ klicken:<div class="wz-copyline"><code>${REDIRECT("spotify")}</code><button class="btn btn--sm btn--ghost" data-copy="${REDIRECT("spotify")}">Kopieren</button></div>Typische Fehler: <code>localhost</code> statt <code>127.0.0.1</code>, <code>https</code>, ein <code>/</code> am Ende, „Save“ vergessen. Nach dem Speichern kann es 1–2 Minuten dauern.`],
      ["„INVALID_CLIENT: Invalid client“", "Die Client ID ist falsch (oder es wurde das Secret eingefügt). Einrichtung wiederholen und die Client ID neu kopieren."],
      ["Hinweis zu Premium oder „user not registered“", "Spotify verlangt seit 2026 Premium für den Besitzer der Entwickler-App. Andere Konten musst du in deiner App unter „User Management“ eintragen (höchstens 5). Ohne Premium: nimm den Datei-Import."],
      ["Es passiert gar nichts", "Hat sich der Browser geöffnet? Sonst den Link oben im Fenster anklicken. Läuft SH-Tunebridge? Die Anmeldung kommt an diese App zurück."],
    ],
  },
  youtube: {
    name: "YouTube", needs: "ein Google-Konto", time: "ca. 10 Minuten",
    why: "Google lässt andere Programme nur über ein eigenes, kostenloses „Google-Cloud-Projekt“ an deine YouTube-Playlists. Es wird nur gelesen.",
    steps: [
      { title: "Projekt anlegen", link: ["https://console.cloud.google.com/projectcreate", "Google Cloud öffnen"],
        html: "Mit deinem Google-Konto anmelden. Beim ersten Mal Land wählen und den Bedingungen zustimmen. Projektname eintragen und <b>„Erstellen“</b>. Kostet nichts – es wird keine Zahlungsart gebraucht.",
        copy: [["Projektname", "SH-Tunebridge"]],
        sketch: sketch("console.cloud.google.com/projectcreate", [`Neues Projekt`, `Projektname ${fake("SH-Tunebridge")}`, hl("Erstellen")]) },
      { title: "YouTube-Schnittstelle einschalten", link: ["https://console.cloud.google.com/apis/library/youtube.googleapis.com", "YouTube Data API öffnen"],
        html: "Oben muss dein neues Projekt „SH-Tunebridge“ ausgewählt sein. Dann auf <b>„Aktivieren“</b> klicken.",
        sketch: sketch("console.cloud.google.com/apis/library/youtube…", [`YouTube Data API v3`, hl("Aktivieren")]) },
      { title: "Anmeldeseite einrichten", link: ["https://console.cloud.google.com/auth/overview", "Google Auth Platform öffnen"],
        html: "Auf <b>„Jetzt starten“</b>. App-Name eintragen, als Support-E-Mail deine Adresse wählen › Weiter. Zielgruppe <b>„Extern“</b> › Weiter. Kontakt-E-Mail: deine Adresse › Weiter. Zustimmen › <b>„Erstellen“</b>.",
        copy: [["App-Name", "SH-Tunebridge"]],
        sketch: sketch("console.cloud.google.com/auth/overview", [`App-Name ${fake("SH-Tunebridge")}`, `Zielgruppe ${hl("Extern")}`, hl("Erstellen")]) },
      { title: "Dich als Testnutzer eintragen", link: ["https://console.cloud.google.com/auth/audience", "Zielgruppe öffnen"],
        html: "Unter <b>„Testnutzer“</b> auf <b>„+ Add users“</b> und deine eigene Gmail-Adresse eintragen › Speichern. Ohne diesen Schritt sagt Google später „Zugriff blockiert“.",
        sketch: sketch("console.cloud.google.com/auth/audience", [`Testnutzer`, `${hl("+ Add users")} ${fake("du@gmail.com")}`]) },
      { title: "Zugangsdaten erstellen", link: ["https://console.cloud.google.com/auth/clients/create", "Client erstellen"],
        html: "Anwendungstyp <b>„Desktop-App“</b> wählen (wichtig!), Name eintragen › <b>„Erstellen“</b>. Google zeigt dann <b>Client-ID</b> und <b>Clientschlüssel</b> – beide kopieren und hier einfügen.",
        copy: [["Name", "SH-Tunebridge"]],
        sketch: sketch("console.cloud.google.com/auth/clients/create", [`Anwendungstyp ${hl("Desktop-App")}`, `Client-ID ${fake("123…apps.googleusercontent.com")}`, `Clientschlüssel ${fake("GOCSPX-…")}`]),
        fields: [{ id: "YOUTUBE_OAUTH_CLIENT_ID", label: "Client-ID", ph: "…apps.googleusercontent.com", re: /^[\w.-]+\.apps\.googleusercontent\.com$/,
                   err: "Die Client-ID endet auf „.apps.googleusercontent.com“." },
                 { id: "YOUTUBE_OAUTH_CLIENT_SECRET", label: "Clientschlüssel", ph: "GOCSPX-…", secret: true, re: /^\S{10,}$/, err: "Bitte auch den Clientschlüssel einfügen." }] },
    ],
    trouble: [
      ["„Zugriff blockiert“ / „access_denied“", "Du bist nicht als Testnutzer eingetragen (Schritt 4). Danach erneut verbinden."],
      ["„Google hat diese App nicht überprüft“", "Das ist bei eigenen Projekten normal: auf „Weiter“ klicken. Es ist deine eigene App."],
      ["„redirect_uri_mismatch“", "Der Client ist keine „Desktop-App“. Lege in Schritt 5 einen neuen Client als Desktop-App an und trage die neuen Daten ein."],
      ["„YouTube Data API … has not been used“", "Die Schnittstelle ist nicht eingeschaltet (Schritt 2) – oder oben war ein anderes Projekt ausgewählt."],
      ["Nach 7 Tagen abgemeldet", "Google beendet Logins von Test-Apps nach 7 Tagen. Einfach erneut auf „Verbinden“ klicken."],
    ],
  },
  soundcloud: {
    name: "SoundCloud", needs: "SoundCloud Artist Pro", time: "ca. 5 Minuten",
    why: "SoundCloud gibt Zugriff nur über eine eigene SoundCloud-App. Neue Apps können nur Konten mit Artist Pro anlegen. Einen Datenexport zum Hochladen bietet SoundCloud leider nicht an.",
    steps: [
      { title: "Bevor es losgeht", html: `SoundCloud erlaubt eigene Apps nur mit <b>Artist Pro</b> (kostenpflichtiges SoundCloud-Abo für Künstler).
          Ohne Artist Pro fehlt auf der Apps-Seite der Knopf zum Anlegen – dann geht SoundCloud leider nicht.`,
        gate: ["Mein SoundCloud-Konto hat Artist Pro"] },
      { title: "App anlegen", link: ["https://soundcloud.com/you/apps", "SoundCloud-Apps öffnen"],
        html: `<ol class="wz-list"><li>Mit deinem SoundCloud-Konto anmelden.</li><li>Neue App anlegen (<b>„Register a new application“</b>).</li>
          <li>Name eintragen und bei <b>Redirect URI</b> genau diese Adresse einfügen – <b>mit</b> <code>http://</code> vorne, nicht <code>localhost</code>, kein <code>/</code> am Ende.</li>
          <li><b>Achtung:</b> Das Feld <b>„Website deiner App“</b> ist ein anderes Feld – dort gehört die Adresse <b>nicht</b> hin (leer lassen oder eine beliebige Website).</li>
          <li>Speichern.</li></ol>`,
        copy: [["Name", "SH-Tunebridge"], ["Redirect URI", REDIRECT("soundcloud")]],
        sketch: sketch("soundcloud.com/you/apps", [`Register a new application`, `Redirect URI ${fake("http://127.0.0.1:8765/…")}`, hl("Save")]),
        gate: ["Die App ist gespeichert und die Redirect URI steht genau so drin"] },
      { title: "Zugangsdaten kopieren", html: "In deiner App stehen <b>Client ID</b> und <b>Client Secret</b>. Beide einzeln kopieren und hier einfügen – nicht vertauschen. Beim Speichern prüft SH-Tunebridge sie direkt bei SoundCloud.",
        fields: [{ id: "SOUNDCLOUD_CLIENT_ID", label: "Client ID", ph: "Client ID", re: /^[A-Za-z0-9_-]{16,64}$/, err: "Das sieht nicht nach einer Client ID aus." },
                 { id: "SOUNDCLOUD_CLIENT_SECRET", label: "Client Secret", ph: "Client Secret", secret: true, re: /^\S{8,}$/, err: "Bitte auch das Client Secret einfügen." }] },
    ],
    trouble: [
      ["Die SoundCloud-Seite bleibt weiß", `SoundCloud zeigt bei falschen App-Angaben keine Fehlermeldung, nur eine weiße Seite. Fast immer stimmt die <b>Redirect URI</b> in deiner SoundCloud-App nicht genau (häufig landet sie versehentlich im Feld „Website deiner App“ oder ohne <code>http://</code>). Ins Feld <b>Redirect URI</b> genau diese Adresse eintragen und speichern:<div class="wz-copyline"><code>${REDIRECT("soundcloud")}</code><button class="btn btn--sm btn--ghost" data-copy="${REDIRECT("soundcloud")}">Kopieren</button></div>Danach die weiße Seite schließen und hier „Einrichtung wiederholen“. Hilft das nicht: Werbeblocker/Tracking-Schutz für soundcloud.com kurz ausschalten (die Anmeldeseite braucht deren Skripte).`],
      ["„invalid_client“", "Client ID oder Secret falsch – Einrichtung wiederholen."],
    ],
  },
  lastfm: {
    name: "Last.fm", needs: "ein kostenloses Last.fm-Konto", time: "ca. 3 Minuten", login: true,
    why: "Last.fm liefert Genre-Angaben und deine Loved Tracks. Dafür legst du einmal ein kostenloses API-Konto an – danach meldest du dich ganz normal mit Last.fm an.",
    steps: [
      { title: "Bei Last.fm anmelden", link: ["https://www.last.fm/login", "Last.fm öffnen"],
        html: `Im Browser bei Last.fm anmelden. Noch kein Konto? Dort über <b>„Registrieren“</b> kostenlos eins anlegen.
          <p class="muted">Tipp: Verbinde Last.fm in Spotify/YouTube Music mit „Scrobbeln“ – dann landet auch dort Gehörtes bei Last.fm.</p>`,
        gate: ["Ich bin im Browser bei Last.fm angemeldet"] },
      { title: "API-Konto anlegen", link: ["https://www.last.fm/api/account/create", "API-Konto anlegen"],
        html: `<ol class="wz-list"><li>Bei <b>„Contact email“</b> deine E-Mail-Adresse eintragen, die Felder unten <b>einzeln kopieren</b> und einfügen.</li>
          <li>Bei <b>„Callback URL“</b> genau diese Adresse eintragen.</li><li>„Application homepage“ darf leer bleiben.</li>
          <li>Auf <b>„Submit“</b> klicken.</li></ol>`,
        copy: [["Application name", "SH-Tunebridge"], ["Application description", "Genres und Loved Tracks für SH-Tunebridge"], ["Callback URL", LFM_CB]],
        sketch: sketch("last.fm/api/account/create", [`Application name ${fake("SH-Tunebridge")}`, `Callback URL ${fake("http://127.0.0.1:8765/…")}`, hl("Submit")]),
        gate: ["Ich habe auf „Submit“ geklickt und sehe jetzt „API key“ und „Shared secret“"] },
      { title: "Beide Schlüssel kopieren", html: `Last.fm zeigt jetzt zwei Zeilen. <b>Beide</b> einzeln kopieren – nicht vertauschen:
          <ul class="wz-list"><li><b>API key</b> → erstes Feld</li><li><b>Shared secret</b> → zweites Feld</li></ul>
          <p class="muted">Diese Seite findest du später wieder unter last.fm/api/accounts. Die Schlüssel bleiben nur auf diesem Rechner.</p>`,
        sketch: sketch("last.fm/api/account/create", [`API key ${hl("0123abcd…")}`, `Shared secret ${hl("4567ef01…")}`]),
        fields: [{ id: "LASTFM_API_KEY", label: "API key", ph: "32 Zeichen", re: /^[0-9a-f]{32}$/i, err: "Der API key besteht aus 32 Zeichen (Ziffern und a–f)." },
                 { id: "LASTFM_SHARED_SECRET", label: "Shared secret", ph: "32 Zeichen", secret: true, re: /^[0-9a-f]{32}$/i, err: "Das Shared secret besteht aus 32 Zeichen (Ziffern und a–f)." }] },
    ],
    trouble: [
      ["Last.fm meldet einen Fehler mit Token oder Signatur", "Fast immer ist das <b>Shared secret</b> falsch kopiert oder mit dem API key vertauscht. Unter <a href=\"https://www.last.fm/api/accounts\" target=\"_blank\" rel=\"noopener\">last.fm/api/accounts</a> nachsehen und „Einrichtung wiederholen“."],
      ["Nach dem Erlauben passiert nichts", `Prüfe, ob SH-Tunebridge noch läuft. Die Adresse im Browser muss mit <code>${LFM_CB}</code> beginnen.`],
    ],
  },
  deezer: {
    name: "Deezer", needs: "ein Deezer-Konto (auch kostenlos)", time: "ca. 2 Minuten", profile: true,
    why: "Ein richtiger Deezer-Login ist leider nicht möglich: Deezer nimmt seit 2026 keine neuen Entwickler-Apps mehr an. SH-Tunebridge liest deshalb dein <b>öffentliches</b> Deezer-Profil – Lieblingssongs und öffentliche Playlists, ohne Passwort.",
    steps: [
      { title: "Profil öffentlich machen", link: ["https://www.deezer.com/account/settings", "Deezer-Einstellungen öffnen"],
        html: `<ol class="wz-list"><li>Bei Deezer anmelden.</li>
          <li>In den Einstellungen den Bereich zur <b>Privatsphäre</b> öffnen und <b>„Privates Profil“ ausschalten</b> (die Bezeichnung kann je nach Deezer-Version leicht abweichen).</li>
          <li>Playlists, die SH-Tunebridge sehen soll, müssen <b>öffentlich</b> sein (in der Playlist: „Öffentlich“ bzw. Schloss-Symbol aus).</li></ol>
          <p class="muted">Öffentlich heißt: Auch andere könnten dein Profil ansehen. Willst du das nicht, nutze stattdessen „Link einfügen“ für einzelne Playlists.</p>`,
        gate: ["Mein Deezer-Profil ist nicht mehr privat"] },
      { title: "Profil-Link kopieren", link: ["https://www.deezer.com/", "deezer.com öffnen"],
        html: `<ol class="wz-list"><li>Auf deezer.com oben auf dein <b>Profilbild</b> klicken › <b>„Mein Profil“</b> (oder links „Favoriten“).</li>
          <li>Die Adresse oben in der Adresszeile kopieren – sie enthält <code>/profile/</code> und eine Zahl.</li>
          <li>In der Deezer-App: Profil › Teilen › „Link kopieren“ geht auch.</li></ol>`,
        sketch: sketch("deezer.com/de/profile/123456789", [`${hl("deezer.com/de/profile/123456789")} ← diese Adresse kopieren`]),
        fields: [{ id: "DEEZER_PROFILE", label: "Profil-Link", ph: "https://www.deezer.com/de/profile/123456789", re: /(profile|user)\/\d+|^\d{3,}$|deezer\.page\.link|link\.deezer\.com/, err: "Der Link muss /profile/ und eine Zahl enthalten." }] },
    ],
    trouble: [],
  },
};

const IMPORT = {
  spotify: {
    name: "Spotify", wait: "meist 1–5 Tage", accept: ".zip,.json",
    why: "Spotify muss dir eine Kopie deiner Daten geben (DSGVO). Darin stecken alle eigenen Playlists und Lieblingssongs. Kein Premium, keine Entwickler-App.",
    steps: [
      { title: "Daten anfordern", link: ["https://www.spotify.com/de/account/privacy/", "Spotify-Datenschutzseite öffnen"],
        html: "Anmelden und nach unten zu <b>„Daten herunterladen“</b>. Nur <b>„Kontodaten“</b> anhaken – das reicht (der erweiterte Streamingverlauf ist nicht nötig). Auf <b>„Daten anfordern“</b> klicken.",
        sketch: sketch("spotify.com/account/privacy", [`Daten herunterladen`, `☑ ${hl("Kontodaten")}`, `☐ ${fake("Erweiterter Streamingverlauf")}`, hl("Daten anfordern")]) },
      { title: "E-Mail bestätigen", html: "Spotify schickt sofort eine E-Mail. Darin auf den <b>Bestätigungs-Link</b> klicken – sonst wird nichts vorbereitet." },
      { title: "Warten und Datei hier reinziehen", html: "Wenn die Daten fertig sind (meist nach 1–5 Tagen), kommt eine zweite E-Mail. Die Datei <b>my_spotify_data.zip</b> herunterladen und unten hineinziehen. Entpacken ist nicht nötig.", drop: true },
    ],
  },
  youtube: {
    name: "YouTube / YouTube Music", wait: "meist Minuten bis Stunden", accept: ".zip,.csv",
    why: "Google Takeout gibt dir deine YouTube-Playlists und die YouTube-Music-Bibliothek als Datei. Kein Google-Cloud-Projekt nötig.",
    steps: [
      { title: "Takeout öffnen und nur YouTube wählen", link: ["https://takeout.google.com/", "Google Takeout öffnen"],
        html: "Oben auf <b>„Auswahl aufheben“</b>, dann nach unten scrollen und nur <b>„YouTube und YouTube Music“</b> anhaken.",
        sketch: sketch("takeout.google.com", [hl("Auswahl aufheben"), `☐ ${fake("Chrome")}  ☐ ${fake("Drive")} …`, `☑ ${hl("YouTube und YouTube Music")}`]) },
      { title: "Nur Playlists und Musik", html: "Bei YouTube auf <b>„Alle YouTube-Daten einbezogen“</b> klicken › <b>„Auswahl aufheben“</b> › nur <b>„Musikbibliothek“</b> und <b>„Playlists“</b> anhaken › OK.<br><span class=\"muted\">Wichtig: „Videos“ nicht auswählen – sonst wird die Datei riesig.</span>",
        sketch: sketch("takeout.google.com", [`☑ ${hl("Musikbibliothek")}`, `☑ ${hl("Playlists")}`, `☐ ${fake("Videos")} ← nicht auswählen`]) },
      { title: "Export erstellen", html: "Ganz unten <b>„Nächster Schritt“</b> › „Einmal exportieren“, Dateityp <b>.zip</b> › <b>„Export erstellen“</b>." },
      { title: "Datei hier reinziehen", html: "Wenn Google die E-Mail schickt, die ZIP-Datei herunterladen und unten hineinziehen. Für Playlists liefert Google nur Video-Nummern – die Titel fragt SH-Tunebridge dann einzeln bei YouTube ab (offizielles oEmbed, ohne Konto). Das kann bei großen Listen ein paar Minuten dauern.", drop: true },
    ],
  },
  apple: {
    name: "Apple Music", wait: "sofort", accept: ".xml,.txt,.csv,.m3u,.m3u8,.zip",
    why: "Die Musik-App kann deine ganze Mediathek als Datei speichern – mit allen Playlists.",
    steps: [
      { title: "Mediathek exportieren", html: "<b>Mac:</b> Musik-App › Menü <b>„Ablage“</b> › <b>„Mediathek“</b> › <b>„Mediathek exportieren …“</b> › speichern.<br><b>Windows:</b> iTunes › <b>„Datei“</b> › <b>„Mediathek“</b> › <b>„Mediathek exportieren …“</b>.<br><span class=\"muted\">Nur eine Playlist? Rechtsklick auf die Playlist › „Playlist exportieren …“ geht auch.</span>",
        sketch: sketch("Musik › Ablage", [`Ablage › ${hl("Mediathek")} › ${hl("Mediathek exportieren …")}`]) },
      { title: "Datei hier reinziehen", html: "Die gespeicherte <b>.xml</b>-Datei unten hineinziehen.", drop: true },
    ],
  },
  shazam: {
    name: "Shazam", wait: "einige Tage", accept: ".csv",
    why: "Shazam lässt fremde Apps nicht ins Konto – eine Anmeldung hier wäre nur über Umwege möglich, die wir bewusst nicht gehen. Die frühere Seite „Meine Bibliothek“ mit CSV-Download hat Shazam abgeschaltet. Am einfachsten: <b>die Android-App von SH-Tunebridge</b> erkennt ab jetzt selbst und gleicht mit diesem PC ab (Einstellungen › Handy). Ältere CSV-Dateien lassen sich hier weiter laden.",
    steps: [
      { title: "Kopie deiner Daten bei Shazam anfordern", link: ["https://www.shazam.com/privacy", "shazam.com › Datenschutz öffnen"],
        html: "Nach Art. 15/20 DSGVO steht dir eine Kopie deiner Shazams zu. Auf der Datenschutz-Seite von Shazam die Datenauskunft anfordern – mit dem Konto, mit dem die Shazam-App verknüpft ist (Apple-ID oder Google-Konto). Die Antwort dauert meist einige Tage, das Format bestimmt Shazam.<br><span class=\"muted\">Kommt die Datei als CSV, lässt sie sich unten direkt laden. Hast du noch eine alte <b>shazamlibrary.csv</b>, geht die auch.</span>" },
      { title: "Datei hier reinziehen", html: "Die CSV-Datei (z. B. <b>shazamlibrary.csv</b>) unten hineinziehen. Daraus wird die Playlist <b>„Meine Shazams“</b> (neueste zuerst, ohne Doppelte) und – wenn deine Scans über mehrere Jahre gehen – je Jahr eine weitere. Danach kannst du sie sortieren, in eigene Playlists übernehmen oder zu Spotify &amp; Co. übertragen. Neu importieren geht jederzeit.", drop: true },
    ],
  },
};

/* Auswahl: direkt verbinden oder Datei importieren */
function connectService(sid, main) {
  const c = SETUP[sid], im = IMPORT[sid];
  if (c && !im) return setupWizard(sid, main);
  if (im && !c) return importWizard(sid, main);
  modal({
    title: `${c.name} verbinden`, wide: true, cancel: "Abbrechen", confirm: "Weiter",
    body: `<div class="wz-choice">
      <label class="wz-opt"><input type="radio" name="wzc" value="connect" checked><div><b>Direkt verbinden</b>
        <span class="wz-tags"><span class="acc-badge ok">immer aktuell</span><span class="acc-badge">${esc(c.time)} Einrichtung</span><span class="acc-badge warn">braucht ${esc(c.needs)}</span></span>
        <p>${c.why}</p></div></label>
      <label class="wz-opt"><input type="radio" name="wzc" value="import"><div><b>Datenexport importieren</b>
        <span class="wz-tags"><span class="acc-badge ok">einfach</span><span class="acc-badge ok">ohne Premium</span><span class="acc-badge">Wartezeit ${esc(im.wait)}</span></span>
        <p>${im.why} Aktualisiert sich nicht von selbst – neu importieren geht jederzeit.</p></div></label></div>`,
    onConfirm: box => { const v = $("input[name=wzc]:checked", box).value; setTimeout(() => v === "import" ? importWizard(sid, main) : setupWizard(sid, main), 50); },
  });
}

/* Ein Assistent mit Schritten. Weiter/Zurück im selben Fenster; der letzte Schritt speichert. */
function Wizard({ title, intro, steps, finishLabel, onFinish, onRender }) {
  let i = 0;
  const vals = {};
  const draw = box => {
    const s = steps[i];
    $("#wzBody", box).innerHTML = `
      <div class="wz-prog">${steps.map((_, k) => `<span class="${k < i ? "done" : k === i ? "on" : ""}"></span>`).join("")}<em>Schritt ${i + 1} von ${steps.length}</em></div>
      ${i === 0 && intro ? `<p class="wz-intro">${intro}</p>` : ""}
      <h4 class="wz-title">${esc(s.title)}</h4>
      ${s.link ? `<a class="btn btn--sm btn--primary wz-link" href="${esc(s.link[0])}" target="_blank" rel="noopener">${icon("external")}${esc(s.link[1])}</a>` : ""}
      <div class="wz-text">${s.html}</div>
      ${s.copy ? `<div class="wz-copies">${s.copy.map(([l, v]) => `<div class="wz-copyline"><span>${esc(l)}</span><code>${esc(v)}</code><button class="btn btn--sm btn--ghost" data-copy="${esc(v)}">${icon("copy")}Kopieren</button></div>`).join("")}</div>` : ""}
      ${s.after ? `<div class="wz-text">${s.after}</div>` : ""}
      ${s.sketch || ""}
      ${(s.fields || []).map(f => `<label class="wz-field"><span>${esc(f.label)}</span><input class="input" data-f="${f.id}" type="${f.secret ? "password" : "text"}" placeholder="${esc(f.ph)}" autocomplete="off" spellcheck="false" value="${esc(vals[f.id] || "")}"><small class="wz-err hidden"></small></label>`).join("")}
      ${s.drop ? `<div id="wzDrop"></div>` : ""}
      ${(s.gate || []).length ? `<div class="wz-gate">${s.gate.map((g, k) => `<label class="cons-check"><input type="checkbox" data-gate="${k}" ${vals[`gate${i}_${k}`] ? "checked" : ""}><span>${g}</span></label>`).join("")}</div>` : ""}
      ${s.alt ? `<div class="wz-alt">${s.alt[0]} <button class="btn btn--sm btn--ghost" data-alt>${esc(s.alt[1])}</button></div>` : ""}
      ${i > 0 ? `<button class="link-btn wz-back">← Zurück</button>` : ""}`;
    hydrateIcons(box);
    $$("[data-copy]", box).forEach(b => b.onclick = async () => { await Clip.write(b.dataset.copy); b.classList.add("ok"); toast("Kopiert"); });
    const back = $(".wz-back", box); if (back) back.onclick = () => { save(box); i--; draw(box); };
    $$("[data-f]", box).forEach(inp => inp.addEventListener("input", () => { inp.value = inp.value.trim(); }));
    $$("[data-gate]", box).forEach(c => c.onchange = () => { vals[`gate${i}_${c.dataset.gate}`] = c.checked; });
    const alt = $("[data-alt]", box); if (alt) alt.onclick = () => { $("#modal").classList.remove("open"); delete $("#modal").dataset.sticky; setTimeout(s.alt[2], 60); };
    const ok = $("[data-m=ok]"); if (ok) { ok.textContent = i === steps.length - 1 ? (finishLabel || "Fertig") : "Weiter"; ok.classList.toggle("hidden", !!s.drop); }
    onRender?.(box, s);
  };
  const save = box => $$("[data-f]", box).forEach(inp => { vals[inp.dataset.f] = inp.value.trim(); });
  modal({
    title, wide: true, sticky: true, cancel: "Abbrechen", confirm: "Weiter", body: `<div id="wzBody" class="wz"></div>`,
    onConfirm: async box => {
      save(box);
      const s = steps[i];
      let bad = false;
      for (const f of s.fields || []) {
        const v = vals[f.id] || "", errEl = $(`[data-f="${f.id}"]`, box).parentElement.querySelector(".wz-err");
        const okv = f.re.test(v);
        errEl.textContent = okv ? "" : (v ? f.err : "Bitte ausfüllen."); errEl.classList.toggle("hidden", okv); bad ||= !okv;
      }
      if (bad) throw { silent: true };
      if ((s.gate || []).some((_, k) => !vals[`gate${i}_${k}`])) {
        toast("Bitte erst die Punkte abhaken – genau hier hakt es sonst später", "err");
        $(".wz-gate", box)?.classList.add("wz-gate--warn"); throw { silent: true };
      }
      if (i < steps.length - 1) { i++; draw(box); throw { silent: true }; }
      await onFinish(vals);
    },
  });
  draw($("#modalBox"));
}

function setupWizard(sid, main) {
  const c = SETUP[sid];
  Wizard({
    title: `${c.name} einrichten (einmalig)`, steps: c.steps, finishLabel: c.key ? "Speichern" : c.profile ? "Prüfen & speichern" : "Speichern & verbinden",
    intro: `${c.why} <span class="muted">Du brauchst: ${esc(c.needs)} · Dauer: ${esc(c.time)}. Alle Angaben bleiben nur auf diesem Rechner.</span>`,
    onFinish: async vals => {
      if (c.profile) {                       // öffentliches Profil (Deezer): beim Dienst prüfen, dann speichern
        try { await api(`/api/services/${sid}/profile`, { method: "POST", body: { value: vals.DEEZER_PROFILE } }); }
        catch (e) { toast(e.message, "err"); throw { silent: true }; }
        toast(`${c.name}-Profil verknüpft`); setTimeout(route, 200); return;
      }
      const ids = new Set(c.steps.flatMap(st => (st.fields || []).map(f => f.id)));
      for (const [k, v] of Object.entries(vals)) if (v && ids.has(k)) await api("/api/settings", { method: "POST", body: { key: k, value: String(v).trim() } });
      if (c.key) { toast(`${c.name}-Key gespeichert`); setTimeout(route, 200); return; }
      if (c.login) { setTimeout(() => platformLogin({ id: sid, name: c.name }, main), 250); return; }
      const plats = await api("/api/platforms");
      setTimeout(() => platformLogin(plats.find(p => p.id === sid), main), 250);
    },
  });
}

function importWizard(sid, main) {
  const c = IMPORT[sid];
  Wizard({
    title: `${c.name}: Datenexport importieren`, steps: c.steps,
    intro: `${c.why} <span class="muted">Gelesen werden nur Playlist-Namen, Titel, Künstler und Album – der Rest der Datei (z. B. Hörverlauf) wird nicht angefasst, die Datei selbst nicht gespeichert.</span>`,
    onFinish: async () => {},
    onRender: (box, s) => { if (s.drop) dropZone($("#wzDrop", box), sid, c.accept, main); },
  });
}

function dropZone(el, sid, accept, main) {
  el.innerHTML = `<label class="wz-drop" tabindex="0">${icon("upload")}<b>Datei hier hineinziehen</b><span>oder klicken zum Auswählen (${esc(accept)})</span>
    <input type="file" accept="${esc(accept)}" hidden></label><div class="wz-imp hidden"></div>`;
  hydrateIcons(el);
  const zone = $(".wz-drop", el), inp = $("input", el), out = $(".wz-imp", el);
  const go = async f => {
    if (!f) return;
    zone.classList.add("hidden"); out.classList.remove("hidden");
    out.innerHTML = `<div class="login-wait"><span class="upd-dot spin"></span><span id="impState">Lade ${esc(f.name)} …</span></div>`;
    try {
      const r = await fetch(`/api/services/${sid}/import?name=${encodeURIComponent(f.name)}`, { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: f });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || r.statusText);
      let st;
      for (;;) {
        await new Promise(res => setTimeout(res, 700));
        st = await api(`/api/services/import/${j.job}`);
        const lbl = $("#impState"); if (!lbl) return;
        lbl.textContent = st.state === "titles" ? `Hole Titel bei YouTube … ${st.done} / ${st.total}` : "Lese die Datei …";
        if (["done", "error", "cancelled"].includes(st.state)) break;
      }
      if (st.state !== "done") throw new Error(st.error || "Abgebrochen");
      const res = st.result;
      out.innerHTML = `<div class="notice ok">${icon("check")}<div><b>Fertig!</b> ${res.playlists} Playlist${res.playlists === 1 ? "" : "s"}${res.liked ? ` und ${res.liked} Lieblingssong${res.liked === 1 ? "" : "s"}` : ""} – zusammen ${res.songs} Songs.</div></div>`;
      hydrateIcons(out);
      const ok = $("[data-m=ok]"); ok.textContent = "Playlists ansehen"; ok.classList.remove("hidden");
      ok.onclick = () => { $("#modal").classList.remove("open"); SideSvc.loaded = false; location.hash = `#/services?svc=${sid}`; };
    } catch (e) {
      out.innerHTML = `<div class="notice">${icon("info")}<div>${esc(e.message)}</div></div><button class="btn btn--sm btn--ghost wz-again">Andere Datei wählen</button>`;
      hydrateIcons(out);
      $(".wz-again", out).onclick = () => { out.classList.add("hidden"); zone.classList.remove("hidden"); inp.value = ""; };
    }
  };
  inp.onchange = () => go(inp.files[0]);
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", e => { e.preventDefault(); zone.classList.remove("over"); go(e.dataTransfer.files[0]); });
}

/* Hilfe, wenn die Anmeldung nicht zurückkommt (die Fehlermeldung zeigt der Dienst nur in seinem eigenen Fenster) */
function loginTrouble(sid, main) {
  const c = SETUP[sid];
  if (!c?.trouble?.length) return "";
  return `<div class="wz-trouble"><b>Kommt nichts zurück? Steht beim Dienst eine Fehlermeldung?</b>
    ${c.trouble.map(([t, h], k) => `<details ${k === 0 && ["spotify", "soundcloud", "lastfm"].includes(sid) ? "open" : ""}><summary>${esc(t)}</summary><div>${h}</div></details>`).join("")}
    <div class="btn-row"><button class="btn btn--sm btn--ghost" data-redo="${sid}">${icon("key")}Einrichtung wiederholen</button>
    ${IMPORT[sid] ? `<button class="btn btn--sm btn--ghost" data-imp="${sid}">${icon("upload")}Stattdessen Datei importieren</button>` : ""}</div></div>`;
}

async function platformLogin(p, main, write = false) {
  let st;
  const lapi = p.id === "lastfm" ? "/api/lastfm/login" : `/api/platforms/${p.id}/login${write ? "?write=1" : ""}`;
  try { st = await api(lapi, { method: "POST" }); }
  catch (e) {
    if (/Client-ID|Shared secret/.test(e.message) && SETUP[p.id]) return setupWizard(p.id, main);
    if (SETUP[p.id]) return modal({ title: `${p.name}: Anmeldung nicht möglich`, text: e.message, confirm: "Einrichtung wiederholen", cancel: "Schließen",
      onConfirm: () => { setTimeout(() => setupWizard(p.id, main), 60); } });
    return toast(e.message, "err");
  }
  let alive = true;
  modal({
    title: `Mit ${p.name} verbinden`,
    text: st.code ? "Im Browser hat sich die Anmeldeseite geöffnet. Logge dich dort ein und bestätige den Code:"
                  : "Im Browser hat sich die Anmeldeseite geöffnet. Logge dich dort ein und erlaube den Zugriff – danach geht es hier automatisch weiter.",
    body: `${st.code ? `<div class="login-code">${esc(st.code)}</div>` : ""}
      <div class="login-wait"><span class="upd-dot spin"></span><span id="loginState">Warte auf Bestätigung …</span></div>
      <div class="cell-sub" style="white-space:normal">Browser nicht aufgegangen? <a href="${esc(st.url)}" target="_blank" rel="noopener">Anmeldeseite öffnen</a></div>
      <div id="loginHelp"></div>`,
    confirm: "Fertig", cancel: "Abbrechen", wide: !!SETUP[p.id],
    onCancel: () => { alive = false; },
    onConfirm: async () => { alive = false; route(); },
  });
  $("[data-m=ok]").disabled = true;
  const t0 = Date.now();
  while (alive) {
    if (Date.now() - t0 > (["spotify", "soundcloud", "lastfm"].includes(p.id) ? 0 : 20000) && $("#loginHelp") && !$("#loginHelp").innerHTML) {
      $("#loginHelp").innerHTML = loginTrouble(p.id, main); hydrateIcons($("#loginHelp"));
      $$("#loginHelp [data-copy]").forEach(b => b.onclick = async () => { await Clip.write(b.dataset.copy); toast("Kopiert"); });
      $$("#loginHelp [data-redo]").forEach(b => b.onclick = () => { alive = false; setupWizard(p.id, main); });
      $$("#loginHelp [data-imp]").forEach(b => b.onclick = () => { alive = false; importWizard(p.id, main); });
    }
    await new Promise(r => setTimeout(r, 2000));
    if (!alive) break;
    const s = await api(lapi).catch(() => ({}));
    if (s.state === "connected") {
      alive = false; $("#modal").classList.remove("open");
      toast(`${p.name} verbunden`); route(); break;
    }
    if (["failed", "expired"].includes(s.state)) {
      $("#loginState").textContent = s.state === "expired" ? "Code abgelaufen – bitte neu verbinden" : `Fehlgeschlagen: ${s.error || "?"}`;
      $(".login-wait .upd-dot").classList.remove("spin"); $("[data-m=ok]").disabled = false; break;
    }
  }
}

/* Auswahlliste mit eingebauter Suche (lange Playlist-Listen) – Tastatur: ↑ ↓ Enter Esc */
function picker(host, { placeholder = "Playlist wählen", empty = "Keine Playlists", onChange } = {}) {
  const st = { items: [], value: "", open: false, hi: 0, loading: false };
  host.classList.add("pk");
  host.innerHTML = `<button type="button" class="pk-btn"></button>
    <div class="pk-pop hidden"><label class="pk-search">${icon("search")}<input placeholder="Playlist suchen …" autocomplete="off" spellcheck="false"></label>
    <div class="pk-list" role="listbox"></div></div>`;
  const btn = $(".pk-btn", host), pop = $(".pk-pop", host), q = $("input", pop), list = $(".pk-list", pop);
  const cur = () => st.items.find(x => x.id === st.value);
  const drawBtn = () => {
    const it = cur();
    btn.innerHTML = (st.loading ? `<span class="pk-ph">Lade …</span>`
      : it ? `<span class="pk-name">${esc(it.name)}</span>${it.count != null ? `<span class="pk-count">${it.count}</span>` : ""}`
      : `<span class="pk-ph">${esc(st.items.length ? placeholder : empty)}</span>`) + icon("chevron");
    btn.disabled = st.loading || !st.items.length;
    hydrateIcons(btn);
  };
  const hits = () => { const n = q.value.toLowerCase().trim(); return st.items.filter(x => !n || x.name.toLowerCase().includes(n)); };
  const drawList = () => {
    const h = hits(); st.hi = Math.min(st.hi, Math.max(0, h.length - 1));
    list.innerHTML = h.length ? h.map((x, i) => `<button type="button" class="pk-item ${x.id === st.value ? "on" : ""} ${i === st.hi ? "hi" : ""}" data-i="${i}">
      <span class="pk-name">${esc(x.name)}</span>${x.sub ? `<span class="pk-sub">${esc(x.sub)}</span>` : ""}${x.count != null ? `<span class="pk-count">${x.count}</span>` : ""}</button>`).join("")
      : `<div class="pk-none">Keine Treffer</div>`;
    $$(".pk-item", list).forEach(b => b.onclick = () => pick(h[+b.dataset.i]));
    $(".pk-item.hi", list)?.scrollIntoView({ block: "nearest" });
  };
  const outside = e => { if (!host.contains(e.target)) close(); };
  const open = () => {
    st.open = true; pop.classList.remove("hidden"); host.classList.add("open");
    q.value = ""; st.hi = Math.max(0, st.items.findIndex(x => x.id === st.value)); drawList(); q.focus();
    setTimeout(() => document.addEventListener("mousedown", outside), 0);
  };
  const close = () => { st.open = false; pop.classList.add("hidden"); host.classList.remove("open"); document.removeEventListener("mousedown", outside); };
  const pick = it => { if (!it) return; st.value = it.id; close(); drawBtn(); onChange?.(it); };
  btn.onclick = () => st.open ? close() : open();
  q.oninput = () => { st.hi = 0; drawList(); };
  q.onkeydown = e => {
    const h = hits();
    if (e.key === "ArrowDown") { e.preventDefault(); st.hi = Math.min(h.length - 1, st.hi + 1); drawList(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); st.hi = Math.max(0, st.hi - 1); drawList(); }
    else if (e.key === "Enter") { e.preventDefault(); pick(h[st.hi]); }
    else if (e.key === "Escape") { e.preventDefault(); close(); btn.focus(); }
  };
  drawBtn();
  return {
    get value() { return st.value; },
    get item() { return cur(); },
    loading() { st.loading = true; drawBtn(); },
    set(items, value) { st.items = items; st.loading = false; st.value = items.some(x => x.id === value) ? value : (items[0]?.id || ""); drawBtn(); if (st.open) drawList(); },
  };
}

Views.transfer = async (main) => {
  const plats = await api("/api/platforms");
  const conn = plats.filter(p => p.connected);
  const svcs = [{ id: "local", name: "SH-Tunebridge", can_write: true }, ...conn];
  const T = { src: "local", dst: conn[0]?.id || "local", mode: "pl" };
  const badge = id => { if (id === "local") return `<span class="ss-badge" style="--pc:var(--accent)">SH</span>`;
    const [m, c] = svcStyle(id); return `<span class="ss-badge" style="--pc:${c}">${m}</span>`; };
  const chips = (key) => svcs.map(s => `<button type="button" class="tf-svc" data-${key}="${s.id}">${badge(s.id)}<span>${esc(s.name.split(" / ")[0])}</span></button>`).join("");
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Übertragen</h1><p>Playlists und Lieblingssongs zwischen SH-Tunebridge und deinen Diensten mitnehmen.</p></div></div>
    ${conn.length ? "" : `<div class="notice">${icon("info")}<div>Verbinde unten zuerst einen Dienst – dann kannst du z. B. deine einsortierten Songs als Playlist zu TIDAL schicken oder eine TIDAL-Playlist holen und nach Genres aufteilen.</div></div>`}
    <div class="card tf">
      <div class="tf-grid">
        <section class="tf-side">
          <div class="tf-h"><span class="mx-num">1</span>Von</div>
          <div class="tf-svcs">${chips("src")}</div>
          <div class="tf-lbl">Playlist</div>
          <div class="tf-row"><div id="tSrcPick" class="tf-grow"></div>
            <button class="btn btn--ghost tf-view" id="tView" title="Songs ansehen und vorhören">${icon("play")}Ansehen</button></div>
        </section>
        <div class="tf-arrow">${icon("arrow")}</div>
        <section class="tf-side">
          <div class="tf-h"><span class="mx-num">2</span>Nach</div>
          <div class="tf-svcs">${chips("dst")}</div>
          <div id="tTarget"></div>
        </section>
      </div>
      <div class="tf-foot"><div class="tf-sum" id="tSum"></div><button class="btn btn--primary" id="tGo">${icon("transfer")}Übertragen</button></div>
    </div>
    <div id="tJob"></div>
    <div class="section-title">Dienste</div>
    <div class="platforms">${plats.map(p => { const [n, m, c] = PLATFORM_STYLE[p.id] || [p.name, "?", "#888"]; return `
      <div class="card platform ${p.available ? "" : "planned"}"><div class="p-logo" style="--pc:${c}">${m}</div>
        <div><h4>${esc(n)} ${p.connected ? `<span class="acc-badge ok">${icon("check")}Verbunden</span>` : p.available ? "" : `<span class="acc-badge">Geplant</span>`}</h4>
        <p>${p.connected && p.account ? `Angemeldet als <b>${esc(p.account)}</b>` : esc(p.info)}</p>
        ${p.available ? (p.connected ? `<button class="btn btn--sm btn--ghost" data-logout="${p.id}">Trennen</button>` : `<button class="btn btn--sm btn--primary" data-login="${p.id}">${icon("key")}Verbinden</button>`) : ""}</div></div>`; }).join("")}</div>
  </div>`;
  hydrateIcons(main);
  $$("[data-login]").forEach(b => b.onclick = () => platformLogin(plats.find(p => p.id === b.dataset.login), main));
  $$("[data-logout]").forEach(b => b.onclick = () => modal({ title: "Verbindung trennen?", text: "Das gespeicherte Login-Token wird gelöscht.", confirm: "Trennen", danger: true,
    onConfirm: async () => { await api(`/api/platforms/${b.dataset.logout}/logout`, { method: "POST" }); Views.transfer(main); } }));

  const svcName = id => (svcs.find(s => s.id === id)?.name || SVC_NAME(id)).split(" / ")[0];
  const localLists = () => S.playlists.map(p => ({ id: p.name, name: p.name, count: p.count, sub: p.origin === "lokal" ? "" : `Export · ${p.origin}` }));
  const lists = {};                                  // Dienst -> Playlists (einmal pro Seitenaufruf laden)
  const loadLists = async sid => {
    if (sid === "local") return localLists();
    if (!lists[sid]) lists[sid] = api(`/api/platforms/${sid}/playlists`).catch(e => { toast(e.message, "err"); delete lists[sid]; return []; });
    return lists[sid];
  };
  const srcPick = picker($("#tSrcPick"), { onChange: () => { renderTarget(); } });
  let dstPick = null;
  const markChips = () => {
    $$("[data-src]", main).forEach(b => b.classList.toggle("on", b.dataset.src === T.src));
    $$("[data-dst]", main).forEach(b => b.classList.toggle("on", b.dataset.dst === T.dst));
  };
  const summary = () => {
    const box = $("#tSum"), go = $("#tGo"), it = srcPick.item, p = plats.find(x => x.id === T.dst);
    let err = "";
    if (!it) err = "Playlist wählen";
    else if (T.src === T.dst && T.src !== "local") err = "Quelle und Ziel sind derselbe Dienst";
    else if (p && !p.can_write) err = "Erst das Schreibrecht erteilen";
    else if (T.mode === "exist" && !dstPick?.value) err = "Ziel-Playlist wählen";
    else if (T.mode === "pl" && !$("#tName")?.value.trim()) err = "Namen eingeben";
    else if (T.src === "local" && T.dst === "local" && T.mode === "pl" && $("#tName").value.trim() === it.id) err = "Anderen Namen wählen – das ist die Quelle selbst";
    go.disabled = !!err;
    if (err) { box.innerHTML = `<span class="tf-sum-hint">${esc(err)}</span>`; return; }
    const what = `<b>${esc(it.name)}</b>${it.count != null ? ` · ${it.count} Songs` : ""}`;
    const to = T.mode === "like" ? `zu deinen <b>Lieblingssongs</b>` : T.mode === "exist" ? `in <b>${esc(dstPick.item.name)}</b>` : `als neue Playlist <b>${esc($("#tName").value.trim())}</b>`;
    box.innerHTML = `${badge(T.src)}${what}<span class="tf-sum-arrow">${icon("arrow")}</span>${badge(T.dst)}<span>${esc(svcName(T.dst))} ${to}</span>`;
    hydrateIcons(box);
  };
  const renderTarget = async () => {
    const box = $("#tTarget"), p = plats.find(x => x.id === T.dst), toSvc = T.dst !== "local";
    dstPick = null;
    if (toSvc && p && !p.can_write) {
      box.innerHTML = `<div class="t-perm">${icon("key")}<span>${esc(p.name)} ist nur zum Lesen verbunden. Zum Übertragen fragt
        ${T.dst === "youtube" ? "Google" : esc(p.name)} einmal nach dem Recht, Playlists anzulegen.</span>
        <button class="btn btn--sm btn--primary" id="tPerm">Schreibrecht erteilen</button></div>`;
      hydrateIcons(box); $("#tPerm").onclick = () => platformLogin(p, main, true);
      return summary();
    }
    if (!toSvc && T.mode === "like") T.mode = "pl";
    const modes = [["pl", "Neue Playlist"], ["exist", "Bestehende"], ...(toSvc ? [["like", "Lieblingssongs"]] : [])];
    box.innerHTML = `<div class="tf-lbl">Als</div>
      <div class="segmented tf-modes">${modes.map(([k, l]) => `<button type="button" data-mode="${k}" class="${T.mode === k ? "on" : ""}">${l}</button>`).join("")}</div>
      ${T.mode === "pl" ? `<input class="input tf-name" id="tName" maxlength="150" placeholder="Name der neuen Playlist" value="${esc(srcPick.item?.name || "")}">` : ""}
      ${T.mode === "exist" ? `<div id="tDstPick"></div>` : ""}
      ${T.dst === "youtube" ? `<div class="t-hint">YouTube erlaubt eigenen Apps etwa 60–70 Songs pro Tag. Reicht es nicht, morgen „Bestehende“ wählen – Vorhandenes wird übersprungen.</div>` : ""}
      ${T.dst === "soundcloud" ? `<div class="t-hint">SoundCloud legt die Playlist privat an (höchstens 500 Songs).</div>` : ""}`;
    $$("[data-mode]", box).forEach(b => b.onclick = () => { T.mode = b.dataset.mode; renderTarget(); });
    const name = $("#tName"); if (name) name.oninput = summary;
    if (T.mode === "exist") {
      dstPick = picker($("#tDstPick"), { placeholder: "Ziel-Playlist wählen", onChange: summary });
      dstPick.loading(); summary();
      const all = await loadLists(T.dst);
      if (!dstPick || !document.body.contains($("#tDstPick"))) return;
      // eigene Playlists; bei SH-Tunebridge → SH-Tunebridge nicht die Quelle selbst
      const opts = all.filter(x => x.id !== "__liked__" && x.own !== false && !x.sub && !(T.dst === "local" && T.src === "local" && x.id === srcPick.value));
      dstPick.set(opts, (opts.find(x => x.name === srcPick.item?.name) || {}).id);
    }
    summary();
  };
  const setSrc = async sid => {
    T.src = sid; markChips(); srcPick.loading(); summary();
    const l = await loadLists(sid);
    if (T.src !== sid) return;
    srcPick.set(l, srcPick.value); renderTarget();
  };
  $$("[data-src]", main).forEach(b => b.onclick = () => setSrc(b.dataset.src));
  $$("[data-dst]", main).forEach(b => b.onclick = () => { T.dst = b.dataset.dst; markChips(); renderTarget(); });
  $("#tView").onclick = () => srcPick.value && showPlatformPlaylist(T.src, srcPick.value, srcPick.item?.name || "");
  markChips();
  await setSrc("local");
  $("#tGo").onclick = async () => {
    const it = srcPick.item; if (!it) return;
    const body = { src: T.src, src_id: it.id, dst: T.dst, like: T.mode === "like",
      name: T.mode === "exist" ? dstPick.item.name : T.mode === "pl" ? $("#tName").value.trim() : "",
      dst_pid: T.mode === "exist" && T.dst !== "local" ? dstPick.value : "" };
    try { const r = await api("/api/transfer", { method: "POST", body }); Transfer.job = r.job; pollTransfer(main); }
    catch (e) { toast(e.message, "err"); }
  };
  if (Transfer.job) pollTransfer(main);
};

async function showPlatformPlaylist(svc, plid, name) {
  let tracks;
  try {
    tracks = svc === "local" ? (await api(`/api/playlists/${enc(plid)}`)).entries.map(e => e.track)
      : await api(`/api/platforms/${svc}/playlists/${encodeURIComponent(plid)}/tracks`);
  } catch (e) { return toast(e.message, "err"); }
  modal({ title: name, text: `${tracks.length} Songs · Hörproben (30 s) nur, wo der Dienst sie offiziell anbietet – sonst sucht SH-Tunebridge bei Deezer.`,
    wide: true, cancel: null, confirm: "Schließen", onConfirm: () => {},
    body: `<div class="li-list">${tracks.slice(0, 500).map(t => trackLine({ ...t, artists: t.artists || (t.artist ? [t.artist] : []), preview_url: t.preview_url || `deezer:${t.artist || ""}|${t.title}` })).join("") || "<div class='cell-sub'>Leer</div>"}</div>` });
  hydrateIcons($("#modalBox")); Player.sync();
}

/* ---------- Neu von deinen Diensten (automatischer Abgleich) */
const Inbox = {
  timer: null,
  async badge() {
    const s = await api("/api/autosync/status").catch(() => null);
    const el = $("#cntInbox"); if (!el || !s) return;
    el.textContent = s.count || ""; el.classList.toggle("new", !!s.count);
    if (s.running && !this.timer) this.timer = setTimeout(() => { this.timer = null; this.badge(); }, 4000);
  },
};
/* Filter für „Neu für dich“ */
const INBOX_FILTER0 = { q: "", sid: "", source: "", genre: "", status: "", bmin: null, bmax: null, sort: "neu" };
Inbox.filter = { ...INBOX_FILTER0, ...store.get("inboxFilter", {}) };
const inboxFiltered = F => !!(F.q || F.sid || F.source || F.genre || F.status || F.bmin != null || F.bmax != null);
function inboxApply(items, F) {
  const q = (F.q || "").toLowerCase().trim();
  const out = items.filter(it => (!q || `${it.title} ${(it.artists || []).join(" ")} ${it.album || ""}`.toLowerCase().includes(q))
    && (!F.sid || it.sid === F.sid) && (!F.source || it.source === F.source)
    && (!F.genre || (F.genre === "?" ? !it.genre : it.genre === F.genre))
    && (!F.status || (F.status === "auto" ? !!it.auto : !it.auto))
    && (F.bmin == null || (it.bpm && it.bpm >= F.bmin)) && (F.bmax == null || (it.bpm && it.bpm <= F.bmax)));
  const by = { neu: (a, b) => b.ts - a.ts, alt: (a, b) => a.ts - b.ts,
    kuenstler: (a, b) => ((a.artists || [])[0] || "").localeCompare((b.artists || [])[0] || "", "de"),
    titel: (a, b) => (a.title || "").localeCompare(b.title || "", "de"),
    bpm: (a, b) => (a.bpm || 999) - (b.bpm || 999), genre: (a, b) => (a.genre || "~").localeCompare(b.genre || "~", "de") }[F.sort] || null;
  return by ? out.sort(by) : out;
}
function inboxFilterBar(items) {
  const F = Inbox.filter, uniq = k => [...new Set(items.map(it => it[k]).filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b), "de"));
  const opt = (k, v, label) => `<option value="${esc(v)}" ${F[k] === v ? "selected" : ""}>${esc(label)}</option>`;
  const svcs = [...new Map(items.map(it => [it.sid, it.service])).entries()];
  return `<div class="card ib-filter">
    <input class="input" data-f="q" placeholder="Suchen: Titel, Künstler, Album …" value="${esc(F.q)}">
    <select class="select select--sm" data-f="sid">${opt("sid", "", "Alle Dienste")}${svcs.map(([k, v]) => opt("sid", k, v)).join("")}</select>
    <select class="select select--sm" data-f="source">${opt("source", "", "Alle Quellen")}${uniq("source").map(v => opt("source", v, v)).join("")}</select>
    <select class="select select--sm" data-f="genre">${opt("genre", "", "Alle Genres")}${uniq("genre").map(v => opt("genre", v, v)).join("")}${items.some(it => !it.genre) ? opt("genre", "?", "Genre unbekannt") : ""}</select>
    <select class="select select--sm" data-f="status">${opt("status", "", "Jeder Status")}${opt("status", "offen", "Noch offen")}${opt("status", "auto", "Automatisch einsortiert")}</select>
    <span class="ib-bpm">BPM <input class="input num" type="number" min="40" max="250" data-f="bmin" value="${F.bmin ?? ""}" placeholder="von"> – <input class="input num" type="number" min="40" max="250" data-f="bmax" value="${F.bmax ?? ""}" placeholder="bis"></span>
    <select class="select select--sm" data-f="sort" title="Sortierung">${opt("sort", "neu", "Neueste zuerst")}${opt("sort", "alt", "Älteste zuerst")}${opt("sort", "kuenstler", "Künstler A–Z")}${opt("sort", "titel", "Titel A–Z")}${opt("sort", "bpm", "Tempo (BPM)")}${opt("sort", "genre", "Genre")}</select>
    <button class="btn btn--sm btn--ghost" id="ibReset" title="Alle Filter zurücksetzen">${icon("x")}Zurücksetzen</button>
  </div>`;
}
const ago = ts => { const m = Math.round((Date.now() / 1000 - ts) / 60); return m < 1 ? "gerade eben" : m < 60 ? `vor ${m} min` : m < 1440 ? `vor ${Math.round(m / 60)} h` : `vor ${Math.round(m / 1440)} Tagen`; };

Views.inbox = async (main) => {
  main.innerHTML = `<div class="page view-enter">${skeletonRows(4)}</div>`;
  const d = await api("/api/autosync");
  const cfg = d.settings, items = d.items || [];
  const errs = Object.entries(d.errors || {});
  const row = it => {
    const t = { ...it, preview_url: it.preview_url || `deezer:${(it.artists || []).join(", ")}|${it.title}` };
    const sug = (it.suggestions || []).map(s => `<button class="btn btn--sm ${s.new ? "btn--ghost" : ""}" data-add="${esc(it.id)}" data-pl="${esc(s.playlist)}" title="${esc(s.reason || "")}">${icon(s.new ? "plus" : "stack")}${esc(s.playlist)}${s.new ? " (neu)" : ` · ${Math.round(s.score * 100)} %`}</button>`).join("");
    const [m, c] = SVC_STYLE[it.sid] || ["?", "#888"];
    return `<div class="ib-row" data-id="${esc(it.id)}">${trackLine(t)}
      <div class="ib-meta"><span class="ss-badge sm" style="--pc:${c}">${m}</span><span>${esc(it.service)} · ${esc(it.source || "")} · ${ago(it.ts)}${it.bpm ? ` · ${Math.round(it.bpm)} BPM` : ""}</span></div>
      ${it.auto ? `<div class="ib-auto">${icon("check")}<span>Automatisch in <b>${esc(it.auto.playlist)}</b> einsortiert · ${Math.round(it.auto.score * 100)} %${it.auto.reason ? ` · ${esc(it.auto.reason)}` : ""}</span>
        <button class="btn btn--sm btn--primary" data-done="${esc(it.id)}">${icon("check")}Passt</button>
        <button class="btn btn--sm btn--ghost" data-undo="${esc(it.id)}" title="Wieder aus der Playlist nehmen und selbst entscheiden">Rückgängig</button></div>`
      : `<div class="ib-act">${sug}<button class="btn btn--sm btn--ghost" data-other="${esc(it.id)}">${icon("pencil")}Andere Playlist</button>
        <button class="btn btn--sm btn--ghost" data-done="${esc(it.id)}" title="Aus der Liste nehmen">${icon("check")}Erledigt</button></div>`}</div>`;
  };
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Neu von deinen Diensten</h1><p>SH-Tunebridge schaut regelmäßig in deine verbundenen Dienste (Lieblingssongs${cfg.lists ? " und Playlists" : ""}). Neue Songs werden analysiert und bekommen Vorschläge, in welche deiner Playlists sie passen. Alles bleibt auf diesem Rechner.</p></div></div>
    <div class="card ib-bar">
      <label class="switch-row"><input type="checkbox" id="ibOn" ${cfg.enabled ? "checked" : ""}><span>Automatisch abgleichen</span></label>
      <label class="switch-row">alle <select class="select select--sm" id="ibInt">${[1, 3, 6, 12, 24, 48].map(h => `<option value="${h}" ${cfg.interval_h === h ? "selected" : ""}>${h} h</option>`).join("")}</select></label>
      <label class="switch-row"><input type="checkbox" id="ibLists" ${cfg.lists ? "checked" : ""}><span>Auch Playlists (nicht nur Likes)</span></label>
      <label class="switch-row" title="Neue Songs landen selbst in deiner am besten passenden Playlist – du kannst jeden Eintrag rückgängig machen"><input type="checkbox" id="ibAuto" ${cfg.auto_sort ? "checked" : ""}><span>Automatisch einsortieren ab</span>
        <select class="select select--sm" id="ibMin" ${cfg.auto_sort ? "" : "disabled"}>${[50, 60, 70, 80, 90].map(p => `<option value="${p}" ${cfg.auto_min === p ? "selected" : ""}>${p} %</option>`).join("")}</select></label>
      <span class="cell-sub grow">${d.running ? `<span class="upd-dot spin"></span> ${esc(d.phase || "Läuft …")}` : cfg.last_run ? `Zuletzt ${ago(cfg.last_run)}${d.next_run ? ` · nächster Abgleich ${new Date(d.next_run * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}` : ""}` : "Noch nie abgeglichen"}</span>
      <button class="btn btn--sm btn--primary" id="ibRun" ${d.running ? "disabled" : ""}>${icon("repeat")}Jetzt abgleichen</button>
      <button class="btn btn--sm btn--ghost" id="ibMore" title="Mehr">${icon("sliders")}</button>
    </div>
    ${errs.length ? `<div class="notice">${icon("info")}<div>${errs.map(([k, v]) => `<b>${esc(SVC_NAME(k))}:</b> ${esc(v)}`).join("<br>")}</div></div>` : ""}
    ${items.length ? `${inboxFilterBar(items)}<div class="ib-head"><span id="ibCount"></span><button class="btn btn--sm btn--ghost" id="ibClear">Alle erledigt</button></div><div class="ib-list" id="ibList"></div>`
      : `<div class="empty">${icon("inbox")}<h3>Nichts Neues</h3><p>${cfg.last_run ? "Seit dem letzten Abgleich ist in deinen Diensten nichts dazugekommen." : "Beim ersten Abgleich merkt sich SH-Tunebridge nur, was schon da ist – ab dann erscheinen hier neue Songs."}<br><a href="#/services">Dienste verbinden</a></p></div>`}
  </div>`;
  hydrateIcons(main);
  const save = async patch => { await api("/api/autosync", { method: "POST", body: patch }).catch(e => toast(e.message, "err")); };
  $("#ibOn").onchange = e => save({ enabled: e.target.checked });
  $("#ibInt").onchange = e => save({ interval_h: +e.target.value });
  $("#ibLists").onchange = e => save({ lists: e.target.checked });
  $("#ibAuto").onchange = e => { save({ auto_sort: e.target.checked }); $("#ibMin").disabled = !e.target.checked;
    if (e.target.checked) toast("Ab dem nächsten Abgleich: sichere Treffer landen selbst in der Playlist – hier siehst du sie mit „Rückgängig“"); };
  $("#ibMin").onchange = e => save({ auto_min: +e.target.value });
  $("#ibRun").onclick = async () => { await api("/api/autosync/run", { method: "POST" }); toast("Abgleich läuft …"); setTimeout(() => route(), 600); Inbox.badge(); };
  $("#ibMore").onclick = () => modal({ title: "Abgleich zurücksetzen?", text: "SH-Tunebridge vergisst, welche Songs es schon gesehen hat, und leert diese Liste. Der nächste Abgleich merkt sich nur wieder den Ist-Stand.", confirm: "Zurücksetzen", danger: true,
    onConfirm: async () => { await api("/api/autosync/reset", { method: "POST" }); Inbox.badge(); route(); } });
  // Filter (nur in der Ansicht, gemerkt pro Rechner)
  let shown = items;
  const F = Inbox.filter;
  const draw = () => {
    const list = $("#ibList", main); if (!list) return;
    shown = inboxApply(items, F);
    list.innerHTML = shown.length ? shown.map(row).join("") : `<div class="cell-sub" style="padding:14px">Kein Song passt zum Filter.</div>`;
    $("#ibCount", main).textContent = inboxFiltered(F) ? `${shown.length} von ${items.length} neuen Songs` : `${items.length} neue Songs`;
    $("#ibClear", main).textContent = inboxFiltered(F) ? `${shown.length} gefilterte erledigt` : "Alle erledigt";
    $("#ibClear", main).disabled = !shown.length;
    hydrateIcons(list); bindRows(); Player.sync();
  };
  $$("[data-f]", main).forEach(el => el[el.tagName === "SELECT" ? "onchange" : "oninput"] = () => {
    F[el.dataset.f] = el.type === "number" ? (el.value === "" ? null : +el.value) : el.value;
    store.set("inboxFilter", F); draw();
  });
  const fr = $("#ibReset", main);
  if (fr) fr.onclick = () => { Object.assign(F, INBOX_FILTER0); store.set("inboxFilter", F); route(); };
  const clr = $("#ibClear"); if (clr) clr.onclick = async () => {
    if (!inboxFiltered(F)) { await api("/api/autosync/inbox/clear", { method: "POST" }); Inbox.badge(); return route(); }
    for (const it of shown) await api(`/api/autosync/inbox/${it.id}/done`, { method: "POST" }).catch(() => null);
    toast(`${shown.length} Songs erledigt`); Inbox.badge(); route();
  };
  const gone = id => { const i = items.findIndex(x => x.id === id); if (i >= 0) items.splice(i, 1); Inbox.badge(); if (!items.length) return route(); draw(); };
  const add = async (id, pl) => {
    try { const r = await api(`/api/autosync/inbox/${id}/add`, { method: "POST", body: { playlist: pl } }); toast(r.added ? `In „${pl}“ einsortiert` : `War schon in „${pl}“`); gone(id); refreshMeta(); }
    catch (e) { toast(e.message, "err"); }
  };
  const bindRows = () => {
  $$("[data-add]", main).forEach(b => b.onclick = () => add(b.dataset.add, b.dataset.pl));
  $$("[data-undo]", main).forEach(b => b.onclick = async () => {
    try { const r = await api(`/api/autosync/inbox/${b.dataset.undo}/undo`, { method: "POST" }); toast(`Aus „${r.playlist}“ genommen – entscheide selbst`); refreshMeta(); route(); }
    catch (e) { toast(e.message, "err"); }
  });
  $$("[data-done]", main).forEach(b => b.onclick = async () => { await api(`/api/autosync/inbox/${b.dataset.done}/done`, { method: "POST" }); gone(b.dataset.done); });
  $$("[data-other]", main).forEach(b => b.onclick = () => modal({ title: "In welche Playlist?", body: `<input class="input" id="ibPl" list="plnames" placeholder="Name einer Playlist (neu oder vorhanden)" style="width:100%" autocomplete="off">`, confirm: "Einsortieren",
    onConfirm: async box => { const v = $("#ibPl", box).value.trim(); if (!v) { toast("Bitte einen Namen eingeben", "err"); throw { silent: true }; } await add(b.dataset.other, v); } }));
  };
  draw();
  if (d.running) setTimeout(() => location.hash.startsWith("#/inbox") && route(), 3000);
};

/* ---------- Genre-Datenbank: eigene Einordnungen (wirken sofort) + Gemeinschafts-Datenbank (mit Einwilligung) */
const GDB_SRC = { playlist: "Playlist-Name", app: "App", ki: "KI", korrektur: "von dir geändert" };
const GDB_STATUS = { ok: ["passt", "ok"], pruefen: ["bitte prüfen", "warn"], offen: ["unbekannt", ""], eingeordnet: ["eingeordnet", "own"] };
const GenreDB = {
  tax: null, job: null, filter: "pruefen",
  async taxonomy() { if (!this.tax) this.tax = (await api("/api/genredb")).taxonomy; return this.tax; },
  genreSel(g, attrs = "") {
    return `<select class="select select--sm" data-g ${attrs}><option value="">– Genre –</option>${Object.keys(this.tax).map(x => `<option ${x === g ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>`;
  },
  subSel(g, sub, attrs = "") {
    return `<select class="select select--sm" data-s ${attrs}><option value="">– kein Subgenre –</option>${(this.tax[g] || []).map(x => `<option ${x === sub ? "selected" : ""}>${esc(x)}</option>`).join("")}</select>`;
  },
  async pick(g, sub, label, save) {
    await this.taxonomy();
    modal({ title: "Genre festlegen", text: label,
      body: `<div class="gdb-pick">${this.genreSel(g)}${this.subSel(g, sub)}</div>
        <div class="hint" style="margin-top:10px">Gilt sofort für diesen Song – auch beim nächsten Erkennen – und geht allem anderen vor.
        Wenn du „Zur Gemeinschafts-Datenbank beitragen“ erlaubt hast, fließt es anonym mit ein.</div>`,
      confirm: "Speichern",
      onConfirm: async box => {
        const gv = $("[data-g]", box).value; if (!gv) { toast("Bitte ein Genre wählen", "err"); throw { silent: true }; }
        await save(gv, $("[data-s]", box).value || null);
      } });
    const box = $("#modal");
    $("[data-g]", box).onchange = e => { $("[data-s]", box).outerHTML = this.subSel(e.target.value, null); };
  },
};

Views.genredb = async (main) => {
  main.innerHTML = `<div class="page view-enter">${skeletonRows(4)}</div>`;
  const [d, svcs] = await Promise.all([api("/api/genredb"), api("/api/services").catch(() => [])]);
  GenreDB.tax = d.taxonomy;
  const srcs = [["local", "SH-Tunebridge (lokal)"], ...svcs.filter(s => s.ready && s.id !== "local").map(s => [s.id, s.name])];
  const c = d.counts, cm = d.community || {};
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Genre-Datenbank</h1><p>Lass deine Playlists einordnen und bestätige oder korrigiere die Vorschläge. Deine Einordnungen gelten sofort für die Erkennung –
      und fließen auf Wunsch anonym in die Gemeinschafts-Datenbank ein, von der alle profitieren.</p></div></div>
    <div class="gdb-stats">
      <div class="card gdb-stat"><b>${c.total}</b><span>eigene Einordnungen${c.total ? ` · ${c.sent} beigetragen` : ""}</span></div>
      <div class="card gdb-stat"><b>${cm.songs ?? "–"}</b><span>${cm.songs != null ? `Songs in der Gemeinschafts-Datenbank · Stand ${esc(cm.created || "?")}` : d.consent.genredb ? "Gemeinschafts-Datenbank noch nicht geladen" : "Gemeinschafts-Datenbank nicht aktiviert"}</span></div>
      <div class="card gdb-stat gdb-consent">
        <div>${icon(d.consent.genres ? "check" : "x")} Beitragen: <b>${d.consent.genres ? "an" : "aus"}</b></div>
        <div>${icon(d.consent.genredb ? "check" : "x")} Gemeinschafts-DB nutzen: <b>${d.consent.genredb ? "an" : "aus"}</b></div>
        <div style="display:flex;gap:6px;margin-top:6px"><button class="btn btn--sm btn--ghost" id="gdbConsent">Einstellen</button>
          ${d.consent.genredb ? `<button class="btn btn--sm btn--ghost" id="gdbUpd">${icon("repeat")}Jetzt laden</button>` : ""}</div>
      </div>
    </div>
    <div class="section-title">Playlist analysieren</div>
    <div class="card gdb-form">
      <div class="field"><label>Quelle</label><select class="select" id="gdbSrc">${srcs.map(([v, n]) => `<option value="${v}">${esc(n)}</option>`).join("")}</select></div>
      <div class="field grow"><label>Playlist</label><select class="select" id="gdbPl"><option>Lade …</option></select></div>
      <label class="switch-row" title="${d.ai_ready ? "Die KI sieht nur Künstler, Titel, Album und Tempo – keine Tags oder Genres der Dienste" : "Erst unter Einstellungen › KI eine KI einrichten"}"><input type="checkbox" id="gdbAi" ${d.ai_ready ? "" : "disabled"}><span>KI mitentscheiden lassen</span></label>
      <button class="btn btn--primary" id="gdbGo">${icon("sparkle")}Analysieren</button>
    </div>
    <div class="hint gdb-note">${icon("info")}<span>Ausgewertet wird lokal: das Ergebnis der App, der <b>Name der Playlist</b> (z. B. „Hardtekk 2024“ → Hardtekk – der Name selbst verlässt nie deinen Rechner)
      und auf Wunsch eine KI, die <b>nur Künstler, Titel, Album und Tempo</b> sieht. Gespeichert wird erst, was du übernimmst.</span></div>
    <div id="gdbJob"></div>
    <div class="section-title">Deine Einordnungen <span class="cell-sub">${c.total}</span></div>
    <div id="gdbVotes">${d.votes.length ? `<div class="card gdb-votes">${d.votes.map(v => `<div class="gdb-vote" data-k="${esc(v.key)}">
        <div style="min-width:0"><div class="li-title">${esc(v.title)}</div><div class="cell-sub">${esc(v.artist)}</div></div>
        <div>${genreChip(v.genre, v.subgenre)}</div><span class="cell-sub">${esc(GDB_SRC[v.source] || v.source)}${v.sent ? " · beigetragen" : ""}</span>
        <button class="icon-btn" data-del="${esc(v.key)}" title="Einordnung löschen">${icon("x")}</button></div>`).join("")}
      </div><div style="display:flex;justify-content:flex-end;margin-top:8px"><button class="btn btn--sm btn--ghost" id="gdbDelAll">Alle eigenen Einordnungen löschen</button></div>`
      : `<div class="empty">${icon("stack")}<h3>Noch keine</h3><p>Analysiere eine Playlist oder lege im Song-Detail über „Genre festlegen“ ein Genre fest.</p></div>`}</div>
  </div>`;
  hydrateIcons(main);
  const loadPl = async () => {
    const sid = $("#gdbSrc").value, sel = $("#gdbPl");
    sel.innerHTML = `<option>Lade …</option>`;
    try {
      const list = sid === "local" ? (await api("/api/playlists")).filter(p => p.origin === "lokal").map(p => ({ id: p.name, name: p.name, count: p.count }))
        : await api(`/api/services/${sid}/playlists`);
      sel.innerHTML = list.length ? list.map(p => `<option value="${esc(p.id)}">${esc(p.name)}${p.count != null ? ` (${p.count})` : ""}</option>`).join("") : `<option value="">– keine Playlists –</option>`;
    } catch (e) { sel.innerHTML = `<option value="">${esc(e.message)}</option>`; }
  };
  $("#gdbSrc").onchange = loadPl; loadPl();
  $("#gdbGo").onclick = async () => {
    const pid = $("#gdbPl").value; if (!pid) return toast("Bitte eine Playlist wählen", "err");
    try {
      const r = await api("/api/genredb/analyze", { method: "POST", body: { sid: $("#gdbSrc").value, pid, ai: $("#gdbAi").checked } });
      GenreDB.job = r.job; GenreDB.filter = "pruefen"; pollGdb();
    } catch (e) { toast(e.message, "err"); }
  };
  $("#gdbConsent").onclick = () => Consent.dialog(false);
  const upd = $("#gdbUpd"); if (upd) upd.onclick = async () => {
    try { const r = await api("/api/genredb/update", { method: "POST" }); toast(r.updated ? `Geladen: ${r.songs} Songs` : r.none ? "Noch keine Gemeinschafts-Datenbank veröffentlicht" : "Schon aktuell"); route(); }
    catch (e) { toast(e.message, "err"); }
  };
  $$("[data-del]", main).forEach(b => b.onclick = async () => { await api("/api/genredb/votes/delete", { method: "POST", body: { keys: [b.dataset.del] } }); b.closest(".gdb-vote").remove(); });
  const da = $("#gdbDelAll"); if (da) da.onclick = () => modal({ title: "Alle eigenen Einordnungen löschen?", text: "Die Erkennung nutzt danach wieder nur ihre automatischen Ergebnisse. Bereits Beigetragenes löschst du unter Einstellungen › Nicht erkannt („Alles von mir dort löschen“).",
    confirm: "Löschen", danger: true, onConfirm: async () => { await api("/api/genredb/votes/delete", { method: "POST", body: { all: true } }); route(); } });
  if (GenreDB.job) pollGdb();
};

async function pollGdb() {
  const box = $("#gdbJob"); if (!box || !GenreDB.job) return;
  const j = await api(`/api/genredb/job/${GenreDB.job}`).catch(() => null);
  if (!j) { GenreDB.job = null; box.innerHTML = ""; return; }
  const running = !["done", "error", "cancelled"].includes(j.state);
  if (running) {
    const pct = j.total ? Math.round(j.done / j.total * 100) : 0;
    box.innerHTML = `<div class="card t-job"><div class="t-job-head"><b>${esc(j.name || "Playlist")}</b><button class="btn btn--sm btn--ghost" id="gdbCancel">Abbrechen</button></div>
      <div class="llm-bar"><div style="width:${j.state === "ai" ? 100 : pct}%"></div></div>
      <div class="llm-job">${j.state === "loading" ? "Lade Songs …" : j.state === "ai" ? "KI schätzt ein (nur Künstler/Titel/Album/Tempo) …" : `Analysiere ${j.done} / ${j.total} …`}</div></div>`;
    $("#gdbCancel").onclick = () => api(`/api/genredb/job/${j.id}/cancel`, { method: "POST" });
    return setTimeout(pollGdb, 800);
  }
  if (j.state !== "done") { box.innerHTML = `<div class="notice">${icon("info")}<div>${j.state === "error" ? esc(j.error) : "Abgebrochen"}</div></div>`; GenreDB.job = null; return; }
  renderGdb(box, j);
}

function renderGdb(box, j) {
  const cnt = s => j.items.filter(i => i.status === s).length;
  const f = GenreDB.filter;
  const rows = j.items.filter(i => f === "alle" || i.status === f);
  const [pg, ps] = j.playlist_genre || [];
  const cell = (g, s) => g ? genreChip(g, s) : `<span class="cell-sub">–</span>`;
  box.innerHTML = `<div class="card gdb-res">
    <div class="t-job-head"><b>${esc(j.name)}</b><span class="cell-sub">${j.items.length} Songs${j.cut ? ` (erste ${j.items.length})` : ""} · Playlist-Name ${pg ? `→ ${esc(ps || pg)}` : "nennt kein eindeutiges Genre"}${j.ai_error ? ` · KI: ${esc(j.ai_error)}` : ""}</span>
      <button class="btn btn--sm btn--ghost" id="gdbClose">${icon("x")}</button></div>
    <div class="filter-chips" id="gdbF">${[["pruefen", "Bitte prüfen"], ["ok", "Passt"], ["offen", "Unbekannt"], ["eingeordnet", "Schon eingeordnet"], ["alle", "Alle"]]
      .map(([k, n]) => `<button data-f="${k}" class="${f === k ? "on" : ""}">${n} <em>${k === "alle" ? j.items.length : cnt(k)}</em></button>`).join("")}</div>
    <div class="gdb-table">
      <div class="gdb-row head"><div>Song</div><div>App</div><div>Playlist</div><div>KI</div><div>Ergebnis</div><div></div></div>
      ${rows.map(it => `<div class="gdb-row" data-i="${it.i}">
        <div class="gdb-song">${it.cover ? `<img class="li-cover" src="${esc(it.cover)}" alt="" loading="lazy">` : `<div class="li-cover"></div>`}
          <div style="min-width:0"><div class="li-title">${esc(it.title)}</div><div class="cell-sub">${esc((it.artists || []).join(", "))}</div></div></div>
        <div>${cell(it.app_genre, it.app_subgenre)}</div><div>${cell(it.pl_genre, it.pl_subgenre)}</div><div>${cell(it.ki?.genre, it.ki?.subgenre)}</div>
        <div class="gdb-pick">${GenreDB.genreSel(it.genre)}${GenreDB.subSel(it.genre, it.subgenre)}</div>
        <div class="gdb-act"><span class="acc-badge ${GDB_STATUS[it.status][1]}">${GDB_STATUS[it.status][0]}</span>
          ${it.status !== "eingeordnet" ? `<button class="icon-btn" data-ok="${it.i}" title="Übernehmen">${icon("check")}</button>` : ""}</div>
      </div>`).join("") || `<div class="cell-sub" style="padding:14px">Keine Songs in dieser Ansicht.</div>`}
    </div>
    <div class="gdb-foot"><span class="cell-sub grow">Übernommen wird, was in „Ergebnis“ steht. Änderst du etwas, zählt es als deine Korrektur.</span>
      <button class="btn btn--sm" id="gdbTakeOk">${icon("check")}Alle „Passt“ übernehmen (${cnt("ok")})</button>
      <button class="btn btn--sm btn--primary" id="gdbTakeView">Alle in dieser Ansicht übernehmen</button></div>
  </div>`;
  hydrateIcons(box);
  const val = row => ({ i: +row.dataset.i, genre: $("[data-g]", row).value, subgenre: $("[data-s]", row).value || null });
  const take = async list => {
    list = list.filter(x => x.genre);
    if (!list.length) return toast("Nichts zum Übernehmen – erst ein Genre wählen", "err");
    try { const r = await api(`/api/genredb/job/${j.id}/accept`, { method: "POST", body: { rows: list } }); toast(`${r.saved} Einordnungen gespeichert`); }
    catch (e) { return toast(e.message, "err"); }
    const nj = await api(`/api/genredb/job/${j.id}`); renderGdb(box, nj);
  };
  $$("[data-g]", box).forEach(sel => sel.onchange = () => { $("[data-s]", sel.parentElement).outerHTML = GenreDB.subSel(sel.value, null); });
  $$("[data-ok]", box).forEach(b => b.onclick = () => take([val(b.closest(".gdb-row"))]));
  $("#gdbTakeOk").onclick = () => take(j.items.filter(i => i.status === "ok").map(i => ({ i: i.i, genre: i.genre, subgenre: i.subgenre })));
  $("#gdbTakeView").onclick = () => take($$(".gdb-row[data-i]", box).filter(r => !$(".acc-badge.own", r)).map(val));
  $$("#gdbF button", box).forEach(b => b.onclick = () => { GenreDB.filter = b.dataset.f; renderGdb(box, j); });
  $("#gdbClose").onclick = () => { GenreDB.job = null; box.innerHTML = ""; route(); };
}

function trackLine(t, extra = "") {
  const g = t.genre ? genreChip(t.genre, t.subgenre) : "";
  return `<div class="li-row">${extra}
    <button class="icon-btn" ${playAttr(t)} title="Reinhören">${icon("play")}</button>
    ${t.cover ? `<img class="li-cover" src="${esc(t.cover)}" alt="" loading="lazy">` : `<div class="li-cover"></div>`}
    <div style="min-width:0"><div class="li-title">${esc(t.title)}</div><div class="cell-sub">${esc((t.artists || []).join(", ") || t.artist || "")}</div></div>
    <div class="li-genre">${g}${t.niche ? `<span class="cell-sub"> ${esc(t.niche)}</span>` : ""}</div></div>`;
}

async function pollTransfer(main) {
  const box = $("#tJob");
  if (!box || !Transfer.job) return;
  const j = await api(`/api/transfer/${Transfer.job}`).catch(() => null);
  if (!j) return;
  const pct = j.total ? Math.round(j.done / j.total * 100) : 0;
  const label = { queued: "Startet …", loading: `Lade Songs aus ${SVC_NAME(j.src)} …`, matching: `Suche Songs auf ${SVC_NAME(j.dst)} … ${j.done} / ${j.total}`,
    adding: `Füge zu ${SVC_NAME(j.dst)} hinzu …`, done: "Fertig", error: `Fehler: ${j.error}`, cancelled: "Abgebrochen" }[j.state] || j.state;
  const running = !["done", "error", "cancelled"].includes(j.state);
  box.innerHTML = `<div class="card t-job">
    <div class="t-job-head"><b>${esc(j.like ? "Lieblingssongs" : j.name)}</b><span class="cell-sub">${esc(SVC_NAME(j.src))} → ${esc(SVC_NAME(j.dst))}</span>
      ${running ? `<button class="btn btn--sm btn--ghost" id="tCancel">Abbrechen</button>` : `<button class="btn btn--sm btn--ghost" id="tClose">${icon("x")}</button>`}</div>
    <div class="llm-bar"><div style="width:${j.state === "done" ? 100 : pct}%"></div></div>
    <div class="llm-job ${j.state === "error" ? "err" : ""}">${esc(label)}</div>
    ${j.state === "done" ? `<div class="t-result"><span class="acc-badge ok">${icon("check")}${j.added != null ? `${j.added} neu hinzugefügt${j.found - j.added ? ` · ${j.found - j.added} schon drin` : ""}` : `${j.found} von ${j.total} übertragen`}</span>
      ${j.url ? `<a class="btn btn--sm" href="${esc(j.url)}" target="_blank" rel="noopener">${icon("external")}In ${esc(SVC_NAME(j.dst))} öffnen</a>` : ""}
      ${j.dst === "local" ? `<a class="btn btn--sm" href="#/playlists/${encodeURIComponent(j.name)}">Playlist ansehen</a>` : ""}</div>
      ${j.stopped ? `<div class="t-hint warn">${icon("info")}Vorzeitig gestoppt: ${esc(j.stopped)}</div>` : ""}
      ${j.missing?.length ? `<details class="t-missing"><summary>${j.missing.length} nicht gefunden</summary>${j.missing.map(m => `<div>${esc(m.artist)} – ${esc(m.title)}</div>`).join("")}</details>` : ""}` : ""}
  </div>`;
  const c = $("#tCancel"); if (c) c.onclick = () => api(`/api/transfer/${j.id}/cancel`, { method: "POST" });
  const x = $("#tClose"); if (x) x.onclick = () => { Transfer.job = null; box.innerHTML = ""; };
  if (j.state === "done" && j.dst === "local") refreshMeta();
  if (running) setTimeout(() => pollTransfer(main), 700);
}

/* ---------- Sicherung */
const fmtSize = b => b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
const fmtDate = ts => new Date(ts * 1000).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
const KIND = { manuell: ["Manuell", "manual", "archive"], auto: ["Automatisch", "auto", "repeat"], "vor-wiederherstellung": ["Vor Wiederherstellung", "auto", "restore"] };

// Sicherung lebt unter Einstellungen › Sicherung (#backupBox); alte Links #/backup leiten dorthin um
Views.backup = async (main) => {
  if (main.id === "main") { Hist.replacing = true; location.replace("#/settings?tab=sicherung"); return; }
  const d = await api("/api/backups");
  main.innerHTML = `<div class="backup-embed">
    <div class="backup-hero">
      <div class="card bh-card">
        <h3>${icon("archive")}Jetzt sichern</h3>
        <p>Verlauf, Playlists, Genre-Cache und Exporte in eine einzelne <span class="path">.tbbackup</span>-Datei.</p>
        <label class="check"><input type="checkbox" id="bKeys"> API-Keys mitsichern <span class="muted">(für einen neuen Rechner praktisch)</span></label>
        <div class="actions"><button class="btn btn--primary" id="bCreate">${icon("archive")}Sicherung erstellen</button></div>
      </div>
      <div class="card bh-card">
        <h3>${icon("upload")}Vom alten Rechner holen</h3>
        <p>Backup-Datei auswählen – sie wird in den Sicherungsordner übernommen und kann dann wiederhergestellt werden.</p>
        <p>Ordner: <span class="path">${esc(d.dir)}</span></p>
        <div class="actions"><button class="btn" id="bImport">${icon("upload")}Datei importieren</button>
          <button class="btn btn--ghost" id="bFolder">${icon("folder")}Ordner öffnen</button></div>
      </div>
    </div>
    <div class="card ba-card">
      <h3>${icon("repeat")}Automatisch sichern</h3>
      <div class="ba-grid">
        <div class="field"><label>Wie oft</label><div class="segmented" id="baInt">${[["off", "Aus"], ["daily", "Täglich"], ["weekly", "Wöchentlich"]].map(([v, l]) => `<button data-v="${v}" class="${d.auto.interval === v ? "on" : ""}">${l}</button>`).join("")}</div></div>
        <div class="field"><label>Behalten</label><select class="select" id="baKeep">${[3, 5, 7, 14, 30, 60].concat([d.auto.keep]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map(n => `<option value="${n}" ${n === d.auto.keep ? "selected" : ""}>die letzten ${n}</option>`).join("")}</select></div>
        <div class="field grow"><label>Ordner (z. B. eine zweite Platte)</label>
          <div class="ba-dir"><input class="input" id="baDir" value="${esc(d.dir)}" spellcheck="false" autocomplete="off">
            <button class="btn btn--sm" id="baDirSave">Übernehmen</button>${d.custom_dir ? `<button class="btn btn--sm btn--ghost" id="baDirReset" title="Zurück zum Standard-Ordner im Datenordner">Standard</button>` : ""}</div></div>
      </div>
      <div class="cell-sub ba-state">${d.auto.interval === "off" ? "Automatische Sicherung ist aus." : `Ohne API-Keys · geprüft wird beim Start und danach stündlich${d.last_auto ? ` · zuletzt ${relTime(d.last_auto)}` : ""}${d.next_auto && d.last_auto ? ` · nächste ${fmtDate(d.next_auto)}` : ""}`}
        · Neuer Ordner gilt für neue Sicherungen; vorhandene bleiben im alten Ordner.</div>
    </div>
    <div class="section-title">Vorhandene Sicherungen · ${d.items.length}</div>
    ${d.items.length ? `<div class="rows">${d.items.map(b => { const [kn, kc, ki] = KIND[b.kind] || KIND.manuell; return `
      <div class="row row--backup">
        <div class="b-ico ${kc}">${icon(ki)}</div>
        <div class="cell-main"><div class="cell-title">${fmtDate(b.created)}<span class="tag">${kn}</span>${b.includes_keys ? `<span class="tag tag--keys">mit Keys</span>` : ""}</div>
          <div class="cell-sub">${esc(b.name)}</div></div>
        <div class="cell-muted">${b.stats.recognitions} Songs · ${b.stats.playlists} Playlists · ${esc(b.host)}</div>
        <div class="cell-muted">${fmtSize(b.size)}</div>
        <div class="b-acts">
          <button class="btn btn--sm" data-restore="${esc(b.name)}">${icon("restore")}Wiederherstellen</button>
          <a class="icon-btn" href="/api/backups/download/${enc(b.name)}" download title="Herunterladen">${icon("download")}</a>
          <button class="icon-btn" data-del="${esc(b.name)}" title="Löschen">${icon("trash")}</button>
        </div></div>`; }).join("")}</div>`
      : `<div class="empty">${icon("archive")}<h3>Noch keine Sicherung</h3><p>Erstell die erste – oder importiere eine vom alten Rechner.</p></div>`}
  </div>`;

  $("#bCreate").onclick = async () => {
    $("#bCreate").disabled = true;
    try { const r = await api("/api/backups", { method: "POST", body: { include_keys: $("#bKeys").checked } }); toast(`Gesichert: ${r.name}`); Views.backup(main); }
    catch (e) { toast(e.message, "err"); $("#bCreate").disabled = false; }
  };
  $("#bFolder").onclick = () => api("/api/backups/open-folder", { method: "POST" }).catch(e => toast(e.message, "err"));
  const baSave = async (body, msg) => { try { await api("/api/backups/auto", { method: "POST", body }); toast(msg); Views.backup(main); } catch (e) { toast(e.message, "err"); } };
  $$("#baInt button").forEach(b => b.onclick = () => baSave({ interval: b.dataset.v }, b.dataset.v === "off" ? "Automatische Sicherung aus" : `Automatisch ${b.textContent.toLowerCase()} sichern`));
  $("#baKeep").onchange = e => baSave({ keep: +e.target.value }, `Es bleiben die letzten ${e.target.value} automatischen Sicherungen`);
  $("#baDirSave").onclick = () => baSave({ folder: $("#baDir").value.trim() }, "Sicherungsordner gespeichert");
  $("#baDirReset")?.addEventListener("click", () => baSave({ folder: "" }, "Standard-Ordner"));
  $("#bImport").onclick = () => $("#fileInput").click();
  $("#fileInput").onchange = async e => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    try {
      const r = await fetch("/api/backups/upload", { method: "POST", headers: { "X-Filename": f.name }, body: f });
      const j = await r.json(); if (!r.ok) throw new Error(j.detail || "Import fehlgeschlagen");
      toast("Importiert – jetzt wiederherstellen"); await Views.backup(main); restoreDialog(j, main);
    } catch (err) { toast(err.message, "err"); }
  };
  $$("[data-restore]").forEach(b => b.onclick = () => restoreDialog(d.items.find(x => x.name === b.dataset.restore), main));
  $$("[data-del]").forEach(b => b.onclick = () => modal({
    title: "Sicherung löschen?", text: esc(b.dataset.del), confirm: "Löschen", danger: true,
    onConfirm: async () => { await api(`/api/backups/${enc(b.dataset.del)}`, { method: "DELETE" }); toast("Gelöscht"); Views.backup(main); },
  }));
};

function restoreDialog(b, main) {
  modal({
    title: "Sicherung wiederherstellen",
    text: `Vom ${fmtDate(b.created)} · ${esc(b.host)} · ${b.stats.recognitions} Songs, ${b.stats.playlists} Playlists`,
    body: `
      <label class="choice"><input type="radio" name="rmode" value="replace" checked><div><b>Ersetzen</b><span>Der aktuelle Stand wird durch das Backup ersetzt – richtig für einen neu aufgesetzten Rechner.</span></div></label>
      <label class="choice"><input type="radio" name="rmode" value="merge"><div><b>Zusammenführen</b><span>Songs und Playlists aus dem Backup kommen dazu, nichts geht verloren, nichts wird doppelt.</span></div></label>
      ${b.includes_keys ? `<label class="check" style="margin-top:4px"><input type="checkbox" id="rKeys" checked> Gesicherte API-Keys übernehmen</label>` : ""}
      <div class="cell-sub">${icon("info")} Der jetzige Stand wird vorher automatisch gesichert.</div>`,
    confirm: "Wiederherstellen",
    onConfirm: async box => {
      const mode = $("input[name=rmode]:checked", box).value;
      const r = await api("/api/backups/restore", { method: "POST", body: { name: b.name, mode, restore_keys: !!$("#rKeys", box)?.checked } });
      toast(`Wiederhergestellt: ${r.stats.recognitions} Songs, ${r.stats.playlists} Playlists${r.keys_restored ? `, ${r.keys_restored} Keys` : ""}`);
      S.listen.current = null; await refreshMeta(); Views.backup(main);
    },
  });
}

/* ---------- Updates */
const Update = {
  info: null,
  async check(force = false, prompt = true) {
    try { this.info = await api(`/api/update${force ? "?force=true" : ""}`); } catch { return null; }
    const pill = $("#updatePill");
    if (pill) {
      pill.classList.toggle("hidden", !this.info.available);
      $("#updateVer").textContent = this.info.latest || "";
    }
    if (!force && prompt) this.maybePrompt();
    this.watch();          // läuft schon ein Update (z. B. nach Neuladen der Oberfläche)? -> Status zeigen
    return this.info;
  },
  // Fortschritt: Balken im Dialog + Status in der Seitenleiste („Lädt … 42 %“), solange ein Update läuft
  RUN: ["sicherung", "laden", "pruefen", "installieren"],
  async watch() {
    if (this.watching) return;
    this.watching = true;
    try {
      for (;;) {
        let p = null;
        try { p = await api("/api/update/progress"); } catch { /* Server startet neu */ }
        this.showProgress(p);
        if (!p || !this.RUN.includes(p.phase)) break;
        await new Promise(r => setTimeout(r, 400));
      }
    } finally { this.watching = false; }
  },
  showProgress(p) {
    const run = p && this.RUN.includes(p.phase), pct = p?.percent;
    const mb = n => (n / 1048576).toFixed(1).replace(".", ",");
    const detail = p?.phase === "laden" && p.total ? `${mb(p.done || 0)} von ${mb(p.total)} MB` : "";
    const pill = $("#updatePill");
    if (pill) {
      pill.classList.toggle("update-pill--run", !!run);
      pill.style.setProperty("--p", `${pct ?? 0}%`);
      if (run) {
        pill.classList.remove("hidden");
        $("span", pill).textContent = p.phase === "laden" ? "Update lädt …" : p.text.replace(/ …$/, "") + " …";
        $("#updateVer").textContent = pct != null && p.phase === "laden" ? `${pct} %` : "";
        pill.title = [p.text, detail].filter(Boolean).join(" – ");
      } else {
        $("span", pill).textContent = p?.phase === "fertig" ? "Update bereit" : "Update verfügbar";
        $("#updateVer").textContent = this.info?.latest || "";
        pill.title = "";
        if (!this.info?.available && p?.phase !== "fertig") pill.classList.add("hidden");
      }
    }
    const box = $("#updProg");
    if (box && p?.phase && p.phase !== "vorbereiten") {
      box.classList.remove("hidden");
      box.classList.toggle("upd-prog--err", p.phase === "fehler");
      box.classList.toggle("upd-prog--busy", run && pct == null);
      $(".upd-bar b", box).style.width = `${p.phase === "fehler" ? 100 : pct ?? 0}%`;
      $(".upd-ptext", box).innerHTML = `<span>${esc(p.phase === "fehler" ? p.error || p.text : p.text)}</span><span class="num">${esc(detail)}${pct != null && p.phase === "laden" ? ` · ${pct} %` : ""}</span>`;
      box.setAttribute("aria-valuenow", String(pct ?? 0));
    }
  },
  html(u) {
    if (!u) return "";
    const state = !u.configured ? `<span class="acc-badge">Update-Quelle noch nicht eingerichtet</span>`
      : u.error && /Prozessor/.test(u.error) ? `<span class="acc-badge warn">Nicht für diesen Rechner</span>`
      : u.error ? `<span class="acc-badge warn">Prüfung fehlgeschlagen</span>`
      : u.available ? `<span class="acc-badge warn">${icon("download")}${esc(u.latest)} verfügbar</span>`
      : `<span class="acc-badge ok">${icon("check")}Aktuell</span>`;
    return `<div class="card upd">
      <div class="upd-main">
        <div class="acc-title">SH-Tunebridge ${esc(u.current)} ${state}</div>
        <div class="acc-hint">${u.dev ? "Entwicklerinstallation – Updates hier per <span class=\"path\">git pull</span>. " : ""}${u.system ? `System: ${esc(u.system)} · ` : ""}${u.configured ? `Quelle: <span class="path">${esc(u.repo)}</span>` : ""}${u.checked ? ` · geprüft ${relTime(u.checked)}` : ""}${u.error ? ` · ${esc(u.error)}` : ""}</div>
        ${u.skipped?.length ? `<div class="notice" style="margin:8px 0">${icon("info")}<div><b>Unsignierte Version ignoriert:</b> ${u.skipped.map(esc).join(", ")} – diese stammt nicht vom Herausgeber und wird nicht installiert.</div></div>` : ""}
        <div class="cell-sub">Es werden nur <b>signierte</b> Versionen installiert, und nur wenn du es bestätigst. Vorher wird automatisch gesichert.</div>
      </div>
      <div class="acc-actions">
        <button class="btn btn--sm btn--ghost" id="updCheck">${icon("restore")}Jetzt prüfen</button>
        ${u.available && !u.dev ? `<button class="btn btn--sm btn--primary" id="updGo">${icon("download")}Update ansehen</button>` : ""}
      </div></div>`;
  },
  bind(main) {
    $("#updCheck")?.addEventListener("click", async () => { await this.check(true); Views.settings(main); toast(this.info?.available ? `Update ${this.info.latest} verfügbar` : "Du hast die neueste Version"); });
    $("#updGo")?.addEventListener("click", () => this.dialog());
  },
  // Mittiger Hinweis, sobald ein Update da ist: „Später“ oder „Jetzt aktualisieren“ (lädt, installiert, startet neu)
  SNOOZE_H: 12,
  snoozed(tag) {
    try { const v = JSON.parse(localStorage.getItem("updSnooze") || "{}"); return v.tag === tag && Date.now() - v.t < this.SNOOZE_H * 3600e3; } catch { return false; }
  },
  maybePrompt() {
    const u = this.info;
    if (u?.available && !u.dev && !this.snoozed(u.latest) && !$("#modal").classList.contains("open")) this.dialog();
  },
  async dialog() {
    const u = this.info, tag = u.latest;
    const manual = u.kind === "download";  // Windows/macOS: geprüfte Datei landet in „Downloads“
    const steps = manual
      ? [["prep", "Signatur prüfen"], ["inst", "Herunterladen & Prüfsumme vergleichen (vorher wird gesichert)"]]
      : [["prep", "Herunterladen & Signatur prüfen"], ["inst", "Installieren (vorher wird gesichert)"], ["rest", "Neu starten"]];
    modal({
      title: "Update verfügbar",
      text: `SH-Tunebridge <b>${esc(tag)}</b> ist da – du hast ${esc(u.current)}.`,
      body: `<div id="updBody"><div class="notes" id="updNotes">${skeletonRows(2)}</div></div>
        <div class="upd-steps hidden" id="updSteps">${steps.map(([k, l]) => `<div class="upd-step" data-step="${k}"><span class="upd-dot"></span>${l}</div>`).join("")}</div>
        <div class="upd-prog hidden" id="updProg" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-label="Fortschritt des Updates"><div class="upd-bar"><b></b></div><div class="upd-ptext"></div></div>`,
      confirm: manual ? "Herunterladen" : "Jetzt aktualisieren", cancel: "Später", sticky: true,
      onCancel: () => { try { localStorage.setItem("updSnooze", JSON.stringify({ tag, t: Date.now() })); } catch {} toast(`Erinnerung in ${this.SNOOZE_H} Stunden – oder jederzeit über „Update verfügbar“ links unten`); },
      onConfirm: async () => {
        const step = (k, st) => { const el = $(`[data-step=${k}]`); if (el) el.dataset.state = st; };
        $("#updSteps").classList.remove("hidden");
        $("[data-m=cancel]").disabled = true;
        const ok = $("[data-m=ok]");
        try {
          ok.textContent = "Aktualisiere …";
          step("prep", "run"); await this.prepared; step("prep", "done");
          step("inst", "run");
          const inst = api("/api/update/install", { method: "POST" });
          setTimeout(() => this.watch(), 150);
          const done = await inst; step("inst", "done");
          this.showProgress(await api("/api/update/progress").catch(() => null));
          if (manual) {
            setTimeout(() => modal({ title: "Update heruntergeladen", text: `Geprüft und gespeichert: <span class="path">${esc(done.downloaded)}</span><br>
              Bitte SH-Tunebridge schließen und die neue Version installieren bzw. entpacken – deine Daten bleiben erhalten.`, cancel: null, onConfirm: async () => {} }), 50);
            return;
          }
          step("rest", "run");
          await api("/api/update/restart", { method: "POST" });
          document.body.innerHTML = `<div class="restarting"><div class="spinner"></div><h3>SH-Tunebridge ${esc(tag)} startet …</h3><p>Das Fenster öffnet sich gleich neu.</p></div>`;
        } catch (e) {
          $$(".upd-step[data-state=run]").forEach(el => el.dataset.state = "err");
          $("[data-m=cancel]").disabled = false; ok.textContent = "Erneut versuchen";
          throw e;
        }
        throw Object.assign(new Error(""), { silent: true });
      },
    });
    // Schon beim Öffnen im Hintergrund laden & prüfen -> „Jetzt aktualisieren“ geht danach schnell
    this.prepared = api("/api/update/prepare", { method: "POST", body: { tag } });
    try {
      const p = await this.prepared;
      const n = $("#updNotes"); if (n) n.innerHTML = `<div class="upd-verified">${icon("check")} Signatur geprüft – stammt vom Herausgeber</div>${esc(p.notes || "Keine Beschreibung.").replace(/\n/g, "<br>")}`;
    } catch (e) {
      const n = $("#updNotes"); if (n) n.innerHTML = `<div class="notice">${icon("info")}<div>${esc(e.message)}</div></div>`;
      const ok = $("[data-m=ok]"); if (ok) ok.disabled = true;
    }
  },
};

/* ---------- Einstellungen */
const SETTING_HINTS = {
  LASTFM_API_KEY: `Für Genres & ähnliche Songs. Kostenlos: <a href="https://www.last.fm/api/account/create" target="_blank" rel="noopener">last.fm/api</a>`,
  AUDD_API_TOKEN: `Zweite Erkennung. <a href="https://dashboard.audd.io" target="_blank" rel="noopener">dashboard.audd.io</a>`,
  ACRCLOUD_HOST: `z. B. identify-eu-west-1.acrcloud.com · <a href="https://console.acrcloud.com" target="_blank" rel="noopener">console.acrcloud.com</a>`,
  ACRCLOUD_ACCESS_KEY: "Aus dem ACRCloud-Projekt",
  ACRCLOUD_ACCESS_SECRET: "Aus dem ACRCloud-Projekt",
  LLM_URL: "OpenAI-kompatibel, z. B. http://127.0.0.1:8080/v1 (llama.cpp-Server)",
  LLM_MODEL: "Optional – Modellname für den Server",
  YOUTUBE_OAUTH_CLIENT_ID: `Für den YouTube-Login (Lesen; Schreibrecht erst beim Übertragen). Desktop-App-Client in der <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noopener">Google Cloud Console</a> – einfacher: Dienste › YouTube › „Einrichten & verbinden“`,
  YOUTUBE_OAUTH_CLIENT_SECRET: "Gehört zur YouTube-Client-ID oben",
  SOUNDCLOUD_CLIENT_ID: `Für den SoundCloud-Login (Lesen und Übertragen, Artist Pro nötig). Redirect-URI: http://127.0.0.1:8765/api/oauth/soundcloud/callback`,
  SOUNDCLOUD_CLIENT_SECRET: "Gehört zur SoundCloud-Client-ID oben",
};
const SERVICE_STYLE = { lastfm: ["fm", "#e25c55"], audd: ["Au", "#7aa9ea"], acrcloud: ["AC", "#e0b46a"] };
const STATE_TEXT = { saved: "Verbunden", waiting: "Warte auf Login …", partial: "Teilweise gefunden", checking: "Prüfe …", browser: "Im Browser geöffnet", closed: "Abgebrochen" };

function accountCard(a) {
  const ses = a.session || {}, busy = ["waiting", "partial", "checking", "browser"].includes(ses.state);
  const [m, c] = SERVICE_STYLE[a.id] || ["?", "#888"];
  const badge = a.connected ? `<span class="acc-badge ok">${icon("check")}Verbunden</span>`
    : a.partial ? `<span class="acc-badge warn">Teilweise</span>` : `<span class="acc-badge">Nicht verbunden</span>`;
  return `<div class="card acc ${busy ? "busy" : ""}" data-acc="${a.id}">
    <div class="p-logo" style="--pc:${c}">${m}</div>
    <div class="acc-main">
      <div class="acc-title">${esc(a.name)}${badge}</div>
      <div class="acc-hint">${busy || ses.state === "closed" ? `<span class="acc-live">${esc(ses.message || STATE_TEXT[ses.state] || "")}</span>` : esc(a.hint)}</div>
      ${Object.keys(ses.found || {}).length && busy ? `<div class="acc-found">${Object.entries(ses.found).map(([k, v]) => `<span class="path">${esc(k.replace(/^[A-Z]+_/, "").replace(/_/g, " ").toLowerCase())}: ${esc(v)}</span>`).join(" ")}</div>` : ""}
      <div class="acc-actions">
        <button class="btn btn--sm ${a.connected ? "" : "btn--primary"}" data-connect="${a.id}">${icon(a.connected ? "restore" : "key")}${a.connected ? "Neu verbinden" : busy ? "Fenster erneut öffnen" : "Verbinden"}</button>
        ${busy ? `<button class="btn btn--sm btn--ghost" data-clip="${a.id}">${icon("check")}Key kopiert? Übernehmen</button>` : ""}
        ${a.connected ? `<button class="btn btn--sm btn--ghost" data-test="${a.id}">Prüfen</button>` : ""}
      </div>
    </div></div>`;
}

const Connect = {
  timer: 0, pending: new Set(),
  async poll(main) {
    clearTimeout(this.timer);
    if (!$("#accounts")) return;
    const accs = await api("/api/connect").catch(() => null);
    if (!accs || !$("#accounts")) return;
    for (const a of accs) {
      const card = $(`[data-acc="${a.id}"]`);
      const prev = card?.dataset.state;
      if (card && (prev !== (a.session?.state || "") + a.connected + JSON.stringify(a.session?.found || {}) + (a.session?.message || ""))) {
        card.outerHTML = accountCard(a);
        const nc = $(`[data-acc="${a.id}"]`);
        nc.dataset.state = (a.session?.state || "") + a.connected + JSON.stringify(a.session?.found || {}) + (a.session?.message || "");
        Connect.bind(nc, main);
        if (prev && a.session?.state === "saved" && a.connected) { toast(`${a.name} verbunden`); refreshMeta(); this.pending.delete(a.id); }
      }
      if (["waiting", "partial", "checking", "browser"].includes(a.session?.state)) this.pending.add(a.id); else this.pending.delete(a.id);
    }
    if (this.pending.size) this.timer = setTimeout(() => this.poll(main), 1200);
  },
  bind(root, main) {
    $$("[data-connect]", root).forEach(b => b.onclick = async () => {
      try {
        const r = await api(`/api/connect/${b.dataset.connect}`, { method: "POST" });
        if (r.mode === "browser") toast("Im Browser geöffnet – kopier den Key, SH-Tunebridge erkennt ihn");
        // im App-Fenster wechselt die Seite jetzt zum Dienst; tunebridge kommt danach automatisch zurück
        this.pending.add(b.dataset.connect); this.poll(main);
      } catch (e) { toast(e.message, "err"); }
    });
    $$("[data-clip]", root).forEach(b => b.onclick = () => this.checkClipboard(b.dataset.clip, true));
    $$("[data-test]", root).forEach(b => b.onclick = async () => {
      b.disabled = true;
      const r = await api(`/api/connect/${b.dataset.test}/test`, { method: "POST" }).catch(e => ({ ok: false, message: e.message }));
      toast(r.message, r.ok === false ? "err" : "ok"); b.disabled = false;
    });
  },
  async checkClipboard(id, manual = false) {
    const r = await api(`/api/connect/${id}/clipboard`, { method: "POST" }).catch(() => ({ found: {} }));
    const ent = Object.entries(r.found || {});
    if (!ent.length) { if (manual) toast("In der Zwischenablage ist kein passender Key", "err"); return; }
    const name = ({ lastfm: "Last.fm", audd: "AudD", acrcloud: "ACRCloud" })[id];
    modal({
      title: `${name}-Key in der Zwischenablage`,
      text: ent.map(([k, v]) => `${esc(k)}: <span class="path">${esc(v)}</span>`).join("<br>"),
      confirm: "Prüfen & übernehmen",
      onConfirm: async () => {
        const res = await api(`/api/connect/${id}/accept`, { method: "POST" });
        toast(res.message || "Übernommen"); refreshMeta(); this.poll($("#main"));
      },
    });
  },
};
// Zurück ins Fenster nach dem Kopieren -> Zwischenablage prüfen (nur während eines Verbindungsvorgangs)
window.addEventListener("focus", () => { for (const id of Connect.pending) Connect.checkClipboard(id); });


/* ---------- Lokales LLM */
const fmtGB = b => `${(b / 1e9).toFixed(1)} GB`;
const LLM = {
  timer: null,
  fits(m, o) {
    const s = o.settings;
    if (s.device === "gpu") {
      const g = o.gpus.find(x => x.id === s.gpu) || o.gpus[0];
      if (!g) return null;
      return g.vram_gb < m.need_gb ? "low" : g.free_gb < m.need_gb ? "busy" : "ok";
    }
    return o.ram.total >= m.need_gb + 4 ? "ok" : "low";
  },
  jobText(j) {
    if (!j) return "";
    if (j.state === "downloading") return `${fmtGB(j.done)} von ${fmtGB(j.total)}${j.speed ? ` · ${(j.speed / 1e6).toFixed(1)} MB/s · noch ~${fmtTime(Math.max(0, (j.total - j.done) / j.speed))}` : ""}`;
    return ({ queued: "Startet …", resuming: "Setzt Download fort (prüfe vorhandenen Teil) …", verifying: "Prüfe Datei …",
      error: j.error || "Fehler", cancelled: "Pausiert – Fortsetzen lädt dort weiter, wo aufgehört wurde" })[j.state] || "";
  },
  card(m, o) {
    const s = o.settings, active = s.model === m.id, j = m.job, busy = j && ["queued", "downloading", "resuming", "verifying"].includes(j.state);
    const fit = this.fits(m, o), pct = j && j.total ? Math.round(j.done / j.total * 100) : 0;
    const need = s.device === "gpu" ? `ab ${m.need_gb} GB Grafikspeicher` : `ab ${m.need_gb + 4} GB RAM`;
    let action;
    if (m.downloaded) action = active && s.enabled ? `<span class="acc-badge ok">${icon("check")}Aktiv</span>`
      : `<button class="btn btn--sm btn--primary" data-use="${m.id}">Verwenden</button>`;
    else if (busy) action = `<button class="btn btn--sm" data-cancel="${m.id}">Pausieren</button>`;
    else action = `<button class="btn btn--sm ${j?.state === "cancelled" ? "btn--primary" : ""}" data-dl="${m.id}">${icon("download")}${j?.state === "cancelled" ? "Fortsetzen" : "Herunterladen"}</button>`;
    return `<div class="card llm-model ${active && s.enabled ? "active" : ""}" data-model="${m.id}">
      <div class="llm-tier">${esc(m.tier)}</div>
      <div class="llm-name">${esc(m.name)} <span class="cell-sub">${fmtGB(m.size)}</span></div>
      <div class="llm-desc">${esc(m.desc)}</div>
      <div class="llm-score" title="Test: 30 Songs mit eindeutigem Subgenre"><span class="meter"><b style="width:${Math.round(m.score / 30 * 100)}%"></b></span>${m.score}/30 richtig · CPU ~${m.cpu_s} s/Song</div>
      <div class="llm-need ${fit && fit !== "ok" ? "low" : ""}">${fit && fit !== "ok" ? icon("info") : ""}${need}${fit === "low" ? " – zu groß für diese Auswahl" : fit === "busy" ? " – Grafikspeicher ist gerade von anderen Programmen belegt" : ""}</div>
      ${busy || j?.state === "cancelled" || j?.state === "error" ? `<div class="llm-bar"><div style="width:${pct}%"></div></div><div class="llm-job ${j.state === "error" ? "err" : ""}">${esc(this.jobText(j))}</div>` : ""}
      <div class="llm-actions">${action}${m.downloaded ? `<button class="btn btn--sm btn--ghost btn--danger" data-del="${m.id}" title="Modell löschen">${icon("trash")}</button>` : ""}</div>
    </div>`;
  },
  serverText(o) {
    const sv = o.server, s = o.settings;
    if (!s.enabled) return "Aus – Subgenres kommen nur aus Tags.";
    const name = o.models.find(m => m.id === s.model)?.name;
    if (!o.models.find(m => m.id === s.model)?.downloaded) return `${name} wird noch heruntergeladen …`;
    const rt = o.runtime[s.device];
    if (!rt.installed) return rt.job?.state === "error" ? `Laufzeit: ${rt.job.error}` : "Lade Laufzeit (llama.cpp) …";
    return ({ running: `Läuft · ${name} auf ${s.device === "gpu" ? "Grafikkarte" : "CPU"}`, starting: `Startet ${name} …`,
      error: sv.error || "Fehler", stopped: `Bereit · startet automatisch bei Bedarf, stoppt nach ${s.idle_minutes} min ohne Nutzung` })[sv.state] || sv.state;
  },
  html(o) {
    const s = o.settings, gpuRt = o.runtime.gpu;
    const gpuPick = s.device !== "gpu" ? "" : !gpuRt.installed
      ? `<div class="cell-sub">${gpuRt.job?.state === "error" ? esc(gpuRt.job.error) : "Lade Vulkan-Laufzeit, um Grafikkarten zu erkennen …"}</div>`
      : o.gpus.length ? `<select class="input select" id="llmGpu">${o.gpus.map(g => `<option value="${g.id}" ${g.id === s.gpu ? "selected" : ""}>${esc(g.name)} · ${g.vram_gb} GB (${g.free_gb} GB frei)</option>`).join("")}</select>`
      : `<div class="cell-sub" style="color:var(--warn)">Keine Vulkan-fähige Grafikkarte gefunden – bitte CPU verwenden.</div>`;
    return `<div class="card llm-head">
        <label class="switch"><input type="checkbox" id="llmOn" ${s.enabled ? "checked" : ""}><span class="track"></span><span>Lokales LLM verwenden</span></label>
        <div class="llm-status"><span class="status-dot ${o.server.state === "running" ? "on" : ""}"></span><span id="llmStatus">${esc(this.serverText(o))}</span></div>
        <div class="llm-run">
          <div class="field"><label>Ausführen auf</label>
            <div class="segmented" id="llmDev"><button data-d="cpu" class="${s.device === "cpu" ? "on" : ""}">CPU + RAM</button><button data-d="gpu" class="${s.device === "gpu" ? "on" : ""}">Grafikkarte</button></div></div>
          <div class="field" id="llmGpuWrap">${s.device === "gpu" ? `<label>Grafikkarte</label>${gpuPick}` : `<label>&nbsp;</label><div class="cell-sub">${o.cores} Kerne · ${o.ram.total} GB RAM (${o.ram.available} GB frei)</div>`}</div>
          <div class="llm-btns"><button class="btn btn--sm" id="llmTest" ${s.enabled ? "" : "disabled"}>Testen</button>${o.server.state === "running" ? `<button class="btn btn--sm btn--ghost" id="llmStop">Stoppen</button>` : ""}</div>
        </div>
      </div>
      <div class="llm-models">${o.models.map(m => this.card(m, o)).join("")}</div>
      <div class="cell-sub" style="margin:10px 2px 0;white-space:normal">Downloads laufen im Hintergrund weiter, auch wenn du die Seite wechselst. Speicherort: <span class="path">${esc(o.dir)}</span> · ${o.disk_free_gb} GB frei. Modelle: Gemma 3 von Google (Gemma-Lizenz), Laufzeit: llama.cpp ${esc(o.runtime.cpu.build)}.</div>`;
  },
  async render(box) {
    let o;
    try { o = await api("/api/llm"); } catch { return; }
    if (!document.body.contains(box)) return;
    const sig = JSON.stringify(o, (k, v) => k === "speed" || k === "available" || k === "idle_for" || k === "disk_free_gb" ? undefined : k === "done" ? Math.round(v / 5e7) : v);
    if (box.dataset.sig !== sig) { box.dataset.sig = sig; box.innerHTML = this.html(o); this.bind(box, o); hydrateIcons(box); }
    else $$("[data-model]", box).forEach(c => { const m = o.models.find(x => x.id === c.dataset.model), t = $(".llm-job", c); if (t && m.job) t.textContent = this.jobText(m.job); });
    const active = o.models.some(m => m.job && ["queued", "downloading", "resuming", "verifying"].includes(m.job.state))
      || Object.values(o.runtime).some(r => r.job && ["queued", "downloading", "resuming", "verifying"].includes(r.job.state)) || o.server.state === "starting";
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.render(box), active ? 1000 : 5000);
  },
  async set(box, patch) {
    try { await api("/api/llm/settings", { method: "POST", body: patch }); } catch (e) { toast(e.message, "err"); }
    this.render(box);
  },
  // Gemma-Lizenz: vor Download/Nutzung einmal bestätigen (Bedingungen von Google, u. a. Verbotene-Nutzung-Richtlinie)
  async terms(o) {
    if (o.settings.terms_accepted) return true;
    const ok = await ask({ title: "Nutzungsbedingungen der Modelle", confirm: "Zustimmen", cancel: "Abbrechen",
      text: "Die drei Modelle sind Gemma 3 von Google.",
      body: `<div class="privacy-note"><p>Mit dem Herunterladen und Nutzen stimmst du den <a href="${esc(o.terms_url)}" target="_blank" rel="noopener">Gemma-Nutzungsbedingungen</a>
        und der <a href="${esc(o.policy_url)}" target="_blank" rel="noopener">Richtlinie zur verbotenen Nutzung</a> zu.</p>
        <p class="muted">Das Modell läuft komplett auf deinem Rechner – es werden keine Daten an Google oder andere gesendet. Geladen wird einmalig von Hugging Face.</p></div>` });
    if (!ok) return false;
    await api("/api/llm/settings", { method: "POST", body: { terms_accepted: true } });
    o.settings.terms_accepted = true;
    return true;
  },
  bind(box, o) {
    $("#llmOn", box).onchange = async e => {
      if (e.target.checked && !(await this.terms(o))) { e.target.checked = false; return; }
      const m = o.models.find(x => x.id === o.settings.model);
      if (e.target.checked && !m.downloaded && !m.job) api(`/api/llm/models/${m.id}/download`, { method: "POST" });
      this.set(box, { enabled: e.target.checked });
    };
    $$("#llmDev button", box).forEach(b => b.onclick = () => this.set(box, { device: b.dataset.d }));
    const gsel = $("#llmGpu", box);
    if (gsel) { gsel.onchange = () => this.set(box, { gpu: gsel.value }); if (!o.settings.gpu) { const best = [...o.gpus].sort((a, b) => b.vram_gb - a.vram_gb)[0]; this.set(box, { gpu: best.id }); } }
    $$("[data-dl]", box).forEach(b => b.onclick = async () => {
      if (!(await this.terms(o))) return;
      const m = o.models.find(x => x.id === b.dataset.dl);
      if (m.size / 1e9 + 0.5 > o.disk_free_gb) return toast(`Zu wenig Speicherplatz (${o.disk_free_gb} GB frei)`, "err");
      await api(`/api/llm/models/${m.id}/download`, { method: "POST" });
      if (!o.settings.enabled || !o.models.find(x => x.id === o.settings.model)?.downloaded) await this.set(box, { model: m.id, enabled: true });
      toast(`${m.name} wird im Hintergrund geladen`); this.render(box);
    });
    $$("[data-cancel]", box).forEach(b => b.onclick = async () => { await api(`/api/llm/models/${b.dataset.cancel}/cancel`, { method: "POST" }); this.render(box); });
    $$("[data-use]", box).forEach(b => b.onclick = async () => { if (await this.terms(o)) this.set(box, { model: b.dataset.use, enabled: true }); });
    $$("[data-del]", box).forEach(b => b.onclick = () => {
      const m = o.models.find(x => x.id === b.dataset.del);
      modal({ title: `${m.name} löschen?`, text: `Gibt ${fmtGB(m.size)} frei. Du kannst es jederzeit erneut herunterladen.`, confirm: "Löschen", danger: true,
        onConfirm: async () => { await api(`/api/llm/models/${m.id}`, { method: "DELETE" }); toast("Gelöscht"); this.render(box); } });
    });
    const stop = $("#llmStop", box);
    if (stop) stop.onclick = async () => { await api("/api/llm/stop", { method: "POST" }); this.render(box); };
    $("#llmTest", box).onclick = async e => {
      const b = e.currentTarget; b.disabled = true; b.textContent = "Teste …";
      setTimeout(() => this.render(box), 800);
      try {
        const r = await api("/api/llm/test", { method: "POST" });
        toast(r.ok ? `Antwort: ${r.answer} · Start ${r.start_s} s, Antwort ${r.answer_s} s` : "Modell hat keine passende Antwort gegeben", r.ok ? "" : "err");
      } catch (err) { toast(err.message, "err"); }
      this.render(box);
    };
  },
};

/* ---------- Rate-Limits: anzeigen, wenn ein Dienst pausiert */
const Limits = {
  list: [], timer: 0, at: 0,
  shazam() { return this.list.find(l => l.id === "shazam"); },
  wait(id = "shazam") { const l = this.list.find(x => x.id === id); return l ? Math.max(0, Math.round(l.paused - (Date.now() - this.at) / 1000)) : 0; },
  async refresh() {
    try { this.list = await api("/api/ratelimit"); this.at = Date.now(); } catch { return; }
    this.render();
    clearTimeout(this.timer);
    const active = this.list.some(l => l.paused > 0) || (this.shazam()?.used || 0) > 0;
    this.timer = setTimeout(() => this.refresh(), active ? 1000 : 8000);
  },
  render() {
    const paused = this.list.filter(l => this.wait(l.id) > 0);
    // Erkennen-Seite: Kasten unter dem Kreis
    const box = $("#limitBox");
    if (box) {
      const sh = this.shazam(), w = this.wait("shazam");
      box.innerHTML = paused.length ? paused.map(l => `<div class="limit-msg">${icon("clock")}<div><b>${esc(l.label)}-Limit erreicht</b>
          <span>${l.id === "shazam" ? "Erkennen ist pausiert" : "wird so lange übersprungen"} – wieder frei in <b class="num">${this.wait(l.id)} s</b>${l.reason ? ` · ${esc(l.reason)}` : ""}</span></div></div>`).join("")
        : sh && sh.used >= sh.limit - 4 ? `<div class="limit-use" title="SH-Tunebridge hält sich selbst an ein vorsichtiges Limit, damit Shazam nicht blockt">
            Shazam: ${sh.used}/${sh.limit} Anfragen in der letzten Minute<span class="meter"><b style="width:${Math.min(100, sh.used / sh.limit * 100)}%"></b></span></div>` : "";
      hydrateIcons(box);
      $("#orb")?.classList.toggle("limited", w > 0);
    }
    // überall sonst: kleiner Hinweis in der Ecke
    let pill = $("#limitPill");
    if (!pill) { pill = document.createElement("div"); pill.id = "limitPill"; document.body.appendChild(pill); }
    pill.innerHTML = paused.length && !box ? `${icon("clock")}${paused.map(l => `${esc(l.label)}-Limit · ${this.wait(l.id)} s`).join(" · ")}` : "";
    pill.classList.toggle("show", !!(paused.length && !box));
    hydrateIcons(pill);
  },
};

/* ---------- Genres: Katalog & Dazulernen */
const Genres = {
  async render(box) {
    const d = await api("/api/genres").catch(() => null);
    if (!d || !document.body.contains(box)) return;
    const fams = Object.keys(d.families);
    const famSel = (sel = "") => `<select class="select select--sm" data-fam>${fams.map(f => `<option ${f === sel ? "selected" : ""}>${esc(f)}</option>`).join("")}</select>`;
    const subSel = (fam, sel = "") => `<select class="select select--sm" data-sub><option value="">– kein Subgenre –</option>${(d.families[fam] || []).map(s => `<option ${s === sel ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>`;
    const cooc = c => Object.entries(c || {}).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([g, n]) => `${esc(g)} ${n}×`).join(", ") || "noch ohne Genre";
    const suggestUrl = t => `${ISSUES_URL}?title=${enc(`Genre-Vorschlag: ${t.label}`)}&body=${enc(`Genre: ${t.label}\nFamilie: ${t.main || "?"}\nSubgenre: ${t.sub || "-"}\n\n(Gelernt in SH-Tunebridge. Bitte prüfen und für alle aufnehmen.)`)}`;
    const learnedRow = t => `<div class="gt-row" data-tag="${esc(t.tag)}">
        <div class="gt-main"><b>${esc(t.label)}</b><span class="cell-sub">${t.how === "manuell" ? "von dir zugeordnet" : `automatisch gelernt · ${t.songs} Songs`}</span></div>
        ${genreChip(t.main, t.sub)}
        <div class="btn-row"><a class="icon-btn" href="${suggestUrl(t)}" target="_blank" rel="noopener" title="Für alle vorschlagen (GitHub-Issue, nur der Genre-Name)">${icon("external")}</a>
          <button class="icon-btn" data-act="edit" title="Ändern">${icon("sliders")}</button>
          <button class="icon-btn" data-act="reject" title="Ist kein Genre">${icon("trash")}</button></div></div>`;
    const candRow = t => `<div class="gt-row" data-tag="${esc(t.tag)}">
        <div class="gt-main"><b>${esc(t.label)}</b><span class="cell-sub">${t.songs}/${d.min_songs} Songs · bisher: ${cooc(t.cooc)}</span></div>
        <div class="gt-pick">${famSel(Object.entries(t.cooc || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || fams[0])}</div>
        <div class="btn-row"><button class="btn btn--sm" data-act="accept">${icon("check")}Ist ein Genre</button>
          <button class="btn btn--sm btn--ghost" data-act="reject">Kein Genre</button></div></div>`;
    const cat = d.catalog || {};
    box.innerHTML = `<div class="card">
      <div class="gt-stats">
        <div><b class="num">${(cat.total || 0).toLocaleString("de")}</b><span>Genres im Katalog<br><small>Wikidata/MusicBrainz, gemeinfrei</small></span></div>
        <div><b class="num">${d.curated.aliases}</b><span>handgepflegte Namen<br><small>${d.curated.families} Familien</small></span></div>
        <div><b class="num">${d.learned.length}</b><span>selbst gelernt</span></div>
        <div><b class="num">${d.candidates.length}</b><span>in Beobachtung</span></div>
      </div>
      <div class="btn-row" style="justify-content:flex-start;margin-top:12px"><button class="btn btn--sm" id="gtReclass">${icon("repeat")}Alle gespeicherten Songs neu einordnen</button></div>
    </div>
    ${d.learned.length ? `<div class="section-title">Selbst gelernt</div><div class="card gt-list">${d.learned.map(learnedRow).join("")}</div>` : ""}
    ${d.candidates.length ? `<div class="section-title">In Beobachtung <span class="cell-sub">– ab ${d.min_songs} Songs mit eindeutigem Genre wird automatisch übernommen</span></div>
      <div class="card gt-list">${d.candidates.slice(0, 40).map(candRow).join("")}</div>` : `<div class="cell-sub" style="margin:10px 2px 0">Noch keine unbekannten Tags beobachtet. Sobald Songs Tags haben, die kein bekanntes Genre sind, erscheinen sie hier.</div>`}
    ${d.rejected.length ? `<details class="gt-rej"><summary class="cell-sub">${d.rejected.length} verworfen (keine Genres)</summary>
      <div class="gt-chips">${d.rejected.slice(0, 80).map(t => `<button class="chip" data-reset="${esc(t.tag)}" title="Zurück in Beobachtung">${esc(t.label)}</button>`).join("")}</div></details>` : ""}`;
    hydrateIcons(box);
    const send = async body => { await api("/api/genres/term", { method: "POST", body }); this.render(box); };
    $("#gtReclass", box).onclick = async () => {
      const r = await api("/api/genres/reclassify", { method: "POST" });
      toast(`${r.changed} von ${r.total} Songs neu eingeordnet`); refreshMeta();
    };
    $$(".gt-row", box).forEach(row => {
      const tag = row.dataset.tag;
      $$("[data-act]", row).forEach(b => b.onclick = async () => {
        if (b.dataset.act === "reject") return send({ tag, action: "reject" });
        if (b.dataset.act === "accept") return send({ tag, action: "accept", main: $("[data-fam]", row).value });
        if (b.dataset.act === "edit") {
          const t = d.learned.find(x => x.tag === tag);
          const v = await ask({ title: `„${t.label}“ zuordnen`, confirm: "Speichern", cancel: "Abbrechen",
            body: `<div class="field"><label>Hauptgenre</label>${famSel(t.main)}</div><div class="field" id="gtSubBox"><label>Subgenre</label>${subSel(t.main, t.sub)}</div>`,
            value: m => ({ main: $("[data-fam]", m).value, sub: $("[data-sub]", m).value || null }) });
          if (v) send({ tag, action: "accept", ...v });
        }
      });
    });
    $$("[data-reset]", box).forEach(b => b.onclick = () => send({ tag: b.dataset.reset, action: "reset" }));
  },
};
document.addEventListener("change", e => {   // Subgenre-Liste im Zuordnen-Dialog an die Familie anpassen
  if (e.target.matches("#modalBox [data-fam]") && $("#gtSubBox")) {
    api("/api/genres").then(d => { $("#gtSubBox [data-sub]").innerHTML = `<option value="">– kein Subgenre –</option>` +
      (d.families[e.target.value] || []).map(s => `<option>${esc(s)}</option>`).join(""); });
  }
});

/* ---------- Debug-Protokoll */
const ISSUES_URL = "https://github.com/Bigsmoke002/SH-Tunebridge/issues/new";
const Debug = {
  on: false,
  async render(box) {
    const d = await api("/api/debug").catch(() => null);
    if (!d || !document.body.contains(box)) return;
    this.on = d.enabled;
    box.innerHTML = `<div class="card set-group">
      <div class="set-row"><div><div class="lbl"><span class="status-dot ${d.enabled ? "on" : ""}"></span>Debug-Protokoll aufzeichnen</div>
        <div class="hint">Schreibt jeden Schritt mit: Erkennung, Tempo-Suche, Genre (inkl. warum „Genre unbekannt“), ähnliche Songs, Hörproben, Updates, LLM, Fehler.
        Nur auf deinem Rechner (max. 6 MB) – Schlüssel, Benutzer- und Rechnername werden geschwärzt.</div></div><div></div>
        <label class="switch"><input type="checkbox" id="dbgSw" ${d.enabled ? "checked" : ""}><span class="track"></span></label></div>
      <div class="set-row"><div><div class="lbl">Bericht für den Entwickler</div>
        <div class="hint">${d.size ? `Protokoll: ${fmtSize(d.size)}` : "Protokoll ist leer"} · Es wird nichts automatisch gesendet – du speicherst die Datei und hängst sie selbst an.</div></div><div></div>
        <div class="btn-row">
          <button class="btn btn--sm" id="dbgView">${icon("search")}Ansehen</button>
          <button class="btn btn--sm btn--primary" id="dbgSave">${icon("download")}Bericht speichern</button>
          <button class="btn btn--sm btn--danger" id="dbgClear" ${d.size ? "" : "disabled"}>${icon("trash")}Leeren</button></div></div>
    </div>
    <div class="cell-sub" style="white-space:normal;margin:10px 2px 0">So meldest du ein Problem: Debug einschalten → Problem nachstellen → „Bericht speichern“ →
      <a href="${ISSUES_URL}" target="_blank" rel="noopener">Problem auf GitHub melden</a> und die Datei anhängen. Danach kannst du Debug wieder ausschalten.</div>`;
    hydrateIcons(box);
    $("#dbgSw", box).onchange = async e => {
      await api("/api/debug", { method: "POST", body: { enabled: e.target.checked } });
      toast(e.target.checked ? "Debug-Protokoll läuft – stell das Problem jetzt nach" : "Debug-Protokoll aus"); this.render(box);
    };
    $("#dbgView", box).onclick = async () => {
      const txt = await fetch("/api/debug/report").then(r => r.text());
      modal({ title: "Inhalt des Debug-Berichts", confirm: "Schließen", cancel: null, text: "Genau das steht in der Datei:",
        body: `<pre class="dbg-pre">${esc(txt)}</pre>`, onConfirm: async () => {} });
    };
    $("#dbgSave", box).onclick = async () => {
      try {
        const r = await api("/api/debug/export", { method: "POST" });
        modal({ title: "Bericht gespeichert", confirm: "Schließen", cancel: null,
          text: "Die Datei liegt in deinem Download-Ordner:",
          body: `<div class="path">${esc(r.name)}</div><p class="cell-sub" style="white-space:normal;margin-top:10px">Auf GitHub ein neues Issue anlegen, kurz beschreiben, was passiert ist, und die Datei per Drag & Drop anhängen.</p>
            <div class="btn-row" style="margin-top:10px"><button class="btn btn--sm" id="dbgFolder">${icon("folder")}Ordner öffnen</button>
            <a class="btn btn--sm btn--primary" href="${ISSUES_URL}" target="_blank" rel="noopener">${icon("external")}Problem auf GitHub melden</a></div>`,
          onConfirm: async () => {} });
        hydrateIcons($("#modalBox"));
        $("#dbgFolder").onclick = () => api("/api/debug/open-folder", { method: "POST", body: { folder: r.folder } });
      } catch (e) { toast(e.message, "err"); }
    };
    $("#dbgClear", box).onclick = async () => { await api("/api/debug/clear", { method: "POST" }); toast("Protokoll geleert"); this.render(box); };
  },
};
// Fehler der Oberfläche mitschreiben (nur wenn Debug an ist)
const reportClientError = (message, where, stack) => {
  if (!Debug.on) return;
  fetch("/api/debug/client", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: String(message || "?"), where: String(where || ""), stack: String(stack || "") }) }).catch(() => {});
};
window.addEventListener("error", e => reportClientError(e.message, `${e.filename}:${e.lineno}`, e.error?.stack));
window.addEventListener("unhandledrejection", e => reportClientError(e.reason?.message || e.reason, "promise", e.reason?.stack));
api("/api/debug").then(d => { Debug.on = d.enabled; }).catch(() => {});



/* ---------- KI-Musik-Hinweis & Kaufen */
const AI_STATUS = {
  hinweis: ["chip--warn", "Möglicherweise KI-generiert"],
  wahrscheinlich: ["chip--ai", "Hinweise auf KI-Musik"],
  markiert_ki: ["chip--ai", "KI-generiert (deine Markierung)"],
};
function aiChip(a) {
  const st = a && AI_STATUS[a.status];
  if (!st) return "";
  const tip = `${a.text}. Quellen: ${(a.quellen || []).join(", ")}. Kein Beweis – du kannst die Einschätzung unten korrigieren.`;
  return `<span class="chip ${st[0]}" title="${esc(tip)}">${icon("sparkle")}${esc(st[1])}</span>`;
}
function aiMarkHtml(a) {
  const s = a?.status;
  const src = a?.quellen?.length && !s?.startsWith("markiert") ? ` <span class="cell-sub">(${esc(a.quellen.join(", "))})</span>` : "";
  if (s === "markiert_ki" || s === "markiert_mensch")
    return `<span class="cell-sub">${esc(a.text)}</span> <button class="btn btn--xs btn--ghost" data-aimark="">Zurücksetzen</button>`;
  return `<span class="cell-sub">KI-Musik? ${esc(a?.text || "Noch nicht geprüft")}</span>${src}
    <button class="btn btn--xs btn--ghost" data-aimark="ki" title="Du weißt, dass dieser Song KI-generiert ist">Ist KI</button>
    <button class="btn btn--xs btn--ghost" data-aimark="mensch" title="Du weißt, dass echte Menschen ihn gemacht haben">Ist kein KI</button>`;
}
const BUY_LEVEL = { hires: 3, lossless: 2, lossy: 1 };
const skelBuy = () => `<div class="buy-list">${Array.from({ length: 4 }, () => `<div class="buy-item buy-item--sk"></div>`).join("")}</div>`;
function buyHtml(shops) {
  const tiers = [...new Set(shops.map(b => b.tier))];
  return `<div class="buy-list">${tiers.map(t => `<div class="buy-tier"><span class="q-bars q${BUY_LEVEL[t] || 1}"><b></b><b></b><b></b></span>${esc(shops.find(b => b.tier === t).tier_name)}</div>
    ${shops.filter(b => b.tier === t).map(b => `<a class="buy-item" href="${esc(b.url)}" target="_blank" rel="noopener noreferrer" title="${esc(b.hint)}${b.direct ? "" : " – öffnet die Suche im Shop"}">
      <span class="buy-name">${esc(b.name)}${b.id === "bandcamp" ? `<span class="buy-tag">fair</span>` : ""}</span><span class="buy-fmt">${esc(b.format)}</span>${icon(b.direct ? "external" : "search", "otile-ico")}</a>`).join("")}`).join("")}</div>
    <div class="det-foot">Ohne Provision – SH-Tunebridge verdient nichts daran. Die echte Qualität hängt vom jeweiligen Release ab; Bandcamp gibt den größten Anteil an Künstler weiter.</div>`;
}

/* ---------- Darstellung: Modus, Farbschema, Akzent, Hintergrund, Größe … (lokal + auf dem Server gemerkt) */
const LOOK_PALETTES = [["graphit", "Graphit", "#12151a", "#1d2128"], ["nacht", "Nacht", "#0f1422", "#1a2135"],
  ["aubergine", "Aubergine", "#16111b", "#231b2a"], ["wald", "Wald", "#0f1612", "#19231d"],
  ["espresso", "Espresso", "#181511", "#25201a"], ["oled", "OLED-Schwarz", "#000", "#131316"]];
const LOOK_ACCENTS = [["#6cc8a8", "Mint"], ["#4fc6d8", "Türkis"], ["#5fa8f0", "Blau"], ["#8b8cf8", "Indigo"], ["#b58cf6", "Violett"],
  ["#f07ab0", "Pink"], ["#f2788a", "Koralle"], ["#f39a5b", "Orange"], ["#e8c25a", "Gold"], ["#9bd35f", "Limette"]];
const Look = {
  defaults: { mode: "dunkel", palette: "graphit", accent: "#6cc8a8", font: 100, radius: "normal", density: "normal",
              motion: true, bg_dim: 55, bg_blur: 0, panel: 82 },
  cfg: store.get("look", {}),
  get(k) { return this.cfg[k] ?? this.defaults[k]; },
  apply() {
    const r = document.documentElement, c = this.cfg;
    const mode = this.get("mode") === "system" ? (matchMedia("(prefers-color-scheme: light)").matches ? "hell" : "dunkel") : this.get("mode");
    r.dataset.theme = mode;
    const ds = (k, v, def) => { if (v == null || v === def) delete r.dataset[k]; else r.dataset[k] = v; };
    ds("palette", this.get("palette"), "graphit"); ds("radius", this.get("radius"), "normal");
    ds("density", this.get("density"), "normal"); ds("motion", this.get("motion") ? null : "aus", null);
    r.style.setProperty("--accent-base", this.get("accent"));
    r.style.zoom = this.get("font") === 100 ? "" : this.get("font") / 100;
    if (c.bg) {
      r.dataset.bg = ""; r.style.setProperty("--bg-url", `url(/api/appearance/bg?v=${c.bg_v || 0})`);
      r.style.setProperty("--bg-dim", this.get("bg_dim") + "%");
      r.style.setProperty("--panel", this.get("panel") + "%");
    } else delete r.dataset.bg;
  },
  async load() {
    const d = await api("/api/appearance").catch(() => null);
    if (d) { this.cfg = d; store.set("look", d); this.apply(); }
  },
  set(patch) {
    Object.assign(this.cfg, patch); store.set("look", this.cfg); this.apply();
    clearTimeout(this._t);
    this._t = setTimeout(() => api("/api/appearance", { method: "POST", body: Object.fromEntries(Object.entries(this.cfg).filter(([k]) => k !== "bg")) })
      .catch(e => toast(e.message, "err")), 350);
  },
  /* Bild im Browser auf Bildschirmgröße bringen (lange Kante = Bildschirm × Pixeldichte, max. 2560 px) und als WebP
     speichern – so bleibt die Datei klein und die App flüssig, egal wie groß das Original ist. */
  async optimize(file) {
    const img = await createImageBitmap(file);
    const long = Math.max(1920, Math.min(2560, Math.round(Math.max(screen.width, screen.height) * (window.devicePixelRatio || 1))));
    const sc = Math.min(1, long / Math.max(img.width, img.height));
    const w = Math.round(img.width * sc), h = Math.round(img.height * sc);
    const cv = document.createElement("canvas"); cv.width = w; cv.height = h;
    cv.getContext("2d").drawImage(img, 0, 0, w, h);
    let url = cv.toDataURL("image/webp", 0.82);
    if (!url.startsWith("data:image/webp")) url = cv.toDataURL("image/jpeg", 0.85);
    return { url, w, h, kb: Math.round(url.length * 0.75 / 1024) };
  },
  /* Weichzeichner einmalig ins Bild rechnen (statt CSS-Filter, der bei Software-Rendering jedes Bild neu kostet) */
  async bake(blur) {
    const img = await createImageBitmap(await (await fetch(`/api/appearance/bg?orig=1&t=${Date.now()}`)).blob());
    const cv = document.createElement("canvas"); cv.width = img.width; cv.height = img.height;
    const x = cv.getContext("2d"), px = blur / 4 * (img.width / Math.max(innerWidth, 1));
    if (px > 0) { x.filter = `blur(${px}px)`; const m = px * 2; x.drawImage(img, -m, -m, img.width + 2 * m, img.height + 2 * m); }
    else x.drawImage(img, 0, 0);
    let url = cv.toDataURL("image/webp", 0.82);
    if (!url.startsWith("data:image/webp")) url = cv.toDataURL("image/jpeg", 0.85);
    const d = await api("/api/appearance/bg", { method: "POST", body: { data: url } });
    this.cfg = { ...this.cfg, ...d }; store.set("look", this.cfg); this.apply();
  },
  render(box) {
    const g = k => this.get(k);
    const seg = (key, opts) => `<div class="look-seg" data-seg="${key}">${opts.map(([v, l]) => `<button data-v="${v}" class="${String(g(key)) === String(v) ? "on" : ""}">${l}</button>`).join("")}</div>`;
    const slider = (key, label, unit = "%") => `<label class="look-slider"><span>${label}</span><input type="range" min="0" max="100" value="${g(key)}" data-range="${key}"><output>${g(key)}${unit}</output></label>`;
    const custom = !LOOK_ACCENTS.some(([c]) => c === g("accent"));
    box.innerHTML = `
      <div class="card set-group">
        <div class="set-row"><div><div class="lbl">Modus</div><div class="hint">„System“ folgt der Einstellung deines Betriebssystems.</div></div><div></div>
          ${seg("mode", [["dunkel", "Dunkel"], ["hell", "Hell"], ["system", "System"]])}</div>
        <div class="set-row"><div><div class="lbl">Akzentfarbe</div><div class="hint">Knöpfe, Markierungen, aktive Einträge.</div></div><div></div>
          <div class="look-accents">${LOOK_ACCENTS.map(([c, n]) => `<button class="look-acc ${c === g("accent") ? "on" : ""}" style="background:${c}" data-acc="${c}" title="${n}"></button>`).join("")}
            <label class="look-acc-custom ${custom ? "on" : ""}" title="Eigene Farbe" style="${custom ? `box-shadow:0 0 0 2px var(--text)` : ""}"><input type="color" id="lookColor" value="${g("accent")}"></label></div></div>
      </div>
      <div class="ai-sec">Farbschema</div>
      <div class="card set-group"><div class="look-pals">${LOOK_PALETTES.map(([id, n, a, b]) => `<button class="look-pal ${g("palette") === id ? "on" : ""}" data-pal="${id}">
        <div class="look-pal-prev" style="background:${b}"><i style="background:${a}"></i><b style="background:var(--accent)"></b></div>${n}</button>`).join("")}</div>
        <div class="hint ai-note">Im hellen Modus färbt das Schema die Flächen nur leicht ein.</div></div>
      <div class="ai-sec">Hintergrundbild</div>
      <div class="card set-group"><div class="look-bg">
        <div class="look-bg-prev ${this.cfg.bg ? "has" : ""}" id="lookBgPick" style="${this.cfg.bg ? `background-image:url(/api/appearance/bg?v=${this.cfg.bg_v || 0})` : ""}">Bild wählen<br>(JPG, PNG, WebP …)</div>
        <div class="look-sliders">
          <div class="hint" style="margin:0">Wird automatisch auf deine Bildschirmgröße verkleinert und als WebP gespeichert – auch riesige Fotos bremsen die App nicht.</div>
          ${slider("bg_dim", "Abdunkeln")}${slider("bg_blur", "Weichzeichnen")}${slider("panel", "Deckkraft der Flächen")}
          <div style="display:flex;gap:8px"><button class="btn btn--sm" id="lookBgBtn">${icon("download")}${this.cfg.bg ? "Anderes Bild" : "Bild wählen"}</button>
            ${this.cfg.bg ? `<button class="btn btn--sm btn--ghost" id="lookBgDel">Entfernen</button>` : ""}</div>
        </div>
        <input type="file" accept="image/*" id="lookBgFile" hidden>
      </div></div>
      <div class="ai-sec">Ansicht</div>
      <div class="card set-group">
        <div class="set-row"><div><div class="lbl">Größe</div><div class="hint">Schrift und Bedienelemente der ganzen App.</div></div><div></div>
          ${seg("font", [[90, "90 %"], [100, "100 %"], [110, "110 %"], [115, "115 %"]])}</div>
        <div class="set-row"><div><div class="lbl">Ecken</div><div class="hint">Wie rund Karten, Knöpfe und Felder sind.</div></div><div></div>
          ${seg("radius", [["eckig", "Eckig"], ["normal", "Normal"], ["rund", "Rund"]])}</div>
        <div class="set-row"><div><div class="lbl">Abstände</div><div class="hint">Mehr auf einen Blick oder mehr Luft.</div></div><div></div>
          ${seg("density", [["kompakt", "Kompakt"], ["normal", "Normal"], ["luftig", "Luftig"]])}</div>
        <div class="set-row"><div><div class="lbl">Animationen</div><div class="hint">Aus = ruhiger und sparsamer auf schwachen Rechnern.</div></div><div></div>
          <label class="switch"><input type="checkbox" id="lookMotion" ${g("motion") ? "checked" : ""}><span class="track"></span></label></div>
        <div class="set-row"><div><div class="lbl">Seitenleiste</div><div class="hint">Auch über den Knopf oben neben dem Logo umschaltbar.</div></div><div></div>
          ${`<div class="look-seg" id="lookSide"><button data-v="0" class="${store.get("sideMin", false) ? "" : "on"}">Ausgeklappt</button><button data-v="1" class="${store.get("sideMin", false) ? "on" : ""}">Nur Icons</button></div>`}</div>
        <div class="set-row"><div><div class="lbl">Zurücksetzen</div><div class="hint">Alles auf den Standard (Dunkel, Graphit, Mint). Das Hintergrundbild bleibt.</div></div><div></div>
          <button class="btn btn--sm btn--ghost" id="lookReset">Zurücksetzen</button></div>
      </div>
      <div class="ai-sec">Schwebe-Icon & Statusleiste</div><div id="compBox"></div>`;
    hydrateIcons(box);
    Companion.render($("#compBox", box));
    const again = () => this.render(box);
    $$("[data-seg]", box).forEach(sg => $$("button", sg).forEach(b => b.onclick = () => {
      const k = sg.dataset.seg; this.set({ [k]: k === "font" ? +b.dataset.v : b.dataset.v }); again();
    }));
    $$("[data-acc]", box).forEach(b => b.onclick = () => { this.set({ accent: b.dataset.acc }); again(); });
    $("#lookColor", box).oninput = e => this.set({ accent: e.target.value });
    $("#lookColor", box).onchange = again;
    $$("[data-pal]", box).forEach(b => b.onclick = () => { this.set({ palette: b.dataset.pal }); again(); });
    $$("[data-range]", box).forEach(r => {
      const k = r.dataset.range, root = document.documentElement;
      r.oninput = () => {
        r.nextElementSibling.textContent = r.value + "%";
        if (k === "bg_blur") {   // Live-Vorschau: unbearbeitetes Bild + CSS-Filter, bis der Regler losgelassen wird
          root.dataset.bglive = ""; root.style.setProperty("--bg-url", `url(/api/appearance/bg?orig=1&v=${this.cfg.bg_v || 0})`);
          root.style.setProperty("--bg-blur-live", r.value / 4 + "px"); this.cfg.bg_blur = +r.value;
        } else this.set({ [k]: +r.value });
      };
      if (k === "bg_blur") r.onchange = async () => {
        this.set({ bg_blur: +r.value });
        try { await this.bake(+r.value); } catch (e) { toast(e.message, "err"); }
        delete root.dataset.bglive;
      };
    });
    $("#lookMotion", box).onchange = e => this.set({ motion: e.target.checked });
    $$("#lookSide button", box).forEach(b => b.onclick = () => { Side.set(b.dataset.v === "1"); again(); });
    $("#lookReset", box).onclick = () => { this.set({ ...this.defaults }); again(); toast("Darstellung zurückgesetzt"); };
    const file = $("#lookBgFile", box);
    $("#lookBgPick", box).onclick = $("#lookBgBtn", box).onclick = () => file.click();
    file.onchange = async () => {
      const f = file.files[0]; if (!f) return;
      try {
        const o = await this.optimize(f);
        await api("/api/appearance/bg", { method: "POST", body: { data: o.url, original: true } });
        await this.bake(this.get("bg_blur")); again();
        toast(`Hintergrund optimiert: ${o.w}×${o.h}, ${o.kb} KB (Original ${Math.round(f.size / 1024)} KB)`);
      } catch (e) { toast("Bild nicht verwendbar: " + e.message, "err"); }
    };
    const del = $("#lookBgDel", box); if (del) del.onclick = async () => {
      const d = await api("/api/appearance/bg", { method: "DELETE" }); this.cfg = { ...this.cfg, ...d }; store.set("look", this.cfg); this.apply(); again();
    };
  },
};
Look.apply();
const Companion = {
  async render(box) {
    const c = await api("/api/companion").catch(() => null);
    if (!c || !document.body.contains(box)) return;
    const dis = c.available ? "" : "disabled";
    box.innerHTML = `<div class="card set-group">
      ${c.available ? "" : `<div class="ai-warn" style="margin:14px 18px 0">${icon("info")}<span>${esc(c.why)}</span></div>`}
      <div class="set-row"><div><div class="lbl">Symbol in der Statusleiste</div><div class="hint">Rechtsklick: Erkennen, Öffnen, Schwebe-Icon, Beenden. Solange es an ist, schließt das Fenster-✕ die App nicht, sondern legt sie in die Statusleiste – Erkennen geht weiter.</div></div><div></div>
        <label class="switch"><input type="checkbox" id="compTray" ${c.tray ? "checked" : ""} ${dis}><span class="track"></span></label></div>
      <div class="set-row"><div><div class="lbl">Schwebe-Icon</div><div class="hint">Kleines Icon, das immer im Vordergrund bleibt. <b>Klick</b> = Musik im Hintergrund erkennen · <b>Maus drüber</b> = „Erkennen“ / „App öffnen“ · <b>Ziehen</b> = verschieben · <b>Rechtsklick</b> = Menü. Nutzt die Quelle aus „Erkennen“.</div></div><div></div>
        <label class="switch"><input type="checkbox" id="compBubble" ${c.bubble ? "checked" : ""} ${dis}><span class="track"></span></label></div>
    </div>`;
    hydrateIcons(box);
    const save = async patch => { try { await api("/api/companion", { method: "POST", body: patch }); } catch (e) { toast(e.message, "err"); } this.render(box); };
    const t = $("#compTray", box), b = $("#compBubble", box);
    if (t) t.onchange = () => save({ tray: t.checked });
    if (b) b.onchange = () => save({ bubble: b.checked });
  },
};
matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => { if (Look.get("mode") === "system") Look.apply(); });

/* ---------- KI-Anbieter */
const AI = {
  tried: new Set(), failed: {},   // failed: {anbieter: Fehlertext} vom letzten Abruf
  found: null,                    // Ergebnis der Suche nach lokaler KI (einmal pro Sitzung)
  async render(box) {
    const [d, found] = await Promise.all([api("/api/ai").catch(() => null),
      AI.found ? Promise.resolve(AI.found) : api("/api/ai/detect").catch(() => ({ programme: {}, server: [] }))]);
    AI.found = found;
    if (!d || !document.body.contains(box)) return;
    const P = Object.fromEntries(d.providers.map(p => [p.id, p]));
    const use = d.use || [];
    const on = use.length > 0;
    const state = p => p.id === "lokal" ? (p.ready[0] ? ["on", "bereit – läuft auf deinem Rechner"] : ["", p.ready[1]])
      : p.id === "eigen" ? (d.eigen_url ? (AI.failed.eigen ? ["warn", "nicht erreichbar"] : ["on", d.eigen_url]) : ["", "Adresse fehlt"])
      : p.cli ? (!p.installed ? ["", "nicht installiert"] : !p.consented ? ["warn", "gefunden – Zustimmung fehlt"] : ["on", "bereit"])
      : !p.has_key ? ["", "kein Key"] : AI.failed[p.id] ? ["warn", "Key ungültig? Modelle nicht abrufbar"] : !p.consented ? ["warn", "Key da – Zustimmung fehlt"]
      : ["on", p.model_list ? `bereit · ${p.model_list.length} Modelle` : "bereit"];
    const modelOpts = p => {
      const list = p.model_list || [];
      const opt = m => `<option value="${esc(m)}" ${m === p.model ? "selected" : ""}>${esc(m)}</option>`;
      const stable = list.filter(m => !/preview|exp|beta/.test(m)), prev = list.filter(m => /preview|exp|beta/.test(m));
      const extra = p.model && !list.includes(p.model) ? opt(p.model) : "";
      if (!list.length) return extra || `<option value="">${AI.failed[p.id] ? "– Abruf fehlgeschlagen –" : p.cli ? "Standard des Programms" : p.has_key || p.id === "eigen" ? "– wird abgerufen –" : "– erst Key speichern –"}</option>`;
      return (p.cli ? `<option value="" ${!p.model ? "selected" : ""}>Standard des Programms</option>` : "") + extra +
        (prev.length ? `<optgroup label="Stabil">${stable.map(opt).join("")}</optgroup><optgroup label="Vorschau – kann sich ändern">${prev.map(opt).join("")}</optgroup>` : stable.map(opt).join(""));
    };
    const useSwitch = p => `<label class="ai-use" title="Diese KI benutzen"><span>Benutzen</span><label class="switch"><input type="checkbox" data-use ${use.includes(p.id) ? "checked" : ""} ${p.cli && !p.installed ? "disabled" : ""}><span class="track"></span></label></label>`;
    const consent = p => `<label class="ai-consent"><label class="switch"><input type="checkbox" data-consent ${p.consented ? "checked" : ""}><span class="track"></span></label>
      <span class="hint">Ich stimme zu, dass Künstler, Titel, Album, Tags und Genre-Ergebnis (bei Playlists die Songliste) an ${esc(p.name.replace(/ \(.*\)$/, ""))} gehen. Kein Ton, keine Konten. Es gelten <a href="${esc(p.terms)}" target="_blank" rel="noopener">Bedingungen</a> und <a href="${esc(p.privacy)}" target="_blank" rel="noopener">Datenschutz</a> des Anbieters.${p.id === "gemini" ? " Bei kostenlosen Gemini-Keys kann Google Eingaben zur Verbesserung nutzen (außerhalb von EWR/UK/CH)." : ""}</span></label>`;
    const head = p => `<div class="ai-prov-head"><span class="status-dot ${state(p)[0]}"></span><b>${esc(p.name)}</b><span class="cell-sub">${esc(state(p)[1])}</span>${useSwitch(p)}</div>`;
    const modelField = (p, reload = true) => `<label class="ai-field"><span>Modell ${reload ? `<button class="linkbtn" data-reload title="Liste neu vom Anbieter holen">neu abrufen</button>` : ""}</span>
      <select class="select" data-model ${p.model_list || p.cli ? "" : "disabled"}>${modelOpts(p)}</select></label>`;
    const keyRow = p => `<div class="ai-prov ${use.includes(p.id) ? "is-active" : ""}" data-p="${p.id}">${head(p)}
      <div class="ai-prov-body">
        <label class="ai-field"><span>API-Key <a href="${esc(p.keys_url)}" target="_blank" rel="noopener">erstellen ↗</a></span>
          <span class="ai-inline"><input class="input" type="password" data-key placeholder="${p.has_key ? "gespeichert ••••  – zum Ändern neu eingeben" : "Key einfügen"}" autocomplete="off">
          <button class="btn btn--sm" data-keysave>Speichern</button>${p.has_key ? `<button class="btn btn--sm btn--ghost" data-keydel title="Key löschen">Löschen</button>` : ""}</span></label>
        ${modelField(p, p.has_key)}${consent(p)}
      </div></div>`;
    const cliRow = p => `<div class="ai-prov ${use.includes(p.id) ? "is-active" : ""}" data-p="${p.id}">${head(p)}
      <div class="ai-prov-body"><div class="hint ai-field">${esc(p.info)} Kein Key nötig – das Programm meldet sich selbst an (Abo oder eigener Key, je nach Einrichtung).</div>
        ${modelField(p, false)}${consent(p)}</div></div>`;
    const clis = d.providers.filter(p => p.cli);
    const missing = clis.filter(p => !p.installed);
    const servers = found.server || [];
    const pos = id => use.indexOf(id);
    box.innerHTML = `<div class="card set-group ai-top">
      <div class="set-row"><div><div class="lbl"><span class="status-dot ${d.ready[0] ? "on" : ""}"></span>Benutzte KI${use.length > 1 ? "s" : ""}</div>
        <div class="hint">${on ? (d.ready[0] ? "Bereit." : esc(d.ready[1])) : "Keine KI eingeschaltet – unten bei einem Anbieter „Benutzen“ einschalten."}</div></div><div></div><div></div></div>
      ${on ? `<div class="ai-order">${use.map((id, n) => `<div class="ai-chip" data-p="${id}"><span class="ai-rank">${n + 1}</span><span class="status-dot ${state(P[id])[0]}"></span>${esc(P[id].name)}<span class="cell-sub">${esc(P[id].model || "")}</span>
          <span class="ai-chip-btns"><button class="icon-btn" data-up ${n === 0 ? "disabled" : ""} title="Nach vorne">↑</button><button class="icon-btn" data-down ${n === use.length - 1 ? "disabled" : ""} title="Nach hinten">↓</button><button class="icon-btn" data-off title="Nicht mehr benutzen">✕</button></span></div>`).join("")}</div>` : ""}
      ${use.length > 1 ? `<div class="ai-modes">
        <label class="ai-mode ${d.combine === "reihe" ? "on" : ""}"><input type="radio" name="aiComb" value="reihe" ${d.combine === "reihe" ? "checked" : ""}><b>Nacheinander</b><span>Nr. 1 antwortet. Fällt sie aus (Limit, offline, Fehler), springt die nächste ein. Kosten und Tempo wie bei einer KI.</span></label>
        <label class="ai-mode ${d.combine === "abstimmung" ? "on" : ""}"><input type="radio" name="aiComb" value="abstimmung" ${d.combine === "abstimmung" ? "checked" : ""}><b>Zusammen abstimmen</b><span>Alle werden gleichzeitig gefragt, übernommen wird nur, worauf sich die Mehrheit einigt.</span></label>
      </div>
      ${d.combine === "abstimmung" ? `<div class="ai-warn">${icon("info")}<span>Kann zu Problemen führen: ${use.length}× Kosten bzw. Limits, so langsam wie die langsamste KI, und KIs widersprechen sich – dann wird nichts geändert bzw. das Ergebnis als unsicher markiert. Bei 2 KIs müssen beide zustimmen.</span></div>` : ""}` : ""}
    </div>

    <div class="ai-sec">Auf diesem Rechner gefunden <button class="linkbtn" id="aiRescan">erneut suchen</button></div>
    <div class="card set-group ai-provs">
      <div class="ai-prov ${use.includes("lokal") ? "is-active" : ""}" data-p="lokal">${head(P.lokal)}<div class="hint ai-sub">${esc(P.lokal.info)}</div></div>
      ${clis.filter(p => p.installed).map(cliRow).join("")}
      <div class="ai-prov ${use.includes("eigen") ? "is-active" : ""}" data-p="eigen">${head(P.eigen)}
        <div class="ai-prov-body"><label class="ai-field"><span>Adresse (OpenAI-kompatibel)</span><span class="ai-inline"><input class="input" id="aiUrl" value="${esc(d.eigen_url || "")}" placeholder="http://127.0.0.1:8080/v1"><button class="btn btn--sm" id="aiUrlSave">Speichern</button></span></label>
        ${d.eigen_url ? modelField(P.eigen) : `<div></div>`}
        ${servers.length ? `<div class="ai-found">${servers.map(s => `<span>${icon("check")}<b>${esc(s.name)}</b> läuft · ${esc(s.url)}${s.models.length ? ` · ${s.models.length} Modell${s.models.length > 1 ? "e" : ""}` : ""}</span>${s.url === d.eigen_url ? `<em>verbunden</em>` : `<button class="btn btn--sm btn--ghost" data-take="${esc(s.url)}">Übernehmen</button>`}`).join("")}</div>`
          : `<div class="hint ai-found-none">Kein lokaler Server gefunden (gesucht: llama-server :8080, Ollama :11434, LM Studio :1234, Jan :1337).</div>`}</div></div>
      ${missing.length ? `<div class="hint ai-note">Nicht installiert: ${missing.map(p => esc(p.name.replace(/ \(.*\)$/, ""))).join(", ")} – wird automatisch erkannt, sobald vorhanden.</div>` : ""}
    </div>

    <div class="ai-sec">Cloud mit eigenem API-Key</div>
    <div class="card set-group ai-provs">
      ${["gemini", "claude", "openai"].map(id => keyRow(P[id])).join("")}
      <div class="hint ai-note">Kosten rechnet der Anbieter direkt mit dir ab. Keys bleiben nur auf diesem Rechner (Konfigurationsdatei, nur für dich lesbar).</div>
    </div>
    ${on ? `<div class="ai-sec">Einsatz</div><div class="card set-group">
      <div class="set-row"><div><div class="lbl">Automatisch nach jeder Erkennung</div><div class="hint">Genre/Subgenre nachfragen, wenn die Tags nicht reichen. Nutzt immer nur eine KI (Reihenfolge oben).${P[use[0]]?.cloud ? " Bei Cloud-Anbietern standardmäßig aus – kann Geld kosten." : ""}</div></div><div></div>
        <label class="switch"><input type="checkbox" id="aiAuto" ${d.auto_genre ? "checked" : ""}><span class="track"></span></label></div>
      <div class="set-row"><div><div class="lbl">Beim Sortieren mitprüfen</div><div class="hint">Unter „Dienste“ kontrolliert die KI die Genres der Playlist und korrigiert nur, wo sie sich sicher ist${d.combine === "abstimmung" && use.length > 1 ? " – bei „Zusammen“ nur, wo die Mehrheit zustimmt" : ""}.</div></div><div></div>
        <label class="switch"><input type="checkbox" id="aiReview" ${d.review ? "checked" : ""}><span class="track"></span></label></div>
      <div class="set-row"><div><div class="lbl">Testen</div><div class="hint">Fragt ${use.length > 1 && d.combine === "abstimmung" ? "alle gewählten KIs" : "die KI"} nach „Wilkinson – Afterglow“.</div></div><div class="cell-sub" id="aiTestOut"></div>
        <button class="btn btn--sm" id="aiTest" ${d.ready[0] ? "" : "disabled"}>${icon("sparkle")}Test</button></div>
    </div>` : ""}`;
    hydrateIcons(box);
    const post = patch => api("/api/ai/settings", { method: "POST", body: patch });
    const save = async patch => { try { await post(patch); } catch (e) { toast(e.message, "err"); } this.render(box); };
    const fetchModels = async (id, refresh) => {
      try { const r = await api(`/api/ai/models/${id}${refresh ? "?refresh=1" : ""}`); delete AI.failed[id]; if (refresh) toast(`${r.models.length} Modelle gefunden`); }
      catch (e) { AI.failed[id] = e.message; toast(`${P[id].name}: ${e.message}`, "err"); }
      this.render(box);
    };
    const setUse = list => save({ use: list });
    $$(".ai-chip", box).forEach(ch => {
      const id = ch.dataset.p, n = pos(id), l = [...use];
      $("[data-up]", ch).onclick = () => { [l[n - 1], l[n]] = [l[n], l[n - 1]]; setUse(l); };
      $("[data-down]", ch).onclick = () => { [l[n + 1], l[n]] = [l[n], l[n + 1]]; setUse(l); };
      $("[data-off]", ch).onclick = () => setUse(use.filter(x => x !== id));
    });
    $$("input[name=aiComb]", box).forEach(r => r.onchange = () => save({ combine: r.value }));
    $("#aiRescan", box).onclick = () => { AI.found = null; this.render(box); };
    $("#aiUrlSave", box).onclick = async () => {
      try { await post({ eigen_url: $("#aiUrl", box).value }); } catch (e) { return toast(e.message, "err"); }
      if ($("#aiUrl", box).value.trim()) fetchModels("eigen", true); else this.render(box);
    };
    $$("[data-take]", box).forEach(b => b.onclick = async () => {
      try { await post({ eigen_url: b.dataset.take }); } catch (e) { return toast(e.message, "err"); }
      toast("Server übernommen"); fetchModels("eigen", true);
    });
    $$(".ai-prov[data-p]", box).forEach(row => {
      const id = row.dataset.p, p = P[id];
      const u = $("[data-use]", row); if (u) u.onchange = () => {
        if (u.checked && p.cloud && !p.consented) toast(`Bitte noch der Datenweitergabe an ${p.name} zustimmen`);
        setUse(u.checked ? [...use, id] : use.filter(x => x !== id));
      };
      const ks = $("[data-keysave]", row); if (ks) ks.onclick = async () => {
        const v = $("[data-key]", row).value.trim(); if (!v) return toast("Bitte erst den Key einfügen", "err");
        ks.disabled = true; ks.textContent = "Prüft …";
        try { await post({ keys: { [id]: v } }); } catch (e) { toast(e.message, "err"); return this.render(box); }
        AI.tried.add(id); toast("Key gespeichert – Modelle werden abgerufen"); fetchModels(id, true);
      };
      const kd = $("[data-keydel]", row); if (kd) kd.onclick = () => { delete AI.failed[id]; save({ keys: { [id]: "" } }).then(() => toast("Key gelöscht")); };
      const rl = $("[data-reload]", row); if (rl) rl.onclick = e => { e.preventDefault(); fetchModels(id, true); };
      const ms = $("[data-model]", row); if (ms) ms.onchange = async () => {
        try { await post({ models: { [id]: ms.value } }); toast("Modell gespeichert"); } catch (e) { toast(e.message, "err"); }
        this.render(box);
      };
      const c = $("[data-consent]", row); if (c) c.onchange = () => save({ consent: { [id]: c.checked } });
      const auto = (p.has_key && !p.cli) || (id === "eigen" && d.eigen_url) || p.cli;
      if (auto && p.installed !== false && !p.model_list && id !== "lokal" && !AI.tried.has(id)) { AI.tried.add(id); fetchModels(id, false); }
    });
    const a = $("#aiAuto", box); if (a) a.onchange = () => save({ auto_genre: a.checked });
    const rv = $("#aiReview", box); if (rv) rv.onchange = () => save({ review: rv.checked });
    const t = $("#aiTest", box); if (t) t.onclick = async () => {
      t.disabled = true; $("#aiTestOut", box).textContent = "Fragt …";
      try { const r = await api("/api/ai/test", { method: "POST" }); const v = r.antwort.abstimmung;
        $("#aiTestOut", box).textContent = v ? Object.entries(v).map(([k, x]) => `${P[k]?.name.split(" ")[0] || k}: ${x}`).join(" · ") + ` → ${r.antwort.genre || "?"} / ${r.antwort.subgenre || "?"}${r.antwort.uneinig ? " (uneinig)" : ""} · ${r.dauer_s} s`
          : `${r.antwort.genre || "?"} / ${r.antwort.subgenre || "?"} · ${r.dauer_s} s`; }
      catch (e) { $("#aiTestOut", box).textContent = ""; toast(e.message, "err"); } t.disabled = false;
    };
  },
  async analyzeTrack(ident, btn) {
    if (btn) { btn.disabled = true; btn.innerHTML = `${icon("sparkle")}Analysiert …`; hydrateIcons(btn.parentElement); }
    try {
      const d = await api("/api/ai/analyze/track", { method: "POST", body: ident });
      const li = (k, v) => v && (!Array.isArray(v) || v.length) ? `<dt>${k}</dt><dd>${esc(Array.isArray(v) ? v.join(", ") : String(v))}</dd>` : "";
      modal({ title: "KI-Analyse", text: `Einschätzung von ${esc(d.anbieter)} – kann falsch sein.${d.known === false ? " Die KI kennt diesen Song nicht sicher." : ""}`,
        wide: true, cancel: null, confirm: "Schließen", onConfirm: () => {},
        body: `<p style="margin:0">${esc(d.beschreibung || "")}</p><dl class="kv">${li("Genre", d.genre)}${li("Subgenre", d.subgenre)}${li("Nische", d.nische)}${li("Stimmung", d.stimmung)}${li("Energie", d.energie)}${li("Tempo", d.tempo)}${li("Ähnliche Künstler", d.aehnliche_kuenstler)}${li("Sicherheit", d.sicherheit != null ? Math.round(d.sicherheit * 100) + " %" : "")}${d.ki_generiert && d.ki_generiert !== "unbekannt" ? li("KI-generiert?", `${d.ki_generiert}${d.ki_begruendung ? " – " + d.ki_begruendung : ""} (Einschätzung der KI, kein Beweis)`) : ""}</dl>` });
    } catch (e) { toast(e.message, "err"); }
    if (btn) { btn.disabled = false; btn.innerHTML = `${icon("sparkle")}KI-Analyse`; hydrateIcons(btn.parentElement); }
  },
};

/* ---------- Link einfügen */
const LinkImp = { job: null, sel: new Set() };
Views.links = async (main) => {
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><h1>Link einfügen</h1><p>Song-, Album- oder Playlist-Link einfügen – SH-Tunebridge liest die Songliste, bestimmt die Genres, du hörst rein und übernimmst, was du willst.</p></div></div>
    <div class="card link-in">
      <input class="input" id="lnUrl" placeholder="Link hier einfügen (Strg+V oder Knopf „Einfügen“) – Spotify, Deezer, TIDAL, Apple Music, YouTube, SoundCloud …" spellcheck="false" autocomplete="off">
      <button class="btn" id="lnPaste" title="Link aus der Zwischenablage einfügen und gleich analysieren">${icon("download")}Einfügen</button>
      <button class="btn btn--primary" id="lnGo">${icon("search")}Analysieren</button>
      <label class="btn btn--ghost" title="Playlist-Export von Apple Music/iTunes (.xml/.txt), Google Takeout (YouTube Music), Exportify, TuneMyMusic, Soundiiz (.csv) oder .m3u">
        ${icon("upload")}Datei<input type="file" id="lnFile" accept=".xml,.txt,.csv,.m3u,.m3u8" hidden></label>
    </div>
    <div class="cell-sub" style="margin:8px 2px 0;white-space:normal">Gelesen werden nur Titel, Künstler, Album und ISRC über die offiziellen Schnittstellen – nie Musik heruntergeladen. Hörproben (30 s) nur, wo Deezer/Apple sie offiziell anbieten.
      Spotify-Links brauchen eine Spotify-Verbindung (nur eigene Playlists), YouTube-Playlists einen eigenen YouTube-API-Key.
      Auch möglich: <b>Deezer-Profil</b> (öffentliche Lieblingssongs), <b>Last.fm-Profil</b> (Loved Tracks) und <b>Playlist-Dateien</b> –
      so kommen auch Apple-Music- und YouTube-Music-Playlists rein (Export-Funktion des Dienstes bzw. Google Takeout).</div>
    <div id="lnJob"></div>
  </div>`;
  hydrateIcons(main);
  const go = async () => {
    const url = $("#lnUrl").value.trim();
    if (!url) return;
    try { const r = await api("/api/import-link", { method: "POST", body: { url } }); LinkImp.job = r.job; LinkImp.sel = new Set(); pollLink(); }
    catch (e) { toast(e.message, "err"); }
  };
  $("#lnGo").onclick = go;
  $("#lnFile").onchange = async e => {
    const f = e.target.files[0]; e.target.value = "";
    if (!f) return;
    if (f.size > 5 * 1024 * 1024) return toast("Datei ist zu groß (max. 5 MB)", "err");
    const buf = new Uint8Array(await f.arrayBuffer());
    let bin = ""; for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    try {
      const r = await api("/api/import-file", { method: "POST", body: { name: f.name, data: btoa(bin) } });
      toast(`${r.count} Songs aus „${f.name}“ gelesen`); LinkImp.job = r.job; LinkImp.sel = new Set(); pollLink();
    } catch (err) { toast(err.message, "err"); }
  };
  $("#lnUrl").onkeydown = e => e.key === "Enter" && go();
  // Eingefügter Link (Strg+V, Rechtsklick › Einfügen oder Knopf) -> gleich analysieren
  const auto = () => setTimeout(() => { const v = firstUrl($("#lnUrl").value); if (/^https?:\/\//.test(v)) { $("#lnUrl").value = v; go(); } }, 30);
  $("#lnUrl").addEventListener("paste", auto);
  $("#lnUrl").addEventListener("tb-paste", auto);
  $("#lnPaste").onclick = async () => {
    const t = await Clip.read();
    if (!t.trim()) return toast("Zwischenablage ist leer – kopiere zuerst einen Link", "err");
    $("#lnUrl").value = ""; Clip.insert($("#lnUrl"), firstUrl(t));
  };
  if (LinkImp.job) pollLink();
};

async function pollLink() {
  const box = $("#lnJob");
  if (!box || !LinkImp.job) return;
  const j = await api(`/api/import-link/${LinkImp.job}`).catch(() => null);
  if (!j) { LinkImp.job = null; box.innerHTML = ""; return; }
  const running = !["done", "error", "cancelled"].includes(j.state);
  if (running) {
    const pct = j.total ? Math.round(j.done / j.total * 100) : 0;
    box.innerHTML = `<div class="card t-job"><div class="t-job-head"><b>${esc(j.name || "Lese Link …")}</b><button class="btn btn--sm btn--ghost" id="lnCancel">Abbrechen</button></div>
      <div class="llm-bar"><div style="width:${pct}%"></div></div><div class="llm-job">${j.state === "loading" ? "Lese Songliste …" : `Bestimme Genres … ${j.done} / ${j.total}`}</div></div>`;
    $("#lnCancel").onclick = () => api(`/api/import-link/${j.id}/cancel`, { method: "POST" });
    return setTimeout(pollLink, 800);
  }
  if (j.state !== "done") { box.innerHTML = `<div class="notice">${icon("info")}<div>${esc(j.state === "error" ? j.error : "Abgebrochen")}</div></div>`; hydrateIcons(box); return; }
  const dist = Object.entries(j.verteilung || {});
  const aiCount = j.items.filter(x => ["hinweis", "wahrscheinlich", "markiert_ki"].includes(x.ai?.status)).length;
  const plats = (await api("/api/platforms").catch(() => [])).filter(p => p.connected);
  box.innerHTML = `<div class="card" style="margin-top:14px">
    <div class="t-job-head"><b>${esc(j.name)}</b><span class="cell-sub">${esc(j.service === "datei" ? "Datei" : j.service === "lastfm" ? "Last.fm" : SVC_NAME(j.service))} · ${j.items.length} Songs${j.cut ? ` (nur die ersten ${j.items.length})` : ""}</span></div>
    <div class="ln-dist">${dist.map(([g, n]) => `<span class="chip">${g === "unbekannt" ? "" : `<span class="dot" style="background:${genreColor(g)}"></span>`}${esc(g)} · ${n}</span>`).join("")}
      ${aiCount ? `<span class="chip chip--ai" title="Hinweise aus Community-Tags/Angaben – kein Beweis">${icon("sparkle")}${aiCount}× Hinweis auf KI-Musik</span>` : ""}</div>
    <div class="ln-actions">
      <label class="cons-check" style="margin-right:auto"><input type="checkbox" id="lnAll"><span>Alle auswählen</span></label>
      <button class="btn btn--sm btn--ghost" id="lnAi">${icon("sparkle")}KI-Analyse der Liste</button>
      <select class="select" id="lnDst"><option value="local">SH-Tunebridge (lokal)</option>${plats.map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select>
      <select class="select" id="lnMode"><option value="pl">als neue Playlist</option><option value="like">zu Lieblingssongs</option></select>
      <input class="input" id="lnName" value="${esc(j.name)}" placeholder="Name" style="max-width:220px">
      <button class="btn btn--primary btn--sm" id="lnAdd">${icon("plus")}Übernehmen</button>
    </div>
    <div id="lnAiOut"></div>
    <div class="li-list">${j.items.map((t, i) => trackLine({ ...t, preview_url: t.preview_url || `deezer:${t.artist}|${t.title}`, ids: { ...(t.ids || {}), ...(t.deezer ? { deezer: t.deezer } : {}) } },
      `<input type="checkbox" class="ln-sel" data-i="${i}" ${LinkImp.sel.has(i) ? "checked" : ""}>`) .replace('<div class="li-genre">', `<div class="li-genre">${aiChip(t.ai)}`)).join("")}</div>
    <div id="tJob"></div></div>`;
  hydrateIcons(box); Player.sync();
  $$(".ln-sel", box).forEach(c => c.onchange = () => c.checked ? LinkImp.sel.add(+c.dataset.i) : LinkImp.sel.delete(+c.dataset.i));
  $("#lnAll").onchange = e => { $$(".ln-sel", box).forEach(c => { c.checked = e.target.checked; c.onchange(); }); };
  $("#lnMode").onchange = e => $("#lnName").classList.toggle("hidden", e.target.value === "like");
  $("#lnDst").onchange = e => { $("#lnMode").classList.toggle("hidden", e.target.value === "local"); if (e.target.value === "local") { $("#lnMode").value = "pl"; $("#lnName").classList.remove("hidden"); } };
  $("#lnDst").onchange({ target: $("#lnDst") });
  $("#lnAdd").onclick = async () => {
    const like = $("#lnMode").value === "like" && $("#lnDst").value !== "local", name = $("#lnName").value.trim();
    if (!like && !name) return toast("Name fehlt", "err");
    const sel = [...LinkImp.sel].sort((a, b) => a - b);
    const src_id = sel.length ? `${j.id}:${sel.join(",")}` : j.id;
    try { const r = await api("/api/transfer", { method: "POST", body: { src: "link", src_id, dst: $("#lnDst").value, name, like } }); Transfer.job = r.job; pollTransfer(); }
    catch (e) { toast(e.message, "err"); }
  };
  $("#lnAi").onclick = async () => {
    const b = $("#lnAi"); b.disabled = true; b.textContent = "Analysiert …";
    try {
      const d = await api(`/api/ai/analyze/link/${j.id}`, { method: "POST" });
      $("#lnAiOut").innerHTML = `<div class="privacy-note" style="margin:10px 0"><p><b>${esc(d.stil || "")}</b></p>
        ${d.stimmung?.length ? `<p>Stimmung: ${esc(d.stimmung.join(", "))}</p>` : ""}
        ${d.passt_nicht?.length ? `<p>Fällt heraus: ${esc(d.passt_nicht.join("; "))}</p>` : ""}
        ${d.aufteilen?.length ? `<p>Aufteilen in: ${d.aufteilen.map(a => `<b>${esc(a.name)}</b> (${esc(a.beschreibung || "")})`).join(", ")}</p>` : ""}
        ${d.empfehlungen?.length ? `<p>Passt auch: ${esc(d.empfehlungen.join(", "))}</p>` : ""}
        <p class="cell-sub">Einschätzung von ${esc(d.anbieter)} – kann falsch sein.</p></div>`;
    } catch (e) { toast(e.message, "err"); }
    b.disabled = false; b.innerHTML = `${icon("sparkle")}KI-Analyse der Liste`; hydrateIcons(b.parentElement);
  };
}

/* ---------- Einwilligungen (erster Start + Einstellungen) */
const PRIVACY_URL = "https://github.com/Bigsmoke002/SH-Tunebridge/blob/main/DATENSCHUTZ.md";
const Consent = {
  LOCAL: [
    ["misses", "Liste „Nicht erkannt / Genre unbekannt“",
      "Speichert Songs, die nicht erkannt wurden oder kein Genre bekommen haben: Datum, Pegel, Art der Quelle (Anwendung/Standard/Gerät), " +
      "Treffer-Kandidaten und – falls erlaubt – was laut Player lief. Damit kannst du (und auf Wunsch der Entwickler) Lücken finden. " +
      "Bleibt auf deinem Rechner, max. 1000 Einträge, jederzeit löschbar."],
    ["player", "Was spielt gerade? (Player-Infos über MPRIS)",
      "Liest lokal Titel, Künstler, Album und Länge aus deinem Player/Browser. Wird genutzt für den Dauer-Modus (Songwechsel sofort bemerken) " +
      "und als Hinweis in der Liste „Nicht erkannt“. Gespeichert wird nur das Nötigste: keine lokalen Dateipfade, Web-Adressen ohne Tracking-Parameter."],
    ["cache", "Song-Speicher & lokale Fingerabdrücke",
      "Merkt sich erkannte Songs samt Genre und kurze Fingerabdrücke (Zahlenwerte, kein Ton). Bekannte Stellen werden dann lokal wiedererkannt – " +
      "das spart Anfragen an Shazam und andere Dienste. Ohne diesen Speicher wird jeder Song jedes Mal online nachgeschlagen."],
  ],
  SERVER: [
    ["misses", "Liste „Nicht erkannt / Genre unbekannt“ senden",
      "Gesendet wird je Eintrag: Datum (ohne Uhrzeit), Art (unerkannt/Genre unbekannt), Art der Quelle, Pegel in dB, Treffer-Kandidaten der Dienste, " +
      "Song (Künstler, Titel, ISRC) bzw. Player-Titel/-Künstler/-Album/Web-Adresse, Genre-Tags, deine Notiz, App-Version. " +
      "Zweck: Erkennung und Genre-Zuordnung verbessern, gemeinsam Lücken analysieren. Nur Einträge ab jetzt; ältere nur, wenn du sie selbst sendest."],
    ["fehler", "Fehlerberichte senden (Debug)",
      "Bei einem Programmfehler: Datum, Bereich (z. B. „erkennen“), Fehlermeldung, Fehlertyp und Programmstelle (Datei:Zeile), App-Version. " +
      "Benutzername, Rechnername, Home-Pfad und Schlüssel werden vorher geschwärzt; gleiche Fehler nur einmal, höchstens 50 in der Warteschlange. " +
      "Zweck: Fehler finden und beheben. Das ausführliche Debug-Protokoll bleibt lokal."],
    ["genres", "Zur Gemeinschafts-Genre-Datenbank beitragen",
      "Je Song, den du eingeordnet hast (Playlist-Analyse oder „Genre festlegen“): Datum, Künstler, Titel, ISRC, Genre, Subgenre und Herkunft " +
      "(Playlist-Name / App / KI / von dir geändert). Nie gesendet: Playlist-Namen, ganze Playlists, Konten. Zweck: eine gemeinsame Genre-Datenbank, " +
      "die erst übernimmt, was mehrere Installationen unabhängig voneinander melden. Nur Einordnungen ab jetzt."],
    ["bibliothek", "Genres meiner Bibliothek beitragen",
      "Je Song, den die App schon kennt (Erkennen, Sortieren, „Alles einlesen“): Datum, Künstler, Titel, ISRC, Genre, Subgenre, Sicherheit. Das Genre wird nur aus " +
      "freien Quellen abgeleitet (MusicBrainz, Angaben im Titel) – nie aus Last.fm-, Deezer- oder Apple-Daten. Auch bereits vorhandene Songs, ohne Obergrenze (pro Abgleich in Portionen). " +
      "Nie Playlist-Namen, Playlists, Konten oder Hörzeiten. Zweck: die Gemeinschafts-Genre-Datenbank vergrößern."],
    ["share", "Playlists teilen (Ende-zu-Ende verschlüsselt)",
      "Nur wenn du unter „Teilen“ Playlists freigibst oder Playlists von Freunden ansiehst: Die Playlists (Titel, Künstler, Album, ISRC, Genre – nie Musik oder Cover) " +
      "werden auf deinem Rechner mit AES-256 verschlüsselt; der Server speichert nur unlesbare Blöcke, eine zufällige Kennung und das Datum der letzten Änderung. " +
      "Keine IP-Adressen, kein Konto. Lesen kann nur, wer deinen Schlüssel hat. Unbenutzte Bereiche werden nach einem Jahr gelöscht."],
    ["verzeichnis", "Öffentliches Playlist-Verzeichnis nutzen",
      "Stöbern lädt die Liste veröffentlichter Playlists vom Server (gesendet wird nur die Suchanfrage). Veröffentlichen geht nur einzeln und mit Bestätigung: " +
      "Name der Playlist, dein selbst gewähltes Pseudonym, Genre, Beschreibung und die Songs (Titel, Künstler, Album, ISRC, Länge, Dienst-IDs – nie Musik oder Cover) " +
      "sind dann für alle sichtbar. Der Server kennt dich nur als Hash deines Installations-Schlüssels; Löschen jederzeit, automatisch nach 12 Monaten ohne Aktualisierung."],
    ["relay", "Handy-Abgleich übers Internet (Ende-zu-Ende verschlüsselt)",
      "Nur für Handys, bei denen du „Unterwegs“ einschaltest: Ist das Handy nicht im selben Netz, tauschen Handy und PC den Abgleich (Erkennungen, Playlist-Änderungen, " +
      "ausgewählte Playlists – nie Audio, Konten oder Schlüssel) über eine verschlüsselte Ablage auf dem Server aus. Der Schlüssel stammt aus eurer Kopplung und verlässt die Geräte nie; " +
      "der Server sieht nur zufällige Kennungen, unlesbare Blöcke und das Datum, keine Konten (Verbindungsdaten wie IP-Adresse protokolliert die Server-Technik höchstens 12 Monate). Dieser PC fragt dafür etwa alle 6 Minuten nach. Ablagen werden beim Abschalten gelöscht, sonst nach einem Jahr ohne Nutzung."],
    ["songs", "Erkannte Songs für die Genre-Analyse senden",
      "Je erkanntem Song: Datum, Künstler, Titel, ISRC, ermitteltes Genre/Subgenre/Nische, Sicherheit, Genre-Quelle, genutzter Dienst, Tempo-Faktor, KI-Musik-Hinweis. " +
      "Kein Hörverlauf mit Uhrzeit, keine Playlists, kein Konto. Zweck: Genre-Zuordnung und Song-Analyse für alle verbessern."],
  ],
  LOAD: [
    ["genredb", "Gemeinschafts-Genre-Datenbank laden",
      "Lädt einmal am Tag eine signierte Datei (nur Song → Genre, keine Nutzerdaten) von https://shtunebridge.bs002.de und nutzt sie beim Erkennen und Sortieren. " +
      "Gesendet wird nichts – technisch sieht der Server nur die Anfrage mit deiner IP-Adresse. Die Signatur wird vor der Nutzung geprüft. " +
      "Vorausgewählt, weil es die Genre-Erkennung deutlich verbessert (berechtigtes Interesse); einfach abwählen, wenn du das nicht möchtest."],
  ],
  async dialog(first = false) {
    const c = await api("/api/consent");
    const comp = first ? await api("/api/companion").catch(() => null) : null;
    const compRow = (id, lbl, hint) => `<div class="cons-row">
        <label class="switch"><input type="checkbox" data-comp="${id}" checked><span class="track"></span></label>
        <div><div class="lbl">${esc(lbl)}</div><div class="hint">${esc(hint)}</div></div></div>`;
    const compSec = comp?.available ? `<div class="cons-h">4 · Bedienung am Desktop <span>(jederzeit unter Einstellungen → Darstellung änderbar)</span></div>
      ${compRow("bubble", "Schwebe-Icon anzeigen", "Kleines Icon, das immer im Vordergrund bleibt: ein Klick erkennt die Musik, die gerade am Rechner läuft. Lässt sich frei verschieben.")}
      ${compRow("tray", "Symbol in der Statusleiste (Tray)", "Symbol neben der Uhr: Erkennen, App öffnen, Beenden. Solange es an ist, legt das Fenster-✕ die App dorthin, statt sie zu beenden.")}` : "";
    const sw = (group, [id, lbl, hint]) => `<div class="cons-row">
        <label class="switch"><input type="checkbox" data-c="${group}.${id}" ${c[group][id] ? "checked" : ""}><span class="track"></span></label>
        <div><div class="lbl">${esc(lbl)}</div><div class="hint">${esc(hint)}</div></div></div>`;
    const body = `<div class="cons">
      <p class="cons-intro">SH-Tunebridge sammelt so wenig wie möglich – und nur anonym bzw. pseudonym. Hier legst du einmal fest, was erlaubt ist.
        Alles lässt sich später unter <b>Einstellungen → Datenschutz</b> ändern oder widerrufen.</p>
      <div class="cons-h">1 · Auf diesem Rechner speichern <span>(nur lokal, verlässt den Rechner nicht)</span></div>
      ${this.LOCAL.map(r => sw("local", r)).join("")}
      <div class="cons-h">2 · Vom Entwickler laden <span>(nichts wird gesendet – vorausgewählt, abwählbar)</span></div>
      ${this.LOAD.map(r => sw("server", r)).join("")}
      <div class="cons-h">3 · An den Entwickler senden <span>(freiwillig – standardmäßig aus)</span></div>
      <div class="cons-box">
        <label class="cons-check"><input type="checkbox" data-c="server.domain" ${c.server.domain ? "checked" : ""}>
          <span>Ich erlaube, dass die unten ausgewählten Daten <b>ohne Namen, Konto, Rechnernamen oder Ton</b> ausschließlich an
          <code>https://${esc(c.domain)}</code> gesendet werden (verschlüsselt per HTTPS; Server des Entwicklers in Deutschland).</span></label>
        <div class="hint" style="margin:6px 0 2px 26px">Zur Einordnung: Die Einträge tragen eine zufällige Installations-Kennung (Hash eines Schlüssels, der nur auf deinem Rechner liegt) –
          damit kannst <b>nur du</b> deine Daten dort einsehen und löschen. Sie verrät nicht, wer du bist (pseudonym). Darum ist das Senden nur <b>teilweise anonym</b>:
          Die Annahme-Software speichert keine IP-Adressen, aber die vorgeschaltete Firewall (pfSense) und der Proxy (Nginx Proxy Manager)
          protokollieren IP-Adresse, Zeitpunkt und Anfrage bis zu 12 Monate – zum Schutz vor DDoS-Angriffen, Hacking, Bots und Spam.
          Deine Einträge werden höchstens 12 Monate aufbewahrt.</div>
        <div class="cons-srv ${c.server.domain ? "" : "off"}">${this.SERVER.map(r => sw("server", r)).join("")}
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:6px"><button type="button" class="btn btn--sm btn--ghost" data-cons-none>Alle abwählen</button><button type="button" class="btn btn--sm" data-cons-all>Alle erlauben</button></div></div>
      </div>
      ${compSec}
      <div class="cons-h">${compSec ? 5 : 4} · Datenschutzerklärung</div>
      <label class="cons-check"><input type="checkbox" data-c="privacy" ${c.privacy_at ? "checked" : ""}>
        <span>Ich habe die <a href="${PRIVACY_URL}" target="_blank" rel="noopener">Datenschutzerklärung</a> gelesen und bin einverstanden.
        Kontakt für Datenschutzanfragen: <a href="mailto:info@smokes-hub.de">info@smokes-hub.de</a> · Discord: Bigsmoke002.de</span></label>
    </div>`;
    modal({
      title: first ? "Willkommen bei SH-Tunebridge" : "Datenschutz & Einwilligungen",
      text: first ? "Bevor es losgeht: einmal kurz festlegen, welche Daten erhoben werden dürfen." : "",
      body, wide: true, sticky: first, cancel: first ? null : "Abbrechen", confirm: "Speichern",
      onConfirm: async box => {
        const v = k => $(`[data-c="${k}"]`, box).checked, v2 = k => $(`[data-comp="${k}"]`, box).checked;
        if (!v("privacy")) { toast("Bitte die Datenschutzerklärung bestätigen", "err"); throw { silent: true }; }
        const body = { privacy: true, local: {}, server: { domain: v("server.domain") } };
        this.LOCAL.forEach(([id]) => body.local[id] = v(`local.${id}`));
        this.SERVER.forEach(([id]) => body.server[id] = body.server.domain && v(`server.${id}`));
        this.LOAD.forEach(([id]) => body.server[id] = v(`server.${id}`));
        await api("/api/consent", { method: "POST", body });
        if (compSec) await api("/api/companion", { method: "POST", body: { bubble: v2("bubble"), tray: v2("tray") } })
          .catch(e => toast(e.message, "err"));
        toast("Gespeichert");
        const pb = $("#privacyBox"); if (pb) Privacy.render(pb);
        if (body.server.genredb) toast("Genre-Datenbank wird im Hintergrund geladen");
      },
    });
    // „Speichern“ erst, wenn die Datenschutzerklärung bestätigt ist (vorher sichtbar gesperrt)
    const priv = $('[data-c="privacy"]'), ok = $('#modal [data-m="ok"]');
    const gate = () => { if (ok) { ok.disabled = !priv.checked; ok.title = priv.checked ? "" : "Erst die Datenschutzerklärung bestätigen"; } };
    priv.addEventListener("change", gate); gate();
    const dom = $('[data-c="server.domain"]');
    const sync = () => {
      $(".cons-srv").classList.toggle("off", !dom.checked);
      $$(".cons-srv input").forEach(i => { i.disabled = !dom.checked; if (!dom.checked) i.checked = false; });
    };
    dom.onchange = sync; sync();
    $("[data-cons-all]").onclick = () => { if (!dom.checked) { dom.checked = true; sync(); } $$(".cons-srv input").forEach(i => i.checked = true); };
    $("[data-cons-none]").onclick = () => $$(".cons-srv input").forEach(i => i.checked = false);
  },
  async checkFirstStart() {
    const c = await api("/api/consent").catch(() => null);
    if (c?.needs_onboarding) this.dialog(true);
  },
};

/* ---------- Datenschutz */
const Privacy = {
  async render(box) {
    const [d, c] = await Promise.all([api("/api/privacy").catch(() => null), api("/api/consent").catch(() => null)]);
    if (!d || !c || !document.body.contains(box)) return;
    const allowed = Consent.SERVER.filter(([id]) => c.server.domain && c.server[id]).map(([, l]) => l.replace(/ senden$/, ""));
    const P = d.prefs, raw = d.engines.filter(e => RAW_ENGINES[e]).map(e => RAW_ENGINES[e]).join(" / ") || "AudD / ACRCloud";
    const flow = [
      ["Shazam", "Fingerabdruck der Aufnahme – kein hörbares Audio („Als Slowed/Sped-up suchen“ per Knopf: bis zu 3 weitere)", "nur nach Klick auf „Erkennen“"],
      [raw, "Aufnahme-Ausschnitt (Audio)", "nur mit deiner Zustimmung, siehe Schalter"],
      ["Deezer, iTunes-Suche, Last.fm, MusicBrainz", "Künstler + Titel (für Cover, Hörprobe, Genre, Mikro-Genre)", "nach einer Erkennung oder beim Sortieren"],
      ["Spotify, TIDAL, Deezer, Last.fm, YouTube, SoundCloud", "Abruf deiner Playlists und Likes, bei Spotify/TIDAL auf Wunsch neue Playlists anlegen", "unter „Dienste“ und beim automatischen Abgleich (nur verbundene Dienste)"],
      ["Google (YouTube), SoundCloud", "Anmeldung über deine eigene App – Token bleibt auf diesem Rechner", "nur wenn du den Login einrichtest"],
      ["Deezer („Mehr vom Künstler“)", "Kennung des geprüften Songs und seines Künstlers", "beim Öffnen eines Songs"],
      ["YouTube / Spotify („Ersatz-Hörprobe“)", "beim Laden des offiziellen Players: IP-Adresse, Geräteinfos, ggf. Cookies; zum Finden: Titel + Künstler an die YouTube-Suche (eigener Zugang)", "nur nach Einwilligung je Anbieter und nur, wenn Deezer/Apple keine Hörprobe haben"],
      ["Deezer („Entdecken“)", "Suchbegriff bzw. Deezer-Kennung des angetippten Künstlers, Albums oder Genres", "nur beim Suchen und Öffnen unter „Entdecken“; Ergebnis höchstens 1 Stunde im Arbeitsspeicher"],
      ["Deezer („Remixe & Versionen“)", "Titel und Hauptkünstler des Songs", "nur nach Klick auf „Remixe & Versionen suchen“"],
      ["Deezer („Mix erstellen“)", "eingegebener Künstlername bzw. Kennungen der gewählten und ähnlicher Künstler", "nur beim Suchen und Erstellen eines Mixes"],
      ["MusicBrainz, Last.fm („Mix erstellen“ nach Genre)", "nur der Genre-Name als Tag (z. B. „liquid funk“); Last.fm nur mit eigenem Key", "nur beim Erstellen eines Genre-Mixes"],
      ["Genre-Datenbank", "deine Einordnungen bleiben lokal; Playlist-Namen werden nur lokal ausgewertet", c.server.genres ? "Beiträge: mit deiner Einwilligung" : "Beiträge: aus"],
      [`${c.domain} (Gemeinschafts-Genre-Datenbank)`, "nur die Anfrage – Datei ist signiert, enthält nur Song → Genre", c.server.genredb && c.privacy_at ? "einmal am Tag (abwählbar)" : "aus"],
      [`${c.domain} (Playlists teilen)`, "nur verschlüsselte Blöcke – Server kann sie nicht lesen", c.server.share ? "beim Teilen / Ansehen von Freunde-Playlists" : "aus"],
      ["Dein gekoppeltes Handy (Android-App)", "Erkennungen und lokale Playlists – Ende-zu-Ende verschlüsselt, direkt im eigenen Netz, kein Server dazwischen", "nur wenn du unter Einstellungen › Handy das Erkennen der Netzwerke erlaubst, ein Handy koppelst und es am PC zulässt – nur in den dort gewählten Netzen"],
      ["Offizielle Player (YouTube, Spotify, Apple, TIDAL, SoundCloud, Deezer)", "IP-Adresse, Geräteinfos, ggf. Cookies des Anbieters", "erst nach deinem Klick auf „Player laden“"],
      ["Deezer / Apple (Cover, Hörproben)", "deine IP-Adresse beim Laden", "beim Anzeigen/Abspielen"],
      ["TIDAL, Spotify, YouTube, SoundCloud (Übertragen)", "Titel/Künstler zum Suchen, Name der neuen Playlist – YouTube braucht dafür dein extra Schreibrecht", "nur wenn verbunden und du überträgst"],
      ["GitHub", "deine IP-Adresse", "Update-Prüfung stündlich"],
      ["Hugging Face, GitHub", "deine IP-Adresse", "einmalig beim Modell-Download"],
      ["Lokales LLM", "nichts – läuft komplett auf deinem Rechner", ""],
      ["Debug-Protokoll", "nichts – nur lokal; Bericht verschickst du selbst", "standardmäßig aus"],
      ["Song-Speicher & Fingerabdrücke", "nichts – bekannte Songs werden lokal wiedererkannt, spart Anfragen", ""],
      ["Liste „Nicht erkannt“", c.local.misses ? "nur lokal gespeichert" : "abgeschaltet", ""],
      [c.domain, allowed.length ? allowed.join(", ") : "nichts", allowed.length ? "automatisch alle 6 Std., nur mit deiner Einwilligung" : "nur mit deiner Einwilligung"],
    ];
    box.innerHTML = `<div class="card privacy">
      <div class="privacy-flow">${flow.map(([w, what, when]) => `<div class="pf-row"><b>${esc(w)}</b><span>${esc(what)}</span><em>${esc(when)}</em></div>`).join("")}</div>
      <div class="cell-sub" style="white-space:normal;margin-top:10px">Kein Tracking, keine Werbung, kein Konto bei SH-Tunebridge. Aufnahmen werden nie gespeichert. Alles andere liegt nur auf deinem Rechner.</div>
    </div>
    <div class="card set-group" style="margin-top:12px" id="embedConsents"></div>
    <div class="card set-group" style="margin-top:12px">
      <div class="set-row"><div><div class="lbl">Einwilligungen</div><div class="hint">Datenschutzerklärung bestätigt ${c.privacy_at ? "am " + new Date(c.privacy_at * 1000).toLocaleDateString("de-DE") : "– noch nicht"} ·
        Senden an ${esc(c.domain)}: ${allowed.length ? esc(allowed.join(", ")) : "aus"}${c.pending_errors ? ` · ${c.pending_errors} Fehlerbericht(e) warten` : ""}</div></div><div></div>
        <div class="row-actions">${allowed.length ? `<button class="btn btn--sm" data-cons-send>${icon("upload")}Jetzt senden</button>` : ""}<button class="btn btn--sm" data-cons-edit>${icon("key")}Ändern</button></div></div>
    </div>
    <div class="card set-group" style="margin-top:12px">
      <div class="set-row"><div><div class="lbl">Audio an ${esc(raw)} senden – Desktop</div><div class="hint">Mehr Treffer. Laufende Sprach-/Videoanrufe würden mitgeschickt.</div></div><div></div>
        <label class="switch"><input type="checkbox" data-pref="send_audio_desktop" ${P.send_audio_desktop ? "checked" : ""}><span class="track"></span></label></div>
      <div class="set-row"><div><div class="lbl">Audio an ${esc(raw)} senden – Mikrofon</div><div class="hint">Nicht empfohlen: Gespräche im Raum würden mitgeschickt (§ 201 StGB).</div></div><div></div>
        <label class="switch"><input type="checkbox" data-pref="send_audio_mic" ${P.send_audio_mic ? "checked" : ""}><span class="track"></span></label></div>
    </div>
    <div class="card set-group" style="margin-top:12px">
      <div class="set-row"><div><div class="lbl">Erkennungsverlauf</div><div class="hint">${d.history} Einträge – deine Playlists bleiben erhalten.</div></div><div></div>
        <button class="btn btn--sm btn--danger" data-clear="history" ${d.history ? "" : "disabled"}>${icon("trash")}Löschen</button></div>
      <div class="set-row"><div><div class="lbl">Zwischenspeicher</div><div class="hint">Song-Speicher, Fingerabdrücke, Hörproben, Tags – siehe „Speicher &amp; Cache“ weiter unten.</div></div><div></div><div></div></div>
    </div>
    <div class="cell-sub" style="white-space:normal;margin:10px 2px 0">Hinweis: Ältere Stände stecken auch in deinen Sicherungen – die löschst du unter Einstellungen › Sicherung.</div>`;
    const embBox = $("#embedConsents", box);
    const drawEmb = () => {
      const ok = Embeds.ok(), ids = Object.keys(ok);
      embBox.innerHTML = `<div class="set-row"><div><div class="lbl">Offizielle Player (eingebettet)</div><div class="hint">${ids.length
        ? `„Immer laden“ erlaubt für: ${ids.map(id => `${esc(Embeds.NAMES[id] || id)} (seit ${new Date(ok[id]).toLocaleDateString("de-DE")})`).join(", ")}`
        : "Kein Anbieter dauerhaft erlaubt – jeder Player lädt erst nach deinem Klick."}</div></div><div></div>
        <div class="row-actions">${ids.length ? `<button class="btn btn--sm" data-emb-reset>${icon("x")}Alle widerrufen</button>` : ""}</div></div>
        <div class="set-row"><div><div class="lbl">Ersatz-Hörprobe (YouTube / Spotify)</div><div class="hint" data-fb-state>…</div></div><div></div>
        <div class="row-actions"><button class="btn btn--sm" data-fb-edit>${icon("pencil")}Ändern</button></div></div>`;
      hydrateIcons(embBox);
      Fallback.get(true).then(fs => {
        const el = $("[data-fb-state]", embBox); if (!el || !fs) return;
        const on = ["youtube", "spotify"].filter(k => fs[k]);
        el.textContent = on.length ? `Erlaubt für: ${on.map(k => `${Embeds.NAMES[k]} (seit ${new Date(fs.at[k] * 1000).toLocaleDateString("de-DE")})`).join(", ")} – nur wenn Deezer/Apple keine Hörprobe haben, nur sichtbar eingebettet.`
          : "Aus – ohne Hörprobe bei Deezer/Apple zeigt die App keinen Ersatz-Player.";
      });
      $("[data-fb-edit]", embBox).onclick = () => Fallback.dialog(() => drawEmb());
      const rb = $("[data-emb-reset]", embBox);
      if (rb) rb.onclick = () => { store.set("embedOk", {}); toast("Einwilligungen für Player widerrufen"); drawEmb(); };
    };
    drawEmb();
    hydrateIcons(box);
    $("[data-cons-edit]", box).onclick = () => Consent.dialog(false);
    const sendBtn = $("[data-cons-send]", box);
    if (sendBtn) sendBtn.onclick = async () => {
      sendBtn.disabled = true;
      try { const r = await api("/api/consent/send-now", { method: "POST" }); const n = Object.values(r.gesendet).reduce((a, b) => a + b, 0);
        toast(n ? `${n} Einträge gesendet` : "Nichts Neues zu senden"); this.render(box); }
      catch (e) { toast(e.message, "err"); sendBtn.disabled = false; }
    };
    $$("[data-pref]", box).forEach(i => i.onchange = () => { savePrefs({ [i.dataset.pref]: i.checked }); toast(i.checked ? "Audio wird mitgesendet" : "Nur noch Shazam-Fingerabdruck"); });
    const label = { history: "Erkennungsverlauf löschen?", previews: "Hörproben-Zwischenspeicher leeren?", cache: "Zwischenspeicher leeren?" };
    $$("[data-clear]", box).forEach(b => b.onclick = () => modal({ title: label[b.dataset.clear], text: "Das lässt sich nicht rückgängig machen (außer über eine Sicherung).", confirm: "Löschen", danger: true,
      onConfirm: async () => { await api("/api/privacy/clear", { method: "POST", body: { [b.dataset.clear]: true } }); toast("Gelöscht"); refreshMeta(); this.render(box); } }));
  },
};

const Storage = {
  async render(box) {
    const d = await api("/api/storage").catch(() => null);
    if (!d || !document.body.contains(box)) return;
    const total = d.rows.reduce((a, r) => a + r.bytes, 0);
    const sv = d.saved || {};
    box.innerHTML = `<div class="card">
      <div class="stor-top">
        <div><div class="stor-big">${fmtSize(d.db_bytes)}</div><div class="cell-sub">Datenbank</div></div>
        <div><div class="stor-big">${(d.ram?.count || 0).toLocaleString("de-DE")}</div><div class="cell-sub" title="Häufig gebrauchte Einträge im Arbeitsspeicher (max. ${d.ram?.max || 0}) – Hörproben werden nie gespeichert, nur gestreamt">Im Arbeitsspeicher</div></div>
        <div><div class="stor-big">${fmtSize(d.backups.bytes)}</div><div class="cell-sub">${d.backups.count} Sicherungen</div></div>
        <div><div class="stor-big">${(sv.shazam || 0) + (sv.lookups || 0)}</div><div class="cell-sub">Online-Abfragen gespart</div></div>
      </div>
      <div class="cell-sub" style="white-space:normal;margin-top:6px">${sv.shazam || 0}× Shazam (lokal wiedererkannt) · ${sv.lookups || 0}× Deezer/Last.fm/iTunes (Song-Speicher) · Ordner: ${esc(d.data_dir)}</div>
    </div>
    <div class="card set-group" style="margin-top:12px">
      ${d.rows.map(r => `<div class="set-row stor-row">
        <label class="stor-pick"><input type="checkbox" data-pick="${r.id}" ${r.count ? "" : "disabled"}></label>
        <div><div class="lbl">${esc(r.label)}</div><div class="hint">${esc(r.hint)}</div></div>
        <div class="stor-num"><b>${r.count ? fmtSize(r.bytes) : "leer"}</b><span>${r.count} ${r.id === "fingerprints" ? "Hashes" : r.id === "previews" || r.id === "logs" ? "Dateien" : "Einträge"}</span></div>
        <div class="stor-bar"><b style="width:${total ? Math.max(r.bytes ? 2 : 0, Math.round(r.bytes / total * 100)) : 0}%"></b></div>
      </div>`).join("")}
    </div>
    <div class="btn-row" style="margin-top:10px">
      <button class="btn btn--sm btn--danger" id="storClear" disabled>${icon("trash")}Auswahl leeren</button>
      <button class="btn btn--sm btn--ghost" id="storCache">${icon("trash")}Nur Zwischenspeicher leeren</button>
    </div>
    <div class="cell-sub" style="white-space:normal;margin:8px 2px 0">Verlauf, Playlists und gelernte Genres bleiben dabei immer erhalten. Geleerte Bereiche füllen sich bei Bedarf wieder – dann kostet es eben wieder Online-Abfragen.</div>`;
    hydrateIcons(box);
    const picks = () => $$("[data-pick]:checked", box).map(i => i.dataset.pick);
    $$("[data-pick]", box).forEach(i => i.onchange = () => { $("#storClear", box).disabled = !picks().length; });
    const clear = (what, title) => modal({ title, text: `Betrifft: ${what.map(w => d.rows.find(r => r.id === w).label).join(", ")}.`, confirm: "Leeren", danger: true,
      onConfirm: async () => { const r = await api("/api/storage/clear", { method: "POST", body: { what } }); toast(`Geleert – Datenbank jetzt ${fmtSize(r.db_bytes)}`); this.render(box); } });
    $("#storClear", box).onclick = () => clear(picks(), "Ausgewählte Bereiche leeren?");
    $("#storCache", box).onclick = () => clear(["songs", "fingerprints", "tags", "similar", "links", "other"], "Zwischenspeicher leeren?");
  },
};

const MISS_WHY = { unerkannt: "Nicht erkannt", genre: "Genre unbekannt" };
const Misses = {
  async render(box) {
    const d = await api("/api/misses").catch(() => null);
    if (!d || !document.body.contains(box)) return;
    const items = d.items;
    if (!items.length) {
      box.innerHTML = `<div class="card"><div class="cell-sub" style="white-space:normal">Noch nichts gesammelt. Erkennt SH-Tunebridge einen Song nicht – oder findet kein Genre –, landet er hier: mit Zeit, Pegel, Fehlermeldungen und (falls dein Player es meldet) dem Titel, der gerade lief. Es wird nichts gesendet.</div></div>`;
      return;
    }
    const who = m => m.song ? `${m.song.artist} – ${m.song.title}` : m.player ? `laut Player: ${[m.player.artist, m.player.title].filter(Boolean).join(" – ")}` : "unbekannt (kein Player-Titel)";
    const det = m => {
      const x = m.details || {};
      if (m.kind === "genre") { const t = Object.keys(x.tags || {}); return t.length ? `Tags: ${t.slice(0, 8).join(", ")}` : "keine Tags gefunden"; }
      const parts = [];
      if (m.level_db != null) parts.push(`${Math.round(m.level_db)} dB`);
      if (x.unsichere_treffer?.length) parts.push(`unsicher: ${x.unsichere_treffer.join("; ")}`);
      if (x.tempo_versuche?.length) parts.push(`Tempo-Versuche: ${x.tempo_versuche.join("; ")}`);
      const errs = Object.entries(x.fehler || {}); if (errs.length) parts.push(errs.map(([k, v]) => `${k}: ${v}`).join("; "));
      if (m.player?.url) parts.push(m.player.url.replace(/^https?:\/\//, "").slice(0, 60));
      return parts.join(" · ");
    };
    box.innerHTML = `<div class="card miss-list">
      ${items.map(m => `<div class="miss" data-id="${m.id}">
        <label class="stor-pick"><input type="checkbox" data-mid="${m.id}"></label>
        <div style="min-width:0">
          <div class="cell-title"><span class="chip ${m.kind === "genre" ? "chip--warn" : ""}">${MISS_WHY[m.kind] || m.kind}</span> ${esc(who(m))}</div>
          <div class="cell-sub">${relTime(m.ts)} · ${esc(det(m))}${m.sent ? " · gesendet" : ""}</div>
          <input class="input input--sm" data-note="${m.id}" value="${esc(m.note || "")}" placeholder="Notiz, z. B. richtiger Titel oder Genre …">
        </div>
      </div>`).join("")}
    </div>
    <div class="btn-row" style="margin-top:10px">
      <button class="btn btn--sm" id="mPreview">${icon("info")}Ansehen, was weitergegeben würde</button>
      <button class="btn btn--sm" id="mExport">${icon("download")}Als Datei speichern</button>
      <button class="btn btn--sm btn--primary" id="mSend">${icon("upload")}An Entwickler senden</button>
      <button class="btn btn--sm btn--danger" id="mDel">${icon("trash")}Löschen</button>
    </div>
    <div class="cell-sub" style="white-space:normal;margin:8px 2px 0">${items.length} Einträge${items.filter(m => m.sent).length ? `, davon ${items.filter(m => m.sent).length} schon gesendet` : ""}. Ohne Auswahl gilt alles. Weitergegeben werden nur die gezeigten Felder – kein Ton, kein Rechner- oder Gerätename. Senden geht nur auf Klick und nach Vorschau – oder automatisch, wenn du es unter Datenschutz › Einwilligungen erlaubt hast.</div>
    ${d.server?.identity ? `<div class="cell-sub" style="white-space:normal;margin:6px 2px 0">Beim Entwickler bist du nur als Kennung <b>${esc(d.server.identity)}</b> bekannt. <a href="#" id="mSrvState">Was liegt dort von mir?</a> · <a href="#" id="mSrvDel">Alles von mir dort löschen</a></div>` : ""}`;
    hydrateIcons(box);
    const ids = () => { const p = $$("[data-mid]:checked", box).map(i => +i.dataset.mid); return p.length ? p : null; };
    $$("[data-note]", box).forEach(i => i.onchange = () => api(`/api/misses/${i.dataset.note}/note`, { method: "POST", body: { note: i.value } }).then(() => toast("Notiz gespeichert")));
    $("#mPreview", box).onclick = async () => {
      const data = await api("/api/misses/preview", { method: "POST", body: { ids: ids() } });
      modal({ title: `Vorschau – ${data.eintraege.length} Einträge`, body: `<pre class="dbg-pre">${esc(JSON.stringify(data, null, 1))}</pre>`, confirm: "Schließen", cancel: null });
    };
    $("#mExport", box).onclick = async () => {
      const r = await api("/api/misses/export", { method: "POST", body: { ids: ids() } });
      modal({ title: "Gespeichert", text: `${r.count} Einträge in ${r.name}`, confirm: "Ordner öffnen", cancel: "Schließen",
        onConfirm: () => api("/api/debug/open-folder", { method: "POST", body: { folder: r.folder } }) });
    };
    $("#mSend", box).onclick = async () => {
      const sel = ids();
      const data = await api("/api/misses/preview", { method: "POST", body: { ids: sel } });
      modal({ title: `${data.eintraege.length} Einträge an den Entwickler senden?`,
        body: `<div class="privacy-note"><p>Gesendet wird <b>genau das</b> hier unten – an <code>${esc(d.server?.url || "")}</code>, verschlüsselt (HTTPS).</p>
          <ul><li>Kein Ton, kein Rechner- oder Gerätename, kein Konto. Deine Installation ist dort nur eine zufällige Kennung.</li>
          <li>Auf dem Server sofort verschlüsselt – lesen kann es nur der Entwickler auf seinem eigenen Rechner. Keine IP-Speicherung.</li>
          <li>Zweck: Erkennung und Genres verbessern. Aufbewahrung höchstens 12 Monate.</li>
          <li>Du kannst alles jederzeit hier wieder löschen lassen („Alles von mir dort löschen“).</li></ul></div>
          <pre class="dbg-pre" style="max-height:34vh">${esc(JSON.stringify(data, null, 1))}</pre>`,
        confirm: "Ja, senden",
        onConfirm: async () => {
          try { const r = await api("/api/misses/send", { method: "POST", body: { ids: sel } });
            toast(`Gesendet: ${r.angenommen} neu${r.schon_da ? `, ${r.schon_da} waren schon da` : ""} – danke!`); this.render(box); }
          catch (e) { toast(`Senden fehlgeschlagen: ${e.message}`, "err"); }
        } });
    };
    const st = $("#mSrvState", box);
    if (st) st.onclick = async e => { e.preventDefault();
      try { const r = await api("/api/misses/server"); modal({ title: "Beim Entwickler gespeichert", text: `${r.gespeichert} Einträge von dir (Kennung ${r.identity}). Sie werden nach spätestens ${r.aufbewahrung_tage} Tagen automatisch gelöscht.`, confirm: "OK", cancel: null }); }
      catch (err) { toast(err.message, "err"); } };
    const sd = $("#mSrvDel", box);
    if (sd) sd.onclick = e => { e.preventDefault(); modal({ title: "Alles von dir beim Entwickler löschen?", text: "Alle Einträge, die du je gesendet hast, werden auf dem Server sofort gelöscht. Deine lokale Liste bleibt.", confirm: "Löschen", danger: true,
      onConfirm: async () => { try { const r = await api("/api/misses/server-delete", { method: "POST" }); toast(`${r.geloescht} Einträge auf dem Server gelöscht`); } catch (err) { toast(err.message, "err"); } } }); };
    $("#mDel", box).onclick = () => { const sel = ids(); modal({ title: sel ? `${sel.length} Einträge löschen?` : "Alle Einträge löschen?", confirm: "Löschen", danger: true,
      onConfirm: async () => { await api("/api/misses/delete", { method: "POST", body: { ids: sel } }); this.render(box); } }); };
  },
};

/* ================================================================= Datenverbrauch */
const fmtBytes = n => n >= 1e9 ? `${(n / 1e9).toLocaleString("de-DE", { maximumFractionDigits: 2 })} GB` : n >= 1e6 ? `${(n / 1e6).toLocaleString("de-DE", { maximumFractionDigits: 1 })} MB`
  : n >= 1e3 ? `${Math.round(n / 1e3)} KB` : `${n | 0} B`;
const fmtRate = n => `${fmtBytes(n)}/s`;
/* Einstellungen › Gemeinschaft: Genres beitragen (manuell/automatisch) und die Gemeinschafts-Datenbank laden */
const Community = {
  OPTS: [
    ["genres", "Eigene Einordnungen beitragen", "Songs, deren Genre du selbst festgelegt oder beim Sortieren korrigiert hast: Künstler, Titel, ISRC, Genre, Subgenre, Herkunft. Zählen am meisten."],
    ["bibliothek", "Genres meiner Bibliothek beitragen", "Für die Songs, die die App schon kennt (Erkennen, Sortieren, „Alles einlesen“): Künstler, Titel, ISRC, Genre, Subgenre, Sicherheit. Das Genre wird dafür nur aus freien Quellen abgeleitet (MusicBrainz, Angaben im Titel) und nur gesendet, wenn es mit dem Ergebnis der App übereinstimmt – Daten von Last.fm, Deezer oder Apple fließen nicht ein. Nie Playlist-Namen, Playlists, Konten oder Hörzeiten."],
    ["genredb", "Gemeinschafts-Datenbank laden", "Holt die signierte Datenbank (nur Song → Genre, keine Nutzerdaten) und nutzt sie beim Erkennen und Sortieren. Gesendet wird dabei nur die Anfrage."],
  ],
  async render(box) {
    if (!box) return;
    let d; try { d = await api("/api/community"); } catch (e) { box.innerHTML = `<div class="notice">${icon("info")}<div>${esc(e.message)}</div></div>`; return hydrateIcons(box); }
    const ago = ts => ts ? new Date(ts * 1000).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" }) : "noch nie";
    const ready = d.privacy && d.domain;
    const any = Object.values(d.consent).some(Boolean), canSync = d.privacy && (ready || d.consent.genredb);
    const last = d.last ? `${ago(d.last.ts)}${["genres", "bibliothek", "genredb"].some(k => d.last[k]) ? ` – ${[d.last.genres && `${d.last.genres} Einordnungen`, d.last.bibliothek && `${d.last.bibliothek} Bibliotheks-Songs`, d.last.genredb && "Datenbank aktualisiert"].filter(Boolean).join(", ")}` : " – nichts Neues"}` : "noch nie";
    box.innerHTML = `
      ${ready ? "" : `<div class="card set-group" style="margin-bottom:14px"><div class="set-row" style="grid-template-columns:1fr"><div>
        <div class="lbl">${icon("info")} Zuerst bestätigen</div>
        <label class="cons-check"><input type="checkbox" id="cmP" ${d.privacy ? "checked disabled" : ""}><span>Ich habe die <a href="${PRIVACY_URL}" target="_blank" rel="noopener">Datenschutzerklärung</a> gelesen und bin einverstanden.</span></label>
        <label class="cons-check"><input type="checkbox" id="cmD"><span>Ich erlaube, dass die unten ausgewählten Daten an den Server des Entwicklers (Deutschland) gesendet bzw. von dort geladen werden.</span></label>
      </div></div></div>`}
      <div class="card set-group">
        ${this.OPTS.map(([id, lbl, hint]) => `<div class="set-row"><div><div class="lbl">${esc(lbl)}</div><div class="hint">${esc(hint)}</div></div><div></div>
          <label class="switch"><input type="checkbox" data-cm="${id}" ${d.consent[id] ? "checked" : ""}><span class="track"></span></label></div>`).join("")}
        <div class="set-row"><div><div class="lbl">Abgleich</div><div class="hint">${d.mode === "auto" ? "Automatisch: im Hintergrund etwa alle 6 Stunden (Datenbank einmal am Tag)." : "Manuell: nur, wenn du unten auf „Jetzt abgleichen“ klickst."}</div></div>
          <div class="segmented" id="cmMode"><button data-mode="manuell" class="${d.mode === "manuell" ? "on" : ""}">Manuell</button><button data-mode="auto" class="${d.mode === "auto" ? "on" : ""}">Automatisch</button></div><div></div></div>
      </div>
      <div class="section-title">Stand</div>
      <div class="card set-group"><dl class="kv">
        <dt>Eigene Einordnungen</dt><dd>${d.votes.total} gesamt · ${d.votes_pending} noch nicht beigetragen</dd>
        <dt>Bibliothek</dt><dd>${d.lib_sent} beigetragen · ${d.lib_pending} bereit</dd>
        <dt>Gemeinschafts-Datenbank</dt><dd>${d.community?.songs != null ? `${d.community.songs} Songs · Stand ${esc(d.community.created || "?")}` : "noch nicht geladen"}</dd>
        <dt>Letzter Abgleich</dt><dd>${esc(last)}</dd>
      </dl>
      <div class="btn-row" style="padding:10px 14px 14px"><button class="btn btn--primary" id="cmSync" ${any && canSync ? "" : "disabled"}>${icon("repeat")}Jetzt abgleichen</button>
        <span class="cell-sub">Pro Abgleich höchstens ${d.lib_per_sync} Bibliotheks-Songs und 200 Einordnungen – der Rest folgt beim nächsten Mal.</span></div></div>
      <p class="cell-sub" style="margin-top:10px">Widerrufen: Schalter aus. Bereits Gesendetes löschst du unter <a href="#/settings?tab=datenschutz">Datenschutz</a> („Meine Daten beim Entwickler löschen“).</p>`;
    hydrateIcons(box);
    $$("[data-cm]", box).forEach(i => i.onchange = async () => {
      const load = i.dataset.cm === "genredb";                    // nur laden: Domain-Freigabe nicht nötig
      const privOk = d.privacy || $("#cmP", box)?.checked;
      if (!ready && i.checked && !(privOk && (load || $("#cmD", box)?.checked))) {
        i.checked = false; return toast(load ? "Bitte zuerst die Datenschutzerklärung bestätigen" : "Bitte zuerst beide Punkte oben bestätigen", "err");
      }
      try {
        await api("/api/consent", { method: "POST", body: { privacy: true, server: { ...(ready || load ? {} : { domain: true }), [i.dataset.cm]: i.checked } } });
        toast(i.checked ? "Erlaubt" : "Ausgeschaltet"); this.render(box);
      } catch (e) { i.checked = !i.checked; toast(e.message, "err"); }
    });
    $$("#cmMode button", box).forEach(b => b.onclick = async () => {
      await api("/api/community/mode", { method: "POST", body: { mode: b.dataset.mode } }).catch(e => toast(e.message, "err"));
      this.render(box);
    });
    $("#cmSync", box).onclick = async e => {
      const b = e.currentTarget; b.disabled = true; b.innerHTML = `${icon("repeat")}Gleiche ab …`; hydrateIcons(b);
      try {
        const r = await api("/api/community/sync", { method: "POST" }), x = r.done || {};
        const parts = [x.genres && `${x.genres} Einordnungen`, x.bibliothek && `${x.bibliothek} Bibliotheks-Songs`].filter(Boolean);
        toast(`${parts.length ? `Beigetragen: ${parts.join(", ")}` : "Nichts Neues zu senden"}${x.genredb ? ` · Datenbank: ${x.genredb} Songs` : ""}`);
      } catch (err) { toast(err.message, "err"); }
      this.render(box);
    };
  },
};

const Traffic = {
  pend: new Map(), timer: null,
  // Was das Fenster selbst lädt (Cover, Hörproben) – Größen fremder Server verrät der Browser oft nicht -> Schätzwert
  initClient() {
    try {
      new PerformanceObserver(list => {
        for (const e of list.getEntries()) {
          if (!e.name.startsWith("http") || e.name.startsWith(location.origin) || ["audio", "video"].includes(e.initiatorType)) continue;
          let n = e.transferSize || e.encodedBodySize, est = false;
          if (!n) { n = e.initiatorType === "img" ? 25000 : 4000; est = true; }
          this.note(new URL(e.name).host, n, est);
        }
      }).observe({ type: "resource", buffered: true });
    } catch { /* ältere Engines: dann nur der Server-Anteil */ }
    setInterval(() => this.flush(), 10000);
    window.addEventListener("beforeunload", () => this.flush());
  },
  note(host, bytes, est) {
    const k = `${host}|${est ? 1 : 0}`;
    this.pend.set(k, (this.pend.get(k) || 0) + bytes);
  },
  flush() {
    if (!this.pend.size) return;
    const items = [...this.pend].map(([k, b]) => { const [host, est] = k.split("|"); return { host, bytes: Math.round(b), est: est === "1" }; });
    this.pend.clear();
    api("/api/traffic/client", { method: "POST", body: { items } }).catch(() => {});
  },
  async pill() {
    const el = $("#trafficPill");
    if (!el || document.hidden) return;
    const t = await api("/api/traffic/live").catch(() => null);
    if (!t) return;
    const r = t.rate_in + t.rate_out;
    el.classList.toggle("busy", r > 2000);
    el.innerHTML = `${icon("transfer")}<span class="tp-rate num">${fmtRate(r)}</span><em class="num" title="Heute verbraucht">${fmtBytes(t.today)} heute</em>`;
  },
  async render(box) {
    const d = await api("/api/traffic");
    const card = (lbl, v, sub) => `<div class="tr-stat"><span>${lbl}</span><b class="num">${v}</b>${sub ? `<em>${sub}</em>` : ""}</div>`;
    const sum = rows => rows.reduce((a, r) => a + r.in + r.out, 0);
    const maxH = Math.max(1, ...d.history.map(h => h.in + h.out));
    const maxD = Math.max(1, ...d.daily.map(x => x.bytes));
    const table = rows => rows.length ? `<div class="tr-rows">${rows.map(r => { const tot = r.in + r.out, max = Math.max(1, rows[0].in + rows[0].out);
      return `<div class="tr-row"><div class="tr-name">${esc(r.name)}${r.est ? `<span class="cell-sub" title="Enthält Schätzwerte für Bilder/Hörproben, die das Fenster direkt lädt"> ~</span>` : ""}</div>
        <div class="tr-bar"><b style="width:${tot / max * 100}%"></b></div><div class="num">${fmtBytes(tot)}</div>
        <div class="cell-sub num">↓ ${fmtBytes(r.in)} · ↑ ${fmtBytes(r.out)}</div></div>`; }).join("")}</div>` : `<div class="cell-sub" style="padding:8px 4px">Noch nichts gemessen.</div>`;
    let range = store.get("trRange", "today");
    box.innerHTML = `<div class="tr-grid">
        ${card("Gerade", `<span id="trRate">${fmtRate(d.rate_in + d.rate_out)}</span>`, `↓ ${fmtRate(d.rate_in)} · ↑ ${fmtRate(d.rate_out)}`)}
        ${card("Seit Programmstart", fmtBytes(d.session), new Date(d.since * 1000).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) + " Uhr")}
        ${card("Heute", fmtBytes(sum(d.rows.today)))}
        ${card("30 Tage", fmtBytes(sum(d.rows.days30)))}
        ${card("Gesamt", fmtBytes(sum(d.rows.all)), `seit ${new Date(d.first_day).toLocaleDateString("de-DE")}`)}
      </div>
      <div class="card tr-chart-card"><div class="det-h">${icon("wave")}<b>Letzte 2 Minuten</b><span class="det-legend">je Sekunde</span></div>
        <div class="tr-spark">${d.history.map(h => `<b style="height:${Math.max(2, (h.in + h.out) / maxH * 100)}%" title="${fmtBytes(h.in + h.out)}"></b>`).join("") || `<span class="cell-sub">Gleich geht's los …</span>`}</div></div>
      <div class="card tr-chart-card"><div class="det-h">${icon("clock")}<b>Letzte 14 Tage</b></div>
        <div class="tr-days">${d.daily.map(x => `<div title="${fmtBytes(x.bytes)}"><b style="height:${Math.max(3, x.bytes / maxD * 100)}%"></b><span>${x.day.slice(8)}.${x.day.slice(5, 7)}.</span></div>`).join("")}</div></div>
      <div class="card"><div class="det-h">${icon("grid")}<b>Nach Dienst</b>
        <div class="seg seg--sm" id="trRange" style="margin-left:auto">${[["session", "Sitzung"], ["today", "Heute"], ["days30", "30 Tage"], ["all", "Gesamt"]].map(([k, l]) => `<button data-r="${k}">${l}</button>`).join("")}</div></div>
        <div id="trTable"></div></div>
      <div class="btn-row" style="margin-top:14px"><button class="btn btn--sm btn--ghost" id="trReset">${icon("trash")}Zähler zurücksetzen</button>
        <span class="cell-sub">Gemessen nur auf diesem Rechner, nichts davon wird gesendet. Was das Fenster direkt lädt (Cover, Hörproben), ist teils geschätzt (~).</span></div>`;
    hydrateIcons(box);
    const drawTable = () => { $$("#trRange button", box).forEach(b => b.classList.toggle("on", b.dataset.r === range)); $("#trTable", box).innerHTML = table(d.rows[range] || []); };
    $$("#trRange button", box).forEach(b => b.onclick = () => { range = b.dataset.r; store.set("trRange", range); drawTable(); });
    drawTable();
    $("#trReset", box).onclick = () => modal({ title: "Zähler zurücksetzen?", text: "Alle gespeicherten Tageswerte werden gelöscht.", confirm: "Zurücksetzen", danger: true,
      onConfirm: async () => { await api("/api/traffic/reset", { method: "POST" }); this.render(box); } });
    clearTimeout(this.timer);
    const tick = () => { if (!document.body.contains(box)) return; this.render(box).catch(() => {}); };
    this.timer = setTimeout(tick, 3000);
  },
};

/* ================================================================= Discord Rich Presence */
const DiscordUI = {
  on: false,
  async init() { const d = await api("/api/discord").catch(() => null); this.on = !!d?.enabled; },
  view(v) { if (this.on) api("/api/discord/event", { method: "POST", body: { kind: "view", view: v } }).catch(() => {}); },
  preview(t) { if (this.on) api("/api/discord/event", { method: "POST", body: { kind: "preview", preview: t ? { title: t.title, artists: t.artists, cover: t.cover, genre: t.genre, subgenre: t.subgenre,
    url: t.ids?.deezer ? `https://www.deezer.com/track/${t.ids.deezer}` : null } : null } }).catch(() => {}); },
  async render(box) {
    const d = await api("/api/discord");
    this.on = d.enabled;
    const sw = (k, lbl, hint) => `<div class="set-row"><div><div class="lbl">${lbl}</div><div class="hint">${hint}</div></div><div></div>
      <label class="switch"><input type="checkbox" data-dk="${k}" ${d[k] ? "checked" : ""} ${d.enabled || k === "enabled" ? "" : "disabled"}><span class="track"></span></label></div>`;
    const st = { aus: ["", "Aus"], verbunden: ["on", `Verbunden${d.user ? ` als ${esc(d.user)}` : ""}`], fehler: ["err", esc(d.error || "Fehler")], id_fehlt: ["err", "Application ID fehlt"] }[d.state] || ["", d.state];
    const a = d.preview_activity;
    box.innerHTML = `<div class="dc-wrap">
      <div>
        <div class="card set-group">
          ${sw("enabled", "Discord-Status anzeigen", "SH-Tunebridge zeigt in Discord, was erkannt wurde bzw. was du gerade machst. Läuft nur über das Discord-Programm auf diesem Rechner.")}
          <div class="set-row"><div><div class="lbl">Application ID</div><div class="hint">Aus dem <a href="https://discord.com/developers/applications" target="_blank" rel="noopener">Discord Developer Portal</a>: „New Application“ (Name z. B. „SH-Tunebridge“ – der steht dann in Discord), dann die Application ID kopieren. Öffentlich, kein Geheimnis.</div></div>
            <input class="input" id="dcId" inputmode="numeric" value="${esc(d.client_id)}" placeholder="z. B. 1234567890123456789" autocomplete="off" spellcheck="false">
            <button class="btn btn--sm" id="dcSave">Speichern</button></div>
        </div>
        <div class="section-title">Was angezeigt wird</div>
        <div class="card set-group">
          ${sw("song", "Erkannter Song", "Titel und Künstler des zuletzt erkannten Songs.")}
          ${sw("preview", "Laufende Hörprobe", "Während du in SH-Tunebridge reinhörst.")}
          ${sw("cover", "Cover", "Discord lädt das Cover-Bild direkt beim Anbieter.")}
          ${sw("genre", "Genre", "Genre und Subgenre beim Darüberfahren über das Bild.")}
          ${sw("buttons", "Knopf „Song anhören“", "Freunde können den Song bei Deezer öffnen.")}
          ${sw("elapsed", "Laufzeit", "„seit 2:14“ unter dem Status.")}
          ${sw("activity", "Was du in der App machst", "z. B. „Sortiert eine Playlist“, „Entdeckt neue Musik“ – nur der Bereich, keine Namen.")}
          ${sw("idle", "Auch ohne Aktivität", "„Bereit zum Erkennen“, solange die App offen ist.")}
          <div class="set-row"><div><div class="lbl">Song anzeigen für</div><div class="hint">Danach verschwindet der erkannte Song wieder aus dem Status.</div></div>
            <select class="select" id="dcKeep" ${d.enabled ? "" : "disabled"}>${[5, 10, 15, 30, 60].map(m => `<option value="${m}" ${d.keep_min === m ? "selected" : ""}>${m} Minuten</option>`).join("")}</select><div></div></div>
        </div>
      </div>
      <div class="dc-side">
        <div class="dc-status"><span class="status-dot ${st[0]}"></span>${st[1]}${d.found === false ? ` <span class="cell-sub">· Discord scheint nicht zu laufen</span>` : ""}</div>
        <div class="dc-card">
          <div class="dc-k">${a ? (a.type === 2 ? "Hört SH-Tunebridge" : "Spielt SH-Tunebridge") : "Kein Status"}</div>
          ${a ? `<div class="dc-body">${a.assets?.large_image ? `<img src="${esc(a.assets.large_image)}" alt="">` : `<div class="dc-ph">${icon("wave")}</div>`}
            <div style="min-width:0"><div class="dc-t">${esc(a.details || "")}</div><div class="dc-s">${esc(a.state || "")}</div>
            ${a.assets?.large_text ? `<div class="dc-s">${esc(a.assets.large_text)}</div>` : ""}${a.timestamps ? `<div class="dc-s">seit 0:42</div>` : ""}</div></div>
            ${a.buttons ? a.buttons.map(b => `<div class="dc-btn">${esc(b.label)}</div>`).join("") : ""}`
            : `<div class="dc-s" style="padding:10px 0">${d.enabled ? "Gerade wird nichts angezeigt – erkenne einen Song oder hör rein." : "Discord-Status ist aus."}</div>`}
        </div>
        <div class="cell-sub" style="margin-top:8px">Vorschau – so ungefähr sehen es deine Discord-Kontakte.</div>
        <button class="btn btn--sm" id="dcTest" ${d.enabled && d.client_id ? "" : "disabled"} style="margin-top:12px">${icon("check")}Verbindung testen</button>
        <div class="dc-note">${icon("info")}<span>Datenschutz: Was hier eingeschaltet ist, sehen alle, die deinen Discord-Status sehen. Gesendet wird nur an das Discord-Programm auf deinem Rechner; Discord ist dafür selbst verantwortlich.</span></div>
      </div></div>`;
    hydrateIcons(box);
    const save = async patch => { try { await api("/api/discord", { method: "POST", body: patch }); await this.render(box); } catch (e) { toast(e.message, "err"); } };
    $$("[data-dk]", box).forEach(i => i.onchange = () => save({ [i.dataset.dk]: i.checked }));
    $("#dcSave", box).onclick = () => save({ client_id: $("#dcId", box).value });
    $("#dcKeep", box).onchange = e => save({ keep_min: +e.target.value });
    $("#dcTest", box).onclick = async () => {
      try { const r = await api("/api/discord/test", { method: "POST" }); toast(`Discord verbunden${r.user ? ` (${r.user})` : ""}`); setTimeout(() => this.render(box), 1200); }
      catch (e) { toast(e.message, "err"); }
    };
  },
};

/* ================================================================= Handy (Android-App) */
const PhoneUI = {
  timer: null,
  async render(box) {
    const d = await api("/api/phone").catch(e => ({ error: e.message }));
    if (d.error) { box.innerHTML = `<div class="empty">${esc(d.error)}</div>`; return; }
    const sec = (title, sub = "") => `<div class="section-title">${title}</div>${sub ? `<div class="cell-sub set-sub">${sub}</div>` : ""}`;
    const online = x => x.last_seen && Date.now() / 1000 - x.last_seen < 900;
    const mode = d.net.mode;
    const listen = d.listening.length ? d.listening.map(a => `<code>${esc(a)}</code>`).join(" ") : `<span class="muted">geschlossen</span>`;
    box.innerHTML = `
      <div class="card phone-card">
        <div class="phone-intro">
          <div class="phone-glyph">${icon("phone")}</div>
          <div><div class="lbl">${d.devices.length ? `${d.devices.length === 1 ? "Ein Handy" : `${d.devices.length} Handys`} gekoppelt` : "Noch kein Handy gekoppelt"}</div>
            <div class="hint">In der App unter <b>Mehr › Mit PC koppeln</b> den QR-Code scannen. Handy und PC bestätigen beide, erst dann wird gekoppelt. Ein Handy kann mit mehreren PCs gekoppelt sein.</div></div>
          <button class="btn btn--primary" id="phPair" ${d.enabled && d.net_consent ? "" : "disabled"}>${icon("plus")}Handy koppeln</button>
        </div>
        ${d.devices.length ? `<div class="phone-list">${d.devices.map(x => `
          <div class="phone-row">
            <div class="phone-dot ${online(x) ? "on" : ""}"></div>
            <div class="phone-name"><div>${esc(x.name || "Handy")}</div>
              <div class="cell-sub">Gekoppelt ${ago(x.added)} · zuletzt abgeglichen ${x.last_seen ? ago(x.last_seen) : "noch nie"}${x.ip ? ` · von ${esc(x.ip)}` : ""}${x.last_counts ? ` · ${x.last_counts.empfangen} empfangen, ${x.last_counts.gesendet} gesendet` : ""}${x.app ? ` · App ${esc(x.app)}` : ""}${x.via === "internet" ? " · übers Internet" : ""}</div></div>
            <label class="ph-relay" title="Auch unterwegs abgleichen – verschlüsselt über shtunebridge.bs002.de"><span class="cell-sub">Unterwegs</span>
              <span class="switch"><input type="checkbox" data-ph-relay="${esc(x.id)}" ${x.relay && d.relay_allowed ? "checked" : ""}><span class="track"></span></span></label>
            <button class="btn btn--ghost btn--sm" data-ph-del="${esc(x.id)}">Entfernen</button>
          </div>`).join("")}</div>` : ""}
      </div>

      ${d.net_consent ? "" : `
      <div class="card ph-consent">
        <div class="ph-consent-head"><div class="phone-glyph">${icon("key")}</div><div><div class="lbl">Netzwerke dieses PCs erkennen?</div>
          <div class="hint">Für den Handy-Abgleich braucht SH-Tunebridge deine Zustimmung, bevor es die Netzwerkkarten dieses PCs ausliest.</div></div></div>
        <div class="ph-facts">
          <div><span>Was</span><div>Die eigenen Netzwerkkarten dieses PCs: IP-Adressen, Netze (z. B. <code>192.168.178.0/24</code>, <code>10.0.0.0/24</code>, VPN), Name der Karte und welche Karte ins Internet geht.</div></div>
          <div><span>Wozu</span><div>Damit der PC Handys nur in deinen Heimnetzen annimmt, du die Netze auswählen kannst und das Handy den PC findet (Adressen im QR-Code und verschlüsselt an gekoppelte Handys).</div></div>
          <div><span>Nicht</span><div>Kein Durchsuchen des Netzes, keine anderen Geräte, keine WLAN-Namen, kein Standort. Nichts davon geht ins Internet oder an Dritte; gespeichert wird nur deine Auswahl.</div></div>
          <div><span>Widerruf</span><div>Jederzeit hier unter „Netzwerke“. Danach liest die App nichts mehr aus und schließt den Handy-Zugang.</div></div>
        </div>
        <div class="ph-consent-btns"><button class="btn btn--primary" id="phConsent">${icon("check")}Erlauben</button></div>
      </div>`}

      <div class="set-row"><div><div class="lbl">Abgleich im Netz erlauben</div>
        <div class="hint">Aus: Der PC nimmt keine Anfragen von Handys an, auch nicht von gekoppelten.</div></div><div></div>
        <label class="switch"><input type="checkbox" id="phOn" ${d.enabled ? "checked" : ""}><span class="track"></span></label></div>

      ${d.net_consent ? `${sec("Netzwerke", "Wo der PC Handys annimmt. Er lauscht nur auf seinen eigenen Adressen in den gewählten Netzen und nimmt nur Anfragen aus diesen Netzen an. Virtuelle Netze (Docker, VMs) werden nie verwendet.")}
      <div class="ph-modes" role="radiogroup">
        ${[["all", "Alle Heimnetze", "Jedes erkannte Heimnetz und VPN dieses PCs"],
           ["some", "Nur bestimmte", "Unten auswählen, z. B. nur WLAN und VPN"],
           ["primary", "Nur dieses Heimnetz", "Nur das Netz, über das der PC gerade ins Internet geht"]].map(([k, t, h]) => `
          <label class="ph-mode ${mode === k ? "on" : ""}"><input type="radio" name="phMode" value="${k}" ${mode === k ? "checked" : ""}>
            <div><div class="lbl">${t}</div><div class="hint">${h}</div></div></label>`).join("")}
      </div>
      <div class="ph-nets">
        ${d.networks.length ? d.networks.map(n => `
          <label class="ph-net ${n.active ? "active" : ""}">
            <input type="checkbox" data-net="${esc(n.cidr)}" ${mode === "some" ? "" : "disabled"} ${(mode === "some" ? d.net.selected.includes(n.cidr) : n.active) ? "checked" : ""}>
            <div class="ph-net-main"><div><b>${esc(n.label)}</b>${n.primary ? ` <span class="pill-mini">Haupt-Heimnetz</span>` : ""}</div>
              <div class="cell-sub">Netz <code>${esc(n.cidr)}</code> · Karte ${esc(n.iface)} · dieser PC: <code>${esc(n.ip)}</code></div></div>
            <span class="ph-net-state">${n.active ? "freigegeben" : "gesperrt"}</span>
          </label>`).join("") : `<div class="empty">Kein Heimnetz gefunden – ist der PC mit WLAN oder Kabel verbunden?</div>`}
        ${d.net.selected.filter(c => !d.networks.some(n => n.cidr === c)).map(c => `<div class="cell-sub ph-gone">Ausgewählt, aber gerade nicht verbunden: <code>${esc(c)}</code></div>`).join("")}
      </div>
      <div class="cell-sub ph-revoke">Du hast erlaubt, dass SH-Tunebridge die Netzwerkkarten dieses PCs ausliest (nur lokal). <a href="#" id="phRevoke">Zustimmung widerrufen</a></div>` : ""}

      ${sec("Was passiert wann", "Damit du jederzeit weißt, was zwischen Handy und PC läuft.")}
      <div class="ph-facts">
        <div><span>Wo der PC lauscht</span><div>${listen}<div class="cell-sub">Port ${d.port}, eigener kleiner Server nur für Handys. Die App-Oberfläche selbst bleibt nur auf diesem PC (127.0.0.1).</div></div></div>
        <div><span>Wann</span><div>Nur, solange ein Kopplungs-Code angezeigt wird oder mindestens ein Handy gekoppelt und der Abgleich erlaubt ist. Das Handy meldet sich nach jeder Erkennung, beim Öffnen der App und bei „Jetzt abgleichen“ – und nur, wenn es selbst in einem der freigegebenen Netze ist.</div></div>
        <div><span>Vom Handy empfangen</span><div>Erkennungen am Handy (Song, Zeitpunkt, Shazam-Angaben, unsicher/bestätigt), gelöschte Einträge, Änderungen an Playlists, Gerätename und App-Version.</div></div>
        <div><span>Ans Handy senden</span><div>Deine Erkennungen am PC und lokalen Playlists (Titel, Künstler, Album, ISRC, Länge, Genre, Cover- und Hörproben-Adresse, Dienst-Kennungen).</div></div>
        <div><span>Nie</span><div>Konten, Tokens, API-Keys, Einstellungen, Audio.</div></div>
        <div><span>Wie</span><div>Ende-zu-Ende verschlüsselt (AES-256-GCM), Schlüssel nur auf Handy und PC, Schutz gegen abgefangene und wiederholte Anfragen. Im eigenen Netz kein Server dazwischen.</div></div>
        <div><span>Unterwegs</span><div>Nur wenn du es je Handy einschaltest (hier „Unterwegs“ und in der App beim PC): Ist der PC nicht im selben Netz, legt das Handy seine Anfrage verschlüsselt auf <code>shtunebridge.bs002.de</code> ab; der PC schaut etwa alle 6 Minuten nach und legt die Antwort ebenso verschlüsselt zurück – unterwegs kommt der Abgleich also mit einigen Minuten Verzögerung an. Der Server sieht nur zufällige Kennungen, unlesbare Blöcke, Datum; wie bei jeder Verbindung protokolliert die Server-Technik IP-Adresse und Zeitpunkt der Anfragen (höchstens 12 Monate, siehe Datenschutzerklärung). Playlists über 1500 Songs gehen nur im Heimnetz. Ausschalten löscht beide Ablagen sofort.</div></div>
      </div>
      <div class="dc-note">${icon("info")}<span>Blockiert eine Firewall den Port, findet das Handy den PC nicht – unter Linux z. B. <code>sudo ufw allow from ${esc((d.networks.find(n => n.primary) || d.networks[0] || { cidr: "192.168.0.0/16" }).cidr)} to any port ${d.port} proto tcp</code>.</span></div>`;
    hydrateIcons(box);
    $("#phPair", box).onclick = () => this.pair(box);
    const consent = async ok => {
      try { await api("/api/phone/net-consent", { method: "POST", body: { ok } }); } catch (err) { toast(err.message, "err"); }
      this.render(box);
    };
    if ($("#phConsent", box)) $("#phConsent", box).onclick = () => consent(true);
    if ($("#phRevoke", box)) $("#phRevoke", box).onclick = e => {
      e.preventDefault();
      modal({ title: "Zustimmung widerrufen?", text: "SH-Tunebridge liest dann die Netzwerkkarten dieses PCs nicht mehr aus und schließt den Handy-Zugang. Gekoppelte Handys bleiben eingetragen, gleichen aber erst wieder ab, wenn du erneut zustimmst.",
        confirm: "Widerrufen", danger: true, onConfirm: () => consent(false) });
    };
    $("#phOn", box).onchange = async e => { try { await api("/api/phone/enabled", { method: "POST", body: { enabled: e.target.checked } }); this.render(box); } catch (err) { toast(err.message, "err"); } };
    const saveNet = async (m, sel) => {
      try { await api("/api/phone/network", { method: "POST", body: { mode: m, selected: sel } }); }
      catch (err) { toast(err.message, "err"); }
      this.render(box);
    };
    $$("input[name=phMode]", box).forEach(r => r.onchange = () => {
      const m = r.value;
      const sel = m === "some" ? (d.net.selected.length ? d.net.selected : d.networks.filter(n => n.active).map(n => n.cidr)) : d.net.selected;
      saveNet(m, sel);
    });
    $$("[data-net]", box).forEach(c => c.onchange = () => saveNet("some", $$("[data-net]:checked", box).map(x => x.dataset.net)));
    $$("[data-ph-relay]", box).forEach(c => c.onchange = async () => {
      const id = c.dataset.phRelay, on = c.checked;
      const set = async () => {
        try { await api(`/api/phone/devices/${encodeURIComponent(id)}/relay`, { method: "POST", body: { enabled: on } }); }
        catch (err) { toast(err.message, "err"); }
        this.render(box);
      };
      if (!on || d.relay_allowed) return set();
      c.checked = false;
      modal({
        title: "Unterwegs abgleichen?",
        text: "Ist das Handy nicht im selben Netz wie dieser PC, tauschen beide den Abgleich über eine Ablage auf https://shtunebridge.bs002.de aus. " +
          "Alles wird vorher mit dem Schlüssel aus eurer Kopplung verschlüsselt (AES-256-GCM): der Server sieht nur zufällige Kennungen, unlesbare Blöcke, " +
          "das Datum; wie bei jeder Verbindung protokolliert die Server-Technik IP-Adresse und Zeitpunkt der Anfragen (höchstens 12 Monate). Dieser PC fragt dafür etwa alle 6 Minuten dort nach. " +
          "Inhalt wie im Heimnetz (Erkennungen, Playlist-Änderungen, ausgewählte Playlists bis 1500 Songs), nie Audio, Konten oder Schlüssel. " +
          "Jederzeit abschaltbar – dann werden die Ablagen sofort gelöscht, sonst automatisch nach einem Jahr ohne Nutzung.",
        confirm: "Erlauben und einschalten",
        onConfirm: async () => {
          try { await api("/api/consent", { method: "POST", body: { privacy: true, server: { domain: true, relay: true } } }); }
          catch (err) { return toast(err.message, "err"); }
          await set();
        },
      });
    });
    $$("[data-ph-del]", box).forEach(b => b.onclick = () => modal({
      title: "Handy entfernen?", text: "Das Handy kann danach nicht mehr mit diesem PC abgleichen, bis du es neu koppelst. Bereits übertragene Songs bleiben auf beiden Geräten.",
      confirm: "Entfernen", danger: true,
      onConfirm: async () => { await api(`/api/phone/devices/${encodeURIComponent(b.dataset.phDel)}`, { method: "DELETE" }); this.render(box); },
    }));
  },
  async pair(box) {
    let p;
    try { p = await api("/api/phone/pair", { method: "POST" }); } catch (e) { return toast(e.message, "err"); }
    const stop = () => { clearInterval(this.timer); this.timer = null; };
    let shownReq = null;
    modal({
      title: "Handy koppeln", confirm: "Schließen", cancel: "Abbrechen", sticky: true, wide: true,
      body: `<div class="pair">
        <div class="pair-qr">${p.qr}</div>
        <div class="pair-side">
          <ol class="pair-steps">
            <li>SH-Tunebridge auf dem Handy öffnen</li>
            <li><b>Mehr › Mit PC koppeln</b> tippen</li>
            <li>Diesen Code scannen und am Handy bestätigen</li>
            <li>Hier am PC „Zulassen“ klicken</li>
          </ol>
          <div class="cell-sub">Oder von Hand eingeben:</div>
          <div class="pair-code">${esc(p.code)}</div>
          <div class="cell-sub pair-addr">Der PC ist erreichbar unter: ${p.addresses.map(a => `<span>${esc(a)}</span>`).join("")}</div>
          <div class="pair-state" id="pairState"><span class="spin"></span>Warte auf das Handy … <span id="pairLeft"></span></div>
        </div></div>
        <div id="pairAsk"></div>`,
      onConfirm: () => { stop(); if ($("#pairAsk")?.dataset.open) api("/api/phone/pair/cancel", { method: "POST" }).catch(() => {}); this.render(box); },
      onCancel: () => { stop(); api("/api/phone/pair/cancel", { method: "POST" }).catch(() => {}); this.render(box); },
    });
    const ask = r => {
      const el = $("#pairAsk"); if (!el) return;
      el.dataset.open = "1";
      el.innerHTML = `<div class="pair-ask">
        <div class="pair-ask-head">${icon("phone")}<div><b>${esc(r.name)}</b> möchte sich koppeln
          <div class="cell-sub">von ${esc(r.ip || "?")}${r.app ? ` · App ${esc(r.app)}` : ""}</div></div>
          <div class="pair-check"><span>Prüfzahl</span><b>${esc(r.check.slice(0, 2))} ${esc(r.check.slice(2))}</b></div></div>
        <p>Steht auf dem Handy <b>dieselbe Prüfzahl</b>? Nur dann zulassen. Danach darf dieses Handy Erkennungen und Playlist-Änderungen an diesen PC schicken und bekommt deinen Verlauf und deine Playlists. Entfernen geht jederzeit hier unter „Handy“.</p>
        <div class="pair-ask-btns"><button class="btn btn--ghost" data-dec="0">Ablehnen</button><button class="btn btn--primary" data-dec="1">${icon("check")}Zulassen</button></div>
      </div>`;
      hydrateIcons(el);
      $$("[data-dec]", el).forEach(b => b.onclick = async () => {
        $$("[data-dec]", el).forEach(x => x.disabled = true);
        try { await api("/api/phone/pair/decide", { method: "POST", body: { ok: b.dataset.dec === "1" } }); }
        catch (e) { toast(e.message, "err"); }
        delete el.dataset.open;
        if (b.dataset.dec !== "1") { el.innerHTML = ""; $("#pairState").innerHTML = "Abgelehnt – das Handy wurde nicht gekoppelt."; stop(); }
        else el.innerHTML = "";
      });
    };
    const tick = async () => {
      if (!$("#pairState")) return stop();
      const st = await api("/api/phone").catch(() => null);
      const pr = st?.pairing;
      const left = Math.max(0, Math.round((pr?.expires || p.expires) - Date.now() / 1000));
      const showLeft = () => { const el = $("#pairLeft"); if (el) el.textContent = `(noch ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")})`; };
      queueMicrotask(showLeft);
      if (pr?.paired) {
        stop();
        const name = st.devices.find(x => x.id === pr.paired)?.name || "Handy";
        $("#pairAsk").innerHTML = "";
        $("#pairState").innerHTML = `${icon("check")}<b>${esc(name)}</b> ist gekoppelt.`;
        $("#pairState").classList.add("ok"); hydrateIcons($("#pairState"));
        $(".pair-qr").classList.add("done");
      } else if (pr?.request) {
        if (shownReq !== pr.request.at) { shownReq = pr.request.at; ask(pr.request); }
        $("#pairState").innerHTML = `<span class="spin"></span>Anfrage vom Handy – bitte unten bestätigen <span id="pairLeft"></span>`;
      } else if (!pr) {
        stop();
        if (shownReq) $("#pairAsk").innerHTML = "";
        if (!$("#pairState").textContent.startsWith("Abgelehnt")) $("#pairState").innerHTML = "Code abgelaufen – bitte noch einmal „Handy koppeln“.";
      } else if (shownReq) {
        shownReq = null; $("#pairAsk").innerHTML = "";        // Handy hat aufgegeben (z. B. Zeit abgelaufen)
        $("#pairState").innerHTML = `<span class="spin"></span>Warte auf das Handy … <span id="pairLeft"></span>`;
      }
    };
    this.timer = setInterval(tick, 1200); tick();
  },
};

const SETTING_GROUPS = [
  ["Allgemein", [["allgemein", "Version & Rechner", "sliders"], ["darstellung", "Darstellung", "palette"], ["dienste", "Konten & Dienste", "key"], ["discord", "Discord-Status", "chat"], ["handy", "Handy", "phone"]]],
  ["Analyse", [["ki", "KI & API-Keys", "sparkle"], ["genres", "Genres", "disc"], ["erkennung", "Erkennung", "wave"]]],
  ["Daten", [["sicherung", "Sicherung", "archive"], ["gemeinschaft", "Gemeinschaft", "share"], ["datenschutz", "Datenschutz", "info"], ["traffic", "Datenverbrauch", "transfer"], ["speicher", "Speicher & Cache", "archive"],
             ["nichterkannt", "Nicht erkannt", "search"], ["debug", "Debug-Protokoll", "pencil"]]],
];
const SETTING_TABS = SETTING_GROUPS.flatMap(g => g[1]);

Views.settings = async (main) => {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  let tab = params.get("update") ? "allgemein" : params.get("tab") || store.get("setTab", "allgemein");
  if (!SETTING_TABS.some(t => t[0] === tab)) tab = "allgemein";
  store.set("setTab", tab);
  const [sets, st, accs, upd] = await Promise.all([api("/api/settings"), api("/api/status"), api("/api/connect"), Update.check(false, false)]);
  const row = s => s ? `<div class="set-row" data-key="${s.key}">
    <div><div class="lbl"><span class="status-dot ${s.set ? "on" : ""}"></span>${esc(s.label)}</div><div class="hint">${SETTING_HINTS[s.key] || ""}</div></div>
    <input class="input" type="${s.secret ? "password" : "text"}" placeholder="${s.set ? esc(s.value) : "nicht gesetzt"}" autocomplete="off" spellcheck="false">
    <button class="btn btn--sm" data-save>Speichern</button></div>` : "";
  const keys = ks => `<div class="card set-group">${ks.map(k => row(sets.find(s => s.key === k))).join("")}</div>`;
  const sec = (title, sub = "") => `<div class="section-title">${title}</div>${sub ? `<div class="cell-sub set-sub">${sub}</div>` : ""}`;
  const body = {
    allgemein: () => `${sec("Version & Updates")}${Update.html(upd)}
      ${sec("Dieser Rechner")}<div class="card"><dl class="kv">
        <dt>Rechner</dt><dd>${esc(st.host)}</dd><dt>Konfiguration</dt><dd>${esc(st.config)}</dd><dt>Daten</dt><dd>${esc(st.data)}</dd>
        <dt>Erkennungen</dt><dd>${st.stats.recognitions} · ${st.stats.playlists} Playlists · ${st.stats.entries} Einträge</dd>
        <dt>Lizenz</dt><dd>© 2026 Bigsmoke002 · private, nicht-kommerzielle Nutzung · <a href="https://github.com/Bigsmoke002/SH-Tunebridge/blob/main/LICENSE" target="_blank" rel="noopener">Bedingungen</a> · <a href="https://github.com/Bigsmoke002/SH-Tunebridge/blob/main/THIRD_PARTY.md" target="_blank" rel="noopener">Fremde Bestandteile</a> · <a href="https://github.com/Bigsmoke002/SH-Tunebridge/blob/main/DATENSCHUTZ.md" target="_blank" rel="noopener">Datenschutz</a></dd>
      </dl></div>`,
    dienste: () => `${sec("Konten verbinden", "Du loggst dich im Fenster selbst ein – SH-Tunebridge liest danach nur den Key von der Seite ab, prüft ihn und speichert ihn. Dein Passwort sieht SH-Tunebridge nie.")}
      <div class="accounts" id="accounts">${accs.map(accountCard).join("")}</div>
      ${sec("Musikdienste", "Spotify/TIDAL verbindest du unter <a href=\"#/services\">Dienste</a>. Hier die Schlüssel, die du selbst einträgst.")}${keys(["SPOTIFY_CLIENT_ID", "YOUTUBE_API_KEY", "LASTFM_API_KEY"])}`,
    darstellung: () => `${sec("Darstellung", "Farben, Hell/Dunkel, eigenes Hintergrundbild und Größe – wird sofort angewendet und auf diesem Rechner gespeichert.")}<div id="lookBox"></div>`,
    ki: () => `${sec("KI-Anbieter", "Welche KI Songs, Genres und Playlists einschätzt und beim Sortieren mitprüft. Entweder eine KI, oder mehrere – nacheinander als Ersatz oder zusammen mit Abstimmung. Gefunden wird, was schon auf deinem Rechner läuft (Claude Code, Codex, Gemini CLI, llama.cpp, Ollama, LM Studio); Cloud-KIs gehen mit eigenem API-Key.")}
      <div id="aiBox"></div>
      ${sec("Lokales LLM", "Ein KI-Modell auf deinem Rechner hilft beim Subgenre, wenn die Tags nicht reichen – ohne Cloud, ohne Kosten.")}<div id="llmBox"></div>`,
    genres: () => `${sec("Quellen", "Genres kommen aus Last.fm (Tags), MusicBrainz (offene Datenbank, CC0 – liefert oft das Mikro-Genre), dem Genre von Apple/Shazam und Deezer. Tempo, Tonart und Energie misst SH-Tunebridge selbst an der 30-s-Hörprobe.")}
      ${keys(["LASTFM_API_KEY"])}
      ${sec("Gelernte Genres", "Fehlt ein Genre, lernt SH-Tunebridge es aus den Tags deiner Songs selbst dazu – nur auf deinem Rechner.")}<div id="genreBox"></div>`,
    erkennung: () => `${sec("Anzeige im Kreis", "Was der Erkennen-Kreis und das Schwebe-Icon zeigen, solange Ton läuft – gilt sofort.")}
      <div class="card set-group"><div class="set-row"><div><div class="lbl">Darstellung</div><div class="hint" id="vizHint">${esc((VIZ.find(x => x[0] === Meter.viz) || VIZ[0])[2])}</div></div>
        <div class="segmented" id="vizSeg">${VIZ.map(([v, l, t]) => `<button data-viz="${v}" title="${esc(t)}" class="${Meter.viz === v ? "on" : ""}">${l}</button>`).join("")}</div><div></div></div></div>
      ${sec("Shazam")}<div class="card set-group"><div class="set-row"><div><div class="lbl"><span class="status-dot on"></span>Shazam</div><div class="hint">Immer aktiv, braucht keinen Schlüssel.</div></div><div></div><div></div></div></div>
      ${sec("Weitere Erkennungsdienste", "Optional – nur mit deinem eigenen Schlüssel. Ob Audio dorthin gesendet werden darf, legst du unter Datenschutz fest.")}${keys(["AUDD_API_TOKEN", "ACRCLOUD_HOST", "ACRCLOUD_ACCESS_KEY", "ACRCLOUD_ACCESS_SECRET"])}`,
    datenschutz: () => `${sec("Datenschutz")}<div id="privacyBox"></div>`,
    gemeinschaft: () => `${sec("Gemeinschafts-Genre-Datenbank", "Je mehr Installationen ihre Genres beitragen, desto besser wird die gemeinsame Datenbank – und davon profitiert die Erkennung bei allen. Übernommen wird ein Genre erst, wenn mehrere Installationen unabhängig dasselbe melden.")}<div id="communityBox"></div>`,
    sicherung: () => `<div class="cell-sub set-sub">Alles steckt in einer SQLite-Datenbank – hier sicherst du sie und holst sie auf einem neuen Rechner zurück.</div><div id="backupBox"></div>`,
    traffic: () => `${sec("Datenverbrauch", "Wie viel SH-Tunebridge über das Internet lädt und sendet – gerade, heute und insgesamt, aufgeteilt nach Dienst.")}<div id="trafficBox"></div>`,
    handy: () => `${sec("Handy", "Die Android-App von SH-Tunebridge mit diesem PC verbinden: Erkennungen vom Handy landen hier im Verlauf, deine Playlists und Genres gehen aufs Handy. Direkt im eigenen WLAN – ohne Server dazwischen.")}<div id="phoneBox"></div>`,
    discord: () => `${sec("Discord-Status", "Zeig deinen Freunden in Discord, was gerade läuft – du bestimmst genau, was zu sehen ist.")}<div id="discordBox"></div>`,
    speicher: () => `${sec("Speicher &amp; Cache", "Was SH-Tunebridge auf deinem Rechner ablegt – und wie viele Online-Abfragen das schon erspart hat.")}<div id="storageBox"></div>`,
    nichterkannt: () => `${sec("Nicht erkannt", "Songs ohne Treffer oder ohne Genre – zum Nachtragen und um die Erkennung zu verbessern.")}<div id="missBox"></div>`,
    debug: () => `${sec("Debug-Protokoll")}<div id="debugBox"></div>`,
  };
  const cur = SETTING_TABS.find(t => t[0] === tab);
  main.innerHTML = `<div class="settings-shell">
    <aside class="set-side">
      <div class="set-side-head">Einstellungen</div>
      <button type="button" class="set-search" id="setSearch">${icon("search")}<span>In Einstellungen suchen …</span></button>
      ${SETTING_GROUPS.map(([label, tabs]) => `<div class="nav-label">${label}</div>
        ${tabs.map(([id, t, ic]) => `<a href="#/settings?tab=${id}" class="${id === tab ? "active" : ""}">${icon(ic)}<span>${t}</span></a>`).join("")}`).join("")}
      <div class="set-side-foot">Schlüssel werden nur lokal gespeichert – in deiner Konfigurationsdatei, lesbar nur für dich.</div>
    </aside>
    <div class="set-main" id="setMain"><div class="page view-enter">
      <div class="page-head"><div><h1>${esc(cur[1])}</h1></div></div>
      <div class="set-body">${body[tab]()}</div>
    </div></div>
  </div>`;
  hydrateIcons(main);
  if (tab === "allgemein") { Update.bind(main); if (params.get("update") && upd?.available && !upd.dev) Update.dialog(); }
  if (tab === "ki") { LLM.render($("#llmBox")); AI.render($("#aiBox")); }
  if (tab === "darstellung") Look.render($("#lookBox"));
  if (tab === "genres") Genres.render($("#genreBox"));
  if (tab === "datenschutz") Privacy.render($("#privacyBox"));
  if (tab === "gemeinschaft") Community.render($("#communityBox"));
  if (tab === "speicher") Storage.render($("#storageBox"));
  if (tab === "traffic") Traffic.render($("#trafficBox"));
  if (tab === "sicherung") await Views.backup($("#backupBox"));
  if (tab === "discord") DiscordUI.render($("#discordBox"));
  if (tab === "handy") PhoneUI.render($("#phoneBox"));
  if (tab === "nichterkannt") Misses.render($("#missBox"));
  if (tab === "debug") Debug.render($("#debugBox"));
  $("#setSearch", main).onclick = () => GSearch.open("", "settings");
  if (params.get("find")) settingsFind(params.get("find"));
  if (tab === "erkennung") $$("#vizSeg button").forEach(b => b.onclick = () => {
    Meter.setViz(b.dataset.viz);
    $$("#vizSeg button").forEach(x => x.classList.toggle("on", x === b));
    $("#vizHint").textContent = VIZ.find(x => x[0] === b.dataset.viz)[2];
    toast("Anzeige im Kreis gespeichert");
  });
  if (tab === "dienste") {
    Connect.bind($("#accounts"), main);
    $$("[data-acc]").forEach(c => { const a = accs.find(x => x.id === c.dataset.acc); c.dataset.state = (a.session?.state || "") + a.connected + JSON.stringify(a.session?.found || {}) + (a.session?.message || ""); });
    Connect.poll(main);
  }
  accs.filter(a => a.session?.state === "saved" && a.session.finished && Date.now() / 1000 - a.session.finished < 20)
    .forEach(a => toast(`${a.name} verbunden – ${a.session.message}`));
  accs.filter(a => a.session?.state === "closed" && Date.now() / 1000 - (a.session.started || 0) < 60)
    .forEach(a => toast(`${a.name}: ${a.session.message}`, "err"));
  $$(".set-row[data-key]").forEach(r => {
    const inp = $("input", r), save = async () => {
      try {
        await api("/api/settings", { method: "POST", body: { key: r.dataset.key, value: inp.value } });
        toast(inp.value ? "Gespeichert" : "Entfernt"); await refreshMeta(); Views.settings(main);
      } catch (e) { toast(e.message, "err"); }
    };
    $("[data-save]", r).onclick = save;
    inp.onkeydown = e => e.key === "Enter" && save();
  });
};

/* ================================================================= Dienste: Playlists ansehen & sortieren */
/* ---------- Playlists teilen (Ende-zu-Ende verschlüsselt; privater Schlüssel = lesen+schreiben, öffentlicher = nur lesen) */
const Share = {
  nicks: {},
  remember(st) { (st.friends || []).forEach(f => this.nicks[`friend-${f.id}`] = f.nick || f.name || "Freund"); },
  async call(path, body, method = "POST") {
    try { const st = await api(path, { method, body }); this.remember(st); return st; }
    catch (e) { toast(e.message, "err"); throw { silent: true }; }
  },
  consent() {
    modal({ title: "Playlists teilen erlauben?",
      body: `<div class="cons"><p class="cons-intro">Zum Teilen werden deine ausgewählten Playlists <b>auf deinem Rechner verschlüsselt</b> und nur als
        unlesbarer Block an den Server des Entwicklers gesendet.
        Der Server kennt weder Playlist-Namen noch Songs noch dich – nur eine zufällige Kennung und das Datum der letzten Änderung.
        Lesen kann es nur, wer deinen Schlüssel hat.</p>
        <label class="cons-check"><input type="checkbox" id="shC1"><span>Ich habe die <a href="${PRIVACY_URL}" target="_blank" rel="noopener">Datenschutzerklärung</a> gelesen und bin einverstanden.</span></label>
        <label class="cons-check"><input type="checkbox" id="shC2"><span>Ich erlaube, dass verschlüsselte Playlists an den Server des Entwicklers (Deutschland) gesendet werden.
          Ich teile nur eigene Playlists – es werden nur Titel, Künstler und Album geteilt, nie Musik oder Cover.</span></label></div>`,
      confirm: "Erlauben", wide: true,
      onConfirm: async box => {
        if (!$("#shC1", box).checked || !$("#shC2", box).checked) { toast("Bitte beide Punkte bestätigen", "err"); throw { silent: true }; }
        await api("/api/consent", { method: "POST", body: { privacy: true, server: { domain: true, share: true } } });
        route();
      } });
  },
  keyBox(label, key, hint, secret) {
    return `<div class="sh-key ${secret ? "sh-key--secret" : ""}"><div class="sh-key-head"><b>${label}</b><span class="hint">${hint}</span></div>
      <div class="sh-key-row"><code ${secret ? 'data-secret="1"' : ""}>${secret ? "•".repeat(28) : esc(key)}</code>
      ${secret ? `<button class="btn btn--sm btn--ghost" data-reveal>Anzeigen</button>` : ""}
      <button class="btn btn--sm" data-copykey="${esc(key)}">${icon("copy")}Kopieren</button></div></div>`;
  },
};

/* ================================================================= Öffentliches Playlist-Verzeichnis */
const nSongs = n => `${n} ${n === 1 ? "Song" : "Songs"}`;
const PubDir = {
  q: "", genre: "", page: 0, reasons: {},
  day: ts => new Date(ts * 1000).toLocaleDateString("de-DE"),
  consent() {
    modal({ title: "Playlist-Verzeichnis nutzen?", wide: true, confirm: "Erlauben",
      body: `<div class="cons"><p class="cons-intro">Das Verzeichnis liegt auf dem Server des Entwicklers (Deutschland). Beim <b>Stöbern</b> wird nur die Suchanfrage gesendet.
        <b>Veröffentlichen</b> geht nur einzeln, mit eigener Bestätigung – dann sind Playlist-Name, dein Pseudonym, Genre, Beschreibung und die Songliste für alle sichtbar.</p>
        <label class="cons-check"><input type="checkbox" id="pdC1"><span>Ich habe die <a href="${PRIVACY_URL}" target="_blank" rel="noopener">Datenschutzerklärung</a> gelesen und bin einverstanden.</span></label>
        <label class="cons-check"><input type="checkbox" id="pdC2"><span>Ich erlaube die Verbindung zum Server des Entwicklers für das öffentliche Verzeichnis.</span></label></div>`,
      onConfirm: async box => {
        if (!$("#pdC1", box).checked || !$("#pdC2", box).checked) { toast("Bitte beide Punkte bestätigen", "err"); throw { silent: true }; }
        await api("/api/consent", { method: "POST", body: { privacy: true, server: { domain: true, verzeichnis: true } } });
        route();
      } });
  },
  card(p) {
    return `<button class="card pd-card" data-pd="${p.id}">
      <div class="pd-top"><span class="li-title">${esc(p.name)}</span>${p.info ? tip(p.info) : ""}</div>
      <div class="cell-sub">von ${esc(p.alias)} · ${nSongs(p.n)}${p.genre ? ` · ${esc(p.genre)}` : ""} · ${this.day(p.updated)}</div></button>`;
  },
  async open(id) {
    let p; try { p = await api(`/api/pubdir/item/${id}`); } catch (e) { return toast(e.message, "err"); }
    const rows = (p.tracks || []).map((t, i) => `<li><span class="pd-n">${i + 1}</span><span class="pd-t">${esc(t.title)}</span><span class="cell-sub">${esc((t.artists || []).join(", "))}</span></li>`).join("");
    modal({ title: p.name, wide: true, cancel: "Schließen", confirm: "In meine Playlists übernehmen",
      text: `von ${esc(p.alias)} · ${nSongs(p.n)}${p.genre ? ` · ${esc(p.genre)}` : ""} · aktualisiert ${this.day(p.updated)}`,
      body: `${p.info ? `<p class="pd-info">${esc(p.info)}</p>` : ""}<ol class="pd-tracks">${rows}</ol>
        <div class="pd-foot"><button class="btn btn--sm btn--ghost" id="pdReport">${icon("flag")}Melden</button>
        <span class="cell-sub">Inhalte stammen von Nutzern. Rechtswidriges oder Persönliches bitte melden.</span></div>`,
      onConfirm: async () => {
        const r = await api("/api/pubdir/copy", { method: "POST", body: { id } });
        toast(`„${r.name}“ angelegt · ${nSongs(r.count)}`); refreshMeta();
      } });
    const box = $("#modalBox"); hydrateIcons(box);
    $("#pdReport", box).onclick = () => this.report(p);
  },
  report(p) {
    modal({ title: `„${p.name}“ melden`, confirm: "Meldung senden", danger: true,
      text: "Die Meldung geht an den Betreiber. Nach mehreren Meldungen verschiedener Nutzer wird die Playlist bis zur Prüfung ausgeblendet.",
      body: `<div class="field"><label>Grund</label><select class="input" id="pdRg">${Object.entries(this.reasons).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
        <div class="field" style="margin-top:10px"><label>Begründung (optional)</label><textarea class="input" id="pdRt" maxlength="500" rows="3" style="width:100%"></textarea></div>
        <p class="cell-sub" style="margin-top:8px">Bitte nur ehrlich und nach bestem Wissen melden. Gesendet wird nur der Grund, deine Begründung und die Kennung deiner Installation (gegen Mehrfach-Meldungen).</p>`,
      onConfirm: async box => {
        const r = await api("/api/pubdir/report", { method: "POST", body: { id: p.id, grund: $("#pdRg", box).value, text: $("#pdRt", box).value } });
        toast(r.schon_gemeldet ? "Du hast diese Playlist schon gemeldet" : "Danke – Meldung ist eingegangen");
      } });
  },
  async publish(pre = {}) {
    const [pls, mine] = await Promise.all([api("/api/playlists").catch(() => []), api("/api/pubdir/mine").catch(e => { toast(e.message, "err"); return null; })]);
    if (!mine) return;
    const locals = pls.filter(p => p.origin === "lokal" && p.count);
    if (!locals.length) return toast("Du hast noch keine eigenen Playlists mit Songs", "err");
    const pub = mine.map || {};
    modal({ title: "Playlist veröffentlichen", wide: true, confirm: "Veröffentlichen",
      body: `<div class="pd-form">
        <div class="field"><label>Playlist</label><select class="input" id="pdPl">${locals.map(p => `<option value="${esc(p.name)}" ${p.name === pre.name ? "selected" : ""}>${esc(p.name)} (${p.count})${pub[p.name] ? " – schon veröffentlicht, wird aktualisiert" : ""}</option>`).join("")}</select></div>
        <div class="field"><label>Dein Pseudonym ${tip("Ein Fantasiename, kein Klarname. Wird bei allen deinen Veröffentlichungen angezeigt.")}</label><input class="input" id="pdAl" maxlength="32" value="${esc(mine.alias || "")}" placeholder="z. B. BassKatze"></div>
        <div class="field"><label>Genre (optional)</label><input class="input" id="pdGe" maxlength="60" list="pdGenres" value="${esc(pre.genre || "")}"></div>
        <div class="field"><label>Beschreibung (optional)</label><textarea class="input" id="pdIn" maxlength="300" rows="2"></textarea></div>
        <p class="cell-sub">Keine Links, E-Mail-Adressen oder Telefonnummern. Höchstens 500 Songs, ${mine.max || 20} Playlists pro Installation.</p>
        <label class="cons-check"><input type="checkbox" id="pdOk1"><span>Mir ist klar: Name, Pseudonym, Genre, Beschreibung und die Songliste (Titel, Künstler, Album, ISRC, Länge, Dienst-IDs) sind <b>für alle sichtbar</b>. Keine Musik, keine Cover.</span></label>
        <label class="cons-check"><input type="checkbox" id="pdOk2"><span>Die Texte enthalten keine persönlichen Daten (keinen Klarnamen, keine Kontaktdaten) und verletzen keine Rechte anderer.</span></label>
        <p class="cell-sub">Löschen kannst du jederzeit unter „Meine Veröffentlichungen“. Ohne Aktualisierung löscht der Server nach 12 Monaten.</p></div>`,
      onConfirm: async box => {
        if (!$("#pdOk1", box).checked || !$("#pdOk2", box).checked) { toast("Bitte beide Punkte bestätigen", "err"); throw { silent: true }; }
        const r = await api("/api/pubdir/publish", { method: "POST", body: { name: $("#pdPl", box).value, alias: $("#pdAl", box).value,
          genre: $("#pdGe", box).value, info: $("#pdIn", box).value, confirm: true } });
        toast(`Veröffentlicht · ${nSongs(r.n)}${r.gekappt ? " (auf 500 gekürzt)" : ""}`); route();
      } });
    const box = $("#modalBox"); hydrateIcons(box);
    const fill = () => {        // schon veröffentlicht: bisheriges Genre / bisherige Beschreibung vorbelegen
      const cur = (mine.playlists || []).find(x => x.id === pub[$("#pdPl", box).value]);
      if (cur) { $("#pdGe", box).value = cur.genre || ""; $("#pdIn", box).value = cur.info || ""; }
    };
    $("#pdPl", box).onchange = fill; fill();
  },
  async mine(box) {
    box.innerHTML = `<div class="hint" style="padding:12px">Lade …</div>`;
    let d; try { d = await api("/api/pubdir/mine"); } catch (e) { box.innerHTML = `<div class="hint" style="padding:12px">${esc(e.message)}</div>`; return; }
    const names = Object.fromEntries(Object.entries(d.map || {}).map(([k, v]) => [v, k]));
    box.innerHTML = d.playlists.length ? d.playlists.map(p => `<div class="sh-pl pd-mine">
        <div style="min-width:0"><div class="li-title">${esc(p.name)} ${p.status === "sichtbar" ? `<span class="chip chip--ok">sichtbar</span>` : `<span class="chip chip--warn">${esc(p.status)}</span>`}</div>
          <div class="cell-sub">${nSongs(p.n)} · als ${esc(p.alias)} · aktualisiert ${this.day(p.updated)} · wird gelöscht am ${this.day(p.loeschung)} ohne Aktualisierung${p.grund ? ` · Grund: ${esc(p.grund)}` : ""}</div></div>
        ${names[p.id] ? `<button class="btn btn--sm btn--ghost" data-pdup="${esc(names[p.id])}" title="Mit dem aktuellen Stand deiner Playlist neu veröffentlichen">${icon("repeat")}Aktualisieren</button>` : ""}
        <button class="icon-btn" data-pddel="${p.id}" title="Aus dem Verzeichnis löschen">${icon("trash")}</button></div>`).join("")
        + `<div class="btn-row" style="padding:10px 14px"><button class="btn btn--sm btn--ghost" id="pdDelAll">${icon("trash")}Alle meine Veröffentlichungen löschen</button></div>`
      : `<div class="hint" style="padding:12px">Du hast noch nichts veröffentlicht.</div>`;
    hydrateIcons(box);
    $$("[data-pdup]", box).forEach(b => b.onclick = () => this.publish({ name: b.dataset.pdup }));
    $$("[data-pddel]", box).forEach(b => b.onclick = () => modal({ title: "Aus dem Verzeichnis löschen?", text: "Die Playlist verschwindet sofort für alle. Deine eigene Playlist bleibt.", confirm: "Löschen", danger: true,
      onConfirm: async () => { await api("/api/pubdir/delete", { method: "POST", body: { id: b.dataset.pddel } }); toast("Gelöscht"); route(); } }));
    const all = $("#pdDelAll", box);
    if (all) all.onclick = () => modal({ title: "Alles löschen?", text: "Alle deine Veröffentlichungen und Meldungen werden auf dem Server sofort gelöscht.", confirm: "Alles löschen", danger: true,
      onConfirm: async () => { const r = await api("/api/pubdir/delete", { method: "POST", body: { alle: true } }); toast(`${r.geloescht} gelöscht`); route(); } });
  },
};

Views.directory = async (main, _x, params) => {
  // Zustand kommt immer aus der Adresse – so stimmen Zurück/Vor und Lesezeichen
  PubDir.q = params?.get("q") || ""; PubDir.genre = params?.get("genre") || ""; PubDir.page = Math.max(0, +(params?.get("page") || 0) || 0);
  main.innerHTML = `<div class="page view-enter">${skeletonRows(3)}</div>`;
  const head = `<div class="page-head"><div><h1>Playlist-Verzeichnis</h1><p>Öffentliche Playlists anderer Nutzer durchstöbern und übernehmen – oder eigene veröffentlichen.
    Nur Songlisten, keine Musik. ${tip("Veröffentlicht wird nur, was du einzeln freigibst – unter einem Pseudonym. Du kannst jederzeit löschen. Gemeldete Inhalte werden geprüft.")}</p></div></div>`;
  const qs = new URLSearchParams({ q: PubDir.q, genre: PubDir.genre, page: PubDir.page });
  let d; try { d = await api(`/api/pubdir?${qs}`); } catch (e) {
    main.innerHTML = `<div class="page view-enter">${head}<div class="empty">${icon("info")}<h3>Verzeichnis nicht erreichbar</h3><p>${esc(e.message)}</p></div></div>`; return hydrateIcons(main);
  }
  PubDir.reasons = d.reasons || {};
  if (!d.allowed) {
    main.innerHTML = `<div class="page view-enter">${head}<div class="card sh-off"><div>${icon("globe")}</div><div><h3>Das Verzeichnis ist noch aus</h3>
      <p>Zum Stöbern und Veröffentlichen braucht es deine Einwilligung, weil das Verzeichnis auf dem Server des Entwicklers liegt.</p>
      <button class="btn btn--primary" id="pdAllow">Verzeichnis erlauben</button></div></div></div>`;
    hydrateIcons(main); $("#pdAllow").onclick = () => PubDir.consent(); return;
  }
  const pages = Math.max(1, Math.ceil(d.total / (d.seite || 30)));
  main.innerHTML = `<div class="page view-enter">${head}
    <div class="card pd-bar"><input class="input" id="pdQ" placeholder="Suchen: Name, Künstler, Pseudonym …" value="${esc(PubDir.q)}" maxlength="80">
      <select class="input" id="pdG"><option value="">Alle Genres</option>${(d.genres || []).map(g => `<option value="${esc(g.genre)}" ${g.genre === PubDir.genre ? "selected" : ""}>${esc(g.genre)} (${g.n})</option>`).join("")}</select>
      <button class="btn" id="pdGo">${icon("search")}Suchen</button>
      <button class="btn btn--primary" id="pdPub">${icon("globe")}Veröffentlichen</button></div>
    <datalist id="pdGenres">${(d.genres || []).map(g => `<option value="${esc(g.genre)}">`).join("")}</datalist>
    <div class="section-title">${d.total === 1 ? "1 Playlist" : `${d.total} Playlists`}${PubDir.q || PubDir.genre ? " gefunden" : ""}</div>
    ${d.playlists.length ? `<div class="pd-grid">${d.playlists.map(p => PubDir.card(p)).join("")}</div>`
      : `<div class="empty">${icon("globe")}<h3>${PubDir.q || PubDir.genre ? "Nichts gefunden" : "Noch leer"}</h3><p>${PubDir.q || PubDir.genre ? "Andere Suchwörter probieren." : "Sei die erste Person, die eine Playlist veröffentlicht."}</p></div>`}
    ${pages > 1 ? `<div class="btn-row pd-pages"><button class="btn btn--sm btn--ghost" id="pdPrev" ${PubDir.page ? "" : "disabled"}>Zurück</button>
      <span class="cell-sub">Seite ${PubDir.page + 1} von ${pages}</span><button class="btn btn--sm btn--ghost" id="pdNext" ${PubDir.page + 1 < pages ? "" : "disabled"}>Weiter</button></div>` : ""}
    <details class="card pd-minebox" id="pdMineBox"><summary>${icon("chevron")}<b>Meine Veröffentlichungen</b><span class="cell-sub">ändern, Status ansehen, löschen</span></summary><div id="pdMine"></div></details>
  </div>`;
  hydrateIcons(main);
  const go = page => { PubDir.q = $("#pdQ").value.trim(); PubDir.genre = $("#pdG").value; PubDir.page = page; location.hash = `#/directory?${new URLSearchParams({ q: PubDir.q, genre: PubDir.genre, page })}`; };
  $("#pdGo").onclick = () => go(0);
  $("#pdQ").onkeydown = e => { if (e.key === "Enter") go(0); };
  $("#pdG").onchange = () => go(0);
  const pv = $("#pdPrev"), nx = $("#pdNext");
  if (pv) pv.onclick = () => go(PubDir.page - 1);
  if (nx) nx.onclick = () => go(PubDir.page + 1);
  $("#pdPub").onclick = () => PubDir.publish();
  $$("[data-pd]", main).forEach(b => b.onclick = e => { if (!e.target.closest(".tip")) PubDir.open(b.dataset.pd); });
  $("#pdMineBox").ontoggle = e => { if (e.target.open) PubDir.mine($("#pdMine")); };
};

Views.share = async (main) => {
  main.innerHTML = `<div class="page view-enter">${skeletonRows(3)}</div>`;
  const [st, pls] = await Promise.all([api("/api/share"), api("/api/playlists").catch(() => [])]);
  Share.remember(st);
  const locals = pls.filter(p => p.origin === "lokal");
  const head = `<div class="page-head"><div><h1>Playlists teilen</h1><p>Teile eigene Playlists mit Freunden – über einen Schlüssel, ohne Konto.
    Der <b>öffentliche Schlüssel</b> zeigt nur die Playlists, die du freigibst (nur lesen). Mit dem <b>privaten Schlüssel</b> verwaltest du alles, z. B. von deinem zweiten Rechner.</p></div></div>`;
  const legal = `<div class="hint gdb-note">${icon("info")}<span>Geteilt werden nur <b>Titel, Künstler, Album, ISRC und Genre</b> – keine Musik, keine Cover, keine Hörproben.
    Alles wird auf deinem Rechner verschlüsselt (AES-256); der Server sieht nur unlesbare Blöcke. Teile nur eigene Playlists.
    Unbenutzte Bereiche löscht der Server nach einem Jahr.</span></div>`;
  if (!st.allowed) {
    main.innerHTML = `<div class="page view-enter">${head}
      <div class="card sh-off"><div>${icon("key")}</div><div><h3>Teilen ist noch aus</h3>
        <p>Zum Teilen braucht es deine Einwilligung, weil verschlüsselte Playlists über den Server des Entwicklers laufen. Freunde-Playlists ansehen braucht sie auch.</p>
        <button class="btn btn--primary" id="shAllow">Teilen erlauben</button></div></div>${legal}</div>`;
    hydrateIcons(main);
    $("#shAllow").onclick = () => Share.consent();
    return;
  }
  const mine = !st.active ? `<div class="sh-start">
      <div class="card"><h3>${icon("plus")}Neu anlegen</h3><p class="hint">Erstellt deinen Teilen-Bereich mit einem privaten und einem öffentlichen Schlüssel.</p>
        <div class="sh-in"><input class="input" id="shName" placeholder="Name, den Freunde sehen (z. B. „Leons Playlists“)" maxlength="80"><button class="btn btn--primary" id="shCreate">Anlegen</button></div></div>
      <div class="card"><h3>${icon("key")}Mit privatem Schlüssel verbinden</h3><p class="hint">Du hast schon einen Bereich (z. B. auf deinem anderen Rechner)? Privaten Schlüssel <code>SHT-P-…</code> einfügen.</p>
        <div class="sh-in"><input class="input" id="shJoin" placeholder="SHT-P-…" autocomplete="off" spellcheck="false"><button class="btn" id="shJoinGo">Verbinden</button></div></div>
    </div>`
    : `<div class="card sh-space">
      <div class="sh-space-head"><div><div class="cell-sub">Dein Teilen-Bereich</div><h3>${esc(st.name || "Ohne Namen")} <button class="icon-btn" id="shRename" title="Umbenennen">${icon("pencil")}</button></h3></div>
        <div class="btn-row"><button class="btn btn--sm btn--ghost" id="shSync" title="Geteilte Playlists mit dem aktuellen Stand deiner Playlists hochladen">${icon("repeat")}Aktualisieren</button>
        <button class="btn btn--sm btn--ghost" id="shLeave" title="Schlüssel von diesem Rechner entfernen – geteilte Playlists bleiben">Von diesem Rechner trennen</button>
        <button class="btn btn--sm btn--ghost" id="shDel">${icon("trash")}Bereich löschen</button></div></div>
      ${Share.keyBox("Öffentlicher Schlüssel", st.public_key, "an Freunde geben – nur lesen, nur freigegebene Playlists", false)}
      ${Share.keyBox("Privater Schlüssel", st.private_key, "wie ein Passwort: nie weitergeben! Lesen und ändern, alle Playlists", true)}
    </div>
    <div class="section-title">Geteilte Playlists <span class="cell-sub">${st.playlists.length}</span>
      <button class="btn btn--sm btn--primary" id="shAdd" style="margin-left:auto">${icon("plus")}Playlists hinzufügen</button></div>
    ${st.playlists.length ? `<div class="card gdb-votes">${st.playlists.map(p => `<div class="sh-pl" data-pid="${p.id}">
        <div style="min-width:0"><div class="li-title">${esc(p.name)}</div><div class="cell-sub">${p.count} Songs${p.local ? "" : " · von einem anderen Rechner"}</div></div>
        <label class="switch-row" title="Öffentlich = sichtbar für alle mit dem öffentlichen Schlüssel"><label class="switch"><input type="checkbox" data-pub="${p.id}" ${p.public ? "checked" : ""}><span class="track"></span></label><span>${p.public ? "öffentlich" : "nur privat"}</span></label>
        <button class="icon-btn" data-rm="${p.id}" title="Nicht mehr teilen">${icon("x")}</button></div>`).join("")}</div>`
      : `<div class="empty">${icon("stack")}<h3>Noch nichts geteilt</h3><p>Füge Playlists hinzu und lege fest, welche öffentlich sind.</p></div>`}`;
  const friends = `<div class="section-title">Von Freunden <span class="cell-sub">${st.friends.length}</span></div>
    <div class="card sh-addf"><input class="input" id="shFKey" placeholder="Öffentlichen Schlüssel einfügen (SHT-O-…)" autocomplete="off" spellcheck="false">
      <input class="input" id="shFNick" placeholder="Name (optional)" maxlength="60"><button class="btn btn--primary" id="shFAdd">Hinzufügen</button></div>
    <div id="shFriends">${st.friends.map(f => `<div class="card sh-friend" data-fid="${f.id}">
      <div class="sh-friend-head"><div><h4>${esc(f.nick || f.name || "Freund")}</h4><div class="cell-sub">${esc(f.name && f.nick ? f.name : "")}</div></div>
        <div class="btn-row"><button class="btn btn--sm btn--ghost" data-fre="${f.id}">${icon("repeat")}Neu laden</button>
        <button class="icon-btn" data-frm="${f.id}" title="Entfernen">${icon("trash")}</button></div></div>
      <div class="sh-flists" data-fl="${f.id}"><div class="hint">Lade …</div></div></div>`).join("")}</div>`;
  main.innerHTML = `<div class="page view-enter">${head}${mine}${friends}${legal}</div>`;
  hydrateIcons(main);

  $$("[data-copykey]", main).forEach(b => b.onclick = async () => toast(await Clip.write(b.dataset.copykey) ? "Schlüssel kopiert" : "Kopieren fehlgeschlagen", "ok"));
  $$("[data-reveal]", main).forEach(b => b.onclick = () => {
    const c = $("code", b.parentElement); const show = c.dataset.secret === "1";
    c.textContent = show ? st.private_key : "•".repeat(28); c.dataset.secret = show ? "0" : "1"; b.textContent = show ? "Verbergen" : "Anzeigen";
  });
  const go = async (path, body, method) => { await Share.call(path, body, method).catch(() => null); route(); };
  const btn = (id, fn) => { const b = $(id, main); if (b) b.onclick = fn; };
  btn("#shCreate", async () => { await Share.call("/api/share/create", { name: $("#shName").value }).then(() => toast("Teilen-Bereich angelegt")).catch(() => null); route(); });
  btn("#shJoinGo", async () => { await Share.call("/api/share/join", { key: $("#shJoin").value }).then(() => toast("Verbunden")).catch(() => null); route(); });
  btn("#shSync", async () => { await Share.call("/api/share/sync").then(() => toast("Aktualisiert")).catch(() => null); route(); });
  btn("#shRename", () => modal({ title: "Namen ändern", body: `<input class="input" id="shRn" maxlength="80" style="width:100%" value="${esc(st.name)}">`, confirm: "Speichern",
    onConfirm: async box => { await Share.call("/api/share/rename", { name: $("#shRn", box).value }); route(); } }));
  btn("#shLeave", () => modal({ title: "Von diesem Rechner trennen?", text: "Der Schlüssel wird hier gelöscht. Deine geteilten Playlists bleiben auf dem Server – mit dem privaten Schlüssel kannst du dich wieder verbinden. Hast du ihn nicht notiert, kommst du nicht mehr heran.",
    confirm: "Trennen", danger: true, onConfirm: () => go("/api/share/leave") }));
  btn("#shDel", () => modal({ title: "Teilen-Bereich löschen?", text: "Alle geteilten Playlists werden vom Server gelöscht. Beide Schlüssel funktionieren danach nicht mehr – auch nicht bei deinen Freunden. Deine Playlists in der App bleiben.",
    confirm: "Endgültig löschen", danger: true, onConfirm: () => go("/api/share/delete") }));
  btn("#shAdd", () => {
    const shared = new Set(st.playlists.map(p => p.local).filter(Boolean));
    const avail = locals.filter(p => !shared.has(p.name));
    if (!avail.length) return toast(locals.length ? "Alle deine Playlists sind schon geteilt" : "Du hast noch keine eigenen Playlists", "err");
    modal({ title: "Playlists teilen", wide: true,
      body: `<div class="sh-pick">${avail.map(p => `<label class="cons-check"><input type="checkbox" data-n="${esc(p.name)}"><span>${esc(p.name)} <span class="cell-sub">· ${p.count} Songs</span></span></label>`).join("")}</div>
        <label class="switch-row" style="margin-top:12px"><label class="switch"><input type="checkbox" id="shPub"><span class="track"></span></label><span>Gleich öffentlich machen (für alle mit dem öffentlichen Schlüssel sichtbar)</span></label>`,
      confirm: "Teilen",
      onConfirm: async box => {
        const names = $$("[data-n]:checked", box).map(i => i.dataset.n);
        if (!names.length) { toast("Bitte mindestens eine Playlist wählen", "err"); throw { silent: true }; }
        await Share.call("/api/share/playlists", { names, public: $("#shPub", box).checked }); toast("Geteilt"); route();
      } });
  });
  $$("[data-pub]", main).forEach(i => i.onchange = async () => {
    try { await Share.call(`/api/share/playlists/${i.dataset.pub}/public`, { public: i.checked }); i.closest(".switch-row").lastElementChild.textContent = i.checked ? "öffentlich" : "nur privat"; }
    catch { i.checked = !i.checked; }
  });
  $$("[data-rm]", main).forEach(b => b.onclick = () => go(`/api/share/playlists/${b.dataset.rm}`, undefined, "DELETE"));
  btn("#shFAdd", async () => {
    const key = $("#shFKey").value.trim(); if (!key) return toast("Bitte einen Schlüssel einfügen", "err");
    await Share.call("/api/share/friends", { key, nick: $("#shFNick").value }).then(() => { toast("Hinzugefügt"); SideSvc.pls = {}; }).catch(() => null); route();
  });
  $$("[data-frm]", main).forEach(b => b.onclick = () => modal({ title: "Freund entfernen?", text: "Seine geteilten Playlists verschwinden hier. Was du schon in deine Playlists kopiert hast, bleibt.", confirm: "Entfernen", danger: true,
    onConfirm: () => go(`/api/share/friends/${b.dataset.frm}`, undefined, "DELETE") }));
  const loadF = async (fid, fresh = false) => {
    const box = $(`[data-fl="${fid}"]`, main); if (!box) return;
    const sid = `friend-${fid}`;
    try {
      const lists = await api(`/api/services/${sid}/playlists${fresh ? "?refresh=1" : ""}`);
      box.innerHTML = lists.length ? lists.map(p => `<div class="sh-fl"><a href="${svcPlHref(sid, p)}">${icon("stack")}<span>${esc(p.name)}</span><em>${p.count} Songs</em></a>
          <button class="btn btn--sm btn--ghost" data-cp="${esc(p.id)}" data-cpn="${esc(p.name)}">${icon("download")}In meine Playlists</button></div>`).join("")
        : `<div class="hint">Gerade ist nichts öffentlich geteilt.</div>`;
      hydrateIcons(box);
      $$("[data-cp]", box).forEach(b => b.onclick = () => Share.copy(fid, b.dataset.cp, b.dataset.cpn));
    } catch (e) { box.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
  };
  st.friends.forEach(f => loadF(f.id));
  $$("[data-fre]", main).forEach(b => b.onclick = () => loadF(b.dataset.fre, true));
};
// Freundes-Playlist übernehmen: in eine bestehende oder neue eigene Playlist (früher nur neu)
Share.copy = async (fid, pid, name) => { await refreshMeta(); plMergeTo(`friend-${fid}`, pid, name); };

const SVC_STYLE = {
  spotify: ["S", "#1ed760"], tidal: ["T", "#d6dbe2"], youtube: ["YT", "#ff5a50"], deezer: ["D", "#a238ff"],
  lastfm: ["fm", "#d51007"], apple: ["A", "#fa6a86"], soundcloud: ["SC", "#ff8a3d"], shazam: ["Sh", "#0a8cff"],
};
const svcStyle = sid => SVC_STYLE[sid] || (String(sid).startsWith("friend-") ? ["♪", "#8b8cf8"] : ["?", "#888"]);
const SORT_LEVELS = [
  [1, "Passende Mixes", "Tempo-Blöcke von etwa einer Stunde, Reihenfolge nach Tempo, Tonart und Energie – Genre egal."],
  [2, "Stimmung & Energie", "Chill · Groove · Energie · Peak – darin mixbar geordnet."],
  [3, "Feinsäuberlich", "Stimmung × Tempobereich (z. B. „Peak · 170–180 BPM“), darin mixbar geordnet."],
  [4, "Genre-Familie", "Grobe Richtung: Elektronisch, Hip-Hop & R&B, Rock & Indie …"],
  [5, "Genre", "Die Hauptgenres: Drum & Bass, Phonk, House …"],
  [6, "Mikro-Genre", "Subgenre, z. B. „Drum & Bass – Liquid“. Unsichere Songs bleiben beim Hauptgenre."],
];
const SORT_STATE = { queued: "Startet …", loading: "Lade Playlist …", analysing: "Analysiere Songs (Genre, Tempo, Tonart) …", ai: "KI prüft die Genres …" };
const Sorter = { job: null, svc: null, groups: null, level: store.get("sortLevel", 6), min: store.get("sortMin", 3) };

Views.services = async (main, _, params) => {
  const sid = params.get("svc"), pid = params.get("pl");
  if (sid && params.get("view")) return Views.svcPlaylist(main, sid, params.get("view"), params.get("name") || "");
  if (sid && pid) return Views.sortPreview(main, sid, pid, params.get("name") || "");
  if (sid) return Views.servicePlaylists(main, sid);
  main.innerHTML = `<div class="page view-enter"><div class="page-head"><div><h1>Dienste</h1><p>Deine Playlists bei den Musikanbietern ansehen und als Vorschau sortieren lassen – vom passenden Mix bis zum Mikro-Genre.</p></div></div>${skeletonRows(3)}</div>`;
  const list = await api("/api/services");
  SideSvc.load(list);
  const card = s => {
    const [m, c] = SVC_STYLE[s.id] || ["?", "#888"];
    const off = !s.ready;
    const badge = s.ready && s.account ? `<span class="acc-badge ok">${icon("check")}${esc(s.account)}</span>`
      : s.kind === "none" ? `<span class="acc-badge">Nicht möglich</span>` : s.kind === "file" ? `<span class="acc-badge">Datei</span>`
      : s.error ? `<span class="acc-badge warn">Angemeldet, aber gesperrt</span>` : `<span class="acc-badge">Nicht verbunden</span>`;
    let act = "";
    const imp = s.mode === "import";
    const impBtns = s.importable ? (s.import
      ? `<button class="btn btn--sm btn--ghost" data-imp="${s.id}">${icon("upload")}Neu importieren</button><button class="btn btn--sm btn--ghost" data-impdel="${s.id}">Import löschen</button>`
      : (s.kind === "account" && !s.ready) ? "" : `<button class="btn btn--sm btn--ghost" data-imp="${s.id}">${icon("upload")}Datei importieren</button>`) : "";
    if (s.kind === "account") {
      if (s.ready && !imp) act = `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button>`;
      else if (imp) act = `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button>${SETUP[s.id] ? `<button class="btn btn--sm btn--ghost" data-connect="${s.id}">${icon("key")}Direkt verbinden</button>` : ""}`;
      else act = s.needs === "connect" ? `<button class="btn btn--sm btn--primary" data-login="${s.id}">${icon("key")}Verbinden</button>`
        : `<button class="btn btn--sm btn--primary" data-connect="${s.id}">${icon("key")}Verbinden</button>`;
      if (s.ready && !imp && s.mode !== "profile" && ["youtube", "soundcloud"].includes(s.id)) act += `<button class="btn btn--sm btn--ghost" data-logout="${s.id}">Trennen</button>`;
      if (s.id === "youtube" && !imp) act += s.mode === "profile" ? `<button class="btn btn--sm btn--ghost" data-login="${s.id}">${icon("key")}Mit Google anmelden</button><button class="btn btn--sm btn--ghost" data-profile="${s.id}">Kanal ändern</button>`
        : !s.ready ? `<button class="btn btn--sm btn--ghost" data-profile="${s.id}" title="Nur öffentliche Playlists, braucht einen YouTube-API-Key">Nur Kanal-Link</button>` : "";
      if (!s.ready && s.needs === "connect" && IMPORT[s.id]) act += `<button class="btn btn--sm btn--ghost" data-imp="${s.id}">${icon("upload")}Datei importieren</button>`;
      if (s.ready && !imp && SETUP[s.id]) act += `<button class="btn btn--sm btn--ghost" data-redo="${s.id}" title="Zugangsdaten deiner Entwickler-App ändern">Einrichtung ändern</button>`;
      if (imp || s.ready) act += impBtns;
    }
    else if (s.id === "lastfm") {
      if (s.ready) act = `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button>`
        + (s.login ? `<button class="btn btn--sm btn--ghost" data-lfout>Abmelden</button>` : `<button class="btn btn--sm btn--ghost" data-lflogin>${icon("key")}Mit Last.fm anmelden</button>`);
      else act = `<button class="btn btn--sm btn--primary" data-lflogin>${icon("key")}Mit Last.fm anmelden</button>`
        + (s.needs === "profile" ? `<button class="btn btn--sm btn--ghost" data-profile="${s.id}" title="Ohne Anmeldung: nur öffentliche Loved Tracks">Nur Benutzername</button>` : "");
      if (s.needs !== "key") act += `<button class="btn btn--sm btn--ghost" data-redo="${s.id}" title="API key und Shared secret ändern">Einrichtung ändern</button>`;
    }
    else if (s.id === "deezer") act = s.ready
      ? `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button><button class="btn btn--sm btn--ghost" data-redo="${s.id}">Profil ändern</button><button class="btn btn--sm btn--ghost" data-unprofile="${s.id}">Trennen</button>`
      : `<button class="btn btn--sm btn--primary" data-redo="${s.id}">${icon("key")}Einrichten</button>`;
    else if (s.kind === "profile") act = s.needs === "key" ? `<button class="btn btn--sm btn--primary" data-redo="${s.id}">${icon("key")}Einrichten</button>`
      : s.ready ? `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button><button class="btn btn--sm btn--ghost" data-profile="${s.id}">Profil ändern</button>`
      : `<button class="btn btn--sm" data-profile="${s.id}">${icon("key")}Profil verknüpfen</button>`;
    else if (s.kind === "file") act = s.import ? `<button class="btn btn--sm btn--primary" data-open="${s.id}">${icon("stack")}Playlists</button>${impBtns}`
      : `<button class="btn btn--sm btn--primary" data-imp="${s.id}">${icon("upload")}${s.id === "shazam" ? "Shazams importieren" : "Mediathek importieren"}</button>`;
    return `<div class="card platform svc-card ${off ? "planned" : ""}"><div class="p-logo" style="--pc:${c}">${m}</div>
      <div><h4>${esc(s.name)} ${badge}</h4><p>${esc(s.note)}</p>${s.error && !s.ready ? `<p class="svc-err">${icon("info")}${esc(s.error)}</p>` : ""}<div class="btn-row">${act}</div></div></div>`;
  };
  const scanable = list.filter(s => (s.ready || s.import) && s.kind !== "none");
  $(".page", main).innerHTML = `<div class="page-head"><div><h1>Dienste</h1><p>Deine Playlists bei den Musikanbietern ansehen und als Vorschau sortieren lassen – vom passenden Mix bis zum Mikro-Genre. Gelesen werden nur Titel, Künstler und Album – nie Musik.</p></div>
      ${scanable.length ? `<div class="actions"><button class="btn btn--primary" id="scanAll">${icon("layers")}Alles einlesen</button></div>` : ""}</div>
    <div class="platforms">${list.map(card).join("")}</div>`;
  hydrateIcons(main);
  const sa = $("#scanAll", main); if (sa) sa.onclick = () => scanAllDialog(scanable);
  $$("[data-open]", main).forEach(b => b.onclick = () => location.hash = `#/services?svc=${b.dataset.open}`);
  $$("[data-login]", main).forEach(b => b.onclick = async () => { const plats = await api("/api/platforms"); platformLogin(plats.find(p => p.id === b.dataset.login), main); });
  $$("[data-connect]", main).forEach(b => b.onclick = () => connectService(b.dataset.connect, main));
  $$("[data-redo]", main).forEach(b => b.onclick = () => setupWizard(b.dataset.redo, main));
  $$("[data-imp]", main).forEach(b => b.onclick = () => importWizard(b.dataset.imp, main));
  $$("[data-impdel]", main).forEach(b => b.onclick = () => modal({ title: "Import löschen?", text: "Die importierten Playlists werden aus SH-Tunebridge entfernt. Bei deinem Dienst ändert sich nichts.", confirm: "Löschen", danger: true,
    onConfirm: async () => { await api(`/api/services/${b.dataset.impdel}/import`, { method: "DELETE" }); SideSvc.loaded = false; route(); } }));
  $$("[data-logout]", main).forEach(b => b.onclick = () => modal({ title: "Verbindung trennen?", text: "Das gespeicherte Login-Token wird auf diesem Rechner gelöscht. Deine App-Daten (Client-ID) bleiben eingetragen.", confirm: "Trennen", danger: true,
    onConfirm: async () => { await api(`/api/platforms/${b.dataset.logout}/logout`, { method: "POST" }); SideSvc.loaded = false; route(); } }));
  $$("[data-lflogin]", main).forEach(b => b.onclick = () => {
    const s = list.find(x => x.id === "lastfm");
    if (!s.login_ready) return setupWizard("lastfm", main);
    platformLogin({ id: "lastfm", name: "Last.fm" }, main);
  });
  $$("[data-lfout]", main).forEach(b => b.onclick = async () => { await api("/api/lastfm/logout", { method: "POST" }); toast("Bei Last.fm abgemeldet"); route(); });
  $$("[data-unprofile]", main).forEach(b => b.onclick = async () => { await api(`/api/services/${b.dataset.unprofile}/profile`, { method: "POST", body: { value: "" } }); toast("Getrennt"); route(); });
  $$("[data-profile]", main).forEach(b => b.onclick = () => {
    const id = b.dataset.profile, ph = { deezer: "https://www.deezer.com/de/profile/123456", lastfm: "Benutzername oder last.fm/user/…", youtube: "https://www.youtube.com/@deinkanal" }[id];
    modal({ title: `${list.find(x => x.id === id).name}: Profil verknüpfen`, text: id === "deezer" ? "Dein Profil muss in Deezer öffentlich sein (Einstellungen › Datenschutz)." : id === "youtube" ? "Es werden nur die öffentlichen Playlists des Kanals gelesen." : "Es werden nur deine öffentlichen Loved Tracks gelesen.",
      body: `<input class="input" id="pfIn" placeholder="${esc(ph)}" autocomplete="off" spellcheck="false" style="width:100%">`, confirm: "Speichern",
      onConfirm: async box => { try { await api(`/api/services/${id}/profile`, { method: "POST", body: { value: $("#pfIn", box).value } }); toast("Profil gespeichert"); route(); } catch (e) { toast(e.message, "err"); throw { silent: true }; } } });
  });
};

Views.servicePlaylists = async (main, sid) => {
  const [m, c] = svcStyle(sid);
  if (!SideSvc.loaded) await SideSvc.load();
  const s = SideSvc.list.find(x => x.id === sid) || { id: sid, name: SVC_NAME(sid), account: "" };
  main.innerHTML = `<div class="page view-enter">
    <section class="pls-hero" style="--hc:${c}"><div><a class="ph-back" href="#/services">← Dienste</a>
      <div class="ph-kicker"><span class="ss-badge sm" style="--pc:${c}">${m}</span>${esc(s.name)}${s.account ? ` · ${esc(s.account)}` : ""}</div><h1>Playlists</h1>
      <p>Ansehen, reinhören oder als Vorschau sortieren lassen. An deinem Dienst ändert sich dabei nichts.</p></div>
      <div class="pls-stats" id="svcStats"></div></section>
    <div class="pls-bar"><div class="ph-tools" style="margin-left:0">
      <label class="ph-search">${icon("search")}<input id="plsQ" placeholder="Playlist suchen" autocomplete="off" spellcheck="false"></label>
      <button class="btn btn--sm btn--ghost" id="svcRe">${icon("repeat")}Neu laden</button></div></div>
    <div id="plsOut"><div class="pl-grid">${Array.from({ length: 6 }, () => `<div class="pl-card"><div class="mosaic skeleton"></div><div class="skeleton" style="height:12px;width:70%;margin-top:12px"></div></div>`).join("")}</div></div></div>`;
  hydrateIcons(main);
  let q = "";
  const draw = async (fresh = false) => {
    const lists = await SideSvc.fetch(sid, fresh);
    const out = $("#plsOut"); if (!out) return;
    if (lists?.error) { out.innerHTML = `<div class="notice">${icon("info")}<div>${esc(lists.error)}</div></div>`; hydrateIcons(out); return; }
    $("#svcStats").innerHTML = `<div><b class="num">${lists.length}</b><span>Playlists</span></div><div><b class="num">${lists.reduce((a, p) => a + (p.count || 0), 0)}</b><span>Songs</span></div>`;
    const l = lists.filter(p => !q || p.name.toLowerCase().includes(q));
    out.innerHTML = l.length ? `<div class="pl-grid">${l.map(p => svcCard(sid, p)).join("")}</div>` : `<div class="empty"><h3>Keine Playlists gefunden</h3></div>`;
    hydrateIcons(out); bindCardPlay(out);
  };
  $("#plsQ").oninput = e => { q = e.target.value.trim().toLowerCase(); draw(); };
  $("#svcRe").onclick = () => draw(true);
  draw();
};

Views.svcPlaylist = async (main, sid, pid, name) => {
  const [m, c] = svcStyle(sid);
  if (!SideSvc.loaded) await SideSvc.load();
  const sname = SideSvc.list.find(x => x.id === sid)?.name || SVC_NAME(sid);
  main.innerHTML = `<div class="page page--pl view-enter"><section class="ph" style="--hc:${c}"><div class="ph-art"><div class="mosaic skeleton"></div></div>
    <div class="ph-info"><div class="ph-kicker">Playlist · ${esc(sname)}</div><h1>${esc(name)}</h1><div class="ph-meta">Lade Songs …</div></div></section>${skeletonRows(6)}</div>`;
  let tracks;
  try { tracks = await svcTracks(sid, pid); }
  catch (e) { $(".page", main).insertAdjacentHTML("beforeend", `<div class="notice">${icon("info")}<div>${esc(e.message)}</div></div>`); $(".rows", main)?.remove(); hydrateIcons(main); return; }
  if (!document.body.contains(main) || !location.hash.includes(`view=${encodeURIComponent(pid)}`)) return;
  const ms = tracks.reduce((a, t) => a + (t.duration_ms || 0), 0);
  const covers = [...new Set(tracks.map(t => t.cover).filter(Boolean))].slice(0, 4);
  const sortHref = `#/services?svc=${sid}&pl=${encodeURIComponent(pid)}&name=${encodeURIComponent(name)}`;
  main.innerHTML = `<div class="page page--pl view-enter">
    ${plHero({ kicker: `<span class="ss-badge sm" style="--pc:${c}">${m}</span>Playlist · ${esc(sname)}`, title: name, count: tracks.length, ms, covers, color: c,
      back: sid.startsWith("friend-") ? ["#/share", "Teilen"] : [`#/services?svc=${sid}`, `${sname}-Playlists`],
      sorts: [["", "Reihenfolge"], ["title", "Titel"], ["artist", "Künstler"], ["album", "Album"], ["dur", "Länge"]],
      actions: `<a class="btn btn--sm btn--primary" href="${sortHref}">${icon("layers")}Sortieren lassen</a>
        <button class="btn btn--sm btn--ghost" id="plCopy" title="Songs in eine bestehende oder neue lokale Playlist übernehmen">${icon("download")}In meine Playlists</button>
        <button class="btn btn--sm btn--ghost" id="plReload">${icon("repeat")}Neu laden</button>` })}
    <div class="pls-src">${icon("info")}${sid.startsWith("friend-") ? `Geteilt von ${esc(sname)} (Ende-zu-Ende verschlüsselt, nur Titel/Künstler/Album). Hörproben suchst du über die Song-Details selbst.` : `Titel, Künstler und Cover-Adressen kommen über die offizielle Schnittstelle von ${esc(sname)} und liegen nur im Arbeitsspeicher. Hörproben (30 s) werden direkt beim Anbieter gestreamt.`}</div>
    <div class="tl tl--svc" id="plList"></div></div>`;
  hydrateIcons(main);
  plList(main, tracks.map(t => ({ t, c3: `<span class="cell-muted">${esc(t.album || "")}</span>`, c4: t.duration_ms ? fmtTime(t.duration_ms / 1000) : "" })),
    { h3: "Album", h4: "Länge", empty: "Diese Playlist ist leer.", bind: box => {
      $$(".tl-row", box).forEach(row => row.ondblclick = () => $(".tl-play", row)?.click());
    } });
  $("#plCopy").onclick = async () => { await refreshMeta(); plMergeTo(sid, pid, name); };
  $("#plReload").onclick = async () => { await svcTracks(sid, pid, true).catch(e => toast(e.message, "err")); Views.svcPlaylist(main, sid, pid, name); };
};

/* „Alles einlesen“: alle verbundenen Dienste auf einmal in die Sortier-Vorschau */
function scanAllDialog(scanable) {
  const row = (id, lbl, hint, on) => `<label class="cons-row"><span class="switch"><input type="checkbox" data-sa="${id}" ${on ? "checked" : ""}><span class="track"></span></span>
    <div><div class="lbl">${lbl}</div>${hint ? `<div class="hint">${hint}</div>` : ""}</div></label>`;
  modal({ title: "Alles einlesen", wide: true, confirm: "Einlesen starten",
    body: `<div class="cons"><p class="cons-intro">Liest deine Musik aus allen gewählten Diensten auf einmal ein, führt doppelte Songs zusammen
      und zeigt danach die Sortier-Vorschau – gespeichert wird erst, wenn du dort „Übernehmen“ klickst.</p>
      <div class="cons-h">Dienste</div>
      ${scanable.map(s => row(`svc:${s.id}`, esc(s.name), s.account ? esc(s.account) : s.import ? "importierte Datei" : "", true)).join("")}
      <div class="cons-h">Was einlesen?</div>
      ${row("k:liked", "Lieblingssongs", "Gelikte Songs / Loved Tracks", true)}
      ${row("k:own", "Eigene Playlists", "", true)}
      ${row("k:followed", "Gefolgte Playlists anderer", "Playlists, die du nur abonniert hast – oft sehr groß", false)}
      <p class="hint" style="margin-top:10px">Grenzen: höchstens 300 Playlists pro Dienst und 80.000 verschiedene Songs. Bittet ein Dienst um eine Pause,
      wartet die App sie ab – große Bibliotheken brauchen deshalb etwas Zeit (läuft im Hintergrund weiter). Gelesen wird nur über die offiziellen
      Schnittstellen mit deinem eigenen Login.</p></div>`,
    onConfirm: box => {
      const on = $$("[data-sa]", box).filter(i => i.checked).map(i => i.dataset.sa);
      const sids = on.filter(x => x.startsWith("svc:")).map(x => x.slice(4)), kinds = on.filter(x => x.startsWith("k:")).map(x => x.slice(2));
      if (!sids.length || !kinds.length) { toast("Bitte mindestens einen Dienst und eine Art auswählen", "err"); throw { silent: true }; }
      location.hash = `#/services?svc=__all__&pl=${encodeURIComponent(`${sids.join(",")}|${kinds.join(",")}`)}&name=${encodeURIComponent("Alle Dienste")}`;
    } });
}

Views.sortPreview = async (main, sid, pid, name) => {
  const ai = await api("/api/ai").catch(() => null);
  const aiOk = !!ai?.ready?.[0];
  const same = Sorter.job && Sorter.svc === sid && Sorter.pl === pid;
  main.innerHTML = `<div class="page view-enter">
    <div class="page-head"><div><a href="#/services${sid === "apple" || sid === "__all__" ? "" : `?svc=${sid}`}" class="muted" style="font-size:13px">← zurück</a><h1>${esc(name || "Playlist")} sortieren</h1>
      <p>Erst eine Vorschau: Die Songs werden analysiert (Genre, Mikro-Genre, Tempo, Tonart, Energie) und in Gruppen eingeteilt. Gespeichert wird erst, wenn du „Übernehmen“ klickst.</p></div></div>
    <div class="card sort-head">
      <div class="set-row"><div><div class="lbl">${icon("sparkle")} Mit KI prüfen</div><div class="hint">${aiOk ? `Die KI (${esc(ai.providers.find(p => p.id === ai.provider)?.name || ai.provider)}) kontrolliert die Genres und korrigiert nur, wo sie sich sicher ist. Gesendet werden Künstler, Titel, Tags.` : `Nicht eingerichtet: ${esc(ai?.ready?.[1] || "KI aus")} – <a href="#/settings?tab=ki">Einstellungen › KI</a>`}</div></div><div></div>
        <label class="switch"><input type="checkbox" id="srtAi" ${aiOk && (ai.review || false) ? "checked" : ""} ${aiOk ? "" : "disabled"}><span class="track"></span></label></div>
      <div class="btn-row" style="padding:4px 2px 2px"><button class="btn btn--primary" id="srtGo">${icon("layers")}${same ? "Neu analysieren" : "Vorschau erstellen"}</button>
        <span class="cell-sub" id="srtHint">Pro Song einmal ein paar Abfragen – bekannte Songs kommen aus dem Speicher.</span></div>
    </div>
    <div id="srtJob"></div><div id="srtOut"></div></div>`;
  hydrateIcons(main);
  $("#srtGo").onclick = async () => {
    const body = { service: sid, playlist: pid, name, ai_check: $("#srtAi").checked };
    if (pid === "__file__") { if (!Sorter.file) return toast("Bitte die Datei erneut laden", "err"); Object.assign(body, { file_name: Sorter.file.name, file_data: Sorter.file.data }); }
    try { const r = await api("/api/sort/start", { method: "POST", body }); Object.assign(Sorter, { job: r.job, svc: sid, pl: pid, groups: null }); pollSort(main); }
    catch (e) { toast(e.message, "err"); }
  };
  if (same) pollSort(main);
};

async function sortAiWait() {
  const jid = Sorter.job;
  for (;;) {
    await new Promise(r => setTimeout(r, 1500));
    if (Sorter.job !== jid || !$(".sort-grid")) return;
    let j; try { j = await api(`/api/sort/${jid}`); } catch (e) { toast(e.message, "err"); return; }
    if (j.state !== "done") continue;
    const box = $("#srtJob"); if (box) box.innerHTML = "";
    if (j.ai_error) return toast(`KI-Prüfung fehlgeschlagen: ${j.ai_error}`, "err");
    (j.ai_new || []).forEach(n => { Sorter.items[n] = j.items[n]; sortPlace(n); });
    sortRedraw();
    return toast((j.ai_new || []).length ? `KI hat ${j.ai_new.length} Songs eingeordnet (mit „KI“ markiert)` : "Die KI kannte keinen der unsortierten Songs sicher genug");
  }
}

async function pollSort(main) {
  const jid = Sorter.job;
  while (Sorter.job === jid && document.body.contains($("#srtJob"))) {
    let j; try { j = await api(`/api/sort/${jid}`); } catch (e) { toast(e.message, "err"); return; }
    const box = $("#srtJob"); if (!box) return;
    if (j.state === "done") {
      box.innerHTML = ""; Sorter.items = j.items; Sorter.meta = j;
      if (j.scan) scanSummary(j.scan);
      return renderSort(main);
    }
    if (["error", "cancelled"].includes(j.state)) { box.innerHTML = `<div class="notice">${icon("info")}<div>${j.state === "error" ? esc(j.error) : "Abgebrochen."}</div></div>`; hydrateIcons(box); return; }
    const sc = j.scan, scanning = sc && j.state === "loading";
    const pct = scanning ? (sc.n ? Math.round(sc.i / sc.n * 100) : 0) : j.total ? Math.round(j.done / j.total * 100) : 0;
    const pause = (j.pausen || []).map(p => `${esc(p.label)} (noch ${p.s} s)`).join(", ");
    box.innerHTML = `<div class="card t-job"><div class="t-job-head"><b>${esc(scanning ? "Lese deine Dienste ein …" : SORT_STATE[j.state] || j.state)}</b><span class="cell-sub">${scanning ? `Liste ${sc.i}/${sc.n || "?"}` : `${j.done}/${j.total || "?"}`}</span>
      <button class="btn btn--xs btn--ghost" id="srtCancel">Abbrechen</button></div><div class="llm-bar"><div style="width:${pct}%"></div></div>
      ${pause ? `<div class="cell-sub" style="margin-top:6px">Kurze Pause, weil ${pause} um Geduld bittet – danach geht es automatisch weiter. So bekommt jeder Song sein Genre.</div>` : ""}
      ${scanning ? `<div class="cell-sub" style="margin-top:6px">${esc(sc.dienst || "")} › ${esc(sc.playlist || "")} · ${sc.songs} verschiedene Songs bisher${sc.doppelt ? `, ${sc.doppelt} doppelte zusammengeführt` : ""}</div>` : ""}
      ${sc && !scanning ? `<div class="cell-sub" style="margin-top:6px">Eingelesen: ${sc.lists} Listen, ${sc.songs} verschiedene Songs${sc.doppelt ? ` (${sc.doppelt} doppelte zusammengeführt)` : ""}${sc.fehler.length ? ` · ${sc.fehler.length} Liste(n) übersprungen` : ""}.</div>` : ""}
      ${j.cut ? `<div class="cell-sub" style="margin-top:6px">Sehr große Liste: analysiert werden die ersten ${j.total} Songs, ${j.cut} bleiben außen vor.</div>` : ""}</div>`;
    $("#srtCancel").onclick = () => api(`/api/sort/${jid}/cancel`, { method: "POST" });
    await new Promise(r => setTimeout(r, 1200));
  }
}

function scanSummary(sc) {
  const box = $("#srtJob"); if (!box) return;
  const skipped = sc.fehler || [];
  box.innerHTML = `<div class="notice">${icon("info")}<div>Eingelesen: <b>${sc.lists}</b> Listen, <b>${sc.songs}</b> verschiedene Songs${sc.doppelt ? ` (${sc.doppelt} doppelte zusammengeführt)` : ""}${sc.gekappt ? " – Obergrenze erreicht, nicht alles wurde eingelesen" : ""}.
    ${skipped.length ? `<details style="margin-top:6px"><summary>${skipped.length} Liste(n) übersprungen</summary><ul class="cell-sub">${skipped.slice(0, 50).map(f => `<li>${esc(f.dienst)} › ${esc(f.playlist || "–")}: ${esc(f.grund)}</li>`).join("")}</ul></details>` : ""}</div></div>`;
  hydrateIcons(box);
}

async function renderSort(main) {
  const out = $("#srtOut"); if (!out) return;
  const it = Sorter.items, meta = Sorter.meta;
  const groups = await api(`/api/sort/${Sorter.job}/groups`, { method: "POST", body: { level: Sorter.level, min_size: Sorter.min } });
  Sorter.groups = groups.map(g => ({ ...g, keep: !g.nomusic }));     // Videos ohne Musik: nicht mit übernehmen
  const svcs = await api("/api/services").catch(() => []);
  const targets = [["local", "SH-Tunebridge (lokal)"], ...svcs.filter(s => s.writable && s.ready).map(s => [s.id, s.name])];
  const lv = SORT_LEVELS.find(l => l[0] === Sorter.level);
  const known = it.filter(x => x.bpm).length, sub = it.filter(x => x.subgenre).length;
  out.innerHTML = `<div class="card sort-ctl">
      <div class="sort-levels" id="srtLv">${SORT_LEVELS.map(([n, t]) => `<button data-lv="${n}" class="${n === Sorter.level ? "on" : ""}"><b>${n}</b><span>${t}</span></button>`).join("")}</div>
      <div class="sort-desc">${esc(lv[2])}</div>
      <div class="form-row" style="margin-top:10px">
        <div class="field"><label>Mindestgröße pro Gruppe</label><input class="input" type="number" id="srtMin" min="1" max="50" value="${Sorter.min}" style="width:90px"></div>
        <div class="field grow"><label>Analyse</label><div class="cell-sub" style="padding-top:8px">${it.length} Songs · ${sub} mit Mikro-Genre · ${known} mit Tempo/Tonart${meta.ai_fixes != null ? ` · KI hat ${meta.ai_fixes} korrigiert` : ""}${meta.ai_error ? ` · KI-Prüfung fehlgeschlagen: ${esc(meta.ai_error)}` : ""}</div></div>
      </div>
    </div>
    ${meta.nomusic ? `<div class="notice">${icon("info")}<div>${meta.nomusic} Einträge sind laut YouTube keine Musik (gelikte Shorts, Gaming, Dokus …). Sie stehen ganz unten unter „Keine Musik“ und werden nicht mit übernommen – Häkchen setzen, falls doch.</div></div>` : ""}
    ${meta.cut ? `<div class="notice">${icon("info")}<div>Nur die ersten ${it.length} Songs wurden sortiert – ${meta.cut} weitere passen nicht in einen Durchgang.</div></div>` : ""}
    <div class="section-title">Vorschau · ${groups.length} Playlists <span class="cell-sub" style="font-weight:400">· Mit ▶ reinhören, Song anklicken zum Verschieben</span></div>
    <div class="split-grid sort-grid">${Sorter.groups.map((g, gi) => sortCard(g, gi)).join("")}</div>
    <div class="card sort-apply">
      <div class="field"><label>Anlegen in</label><select class="select" id="srtTarget">${targets.map(([v, n]) => `<option value="${v}">${esc(n)}</option>`).join("")}</select></div>
      <div class="field grow"><label>Präfix (optional)</label><input class="input" id="srtPre" placeholder="z. B. „${esc(meta.name || "Playlist")} · “"></div>
      <div class="field"><label>&nbsp;</label><button class="btn btn--primary" id="srtApply">${icon("check")}Alle ausgewählten übernehmen</button></div>
    </div>
    <div class="cell-sub" style="margin-top:6px">Einzeln geht auch: „Übernehmen“ oben auf jeder Playlist. Bereits angelegte Playlists sind markiert und werden nicht doppelt angelegt.</div>`;
  hydrateIcons(out);
  $$("#srtLv button").forEach(b => b.onclick = () => { Sorter.level = +b.dataset.lv; store.set("sortLevel", Sorter.level); renderSort(main); });
  let tmo; $("#srtMin").oninput = e => { clearTimeout(tmo); tmo = setTimeout(() => { Sorter.min = Math.max(1, Math.min(50, +e.target.value || 1)); store.set("sortMin", Sorter.min); renderSort(main); }, 400); };
  bindSortCards(out);
  $("#srtApply").onclick = () => sortApply(Sorter.groups.filter(g => g.keep && !g.done && g.items.length), targets);
  Sorter.applyOne = gi => sortApply([Sorter.groups[gi]], targets, true);
}

/* Übernehmen: alle ausgewählten Playlists auf einmal oder eine einzelne (Knopf auf der Karte) */
function sortApply(groups, targets, single = false) {
  groups = groups.filter(g => g && g.items.length);
  if (!groups.length) return toast(Sorter.groups.some(g => g.done) ? "Alles Ausgewählte ist schon angelegt" : "Keine Playlist ausgewählt", "err");
  const plan = groups.map(g => ({ name: g.name, items: g.items }));
  const target = $("#srtTarget").value, tname = targets.find(t => t[0] === target)[1];
  const again = single && groups[0].done ? ` Achtung: „${groups[0].name}“ wurde schon angelegt – die Songs kommen noch einmal dazu.` : "";
  modal({ title: single ? `„${groups[0].name}“ in ${tname} anlegen?` : `${plan.length} Playlists in ${tname} anlegen?`,
    text: `${plan.reduce((a, g) => a + g.items.length, 0)} Songs. Die Original-Playlist bleibt unverändert.${target !== "local" ? " Songs, die es dort nicht gibt, werden übersprungen." : ""}${again}`,
    confirm: "Anlegen", onConfirm: async () => {
      try {
        const r = await api(`/api/sort/${Sorter.job}/apply`, { method: "POST", body: { plan, target, prefix: $("#srtPre").value } });
        groups.forEach(g => { g.done = target; g.keep = false; });
        refreshMeta(); sortRedraw();
        if (single) return toast(`„${r.playlists[0]?.name || groups[0].name}“ angelegt · ${r.playlists[0]?.count ?? 0} Songs${r.missing ? `, ${r.missing} nicht gefunden` : ""}`);
        setTimeout(() => modal({ title: "Fertig", text: `${r.playlists.length} Playlists angelegt${r.missing ? `, ${r.missing} Songs nicht gefunden` : ""}.`, cancel: null, confirm: "OK",
          body: `<ul class="sort-done">${r.playlists.map(p => `<li>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>` : esc(p.name)} · ${p.count}</li>`).join("")}</ul>` }), 200);
      } catch (e) { toast(e.message, "err"); }
    } });
}

// Hörprobe für einen Song der Sortier-Vorschau (offizielle 30-s-Hörprobe; fehlt sie, sucht der Server bei Deezer)
const sortPrev = t => ({ title: t.title, artists: t.artists?.length ? t.artists : [t.artist || ""], cover: t.cover, isrc: t.isrc || null,
  ids: t.ids || {}, preview_url: t.preview_url || `deezer:${(t.artists || [])[0] || t.artist || ""}|${t.title}` });

function sortCard(g, gi) {
  const it = Sorter.items, i = g.info || {};
  const meta = [`${g.items.length} ${g.items.length === 1 ? "Song" : "Songs"}`, i.bpm ? `${i.bpm[0]}–${i.bpm[1]} BPM` : "", i.minuten ? `~${i.minuten} Min.` : "",
    i.energie != null ? `Energie ${Math.round(i.energie * 100)} %` : ""].filter(Boolean).join(" · ");
  const first = it[g.items[0]] || {};
  return `<div class="card split-card sort-card ${g.keep || g.done ? "" : "off"} ${g.done ? "done" : ""}" data-g="${gi}">
    <div class="sort-card-head"><label class="check"><input type="checkbox" data-keep="${gi}" ${g.keep ? "checked" : ""}></label>
      <span class="dot" style="background:${genreColor(first.genre, first.subgenre)}"></span>
      <input class="sort-name" data-rename="${gi}" value="${esc(g.name)}" spellcheck="false">
      ${!g.nomusic && g.items.length && g.items.every(n => !it[n].genre) ? `<button class="btn btn--xs btn--ghost" data-aiuns title="Die eingestellte KI ordnet nur Songs ein, die sie wirklich kennt">${icon("sparkle")}Mit KI prüfen</button>` : ""}
      <button class="btn btn--xs btn--ghost" data-listen="${gi}" title="Alle Songs dieser Playlist nacheinander anhören (je 30 s Hörprobe)">${icon("play")}Anhören</button></div>
    ${!g.nomusic && g.items.length && g.items.every(n => !it[n].genre) ? `<div class="cell-sub sort-hint">Song anklicken → „Genre selbst festlegen“. Was du festlegst, merkt sich die App für die Zukunft.</div>` : ""}
    <div class="sort-card-act"><span class="cnt">${esc(meta)}</span>
      ${g.done ? `<span class="chip chip--ok" title="Schon angelegt">${icon("check")}angelegt</span>` : ""}
      <button class="btn btn--xs ${g.done ? "btn--ghost" : ""}" data-one="${gi}" title="Nur diese Playlist jetzt anlegen">${icon("check")}${g.done ? "Nochmal anlegen" : "Diese übernehmen"}</button></div>
    <ul>${g.items.slice(0, g.shown || SORT_STEP).map(n => { const t = it[n];
      const sub = [t.ki ? "KI" : "", t.own ? "von dir" : "", Sorter.level <= 4 ? (t.subgenre || t.genre || "") : "", !t.genre && !t.nomusic && t.why ? t.why : "",
        t.bpm ? `${Math.round(t.bpm)} BPM` : "", t.camelot || ""].filter(Boolean);
      const pv = sortPrev(t);
      return `<li data-i="${n}" title="Klicken zum Verschieben${t.ki ? ` · KI: vorher ${esc(t.ki.vorher.filter(Boolean).join(" / ") || "?")} – ${esc(t.ki.grund || "")}` : ""}">
      <button class="icon-btn sort-play" ${playAttr(pv)} title="Reinhören">${icon(Player.isPlaying(pv.preview_url) ? "pause" : "play")}</button>
      ${t.cover ? `<img src="${esc(t.cover)}" alt="" loading="lazy">` : `<span class="ph"></span>`}
      <div class="sl"><span>${esc(t.artist)} – ${esc(t.title)}</span><em title="${esc(sub.join(" · "))}">${sub.map(x => x === "KI" ? `<b class="chip chip--ai">KI</b>` : x === "von dir" ? `<b class="chip">von dir</b>` : esc(x)).join(" · ")}</em></div></li>`; }).join("")}</ul>
    ${g.items.length > (g.shown || SORT_STEP) ? `<button class="btn btn--xs btn--ghost dp-more" data-more="${gi}">Weitere anzeigen (${g.items.length - (g.shown || SORT_STEP)} übrig)</button>` : ""}</div>`;
}
// Große Gruppen (Alles einlesen: bis 80.000 Songs) nur portionsweise zeichnen – sonst friert die Seite ein
const SORT_STEP = 100;

// Häufigstes Genre einer Gruppe (ohne Song „skip“) – nur wenn eindeutig (≥ 60 %)
function sortDominant(g, skip = -1) {
  const c = {}; let n = 0;
  g.items.forEach(i => { if (i === skip) return; const t = Sorter.items[i]; if (!t.genre) return; n++; const k = `${t.genre}|${t.subgenre || ""}`; c[k] = (c[k] || 0) + 1; });
  const best = Object.entries(c).sort((a, b) => b[1] - a[1])[0];
  if (best && best[1] / n >= .6) { const [genre, sub] = best[0].split("|"); return { genre, subgenre: sub || null }; }
  const gc = {}; g.items.forEach(i => { const t = Sorter.items[i]; if (i !== skip && t.genre) gc[t.genre] = (gc[t.genre] || 0) + 1; });
  const bg = Object.entries(gc).sort((a, b) => b[1] - a[1])[0];
  return bg && bg[1] / n >= .6 ? { genre: bg[0], subgenre: null } : null;
}
const sortRedraw = () => { Sorter.groups = Sorter.groups.filter(g => g.items.length); const grid = $(".sort-grid"); grid.innerHTML = Sorter.groups.map((g, gi) => sortCard(g, gi)).join(""); hydrateIcons(grid); bindSortCards(grid); };
// Song mit (neuem) Genre in die passende Gruppe legen – sonst neue Gruppe mit dem Genre-Namen
function sortPlace(n) {
  const t = Sorter.items[n], from = Sorter.groups.findIndex(g => g.items.includes(n));
  let to = Sorter.groups.findIndex((g, gi) => gi !== from && !g.nomusic && (d => d && d.genre === t.genre && (!t.subgenre || !d.subgenre || d.subgenre === t.subgenre))(sortDominant(g)));
  if (to < 0) { Sorter.groups.push({ name: t.subgenre || t.genre, items: [], info: {}, keep: true }); to = Sorter.groups.length - 1; }
  if (from >= 0) Sorter.groups[from].items = Sorter.groups[from].items.filter(x => x !== n);
  Sorter.groups[to].items.push(n);
  return Sorter.groups[to].name;
}
async function sortSetGenre(n) {
  const t = Sorter.items[n];
  await GenreDB.pick(t.genre, t.subgenre, `${esc(t.artist)} – ${esc(t.title)}`, async (g, sg) => {
    Sorter.items[n] = await api(`/api/sort/${Sorter.job}/genre`, { method: "POST", body: { i: n, genre: g, subgenre: sg, learn: true } });
    const name = sortPlace(n); sortRedraw(); toast(`Gemerkt: ${sg || g} – liegt jetzt in „${name}“`);
  });
}

function bindSortCards(root) {
  $$("[data-more]", root).forEach(b => b.onclick = () => {
    const gi = +b.dataset.more, g = Sorter.groups[gi];
    g.shown = (g.shown || SORT_STEP) + 4 * SORT_STEP;
    const tmp = document.createElement("div"); tmp.innerHTML = sortCard(g, gi);
    const card = tmp.firstElementChild; b.closest(".sort-card").replaceWith(card); hydrateIcons(card); bindSortCards(card);
  });
  $$("[data-one]", root).forEach(b => b.onclick = e => { e.stopPropagation(); Sorter.applyOne?.(+b.dataset.one); });
  $$("[data-aiuns]", root).forEach(b => b.onclick = async () => {
    try {
      const r = await api(`/api/sort/${Sorter.job}/ai-unsorted`, { method: "POST" });
      Sorter.aiUnsorted = true; toast(`KI prüft ${r.songs} unsortierte Songs …`);
      const box = $("#srtJob"); box.innerHTML = `<div class="card t-job"><b>KI prüft die unsortierten Songs …</b><div class="cell-sub">Nur Songs, die die KI wirklich kennt, werden eingeordnet. Deine Verschiebungen bleiben.</div></div>`;
      sortAiWait();
    } catch (e) { toast(e.message, "err"); }
  });
  $$("[data-keep]", root).forEach(c => c.onchange = () => { const g = Sorter.groups[+c.dataset.keep]; g.keep = c.checked; c.closest(".sort-card").classList.toggle("off", !c.checked); });
  $$("[data-rename]", root).forEach(inp => inp.onchange = () => { Sorter.groups[+inp.dataset.rename].name = inp.value.trim() || Sorter.groups[+inp.dataset.rename].name; });
  $$("[data-listen]", root).forEach(b => b.onclick = () => {
    const g = Sorter.groups[+b.dataset.listen];
    Player.playList(g.items.map(n => sortPrev(Sorter.items[n])));
    toast(`„${g.name}“: ${g.items.length} Hörproben nacheinander – unten im Player weiter/stoppen`);
  });
  $$(".sort-card li[data-i]", root).forEach(li => li.onclick = e => {
    if (e.target.closest("[data-play]")) return;          // Play-Knopf: nur reinhören, nicht verschieben
    const n = +li.dataset.i, t = Sorter.items[n], from = +li.closest(".sort-card").dataset.g;
    modal({ title: "Verschieben nach …", text: esc(`${t.artist} – ${t.title}${t.genre ? ` · ${t.genre}${t.subgenre ? " / " + t.subgenre : ""}` : ""}`),
      body: `<select class="select" id="mvTo" style="width:100%">${Sorter.groups.map((g, gi) => `<option value="${gi}" ${gi === from ? "selected" : ""}>${esc(g.name)}</option>`).join("")}<option value="new">+ Neue Playlist …</option></select>
        <input class="input hidden" id="mvNew" placeholder="Name der neuen Playlist" style="width:100%;margin-top:8px">
        <label class="check hidden" id="mvLearnRow" style="margin-top:12px;display:flex;gap:8px;align-items:flex-start"><input type="checkbox" id="mvLearn" checked><span id="mvLearnTxt"></span></label>
        <button class="link-btn" id="mvGenre" style="margin-top:12px">${icon("pencil")}Genre selbst festlegen …</button>`,
      confirm: "Verschieben", onConfirm: async box => {
        let to = $("#mvTo", box).value;
        if (to === "new") { const nm = $("#mvNew", box).value.trim(); if (!nm) { toast("Bitte einen Namen eingeben", "err"); throw { silent: true }; }
          Sorter.groups.push({ name: nm, items: [], info: {}, keep: true }); to = Sorter.groups.length - 1; }
        to = +to; if (to === from) return;
        const d = sortDominant(Sorter.groups[to], n);
        if (d && $("#mvLearn", box).checked && !$("#mvLearnRow", box).classList.contains("hidden")) {
          Sorter.items[n] = await api(`/api/sort/${Sorter.job}/genre`, { method: "POST", body: { i: n, genre: d.genre, subgenre: d.subgenre, learn: true } });
          toast(`Gemerkt: ${d.subgenre || d.genre}`);
        }
        Sorter.groups[from].items = Sorter.groups[from].items.filter(x => x !== n);
        Sorter.groups[to].items.push(n);
        sortRedraw();
      } });
    const sel = $("#mvTo");
    const learnInfo = () => {    // Ziel hat ein eindeutiges Genre, das vom Song abweicht -> „merken“ anbieten
      const d = sel.value === "new" ? null : sortDominant(Sorter.groups[+sel.value], n);
      const show = d && +sel.value !== from && (d.genre !== t.genre || (d.subgenre || null) !== (t.subgenre || null));
      $("#mvLearnRow").classList.toggle("hidden", !show);
      if (show) $("#mvLearnTxt").innerHTML = `Als <b>${esc(d.subgenre ? `${d.genre} / ${d.subgenre}` : d.genre)}</b> merken – gilt künftig beim Erkennen und Sortieren`;
    };
    sel.onchange = () => { $("#mvNew").classList.toggle("hidden", sel.value !== "new"); learnInfo(); };
    learnInfo(); hydrateIcons($("#modalBox"));
    $("#mvGenre").onclick = () => sortSetGenre(n);
  });
}

/* ================================================================= Router */
async function route() {
  const main = $("#main");
  const [path, qs] = (location.hash.slice(1) || "/listen").split("?");
  const params = new URLSearchParams(qs || "");
  const parts = path.split("/").filter(Boolean);
  closeDrawer();
  GSearch.close();
  markNav();
  if (parts[0] && parts[0] !== "listen") Meter.stop();
  DiscordUI.view(params.get("pl") ? "sort" : parts[0] || "listen");
  try {
    if (parts[0] === "playlists" && parts[1]) await Views.playlist(main, decodeURIComponent(parts.slice(1).join("/")));
    else await (Views[parts[0]] || Views.listen)(main, null, params);
  } catch (e) {
    main.innerHTML = `<div class="page"><div class="empty">${icon("info")}<h3>Da ist etwas schiefgelaufen</h3><p>${esc(e.message)}</p></div></div>`;
  }
  main.scrollTop = 0;
  Player.sync();
}

/* ================================================================= Globale Suche (Seitenleiste, Strg+K) */
const SEARCH_PAGES = [
  ["#/listen", "Erkennen", "wave", "song erkennen shazam mikrofon aufnehmen hören dauer-modus"],
  ["#/history", "Verlauf", "clock", "erkennungsverlauf erkannte songs"],
  ["#/stats", "Statistik", "chart", "auswertung jahr top künstler genres"],
  ["#/playlists", "Playlists", "stack", "bibliothek sammlungen"],
  ["#/services", "Dienste", "grid", "spotify tidal youtube soundcloud deezer verbinden alles einlesen sortieren"],
  ["#/inbox", "Neu für dich", "inbox", "automatischer abgleich neue songs likes einsortieren filter"],
  ["#/links", "Link einfügen", "external", "url link öffnen playlist link"],
  ["#/discover", "Entdecken", "compass", "stöbern browsen suchen katalog künstler album charts genre ähnliche songs neue musik finden bpm tonart"],
  ["#/mix", "Mix erstellen", "shuffle", "neue playlist künstler genre subgenre ähnliche künstler mix generieren tempo bpm tonart camelot energie passend"],
  ["#/share", "Teilen", "share", "playlists teilen freunde schlüssel verschlüsselt"],
  ["#/directory", "Verzeichnis", "globe", "öffentliche playlists veröffentlichen melden stöbern"],
  ["#/genredb", "Genre-Datenbank", "tag", "genre festlegen einordnungen gemeinschaft"],
  ["#/setplan", "Set-Planer", "disc", "dj set reihenfolge mix energie"],
  ["#/dupes", "Doppelte Songs", "dupe", "duplikate doppelt aufräumen"],
  ["#/split", "Aufteilen", "split", "playlist aufteilen nach genre"],
  ["#/transfer", "Übertragen", "transfer", "playlist übertragen kopieren zwischen diensten"],
  ["#/settings", "Einstellungen", "sliders", "optionen konfiguration"],
];
// [Reiter, Bezeichnung, Suchwörter] – Treffer öffnen den Reiter und heben die Stelle hervor
const SETTINGS_INDEX = [
  ["allgemein", "Version & Updates", "update aktualisieren version neu changelog jetzt prüfen"],
  ["allgemein", "Dieser Rechner", "rechner pfad daten konfiguration lizenz"],
  ["darstellung", "Darstellung", "aussehen theme hell dunkel modus farbe"],
  ["darstellung", "Akzentfarbe", "farbe akzent"],
  ["darstellung", "Hintergrund", "hintergrundbild bild wallpaper"],
  ["darstellung", "Größe", "schrift zoom skalierung größe"],
  ["darstellung", "Ecken", "rundung radius"],
  ["darstellung", "Abstände", "kompakt dichte"],
  ["darstellung", "Animationen", "bewegung animation reduziert"],
  ["darstellung", "Seitenleiste", "sidebar leiste einklappen"],
  ["darstellung", "Schwebe-Icon", "bubble overlay schwebe icon vordergrund"],
  ["darstellung", "Symbol in der Statusleiste", "tray statusleiste symbol uhr"],
  ["dienste", "Konten verbinden", "login konto last.fm anmelden"],
  ["dienste", "Musikdienste", "spotify client id youtube api key schlüssel"],
  ["dienste", "YouTube-Login", "youtube oauth client"],
  ["dienste", "SoundCloud-Login", "soundcloud client"],
  ["discord", "Discord-Status", "discord rich presence status freunde"],
  ["handy", "Handy koppeln", "handy android smartphone app koppeln qr abgleich wlan"],
  ["discord", "Application ID", "discord application id"],
  ["ki", "KI-Anbieter", "ki claude openai gemini codex ollama lm studio llama"],
  ["ki", "Lokales LLM", "llm llama.cpp modell lokal server"],
  ["ki", "Beim Sortieren mitprüfen", "ki sortieren prüfen"],
  ["genres", "Quellen", "genre quellen last.fm musicbrainz deezer apple"],
  ["genres", "Gelernte Genres", "genres lernen tags"],
  ["erkennung", "Anzeige im Kreis", "visualisierung spektrum pegel kreis"],
  ["erkennung", "Shazam", "shazam erkennung"],
  ["erkennung", "Weitere Erkennungsdienste", "audd acrcloud erkennung schlüssel"],
  ["sicherung", "Sicherung", "backup sichern wiederherstellen export import datenbank"],
  ["gemeinschaft", "Gemeinschafts-Genre-Datenbank", "gemeinschaft community genres beitragen"],
  ["gemeinschaft", "Genres meiner Bibliothek beitragen", "bibliothek beitragen genres"],
  ["gemeinschaft", "Abgleich", "manuell automatisch abgleichen sync"],
  ["datenschutz", "Einwilligungen", "datenschutz einwilligung senden server dsgvo privatsphäre"],
  ["datenschutz", "Offizielle Player (eingebettet)", "player eingebettet youtube spotify laden"],
  ["datenschutz", "Öffentliches Playlist-Verzeichnis nutzen", "verzeichnis öffentlich einwilligung"],
  ["datenschutz", "Playlists teilen", "teilen einwilligung verschlüsselt"],
  ["datenschutz", "Handy-Abgleich übers Internet", "unterwegs handy internet abgleich relais einwilligung"],
  ["traffic", "Datenverbrauch", "traffic daten mb internet verbrauch"],
  ["speicher", "Zwischenspeicher", "cache speicher leeren song-speicher fingerabdrücke"],
  ["nichterkannt", "Nicht erkannt", "unerkannt fehlende songs senden"],
  ["debug", "Debug-Protokoll", "debug log fehler protokoll"],
  ["debug", "Bericht für den Entwickler", "fehlerbericht bericht senden"],
];
const _norm = s => String(s || "").toLocaleLowerCase("de").normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/ß/g, "ss");
function _match(words, label, extra = "") {
  const l = _norm(label), all = l + " " + _norm(extra);
  if (!words.every(w => all.includes(w))) return 0;
  return (l.startsWith(words[0]) ? 3 : 0) + words.filter(w => l.includes(w)).length + 1;
}
const GSearch = {
  sel: 0, items: [], timer: null, seq: 0, scope: "",
  open(q = "", scope = "") {
    this.scope = scope;
    let el = $("#gs");
    if (!el) {
      document.body.insertAdjacentHTML("beforeend", `<div class="gs" id="gs" role="dialog" aria-label="Suche"><div class="gs-box">
        <div class="gs-in">${icon("search")}<input id="gsQ" autocomplete="off" spellcheck="false"><kbd>Esc</kbd></div>
        <div class="gs-res" id="gsRes"></div></div></div>`);
      el = $("#gs"); hydrateIcons(el);
      el.onclick = e => { if (e.target === el) this.close(); };
      $("#gsQ").oninput = () => { clearTimeout(this.timer); this.timer = setTimeout(() => this.run(), 160); };
      $("#gsQ").onkeydown = e => {
        if (e.key === "Escape") { e.preventDefault(); this.close(); }
        else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); this.move(e.key === "ArrowDown" ? 1 : -1); }
        else if (e.key === "Enter") { e.preventDefault(); this.go(this.sel); }
      };
    }
    $("#gsQ").placeholder = scope === "settings" ? "In den Einstellungen suchen …" : "Suchen: Seiten, Einstellungen, Playlists, Songs, Verlauf …";
    $("#gsQ").value = q; el.classList.add("open"); $("#gsQ").focus(); this.run();
  },
  close() { $("#gs")?.classList.remove("open"); },
  local(q) {
    const words = _norm(q).split(/\s+/).filter(Boolean), out = [];
    const add = (group, list, max = 8) => { const l = list.filter(x => x.s).sort((a, b) => b.s - a.s).slice(0, max); if (l.length) out.push([group, l]); };
    if (this.scope !== "settings") add("Seiten & Funktionen", SEARCH_PAGES.map(([h, l, ic, kw]) => ({ s: words.length ? _match(words, l, kw) : 1, ic, title: l, sub: "", href: h })));
    add("Einstellungen", [...SETTING_TABS.map(([id, l, ic]) => ({ s: !words.length ? (this.scope === "settings" ? 1 : 0) : _match(words, l) ? _match(words, l) + 1 : 0, ic, title: l, sub: "Einstellungen", href: `#/settings?tab=${id}` })),
      ...SETTINGS_INDEX.map(([tab, l, kw]) => ({ s: words.length ? _match(words, l, kw) : 0, ic: "sliders", title: l,
        sub: `Einstellungen › ${(SETTING_TABS.find(t => t[0] === tab) || [])[1] || ""}`, href: `#/settings?tab=${tab}&find=${enc(l)}` }))]
      .filter((x, i, a) => a.findIndex(y => y.href === x.href) === i), this.scope === "settings" ? 30 : 8);
    if (this.scope !== "settings" && words.length) {
      add("Deine Playlists", (S.playlists || []).filter(p => p.origin === "lokal").map(p => ({ s: _match(words, p.name), ic: "stack", title: p.name, sub: `${p.count} Songs`, href: `#/playlists/${enc(p.name)}` })));
      const svc = [];
      for (const s of SideSvc.list) for (const p of (Array.isArray(SideSvc.pls[s.id]) ? SideSvc.pls[s.id] : []))
        svc.push({ s: _match(words, p.name), ic: "grid", title: p.name, sub: `${s.name}${p.count != null ? ` · ${p.count} Songs` : ""}`, href: svcPlHref(s.id, p) });
      add("Playlists deiner Dienste", svc);
    }
    return out;
  },
  async run() {
    const q = $("#gsQ").value.trim(), my = ++this.seq;
    let groups = this.local(q);
    this.render(groups, q.length >= 2 && this.scope !== "settings");
    if (q.length < 2 || this.scope === "settings") return;
    let r; try { r = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch { r = { songs: [], history: [] }; }
    if (my !== this.seq) return;
    const fmt = t => (t.artists || []).join(", ");
    if (r.songs.length) groups.push(["Songs in deinen Playlists", r.songs.map(t => ({ ic: "disc", title: t.title, sub: `${fmt(t)} · in ${t.playlists.slice(0, 3).join(", ")}${t.playlists.length > 3 ? " …" : ""}`,
      cover: t.cover, play: t.preview_url ? t : null, act: () => openDrawer(() => api("/api/track", { method: "POST", body: { key: t.key } })) }))]);
    if (r.history.length) groups.push(["Erkennungsverlauf", r.history.map(h => ({ ic: "clock", title: h.title, sub: `${fmt(h)} · ${new Date(h.ts * 1000).toLocaleDateString("de-DE")}`,
      cover: h.cover, act: () => openDrawer(() => api(`/api/recognition/${h.id}`)) }))]);
    this.render(groups, false);
  },
  render(groups, loading) {
    this.items = groups.flatMap(g => g[1]); this.sel = 0;
    let n = 0;
    $("#gsRes").innerHTML = groups.length ? groups.map(([g, l]) => `<div class="gs-group">${esc(g)}</div>${l.map(x => { const i = n++;
      return `<div class="gs-item" data-i="${i}" role="option">${x.cover ? `<img src="${esc(x.cover)}" alt="" loading="lazy">` : `<span class="gs-ic">${icon(x.ic)}</span>`}
        <div class="gs-txt"><b>${esc(x.title)}</b>${x.sub ? `<span>${esc(x.sub)}</span>` : ""}</div>
        ${x.play ? `<button class="icon-btn" ${playAttr(x.play)} title="Reinhören">${icon("play")}</button>` : ""}</div>`; }).join("")}`).join("")
      + (loading ? `<div class="gs-more">Suche Songs …</div>` : "")
      : `<div class="gs-empty">${loading ? "Suche …" : "Nichts gefunden."}</div>`;
    hydrateIcons($("#gsRes")); this.move(0);
    $$(".gs-item", $("#gsRes")).forEach(el => {
      el.onclick = e => { if (!e.target.closest("[data-play]")) this.go(+el.dataset.i); };
      el.onmousemove = () => { if (this.sel !== +el.dataset.i) { this.sel = +el.dataset.i; this.move(0); } };
    });
  },
  move(d) {
    if (!this.items.length) return;
    this.sel = (this.sel + d + this.items.length) % this.items.length;
    $$(".gs-item", $("#gsRes")).forEach(el => el.classList.toggle("on", +el.dataset.i === this.sel));
    $(`.gs-item[data-i="${this.sel}"]`, $("#gsRes"))?.scrollIntoView({ block: "nearest" });
  },
  go(i) {
    const x = this.items[i]; if (!x) return;
    this.close();
    if (x.act) return x.act();
    if (location.hash === x.href) route(); else location.hash = x.href;
  },
};
$("#gsOpen")?.addEventListener("click", () => GSearch.open());
document.addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); GSearch.open(); }
});
/* Einstellungen: Stelle aus der Suche hervorheben (?find=…) – wartet, bis nachgeladene Bereiche da sind */
function settingsFind(label) {
  const want = _norm(label);
  let tries = 0;
  const look = () => {
    const root = $("#setMain"); if (!root) return;
    const els = $$(".section-title, .lbl, h3, h4, label, dt, .cons-row b, .set-row div", root);
    const hit = els.find(el => _norm(el.firstChild?.textContent || el.textContent).trim().startsWith(want))
      || els.find(el => _norm(el.textContent).includes(want));
    if (!hit) { if (++tries < 12) setTimeout(look, 250); return; }
    const box = hit.closest(".set-row, .cons-row, .card") || hit;
    box.scrollIntoView({ block: "center", behavior: "smooth" });
    box.classList.remove("find-flash"); void box.offsetWidth; box.classList.add("find-flash");
  };
  setTimeout(look, 150);
}

/* ================================================================= Tastatur */
document.addEventListener("keydown", e => {
  if (e.target.closest("input, textarea, select, [contenteditable=true]")) return;
  if (e.key === "Escape") { if (!$("#modal").dataset.sticky) $("#modal").classList.remove("open"); return closeDrawer(); }
  if (e.code === "Space") {
    e.preventDefault();
    // Datenschutz: Leertaste startet KEINE Erkennung (nur der Klick auf den Kreis), sie steuert nur die Hörprobe
    if (!e.target.closest("button, a")) Player.toggle();
  }
  const nav = { "1": "listen", "2": "history", "3": "playlists", "4": "discover", "5": "split", "6": "transfer", "7": "settings?tab=sicherung", ",": "settings" };
  if ((e.ctrlKey || e.metaKey) && nav[e.key]) { e.preventDefault(); location.hash = "#/" + nav[e.key]; }
});

/* ================================================================= Start */
hydrateIcons();
api("/api/companion").then(c => { if (c?.viz && c.viz !== Meter.viz) { Meter.viz = c.viz; store.set("viz", c.viz); } }).catch(() => {});
/* Hauptleiste ein-/ausklappen (gemerkt pro Rechner); eingeklappt zeigen Tooltips die Namen */
const Side = {
  set(min) {
    $(".app").classList.toggle("side-min", min); store.set("sideMin", min);
    $("#sideToggle").setAttribute("aria-label", min ? "Leiste ausklappen" : "Leiste einklappen");
    $$(".nav a, .foot-link").forEach(a => { const t = $("span", a)?.textContent; if (t) a.title = min ? t : ""; });
  },
};
Side.set(!!store.get("sideMin", false));
/* Bereiche der Leiste (Bibliothek, Werkzeuge, Deine Dienste, Deine Playlists) einzeln einklappbar – gemerkt pro Rechner */
const Fold = {
  state: store.get("navFold", {}),
  apply() {
    $$("[data-fold]").forEach(b => {
      const shut = !!this.state[b.dataset.fold];
      b.classList.toggle("folded", shut); b.setAttribute("aria-expanded", String(!shut));
      $(`[data-fold-body="${b.dataset.fold}"]`)?.classList.toggle("folded", shut);
    });
  },
  init() {
    $$("[data-fold]").forEach(b => b.onclick = () => {
      this.state[b.dataset.fold] = !this.state[b.dataset.fold]; store.set("navFold", this.state); this.apply();
    });
    this.apply();
  },
};
Fold.init();
Look.load();   // Darstellung vom Server (falls auf einem anderen Weg geändert)
$("#sideToggle").onclick = () => Side.set(!$(".app").classList.contains("side-min"));
Player.init();
Traffic.initClient();
DiscordUI.init();
setInterval(() => Traffic.pill(), 2500); Traffic.pill();
/* Vor/Zurück wie im Browser: Pfeile oben links, Alt+←/→, Maus-Seitentasten.
   Jeder Eintrag im Fensterverlauf bekommt eine Nummer (history.state.tbIdx) – so wissen die Pfeile,
   ob es noch zurück bzw. vor geht. */
const Hist = {
  idx: 0, max: 0, replacing: false,
  init() {
    try { this.max = +sessionStorage.getItem("tb:histMax") || 0; } catch { /* ohne Speicher: nur diese Sitzung */ }
    const st = history.state;
    if (st && typeof st.tbIdx === "number") this.idx = st.tbIdx;
    else history.replaceState({ tbIdx: 0 }, "");
    this.max = Math.max(this.max, this.idx);
    $("#navBack").onclick = () => this.go(-1);
    $("#navFwd").onclick = () => this.go(1);
    document.addEventListener("keydown", e => {
      if (!e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
      if (e.target.closest("input, textarea, select, [contenteditable=true]")) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); this.go(-1); }
      if (e.key === "ArrowRight") { e.preventDefault(); this.go(1); }
    });
    // Maus-Seitentasten (3 = zurück, 4 = vor); preventDefault verhindert, dass das Fenster selbst noch einmal springt
    document.addEventListener("mousedown", e => { if (e.button === 3 || e.button === 4) e.preventDefault(); });
    document.addEventListener("mouseup", e => {
      if (e.button === 3 || e.button === 4) { e.preventDefault(); this.go(e.button === 3 ? -1 : 1); }
    });
    this.render();
  },
  go(d) {
    if (d < 0 && this.idx > 0) history.back();
    else if (d > 0 && this.idx < this.max) history.forward();
  },
  changed() {
    const st = history.state;
    if (st && typeof st.tbIdx === "number") this.idx = st.tbIdx;            // vor/zurück zu bekanntem Eintrag
    else {                                                                  // neue Ansicht (oder ersetzt)
      if (!this.replacing) this.idx += 1;
      this.max = this.idx;                                                  // „Vor“-Einträge sind jetzt weg
      history.replaceState({ tbIdx: this.idx }, "");
    }
    this.replacing = false;
    try { sessionStorage.setItem("tb:histMax", String(this.max)); } catch { /* egal */ }
    this.render();
  },
  render() {
    $("#navBack").disabled = this.idx <= 0;
    $("#navFwd").disabled = this.idx >= this.max;
  },
};
Hist.init();
window.addEventListener("hashchange", () => Hist.changed());
window.addEventListener("hashchange", route);
setTimeout(() => Update.check(), 4000);
Limits.refresh();   // Limit-Hinweis auf allen Seiten
$("#updatePill").addEventListener("click", e => { if (Update.info?.available && !Update.info.dev) { e.preventDefault(); Update.dialog(); } });
setInterval(() => Update.check(), 3600 * 1000);
Promise.all([refreshMeta(), loadPrefs()]).then(() => { SideSvc.load(); }).then(route).then(() => Consent.checkFirstStart()).catch(e => { $("#main").innerHTML = `<div class="page"><div class="empty"><h3>Backend nicht erreichbar</h3><p>${esc(e.message)}</p></div></div>`; });
