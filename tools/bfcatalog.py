"""BrushForge catalog data + color-matching engine for the website generator.

Ports the matching behavior of the Android app so web pages and app agree:
  - sRGB -> LAB (D65) and CIEDE2000/CIE76 distances   (app: ColorMath.kt)
  - finish groups: metallic / translucent / standard  (app: FindSimilarPaintsUseCase.finishGroup)
  - converter quality tiers and confidence formula    (app: PaintMatch.kt)
  - similar-paints labels on DeltaE76                 (app: PaintDetailViewModel.confidenceForDelta)
  - highlight/shadow synthesis + nearest real paint   (app: ColorHarmony.kt, GetColorRecommendationsUseCase.kt)
Reads the catalog from the Catalog Workbench SQLite DB (library_paints).
"""

import json
import math
import re
import sqlite3
from pathlib import Path

DEFAULT_DB = "/Users/bas/Desktop/Brushforge/PaintGit 2.0/.workbench-data/workbench.db"

# ---------------------------------------------------------------- color math

def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def srgb_to_lab(r, g, b):
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    X = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    Y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    Z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    def f(t):
        return t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29
    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de76(lab1, lab2):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(lab1, lab2)))


def de2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1 = math.hypot(a1, b1)
    C2 = math.hypot(a2, b2)
    Cbar = (C1 + C2) / 2
    G = 0.5 * (1 - math.sqrt(Cbar ** 7 / (Cbar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    def hp(a, b):
        if a == 0 and b == 0:
            return 0.0
        h = math.degrees(math.atan2(b, a))
        return h + 360 if h < 0 else h
    h1p, h2p = hp(a1p, b1), hp(a2p, b2)
    dLp = L2 - L1
    dCp = C2p - C1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dhp) / 2)
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * math.cos(math.radians(hbp - 30)) + 0.24 * math.cos(math.radians(2 * hbp))
         + 0.32 * math.cos(math.radians(3 * hbp + 6)) - 0.20 * math.cos(math.radians(4 * hbp - 63)))
    dTheta = 30 * math.exp(-(((hbp - 275) / 25) ** 2))
    RC = 2 * math.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    SL = 1 + 0.015 * (Lbp - 50) ** 2 / math.sqrt(20 + (Lbp - 50) ** 2)
    SC = 1 + 0.045 * Cbp
    SH = 1 + 0.015 * Cbp * T
    RT = -math.sin(math.radians(2 * dTheta)) * RC
    return math.sqrt((dLp / SL) ** 2 + (dCp / SC) ** 2 + (dHp / SH) ** 2 + RT * (dCp / SC) * (dHp / SH))


