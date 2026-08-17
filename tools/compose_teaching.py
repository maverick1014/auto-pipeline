#!/usr/bin/env python3
"""
教学式经文图解排版器
====================
体例参照 Maverick 选定的样张: 逐节经文直引 + 出处标注 + 色带章节标题
+ 编号小节 + 概要表 + 核心真理 + 金句卷轴 + 页码。

铁律第 5 条: 所有文字都在这一层叠加,绝不烧进 AI 图像。
铁律第 1 条: 经文框里的字必须与 data/bible/ 中的原文一致,ref 必须标注。

版面由 data/episodes/<ep>-pages.json 驱动(铁律第 8 条: 结构化 JSON)。

块类型
------
header  页眉大标题 + 主题句 + 出处
band    色带章节标题(左标题 / 右经文范围)
row     一行图格,每格可带编号、小标题、经文框(含 ref)或说明
table   概要表 / 特征表
truths  核心真理条目
quote   金句卷轴 + 印章
footer  结语条
"""
from __future__ import annotations
import argparse, json, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "episodes")
OUT_DIR = os.path.expanduser("~/ComfyUI/output")
EXPORT = os.path.join(ROOT, "exports")

PAGE_W, PAGE_H = 1240, 1754
MARGIN, GAP = 46, 16

BG        = (245, 240, 229)
INK       = (36, 29, 22)
INK_SOFT  = (92, 80, 66)
GOLD      = (176, 138, 58)
BOX_BG    = (252, 250, 244)
BORDER    = (28, 22, 16)

BANDS = {
    "crimson": (146, 36, 40),
    "navy":    (30, 55, 100),
    "purple":  (84, 44, 108),
    "gold":    (150, 112, 38),
    "teal":    (26, 88, 88),
}

F_SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"
F_SANS  = "/System/Library/Fonts/Hiragino Sans GB.ttc"


def font(path, size, index=0):
    for i in (index, 0):
        try:
            return ImageFont.truetype(path, size, index=i)
        except Exception:
            continue
    return ImageFont.load_default()


def wrap_cjk(text, fnt, max_w, d):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if d.textlength(cur + ch, font=fnt) <= max_w or not cur:
            cur += ch
        else:
            lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def fit_cover(img, w, h, y_bias=0.36):
    """y_bias<0.5: 竖向裁切偏向保留上部 —— 人脸几乎总在画面上半。"""
    iw, ih = img.size
    s = max(w / iw, h / ih)
    nw, nh = int(iw * s + .5), int(ih * s + .5)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - w) // 2, int((nh - h) * y_bias),
                     (nw - w) // 2 + w, int((nh - h) * y_bias) + h))


def aspect(files, pid):
    f = files.get(pid)
    if f:
        p = os.path.join(OUT_DIR, f)
        if os.path.exists(p):
            iw, ih = Image.open(p).size
            return iw / ih
    return 0.75


# ── 块渲染 ──────────────────────────────────────────────────
def draw_header(page, spec, y, h):
    d = ImageDraw.Draw(page)
    ft = font(F_SERIF, 74, 3)
    fs = font(F_SERIF, 29, 1)
    fr = font(F_SANS, 23, 0)
    w = PAGE_W - MARGIN * 2

    t = spec["title"]
    tw = d.textlength(t, font=ft)
    d.text(((PAGE_W - tw) / 2, y + 8), t, font=ft, fill=INK)

    ly = y + 100
    d.line([(PAGE_W / 2 - 190, ly), (PAGE_W / 2 + 190, ly)], fill=GOLD, width=3)
    d.ellipse([PAGE_W / 2 - 5, ly - 5, PAGE_W / 2 + 5, ly + 5], fill=GOLD)

    s = spec.get("subtitle", "")
    if s:
        sw = d.textlength(s, font=fs)
        d.text(((PAGE_W - sw) / 2, ly + 16), s, font=fs, fill=INK_SOFT)

    r = spec.get("source", "")
    if r:
        rw = d.textlength(r, font=fr)
        d.text(((PAGE_W - rw) / 2, ly + 58), r, font=fr, fill=GOLD)
    return h


