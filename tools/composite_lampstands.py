#!/usr/bin/env python3
"""
七金灯台合成器
==============
问题: SD1.5 数不准数量。"seven golden lampstands" 试了三次,
      分别出成金色大教堂、曼陀罗图案、一片烛海 —— 从来没有七个独立灯台。

解法: 生成**一座**灯台(模型很擅长),程序化复制七次并排布。
      数量从此是确定的,不是概率的。

排布逻辑: 七座沿一段外凸的弧线排开 —— 中间的远(小、高),
两端的近(大、低)。读起来像"你站在灯台围成的圈里",
对应经文"灯台中间有一位好像人子"(启 1:13)。
"""
from __future__ import annotations
import argparse, os, sys
from PIL import Image, ImageFilter, ImageChops

OUT_DIR = os.path.expanduser("~/ComfyUI/output")


def cutout(img: Image.Image, floor: int = 14, gamma: float = 1.25) -> Image.Image:
    """黑底发光物体 → 带 alpha 的贴图。

    用亮度当 alpha: 发光物体在纯黑背景上,亮度天然就是遮罩,
    而且能自动保留光晕的柔边 —— 比抠边干净得多。
    """
    rgb = img.convert("RGB")
    lum = rgb.convert("L")
    lum = lum.point(lambda v: 0 if v < floor else
                    min(255, int(255 * ((v - floor) / (255 - floor)) ** (1 / gamma))))
    out = rgb.convert("RGBA")
    out.putalpha(lum)
    return out


def build(src: str, dst: str, count: int = 7,
          size: tuple[int, int] = (768, 512),
          spread: float = 0.46, depth: float = 0.30,
          near_scale: float = 0.46, base_scale: float = 0.62) -> str:
    W, H = size
    canvas = Image.new("RGBA", (W, H), (4, 3, 6, 255))
    stand = cutout(Image.open(os.path.join(OUT_DIR, src)))

    items = []
    for i in range(count):
        t = -1.0 + 2.0 * i / (count - 1)      # -1 .. 1
        nearness = t * t                       # 中间远,两端近
        s = base_scale + near_scale * nearness
        cx = W * 0.5 + t * spread * W
        cy = H * (0.52 + depth * nearness)
        items.append((nearness, t, s, cx, cy))

    # 远的先画,近的后画 —— 保证遮挡关系正确
    for nearness, t, s, cx, cy in sorted(items, key=lambda k: k[0]):
        sw, sh = int(stand.width * s), int(stand.height * s)
        sp = stand.resize((sw, sh), Image.LANCZOS)
        # 远处的灯台压暗一点,拉开空间层次
        dim = 0.55 + 0.45 * nearness
        sp.putalpha(sp.getchannel("A").point(lambda v, d=dim: int(v * d)))
        canvas.alpha_composite(sp, (int(cx - sw / 2), int(cy - sh)))

    # 整体辉光 —— 把七个独立贴图融进同一个光场里
    glow = canvas.convert("RGB").filter(ImageFilter.GaussianBlur(26))
    merged = ImageChops.screen(canvas.convert("RGB"),
                               glow.point(lambda v: int(v * 0.55)))

    path = os.path.join(OUT_DIR, dst)
    merged.save(path)
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="单座灯台图(位于 ComfyUI/output)")
    ap.add_argument("--dst", default="rev-01_p13_composited.png")
    ap.add_argument("--count", type=int, default=7)
    a = ap.parse_args()
    print("✅", build(a.src, a.dst, a.count))