def rgb_to_hsl(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, s, l


def hsl_to_hex(h, s, l):
    h = (h % 360) / 360.0
    def hue(p, q, t):
        t = t % 1.0
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p
    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r, g, b = hue(p, q, h + 1 / 3), hue(p, q, h), hue(p, q, h - 1 / 3)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def rgb_to_hsv(r, g, b):
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx
    d = mx - mn
    s = 0 if mx == 0 else d / mx
    if d == 0:
        h = 0
    elif mx == r:
        h = 60 * (((g - b) / d) % 6)
    elif mx == g:
        h = 60 * ((b - r) / d + 2)
    else:
        h = 60 * ((r - g) / d + 4)
    return h, s, v


def color_family(r, g, b):
    """Approximation of the app's HSV color-family classifier (11 families)."""
    h, s, v = rgb_to_hsv(r, g, b)
    if v < 0.1:
        return "Black"
    if s < 0.12 and v > 0.9:
        return "White"
    if s < 0.12:
        return "Grey"
    if h < 15 or h >= 345:
        fam = "Red"
    elif h < 45:
        fam = "Orange"
    elif h < 70:
        fam = "Yellow"
    elif h < 170:
        fam = "Green"
    elif h < 255:
        fam = "Blue"
    elif h < 290:
        fam = "Purple"
    else:
        fam = "Pink"
    if fam in ("Red", "Orange", "Yellow") and v < 0.62 and s < 0.85:
        return "Brown"
    return fam

# ------------------------------------------------------------- tier wording

def confidence(de):
    """App formula: confidence = 1 - deltaE/50, clamped to [0, 1]."""
    return max(0.0, min(1.0, 1.0 - de / 50.0))


def match_quality(de):
    """Converter result labels (PaintMatch.kt)."""
    c = confidence(de)
    if c >= 0.9 and de <= 5.0:
        return "Excellent Match", "excellent"
    if c >= 0.7 and de <= 15.0:
        return "Good Match", "good"
    if c >= 0.5:
        return "Fair Match", "fair"
    return "Poor Match", "poor"


def de_scale(de):
    """The app's ΔE reference scale wording (MatchingInfoSheet.kt)."""
    if de < 0.5:
        return "identical", "excellent"
    if de <= 2.0:
        return "nearly identical", "excellent"
    if de <= 5.0:
        return "close match", "good"
    if de <= 10.0:
        return "noticeable difference", "fair"
    return "different color", "poor"


def similar_label(d76):
    """Similar-paints labels (PaintDetailViewModel.confidenceForDelta, ΔE76)."""
    if d76 <= 1.5:
        return "Exact"
    if d76 <= 3.0:
        return "Very close"
    if d76 <= 5.0:
        return "Close"
    if d76 <= 8.0:
        return "Approximate"
    return "Explore"

# ---------------------------------------------------------------- catalog

EXCLUDED_TYPES = {"technical", "varnish", "medium", "auxiliary", "primer", "marker", "effect", "air"}
LOGGED_TYPES = {"dry"}
EXCLUDED_LINES = {"auxiliary products", "weathering fx", "pigment fx", "diorama fx", "varnish"}
AIR_LINE = re.compile(r"air|airbrush|spray|mecha", re.I)
WASHY_TYPES = {"wash", "ink", "contrast", "speedpaint", "glaze"}
STANDARD_TYPES = {"color", "base", "layer"}

BRAND_SLUGS = {
    "Citadel": "citadel", "Vallejo": "vallejo", "Army Painter": "army-painter",
    "AK Interactive": "ak-interactive", "Two Thin Coats": "two-thin-coats",
    "Scale75": "scale75", "Monument Hobbies": "pro-acryl", "Kimera Kolors": "kimera-kolors",
}
POOL_LABEL = {"standard": "Standard", "metallic": "Metallic", "wash": "Washes & Contrast"}

# Lines kept as page subjects but excluded from cross-brand recommendations
# (craft or military-modelling ranges a miniature painter is unlikely to buy).
RECO_EXCLUDED_LINES = {
    ("Vallejo", "Arte Deco"),
    ("Vallejo", "Arte Deco Colores Fluoresecents"),
    ("AK Interactive", "AFV Series"),
    ("AK Interactive", "Naval Series"),
    ("AK Interactive", "General Series"),
}


def recommendable(p):
    return (p["brand"], p["line"]) not in RECO_EXCLUDED_LINES


def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)


def classify_pool(typ, finish, line, line_variant=""):
    if typ in EXCLUDED_TYPES or typ in LOGGED_TYPES:
        return None
    low = (line or "").lower()
    if low in EXCLUDED_LINES or "primer" in low:
        return None
    if AIR_LINE.search(line or "") or AIR_LINE.search(line_variant or ""):
        return None
    if finish == "metallic":
        return "metallic"
    if finish == "translucent" or typ in WASHY_TYPES:
        return "wash"
    if typ in STANDARD_TYPES:
        return "standard"
    return None