def draw_band(page, b, y, h):
    d = ImageDraw.Draw(page)
    col = BANDS.get(b.get("color", "crimson"), BANDS["crimson"])
    x0, x1 = MARGIN, PAGE_W - MARGIN
    d.rectangle([x0, y, x1, y + h], fill=col)
    d.rectangle([x0, y + h - 4, x1, y + h], fill=GOLD)
    ft = font(F_SANS, 31, 1)
    d.text((x0 + 22, y + (h - 38) / 2), b["title"], font=ft, fill=(255, 252, 245))
    if b.get("ref"):
        fr = font(F_SANS, 22, 0)
        rw = d.textlength(b["ref"], font=fr)
        d.text((x1 - rw - 22, y + (h - 26) / 2), b["ref"], font=fr,
               fill=(238, 226, 200))
    return h


def _label_bar(page, box, num, name):
    d = ImageDraw.Draw(page)
    x0, y0, x1, _ = box
    fn = font(F_SANS, 23, 1)
    txt = f"{num}. {name}" if num else name
    tw = d.textlength(txt, font=fn)
    bw, bh = min(tw + 34, (x1 - x0) - 20), 40
    d.rectangle([x0 + 10, y0 + 10, x0 + 10 + bw, y0 + 10 + bh],
                fill=(250, 247, 238), outline=BORDER, width=2)
    d.rectangle([x0 + 10, y0 + 10, x0 + 15, y0 + 10 + bh], fill=GOLD)
    d.text((x0 + 26, y0 + 18), txt, font=fn, fill=INK)


def _text_box(page, box, text, ref=None, layer=None):
    d = ImageDraw.Draw(page)
    x0, _, x1, y1 = box
    fv = font(F_SERIF, 22, 1)
    fr = font(F_SANS, 17, 0)
    inner = (x1 - x0) - 40
    lines = wrap_cjk(text, fv, inner - 28, d)
    lh = 31
    bh = len(lines) * lh + 24 + (24 if ref or layer else 0)
    bx0, by0 = x0 + 12, y1 - bh - 12
    bx1, by1 = x1 - 12, y1 - 12

    panel = Image.new("RGBA", (bx1 - bx0, by1 - by0), (252, 250, 244, 238))
    page.paste(panel, (bx0, by0), panel)
    d.rectangle([bx0, by0, bx1, by1], outline=BORDER, width=2)

    ty = by0 + 12
    for ln in lines:
        d.text((bx0 + 14, ty), ln, font=fv, fill=INK)
        ty += lh
    if ref or layer:
        tag = ref or ""
        if layer and layer != "CANONICAL_QUOTE":
            tag = f"{tag}　[{layer}]" if tag else f"[{layer}]"
        d.text((bx0 + 14, ty + 2), tag, font=fr, fill=GOLD)


def draw_row(page, b, y, h, files):
    d = ImageDraw.Draw(page)
    cells = b["cells"]
    asp = [aspect(files, c["panel"]) for c in cells]
    inner = PAGE_W - MARGIN * 2 - GAP * (len(cells) - 1)
    x = MARGIN
    for c, a in zip(cells, asp):
        cw = int(inner * a / sum(asp))
        f = files.get(c["panel"])
        if f and os.path.exists(os.path.join(OUT_DIR, f)):
            im = Image.open(os.path.join(OUT_DIR, f)).convert("RGB")
            page.paste(fit_cover(im, cw, h), (x, y))
        else:
            d.rectangle([x, y, x + cw, y + h], fill=(228, 222, 210))
            d.text((x + 18, y + 18), f"[缺 {c['panel']}]", fill=(150, 40, 40))
        d.rectangle([x, y, x + cw, y + h], outline=BORDER, width=4)
        box = (x, y, x + cw, y + h)
        if c.get("num") or c.get("name"):
            _label_bar(page, box, c.get("num"), c.get("name", ""))
        if c.get("verse"):
            _text_box(page, box, c["verse"], c.get("ref"), "CANONICAL_QUOTE")
        elif c.get("note"):
            _text_box(page, box, c["note"], None, c.get("layer", "ADAPTED"))
        x += cw + GAP
    return h


