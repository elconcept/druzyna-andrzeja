"use strict";

/**
 * Read-only in-site Git tree and text-file preview.
 * GitHub.dev is always available as a full external repository explorer.
 * Data stays server-side proxied via Cloudflare Worker; no user token required.
 */
(() => {
  const $ = (id) => document.getElementById(id);
  const dialog = $("code-dialog");
  if (!dialog) return;
  const tree = $("code-tree");
  const preview = $("code-preview");
  const expanded = new Set();
  let current = null;
  let entries = [];
  let selected = "";
  let generation = 0;
  let lastFocus = null;

  function message(value) { $("code-message").textContent = value; }
  function safePath(path) {
    return typeof path === "string" && path.length <= 700 &&
      !path.split("/").some(p => p === ".." || p === "." || p === "") &&
      !path.includes("\0");
  }
  function close() {
    dialog.hidden = true;
    document.body.style.overflow = "";
    generation++;
    if (lastFocus?.focus) lastFocus.focus();
  }
  $("code-close").addEventListener("click", close);
  $("code-backdrop").addEventListener("click", close);
  document.addEventListener("keydown", (event) => { if (!dialog.hidden && event.key === "Escape") close(); });
  $("code-search").addEventListener("input", drawTree);

  async function api(endpoint, query) {
    const params = new URLSearchParams(query);
    const response = await fetch("/api/" + endpoint + "?" + params, { cache: "no-cache" });
    let data;
    try { data = await response.json(); } catch { throw Error("Nieprawidłowa odpowiedź serwera"); }
    if (!response.ok) throw Error(data.error || "HTTP " + response.status);
    return data;
  }

  function drawTree() {
    tree.replaceChildren();
    const filter = $("code-search").value.toLocaleLowerCase("pl").trim();
    const chosen = entries.filter((entry) => {
      if (filter) return entry.type === "blob" && entry.path.toLocaleLowerCase("pl").includes(filter);
      return entry.path.split("/").slice(0,-1).every((_,i) =>
        expanded.has(entry.path.split("/").slice(0,i+1).join("/")));
    }).slice(0, 1500);
    if (!chosen.length) {
      const p = document.createElement("p");
      p.className = "code-empty";
      p.textContent = "Brak pasujących plików. Rozwiń katalog lub zmień filtr.";
      tree.append(p);
      return;
    }
    const fragment = document.createDocumentFragment();
    for (const entry of chosen) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "code-entry " + (entry.type === "tree" ? "folder" : "") + (entry.path === selected ? " selected" : "");
      btn.style.paddingLeft = (filter ? 8 : 8 + Math.min(15,entry.path.split("/").length-1)*11) + "px";
      btn.textContent = (entry.type === "tree" ? (expanded.has(entry.path) ? "▾ " : "▸ ") : "▹ ") +
        (filter ? entry.path : entry.path.split("/").at(-1));
      if (entry.type === "tree") {
        btn.setAttribute("aria-expanded", String(expanded.has(entry.path)));
        btn.addEventListener("click", () => {
          expanded.has(entry.path) ? expanded.delete(entry.path) : expanded.add(entry.path);
          drawTree();
        });
      } else {
        btn.addEventListener("click", () => showFile(entry));
      }
      fragment.append(btn);
    }
    tree.append(fragment);
    if (chosen.length === 1500) tree.append(Object.assign(document.createElement("p"),
      { className: "code-empty", textContent: "Wyświetlono maks. 1500 pozycji. Użyj filtra plików." }));
  }

  async function showFile(entry) {
    if (!current || !safePath(entry.path)) return;
    const id = generation;
    selected = entry.path;
    $("code-path").textContent = entry.path + (entry.size ? " · " + entry.size.toLocaleString("pl-PL") + " B" : "");
    preview.textContent = "Wczytywanie pliku…";
    drawTree();
    if (entry.size > 250000) {
      preview.textContent = "Plik za duży do podglądu (limit 250 KB). Otwórz go w GitHub.dev.";
      return;
    }
    try {
      const data = await api("file", { repo: current.slug, ref: current.ref, path: entry.path });
      if (id !== generation) return;
      preview.textContent = data.content;
      message("Podgląd pliku · " + entry.path);
    } catch (error) {
      if (id !== generation) return;
      preview.textContent = "Nie udało się otworzyć pliku: " + error.message + "\nUżyj pełnej przeglądarki GitHub.dev.";
    }
  }

  window.openCodeBrowser = async function(item) {
    if (!item?.github) return;
    const m = item.url.match(/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+)$/i);
    if (!m) return;
    const slug = m[1] + "/" + m[2];
    const ref = item.metrics?.last_commit_sha;
    const id = ++generation;
    lastFocus = document.activeElement;
    current = { slug, ref };
    entries = [];
    selected = "";
    expanded.clear();
    $("code-search").value = "";
    dialog.hidden = false;
    document.body.style.overflow = "hidden";
    $("code-title").textContent = item.name;
    $("code-ref").textContent = slug + (ref ? " · " + ref.slice(0,10) : "") + " · podgląd tylko do odczytu";
    $("code-github").href = item.url;
    $("code-dev").href = "https://github.dev/" + slug;
    $("code-close").focus();
    tree.textContent = "";
    preview.textContent = "Wybierz plik z drzewa.";
    message("Wczytywanie drzewa Git…");
    if (!/^[a-f0-9]{40}$/i.test(ref || "")) {
      message("Brak identyfikatora commita w metrykach.");
      tree.textContent = "Wybierz „Otwórz pełny edytor GitHub.dev”.";
      return;
    }
    try {
      const data = await api("tree", { repo: slug, ref });
      if (id !== generation) return;
      entries = (data.tree || []).filter(v => safePath(v.path) && (v.type === "tree" || v.type === "blob"));
      entries.sort((a,b) => {
        const ap = a.path.split("/"), bp = b.path.split("/");
        if (ap.slice(0,-1).join("/") === bp.slice(0,-1).join("/") && a.type !== b.type) return a.type === "tree" ? -1 : 1;
        return a.path.localeCompare(b.path, "pl");
      });
      message(entries.length + " pozycji" + (data.truncated ? " · GitHub ograniczył rozmiar drzewa" : ""));
      drawTree();
    } catch (error) {
      if (id !== generation) return;
      message("Nie udało się pobrać drzewa.");
      tree.textContent = "Błąd: " + error.message + ". Skorzystaj z GitHub.dev.";
    }
  };
})();