def load_catalog(db_path=DEFAULT_DB):
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT paint_id, name, brand, line, line_variant, code, type, finish, color_json, tags_json "
        "FROM library_paints ORDER BY brand, name, line"
    ).fetchall()
    con.close()
    paints, skipped = [], {"no_color": [], "excluded": [], "logged_type": []}
    for pid, name, brand, line, line_variant, code, typ, finish, cj, tj in rows:
        if not cj:
            skipped["no_color"].append(f"{brand} / {name} ({line})")
            continue
        c = json.loads(cj)
        if c.get("r") is None or not c.get("hex"):
            skipped["no_color"].append(f"{brand} / {name} ({line})")
            continue
        tags = json.loads(tj) if tj else []
        if any(t in ("effect", "varnish", "pigment", "placeholder_color") for t in tags):
            skipped["excluded"].append(f"{brand} / {name} ({line}) [tag]")
            continue
        pool = classify_pool(typ, finish or "unknown", line or "", line_variant or "")
        if pool is None:
            key = "logged_type" if typ in LOGGED_TYPES else "excluded"
            skipped[key].append(f"{brand} / {name} ({line}) [{typ}/{finish}]")
            continue
        r, g, b = c["r"], c["g"], c["b"]
        paints.append({
            "id": pid, "name": name, "brand": brand, "line": line or "",
            "line_variant": line_variant or "", "code": code or "",
            "type": typ, "finish": finish or "unknown", "pool": pool,
            "hex": c["hex"].upper() if not c["hex"].startswith("#") else c["hex"].upper(),
            "r": r, "g": g, "b": b,
            "lab": srgb_to_lab(r, g, b), "hsl": rgb_to_hsl(r, g, b),
            "family": color_family(r, g, b),
        })
    # unique slugs per brand: name -> +line -> +variant -> +code -> counter
    def assign(group, keyfn, depth):
        buckets = {}
        for p in group:
            buckets.setdefault(keyfn(p), []).append(p)
        for slug, sub in buckets.items():
            if len(sub) == 1:
                sub[0]["slug"] = slug
            elif depth == 0:
                assign(sub, lambda p: slugify(f'{p["name"]} {p["line"]}'), 1)
            elif depth == 1:
                assign(sub, lambda p: slugify(f'{p["name"]} {p["line"]} {p["line_variant"]}'), 2)
            elif depth == 2:
                assign(sub, lambda p: slugify(f'{p["name"]} {p["line"]} {p["line_variant"]} {p["code"]}'), 3)
            else:
                for i, p in enumerate(sub):
                    p["slug"] = f"{slug}-{i + 1}" if i else slug
                skipped["possible_dups"].extend(
                    f'{p["brand"]} / {p["name"]} ({p["line"]} {p["line_variant"]}) code={p["code"] or "-"}'
                    for p in sub)
    skipped["possible_dups"] = []
    by_brand = {}
    for p in paints:
        by_brand.setdefault(p["brand"], []).append(p)
    for group in by_brand.values():
        assign(group, lambda p: slugify(p["name"]), 0)
    return paints, skipped

# ---------------------------------------------------------------- matching

def best_match(source, paints, target_brand):
    """Best equivalent in target brand, same finish pool (app: Grouped policy)."""
    best, best_de = None, None
    for p in paints:
        if p["brand"] != target_brand or p["pool"] != source["pool"] or p is source:
            continue
        if not recommendable(p):
            continue
        d = de2000(source["lab"], p["lab"])
        if best_de is None or d < best_de:
            best, best_de = p, d
    return (best, best_de) if best else (None, None)


def similar_paints(source, paints, n=6):
    """App: 6 nearest by ΔE76, cross-brand, same finish pool, excluding self."""
    cands = []
    for p in paints:
        if p is source or p["pool"] != source["pool"]:
            continue
        cands.append((de76(source["lab"], p["lab"]), p))
    cands.sort(key=lambda t: t[0])
    return cands[:n]

# ------------------------------------------- highlight / shadow (Layering)

def _highlight_boost(l):
    if l < 0.15: return 0.75
    if l < 0.3: return 0.6
    if l < 0.5: return 0.45
    if l < 0.7: return 0.3
    return 0.2


def _shadow_depth(l):
    if l > 0.85: return 0.65
    if l > 0.7: return 0.5
    if l > 0.5: return 0.35
    if l > 0.3: return 0.25
    return 0.18


def _hue_shift_amount(s):
    if s < 0.1: return 0.0
    if s < 0.3: return 6.0
    if s < 0.6: return 10.0
    return 14.0


def _shift_hue_toward(h, target, max_shift):
    diff = (target - h + 540) % 360 - 180
    if abs(diff) <= max_shift:
        return target
    return (h + math.copysign(max_shift, diff)) % 360


def synth_highlight(hexcolor, intensity=0.16):
    h, s, l = rgb_to_hsl(*hex_to_rgb(hexcolor))
    boost = max(intensity, _highlight_boost(l))
    nl = min(0.98, l + (1 - l) * boost)
    nh = _shift_hue_toward(h, 65.0, _hue_shift_amount(s))
    if s < 0.1: red = 0.25
    elif s < 0.3: red = 0.20
    elif s < 0.6: red = 0.12
    else: red = 0.08
    ns = max(0.0, s * (1 - red))
    return hsl_to_hex(nh, ns, nl)


def synth_shadow(hexcolor, intensity=0.16):
    h, s, l = rgb_to_hsl(*hex_to_rgb(hexcolor))
    depth = max(intensity, _shadow_depth(l))
    nl = max(0.02, l - l * depth)
    nh = _shift_hue_toward(h, 240.0, _hue_shift_amount(s) * 1.1)
    if s < 0.1: mul = 1.35
    elif s < 0.3: mul = 1.20
    else: mul = 1.05
    ns = min(1.0, s * mul)
    return hsl_to_hex(nh, ns, nl)


