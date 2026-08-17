#!/usr/bin/env python3
"""
Episode 生成器 —— storyboard JSON → panel 图
==========================================
铁律执行点:
  · prompt 按固定顺序拼装,DNA 段由代码注入(不经过 LLM)
  · 每个角色锁定 seed —— 纯 prompt 方案下这是最强的一致性手段
  · 对白/旁白**不进 prompt**,后期作为可编辑图层叠加
  · 生成走 HardwareGuard,热限速自动降温

用法:
    python tools/generate_episode.py rev-01
    python tools/generate_episode.py rev-01 --panels p09,p10,p11   # 只重生成指定格
    python tools/generate_episode.py rev-01 --steps 24 --variant 2 # 换一版
"""
from __future__ import annotations
import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workflows import assemble_prompt, txt2img, GLOBAL_NEGATIVE, FRAMING
from comfy_client import HardwareGuard, submit, contact_sheet, ram_free_gb, OUT_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "episodes")


def load(episode_id: str):
    with open(os.path.join(DATA, f"{episode_id}.json"), encoding="utf-8") as f:
        ep = json.load(f)
    with open(os.path.join(DATA, f"{episode_id}-storyboard.json"),
              encoding="utf-8") as f:
        sb = json.load(f)
    return ep, sb


def build_prompt(panel: dict, ep: dict) -> tuple[str, str, tuple[int, int]]:
    """返回 (正向, 负向, 画幅)。

    景别三重强制: 画幅 + 正向加权 + **负向排除不想要的景别**。
    实测第三条最有效 —— 只写正向 "close-up" 基本无用。
    """
    chars = {c["id"]: c for c in ep["characters"]}
    locs = {l["id"]: l for l in ep["locations"]}
    fr = FRAMING.get(panel.get("framing", "full_body"), FRAMING["full_body"])

    ids = [c for c in panel.get("characters", []) if c in chars]
    char_dna = ", ".join(chars[c]["dna"] for c in ids)
    if panel.get("subjectOverride"):
        # 既不要完整角色 DNA、也不是纯风景的格子 —— 例如"一只发光的手"、
        # "火焰本身"。角色 DNA 会把整个人物拉进来,"no humans" 又会压掉主体。
        char_dna = panel["subjectOverride"]
    elif not ids:
        char_dna = "no humans, no people, scenery and objects only"

    loc = locs.get(panel.get("location"), {})
    camera = ", ".join(x for x in (fr["pos"], panel.get("angle")) if x)

    # 统一背景 —— 样张验证过的一致性捷径: 全篇共用同一片金色云海。
    # 统一环境比统一角色脸容易得多,视觉统一感却一样强。
    style = ep["style"]["dna"]
    if ep["style"].get("unifiedBackground") and not panel.get("noUnifiedBackground"):
        style += ", " + ep["style"]["unifiedBackground"]

    positive = assemble_prompt(
        style=style,
        character_dna=char_dna,
        location_dna=loc.get("dna", ""),
        camera=camera,
        lighting=panel.get("lighting", ""),
        action=panel.get("action", ""),
        emotion=panel.get("emotion", ""),
        composition=panel.get("composition", ""),
    )
    if panel.get("extraPositive"):
        positive += ", " + panel["extraPositive"]

    neg = [GLOBAL_NEGATIVE, fr["neg"]]
    neg += [chars[c]["extraNegative"] for c in ids if chars[c].get("extraNegative")]
    if panel.get("extraNegative"):
        neg.append(panel["extraNegative"])

    size = tuple(panel.get("size") or fr["size"])
    return positive, ", ".join(neg), size


def panel_seed(panel: dict, ep: dict, variant: int) -> int:
    """角色锁定 seed —— 同一角色所有格用同一 seed,脸部结构最稳。
    无角色的格子按 panel id 派生一个稳定 seed。"""
    chars = {c["id"]: c for c in ep["characters"]}
    ids = [c for c in panel.get("characters", []) if c in chars]
    if ids:
        base = chars[ids[0]]["seed"]
    else:
        digits = "".join(c for c in panel["id"] if c.isdigit())
        base = 5000 + (int(digits) if digits else sum(map(ord, panel["id"]))) * 17
    return base + variant * 10007


def manifest_path(episode: str) -> str:
    return os.path.join(DATA, f"{episode}-generated.json")


def load_manifest(episode: str) -> dict:
    p = manifest_path(episode)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {"episodeId": episode, "panels": []}


