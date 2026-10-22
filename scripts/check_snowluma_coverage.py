#!/usr/bin/env python3
"""Compare action literals and protocol tables against SnowLuma's v1.14.x facts."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from snowluma_reverse.protocol.actions import SNOWLUMA_ACTIONS, SNOWLUMA_UNSUPPORTED  # noqa: E402
from snowluma_reverse.protocol.segments import SNOWLUMA_SEGMENTS  # noqa: E402

ACTION_PATTERN = re.compile(
    r"(?:call_action(?:_data)?|_safe_call_action_data|safe_call_action_data|_dispatch)\s*\(\s*['\"]([^'\"]+)['\"]"
    r"|action_name\s*=\s*['\"]([^'\"]+)['\"]"
)
API_PATTERN = re.compile(r"@API\(\s*['\"]adapter\.[^.'\"]+\.[^.'\"]+\.([^.'\"]+)['\"]")
NOTICE_TYPES = "bot_offline essence friend_add friend_recall group_admin group_ban group_card group_decrease group_increase group_msg_emoji_like group_recall group_upload notify".split()
NOTIFY_TYPES = "poke group_name title input_status profile_like".split()


def collect_actions() -> set[str]:
    found: set[str] = set()
    for file in (ROOT / "snowluma_reverse").rglob("*.py"):
        if file.name == "actions.py":
            continue
        for match in ACTION_PATTERN.finditer(file.read_text(encoding="utf-8")):
            found.add(match.group(1) or match.group(2))
    return found


def collect_api_action_names() -> set[str]:
    found: set[str] = set()
    for file in (ROOT / "snowluma_reverse" / "apis").glob("*.py"):
        for match in API_PATTERN.finditer(file.read_text(encoding="utf-8")):
            found.add(match.group(1))
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    called = collect_actions()
    api_names = collect_api_action_names()
    unregistered = called - SNOWLUMA_ACTIONS - SNOWLUMA_UNSUPPORTED
    unsupported = SNOWLUMA_UNSUPPORTED
    aligned = (called | api_names) & SNOWLUMA_ACTIONS - {"SnowLuma"}
    api_aligned = api_names & aligned
    internal_aligned = aligned - api_aligned
    unused = SNOWLUMA_ACTIONS - called - api_names - {"SnowLuma"}
    print(f"已对齐: {len(aligned)}")
    print(f"  已封装 @API: {len(api_aligned)}")
    print(f"  内部使用: {len(internal_aligned)}")
    print(f"调用但未注册: {len(unregistered)}")
    print(f"按设计不支持: {len(unsupported)}")
    print(f"注册但未使用: {len(unused)}")
    for title, names in (("调用但未注册", sorted(unregistered)), ("按设计不支持", sorted(unsupported)), ("注册但未使用", sorted(unused))):
        print(f"{title}明细: {', '.join(names) if names else '（无）'}")

    if args.markdown:
        rows = ["# SnowLuma 协议覆盖表", "", "## Action 覆盖", "", "| 分类 | 数量 | Action |", "|---|---:|---|"]
        rows += [f"| 已封装 @API | {len(api_aligned)} | {', '.join(sorted(api_aligned)) or '—'} |",
                 f"| 内部使用 | {len(internal_aligned)} | {', '.join(sorted(internal_aligned))} |",
                 f"| 按设计不支持 | {len(SNOWLUMA_UNSUPPORTED)} | {', '.join(sorted(SNOWLUMA_UNSUPPORTED))} |",
                 f"| 未使用 | {len(unused)} | {', '.join(sorted(unused))} |"]
        rows += ["", "## Event 覆盖", "", "| 类型 | 映射 |", "|---|---|"]
        rows += [f"| notice_type `{name}` | 普通 MaiBot 通知（系统文本） |" for name in NOTICE_TYPES]
        rows += [f"| notify `{name}` | 普通 MaiBot 通知（输入状态由配置控制） |" for name in NOTIFY_TYPES]
        rows += ["| post_type `message` | 入站消息编解码器 |", "| post_type `notice` | 通知编解码器 |", "| post_type `meta_event` | 运行态与心跳观测 |", "| post_type 未知 | debug 后跳过 |",
                 "", "## Segment 覆盖", "", "| 类型 | 入站 | 出站 | 降级策略 |", "|---|---|---|---|"]
        supported = {"text", "at", "face", "image", "record", "video", "file", "forward", "json", "xml", "markdown", "reply"}
        for name in sorted(SNOWLUMA_SEGMENTS):
            inbound = "支持" if name in supported or name in {"flash_file", "mface", "poke", "inline_keyboard"} else "占位"
            outbound = "支持" if name in {"text", "at", "face", "image", "record", "video", "file", "forward", "json", "xml", "reply"} else "文本降级"
            fallback = {"flash_file": "文本+文件名/大小/URL，不下载", "mface": "摘要或类型 ID 文本", "poke": "[戳一戳]", "inline_keyboard": "[内联键盘]"}.get(name, "未知类型占位" if name not in supported else "—")
            rows.append(f"| `{name}` | {inbound} | {outbound} | {fallback} |")
        rows += ["", "数据来源：SnowLuma 源码注册表 + 官方 OpenAPI spec；事件字段据事件转换实现核对。", "重新生成：`uv run python scripts/check_snowluma_coverage.py --markdown docs/snowluma-coverage.md`", "SnowLuma 版本：源码副本 v1.14.x。", ""]
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text("\n".join(rows), encoding="utf-8")
    return 1 if args.check and unregistered else 0


if __name__ == "__main__":
    raise SystemExit(main())
