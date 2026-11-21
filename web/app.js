"use strict";

const $ = (id) => document.getElementById(id);
const controls = ["search", "kind", "status", "category", "tag", "sort"].map($);
let proposals = [];
let visible = [];
let shown = 60;
let toastTimer;

const number = (value) => typeof value === "number" ? new Intl.NumberFormat("pl-PL").format(value) : "—";
const date = (value) => {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isFinite(d.getTime()) ? new Intl.DateTimeFormat("pl-PL", { year: "numeric", month: "short", day: "numeric" }).format(d) : "—";
};
const validUrl = (value) => {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : "#"; }
  catch { return "#"; }
};
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}
function link(text, href, className = "") {
  const node = el("a", className, text);
  node.href = validUrl(href);
  node.rel = "noreferrer noopener";
  node.target = "_blank";
  return node;
}
function notice(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("visible"), 3300);
}
function requestDownloadUrl(item) {
  const slug = repoSlug(item);
  if (!slug) return null;
  const url = new URL("https://github.com/elconcept/druzyna-andrzeja/issues/new");
  url.searchParams.set("title", "fetch: " + slug);
  url.searchParams.set("body",
    "Zgłoszenie pobrania publicznego repozytorium do katalogów _vendor/ i _workbench/.\n" +
    "Repozytorium: " + item.url + "\n" +
    "Po zapisaniu issue GitHub Actions zweryfikuje katalog prawa polskiego, licencję i rozmiar źródła.");
  return url.href;
}

function metric(label, value, extra = "", title = "") {
  const span = el("span", "metric" + (value === "—" ? " unknown" : ""));
  if (title) span.title = title;
  span.append(el("span", "metric-label", label), el("b", "", value), el("span", "", extra));
  return span;
}

function health(item) {
  const m = item.metrics || {};
  if (!item.github || typeof m.stars !== "number" || !m.last_commit) return null;
  if (item.health?.method === "repo-health-v1" && typeof item.health.value === "number") return item.health;
  const days = Math.max(0, (Date.now() - Date.parse(m.last_commit)) / 86400000);
  if (!Number.isFinite(days)) return null;
  const cap = (value, max) => Math.min(1, Math.log1p(Math.max(0, value || 0)) / Math.log1p(max));
  const parts = {
    "popularność": +(25 * cap(m.stars, 1000) + 10 * cap(m.forks, 200)).toFixed(1),
    "aktualność": +(40 * Math.exp(-days / 260)).toFixed(1),
    "społeczność": +(20 * cap(m.contributors, 40)).toFixed(1),
    "licencja": m.license && m.license !== "NOASSERTION" ? 5 : 0,
  };
  const value = Math.round(Math.max(0, Math.min(100, Object.values(parts).reduce((x,y) => x+y, 0) - (m.archived ? 35 : 0))));
  return { value, parts, method: "repo-health-v1", archived_penalty: !!m.archived };
}
function repoSlug(item) {
  if (!item.github) return null;
  const match = item.url.match(/^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+)$/i);
  return match ? match[1] + "/" + match[2] : null;
}

