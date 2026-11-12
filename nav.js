/* Shared navigation: sidebar on desktop, bottom bar on phones. Loaded by every signed-in page. */
(function () {
  var svg = function (p) {
    return '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + p + "</svg>";
  };
  // path + optional hash decide where a link goes; bar:1 means it also appears in the phone bottom bar
  var ITEMS = [
    { id: "food", label: "Nutrition", path: "/", hash: "", bar: 1, ic: '<path d="M6 3v7a2 2 0 0 0 2 2v9M10 3v7a2 2 0 0 1-2 2M8 3v5M17 21V3c-2.5 1.5-3.5 4-3.5 8h3.5"/>' },
    { id: "workouts", label: "Workouts", path: "/workouts", hash: "", bar: 1, ic: '<path d="M6 7v10M3 9.5v5M18 7v10M21 9.5v5M6 12h12"/>' },
    { id: "calendar", label: "Calendar", path: "/calendar", hash: "", bar: 1, ic: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>' },
    { id: "progress", label: "Progress", path: "/progress", hash: "", bar: 1, ic: '<path d="M3 17l6-6 4 4 8-9M15 6h6v6"/>' },
    { id: "awards", label: "Achievements", short: "Awards", path: "/achievements", hash: "", bar: 0, ic: '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4c0 3 1 4 4 5M16 6h4c0 3-1 4-4 5M12 13v4M8 21h8M10 17h4"/>' },
    { id: "settings", label: "Settings", path: "/account", hash: "", bar: 1, ic: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>' }
  ];
  var norm = function (p) { return p.replace(/\/+$/, "") || "/"; };
  var here = norm(location.pathname);

  var css = document.createElement("style");
  css.textContent =
    "section[id]{scroll-margin-top:16px}" +
    ".nv-side{display:none}" +
    ".nv-bar{display:flex;position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--card);border-top:1px solid var(--bd);padding-bottom:env(safe-area-inset-bottom,0px)}" +
    ".nv-bar a{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;gap:2px;padding:8px 0 7px;color:var(--mu);text-decoration:none;font-size:11.5px;font-weight:600;touch-action:manipulation}" +
    ".nv-bar a.on{color:var(--tx);box-shadow:inset 0 2px 0 var(--ac)}" +
    ".bn{display:none!important}" +
    "@media(max-width:780px){body{padding-bottom:calc(66px + env(safe-area-inset-bottom,0px))}}" +
    "@media(min-width:781px){" +
    "body{padding-left:224px}" +
    ".nv-bar{display:none}" +
    ".nv-side{display:flex;flex-direction:column;gap:2px;position:fixed;top:0;left:0;bottom:0;width:224px;padding:calc(20px + env(safe-area-inset-top,0px)) 12px 18px;background:var(--card);border-right:1px solid var(--bd);z-index:30;overflow-y:auto}" +
    ".nv-brand{display:flex;align-items:center;gap:10px;font-weight:750;font-size:19px;letter-spacing:-.02em;padding:2px 12px 18px;color:var(--tx)}" +
    ".nv-brand i{width:10px;height:10px;border-radius:50%;background:var(--ac)}" +
    ".nv-side a{display:flex;align-items:center;gap:12px;padding:10px 12px;border-radius:8px;color:var(--mu);text-decoration:none;font-weight:600;font-size:14.5px}" +
    ".nv-side a:hover{background:var(--pn);color:var(--tx)}" +
    ".nv-side a.on{background:var(--pn);color:var(--tx);box-shadow:inset 3px 0 0 var(--ac)}" +
    ".nv-side a:focus-visible{outline:2px solid var(--ac);outline-offset:1px}" +
    ".nv-sp{flex:1}" +
    "}";
  document.head.appendChild(css);

  var link = function (it, bar) {
    return '<a href="' + it.path + it.hash + '" data-nv="' + it.id + '">' + svg(it.ic) + "<span>" + (bar && it.short ? it.short : it.label) + "</span></a>";
  };
  var side = document.createElement("nav");
  side.className = "nv-side";
  side.setAttribute("aria-label", "Main");
  var main = ITEMS.filter(function (i) { return i.id !== "settings"; }).map(function (i) { return link(i, false); }).join("");
  side.innerHTML = '<div class="nv-brand"><i></i>Calories</div>' + main + '<div class="nv-sp"></div>' + link(ITEMS[ITEMS.length - 1], false);
  var bar = document.createElement("nav");
  bar.className = "nv-bar";
  bar.setAttribute("aria-label", "Main");
  bar.innerHTML = ITEMS.filter(function (i) { return i.bar; }).map(function (i) { return link(i, true); }).join("");
  document.body.appendChild(side);
  document.body.appendChild(bar);

  function current() {
    if (here === "/") return "food";
    for (var i = 0; i < ITEMS.length; i++) if (ITEMS[i].path !== "/" && ITEMS[i].path === here) return ITEMS[i].id;
    return "";
  }
  function mark() {
    var c = current();
    document.querySelectorAll("[data-nv]").forEach(function (a) {
      var on = a.getAttribute("data-nv") === (c === "awards" && a.closest(".nv-bar") ? "progress" : c);
      a.classList.toggle("on", on);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }
  mark();
  window.addEventListener("hashchange", mark);

  // On the tracker page, section links scroll instead of reloading
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[data-nv]");
    if (!a || here !== "/") return;
    var u = new URL(a.href, location.href);
    if (norm(u.pathname) !== "/") return;
    e.preventDefault();
    var smooth = !(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);
    var t = u.hash && document.querySelector(u.hash);
    if (t) t.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
    else scrollTo({ top: 0, behavior: smooth ? "smooth" : "auto" });
    history.replaceState(null, "", u.pathname + u.hash);
    mark();
  });
})();
