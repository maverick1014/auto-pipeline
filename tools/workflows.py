#!/usr/bin/env python3
"""
ComfyUI workflow 构造器
=======================
铁律: prompt 必须由结构化片段按固定顺序拼装,LLM 只能填「可变」部分。

    GLOBAL_STYLE + CHARACTER_DNA + LOCATION_DNA
      + SCENE/CAMERA/LIGHTING/ACTION/EMOTION/COMPOSITION
      + NEGATIVE

DNA 段由代码注入,绝不交给 LLM 重写 —— 那是一致性崩掉的头号原因。
"""
from __future__ import annotations

CKPT_DEFAULT = "dreamshaper_8.safetensors"
CN_OPENPOSE = "control_v11p_sd15_openpose_fp16.safetensors"

# 项目级画风 —— 所有 episode 共用,永不随 panel 变化
GLOBAL_STYLE = (
    "masterpiece, best quality, highly detailed, "
    "(classical religious oil painting:1.3), (renaissance sacred art:1.2), "
    "painterly brushwork, soft luminous rendering, "
    "warm ivory and gold palette, volumetric god rays, "
    "biblical era, solemn reverent atmosphere"
)

# 全局负向 —— 含内容安全强制排除项
GLOBAL_NEGATIVE = (
    "lowres, bad anatomy, bad hands, missing fingers, "
    "extra digits, worst quality, low quality, jpeg artifacts, "
    "signature, watermark, text, letters, modern clothing, glasses, "
    "nude, nsfw, exposed, "
    "anime, manga, cel shading, flat colors, chibi, "
    "multiple views, 2boys, 2girls"
)


# ── 景别系统 ────────────────────────────────────────────────
# 实测教训: 纯靠正向 prompt 写 "close-up" 基本无效 —— SD1.5 有极强的
# "画全身站立人物" 先验。16 格里 13 格出成全身站姿。
#
# 三重强制:
#   1) 画幅本身就是景别信号 —— 特写用近方形/横幅,全身用高竖幅
#   2) 正向加权 (extreme close-up:1.5)
#   3) **把不想要的景别写进负向** —— 这条最有效
FRAMING = {
    "extreme_close_up": {
        "size": (576, 448),
        "pos": "(extreme close-up:1.5), (face fills the entire frame:1.4), "
               "macro detail, cropped tight",
        "neg": "full body, wide shot, cowboy shot, medium shot, legs, feet, "
               "whole body, distant, small figure, landscape",
    },
    "close_up": {
        "size": (512, 576),
        "pos": "(close-up:1.4), (head and shoulders only:1.3), portrait framing",
        "neg": "full body, wide shot, legs, feet, knees, whole body, "
               "distant, small figure",
    },
    "medium_close_up": {
        "size": (512, 640),
        "pos": "(medium close-up:1.35), (chest up:1.25), bust shot",
        "neg": "full body, wide shot, legs, feet, knees, whole body, distant",
    },
    "medium": {
        "size": (512, 704),
        "pos": "(medium shot:1.3), (waist up:1.2)",
        "neg": "full body, extreme wide shot, feet, distant tiny figure",
    },
    "cowboy": {
        "size": (512, 736),
        "pos": "(cowboy shot:1.3), (thighs up:1.2)",
        "neg": "extreme wide shot, feet, distant tiny figure",
    },
    "full_body": {
        "size": (512, 768),
        "pos": "(full body:1.3), (standing full figure:1.2)",
        "neg": "close-up, extreme close-up, cropped head, portrait",
    },
    "wide": {
        "size": (768, 512),
        "pos": "(wide shot:1.4), (small figure in vast environment:1.3), "
               "establishing shot",
        "neg": "close-up, portrait, face focus, cropped",
    },
    "extreme_wide": {
        "size": (832, 448),
        "pos": "(extreme wide shot:1.5), (tiny distant figure:1.4), "
               "vast landscape, establishing shot",
        "neg": "close-up, portrait, face focus, medium shot, cropped",
    },
    "insert": {   # 道具特写 —— 手、物件,不要人脸
        "size": (576, 512),
        "pos": "(extreme close-up on the object:1.5), (object fills frame:1.4), "
               "detail insert shot",
        "neg": "full body, face, portrait, wide shot, standing figure, "
               "whole person",
    },
}


def framing_size(key: str) -> tuple[int, int]:
    return FRAMING.get(key, FRAMING["full_body"])["size"]


def assemble_prompt(character_dna: str = "",
                    location_dna: str = "",
                    scene: str = "",
                    camera: str = "",
                    lighting: str = "",
                    action: str = "",
                    emotion: str = "",
                    composition: str = "",
                    style: str = GLOBAL_STYLE) -> str:
    """按铁律顺序拼装正向 prompt。空段自动跳过。"""
    parts = [style, character_dna, location_dna, scene,
             camera, lighting, action, emotion, composition]
    return ", ".join(p.strip().strip(",") for p in parts if p and p.strip())


def txt2img(positive: str, negative: str, seed: int,
            width: int = 512, height: int = 768, steps: int = 20,
            cfg: float = 7.0, ckpt: str = CKPT_DEFAULT,
            sampler: str = "dpmpp_2m", scheduler: str = "karras",
            prefix: str = "img") -> dict:
    """基础 txt2img。SaveImage 节点固定为 "9"。"""
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg,
            "sampler_name": sampler, "scheduler": scheduler, "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0]}},
        "4": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode",
              "inputs": {"text": positive, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode",
              "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def txt2img_openpose(positive: str, negative: str, seed: int,
                     pose_image: str,
                     strength: float = 0.85,
                     start_pct: float = 0.0,
                     end_pct: float = 0.85,
                     width: int = 512, height: int = 768, steps: int = 20,
                     cfg: float = 7.0, ckpt: str = CKPT_DEFAULT,
                     controlnet: str = CN_OPENPOSE,
                     sampler: str = "dpmpp_2m", scheduler: str = "karras",
                     prefix: str = "cn") -> dict:
    """
    带 openpose 控制的 txt2img —— 镜头/构图由骨架图决定,不靠 prompt。

    pose_image  相对 ~/ComfyUI/input/ 的路径,如 "poses/framing_close_up.png"
    strength    控制强度。1.0 过硬会牺牲画质,0.85 是平衡点
    end_pct     0.85 = 后 15% 步数放开控制,让模型补细节
    """
    wf = txt2img(positive, negative, seed, width, height, steps, cfg,
                 ckpt, sampler, scheduler, prefix)
    wf["10"] = {"class_type": "LoadImage", "inputs": {"image": pose_image}}
    wf["11"] = {"class_type": "ControlNetLoader",
                "inputs": {"control_net_name": controlnet}}
    wf["12"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": ["6", 0], "negative": ["7", 0],
        "control_net": ["11", 0], "image": ["10", 0],
        "strength": strength,
        "start_percent": start_pct, "end_percent": end_pct}}
    # KSampler 改接 ControlNet 的输出
    wf["3"]["inputs"]["positive"] = ["12", 0]
    wf["3"]["inputs"]["negative"] = ["12", 1]
    return wf
