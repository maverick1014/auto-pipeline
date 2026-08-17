#!/usr/bin/env python3
"""
圣经经文抓取 —— 只抓公共领域译本
================================
铁律第 1 条: 绝不静默修改圣经原文。

因此本脚本:
  - 原样保存抓取到的文本(sourceText),一个字都不动
  - 繁→简转换结果单独存在 simplifiedText 字段,并记录 transform 来源
  - 记录 translationId / license / canRedistribute,供导出时判断
  - 只允许公共领域译本。RCUVSS / NIV 等有版权的必须用户自行导入

用法:
    python tools/fetch_bible.py REV 1
    python tools/fetch_bible.py GEN 1 --translation cuv
"""
from __future__ import annotations
import argparse, json, os, ssl, sys, urllib.request


def _ssl_ctx():
    """python.org 版 Python 在 macOS 上默认没有 CA 包,会 CERTIFICATE_VERIFY_FAILED。
    根治办法是跑 /Applications/Python 3.x/Install Certificates.command,
    这里再用 certifi 兜一层,换环境也不会挂。"""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()

API = "https://bible-api.com/data"
OUT_ROOT = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "bible")

# 只有这里列出的译本才允许自动抓取
ALLOWED = {
    "cuv": {
        "name": "Chinese Union Version (和合本 1919)",
        "license": "public-domain",
        "canRedistribute": True,
        "script": "traditional",
        "languageCode": "zh-tw",
    },
    "web": {
        "name": "World English Bible",
        "license": "public-domain",
        "canRedistribute": True,
        "script": "latin",
        "languageCode": "en",
    },
}


def fetch(book: str, chapter: int, translation: str) -> dict:
    if translation not in ALLOWED:
        raise SystemExit(
            f"❌ 拒绝抓取 {translation!r} —— 只允许公共领域译本 "
            f"{sorted(ALLOWED)}。RCUVSS / NIV 有版权,必须自行导入。")
    url = f"{API}/{translation}/{book.upper()}/{chapter}"
    with urllib.request.urlopen(url, timeout=45, context=_ssl_ctx()) as r:
        return json.loads(r.read())


def build(raw: dict, book: str, chapter: int, translation: str) -> dict:
    meta = ALLOWED[translation]
    verses = []
    simplifier = None
    if meta["script"] == "traditional":
        try:
            from opencc import OpenCC
            simplifier = OpenCC("t2s")
        except ImportError:
            print("⚠️ 未装 opencc,跳过简体转换 (pip install opencc-python-reimplemented)",
                  file=sys.stderr)

    for v in raw.get("verses", []):
        text = v.get("text", "").strip()
        rec = {"verse": v.get("verse"), "sourceText": text}
        if simplifier:
            # 转换结果单独存放 —— 原文永不覆盖
            rec["simplifiedText"] = simplifier.convert(text)
        verses.append(rec)

    return {
        "translationId": translation,
        "translationName": meta["name"],
        "license": meta["license"],
        "canRedistribute": meta["canRedistribute"],
        "languageCode": meta["languageCode"],
        "sourceScript": meta["script"],
        "source": f"{API}/{translation}/{book.upper()}/{chapter}",
        "transform": ("opencc t2s (繁→简) —— 仅存于 simplifiedText,"
                      "sourceText 为原样抓取,未做任何修改")
        if simplifier else None,
        "book": book.upper(),
        "chapter": chapter,
        "verseCount": len(verses),
        "verses": verses,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", help="三字母书卷 ID,如 REV / GEN / JHN")
    ap.add_argument("chapter", type=int)
    ap.add_argument("--translation", default="cuv")
    a = ap.parse_args()

    doc = build(fetch(a.book, a.chapter, a.translation),
                a.book, a.chapter, a.translation)
    out_dir = os.path.join(OUT_ROOT, a.translation)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{a.book.lower()}-{a.chapter}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    print(f"✅ {doc['translationName']}  {a.book.upper()} {a.chapter}  "
          f"{doc['verseCount']} 节")
    print(f"   license: {doc['license']}  可再分发: {doc['canRedistribute']}")
    print(f"   -> {path}")


if __name__ == "__main__":
    main()
