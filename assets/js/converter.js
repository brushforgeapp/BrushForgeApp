/* BrushForge web converter: same matching engine as the app.
   sRGB→LAB (D65) + CIEDE2000, finish-group pooling, ΔE tier wording.
   Data: /assets/data/paints.min.json (lazy-loaded on first interaction). */
(function () {
  "use strict";

  var DATA_URL = "/assets/data/paints.min.json";
  var APP_URL = "https://play.google.com/store/apps/details?id=io.brushforge.brushforge_android_app&referrer=utm_source%3Dbrushforgeapp.com%26utm_medium%3Dweb%26utm_campaign%3Dcatalog%26utm_content%3Dconverter";
  var IOS_URL = "https://apps.apple.com/be/app/brushforge/id6749896227";
  var dataPromise = null;
  var PAINTS = null;
  var BRAND_DISPLAY = { "Monument Hobbies": "Pro Acryl" };

  function disp(brand) {
    return BRAND_DISPLAY[brand] || brand;
  }

  /* ---------------- color math (port of tools/bfcatalog.py) ---------------- */

  function hexToLab(hex) {
    var n = parseInt(hex.slice(1), 16);
    var r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
    function lin(c) { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); }
    var rl = lin(r), gl = lin(g), bl = lin(b);
    var X = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375;
    var Y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750;
    var Z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041;
    function f(t) { return t > 0.008856451679 ? Math.cbrt(t) : t / (3 * 0.042806183202) + 4 / 29; }
    var fx = f(X / 0.95047), fy = f(Y / 1.0), fz = f(Z / 1.08883);
    return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
  }

  function de2000(l1, l2) {
    var L1 = l1[0], a1 = l1[1], b1 = l1[2], L2 = l2[0], a2 = l2[1], b2 = l2[2];
    var C1 = Math.hypot(a1, b1), C2 = Math.hypot(a2, b2);
    var Cbar = (C1 + C2) / 2;
    var C7 = Math.pow(Cbar, 7);
    var G = 0.5 * (1 - Math.sqrt(C7 / (C7 + Math.pow(25, 7))));
    var a1p = (1 + G) * a1, a2p = (1 + G) * a2;
    var C1p = Math.hypot(a1p, b1), C2p = Math.hypot(a2p, b2);
    function hp(a, b) {
      if (a === 0 && b === 0) return 0;
      var h = Math.atan2(b, a) * 180 / Math.PI;
      return h < 0 ? h + 360 : h;
    }
    var h1p = hp(a1p, b1), h2p = hp(a2p, b2);
    var dLp = L2 - L1, dCp = C2p - C1p, dhp;
    if (C1p * C2p === 0) dhp = 0;
    else if (Math.abs(h2p - h1p) <= 180) dhp = h2p - h1p;
    else if (h2p - h1p > 180) dhp = h2p - h1p - 360;
    else dhp = h2p - h1p + 360;
    var dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin(dhp * Math.PI / 360);
    var Lbp = (L1 + L2) / 2, Cbp = (C1p + C2p) / 2, hbp;
    if (C1p * C2p === 0) hbp = h1p + h2p;
    else if (Math.abs(h1p - h2p) <= 180) hbp = (h1p + h2p) / 2;
    else if (h1p + h2p < 360) hbp = (h1p + h2p + 360) / 2;
    else hbp = (h1p + h2p - 360) / 2;
    var rad = Math.PI / 180;
    var T = 1 - 0.17 * Math.cos((hbp - 30) * rad) + 0.24 * Math.cos(2 * hbp * rad)
        + 0.32 * Math.cos((3 * hbp + 6) * rad) - 0.20 * Math.cos((4 * hbp - 63) * rad);
    var dTheta = 30 * Math.exp(-Math.pow((hbp - 275) / 25, 2));
    var Cbp7 = Math.pow(Cbp, 7);
    var RC = 2 * Math.sqrt(Cbp7 / (Cbp7 + Math.pow(25, 7)));
    var SL = 1 + 0.015 * Math.pow(Lbp - 50, 2) / Math.sqrt(20 + Math.pow(Lbp - 50, 2));
    var SC = 1 + 0.045 * Cbp;
    var SH = 1 + 0.015 * Cbp * T;
    var RT = -Math.sin(2 * dTheta * rad) * RC;
    return Math.sqrt(Math.pow(dLp / SL, 2) + Math.pow(dCp / SC, 2) + Math.pow(dHp / SH, 2)
        + RT * (dCp / SC) * (dHp / SH));
  }

  function deScale(de) {
    if (de < 0.5) return ["identical", "excellent"];
    if (de <= 2) return ["nearly identical", "excellent"];
    if (de <= 5) return ["close match", "good"];
    if (de <= 10) return ["noticeable difference", "fair"];
    return ["different color", "poor"];
  }

  function confidence(de) {
    return Math.max(0, Math.min(1, 1 - de / 50));
  }

  /* ------------------------------- data ---------------------------------- */

  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch(DATA_URL).then(function (r) { return r.json(); }).then(function (raw) {
        PAINTS = raw.paints.map(function (row) {
          return {
            name: row[0], brand: row[1], line: row[2], code: row[3], type: row[4],
            finish: row[5], pool: row[6], hex: row[7], path: row[8], reco: row[9],
            lab: hexToLab(row[7]),
            key: (row[0] + " " + row[1] + " " + row[3] + " " + row[2]).toLowerCase()
          };
        });
        return PAINTS;
      });
    }
    return dataPromise;
  }

  /* -------------------------------- utils --------------------------------- */

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function swatchHtml(hex, metallic) {
    return '<span class="bf-swatch' + (metallic ? " bf-metallic" : "") +
        '" style="background:' + esc(hex) + '"></span>';
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, ms);
    };
  }

  /* ------------------------------ component ------------------------------- */

  function setup(root) {
    var sourceBrand = root.getAttribute("data-source-brand") || "";
    var presetTarget = root.getAttribute("data-target-brand") || "";
    var input = root.querySelector(".bfc-input");
    var drop = root.querySelector(".bfc-drop");
    var panel = root.querySelector(".bfc-panel");
    var status = root.querySelector(".bfc-status");
    var source = null;
    var targetBrand = presetTarget || "ALL";
    var dropItems = [];
    var activeIdx = -1;

    function setStatus(msg) { status.textContent = msg || ""; }

    function ensure() {
      setStatus("Loading paint database…");
      return loadData().then(function (p) { setStatus(""); return p; });
    }

    input.addEventListener("focus", function () { ensure(); }, { once: true });

    var runSearch = debounce(function () {
      var q = input.value.trim().toLowerCase();
      if (q.length < 2) { closeDrop(); return; }
      ensure().then(function (paints) {
        var starts = [], contains = [];
        for (var i = 0; i < paints.length; i++) {
          var p = paints[i];
          if (sourceBrand && p.brand !== sourceBrand) continue;
          var namePos = p.name.toLowerCase().indexOf(q);
          var keyPos = namePos >= 0 ? namePos : p.key.indexOf(q);
          if (keyPos < 0) continue;
          (namePos === 0 ? starts : contains).push(p);
          if (starts.length > 40) break;
        }
        var hits = starts.concat(contains).slice(0, 30);
        renderDrop(hits, q);
      });
    }, 300);

    input.addEventListener("input", runSearch);

    input.addEventListener("keydown", function (ev) {
      if (drop.hidden) return;
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        var n = dropItems.length;
        if (!n) return;
        activeIdx = ev.key === "ArrowDown" ? (activeIdx + 1) % n : (activeIdx - 1 + n) % n;
        dropItems.forEach(function (it, i) {
          it.classList.toggle("active", i === activeIdx);
        });
      } else if (ev.key === "Enter" || ev.key === "Return") {
        ev.preventDefault();
        var pick = activeIdx >= 0 ? dropItems[activeIdx] : dropItems[0];
        if (pick) pick.click();
      } else if (ev.key === "Escape") {
        closeDrop();
      }
    });

    document.addEventListener("click", function (ev) {
      if (!root.contains(ev.target)) closeDrop();
    });

    function closeDrop() { drop.hidden = true; drop.innerHTML = ""; dropItems = []; activeIdx = -1; }

    function renderDrop(hits, q) {
      drop.innerHTML = "";
      dropItems = []; activeIdx = -1;
      if (!hits.length) {
        drop.appendChild(el("div", "bfc-empty", "No paints found for “" + esc(q) + "”"));
        drop.hidden = false;
        return;
      }
      hits.forEach(function (p) {
        var item = el("button", "bfc-item",
            swatchHtml(p.hex, p.pool === "metallic") +
            '<span class="bfc-iname">' + esc(p.name) +
            (p.code ? ' <span class="bfc-imeta">' + esc(p.code) + "</span>" : "") + "</span>" +
            '<span class="bfc-imeta">' + esc(disp(p.brand)) + " · " + esc(p.line) + "</span>");
        item.type = "button";
        item.addEventListener("click", function () { select(p); });
        drop.appendChild(item);
        dropItems.push(item);
      });
      drop.hidden = false;
    }

    function select(p) {
      source = p;
      input.value = p.name;
      closeDrop();
      render();
    }

    function brandsAvailable() {
      var set = {};
      PAINTS.forEach(function (p) {
        if (p.reco && p.brand !== source.brand && p.pool === source.pool) set[p.brand] = 1;
      });
      return Object.keys(set).sort();
    }

    function computeMatches() {
      var rows = [];
      if (targetBrand === "ALL") {
        var bestPerBrand = {};
        PAINTS.forEach(function (p) {
          if (!p.reco || p === source || p.brand === source.brand || p.pool !== source.pool) return;
          var d = de2000(source.lab, p.lab);
          if (!bestPerBrand[p.brand] || d < bestPerBrand[p.brand].d) {
            bestPerBrand[p.brand] = { d: d, p: p };
          }
        });
        rows = Object.keys(bestPerBrand).map(function (b) { return bestPerBrand[b]; });
      } else {
        PAINTS.forEach(function (p) {
          if (!p.reco || p === source || p.brand !== targetBrand || p.pool !== source.pool) return;
          rows.push({ d: de2000(source.lab, p.lab), p: p });
        });
        rows.sort(function (a, b) { return a.d - b.d; });
        rows = rows.slice(0, 8);
      }
      rows.sort(function (a, b) { return a.d - b.d; });
      return rows;
    }

    function render() {
      var brands = brandsAvailable();
      var pills = ['<button type="button" class="bfc-pill' + (targetBrand === "ALL" ? " on" : "") +
          '" data-b="ALL">Best per brand</button>'];
      brands.forEach(function (b) {
        pills.push('<button type="button" class="bfc-pill' + (targetBrand === b ? " on" : "") +
            '" data-b="' + esc(b) + '">' + esc(disp(b)) + "</button>");
      });
      var matches = computeMatches();
      var rowsHtml = matches.map(function (m) {
        var s = deScale(m.d);
        return '<a class="bf-row" href="/paints/' + esc(m.p.path) + '.html">' +
            '<span class="bf-swatch-pair"><span style="background:' + esc(source.hex) +
            '"></span><span style="background:' + esc(m.p.hex) + '"></span></span>' +
            '<span class="grow"><span class="rname">' + esc(m.p.name) +
            (m.p.code ? " · " + esc(m.p.code) : "") + '</span><br><span class="rmeta">' +
            esc(disp(m.p.brand)) + " · " + esc(m.p.line) + " · " + esc(m.p.type) + '</span></span>' +
            '<span class="bfc-score"><span class="bf-tier ' + s[1] + '">&Delta;E ' +
            m.d.toFixed(1) + " · " + s[0] + '</span><span class="bfc-conf">' +
            Math.round(confidence(m.d) * 100) + "% confidence</span></span></a>";
      }).join("");
      if (!matches.length) {
        rowsHtml = '<div class="bfc-empty">No ' + esc(targetBrand === "ALL" ? "" : targetBrand) +
            " equivalents with reliable color data for this paint type.</div>";
      }
      panel.innerHTML =
          '<div class="bfc-source">' + swatchHtml(source.hex, source.pool === "metallic") +
          '<span><strong>' + esc(source.name) + "</strong>" +
          (source.code ? " · " + esc(source.code) : "") + '<br><span class="bfc-imeta">' +
          esc(source.brand) + " · " + esc(source.line) + " · " + esc(source.finish) +
          '</span></span></div>' +
          '<div class="bfc-pills" role="group" aria-label="Target brand">' + pills.join("") + "</div>" +
          '<div class="bf-rows">' + rowsHtml +
          '<div class="bf-tease"><span>The app ranks up to 50 matches with filters, mixing recipes ' +
          "and your own inventory, all offline.</span>" +
          '<a href="' + APP_URL + '" rel="noopener">Get BrushForge free &rarr;</a></div></div>';
      panel.hidden = false;
      panel.querySelectorAll(".bfc-pill").forEach(function (btn) {
        btn.addEventListener("click", function () {
          targetBrand = btn.getAttribute("data-b");
          render();
        });
      });
    }
  }

  function init() {
    document.querySelectorAll(".bfc").forEach(setup);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