def table_height(b):
    cols = b.get("cols", 3)
    rows = (len(b["items"]) + cols - 1) // cols
    return 54 + rows * 78


def draw_table(page, b, y, h):
    d = ImageDraw.Draw(page)
    x0, x1 = MARGIN, PAGE_W - MARGIN
    d.rectangle([x0, y, x1, y + h], fill=BOX_BG, outline=GOLD, width=3)
    ft = font(F_SANS, 25, 1)
    tw = d.textlength(b["title"], font=ft)
    d.text(((PAGE_W - tw) / 2, y + 12), b["title"], font=ft, fill=INK)

    cols = b.get("cols", 3)
    fn = font(F_SANS, 22, 1)
    fnote = font(F_SERIF, 19, 1)
    flab = font(F_SERIF, 24, 3)
    cw = (x1 - x0 - 24) / cols
    for i, it in enumerate(b["items"]):
        cx = x0 + 12 + (i % cols) * cw
        cy = y + 54 + (i // cols) * 78
        if it.get("label"):
            d.ellipse([cx + 6, cy + 12, cx + 42, cy + 48], outline=GOLD, width=2)
            lw = d.textlength(it["label"], font=flab)
            d.text((cx + 24 - lw / 2, cy + 18), it["label"], font=flab, fill=GOLD)
            tx = cx + 54
        else:
            tx = cx + 10
        d.text((tx, cy + 10), it["name"], font=fn, fill=INK)
        note = it.get("note", "")
        if it.get("ref"):
            note = f"{note}　({it['ref']})" if note else it["ref"]
        for j, ln in enumerate(wrap_cjk(note, fnote, cw - (tx - cx) - 14, d)[:2]):
            d.text((tx, cy + 40 + j * 24), ln, font=fnote, fill=INK_SOFT)
    return h


def truths_height(b):
    return 52 + len(b["items"]) * 62


def draw_truths(page, b, y, h):
    d = ImageDraw.Draw(page)
    x0, x1 = MARGIN, PAGE_W - MARGIN
    d.rectangle([x0, y, x1, y + h], fill=(250, 246, 236), outline=BORDER, width=3)
    d.rectangle([x0, y, x0 + 8, y + h], fill=BANDS["crimson"])
    ft = font(F_SANS, 25, 1)
    d.text((x0 + 26, y + 12), b["title"], font=ft, fill=BANDS["crimson"])

    fn = font(F_SANS, 22, 1)
    fnote = font(F_SERIF, 20, 1)
    for i, it in enumerate(b["items"]):
        cy = y + 50 + i * 62
        d.ellipse([x0 + 28, cy + 8, x0 + 42, cy + 22], fill=GOLD)
        d.text((x0 + 56, cy), it["name"], font=fn, fill=INK)
        for j, ln in enumerate(wrap_cjk(it.get("note", ""), fnote,
                                        x1 - x0 - 120, d)[:1]):
            d.text((x0 + 56, cy + 30), ln, font=fnote, fill=INK_SOFT)
    return h


def draw_quote(page, b, y, h):
    d = ImageDraw.Draw(page)
    x0, x1 = MARGIN + 80, PAGE_W - MARGIN - 80
    d.rounded_rectangle([x0, y, x1, y + h], radius=10,
                        fill=(250, 244, 228), outline=GOLD, width=3)
    d.rectangle([x0 - 14, y + 10, x0 + 2, y + h - 10], fill=(236, 226, 202),
                outline=GOLD, width=2)
    d.rectangle([x1 - 2, y + 10, x1 + 14, y + h - 10], fill=(236, 226, 202),
                outline=GOLD, width=2)

    fq = font(F_SERIF, 27, 1)
    lines = []
    for seg in b["text"].split("\n"):
        lines += wrap_cjk(seg, fq, x1 - x0 - 60, d)
    ty = y + (h - len(lines) * 38 - 26) / 2
    for ln in lines:
        lw = d.textlength(ln, font=fq)
        d.text(((PAGE_W - lw) / 2, ty), ln, font=fq, fill=INK)
        ty += 38
    fr = font(F_SANS, 19, 0)
    rw = d.textlength(b["ref"], font=fr)
    d.text(((PAGE_W - rw) / 2, ty + 2), b["ref"], font=fr, fill=GOLD)
    return h


def draw_footer(page, b, y, h):
    d = ImageDraw.Draw(page)
    x0, x1 = MARGIN, PAGE_W - MARGIN
    d.rectangle([x0, y, x1, y + h], fill=BANDS["crimson"])
    ft = font(F_SANS, 24, 1)
    tw = d.textlength(b["text"], font=ft)
    d.text(((PAGE_W - tw) / 2, y + (h - 30) / 2), b["text"], font=ft,
           fill=(255, 250, 240))
    return h


FIXED = {"header": 178, "band": 56, "quote": 176, "footer": 58}


def render_page(spec, page_def, files, page_no, total):
    page = Image.new("RGB", (PAGE_W, PAGE_H), BG)
    d = ImageDraw.Draw(page)
    blocks = page_def["blocks"]

    foot_h = 34
    avail = PAGE_H - MARGIN * 2 - foot_h

    heights, rows = [], []
    for b in blocks:
        t = b["type"]
        if t in FIXED:
            heights.append(FIXED[t])
        elif t == "table":
            heights.append(table_height(b))
        elif t == "truths":
            heights.append(truths_height(b))
        else:                                   # row —— 自然高度,稍后缩放
            asp = [aspect(files, c["panel"]) for c in b["cells"]]
            inner = PAGE_W - MARGIN * 2 - GAP * (len(b["cells"]) - 1)
            nat = inner / sum(asp)
            heights.append(nat)
            rows.append(len(heights) - 1)

    fixed_total = sum(h for i, h in enumerate(heights) if i not in rows)
    rows_total = sum(heights[i] for i in rows)
    gaps = GAP * (len(blocks) - 1)
    if rows and rows_total > 0:
        scale = max(0.2, (avail - fixed_total - gaps) / rows_total)
        for i in rows:
            heights[i] *= scale

    y = MARGIN
    for b, h in zip(blocks, heights):
        h = int(h)
        t = b["type"]
        if t == "header":
            draw_header(page, spec, y, h)
        elif t == "band":
            draw_band(page, b, y, h)
        elif t == "row":
            draw_row(page, b, y, h, files)
        elif t == "table":
            draw_table(page, b, y, h)
        elif t == "truths":
            draw_truths(page, b, y, h)
        elif t == "quote":
            draw_quote(page, b, y, h)
        elif t == "footer":
            draw_footer(page, b, y, h)
        y += h + GAP

    fp = font(F_SANS, 19, 0)
    pn = f"{page_no} / {total}"
    pw = d.textlength(pn, font=fp)
    d.text(((PAGE_W - pw) / 2, PAGE_H - MARGIN - 8), pn, font=fp, fill=INK_SOFT)
    if page_no == total and spec.get("translationLine"):
        fl = font(F_SANS, 16, 0)
        lw = d.textlength(spec["translationLine"], font=fl)
        d.text(((PAGE_W - lw) / 2, PAGE_H - MARGIN - 32),
               spec["translationLine"], font=fl, fill=(150, 140, 126))
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    a = ap.parse_args()

    with open(os.path.join(DATA, f"{a.episode}-pages.json"), encoding="utf-8") as f:
        spec = json.load(f)
    with open(os.path.join(DATA, f"{a.episode}-generated.json"), encoding="utf-8") as f:
        gen = json.load(f)
    files = {p["panel"]: p["file"] for p in gen["panels"]}

    total = len(spec["pages"])
    pages = [render_page(spec, pd, files, i + 1, total)
             for i, pd in enumerate(spec["pages"])]

    os.makedirs(EXPORT, exist_ok=True)
    pdf = os.path.join(EXPORT, f"{a.episode}-teaching.pdf")
    pages[0].save(pdf, "PDF", resolution=150.0, save_all=True,
                  append_images=pages[1:])
    for i, pg in enumerate(pages):
        pg.save(os.path.join(EXPORT, f"{a.episode}_t{i+1:02d}.png"))
    print(f"✅ {total} 页 -> {pdf}")


if __name__ == "__main__":
    main()
