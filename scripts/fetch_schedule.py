#!/usr/bin/env python3
"""抓取河海大学课表，输出明文 JSON（可选）与口令加密文件。

用法::

    python scripts/fetch_schedule.py \
        --out web/data/schedule.enc.json \
        [--plain build/schedule.json] \
        [--secrets-file scripts/local_secrets.json]

凭据来源优先级：命令行参数 > 环境变量 > secrets 文件。
对应键名：username / password / passphrase（环境变量：HHU_USERNAME、HHU_PASSWORD、
SCHEDULE_PASSPHRASE）。脚本任何情况下都不会打印凭据。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from hhu import auth, crypto, parse  # noqa: E402

CHINA_TZ = dt.timezone(dt.timedelta(hours=8))
VERSION = 1


def _load_secrets(path: str | None) -> dict:
    if not path:
        return {}
    file = Path(path)
    if not file.is_file():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"secrets 文件不是合法 JSON：{exc}") from exc
    return data if isinstance(data, dict) else {}


def _resolve(cli_value, env_name: str, secrets: dict, key: str, label: str) -> str:
    value = cli_value or os.environ.get(env_name) or secrets.get(key)
    if not value:
        raise SystemExit(f"缺少{label}：请用 --{key.replace('_', '-')}、环境变量 {env_name} 或 secrets 文件提供")
    return str(value)


def build_schedule(schedule_html: str, calendar_html: str) -> dict:
    """把两个页面合并成 App 使用的课表数据。"""
    schedule = parse.parse_schedule_page(schedule_html)
    calendar = parse.parse_calendar_page(calendar_html)

    term = schedule.get("term") or calendar.get("term") or ""
    term_name = calendar.get("termName") or schedule.get("termName") or term
    return {
        "version": VERSION,
        "term": term,
        "termName": term_name,
        "startDate": calendar.get("startDate", ""),
        "totalWeeks": calendar.get("totalWeeks", 0),
        "weeks": calendar.get("weeks", []),
        "fetchedAt": dt.datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
        "periods": schedule.get("periods", []),
        "courses": schedule.get("courses", []),
        "otherCourses": schedule.get("otherCourses", []),
    }


def fetch_all(username: str, password: str, attempts: int = 3) -> tuple[str, str]:
    """登录并抓取课表页与教学周历页，网络抖动时自动重试。"""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            session = auth.login(username, password)
            return auth.fetch_schedule_html(session), auth.fetch_calendar_html(session)
        except Exception as exc:  # noqa: BLE001 - 重试后统一抛出
            last_error = exc
            if attempt < attempts:
                time.sleep(5 * attempt)
    raise SystemExit(f"抓取失败：{last_error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="抓取河海大学课表并加密输出")
    parser.add_argument("--out", default="web/data/schedule.enc.json", help="加密输出路径")
    parser.add_argument("--plain", default="", help="明文 JSON 输出路径（调试用，切勿提交）")
    parser.add_argument("--username", default="", help="学号")
    parser.add_argument("--password", default="", help="密码")
    parser.add_argument("--passphrase", default="", help="加密口令")
    parser.add_argument("--secrets-file", default="", help="本地凭据 JSON（已被 .gitignore 忽略）")
    parser.add_argument("--iterations", type=int, default=crypto.DEFAULT_ITERATIONS, help="PBKDF2 迭代次数")
    parser.add_argument("--force", action="store_true", help="数据未变化时也重新写文件")
    args = parser.parse_args(argv)

    secrets = _load_secrets(args.secrets_file)
    username = _resolve(args.username, "HHU_USERNAME", secrets, "username", "学号")
    password = _resolve(args.password, "HHU_PASSWORD", secrets, "password", "密码")
    passphrase = _resolve(args.passphrase, "SCHEDULE_PASSPHRASE", secrets, "passphrase", "加密口令")

    schedule_html, calendar_html = fetch_all(username, password)
    data = build_schedule(schedule_html, calendar_html)

    stable = {key: value for key, value in data.items() if key != "fetchedAt"}
    new_hash = crypto.payload_hash(stable)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = ""
    if out_path.is_file():
        try:
            previous_hash = json.loads(out_path.read_text(encoding="utf-8")).get("payloadHash", "")
        except (json.JSONDecodeError, OSError):
            previous_hash = ""

    changed = new_hash != previous_hash
    if changed or args.force:
        envelope = crypto.encrypt_json(stable, passphrase, iterations=args.iterations, updated=data["fetchedAt"])
        out_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.plain:
        plain_path = Path(args.plain)
        plain_path.parent.mkdir(parents=True, exist_ok=True)
        plain_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"学期：{data['term']}（{data['termName']}）")
    print(f"第 1 周起始：{data['startDate'] or '未知'}，共 {data['totalWeeks']} 周")
    print(f"课程安排：{len(data['courses'])} 条，无课表课程 {len(data['otherCourses'])} 门")
    print(f"输出：{out_path}{'' if (changed or args.force) else '（数据无变化，保持原文件）'}")
    print("CHANGED=" + ("1" if changed else "0"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
