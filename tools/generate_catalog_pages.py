#!/usr/bin/env python3
"""Generate BrushForge catalog pages: conversion charts, paint pages, hubs, sitemaps.

Usage:
  python3 tools/generate_catalog_pages.py --sample   # 1 chart + a dozen paint pages
  python3 tools/generate_catalog_pages.py --full     # everything
Reads the Catalog Workbench DB (see tools/bfcatalog.py), writes static HTML into
the repo root (convert/, paints/, sitemap*.xml, assets/data/paints.min.json).
"""

import argparse
import html
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bfcatalog as bf

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://brushforgeapp.com"
TODAY = "2026-07-17"
TODAY_HUMAN = "17 July 2026"

PLAY_BASE = "https://play.google.com/store/apps/details?id=io.brushforge.brushforge_android_app"
IOS_URL = "https://apps.apple.com/be/app/brushforge/id6749896227"


def play_url(slot):
    ref = f"utm_source%3Dbrushforgeapp.com%26utm_medium%3Dweb%26utm_campaign%3Dcatalog%26utm_content%3D{slot}"
    return f"{PLAY_BASE}&referrer={ref}"


def esc(s):
    return html.escape(str(s), quote=True)


def fmt_de(d):
    return f"{d:.1f}"


def tier_class(de):
    return bf.de_scale(de)[1]


def brand_slug(brand):
    return bf.BRAND_SLUGS[brand]


BRAND_DISPLAY = {"Monument Hobbies": "Pro Acryl"}


def disp(brand):
    return BRAND_DISPLAY.get(brand, brand)

# --------------------------------------------------------------- html shell

HEAD_CSP = ('<meta http-equiv="Content-Security-Policy" content="default-src \'self\'; '
            "img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'\">")