def nearest_value_shift(source, target_hex, paints, direction, min_dl=0.08,
                        value_tol=0.22, min_score=0.5):
    """App: findBestValueShiftCandidate — score = colorScore*0.72 + valueScore*0.28."""
    t_lab = srgb_to_lab(*hex_to_rgb(target_hex))
    t_l = rgb_to_hsl(*hex_to_rgb(target_hex))[2]
    s_l = source["hsl"][2]
    best, best_score = None, 0.0
    for p in paints:
        if p is source or p["pool"] != "standard" or not recommendable(p):
            continue
        dl = p["hsl"][2] - s_l
        if direction == "highlight" and dl < min_dl:
            continue
        if direction == "shadow" and dl > -min_dl:
            continue
        d = de2000(t_lab, p["lab"])
        color_score = max(0.0, 1 - d / 100.0)
        value_score = max(0.0, 1 - abs(p["hsl"][2] - t_l) / value_tol)
        score = color_score * 0.72 + value_score * 0.28
        if direction == "shadow" and p["hsl"][2] < 0.08 and s_l > 0.3:
            score *= 0.65
        elif direction == "shadow" and p["hsl"][2] < 0.12 and s_l > 0.25:
            score *= 0.78
        if score > best_score:
            best, best_score = p, score
    return best if best_score >= min_score else None

# ------------------------------------------------------------ complementary

def complementary(source, paints, tolerance=45.0, limit=2, min_score=0.5):
    """App: harmony via hue offset +180°, scored 0.6 hue / 0.25 contrast / 0.15 sat."""
    h, s, l = source["hsl"]
    target_h = (h + 180) % 360
    scored = []
    for p in paints:
        if p is source or p["pool"] != "standard" or not recommendable(p):
            continue
        ph, ps, pl = p["hsl"]
        diff = abs((ph - target_h + 540) % 360 - 180)
        if diff > tolerance:
            continue
        hue_score = 1 - diff / tolerance
        light_score = min(1.0, abs(pl - l) / 0.45)
        sat_score = max(0.0, 1 - abs(ps - s) / 0.45)
        score = hue_score * 0.6 + light_score * 0.25 + sat_score * 0.15
        if score >= min_score:
            scored.append((score, p))
    scored.sort(key=lambda t: -t[0])
    return [p for _, p in scored[:limit]]


if __name__ == "__main__":
    black = srgb_to_lab(0, 0, 0)
    white = srgb_to_lab(255, 255, 255)
    assert de2000(black, black) == 0
    assert de2000(black, white) > 90
    meph = srgb_to_lab(150, 12, 9)
    carmine = srgb_to_lab(0x97, 0x21, 0x1F)
    d = de2000(meph, carmine)
    assert 4.0 < d < 4.5, d
    assert match_quality(3.0)[0] == "Excellent Match"
    assert match_quality(8.0)[0] == "Good Match"
    assert similar_label(2.2) == "Very close"
    paints, skipped = load_catalog()
    pools = {}
    for p in paints:
        pools[p["pool"]] = pools.get(p["pool"], 0) + 1
    print(f"loaded: {len(paints)} | pools: {pools}")
    print(f"skipped: no_color={len(skipped['no_color'])} excluded={len(skipped['excluded'])} "
          f"logged_type={len(skipped['logged_type'])}")
    slugs = {(p['brand'], p['slug']) for p in paints}
    assert len(slugs) == len(paints), "slug collision"
    src = next(p for p in paints if p["name"] == "Mephiston Red" and p["line"] == "Base")
    m, dd = best_match(src, paints, "Vallejo")
    print(f"Mephiston Red -> Vallejo: {m['name']} {m['code']} ΔE {dd:.1f}")
    hl_hex = synth_highlight(src["hex"])
    hl = nearest_value_shift(src, hl_hex, paints, "highlight")
    sh_hex = synth_shadow(src["hex"])
    sh = nearest_value_shift(src, sh_hex, paints, "shadow")
    print(f"highlight target {hl_hex} -> {hl['brand'] + ' ' + hl['name'] if hl else None}")
    print(f"shadow target {sh_hex} -> {sh['brand'] + ' ' + sh['name'] if sh else None}")
    comp = complementary(src, paints)
    print("complementary:", [f'{p["brand"]} {p["name"]}' for p in comp])
    print("self-test OK")