def save_manifest(episode: str, doc: dict, entries: dict) -> None:
    """每生成一格就落盘 —— 中途被杀也不会丢记录。
    铁律第 4 条: 生成资产只增不减,旧版本进 history。"""
    doc["panels"] = sorted(entries.values(), key=lambda p: p["panel"])
    with open(manifest_path(episode), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def merge_entry(entries: dict, rec: dict) -> None:
    old = entries.get(rec["panel"])
    if old:
        rec["history"] = (old.get("history", []) +
                          [{k: v for k, v in old.items() if k != "history"}])
    entries[rec["panel"]] = rec


def rebuild_from_disk(episode: str, ep: dict, sb: dict, variant: int) -> dict:
    """从 ComfyUI output 目录重建 manifest。
    prompt/seed 都是纯函数算出来的,可精确复原;文件取每个 panel 前缀的最新一个。"""
    entries = {}
    for p in sb["panels"]:
        pref = f"{episode}_{p['id']}_"
        cands = [f for f in os.listdir(OUT_DIR)
                 if f.startswith(pref) and f.endswith(".png")]
        if not cands:
            continue
        newest = max(cands, key=lambda f: os.path.getmtime(
            os.path.join(OUT_DIR, f)))
        positive, negative, (w, h) = build_prompt(p, ep)
        entries[p["id"]] = {
            "panel": p["id"], "file": newest,
            "seed": panel_seed(p, ep, variant),
            "framing": p.get("framing"), "size": f"{w}x{h}",
            "seconds": None, "prompt": positive, "negative": negative,
            "recovered": True,
        }
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--panels", help="逗号分隔,只生成这些格")
    ap.add_argument("--steps", type=int, default=22)
    ap.add_argument("--cfg", type=float, default=7.5)
    ap.add_argument("--variant", type=int, default=0, help="换一版(改变 seed 偏移)")
    ap.add_argument("--rebuild-manifest", action="store_true",
                    help="不生成,只从磁盘已有图片重建 manifest")
    a = ap.parse_args()

    ep, sb = load(a.episode)

    if a.rebuild_manifest:
        doc = load_manifest(a.episode)
        entries = rebuild_from_disk(a.episode, ep, sb, a.variant)
        save_manifest(a.episode, doc, entries)
        print(f"✅ 从磁盘重建 {len(entries)} 格 -> {manifest_path(a.episode)}")
        missing = [p["id"] for p in sb["panels"] if p["id"] not in entries]
        if missing:
            print(f"   缺失: {', '.join(missing)}")
        return

    panels = sb["panels"]
    if a.panels:
        want = {p.strip() for p in a.panels.split(",")}
        panels = [p for p in panels if p["id"] in want]

    guard = HardwareGuard()
    print("=" * 78)
    print(f"{ep['title']}   {len(panels)} 格")
    print(f"经文: {ep['passage']['translationName']}  ({ep['passage']['license']})")
    print(f"RAM free: {ram_free_gb():.2f} GB")
    print("=" * 78)

    doc = load_manifest(a.episode)
    doc.update({"variant": a.variant, "steps": a.steps, "cfg": a.cfg})
    entries = {p["panel"]: p for p in doc.get("panels", [])}

    results, files, labels = [], [], []
    t_start = time.time()
    for p in panels:
        positive, negative, (w, h) = build_prompt(p, ep)
        seed = panel_seed(p, ep, a.variant)

        guard.check()
        wf = txt2img(positive, negative, seed=seed,
                     width=w, height=h, steps=a.steps, cfg=a.cfg,
                     prefix=f"{a.episode}_{p['id']}")
        out, dt = submit(wf)
        rec = {"panel": p["id"], "file": out, "seed": seed,
               "framing": p.get("framing"), "size": f"{w}x{h}",
               "seconds": round(dt, 1),
               "prompt": positive, "negative": negative}
        results.append(rec)
        merge_entry(entries, rec)
        save_manifest(a.episode, doc, entries)   # ← 逐格落盘,中断也不丢
        files.append(out)
        labels.append(f"{p['id']} {p.get('framing','')}")
        print(f"  {p['id']}  {p.get('framing',''):18s} {w}x{h:<4d} "
              f"seed={seed:<6d} {dt:6.1f}s -> {out}", flush=True)

    sheet = os.path.join(OUT_DIR, f"{a.episode}_SHEET.png")
    contact_sheet(files, labels, sheet, cols=4, thumb=(224, 336))

    man = manifest_path(a.episode)
    total = time.time() - t_start
    print("-" * 78)
    print(f"完成 {len(results)} 格   总耗时 {total/60:.1f} 分钟   "
          f"均值 {total/max(1,len(results)):.1f}s/格")
    print(f"对照图: {sheet}")
    print(f"记录:   {man}")


if __name__ == "__main__":
    main()
