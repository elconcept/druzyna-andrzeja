"use strict";

const $ = (id) => document.getElementById(id);
const controls = ["search", "kind", "status", "tag", "sort"].map($);
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
async function copyApproval(item) {
  if (!item.github) return;
  const url = new URL(item.url);
  const pieces = url.pathname.replace(/^\/|\/$/g, "").split("/");
  if (pieces.length !== 2) return;
  const repo = pieces[1].replace(/\.git$/i, "");
  let slug = (pieces[0] + "-" + repo).toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 100);
  if (!/^[a-z]/.test(slug)) slug = "repo-" + slug;
  const code = '[[' + 'repo]]\nname = "' + slug + '"\nurl = "' + item.url + '.git"\n';
  try {
    await navigator.clipboard.writeText(code);
    notice("Wpis TOML skopiowany. Dodaj go do sources.toml i zatwierdź commit na GitHub.");
  } catch {
    window.prompt("Skopiuj wpis do sources.toml:", code);
  }
}
function metric(label, value, extra = "", title = "") {
  const span = el("span", "metric");
  if (title) span.title = title;
  span.append(el("span", "", label), el("b", "", value), el("span", "", extra));
  return span;
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
  top.append(identity, state);
  root.append(top, el("p", "description", item.description || "Brak opisu w źródłowej liście."));
  const tags = el("div", "tags");
  const tagList = [...new Set([...(item.tags || []), ...(item.metrics?.github_topics || [])].filter(Boolean))];
  if (item.github) tagList.push("GitHub");
  else tagList.push("Źródło zewnętrzne");
  for (const name of [...new Set(tagList)].slice(0, 6)) {
    const badge = el("span", "tag" + (/archiv|deprecat/i.test(name) ? " archived" : ""), name);
    badge.title = name;
    tags.append(badge);
  }
  root.append(tags);
  const stats = el("div", "metrics");
  const m = item.metrics || {};
  if (item.github) {
    stats.append(
      metric("★", number(m.stars), "", "Gwiazdki GitHub"),
      metric("↗", number(m.open_prs), "PR", "Otwarte pull requesty"),
      metric("◉", number(m.contributors), "autorów", "Contributors z GitHub"),
      metric("⑂", number(m.forks), "forków", "Forks GitHub"),
      metric("◷", date(m.last_commit), "", "Data ostatniego commita na głównej gałęzi")
    );
  } else {
    stats.append(el("span", "metric", "Poza GitHub · statystyki commitów i PR niedostępne"));
  }
  if (m.archived) stats.append(el("span", "tag archived", "ARCHIWUM GH"));
  root.append(stats);
  const bottom = el("div", "item-bottom");
  bottom.append(link("Otwórz źródło ↗", item.url));
  if (item.github) {
    if (item.approved) {
      bottom.append(el("button", "", "W sources.toml"));
      bottom.lastChild.disabled = true;
    } else {
      const btn = el("button", "", "Kopiuj wpis TOML");
      btn.type = "button";
      btn.title = "Kopiuj blok [[repo]] do ręcznego zatwierdzenia w sources.toml";
      btn.addEventListener("click", () => copyApproval(item));
      bottom.append(btn);
    }
  }
  root.append(bottom);
  return root;
}
function compare(a, b, choice) {
  if (choice === "name") return a.name.localeCompare(b.name, "pl");
  const field = { stars: "stars", contributors: "contributors", prs: "open_prs" }[choice];
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
  const kind = $("kind").value, status = $("status").value, tag = $("tag").value;
  visible = proposals.filter((p) => {
    if (kind === "github" && !p.github || kind === "external" && p.github) return false;
    if (status === "approved" && !p.approved || status === "pending" && p.approved) return false;
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
    for (const c of controls) c.value = c.id === "sort" ? "name" : c.id === "tag" || c.id === "search" ? "" : "all";
    filter();
  });
  $("load-more").addEventListener("click", () => { shown += 60; render(); });
  try {
    const response = await fetch("./data/proposals.json", { cache: "no-cache" });
    if (!response.ok) throw new Error("HTTP " + response.status);
    const data = await response.json();
    if (data.schema !== 1 || !Array.isArray(data.proposals)) throw new Error("Nieprawidłowy schemat katalogu");
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
    filter();
  } catch (err) {
    $("result-count").textContent = "Błąd ładowania";
    $("error").hidden = false;
    $("error").textContent = "Nie udało się pobrać danych katalogu: " + String(err) + ". Sprawdź workflow katalogu.";
  }
}
start();
