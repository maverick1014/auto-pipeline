#!/usr/bin/env python3
"""
ComfyUI 客户端 + 硬件保护
=========================
Bible AI Studio 所有批量生成都必须走这里,不要直接 POST /prompt。

硬件保护(针对 MacBook Pro M2 / 8GB):
  - 每张图前检查热压力,进入 throttling 就自动暂停降温
  - 检测电池模式并警告(电池下 macOS 会限制持续高负载性能)
  - 批次间强制冷却间隔,不连续硬跑
  - 磁盘空间检查,低于阈值直接停,避免 swap 把系统拖死
"""
from __future__ import annotations
import json, os, shutil, subprocess, time, urllib.request, uuid

HOST = "http://127.0.0.1:8188"
OUT_DIR = os.path.expanduser("~/ComfyUI/output")

# ── 硬件保护阈值 ────────────────────────────────────────────
COOLDOWN_EVERY = 10          # 每 N 张强制冷却一次
COOLDOWN_SECONDS = 60        # 冷却时长
THERM_PAUSE_SECONDS = 120    # 检测到热限速后暂停时长
MIN_FREE_GB = 8              # 磁盘低于此值直接中止


class HardwareGuard:
    """跑图前的硬件闸门 —— 宁可慢,不要把机器跑坏"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.count = 0
        self.warned_battery = False

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [guard] {msg}", flush=True)

    @staticmethod
    def thermal_throttled() -> bool:
        """macOS 热压力检测 —— 不需要 sudo"""
        try:
            out = subprocess.run(["pmset", "-g", "therm"], capture_output=True,
                                 text=True, timeout=10).stdout.lower()
        except Exception:
            return False
        # 有记录且不为 0 才算真的在限速
        for line in out.splitlines():
            if "cpu_speed_limit" in line or "cpu_available_cpus" in line:
                try:
                    val = int(line.split("=")[-1].strip())
                except ValueError:
                    continue
                if "cpu_speed_limit" in line and val < 100:
                    return True
        return False

    @staticmethod
    def on_battery() -> bool:
        try:
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True,
                                 text=True, timeout=10).stdout
        except Exception:
            return False
        return "Battery Power" in out

    @staticmethod
    def free_gb() -> float:
        return shutil.disk_usage("/System/Volumes/Data").free / 1e9

    def check(self) -> None:
        """每张图之前调用。会阻塞直到条件安全,或抛异常中止。"""
        free = self.free_gb()
        if free < MIN_FREE_GB:
            raise RuntimeError(
                f"磁盘只剩 {free:.1f} GB (阈值 {MIN_FREE_GB} GB) —— 中止。"
                " 8GB 内存机器磁盘满会导致 swap 失败,系统直接卡死。")

        if self.on_battery() and not self.warned_battery:
            self._log("⚠️ 正在用电池 —— macOS 会限制持续高负载性能,建议接电源")
            self.warned_battery = True

        if self.thermal_throttled():
            self._log(f"🌡️ 检测到热限速,暂停 {THERM_PAUSE_SECONDS}s 降温…")
            time.sleep(THERM_PAUSE_SECONDS)

        self.count += 1
        if self.count % COOLDOWN_EVERY == 0:
            self._log(f"❄️ 已生成 {self.count} 张,强制冷却 {COOLDOWN_SECONDS}s")
            time.sleep(COOLDOWN_SECONDS)


def submit(workflow: dict, save_node: str = "9", timeout: int = 1200
           ) -> tuple[str | None, float]:
    """提交 workflow,阻塞到完成。返回 (输出文件名, 耗时秒)。"""
    t0 = time.time()
    req = urllib.request.Request(
        f"{HOST}/prompt",
        data=json.dumps({"prompt": workflow,
                         "client_id": str(uuid.uuid4())}).encode(),
        headers={"Content-Type": "application/json"})
    pid = json.loads(urllib.request.urlopen(req, timeout=60).read())["prompt_id"]

    while True:
        h = json.loads(urllib.request.urlopen(
            f"{HOST}/history/{pid}", timeout=30).read())
        if pid in h:
            imgs = h[pid].get("outputs", {}).get(save_node, {}).get("images", [])
            return (imgs[0]["filename"] if imgs else None), time.time() - t0
        if time.time() - t0 > timeout:
            return None, time.time() - t0
        time.sleep(1.5)


def wait_ready(timeout: int = 180) -> bool:
    """等 ComfyUI 起来"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(f"{HOST}/system_stats", timeout=5).read()
            return True
        except Exception:
            time.sleep(2)
    return False


def ram_free_gb() -> float:
    try:
        d = json.loads(urllib.request.urlopen(
            f"{HOST}/system_stats", timeout=10).read())
        return d["system"]["ram_free"] / 1e9
    except Exception:
        return -1.0


def contact_sheet(files, labels, path, cols=5, thumb=(224, 336)):
    """拼对照图 —— 判断一致性靠肉眼,必须并排看"""
    from PIL import Image, ImageDraw
    files = list(files); labels = list(labels)
    rows = (len(files) + cols - 1) // cols
    pad, bar = 6, 20
    W = cols * (thumb[0] + pad) + pad
    H = rows * (thumb[1] + bar + pad) + pad
    sheet = Image.new("RGB", (W, H), (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    for i, (f, lb) in enumerate(zip(files, labels)):
        if not f:
            continue
        p = f if os.path.isabs(f) else os.path.join(OUT_DIR, f)
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB").resize(thumb, Image.LANCZOS)
        x = pad + (i % cols) * (thumb[0] + pad)
        y = pad + (i // cols) * (thumb[1] + bar + pad)
        sheet.paste(im, (x, y))
        d.text((x + 3, y + thumb[1] + 4), str(lb)[:32], fill=(210, 210, 215))
    sheet.save(path)
    return path
