#!/usr/bin/env python3
"""
漫画页面排版 + PDF 导出
======================
铁律第 5 条: 对白文字绝不烧进 AI 图像。
  → AI 只出干净画面,气泡/旁白/SFX 全部在这一层叠加,随时可改文案、可换位置。

版式 DSL
--------
一页 = 若干行,一行 = 若干 panel id。**格子尺寸由图片真实宽高比自动算出**,
不用手写权重:

    [["p01"],                      # 横幅图独占一行
     ["p02", "p03"],               # 两格并排,列宽按各自宽高比分配
     (1.55, ["p13"])]              # 前置倍数 = 强调(splash 放大)

原则: **竖图必须和别的格子共享一行,绝不独占整页宽** ——
否则 fit_cover 会上下狂裁,把人物的头切掉(v2 的 p06 就是这么废的)。

阅读顺序: 左→右(中文现代漫画惯例)。日式右→左请改 READING_ORDER。
"""
from __future__ import annotations
import argparse, json, os, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "episodes")
OUT_DIR = os.path.expanduser("~/ComfyUI/output")
EXPORT = os.path.join(ROOT, "exports")

# ── 页面规格 (A4 @150dpi) ───────────────────────────────────
PAGE_W, PAGE_H = 1240, 1754
MARGIN = 52
GUTTER = 20
BORDER = 5
READING_ORDER = "ltr"          # "ltr" 中文 / "rtl" 日式

# ── 字体 ────────────────────────────────────────────────────
F_NARR = "/System/Library/Fonts/Supplemental/Songti.ttc"      # 旁白: 宋体,书卷气
F_DIAL = "/System/Library/Fonts/Hiragino Sans GB.ttc"         # 对白: 黑体,清晰
F_TITLE = "/System/Library/Fonts/Supplemental/Songti.ttc"


def font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.load_default()


