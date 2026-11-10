/* radio player — episodes/index + per-episode JSON + audio */
const $ = (id) => document.getElementById(id);
const audio = $("audio");
let ep = null;        // current episode JSON
let station = null;
let rafId = 0;

const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

async function j(path) {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function currentLine(t) {
  if (!ep?.lines_timed) return -1;
  let lo = 0, hi = ep.lines_timed.length - 1, ans = -1;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (ep.lines_timed[m].start <= t) { ans = m; lo = m + 1; } else hi = m - 1;
  }
  return ans;
}

function tick() {
  const t = audio.currentTime;
  $("t-cur").textContent = fmt(t);
  $("seek").value = audio.duration ? (t / audio.duration) * 1000 : 0;
  const i = currentLine(t);
  if (i >= 0) {
    const l = ep.lines_timed[i];
    if ($("now").dataset.i != i) {
      $("now").textContent = l.show;
      $("now").dataset.i = i;
      document.querySelectorAll(".line.on").forEach(e => e.classList.remove("on"));
      const el = document.querySelector(`.line[data-i="${i}"]`);
      if (el) { el.classList.add("on"); el.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      document.querySelectorAll("#chapters button").forEach(b =>
        b.classList.toggle("on", b.dataset.part === l.part));
    }
  }
  rafId = requestAnimationFrame(tick);
}

function renderEpisode() {
  $("ep-title").textContent = ep.title;
  $("ep-date").textContent = ep.date;
  document.title = `${ep.title} — ${station.name}`;

  // chapters: opening + each news + closing
  const ch = $("chapters");
  ch.innerHTML = "";
  const segBtn = (label, part, start) => {
    const b = document.createElement("button");
    b.textContent = label; b.dataset.part = part;
    b.onclick = () => { audio.currentTime = start + 0.01; audio.play(); };
    ch.appendChild(b);
  };
  for (const s of ep.segments || []) {
    const label = s.kind === "news" ? ep.news[s.index].label
      : s.kind === "opening" ? "オープニング" : "エンディング";
    segBtn(label, s.kind === "news" ? `news:${s.index}` : s.kind, s.start);
  }

  // body: transcript sections driven by lines_timed (exact timing index)
  const body = $("body");
  body.innerHTML = "";
  const sec = (h2) => {
    const s = document.createElement("section");
    s.className = "sec";
    if (h2) { const h = document.createElement("h2"); h.textContent = h2; s.appendChild(h); }
    body.appendChild(s);
    return s;
  };
  const sections = { opening: sec(null) };
  ep.news.forEach((n, i) => {
    const s = sec(n.label);
    const ul = document.createElement("ul");
    ul.className = "points";
    (n.points || []).forEach(p => { const li = document.createElement("li"); li.textContent = p; ul.appendChild(li); });
    s.appendChild(ul);
    sections[`news:${i}`] = s;
  });
  sections.closing = sec(null);

  const cardAfter = {};
  (ep.lines_timed || []).forEach((l, idx) => {
    const d = document.createElement("div");
    d.className = "line"; d.dataset.i = idx; d.textContent = l.show;
    d.onclick = () => { audio.currentTime = l.start + 0.01; audio.play(); };
    (sections[l.part] || body).appendChild(d);
    const m = l.part.match(/^news:(\d+)$/);
    if (m) cardAfter[m[1]] = d;
  });
  ep.news.forEach((n, i) => {
    const link = n.link || (n.url ? { url: n.url, title: n.url, site: "" } : null);
    if (link && cardAfter[i]) {
      const a = document.createElement("a");
      a.className = "card"; a.href = link.url; a.target = "_blank"; a.rel = "noopener";
      a.innerHTML = `<div>${link.title || link.url}</div>${link.site ? `<div class="site">${link.site}</div>` : ""}`;
      cardAfter[i].after(a);
    }
  });
}

async function loadEpisode(date) {
  ep = await j(`episodes/${date}.json`);
  audio.src = ep.audio || `audio/${date}.mp3`;
  renderEpisode();
  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: ep.title, artist: station.name, album: ep.date,
    });
    navigator.mediaSession.setActionHandler("seekbackward", () => audio.currentTime -= 15);
    navigator.mediaSession.setActionHandler("seekforward", () => audio.currentTime += 15);
  }
}

async function init() {
  station = await j("station.json");
  $("st-name").textContent = station.name;
  $("st-tag").textContent = station.tagline || "";
  $("credits").textContent = (station.credits || []).join(" / ");
  document.title = station.name;

  const index = await j(station.episodes || "episodes.json");
  const sel = $("ep-select");
  for (const e of index) {
    const o = document.createElement("option");
    o.value = e.date;
    o.textContent = `${e.date} ${e.title}`.slice(0, 42);
    sel.appendChild(o);
  }
  const want = new URLSearchParams(location.search).get("ep") || index[0]?.date;
  sel.value = want;
  sel.onchange = () => {
    history.replaceState(null, "", `?ep=${sel.value}`);
    loadEpisode(sel.value);
  };
  if (want) await loadEpisode(want);
}

$("btn-play").onclick = () => audio.paused ? audio.play() : audio.pause();
$("btn-back").onclick = () => audio.currentTime -= 15;
$("btn-fwd").onclick = () => audio.currentTime += 15;
$("speed").onchange = (e) => audio.playbackRate = parseFloat(e.target.value);
$("seek").oninput = (e) => { if (audio.duration) audio.currentTime = e.target.value / 1000 * audio.duration; };
audio.onplay = () => { $("btn-play").textContent = "⏸"; cancelAnimationFrame(rafId); tick(); };
audio.onpause = () => { $("btn-play").textContent = "▶"; cancelAnimationFrame(rafId); };
audio.onloadedmetadata = () => $("t-total").textContent = fmt(audio.duration);
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "SELECT" || e.target.tagName === "INPUT") return;
  if (e.key === " ") { e.preventDefault(); $("btn-play").click(); }
  if (e.key === "ArrowLeft") audio.currentTime -= 15;
  if (e.key === "ArrowRight") audio.currentTime += 15;
});

init().catch(e => { $("now").textContent = `読み込み失敗: ${e.message}`; });