def shell(*, title, desc, canonical, body, schemas=(), active="", scripts=()):
    scripts_html = "".join(f'<script defer src="{s}"></script>' for s in scripts)
    schema_html = "".join(
        f'<script type="application/ld+json">{json.dumps(s, ensure_ascii=False)}</script>'
        for s in schemas)
    nav = [
        ("/", "Home", "home"),
        ("/convert/", "Conversion Charts", "charts"),
        ("/paints/", "All Paints", "paints"),
        ("/support.html", "Support", "support"),
    ]
    active_style = ' style="color:var(--accent);"'
    nav_html = "".join(
        f'<a href="{href}"{active_style if key == active else ""}>{label}</a>'
        for href, label, key in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b0d10">
{HEAD_CSP}
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="icon" href="/assets/images/logo.jpg" sizes="any">
<link rel="apple-touch-icon" href="/assets/images/logo.jpg">
<meta name="apple-itunes-app" content="app-id=6749896227">
<link rel="canonical" href="{canonical}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="BrushForge">
<meta property="og:image" content="{SITE}/assets/images/match-overview.png">
<meta name="twitter:card" content="summary">
{schema_html}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Eczar:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/assets/css/site.css">
<link rel="stylesheet" href="/assets/css/catalog.css">
{scripts_html}
</head>
<body>
<header class="header"><div class="container nav">
<a href="/" class="brand"><img src="/assets/images/logo.jpg" class="logo" alt="BrushForge logo"><span>BrushForge</span></a>
<nav class="navlinks">{nav_html}<a href="/#get-app" class="btn primary">Get the App</a></nav>
</div></header>
<main class="bf-main">
{body}
</main>
<footer class="footer"><div class="container footer-inner">
<div class="brand"><img src="/assets/images/logo.jpg" class="logo" alt="BrushForge logo"><span>BrushForge</span></div>
<div class="footer-links">
<a href="/convert/">Conversion Charts</a><a href="/paints/">All Paints</a><a href="/about.html">About</a>
<a href="/privacy.html">Privacy</a><a href="/terms.html">Terms</a><a href="/support.html">Support</a>
</div>
<div class="small">&copy; 2026 BrushForge. Paint names are trademarks of their respective owners; BrushForge is not affiliated with any paint manufacturer or Games Workshop.</div>
</div></footer>
</body>
</html>"""


def crumbs(items):
    out = ['<nav class="bf-crumbs" aria-label="Breadcrumb">']
    for i, (label, href) in enumerate(items):
        if i:
            out.append('<span class="sep">/</span>')
        if href:
            out.append(f'<a href="{href}">{esc(label)}</a>')
        else:
            out.append(f'<span class="here">{esc(label)}</span>')
    out.append("</nav>")
    return "".join(out)


def breadcrumb_schema(items, canonical):
    return {
        "@context": "https://schema.org", "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label,
             "item": (SITE + href) if href else canonical}
            for i, (label, href) in enumerate(items)],
    }


def faq_schema(qas):
    return {
        "@context": "https://schema.org", "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in qas],
    }


def faq_html(qas):
    body = "".join(
        f"<details><summary>{esc(q)}</summary><div class=\"a\">{esc(a)}</div></details>"
        for q, a in qas)
    return f'<h2 class="bf-h2">Frequently asked questions</h2><div class="bf-faq">{body}</div>'


def cta_band(slot, heading, sub):
    return f"""<section class="bf-cta">
<div><h3>{esc(heading)}</h3><p>{esc(sub)}</p>
<div class="bf-proof"><span class="stars">★★★★★</span> Rated 4.9 on the App Store &middot; 4,300+ paints &middot; free to start</div></div>
<div class="actions">
<a class="btn primary" href="{play_url(slot)}" rel="noopener">Get it on Android</a>
<a class="btn" href="{IOS_URL}" rel="noopener">Download for iOS</a>
</div></section>"""


def converter_section(source_brand=None, target_brand=None):
    attrs = ""
    if source_brand:
        attrs += f' data-source-brand="{esc(source_brand)}"'
    if target_brand:
        attrs += f' data-target-brand="{esc(target_brand)}"'
    if source_brand:
        ph = f"Search a {esc(disp(source_brand))} paint by name or code…"
        sub = (f"Type any {esc(disp(source_brand))} paint and get the closest "
               f"{esc(disp(target_brand)) if target_brand else 'cross-brand'} matches instantly, "
               "using the same ΔE2000 engine as the app.")
    else:
        ph = "Search 2,900+ paints by name, code or brand…"
        sub = "Pick any paint, get the closest match in every brand instantly, using the same ΔE2000 engine as the app."
    return f"""<section class="bfc"{attrs}>
<h2 class="bfc-title">Instant converter</h2>
<p class="bfc-sub">{sub}</p>
<div class="bfc-wrap">
<label class="sr-only" for="bfc-q" style="position:absolute;left:-9999px;">Search paints</label>
<input class="bfc-input" id="bfc-q" type="search" autocomplete="off" spellcheck="false" placeholder="{ph}">
<div class="bfc-drop" hidden></div>
</div>
<div class="bfc-status" aria-live="polite"></div>
<div class="bfc-panel" hidden></div>
<noscript><p class="bfc-sub">The instant converter needs JavaScript. No problem: the chart below works everywhere.</p></noscript>
</section>"""


def legend():
    return ('<div class="bf-legend"><b>ΔE2000 color distance:</b>'
            '<span><span class="bf-de excellent">0-2</span> nearly identical</span>'
            '<span><span class="bf-de good">2-5</span> close match</span>'
            '<span><span class="bf-de fair">6-10</span> noticeable difference</span>'
            '<span><span class="bf-de poor">10+</span> different color</span></div>'
            '<p class="bf-disclaimer"><b>Screen preview:</b> paint swatches on screen are '
            'approximate: finish, lighting, night-mode filters and display calibration all '
            'change what you see. Use them to compare relative differences, then confirm with '
            'the physical paint when finish and final appearance matter.</p>')


def swatch(hexcolor, metallic=False, size=""):
    cls = "bf-swatch" + (" bf-metallic" if metallic else "")
    return f'<span class="{cls}" style="background:{hexcolor}"></span>'


def paint_url(p):
    return f"/paints/{brand_slug(p['brand'])}/{p['slug']}.html"


def paint_line_label(p):
    line = p["line"]
    if p["line_variant"]:
        line += f" {p['line_variant']}"
    return line

# ------------------------------------------------------------- precompute

def precompute(paints):
    """For every paint: best equivalent per other brand, 6 similar, hl/sh, complementary."""
    t0 = time.time()
    brands = sorted({p["brand"] for p in paints})
    reco_by_pool = defaultdict(list)
    for p in paints:
        if bf.recommendable(p):
            reco_by_pool[p["pool"]].append(p)
    all_by_pool = defaultdict(list)
    for p in paints:
        all_by_pool[p["pool"]].append(p)

    results = {}
    for i, src in enumerate(paints):
        pool_cands = reco_by_pool[src["pool"]]
        d76 = [(bf.de76(src["lab"], c["lab"]), c) for c in pool_cands if c is not src]
        # equivalents: refine top candidates per brand with ΔE2000
        per_brand = defaultdict(list)
        for d, c in d76:
            per_brand[c["brand"]].append((d, c))
        equivalents = []
        for b in brands:
            if b == src["brand"]:
                continue
            cands = sorted(per_brand.get(b, []), key=lambda t: t[0])[:25]
            best, best_d = None, None
            for _, c in cands:
                d = bf.de2000(src["lab"], c["lab"])
                if best_d is None or d < best_d:
                    best, best_d = c, d
            if best:
                equivalents.append((best_d, best))
        equivalents.sort(key=lambda t: t[0])
        # similar: 6 nearest by ΔE76 in same pool, any brand incl. own (app behavior)
        sim_all = sorted(
            ((bf.de76(src["lab"], c["lab"]), c) for c in all_by_pool[src["pool"]] if c is not src),
            key=lambda t: t[0])[:6]
        entry = {"equivalents": equivalents, "similar": sim_all,
                 "highlight": None, "shadow": None, "hl_hex": None, "sh_hex": None,
                 "complementary": []}
        if src["pool"] == "standard":
            entry["hl_hex"] = bf.synth_highlight(src["hex"])
            entry["sh_hex"] = bf.synth_shadow(src["hex"])
            entry["highlight"] = bf.nearest_value_shift(src, entry["hl_hex"], pool_cands, "highlight")
            entry["shadow"] = bf.nearest_value_shift(src, entry["sh_hex"], pool_cands, "shadow")
            entry["complementary"] = bf.complementary(src, pool_cands)
        results[id(src)] = entry
        if (i + 1) % 500 == 0:
            print(f"  precompute {i + 1}/{len(paints)} ({time.time() - t0:.0f}s)")
    print(f"  precompute done in {time.time() - t0:.0f}s")
    return results

# ------------------------------------------------------------- chart pages

def chart_page(src_brand, dst_brand, paints, pre):
    a, b = src_brand, dst_brand
    ad, bd = disp(a), disp(b)
    a_slug, b_slug = brand_slug(a), brand_slug(b)
    url_path = f"/convert/{a_slug}-to-{b_slug}.html"
    canonical = SITE + url_path

    sections = []  # (pool, line, rows)
    by_pool_line = defaultdict(list)
    for p in paints:
        if p["brand"] != a or not bf.recommendable(p):
            continue
        best = None
        for d, c in pre[id(p)]["equivalents"]:
            if c["brand"] == b:
                best = (d, c)
                break
        by_pool_line[(p["pool"], p["line"])].append((p, best))
    pool_order = {"standard": 0, "metallic": 1, "wash": 2}
    keys = sorted(by_pool_line, key=lambda k: (pool_order[k[0]], k[1]))

    matched = [(p, m) for rows in by_pool_line.values() for p, m in rows if m]
    total = sum(len(v) for v in by_pool_line.values())
    des = [m[0] for _, m in matched]
    pct2 = round(100 * sum(1 for d in des if d <= 2) / len(des)) if des else 0
    pct5 = round(100 * sum(1 for d in des if d <= 5) / len(des)) if des else 0
    avg = sum(des) / len(des) if des else 0

    toc, tables = [], []
    for pool, line in keys:
        rows = sorted(by_pool_line[(pool, line)], key=lambda t: t[0]["name"])
        anchor = f"{pool}-{bf.slugify(line)}"
        label = f"{ad} {line}" + (" (metallic)" if pool == "metallic" else "")
        toc.append(f'<a href="#{anchor}">{esc(label)} ({len(rows)})</a>')
        trs = []
        for p, best in rows:
            left = (f'<a class="name" href="{paint_url(p)}">{swatch(p["hex"], p["pool"] == "metallic")}'
                    f'{esc(p["name"])}</a>'
                    + (f' <span class="meta">{esc(p["code"])}</span>' if p["code"] else ""))
            if best:
                d, c = best
                right = (f'<a class="name" href="{paint_url(c)}">{swatch(c["hex"], c["pool"] == "metallic")}'
                         f'{esc(c["name"])}</a>'
                         + (f' <span class="meta">{esc(c["code"])}</span>' if c["code"] else ""))
                meta = esc(paint_line_label(c))
                decell = f'<span class="bf-de {tier_class(d)}">{fmt_de(d)}</span>'
            else:
                right, meta, decell = '<span class="meta">no close equivalent</span>', "&middot;", "&middot;"
            trs.append(f"<tr><td>{left}</td><td>{right}</td>"
                       f'<td class="meta">{meta}</td><td class="num">{decell}</td></tr>')
        tables.append(
            f'<h2 class="bf-h2" id="{anchor}">{esc(label)}<span class="count">{len(rows)} paints</span></h2>'
            f'<div class="bf-tablewrap"><table class="bf-table">'
            f"<thead><tr><th>{esc(ad)} paint</th><th>Closest {esc(bd)} equivalent</th>"
            f'<th>Range</th><th class="num">&Delta;E2000</th></tr></thead>'
            f"<tbody>{''.join(trs)}</tbody></table></div>")

    qas = [
        (f"Can I use {bd} paints instead of {ad}?",
         f"Yes. This chart lists the closest {bd} equivalent for every {ad} paint in the BrushForge "
         f"database, scored with the ΔE2000 color-difference formula. A ΔE below 2 is practically "
         f"indistinguishable on a miniature, and below 5 reads the same on the tabletop. "
         f"{pct5}% of {ad} paints here have a {bd} equivalent with ΔE 5 or less."),
        ("How accurate is this chart?",
         "Matches are computed in LAB color space with the industry-standard CIEDE2000 formula, the "
         "same engine the BrushForge app uses. Metallics are only matched to metallics, and washes "
         "to washes. Colors shown are screen approximations of real paint."),
        ("What does the ΔE number mean?",
         "ΔE2000 measures how different two colors look to the human eye. 0-2: nearly identical. "
         "2-5: close match. 6-10: noticeable difference. Above 10: a different color. "
         "Aim for ΔE below 5 for a solid substitute."),
        ("Why is a paint missing from this chart?",
         "This chart lists brush-on, metallic and wash paints with verified color data. Airbrush "
         "lines, sprays, primers and technical products are not shown on the web. The BrushForge "
         "app carries the full database of 4,300+ paints, including those ranges, and it grows "
         "with every update."),
    ]
    crumb_items = [("Home", "/"), ("Conversion charts", "/convert/"), (f"{ad} to {bd}", None)]
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"{ad} to {bd} paint conversion chart",
        "description": f"Closest {bd} equivalent for {total} {ad} miniature paints, "
                       f"matched with CIEDE2000 color distance.",
        "url": canonical, "dateModified": TODAY, "license": f"{SITE}/terms.html",
        "creator": {"@type": "Organization", "name": "BrushForge", "url": SITE},
    }
    body = f"""{crumbs(crumb_items)}
<div class="bf-hero"><div>
<h1>{esc(ad)} to {esc(bd)} conversion chart</h1>
<p class="sub">The closest {esc(bd)} equivalent for every {esc(ad)} paint: {total} paints matched
with ΔE2000 color science, the same engine as the BrushForge app.</p>
<p class="bf-updated">Updated {TODAY_HUMAN} &middot; BrushForge paint database</p>
</div></div>
<p class="bf-updated">Charts cover brush-on, metallic and wash paints. Airbrush ranges and sprays are
in the BrushForge app (4,300+ paints in total, updated continuously).</p>
{converter_section(a, b)}
<div class="bf-stats">
<div class="bf-stat"><div class="n">{total}</div><div class="l">{esc(ad)} paints matched</div></div>
<div class="bf-stat"><div class="n">{pct2}%</div><div class="l">nearly identical (&Delta;E &le; 2)</div></div>
<div class="bf-stat"><div class="n">{pct5}%</div><div class="l">close or better (&Delta;E &le; 5)</div></div>
<div class="bf-stat"><div class="n">{avg:.1f}</div><div class="l">average &Delta;E</div></div>
</div>
{legend()}
<div class="bf-toc">{''.join(toc)}</div>
{''.join(tables)}
{cta_band(f'chart-{a_slug}-to-{b_slug}',
          'Stop scrolling charts at the paint desk.',
          'The free BrushForge app looks this up in two taps, plus highlight and shadow suggestions, '
          'mixing recipes, and matching against the paints you already own. Works offline.')}
{faq_html(qas)}
<h2 class="bf-h2">Related charts</h2>
<div class="bf-related">
<a href="/convert/{b_slug}-to-{a_slug}.html">{esc(bd)} to {esc(ad)}</a>
{''.join(f'<a href="/convert/{a_slug}-to-{brand_slug(x)}.html">{esc(ad)} to {esc(disp(x))}</a>'
         for x in sorted(bf.BRAND_SLUGS) if x not in (a, b))}
</div>"""
    title = f"{ad} to {bd} Conversion Chart: every paint matched | BrushForge"
    desc = (f"Free {ad} to {bd} paint conversion chart: the closest {bd} equivalent for {total} {ad} "
            f"paints, scored with ΔE2000 color distance. {pct5}% match at ΔE ≤ 5.")
    schemas = [breadcrumb_schema(crumb_items, canonical), dataset, faq_schema(qas)]
    return url_path, shell(title=title, desc=desc, canonical=canonical, body=body,
                           schemas=schemas, active="charts",
                           scripts=("/assets/js/converter.js",))

# ------------------------------------------------------------- paint pages

def paint_page(p, pre_entry, chart_brands):
    canonical = SITE + paint_url(p)
    b_slug = brand_slug(p["brand"])
    crumb_items = [("Home", "/"), ("Paints", "/paints/"), (disp(p["brand"]), f"/paints/{b_slug}/"),
                   (p["name"], None)]
    equivalents = pre_entry["equivalents"]
    similar = pre_entry["similar"]

    equiv_cards = []
    for d, c in equivalents:
        label, tier = bf.de_scale(d)
        equiv_cards.append(f"""<a class="bf-card" href="{paint_url(c)}">
<div class="brandline">{esc(disp(c['brand']))}</div>
<div class="bf-swatch-pair"><span style="background:{p['hex']}"></span><span style="background:{c['hex']}"></span></div>
<div class="pname">{esc(c['name'])}{f' <span class="pmeta">{esc(c["code"])}</span>' if c['code'] else ''}</div>
<div class="pmeta">{esc(paint_line_label(c))}</div>
<div class="foot"><span class="bf-tier {tier}">&Delta;E {fmt_de(d)} &middot; {esc(label)}</span></div>
</a>""")

    sim_rows = []
    for d, c in similar[:3]:
        sim_rows.append(f"""<a class="bf-row" href="{paint_url(c)}">
{swatch(c['hex'], c['pool'] == 'metallic')}
<div class="grow"><div class="rname">{esc(c['name'])}{f' &middot; {esc(c["code"])}' if c['code'] else ''}</div>
<div class="rmeta">{esc(disp(c['brand']))} &middot; {esc(paint_line_label(c))}</div></div>
<span class="bf-tier {tier_class(d)}">{esc(bf.similar_label(d))}</span>
</a>""")
    hidden = len(similar) - 3
    sim_tease = (f'<div class="bf-tease"><span>{hidden} more similar paints, ranked live against '
                 f'your own collection.</span><a href="{play_url("similar-tease")}" rel="noopener">'
                 f"See them in the app &rarr;</a></div>") if hidden > 0 else ""

    hl, sh = pre_entry["highlight"], pre_entry["shadow"]
    hlsh_html = ""
    if hl or sh:
        cards = []
        for kind, target_hex, m in (("Highlight", pre_entry["hl_hex"], hl),
                                    ("Shadow", pre_entry["sh_hex"], sh)):
            if not m:
                continue
            cards.append(f"""<a class="bf-card" href="{paint_url(m)}">
<div class="brandline">{kind} &middot; step 1 of 2</div>
<div class="bf-swatch-pair"><span style="background:{p['hex']}"></span><span style="background:{m['hex']}"></span></div>
<div class="pname">{esc(m['name'])}{f' <span class="pmeta">{esc(m["code"])}</span>' if m['code'] else ''}</div>
<div class="pmeta">{esc(disp(m['brand']))} &middot; {esc(paint_line_label(m))}</div>
<div class="foot"><span class="bf-chip">target <span class="bf-swatch" style="background:{target_hex}"></span></span></div>
</a>""")
        if cards:
            hlsh_html = f"""<h2 class="bf-h2">Highlight &amp; shadow paints</h2>
<p class="bf-sectionsub">Real paints closest to the ideal first highlight and shadow for
{esc(p['name'])}, using the layering model from the BrushForge app.</p>
<div class="bf-grid">{''.join(cards)}</div>
<div class="bf-tease"><span>The app adds a second, stronger step, a wash &amp; glaze mode, and can
pick highlights from the paints you already own.</span>
<a href="{play_url('hlsh-tease')}" rel="noopener">Open in the app &rarr;</a></div>"""

    comp = pre_entry["complementary"]
    comp_html = ""
    if comp:
        chips = "".join(
            f'<a class="bf-row" href="{paint_url(c)}">{swatch(c["hex"])}'
            f'<div class="grow"><div class="rname">{esc(c["name"])}</div>'
            f'<div class="rmeta">{esc(disp(c["brand"]))} &middot; {esc(paint_line_label(c))}</div></div></a>'
            for c in comp)
        comp_html = f"""<h2 class="bf-h2">Complementary paints</h2>
<p class="bf-sectionsub">Opposite-hue paints that make {esc(p['name'])} pop. Great for basing,
freehand, or contrast details.</p>
<div class="bf-rows">{chips}
<div class="bf-tease"><span>The full harmony wheel with split-complementary, triadic, analogous, and
warm/cool variants lives in the app.</span>
<a href="{play_url('harmony-tease')}" rel="noopener">Explore it free &rarr;</a></div></div>"""

    top = equivalents[0] if equivalents else None
    pool_word = {"standard": "standard", "metallic": "metallic", "wash": "translucent"}[p["pool"]]
    qas = [(f"What color is {p['name']}?",
            f"{p['name']} is a {pool_word} {p['family'].lower()} miniature paint "
            f"from {disp(p['brand'])} ({paint_line_label(p)})"
            + (f", code {p['code']}" if p["code"] else "")
            + f". Its screen color is approximately {p['hex']} with a {p['finish']} finish.")]
    if top:
        d, c = top
        qas.insert(0, (
            f"What is the {disp(c['brand'])} equivalent of {p['name']}?",
            f"The closest {disp(c['brand'])} match for {disp(p['brand'])} {p['name']} is {c['name']}"
            + (f" ({c['code']}, {paint_line_label(c)})" if c["code"] else f" ({paint_line_label(c)})")
            + f" with a ΔE2000 distance of {fmt_de(d)} ({bf.de_scale(d)[0]})."))

    charts_for_brand = "".join(
        f'<a href="/convert/{b_slug}-to-{brand_slug(x)}.html">{esc(disp(p["brand"]))} to {esc(disp(x))} chart</a>'
        for x in chart_brands if x != p["brand"])

    body = f"""{crumbs(crumb_items)}
<div class="bf-hero">
<span class="bf-swatch-xl{' bf-metallic' if p['pool'] == 'metallic' else ''}" style="background:{p['hex']}"></span>
<div><h1>{esc(p['name'])}: equivalents &amp; matches</h1>
<p class="sub">{esc(disp(p['brand']))} &middot; {esc(paint_line_label(p))}{f" &middot; {esc(p['code'])}" if p['code'] else ''}.
The closest match in every major brand, plus highlight, shadow and complement picks, computed
with the BrushForge color engine.</p>
<div class="bf-chips">
<span class="bf-chip">hex <strong>{p['hex']}</strong></span>
<span class="bf-chip">finish <strong>{esc(p['finish'])}</strong></span>
<span class="bf-chip">type <strong>{esc(p['type'])}</strong></span>
<span class="bf-chip">family <strong>{esc(p['family'])}</strong></span>
</div>
<p class="bf-updated">Updated {TODAY_HUMAN}</p>
</div></div>
<h2 class="bf-h2">Closest equivalents in other brands</h2>
{legend()}
<div class="bf-grid">{''.join(equiv_cards)}</div>
<h2 class="bf-h2">Similar paints</h2>
<div class="bf-rows">{''.join(sim_rows)}{sim_tease}</div>
{hlsh_html}
{comp_html}
{cta_band(f'paint-{b_slug}',
          f"Own {p['name']}? Put it in your pocket inventory.",
          'BrushForge tracks your paints, warns before bottles run dry, and matches recipes to what '
          'you actually own. Free, offline-first, no account needed to start.')}
{faq_html(qas)}
<h2 class="bf-h2">Keep exploring</h2>
<div class="bf-related">
<a href="/paints/{b_slug}/">All {esc(disp(p['brand']))} paints</a>
{charts_for_brand}
</div>"""
    title = f"{p['name']} ({disp(p['brand'])}) equivalents in every brand | BrushForge"
    d_top = f" Closest match: {disp(top[1]['brand'])} {top[1]['name']} (ΔE {fmt_de(top[0])})." if top else ""
    desc = (f"{disp(p['brand'])} {p['name']}{' ' + p['code'] if p['code'] else ''}: cross-brand paint "
            f"equivalents, similar colors, highlight & shadow picks.{d_top}")
    schemas = [breadcrumb_schema(crumb_items, canonical), faq_schema(qas)]
    return paint_url(p), shell(title=title, desc=desc, canonical=canonical, body=body,
                               schemas=schemas, active="paints")

# ---------------------------------------------------------------- hub pages

def brand_hub(brand, paints):
    b_slug = brand_slug(brand)
    url_path = f"/paints/{b_slug}/"
    canonical = SITE + url_path
    mine = sorted((p for p in paints if p["brand"] == brand), key=lambda p: (p["line"], p["name"]))
    by_line = defaultdict(list)
    for p in mine:
        by_line[p["line"]].append(p)
    toc = "".join(f'<a href="#{bf.slugify(line)}">{esc(line)} ({len(ps)})</a>'
                  for line, ps in sorted(by_line.items()))
    sections = []
    for line, ps in sorted(by_line.items()):
        rows = "".join(
            f'<a class="bf-row" href="{paint_url(p)}">{swatch(p["hex"], p["pool"] == "metallic")}'
            f'<div class="grow"><div class="rname">{esc(p["name"])}'
            + (f' &middot; {esc(p["code"])}' if p["code"] else "")
            + f'</div><div class="rmeta">{esc(p["type"])} &middot; {esc(p["finish"])}</div></div></a>'
            for p in ps)
        sections.append(f'<h2 class="bf-h2" id="{bf.slugify(line)}">{esc(line)}'
                        f'<span class="count">{len(ps)} paints</span></h2>'
                        f'<div class="bf-rows">{rows}</div>')
    crumb_items = [("Home", "/"), ("Paints", "/paints/"), (disp(brand), None)]
    body = f"""{crumbs(crumb_items)}
<div class="bf-hero"><div>
<h1>{esc(disp(brand))} paints: full database</h1>
<p class="sub">{len(mine)} {esc(disp(brand))} paints with cross-brand equivalents, similar colors and
highlight/shadow picks on every page.</p>
<p class="bf-updated">Updated {TODAY_HUMAN} &middot; brush-on, metallic and wash ranges. The
BrushForge app also covers airbrush and spray lines (4,300+ paints in total).</p>
</div></div>
<div class="bf-toc">{toc}</div>
{''.join(sections)}
{cta_band(f'hub-{b_slug}', 'Your whole paint rack, searchable.',
          'Track which of these you own, find gaps in your collection, and convert to any brand, free in the BrushForge app.')}"""
    title = f"{disp(brand)} Paint Database: every color, with equivalents | BrushForge"
    desc = (f"Browse all {len(mine)} {disp(brand)} miniature paints: color swatches, codes, and the "
            f"closest equivalents in Vallejo, Citadel, Army Painter, AK and more.")
    return url_path + "index.html", shell(title=title, desc=desc, canonical=canonical,
                                          body=body, schemas=[breadcrumb_schema(crumb_items, canonical)],
                                          active="paints")


def paints_index(paints):
    canonical = SITE + "/paints/"
    counts = defaultdict(int)
    for p in paints:
        counts[p["brand"]] += 1
    cards = "".join(
        f'<a class="bf-card" href="/paints/{brand_slug(b)}/">'
        f'<div class="brandline">{esc(disp(b))}</div>'
        f'<div class="pname">{counts[b]} paints</div>'
        f'<div class="pmeta">swatches, codes &amp; equivalents</div></a>'
        for b in sorted(counts))
    crumb_items = [("Home", "/"), ("Paints", None)]
    body = f"""{crumbs(crumb_items)}
<div class="bf-hero"><div>
<h1>The miniature paint database</h1>
<p class="sub">{sum(counts.values())} paints across {len(counts)} brands. Every page shows the
closest equivalent in each other brand, similar colors, and highlight &amp; shadow picks,
powered by the BrushForge ΔE2000 color engine.</p>
<p class="bf-updated">Updated {TODAY_HUMAN} &middot; the site lists brush-on, metallic and wash
paints; the full app database is larger (4,300+ paints including airbrush lines, sprays and
primers) and keeps growing.</p>
</div></div>
<div class="bf-hubgrid">{cards}</div>
<h2 class="bf-h2">Conversion charts</h2>
<p class="bf-sectionsub">Prefer a full side-by-side list? Every brand pair has a dedicated chart.</p>
<div class="bf-related"><a href="/convert/">Browse all conversion charts &rarr;</a></div>
{cta_band('paints-index', 'The full database fits in your pocket.',
          'Convert, track and organize your paints offline with the free BrushForge app.')}"""
    title = "Miniature Paint Database: 2,900+ paints, all brands | BrushForge"
    desc = ("Free database of 2,900+ miniature paints from Citadel, Vallejo, Army Painter, AK, "
            "Scale75, Pro Acryl and more, with cross-brand equivalents for every color.")
    return "/paints/index.html", shell(title=title, desc=desc, canonical=canonical, body=body,
                                       schemas=[breadcrumb_schema(crumb_items, canonical)], active="paints")


def convert_index(chart_paths):
    canonical = SITE + "/convert/"
    by_src = defaultdict(list)
    for a, b, path in chart_paths:
        by_src[a].append((b, path))
    sections = []
    for a in sorted(by_src):
        links = "".join(f'<a href="{path}">{esc(disp(a))} to {esc(disp(b))}</a>'
                        for b, path in sorted(by_src[a]))
        sections.append(f'<h2 class="bf-h2">{esc(disp(a))}</h2><div class="bf-related">{links}</div>')
    crumb_items = [("Home", "/"), ("Conversion charts", None)]
    body = f"""{crumbs(crumb_items)}
<div class="bf-hero"><div>
<h1>Paint conversion charts</h1>
<p class="sub">Free brand-to-brand equivalence charts for miniature paints, matched with ΔE2000
color science: Citadel, Vallejo, Army Painter, AK Interactive, Scale75, Pro Acryl,
Two Thin Coats and Kimera.</p>
<p class="bf-updated">Updated {TODAY_HUMAN}</p>
</div></div>
{converter_section()}
<h2 class="bf-h2">All charts by brand</h2>
{''.join(sections)}
{cta_band('convert-index', 'Charts are handy. The converter is instant.',
          'Search any of 4,300+ paints and convert to any brand in two taps. Free and offline in the BrushForge app.')}"""
    title = "Miniature Paint Conversion Charts: all brands | BrushForge"
    desc = ("Free paint conversion charts for every brand pair: Citadel to Vallejo, Army Painter, "
            "AK, Scale75 and more. ΔE2000-matched equivalents for 2,600+ paints.")
    return "/convert/index.html", shell(title=title, desc=desc, canonical=canonical, body=body,
                                        schemas=[breadcrumb_schema(crumb_items, canonical)],
                                        active="charts", scripts=("/assets/js/converter.js",))

# ---------------------------------------------------------------- sitemaps

def write_sitemaps(paths_by_shard):
    index_entries = []
    for shard, paths in paths_by_shard.items():
        fname = f"sitemap-{shard}.xml"
        urls = "".join(f"<url><loc>{SITE}{p}</loc><lastmod>{TODAY}</lastmod></url>"
                       for p in paths)
        (ROOT / fname).write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"{urls}</urlset>\n")
        index_entries.append(f"<sitemap><loc>{SITE}/{fname}</loc><lastmod>{TODAY}</lastmod></sitemap>")
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(index_entries)}</sitemapindex>\n")

# ------------------------------------------------------------------- main

def clean_url(path):
    """/paints/citadel/index.html -> /paints/citadel/ for sitemap purposes."""
    return path[:-len("index.html")] if path.endswith("index.html") else path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=bf.DEFAULT_DB)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    if not (args.sample or args.full):
        ap.error("pass --sample or --full")

    print("loading catalog…")
    paints, skipped = bf.load_catalog(args.db)
    brands = sorted({p["brand"] for p in paints})
    print(f"  {len(paints)} paints, {len(brands)} brands")

    if args.sample:
        chart_pairs = [("Citadel", "Vallejo")]
        sample_chart_sources = [p for p in paints if p["brand"] == "Citadel"
                                and p["line"] == "Base" and p["pool"] == "standard"]
        page_paints = sample_chart_sources[:12]
    else:
        chart_pairs = [(a, b) for a in brands for b in brands if a != b]
        page_paints = paints

    print("precomputing matches…")
    pre = precompute(paints)

    written = []
    def emit(path, content):
        out = ROOT / path.lstrip("/")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content)
        written.append(path)

    print("writing chart pages…")
    chart_paths = []
    for a, b in chart_pairs:
        path, content = chart_page(a, b, paints, pre)
        emit(path, content)
        chart_paths.append((a, b, path))

    print("writing paint pages…")
    for i, p in enumerate(page_paints):
        path, content = paint_page(p, pre[id(p)], brands)
        emit(path, content)
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{len(page_paints)}")

    print("writing hubs…")
    for b in (brands if args.full else ["Citadel"]):
        path, content = brand_hub(b, paints if args.full else page_paints)
        emit(path, content)
    path, content = paints_index(paints if args.full else page_paints)
    emit(path, content)
    path, content = convert_index(chart_paths)
    emit(path, content)

    print("writing converter data…")
    data = [[p["name"], p["brand"], paint_line_label(p), p["code"], p["type"], p["finish"],
             p["pool"], p["hex"], f"{brand_slug(p['brand'])}/{p['slug']}",
             1 if bf.recommendable(p) else 0] for p in paints]
    (ROOT / "assets/data").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets/data/paints.min.json").write_text(
        json.dumps({"updated": TODAY, "fields": ["name", "brand", "line", "code", "type",
                                                 "finish", "pool", "hex", "path", "reco"],
                    "paints": data}, ensure_ascii=False, separators=(",", ":")))

    if args.full:
        core = ["/", "/about.html", "/the-story.html", "/support.html", "/privacy.html",
                "/terms.html", "/legal.html"]
        shards = {"core": core,
                  "charts": [clean_url(p) for _, _, p in chart_paths] + ["/convert/"],
                  }
        by_brand_paths = defaultdict(list)
        for p in paints:
            by_brand_paths[brand_slug(p["brand"])].append(paint_url(p))
        for b_slug, paths in by_brand_paths.items():
            shards[f"paints-{b_slug}"] = [f"/paints/{b_slug}/"] + sorted(paths)
        shards["paints-index"] = ["/paints/"]
        write_sitemaps(shards)
        print(f"  sitemap index + {len(shards)} shards")

    log = ROOT / "tools/build-log.txt"
    with log.open("w") as f:
        f.write(f"BrushForge catalog build — {TODAY}\n")
        f.write(f"mode: {'full' if args.full else 'sample'}\n")
        f.write(f"pages written: {len(written)}\n")
        f.write(f"paints in DB considered: {len(paints)}\n\n")
        for key, items in skipped.items():
            f.write(f"[{key}] {len(items)}\n")
            for it in items:
                f.write(f"  - {it}\n")
            f.write("\n")
    print(f"done: {len(written)} pages. log: tools/build-log.txt")


if __name__ == "__main__":
    main()