def wrap_cjk(text, fnt, max_w, draw):
    """中文按字断行(没有空格可依)"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        trial = cur + ch
        if draw.textlength(trial, font=fnt) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = ch
    if cur:
        lines.append(cur)
    return lines


def fit_cover(img, w, h, y_bias=0.36):
    """裁剪填充。

    y_bias < 0.5 表示竖向裁切时偏向保留上部 —— 人物的脸几乎总在画面上半,
    居中裁切会把头切掉(v2 的 p06 就是这么废的)。
    """
    iw, ih = img.size
    s = max(w / iw, h / ih)
    nw, nh = int(iw * s + 0.5), int(ih * s + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    ox = (nw - w) // 2
    oy = int((nh - h) * y_bias)
    return img.crop((ox, oy, ox + w, oy + h))


# ── 文本图层 ────────────────────────────────────────────────
def draw_narration(page, box, text, anchor="tl"):
    """旁白框 —— 直角白框,经文/叙述用"""
    d = ImageDraw.Draw(page)
    x0, y0, x1, y1 = box
    fnt = font(F_NARR, 27, index=1)
    pad, maxw = 18, min(int((x1 - x0) * 0.62), 430)
    lines = wrap_cjk(text, fnt, maxw, d)
    lh = 38
    bw = max(d.textlength(l, font=fnt) for l in lines) + pad * 2
    bh = len(lines) * lh + pad * 2 - 8

    bx = x0 + 16 if "l" in anchor else x1 - bw - 16
    by = y0 + 16 if "t" in anchor else y1 - bh - 16

    d.rectangle([bx, by, bx + bw, by + bh], fill=(252, 250, 245),
                outline=(20, 20, 20), width=3)
    for i, ln in enumerate(lines):
        d.text((bx + pad, by + pad + i * lh), ln, font=fnt, fill=(15, 15, 15))


def draw_bubble(page, box, text, speaker=None, anchor="bl"):
    """对白气泡 —— 椭圆 + 指向尾巴"""
    d = ImageDraw.Draw(page)
    x0, y0, x1, y1 = box
    fnt = font(F_DIAL, 28, index=0)
    maxw = min(int((x1 - x0) * 0.56), 380)
    lines = wrap_cjk(text, fnt, maxw, d)
    lh = 40
    tw = max(d.textlength(l, font=fnt) for l in lines)
    bw, bh = tw + 76, len(lines) * lh + 62

    bx = x0 + 28 if "l" in anchor else x1 - bw - 28
    by = y0 + 28 if "t" in anchor else y1 - bh - 66

    # 尾巴(指向画面内侧)
    tip_x = bx + bw * 0.35 if "l" in anchor else bx + bw * 0.65
    d.polygon([(bx + bw * 0.42, by + bh - 8), (bx + bw * 0.6, by + bh - 8),
               (tip_x, by + bh + 42)], fill=(255, 255, 255),
              outline=(20, 20, 20))

    d.ellipse([bx, by, bx + bw, by + bh], fill=(255, 255, 255),
              outline=(20, 20, 20), width=4)

    ty = by + (bh - len(lines) * lh) / 2
    for i, ln in enumerate(lines):
        lw = d.textlength(ln, font=fnt)
        d.text((bx + (bw - lw) / 2, ty + i * lh), ln, font=fnt,
               fill=(10, 10, 10))

    if speaker:
        sf = font(F_DIAL, 20, index=0)
        d.text((bx + 8, by - 28), speaker, font=sf, fill=(40, 40, 40))


def draw_sfx(page, box, text):
    """拟声词 —— 白描边黑字,斜置"""
    x0, y0, x1, y1 = box
    fnt = font(F_DIAL, 62, index=0)
    layer = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    px, py = int((x1 - x0) * 0.06), int((y1 - y0) * 0.10)
    for dx in range(-4, 5, 2):
        for dy in range(-4, 5, 2):
            d.text((px + dx, py + dy), text, font=fnt, fill=(255, 255, 255, 235))
    d.text((px, py), text, font=fnt, fill=(15, 15, 15, 255))
    layer = layer.rotate(-8, resample=Image.BICUBIC, expand=False)
    page.paste(layer, (x0, y0), layer)


# ── 页面渲染 ────────────────────────────────────────────────
def panel_aspect(panel_files, pid):
    f = panel_files.get(pid)
    if f:
        p = os.path.join(OUT_DIR, f)
        if os.path.exists(p):
            iw, ih = Image.open(p).size
            return iw / ih
    return 0.75


def render_page(rows, panel_files, storyboard_by_id):
    """rows: [[panel_id, ...], ...] 或 [(强调倍数, [panel_id, ...]), ...]

    格子尺寸**按图片真实宽高比自动分配**:
      · 列宽 ∝ 该图宽高比  → 横图得到宽格,竖图得到窄格
      · 行高 ∝ 该行的自然高度(justified gallery 算法)
    这样竖图永远不会被塞进整页宽的横格里(v2 的裁剪 bug 根因)。

    强调倍数用来给关键格(splash)额外放大。
    """
    page = Image.new("RGB", (PAGE_W, PAGE_H), (255, 255, 255))
    d = ImageDraw.Draw(page)

    avail_w = PAGE_W - MARGIN * 2
    avail_h = PAGE_H - MARGIN * 2

    norm = []
    for r in rows:
        emph, ids = r if isinstance(r, tuple) else (1.0, r)
        asp = [panel_aspect(panel_files, p) for p in ids]
        inner_w = avail_w - GUTTER * (len(ids) - 1)
        nat_h = inner_w / sum(asp)              # 该行的自然高度
        norm.append((emph, ids, asp, nat_h * emph))

    scale = (avail_h - GUTTER * (len(norm) - 1)) / sum(n[3] for n in norm)

    y = MARGIN
    for emph, ids, asp, nat_h in norm:
        rh = int(nat_h * scale)
        order = list(zip(ids, asp))
        if READING_ORDER == "rtl":
            order = list(reversed(order))
        inner_w = avail_w - GUTTER * (len(ids) - 1)
        x = MARGIN
        for pid, a in order:
            cw = int(inner_w * a / sum(asp))
            f = panel_files.get(pid)
            if f and os.path.exists(os.path.join(OUT_DIR, f)):
                im = Image.open(os.path.join(OUT_DIR, f)).convert("RGB")
                page.paste(fit_cover(im, cw, rh), (x, y))
            else:
                d.rectangle([x, y, x + cw, y + rh], fill=(230, 230, 230))
                d.text((x + 20, y + 20), f"[missing {pid}]", fill=(120, 0, 0))
            d.rectangle([x, y, x + cw, y + rh], outline=(10, 10, 10),
                        width=BORDER)

            box = (x, y, x + cw, y + rh)
            p = storyboard_by_id.get(pid, {})
            na, da = ANCHORS.get(pid, (None, None))
            if p.get("sfx"):
                draw_sfx(page, box, p["sfx"])
            if p.get("narration"):
                draw_narration(page, box, p["narration"]["text"],
                               p.get("narrationAnchor") or na or "tl")
            if p.get("dialogue"):
                draw_bubble(page, box, p["dialogue"]["text"],
                            p["dialogue"].get("speaker"),
                            p.get("dialogueAnchor") or da or "bl")
            x += cw + GUTTER
        y += rh + GUTTER
    return page


def render_cover(ep, cover_file):
    page = Image.new("RGB", (PAGE_W, PAGE_H), (12, 10, 14))
    if cover_file and os.path.exists(os.path.join(OUT_DIR, cover_file)):
        art = fit_cover(Image.open(os.path.join(OUT_DIR, cover_file)).convert("RGB"),
                        PAGE_W, PAGE_H)
        page.paste(art, (0, 0))

    # 上下压暗,让文字站得住
    grad = Image.new("L", (1, PAGE_H))
    for yy in range(PAGE_H):
        t = yy / PAGE_H
        v = 215 if t < 0.30 else (150 if t > 0.78 else 0)
        if t < 0.30:
            v = int(215 * (1 - t / 0.30))
        elif t > 0.78:
            v = int(170 * ((t - 0.78) / 0.22))
        else:
            v = 0
        grad.putpixel((0, yy), v)
    dark = Image.new("RGB", (PAGE_W, PAGE_H), (0, 0, 0))
    page = Image.composite(dark, page, grad.resize((PAGE_W, PAGE_H)))

    d = ImageDraw.Draw(page)
    title = ep["title"].split("—")
    main = title[0].strip()
    sub = title[1].strip() if len(title) > 1 else ""

    ft = font(F_TITLE, 92, index=1)
    fs = font(F_TITLE, 44, index=1)
    fm = font(F_DIAL, 26, index=0)

    tw = d.textlength(main, font=ft)
    d.text(((PAGE_W - tw) / 2, 150), main, font=ft, fill=(248, 244, 232))
    d.line([(PAGE_W / 2 - 150, 285), (PAGE_W / 2 + 150, 285)],
           fill=(212, 175, 95), width=3)
    if sub:
        sw = d.textlength(sub, font=fs)
        d.text(((PAGE_W - sw) / 2, 312), sub, font=fs, fill=(228, 214, 180))

    foot = (f"{ep['passage']['translationName']}　·　"
            f"{ep['passage']['license']}")
    fw = d.textlength(foot, font=fm)
    d.text(((PAGE_W - fw) / 2, PAGE_H - 118), foot, font=fm,
           fill=(198, 190, 176))
    note = "AI 辅助制作 · 经文原文未经改动 · 画面为戏剧化演绎"
    nw = d.textlength(note, font=fm)
    d.text(((PAGE_W - nw) / 2, PAGE_H - 78), note, font=fm,
           fill=(160, 154, 144))
    return page


# ── 版式定义 ────────────────────────────────────────────────
# 格子尺寸由图片宽高比自动决定,这里只管**哪几格同一行**。
# 原则: 竖图必须和别的格子共享一行,绝不独占整页宽 —— 否则必被裁掉头。
LAYOUT = [
    # ── 第 1 页 · 序言 + 拔摩岛登场 ─────────────────────
    [["p01"],                       # 极远景 光柱(横幅,可独占)
     ["p02", "p03"],                  # 卷轴 insert + 约翰书写(竖图,配对)
     ["p04", "p05"]],                 # 荒岛俯瞰 + 海浪撞礁

    # ── 第 2 页 · 孤独 → 被圣灵感动 ─────────────────────
    [["p06", "p07"],                  # 约翰独坐(竖) + 脸特写(竖)
     ["p08", "p09"],                  # 苍老的手 + 闭眼中近
     (1.15, ["p10"])],                # 双眼骤睁 极特写(横幅),放大强调

    # ── 第 3 页 · 转身 → 灯台显现 ───────────────────────
    [["p11", "p12"],                  # 逆光背影 + 转头(竖图配对)
     (1.55, ["p13"]),                 # ★ 七金灯台 splash
     ["p14"]],                        # 单座灯台细节

    # ── 第 4 页 · 人子异象 ──────────────────────────────
    [(1.25, ["p15", "p16"]),          # 人子全身(竖) + 眼如火焰(横)
     ["p17", "p18"],                  # 铜脚 + 手托七星
     ["p19"]],                        # 面如烈日

    # ── 第 5 页 · 仆倒 → 安慰 → 收尾 ────────────────────
    [["p20"],                         # 俯角: 仆倒如死(横幅)
     (1.15, ["p21", "p22"]),          # 手按肩(竖) + 仰起的脸(竖)
     ["p23", "p24"]],                 # 钥匙 + 七星七灯台收束
]

# 文字框位置 —— 避免每格都堆在左上角
ANCHORS = {
    "p01": ("tl", None), "p03": ("bl", None), "p04": ("tl", None),
    "p06": ("tr", None), "p09": ("tl", None), "p11": (None, "br"),
    "p12": ("tl", None), "p13": ("tr", None), "p15": ("bl", None),
    "p16": ("tl", None), "p17": ("br", None), "p18": ("tl", None),
    "p19": ("tr", None), "p20": ("tl", None), "p21": (None, "tr"),
    "p22": (None, "bl"), "p23": ("br", None), "p24": ("tl", None),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--cover", help="封面图文件名(位于 ComfyUI/output)")
    a = ap.parse_args()

    with open(os.path.join(DATA, f"{a.episode}.json"), encoding="utf-8") as f:
        ep = json.load(f)
    with open(os.path.join(DATA, f"{a.episode}-storyboard.json"),
              encoding="utf-8") as f:
        sb = json.load(f)
    with open(os.path.join(DATA, f"{a.episode}-generated.json"),
              encoding="utf-8") as f:
        gen = json.load(f)

    files = {p["panel"]: p["file"] for p in gen["panels"]}
    by_id = {p["id"]: p for p in sb["panels"]}

    cover_file = a.cover
    if not cover_file:
        for c in sorted(os.listdir(OUT_DIR)):
            if c.startswith(f"{a.episode}_cover"):
                cover_file = c

    pages = [render_cover(ep, cover_file)]
    for rows in LAYOUT:
        pages.append(render_page(rows, files, by_id))

    os.makedirs(EXPORT, exist_ok=True)
    pdf = os.path.join(EXPORT, f"{a.episode}.pdf")
    pages[0].save(pdf, "PDF", resolution=150.0, save_all=True,
                  append_images=pages[1:])
    for i, pg in enumerate(pages):
        pg.save(os.path.join(EXPORT, f"{a.episode}_page{i:02d}.png"))

    print(f"✅ {len(pages)} 页 (含封面)")
    print(f"   PDF: {pdf}")
    print(f"   PNG: {EXPORT}/{a.episode}_page*.png")


if __name__ == "__main__":
    main()
