#!/usr/bin/env python3
"""
程序化 OpenPose 骨架生成器
==========================
用途: 主动"创作"分镜姿势与景别,而不是从照片里提取。

核心思路
--------
骨架在画面中的**缩放与位置**就等于镜头景别:
    头部占满画面        → EXTREME_CLOSE_UP
    头+肩填充画面        → CLOSE_UP
    全身缩小居中         → WIDE

这样"镜头"从"祈祷 prompt 生效"变成了确定的几何计算 ——
实测纯 prompt 的镜头指令 8 张里 6 张失效,这是根本解法。

坐标系
------
以 neck 为原点,单位 = 1 个头高(head unit),y 轴向下。
标准人体约 7.5 头高。

输出为 ControlNet openpose 期望的 COCO-18 骨架图。
"""
from __future__ import annotations
import math
from PIL import Image, ImageDraw

# ── COCO-18 关键点索引 ──────────────────────────────────────
NOSE, NECK = 0, 1
R_SHO, R_ELB, R_WRI = 2, 3, 4
L_SHO, L_ELB, L_WRI = 5, 6, 7
R_HIP, R_KNE, R_ANK = 8, 9, 10
L_HIP, L_KNE, L_ANK = 11, 12, 13
R_EYE, L_EYE, R_EAR, L_EAR = 14, 15, 16, 17

# OpenPose 标准配色 —— ControlNet 依赖这个配色识别肢体,不要改
COLORS = [
    (255, 0, 0), (255, 85, 0), (255, 170, 0), (255, 255, 0), (170, 255, 0),
    (85, 255, 0), (0, 255, 0), (0, 255, 85), (0, 255, 170), (0, 255, 255),
    (0, 170, 255), (0, 85, 255), (0, 0, 255), (85, 0, 255), (170, 0, 255),
    (255, 0, 255), (255, 0, 170), (255, 0, 85),
]

# 骨架连线 (COCO-18 标准顺序,颜色按此索引取)
LIMBS = [
    (NECK, R_SHO), (NECK, L_SHO), (R_SHO, R_ELB), (R_ELB, R_WRI),
    (L_SHO, L_ELB), (L_ELB, L_WRI), (NECK, R_HIP), (R_HIP, R_KNE),
    (R_KNE, R_ANK), (NECK, L_HIP), (L_HIP, L_KNE), (L_KNE, L_ANK),
    (NECK, NOSE), (NOSE, R_EYE), (R_EYE, R_EAR), (NOSE, L_EYE), (L_EYE, L_EAR),
]

# ── 基础姿势: 标准站姿(正面),单位=头高,原点=neck ─────────────
BASE_STANDING = {
    NOSE:  (0.00, -0.42),
    NECK:  (0.00,  0.00),
    R_EYE: (-0.11, -0.52), L_EYE: (0.11, -0.52),
    R_EAR: (-0.22, -0.48), L_EAR: (0.22, -0.48),
    R_SHO: (-0.52,  0.12), L_SHO: (0.52,  0.12),
    R_ELB: (-0.62,  1.15), L_ELB: (0.62,  1.15),
    R_WRI: (-0.68,  2.15), L_WRI: (0.68,  2.15),
    R_HIP: (-0.30,  2.70), L_HIP: (0.30,  2.70),
    R_KNE: (-0.32,  4.40), L_KNE: (0.32,  4.40),
    R_ANK: (-0.33,  6.10), L_ANK: (0.33,  6.10),
}

HEAD_TOP_Y = -1.05     # 头顶(用于取景计算)
FOOT_Y = 6.35          # 脚底


def _mod(base: dict, changes: dict) -> dict:
    """注意: 必须传 dict 而不是 **kwargs —— 关键点是 int 常量,
    **kwargs 会把键变成字符串,导致渲染时配色索引崩溃。"""
    p = dict(base)
    p.update(changes)
    return p


# ── 姿势库 ──────────────────────────────────────────────────
POSES: dict[str, dict] = {
    "standing": BASE_STANDING,

    # 侧身站立(压缩 x 轴模拟侧面透视)
    "side_profile": {k: (x * 0.35 + 0.12, y)
                     for k, (x, y) in BASE_STANDING.items()},

    # 行走
    "walking": _mod(BASE_STANDING, {
        R_KNE: (-0.45, 4.30), R_ANK: (-0.70, 5.95),
        L_KNE: (0.25, 4.45), L_ANK: (0.15, 6.15),
        R_ELB: (-0.70, 1.10), R_WRI: (-0.55, 2.05),
        L_ELB: (0.58, 1.20), L_WRI: (0.78, 2.10)}),

    # 甩投石索: 右臂高举过头
    "sling_swing": _mod(BASE_STANDING, {
        R_ELB: (-0.85, -0.35), R_WRI: (-0.60, -1.30),
        L_ELB: (0.75, 1.05), L_WRI: (0.95, 1.85),
        R_KNE: (-0.50, 4.35), R_ANK: (-0.72, 6.00),
        L_KNE: (0.38, 4.42), L_ANK: (0.45, 6.10)}),

    # 双臂张开(惊讶/敬拜)
    "arms_open": _mod(BASE_STANDING, {
        R_ELB: (-1.05, 0.55), R_WRI: (-1.55, 0.05),
        L_ELB: (1.05, 0.55), L_WRI: (1.55, 0.05)}),

    # 跪姿
    "kneeling": _mod(BASE_STANDING, {
        R_KNE: (-0.34, 4.10), L_KNE: (0.34, 4.10),
        R_ANK: (-0.36, 4.05), L_ANK: (0.36, 4.05),
        R_ELB: (-0.60, 1.10), R_WRI: (-0.40, 2.00),
        L_ELB: (0.60, 1.10), L_WRI: (0.40, 2.00)}),

    # 伸手去拿(摘果子)
    "reaching_up": _mod(BASE_STANDING, {
        R_ELB: (-0.70, 0.10), R_WRI: (-0.75, -0.95),
        L_ELB: (0.62, 1.15), L_WRI: (0.68, 2.15)}),

    # 抱头/恐惧
    "covering_face": _mod(BASE_STANDING, {
        R_ELB: (-0.72, 0.75), R_WRI: (-0.25, -0.25),
        L_ELB: (0.72, 0.75), L_WRI: (0.25, -0.25)}),
}

