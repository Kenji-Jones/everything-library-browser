/* Everything Library browser: search, filter, sort and a three.js viewer for the exported models. */
(function () {
  "use strict";

  const CAT = window.CATALOG;
  const $ = (id) => document.getElementById(id);
  const TINTS = Object.fromEntries(CAT.categories.map((c) => [c.id, "--t-" + c.id.toLowerCase()]));
  const CANVAS_URL = "https://everythingcanvas.vercel.app/";
  const SIZES = [
    { id: "Tiny", hint: "< 10 cm" },
    { id: "Small", hint: "< 1 m" },
    { id: "Medium", hint: "< 4 m" },
    { id: "Large", hint: "< 20 m" },
    { id: "Huge", hint: "20 m +" },
  ];

  const state = { q: "", cat: "", sub: "", size: "", sort: "category", variants: false, item: "", v: 1 };
  let results = []; // [{item, vi}] currently shown, in display order
  let shuffleKey = new Map();

  // ---------------------------------------------------------------- helpers
  const fmtLen = (m) => {
    if (m < 1e-6) return `${+(m * 1e9).toPrecision(2)} nm`;
    if (m < 1e-3) return `${+(m * 1e6).toPrecision(2)} µm`;
    if (m < 0.01) return `${(m * 1000).toFixed(1)} mm`;
    if (m < 1) return `${(m * 100).toFixed(m < 0.1 ? 1 : 0)} cm`;
    if (m < 10) return `${m.toFixed(2)} m`;
    return `${m.toFixed(1)} m`;
  };
  // Canvas models carry estimated sizes, or none at all.
  // Tiny models are exported magnified by a power of ten; sizes shown here are the real ones.
  const realDims = (v) => v.dims.map((d) => d / (v.magnified || 1));
  const vSize = (v) => (v.size === "unknown" ? null : Math.max(...realDims(v)));
  const sizeText = (v) => (v.size === "unknown" ? "" : (v.size === "estimated" ? "≈ " : "") + fmtLen(vSize(v)));
  const fmtBytes = (b) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1048576).toFixed(1)} MB`);
  const fmtInt = (n) => n.toLocaleString();
  const norm = (s) => s.toLowerCase().normalize("NFKD").replace(/[^\w\s]/g, " ");
  const byId = new Map(CAT.items.map((it, i) => [it.id, Object.assign(it, { _i: i, _name: it.name.toLowerCase(), _kw: norm(it.name + " " + it.keywords) })]));
  const catLabel = (id) => (CAT.categories.find((c) => c.id === id) || { label: id }).label;
  const subLabel = (catId, subId) => {
    const c = CAT.categories.find((c) => c.id === catId);
    const s = c && c.subcategories.find((s) => s.id === subId);
    return s ? s.label : subId;
  };

  // ---------------------------------------------------------------- URL state
  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    state.q = p.get("q") || "";
    state.cat = p.get("cat") || "";
    state.sub = p.get("sub") || "";
    state.size = p.get("size") || "";
    state.sort = p.get("sort") || "category";
    state.variants = p.get("variants") === "1";
    state.item = p.get("item") || "";
    state.v = parseInt(p.get("v") || "1", 10) || 1;
  }
  function writeHash(replace) {
    const p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.cat) p.set("cat", state.cat);
    if (state.sub) p.set("sub", state.sub);
    if (state.size) p.set("size", state.size);
    if (state.sort !== "category") p.set("sort", state.sort);
    if (state.variants) p.set("variants", "1");
    if (state.item) { p.set("item", state.item); if (state.v > 1) p.set("v", state.v); }
    const h = p.toString();
    const url = location.pathname + location.search + (h ? "#" + h : "");
    if (url === location.pathname + location.search + location.hash) return;
    history[replace ? "replaceState" : "pushState"](null, "", url);
  }

  // ---------------------------------------------------------------- filtering
  function score(it, terms) {
    let s = 0;
    for (const t of terms) {
      if (it._name.startsWith(t)) s += 4;
      else if (it._name.includes(t)) s += 3;
      else if (new RegExp("\\b" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).test(it._kw)) s += 2;
      else if (it._kw.includes(t)) s += 1;
      else return -1;
    }
    return s;
  }

  function compute() {
    if (state.sort === "random" && !shuffleKey.size) shuffleKey = new Map(CAT.items.map((it) => [it.id, Math.random()]));
    const terms = norm(state.q).split(/\s+/).filter(Boolean);
    let list = [];
    for (const it of CAT.items) {
      if (state.cat && it.category !== state.cat) continue;
      if (state.sub && it.subcategory !== state.sub) continue;
      const s = terms.length ? score(it, terms) : 0;
      if (s < 0) continue;
      if (state.size) {
        const sizes = it.variants.map((v) => sizeClass(vSize(v)));
        if (!sizes.includes(state.size)) continue;
      }
      list.push({ it, s });
    }
    const cmp = {
      category: (a, b) => a.it._i - b.it._i,
      name: (a, b) => a.it.name.localeCompare(b.it.name),
      "size-asc": (a, b) => bySize(a.it.size, b.it.size, 1),
      "size-desc": (a, b) => bySize(a.it.size, b.it.size, -1),
      variants: (a, b) => b.it.variants.length - a.it.variants.length || a.it._i - b.it._i,
      random: (a, b) => shuffleKey.get(a.it.id) - shuffleKey.get(b.it.id),
    }[state.sort] || ((a, b) => a.it._i - b.it._i);
    list.sort((a, b) => (terms.length && state.sort === "category" ? b.s - a.s : 0) || cmp(a, b));

    results = [];
    for (const { it } of list) {
      if (state.variants) {
        it.variants.forEach((v, i) => {
          if (!state.size || sizeClass(vSize(v)) === state.size) results.push({ it, vi: i + 1 });
        });
      } else {
        results.push({ it, vi: 1 });
      }
    }
    if (state.variants && state.sort.startsWith("size")) {
      const dir = state.sort === "size-asc" ? 1 : -1;
      results.sort((a, b) => bySize(vSize(a.it.variants[a.vi - 1]), vSize(b.it.variants[b.vi - 1]), dir));
    }
    return list.length;
  }

  // Unknown sizes always sort last.
  function bySize(a, b, dir) {
    if (a == null || b == null) return (a == null) - (b == null);
    return dir * (a - b);
  }

  function sizeClass(m) {
    if (m == null) return "Unknown";
    return m < 0.1 ? "Tiny" : m < 1 ? "Small" : m < 4 ? "Medium" : m < 20 ? "Large" : "Huge";
  }

  // ---------------------------------------------------------------- rendering
  const grid = $("grid");
  const tpl = $("cardTpl");

  function renderGrid() {
    const objectCount = compute();
    const frag = document.createDocumentFragment();
    for (const { it, vi } of results) {
      const v = it.variants[vi - 1];
      const node = tpl.content.firstElementChild.cloneNode(true);
      node.querySelector(".card-link").href = "#item=" + encodeURIComponent(it.id) + (vi > 1 ? "&v=" + vi : "");
      node.dataset.id = it.id;
      node.dataset.v = vi;
      node.style.setProperty("--tint", `var(${TINTS[it.category]})`);
      const img = node.querySelector("img");
      img.src = v.thumb;
      img.alt = it.name;
      node.querySelector(".card-name").textContent = state.variants && it.variants.length > 1 ? `${it.name} ${vi}` : it.name;
      const st = sizeText(v);
      node.querySelector(".card-meta").textContent = st ? `${it.subcategoryLabel} · ${st}` : it.subcategoryLabel;
      if (!state.variants && it.variants.length > 1) node.querySelector(".card-badge").textContent = `×${it.variants.length}`;
      node.querySelector(".card-check").setAttribute("aria-label", `Select ${it.name}`);
      frag.appendChild(node);
    }
    grid.replaceChildren(frag);
    lastChecked = -1;
    paintSelection();
    $("empty").hidden = results.length > 0;

    let title = state.q ? "Results" : "All objects";
    if (state.sub) title = subLabel(state.cat, state.sub);
    else if (state.cat) title = catLabel(state.cat);
    $("resultsTitle").textContent = title;
    $("resultsCount").textContent = state.variants
      ? `${fmtInt(results.length)} variants of ${fmtInt(objectCount)} objects`
      : `${fmtInt(objectCount)} object${objectCount === 1 ? "" : "s"}`;
    document.title = (state.q ? `“${state.q}” · ` : state.cat ? title + " · " : "") + "Everything Library";

    const tags = [];
    if (state.q) tags.push(["q", `“${state.q}”`]);
    if (state.cat) tags.push(["cat", catLabel(state.cat)]);
    if (state.sub) tags.push(["sub", subLabel(state.cat, state.sub)]);
    if (state.size) tags.push(["size", state.size]);
    $("activeFilters").replaceChildren(...tags.map(([k, label]) => {
      const b = document.createElement("button");
      b.className = "filter-tag";
      b.innerHTML = `<span></span><svg viewBox="0 0 24 24" width="14" height="14"><path d="M7 7l10 10M17 7L7 17" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>`;
      b.firstChild.textContent = label;
      b.setAttribute("aria-label", `Remove filter ${label}`);
      b.onclick = () => {
        if (k === "cat") { state.cat = ""; state.sub = ""; } else state[k] = "";
        if (k === "q") $("search").value = "";
        update();
      };
      return b;
    }));
  }

  function renderSidebar() {
    const list = $("catList");
    const all = document.createElement("li");
    all.appendChild(catButton("All objects", CAT.itemCount, "", null));
    const items = [all];
    for (const c of CAT.categories) {
      const li = document.createElement("li");
      li.appendChild(catButton(c.label, c.count, c.id, TINTS[c.id]));
      if (state.cat === c.id) {
        const ul = document.createElement("ul");
        ul.className = "sub-list";
        for (const s of c.subcategories) {
          const sli = document.createElement("li");
          const b = document.createElement("button");
          b.className = "sub-btn";
          b.innerHTML = `<span class="cat-label"></span><span class="count">${s.count}</span>`;
          b.firstChild.textContent = s.label;
          b.setAttribute("aria-current", String(state.sub === s.id));
          b.onclick = () => { state.sub = state.sub === s.id ? "" : s.id; update(); closeSidebar(); };
          sli.appendChild(b);
          ul.appendChild(sli);
        }
        li.appendChild(ul);
      }
      items.push(li);
    }
    list.replaceChildren(...items);

    $("sizeChips").replaceChildren(...SIZES.map((s) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.innerHTML = `<span></span><span class="chip-hint">${s.hint}</span>`;
      b.firstChild.textContent = s.id;
      b.setAttribute("aria-pressed", String(state.size === s.id));
      b.onclick = () => { state.size = state.size === s.id ? "" : s.id; update(); };
      return b;
    }));
  }

  function catButton(label, count, id, tint) {
    const b = document.createElement("button");
    b.className = "cat-btn";
    b.innerHTML = `<span class="cat-dot"></span><span class="cat-label"></span><span class="count">${fmtInt(count)}</span>`;
    b.querySelector(".cat-label").textContent = label;
    const dot = b.querySelector(".cat-dot");
    if (tint) dot.style.background = `var(${tint.replace("--t-", "--d-")})`;
    else {
      const step = 100 / CAT.categories.length;
      dot.style.background = `conic-gradient(${CAT.categories.map((c, i) => `var(--d-${c.id.toLowerCase()}) ${i * step}% ${(i + 1) * step}%`).join(", ")})`;
    }
    b.setAttribute("aria-current", String(state.cat === id && !state.sub));
    b.onclick = () => {
      state.cat = id; state.sub = "";
      update();
      if (!id) closeSidebar();
      document.querySelector(".main").scrollIntoView({ block: "start" });
    };
    return b;
  }

  // ---------------------------------------------------------------- selection + zip download
  // A selection is a set of "itemId#variant" keys. It survives filtering and reloads, so people can
  // collect models across several searches, then download them as one zip built in the browser.
  const SEL_KEY = "everything-library-selection";
  const FFLATE = "https://cdn.jsdelivr.net/npm/fflate@0.8.2/esm/browser.js";
  // Selecting everything hands over a prebuilt zip from the GitHub release instead of pulling
  // all ~500 MB back through the host to rezip it here. Same contents and folder layout;
  // tools/build_release_zips.py builds them, and these are the release assets' own sizes.
  const RELEASE = "https://github.com/Kenji-Jones/everything-library-browser/releases/latest/download";
  const RELEASE_ZIP = { glb: 62699346, fbx: 114279793, blend: 203530015 };
  const keyOf = (id, vi) => `${id}#${vi}`;
  const itemKeys = (it) => it.variants.map((_, i) => keyOf(it.id, i + 1));
  const tileKeys = (it, vi) => (state.variants ? [keyOf(it.id, vi)] : itemKeys(it)); // a tile is one variant or a whole object
  const selection = new Set(loadSelection());
  const variantCount = CAT.items.reduce((n, it) => n + it.variants.length, 0);
  const wholeLibrary = () => selection.size === variantCount;
  const downloadLabel = () => (wholeLibrary() ? "Download whole library" : "Download zip");
  let zipping = null;
  let lastChecked = -1;

  function loadSelection() {
    try { return JSON.parse(localStorage.getItem(SEL_KEY) || "[]").filter((k) => byId.has(k.split("#")[0])); }
    catch { return []; }
  }
  function saveSelection() {
    try { localStorage.setItem(SEL_KEY, JSON.stringify([...selection])); } catch { /* private mode: selection lasts for this visit */ }
  }
  function checkState(keys) {
    const n = keys.filter((k) => selection.has(k)).length;
    return n === 0 ? "false" : n === keys.length ? "true" : "mixed";
  }
  function toggle(keys, on) {
    if (on === undefined) on = checkState(keys) !== "true";
    for (const k of keys) on ? selection.add(k) : selection.delete(k);
    saveSelection();
    paintSelection();
  }

  const format = () => document.querySelector('input[name="fmt"]:checked').value;
  function selectedFiles(fmt) {
    const out = [], seen = new Set();
    for (const k of selection) {
      const [id, vs] = k.split("#");
      const it = byId.get(id), vi = +vs, v = it && it.variants[vi - 1];
      if (!v) continue;
      if (fmt === "blend") { // one .blend per object holds every variant
        if (seen.has(id)) continue;
        seen.add(id);
        out.push({ it, v, vi, url: it.blend, bytes: it.blendBytes });
      } else out.push({ it, v, vi, url: v[fmt], bytes: v[fmt + "Bytes"] });
    }
    return out.sort((a, b) => a.it._i - b.it._i || a.vi - b.vi);
  }

  const CHECK_PATH = "M5 12.5l4.5 4.5L19 7.5", DASH_PATH = "M6 12h12";
  function paintCheck(btn, st) {
    btn.setAttribute("aria-checked", st);
    btn.querySelector("path").setAttribute("d", st === "mixed" ? DASH_PATH : CHECK_PATH);
  }

  function paintSelection() {
    for (const card of grid.children) {
      const st = checkState(tileKeys(byId.get(card.dataset.id), +card.dataset.v));
      paintCheck(card.querySelector(".card-check"), st);
      card.dataset.selected = String(st === "true");
    }
    const keys = results.flatMap(({ it, vi }) => tileKeys(it, vi));
    const all = keys.length > 0 && keys.every((k) => selection.has(k));
    $("selectAll").textContent = !results.length ? "" : `${all ? "Deselect" : "Select"} all ${fmtInt(results.length)}`;

    document.body.classList.toggle("has-selection", selection.size > 0);
    $("selbar").hidden = selection.size === 0 && !zipping;
    const files = selectedFiles(format());
    const objects = new Set([...selection].map((k) => k.split("#")[0])).size;
    $("selCount").textContent = `${fmtInt(objects)} object${objects === 1 ? "" : "s"} selected`;
    const bytes = wholeLibrary() ? RELEASE_ZIP[format()] : files.reduce((a, f) => a + f.bytes, 0);
    $("selSize").textContent = `${fmtInt(files.length)} file${files.length === 1 ? "" : "s"} · about ${fmtBytes(bytes)}`;
    if (!zipping) $("selDownload").textContent = downloadLabel();
    paintDetailSelect();
  }

  function paintDetailSelect() {
    const it = byId.get(state.item);
    if (!it) return;
    const st = checkState(itemKeys(it));
    const b = $("dSelect");
    b.setAttribute("aria-pressed", String(st === "true"));
    b.textContent = st === "true" ? "✓ In your download selection" : st === "mixed" ? "Some variants selected · add all" : "Add to download selection";
  }

  function credits(files, fmt) {
    const canvasCats = [...new Set(CAT.items.filter((i) => i.source).map((i) => catLabel(i.category)))];
    const lines = [
      "Everything Library (c) David OReilly - http://davidoreilly.com/library",
      "Licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Credit the author when you use these models.",
      "",
      `${canvasCats.join(", ")} models were sourced from Everything Canvas (https://everythingcanvas.vercel.app/)`,
      "by Vince McKelvie. Their names and sizes are estimates.",
      "",
      `${files.length} ${fmt.toUpperCase()} files:`,
      "",
    ];
    for (const f of files) {
      const parts = [f.url.split("/").pop(), f.it.name, `${catLabel(f.it.category)} > ${f.it.subcategoryLabel}`];
      if (f.it.source) parts.push(`from ${f.it.source} ${f.it.sourceFiles.join(", ")}`);
      if (f.v.magnified) parts.push(`scaled up ${f.v.magnified}x, multiply by ${1 / f.v.magnified} for real size`);
      lines.push(parts.join("  |  "));
    }
    return lines.join("\n") + "\n";
  }

  function setBusy(on) {
    $("selDownload").disabled = on;
    $("selDownload").textContent = on ? "Zipping…" : downloadLabel();
    $("selProgress").hidden = !on;
    $("selClear").hidden = on;
    if (!on) paintSelection();
  }
  function progress(frac, text) {
    $("selBar").style.width = `${Math.round(frac * 100)}%`;
    $("selProgressText").textContent = text;
  }

  async function downloadZip() {
    const fmt = format();
    const files = selectedFiles(fmt);
    if (!files.length || zipping) return;
    // Everything selected: hand over the prebuilt zip. Works from file:// too, since it's
    // an ordinary link rather than something we have to fetch and rebuild.
    if (wholeLibrary()) {
      const a = document.createElement("a");
      a.href = `${RELEASE}/EverythingLibrary-${fmt}.zip`;
      a.rel = "noopener";
      document.body.appendChild(a);
      a.click();
      a.remove();
      return;
    }
    if (location.protocol === "file:") {
      alert("Zip downloads need the local server. Double-click “Open Library.command” in the library folder.");
      return;
    }
    const total = files.reduce((a, f) => a + f.bytes, 0);
    const cats = new Set(files.map((f) => f.it.category));
    const label = cats.size === 1 ? catLabel([...cats][0]).replace(/\W+/g, "") : "Selection";
    const name = `EverythingLibrary_${label}_${fmt.toUpperCase()}.zip`;

    // Big zips stream straight to disk where the browser supports it, so they never sit in memory.
    let writable = null;
    if (window.showSaveFilePicker && total > 150 * 1048576) {
      try {
        const handle = await window.showSaveFilePicker({ suggestedName: name, types: [{ description: "Zip archive", accept: { "application/zip": [".zip"] } }] });
        writable = await handle.createWritable();
      } catch (e) {
        if (e.name === "AbortError") return;
      }
    }

    const job = (zipping = { cancelled: false });
    setBusy(true);
    progress(0, "Starting…");
    try {
      const { Zip, ZipDeflate, ZipPassThrough } = await import(FFLATE);
      const chunks = [];
      let chain = Promise.resolve(), finish, fail;
      const finished = new Promise((res, rej) => { finish = res; fail = rej; });
      const zip = new Zip((err, chunk, final) => {
        if (err) return fail(err);
        if (writable) chain = chain.then(() => writable.write(chunk));
        else chunks.push(chunk);
        if (final) finish();
      });
      const root = "EverythingLibrary/";
      const addText = (path, text) => {
        const e = new ZipDeflate(root + path, { level: 6 });
        zip.add(e);
        e.push(new TextEncoder().encode(text), true);
      };

      // Fetch a few files ahead while adding them to the zip in order.
      const AHEAD = 4, pending = [];
      const get = (i) => {
        const p = fetch(files[i].url).then((r) => {
          if (!r.ok) throw new Error(`${r.status} for ${files[i].url}`);
          return r.arrayBuffer();
        });
        p.catch(() => {}); // surfaced when awaited below; avoids unhandled-rejection noise after a cancel
        return p;
      };
      for (let i = 0; i < Math.min(AHEAD, files.length); i++) pending[i] = get(i);
      let bytes = 0;
      for (let i = 0; i < files.length; i++) {
        if (job.cancelled) throw new DOMException("Cancelled", "AbortError");
        if (i + AHEAD < files.length) pending[i + AHEAD] = get(i + AHEAD);
        const data = new Uint8Array(await pending[i]);
        pending[i] = null;
        const f = files[i];
        const path = `${catLabel(f.it.category)}/${f.it.subcategoryLabel}/${f.url.split("/").pop()}`.replace(/[:*?"<>|]/g, "");
        // .blend files are already compressed; GLB and FBX shrink a lot with deflate.
        const entry = fmt === "blend" ? new ZipPassThrough(root + path) : new ZipDeflate(root + path, { level: 5 });
        zip.add(entry);
        entry.push(data, true);
        bytes += data.length;
        progress((i + 1) / files.length, `${fmtInt(i + 1)} / ${fmtInt(files.length)} files · ${fmtBytes(bytes)}`);
        await chain; // backpressure when writing to disk
      }
      addText("LICENSE.txt", await fetch("LICENSE.txt").then((r) => r.text()));
      addText("CREDITS.txt", credits(files, fmt));
      zip.end();
      await finished;
      await chain;
      if (writable) await writable.close();
      else {
        const url = URL.createObjectURL(new Blob(chunks, { type: "application/zip" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
      }
    } catch (err) {
      if (writable) try { await writable.abort(); } catch { /* already closed */ }
      if (err.name !== "AbortError") {
        console.error(err);
        alert(`The zip couldn't be finished: ${err.message}`);
      }
    } finally {
      zipping = null;
      setBusy(false);
    }
  }

  // ---------------------------------------------------------------- detail
  const dialog = $("detail");

  function openDetail() {
    const it = byId.get(state.item);
    if (!it) { if (dialog.open) dialog.close(); return; }
    const vi = Math.min(Math.max(1, state.v), it.variants.length);
    const v = it.variants[vi - 1];
    if (!dialog.open) dialog.showModal();

    const crumbs = $("dCrumbs");
    crumbs.replaceChildren();
    const mk = (label, fn) => { const b = document.createElement("button"); b.textContent = label; b.onclick = fn; return b; };
    crumbs.append(
      mk(catLabel(it.category), () => { Object.assign(state, { cat: it.category, sub: "", item: "", q: "" }); $("search").value = ""; update(); }),
      " › ",
      mk(it.subcategoryLabel, () => { Object.assign(state, { cat: it.category, sub: it.subcategory, item: "", q: "" }); $("search").value = ""; update(); }),
    );
    $("dName").textContent = it.name + (it.variants.length > 1 ? ` · ${vi}` : "");

    const [w, d, h] = realDims(v);
    const sizeFact = v.size === "unknown"
      ? `Not available<span class="note">the source normalized this model's size</span>`
      : `${v.size === "estimated" ? "≈ " : ""}${fmtLen(w)} × ${fmtLen(d)} × ${fmtLen(h)}<span class="note">width × depth × height, ${v.size === "estimated" ? "estimated real-world size" : "as authored"}</span>`;
    const facts = [
      ["Size", sizeFact],
      ["Variants", it.variants.length > 1 ? `${vi} of ${it.variants.length}` : "1"],
      ["Triangles", fmtInt(v.tris)],
    ];
    if (v.parts > 1) facts.push(["Parts", String(v.parts)]);
    if (v.magnified) facts.push(["Scale", `Model is ${fmtInt(v.magnified)}× real size<span class="note">so it's usable in a scene; scale by ${1 / v.magnified < 1e-3 ? (1 / v.magnified).toExponential(0) : 1 / v.magnified} for true size</span>`]);
    if (it.source) facts.push(["Source", `<a href="${CANVAS_URL}" target="_blank" rel="noopener">${escapeHtml(it.source)}</a> · ${escapeHtml(it.sourceFiles.join(", "))}`]);
    else if (it.sourceName !== it.name.replace(/ /g, "")) facts.push(["Source name", escapeHtml(it.sourceName)]);
    $("dFacts").innerHTML = facts.map(([k, val]) => `<dt>${k}</dt><dd>${val}</dd>`).join("");

    const base = `${it.id}${it.variants.length > 1 ? "_v" + vi : ""}`;
    $("dDownloads").innerHTML = "";
    const dl = (href, fmt, desc, bytes, primary, name) => {
      const a = document.createElement("a");
      a.className = "dl-btn" + (primary ? " primary" : "");
      a.href = href;
      a.download = name || "";
      a.innerHTML = `<span class="dl-fmt">${fmt}</span><span class="dl-desc">${desc}</span><span class="dl-size">${fmtBytes(bytes)}</span>`;
      $("dDownloads").appendChild(a);
    };
    dl(v.glb, "GLB", "glTF binary · web, Unity, Godot, Blender", v.glbBytes, true, base + ".glb");
    dl(v.fbx, "FBX", "Autodesk FBX · Unity, Unreal, Maya", v.fbxBytes, false, base + ".fbx");
    dl(it.blend, ".blend", it.variants.length > 1 ? `Blender · all ${it.variants.length} variants` : "Blender", it.blendBytes, false, it.id + ".blend");

    const tags = [catLabel(it.category), it.subcategoryLabel, ...(it.sizeClass !== "Unknown" ? [it.sizeClass] : []), ...it.tags];
    $("dTags").replaceChildren(...[...new Set(tags)].map((t) => {
      const b = document.createElement("button");
      b.className = "chip";
      b.textContent = t;
      b.onclick = () => {
        Object.assign(state, { item: "", cat: "", sub: "", size: "", q: "" });
        if (t === catLabel(it.category)) state.cat = it.category;
        else if (t === it.subcategoryLabel) { state.cat = it.category; state.sub = it.subcategory; }
        else if (SIZES.some((s) => s.id === t)) state.size = t;
        else state.q = t;
        $("search").value = state.q;
        update();
      };
      return b;
    }));

    const vs = $("variants");
    if (it.variants.length > 1) {
      vs.replaceChildren(...it.variants.map((vv, i) => {
        const b = document.createElement("button");
        b.className = "variant-btn";
        b.setAttribute("role", "tab");
        b.setAttribute("aria-selected", String(i + 1 === vi));
        b.setAttribute("aria-label", `Variant ${i + 1}`);
        b.innerHTML = `<img alt="" decoding="async"><span>${i + 1}</span>`;
        b.firstChild.src = vv.thumb;
        b.onclick = () => { state.v = i + 1; update(true); };
        return b;
      }));
      vs.children[vi - 1].scrollIntoView({ block: "nearest", inline: "nearest" });
    } else vs.replaceChildren();

    const idx = results.findIndex((r) => r.it.id === it.id && (!state.variants || r.vi === vi));
    $("dPrev").disabled = idx <= 0;
    $("dNext").disabled = idx < 0 || idx >= results.length - 1;

    paintDetailSelect();
    Viewer.show(v, it);
  }

  function step(dir) {
    const idx = results.findIndex((r) => r.it.id === state.item && (!state.variants || r.vi === state.v));
    const next = results[idx + dir];
    if (!next) return;
    state.item = next.it.id;
    state.v = next.vi;
    update(true);
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  // ---------------------------------------------------------------- 3D viewer (three.js, loaded on first use)
  const Viewer = (() => {
    let THREE, GLTFLoader, OrbitControls, RoomEnvironment;
    let renderer, scene, camera, controls, model, shadowLight, ground, loader, ready, token = 0;
    let wire = false;
    const el = $("viewer");
    const poster = $("viewerPoster");
    const status = $("viewerStatus");

    async function init() {
      if (ready) return ready;
      ready = (async () => {
        THREE = await import("three");
        ({ GLTFLoader } = await import("three/addons/loaders/GLTFLoader.js"));
        ({ OrbitControls } = await import("three/addons/controls/OrbitControls.js"));
        ({ RoomEnvironment } = await import("three/addons/environments/RoomEnvironment.js"));

        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
        renderer.outputColorSpace = THREE.SRGBColorSpace;
        renderer.toneMapping = THREE.NeutralToneMapping;
        renderer.shadowMap.enabled = true;
        renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        el.prepend(renderer.domElement);

        scene = new THREE.Scene();
        const pmrem = new THREE.PMREMGenerator(renderer);
        scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
        scene.environmentIntensity = 0.55;
        scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8478, 1.1));
        shadowLight = new THREE.DirectionalLight(0xffffff, 1.8);
        shadowLight.castShadow = true;
        shadowLight.shadow.mapSize.set(2048, 2048);
        shadowLight.shadow.radius = 6;
        shadowLight.shadow.bias = -0.0005;
        scene.add(shadowLight, shadowLight.target);

        ground = new THREE.Mesh(new THREE.CircleGeometry(1, 64), new THREE.ShadowMaterial({ opacity: 0.18 }));
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        scene.add(ground);

        camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1000);
        controls = new OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 1.2;
        controls.addEventListener("start", () => { controls.autoRotate = false; setPressed($("vRotate"), false); });

        loader = new GLTFLoader();
        new ResizeObserver(resize).observe(el);
        resize();
        renderer.setAnimationLoop(() => {
          if (!dialog.open) return;
          controls.update();
          renderer.render(scene, camera);
        });
      })();
      return ready;
    }

    function resize() {
      if (!renderer) return;
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    }

    // The library stores light-beam fades and glass transparency in vertex-colour alpha.
    function prepareMaterials(root) {
      root.traverse((o) => {
        if (!o.isMesh) return;
        o.castShadow = true;
        const name = (o.material && o.material.name) || "";
        if (/light/i.test(name)) {
          // Light beams/bulbs: unlit, vertex-coloured, faded by vertex alpha, so they read as glowing.
          o.material = new THREE.MeshBasicMaterial({
            name, vertexColors: true, transparent: true, depthWrite: false, side: THREE.DoubleSide, toneMapped: false,
          });
          o.castShadow = false;
          o.renderOrder = 2;
        } else if (o.material.transparent) {
          // Genuinely transparent, i.e. the glTF says alphaMode BLEND. Matching on the
          // material NAME instead caught every Mat_ParticleTransp model — nearly all of
          // them opaque — and switching off depthWrite stopped a model occluding itself,
          // so legs drew over bodies and bodies over legs depending on draw order.
          o.material.depthWrite = false;
          o.material.side = THREE.DoubleSide;
          o.castShadow = false;
          o.renderOrder = 1;
        } else {
          o.material.depthWrite = true;
          o.material.alphaTest = 0;
        }
        o.material.wireframe = wire;
      });
    }

    function frame(fit) {
      const box = new THREE.Box3().setFromObject(model);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const radius = Math.max(size.length() / 2, 1e-4);
      const dist = radius / Math.sin((camera.fov * Math.PI) / 360) * 1.05;
      const dir = new THREE.Vector3(0.62, 0.42, 0.78).normalize();
      if (fit) {
        camera.position.copy(center).addScaledVector(dir, dist);
        controls.target.copy(center);
      }
      camera.near = dist / 200;
      camera.far = dist * 20;
      camera.updateProjectionMatrix();
      controls.minDistance = radius * 0.3;
      controls.maxDistance = dist * 4;
      controls.update();

      const r = Math.max(size.x, size.z) * 1.2 + radius * 0.4;
      ground.scale.setScalar(r);
      ground.position.set(center.x, box.min.y, center.z);
      shadowLight.position.set(center.x - radius * 1.5, box.min.y + radius * 3, center.z + radius * 1.5);
      shadowLight.target.position.copy(center);
      const cam = shadowLight.shadow.camera;
      cam.left = cam.bottom = -r; cam.right = cam.top = r;
      cam.near = radius * 0.1; cam.far = radius * 8;
      cam.updateProjectionMatrix();
    }

    async function show(v, it) {
      const my = ++token;
      poster.src = v.thumb;
      poster.alt = it.name;
      poster.classList.remove("hidden");
      status.className = "viewer-status";
      status.textContent = "";
      if (location.protocol === "file:") {
        status.classList.add("error");
        status.innerHTML = "3D preview needs the local server. Double-click <code>Open Library.command</code> in the library folder. Downloads work either way.";
        if (model) { scene.remove(model); model = null; }
        return;
      }
      const slow = setTimeout(() => { if (my === token) status.textContent = "Loading model…"; }, 250);
      try {
        await init();
        const gltf = await loader.loadAsync(v.glb);
        if (my !== token) return;
        if (model) { scene.remove(model); dispose(model); }
        model = gltf.scene;
        prepareMaterials(model);
        scene.add(model);
        frame(true);
        controls.autoRotate = $("vRotate").getAttribute("aria-pressed") === "true";
        resize();
        poster.classList.add("hidden");
        status.textContent = "";
      } catch (err) {
        if (my !== token) return;
        console.error(err);
        status.classList.add("error");
        status.textContent = navigator.onLine === false
          ? "The 3D viewer loads three.js from the internet, and you're offline. Downloads still work."
          : "Couldn't load this model in the viewer. Downloads still work.";
      } finally {
        clearTimeout(slow);
      }
    }

    function dispose(root) {
      root.traverse((o) => {
        if (o.geometry) o.geometry.dispose();
        if (o.material) [].concat(o.material).forEach((m) => m.dispose());
      });
    }

    return {
      show,
      reset() { if (model) { frame(true); } },
      setRotate(on) { if (controls) controls.autoRotate = on; },
      setWire(on) { wire = on; if (model) model.traverse((o) => { if (o.isMesh) o.material.wireframe = on; }); },
    };
  })();

  function setPressed(btn, on) { btn.setAttribute("aria-pressed", String(on)); }

  // ---------------------------------------------------------------- wiring
  let lastListKey = "";
  function update(replace) {
    writeHash(replace);
    sync();
  }

  function sync() {
    const listKey = [state.q, state.cat, state.sub, state.size, state.sort, state.variants].join("|");
    if (listKey !== lastListKey) {
      lastListKey = listKey;
      renderSidebar();
      renderGrid();
    }
    $("search").value !== state.q && document.activeElement !== $("search") && ($("search").value = state.q);
    $("sort").value = state.sort;
    $("showVariants").checked = state.variants;
    if (state.item) openDetail();
    else if (dialog.open) dialog.close();
  }

  function closeSidebar() {
    $("sidebar").classList.remove("open");
    $("scrim").hidden = true;
    $("filtersToggle").setAttribute("aria-expanded", "false");
  }

  let searchTimer;
  $("search").addEventListener("input", (e) => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => { state.q = e.target.value.trim(); update(true); }, 90);
  });
  $("search").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && results.length) { e.preventDefault(); state.item = results[0].it.id; state.v = results[0].vi; update(); }
    if (e.key === "Escape") { e.target.value = ""; state.q = ""; update(true); }
  });
  $("sort").addEventListener("change", (e) => {
    state.sort = e.target.value;
    if (state.sort === "random") shuffleKey = new Map(CAT.items.map((it) => [it.id, Math.random()]));
    update();
  });
  $("showVariants").addEventListener("change", (e) => { state.variants = e.target.checked; update(); });
  $("clearAll").addEventListener("click", () => {
    Object.assign(state, { q: "", cat: "", sub: "", size: "" });
    $("search").value = "";
    update();
  });
  $("brandLink").addEventListener("click", (e) => {
    e.preventDefault();
    Object.assign(state, { q: "", cat: "", sub: "", size: "", item: "" });
    $("search").value = "";
    update();
  });

  grid.addEventListener("click", (e) => {
    const card = e.target.closest(".card");
    if (!card) return;
    if (e.target.closest(".card-check")) {
      // Shift-click selects everything between this tile and the last one checked.
      const idx = [...grid.children].indexOf(card);
      if (e.shiftKey && lastChecked >= 0) {
        const [a, b] = [Math.min(lastChecked, idx), Math.max(lastChecked, idx)];
        toggle(results.slice(a, b + 1).flatMap(({ it, vi }) => tileKeys(it, vi)), true);
      } else toggle(tileKeys(byId.get(card.dataset.id), +card.dataset.v));
      lastChecked = idx;
      return;
    }
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    state.item = card.dataset.id;
    state.v = parseInt(card.dataset.v, 10);
    update();
  });

  $("selectAll").onclick = () => {
    const keys = results.flatMap(({ it, vi }) => tileKeys(it, vi));
    toggle(keys, !keys.every((k) => selection.has(k)));
  };
  $("selClear").onclick = () => { selection.clear(); saveSelection(); paintSelection(); };
  $("selCancel").onclick = () => { if (zipping) zipping.cancelled = true; };
  $("selDownload").onclick = downloadZip;
  document.querySelectorAll('input[name="fmt"]').forEach((r) => r.addEventListener("change", paintSelection));
  $("dSelect").onclick = () => { const it = byId.get(state.item); if (it) toggle(itemKeys(it)); };

  $("dClose").onclick = () => { state.item = ""; update(); };
  $("dPrev").onclick = () => step(-1);
  $("dNext").onclick = () => step(1);
  dialog.addEventListener("cancel", (e) => { e.preventDefault(); state.item = ""; update(); });
  dialog.addEventListener("click", (e) => { if (e.target === dialog) { state.item = ""; update(); } });
  $("vRotate").onclick = (e) => { const on = e.currentTarget.getAttribute("aria-pressed") !== "true"; setPressed(e.currentTarget, on); Viewer.setRotate(on); };
  $("vReset").onclick = () => Viewer.reset();
  $("vWire").onclick = (e) => { const on = e.currentTarget.getAttribute("aria-pressed") !== "true"; setPressed(e.currentTarget, on); Viewer.setWire(on); };
  $("dCopy").onclick = async (e) => {
    const btn = e.currentTarget;
    try { await navigator.clipboard.writeText(location.href); btn.textContent = "Link copied"; }
    catch { btn.textContent = "Copy failed. Use the address bar."; }
    setTimeout(() => (btn.textContent = "Copy link to this object"), 1600);
  };

  $("filtersToggle").onclick = () => {
    const open = !$("sidebar").classList.contains("open");
    $("sidebar").classList.toggle("open", open);
    $("scrim").hidden = !open;
    $("filtersToggle").setAttribute("aria-expanded", String(open));
  };
  $("scrim").onclick = closeSidebar;

  document.addEventListener("keydown", (e) => {
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing && !dialog.open) { e.preventDefault(); $("search").focus(); $("search").select(); }
    if (dialog.open && !typing) {
      if (e.key === "ArrowLeft") { e.preventDefault(); step(-1); }
      if (e.key === "ArrowRight") { e.preventDefault(); step(1); }
    }
  });
  window.addEventListener("popstate", () => { readHash(); sync(); });
  window.addEventListener("hashchange", () => { readHash(); sync(); });

  readHash();
  if (state.sort === "random") shuffleKey = new Map(CAT.items.map((it) => [it.id, Math.random()]));
  $("search").value = state.q;
  sync();
})();