function card(item) {
  const root = el("article", "item");
  const top = el("div", "item-top");
  const identity = el("div", "item-ident");
  identity.append(link(item.name, item.url, "item-name"));
  let host = "";
  try { host = new URL(item.url).hostname.replace(/^www\./, ""); } catch { host = item.url; }
  identity.append(el("div", "item-url", item.github ? item.url.replace(/^https:\/\/github\.com\//i, "") : host));
  const state = el("span", "state" + (item.approved ? " approved" : ""), item.approved ? "ZATWIERDZONE" : "DO OCENY");
  const h = health(item);
  const badge = el("span", "score-badge" + (h === null ? " none" : item.metrics?.archived ? " archived" : ""));
  badge.append(el("strong", "", h ? String(h.value) : "—"), el("small", "", "Potencjał"));
  badge.title = h ? "Wskaźnik techniczny (0–100): " + Object.entries(h.parts).map(([k,v]) => k + " " + v).join("; ") + (h.archived_penalty ? "; archiwizacja −35" : "") + ". Nie ocenia poprawności prawa." : "Brak wystarczających metryk GitHub.";
  top.append(identity, badge);
  root.append(top);
  root.append(el("span", "category-pill", item.category || "Inne"));
  root.append(el("p", "description", item.description || "Brak opisu w źródłowej liście."));
  const tags = el("div", "tags");
  const tagList = [...new Set([...(item.tags || []), ...(item.metrics?.github_topics || [])].filter(name => name && name !== "Prawo polskie" && name !== item.category))];
  if (item.github) tagList.push("GitHub");
  else tagList.push("Źródło zewnętrzne");
  for (const name of [...new Set(tagList)].slice(0, 6)) {
    const badge = el("span", "tag" + (/archiv|deprecat/i.test(name) ? " archived" : ""), name);
    badge.title = name;
    tags.append(badge);
  }
  tags.prepend(state);
  root.append(tags);
  const stats = el("div", "metrics");
  const m = item.metrics || {};
  if (item.github) {
    stats.append(
      metric("★", number(m.stars), "gwiazdek", "Popularność: gwiazdki GitHub"),
      metric("⑂", number(m.forks), "forków", "Liczba forków"),
      metric("◉", number(m.contributors), "autorów", "Liczba contributorów GitHub"),
      metric("PR", number(m.open_prs), "otwartych", "Otwarte pull requesty (nie są dowodem jakości)"),
      metric("Issues", number(m.open_issues), "otwartych", "Otwarte zgłoszenia"),
      metric("Commit", date(m.last_commit), "", "Ostatni commit domyślnej gałęzi"),
      metric("Licencja", m.license && m.license !== "NOASSERTION" ? m.license : "—", "", "Identyfikator SPDX lub brak deklaracji")
    );
    if (m.language) stats.append(metric("Kod", m.language, "", "Język główny"));
  } else {
    stats.append(el("span", "metric", "Źródło spoza GitHub · metryki i ranking niedostępne"));
  }
  if (m.archived) stats.append(el("span", "tag archived", "ARCHIWUM GITHUB"));
  root.append(stats);
  const bottom = el("div", "item-bottom");
  bottom.append(link("Źródło ↗", item.url, "action-link"));
  const slug = repoSlug(item);
  if (slug) {
    const inspect = el("button", "action-ghost", "Przeglądaj pliki");
    inspect.type = "button";
    inspect.addEventListener("click", () => {
      if (typeof window.openCodeBrowser === "function") window.openCodeBrowser(item);
      else notice("Przeglądarka kodu jest niedostępna.");
    });
    bottom.append(inspect);
    bottom.append(link("GitHub.dev ↗", "https://github.dev/" + slug, "action-link"));
  }
  if (item.github) {
    if (item.approved) {
      bottom.append(el("button", "", "W sources.toml"));
      bottom.lastChild.disabled = true;
    } else if (item.metrics?.license && item.metrics.license !== "NOASSERTION" && !item.metrics?.archived) {
      const request = link("Pobierz do warsztatu ↗", requestDownloadUrl(item), "action-link");
      request.title = "Zapisz wstępnie wypełnione zgłoszenie na GitHub. Actions pobierze licencjonowane repozytorium automatycznie.";
      bottom.append(request);
    } else {
      const unavailable = el("button", "", "Bez licencji: tylko podgląd");
      unavailable.type = "button";
      unavailable.disabled = true;
      unavailable.title = "Kopiowanie do publicznego workbench wymaga potwierdzonej licencji i niezarchiwizowanego repozytorium.";
      bottom.append(unavailable);
    }
  }
  root.append(bottom);
  return root;
}
function compare(a, b, choice) {
  if (choice === "name") return a.name.localeCompare(b.name, "pl");
  if (choice === "health") {
    const av = health(a)?.value ?? -1, bv = health(b)?.value ?? -1;
    return bv - av || (b.metrics?.stars ?? -1) - (a.metrics?.stars ?? -1) || a.name.localeCompare(b.name, "pl");
  }
  const field = { stars: "stars", contributors: "contributors", forks: "forks", prs: "open_prs" }[choice];
  if (field) {
    const x = a.metrics?.[field], y = b.metrics?.[field];
    return (typeof y === "number" ? y : -1) - (typeof x === "number" ? x : -1) || a.name.localeCompare(b.name, "pl");
  }
  if (choice === "commit") {
    return (b.metrics?.last_commit || "").localeCompare(a.metrics?.last_commit || "") || a.name.localeCompare(b.name, "pl");
  }
  return 0;
}
function filter() {
  const query = $("search").value.trim().toLocaleLowerCase("pl");
  const kind = $("kind").value, status = $("status").value, tag = $("tag").value, category = $("category").value;
  visible = proposals.filter((p) => {
    if (kind === "github" && !p.github || kind === "external" && p.github) return false;
    if (status === "approved" && !p.approved || status === "pending" && p.approved) return false;
    if (category && p.category !== category) return false;
    if (tag && ![...(p.tags || []), ...(p.metrics?.github_topics || [])].includes(tag)) return false;
    if (query && ![p.name, p.url, p.description, ...(p.tags || []), ...(p.metrics?.github_topics || [])].join(" ").toLocaleLowerCase("pl").includes(query)) return false;
    return true;
  }).sort((a, b) => compare(a, b, $("sort").value));
  shown = 60;
  render();
}
function render() {
  const container = $("items");
  const batch = document.createDocumentFragment();
  for (const p of visible.slice(0, shown)) batch.append(card(p));
  container.replaceChildren(batch);
  if (!visible.length) container.append(el("div", "empty", "Brak wyników. Zmień filtr lub frazę wyszukiwania."));
  $("result-count").textContent = "Wyświetlono " + Math.min(shown, visible.length) + " z " + visible.length + " wyników";
  $("load-more").hidden = shown >= visible.length;
}
async function start() {
  for (const control of controls) control.addEventListener(control.id === "search" ? "input" : "change", filter);
  $("reset").addEventListener("click", () => {
    for (const c of controls) c.value = c.id === "sort" ? "health" : c.id === "tag" || c.id === "category" || c.id === "search" ? "" : "all";
    filter();
  });
  $("load-more").addEventListener("click", () => { shown += 60; render(); });
  try {
    const response = await fetch("./data/proposals.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    if (data.schema !== 1 || data.jurisdiction !== "PL" || !Array.isArray(data.proposals)) throw new Error("Katalog nie ma potwierdzonego zakresu prawa polskiego (PL)");
    proposals = data.proposals;
    $("count-all").textContent = number(proposals.length);
    $("count-gh").textContent = number(proposals.filter((p) => p.github).length);
    $("count-approved").textContent = number(proposals.filter((p) => p.approved).length);
    $("checked-at").textContent = date(data.generated_at);
    const tags = [...new Set(proposals.flatMap((p) => [...(p.tags || []), ...(p.metrics?.github_topics || [])]))].sort((a, b) => a.localeCompare(b, "pl"));
    for (const tag of tags) {
      const option = document.createElement("option");
      option.value = option.textContent = tag;
      $("tag").append(option);
    }
    const categories = [...new Set(proposals.map(p => p.category || "Inne"))].sort((a,b) => a.localeCompare(b, "pl"));
    for (const category of categories) {
      const option = document.createElement("option");
      option.value = option.textContent = category;
      $("category").append(option);
    }
    filter();
  } catch (err) {
    $("result-count").textContent = "Błąd ładowania";
    $("error").hidden = false;
    $("error").textContent = "Nie udało się pobrać danych katalogu: " + String(err) + ". Sprawdź workflow katalogu.";
  }
}
start();