# ── 景别: 决定骨架在画面中被裁到什么范围 ────────────────────
# (top_y, bottom_y) 单位=头高,neck 为 0。决定画面上下边界。
FRAMING: dict[str, tuple[float, float]] = {
    "extreme_close_up": (-1.15, -0.05),   # 只有脸
    "close_up":         (-1.30,  0.75),   # 头+肩
    "medium_close_up":  (-1.40,  1.90),   # 头到胸
    "medium":           (-1.55,  3.10),   # 头到腰
    "cowboy":           (-1.70,  4.60),   # 头到大腿
    "full_body":        (-1.90,  6.90),   # 全身
    "wide":             (-3.40,  8.60),   # 全身+周围空间
    "extreme_wide":     (-7.00, 13.00),   # 人物很小
}


def render(pose: str = "standing",
           framing: str = "full_body",
           size: tuple[int, int] = (512, 768),
           flip: bool = False,
           rotate_deg: float = 0.0,
           offset_x: float = 0.0,
           line_w: int | None = None,
           dot_r: int | None = None) -> Image.Image:
    """
    渲染一张 openpose 骨架图。

    pose       姿势名(见 POSES)
    framing    景别名(见 FRAMING) —— 这就是"镜头"
    flip       水平翻转(角色朝向)
    rotate_deg 画面旋转 —— 用来做 Dutch angle
    offset_x   水平偏移,单位=头高。做三分法构图/过肩镜头
    """
    if pose not in POSES:
        raise KeyError(f"未知姿势 {pose!r},可用: {sorted(POSES)}")
    if framing not in FRAMING:
        raise KeyError(f"未知景别 {framing!r},可用: {sorted(FRAMING)}")

    W, H = size
    top, bot = FRAMING[framing]
    span = bot - top
    scale = H / span                      # 像素 / 头高
    cx = W / 2 + offset_x * scale

    pts: dict[int, tuple[float, float]] = {}
    for k, (bx, by) in POSES[pose].items():
        x = -bx if flip else bx
        pts[k] = (cx + x * scale, (by - top) * scale)

    if rotate_deg:
        rad = math.radians(rotate_deg)
        c, s = math.cos(rad), math.sin(rad)
        ox, oy = W / 2, H / 2
        pts = {k: (ox + (x - ox) * c - (y - oy) * s,
                   oy + (x - ox) * s + (y - oy) * c)
               for k, (x, y) in pts.items()}

    # 线宽随景别自适应 —— 特写时骨架被放很大,线也要粗
    if line_w is None:
        line_w = max(2, int(scale * 0.055))
    if dot_r is None:
        dot_r = max(2, int(scale * 0.035))

    img = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(img)

    margin = max(W, H) * 0.6   # 出画一点仍绘制,保证裁切自然

    def visible(p):
        return -margin < p[0] < W + margin and -margin < p[1] < H + margin

    for i, (a, b) in enumerate(LIMBS):
        pa, pb = pts.get(a), pts.get(b)
        if pa and pb and (visible(pa) or visible(pb)):
            d.line([pa, pb], fill=COLORS[i % len(COLORS)], width=line_w)

    for k, p in pts.items():
        if visible(p):
            d.ellipse([p[0] - dot_r, p[1] - dot_r, p[0] + dot_r, p[1] + dot_r],
                      fill=COLORS[k % len(COLORS)])
    return img


if __name__ == "__main__":
    import os
    out = os.path.expanduser("~/ComfyUI/input/poses")
    os.makedirs(out, exist_ok=True)
    n = 0
    for fr in FRAMING:
        img = render("standing", fr)
        img.save(os.path.join(out, f"framing_{fr}.png")); n += 1
    for ps in POSES:
        img = render(ps, "full_body")
        img.save(os.path.join(out, f"pose_{ps}.png")); n += 1
    print(f"生成 {n} 张骨架图 -> {out}")
