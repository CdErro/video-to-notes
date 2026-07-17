#!/usr/bin/env python3
"""
Whisper SRT 修正（数据驱动版）

设计原则：
  - 所有修正规则必须来自对真实 Whisper 输出的观察
  - 英文技术词一般不需修正（Whisper 识别英文准确率高）
  - 重点是中文同音/近音错误：专业术语 / 人名 / 课程常用词

工作流程：
  1. Whisper 产出原始 SRT
  2. 人工/LLM 审阅一小段，收集 wrong → right pair
  3. 追加到 `glossary_<course>.json`
  4. 本脚本批量应用到整份 SRT
  5. 需要语义级修正时，再跑 `llm_correct_srt.py`

用法:
    python3 correct_srt.py input.srt [-o output.srt] [--context CONTEXT] [--stats]
    python3 correct_srt.py audio.srt --domain nju-os --stats
"""

import argparse
import json
import re
from pathlib import Path

from glossary import DEFAULT_USER_ROOT, detect_domains, replacements


def parse_srt(content: str) -> list[dict]:
    """粗略解析 SRT 为 {index, time, text} 列表。"""
    blocks = re.split(r"\n\n+", content.strip())
    entries = []
    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) >= 3:
            entries.append(
                {
                    "index": lines[0],
                    "time": lines[1],
                    "text": "\n".join(lines[2:]),
                }
            )
    return entries


def dump_srt(entries: list[dict]) -> str:
    """写回 SRT 字符串。"""
    return "\n\n".join(f"{e['index']}\n{e['time']}\n{e['text']}" for e in entries) + "\n"


def apply_glossary(text: str, glossary: dict) -> tuple[str, int]:
    """应用词表。支持两种条目格式：
        "wrong_string": "right_string"      # 纯字符串替换
        "pattern": {"replace": "x", "regex": true}  # 正则替换
    返回 (新文本, 命中次数)。
    """
    count = 0
    for key, val in glossary.items():
        if isinstance(val, dict) and val.get("regex"):
            text, n = re.subn(key, val.get("replace", ""), text)
        else:
            assert isinstance(val, str)
            if key in text:
                n = text.count(key)
                text = text.replace(key, val)
            else:
                n = 0
        count += n
    return text, count


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", help="输入 SRT")
    p.add_argument("-o", "--output", help="输出 SRT (默认覆盖输入)")
    p.add_argument("-g", "--glossary", help="兼容旧版的单个 JSON 词表")
    p.add_argument("--domain", action="append", help="词典领域；可重复指定")
    p.add_argument("--context", default="", help="用于自动识别领域")
    p.add_argument("--glossary-root", type=Path, default=DEFAULT_USER_ROOT)
    p.add_argument("--stats", action="store_true", help="打印替换统计")
    args = p.parse_args()

    inp = Path(args.input)
    out = Path(args.output) if args.output else inp
    if args.glossary:
        glossary = json.loads(Path(args.glossary).read_text(encoding="utf-8"))
    else:
        domains = args.domain or detect_domains(args.context)
        if "general" not in domains:
            domains.insert(0, "general")
        glossary = replacements(domains, args.glossary_root)

    content = inp.read_text(encoding="utf-8")
    entries = parse_srt(content)

    total = 0
    for e in entries:
        e["text"], n = apply_glossary(e["text"], glossary)
        total += n

    out.write_text(dump_srt(entries), encoding="utf-8")
    if args.stats:
        print(f"修正完成 -> {out}")
        print(f"  词表条目数：{len(glossary)}")
        print(f"  命中次数：{total}")


if __name__ == "__main__":
    main()
