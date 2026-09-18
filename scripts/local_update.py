#!/usr/bin/env python3
"""本地同步：抓取课表 → 加密 → 提交 → 推送。

为什么需要它：学校教务系统的 WAF 会拦截数据中心 / 境外 IP，
GitHub Actions 的机器抓不到课表，所以抓取放在你自己的电脑上跑。

用法::

    python scripts/local_update.py            # 手动同步
    python scripts/local_update.py --auto     # 计划任务用（不提问、不暂停）
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

from hhu import auth, crypto, parse  # noqa: E402

SECRETS_FILE = ROOT / "scripts" / "local_secrets.json"
OUT_FILE = ROOT / "web" / "data" / "schedule.enc.json"


def log(message: str) -> None:
    print(message, flush=True)


def load_secrets() -> dict:
    if not SECRETS_FILE.is_file():
        log(f"缺少凭据文件：{SECRETS_FILE}")
        log("请复制 scripts/local_secrets.example.json 为 local_secrets.json 并填入学号、密码、口令。")
        raise SystemExit(1)
    data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    for key in ("username", "password", "passphrase"):
        if not data.get(key):
            log(f"凭据文件缺少字段：{key}")
            raise SystemExit(1)
    return data


def fetch_payload(secrets: dict, attempts: int = 3) -> dict:
    """登录并抓取，网络抖动时重试。"""
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            session = auth.login(secrets["username"], secrets["password"])
            schedule_html = auth.fetch_schedule_html(session)
            calendar_html = auth.fetch_calendar_html(session)
            break
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log(f"  第 {attempt} 次抓取失败：{exc}")
            if attempt < attempts:
                time.sleep(5 * attempt)
    else:
        log(f"抓取失败：{last_error}")
        raise SystemExit(1)

    schedule = parse.parse_schedule_page(schedule_html)
    calendar = parse.parse_calendar_page(calendar_html)
    fetched_at = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds")
    return {
        "version": 1,
        "term": schedule.get("term") or calendar.get("term", ""),
        "termName": calendar.get("termName") or schedule.get("termName", ""),
        "startDate": calendar.get("startDate", ""),
        "totalWeeks": calendar.get("totalWeeks", 0),
        "weeks": calendar.get("weeks", []),
        "fetchedAt": fetched_at,
        "periods": schedule.get("periods", []),
        "courses": schedule.get("courses", []),
        "otherCourses": schedule.get("otherCourses", []),
    }


def run_git(args: list[str], retries: int = 4) -> bool:
    """执行 git 命令；网络类命令失败时重试（国内访问 GitHub 经常抖动）。"""
    for attempt in range(1, retries + 1):
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0:
            return True
        message = (result.stderr or result.stdout or "").strip().splitlines()
        detail = message[-1][:120] if message else "未知错误"
        if attempt == retries:
            log(f"  git {args[0]} 失败：{detail}")
            return False
        log(f"  git {args[0]} 第 {attempt} 次失败（{detail}），重试…")
        time.sleep(4 * attempt)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="本地抓取课表并推送到 GitHub")
    parser.add_argument("--auto", action="store_true", help="计划任务模式：不输出多余内容")
    args = parser.parse_args(argv)

    log("=== 河海课表 · 本地同步 ===")
    secrets = load_secrets()
    payload = fetch_payload(secrets, attempts=1 if args.auto else 3)
    log(f"学期：{payload['term']}（{payload['termName']}）")
    log(f"第 1 周起始：{payload['startDate'] or '未知'}，共 {payload['totalWeeks']} 周")
    log(f"课程安排：{len(payload['courses'])} 条，无课表课程 {len(payload['otherCourses'])} 门")

    # fetchedAt 每次都会变，不能参与哈希，否则永远判定为“有变化”
    stable = {key: value for key, value in payload.items() if key != "fetchedAt"}
    new_hash = crypto.payload_hash(stable)
    previous_hash = ""
    if OUT_FILE.is_file():
        try:
            previous_hash = json.loads(OUT_FILE.read_text(encoding="utf-8")).get("payloadHash", "")
        except (json.JSONDecodeError, OSError):
            previous_hash = ""

    if new_hash == previous_hash:
        log("课表数据没有变化，无需提交。")
        return 0

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    envelope = crypto.encrypt_json(stable, secrets["passphrase"], updated=payload["fetchedAt"])
    OUT_FILE.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"已生成加密数据：{OUT_FILE.relative_to(ROOT)}")

    if not run_git(["add", str(OUT_FILE.relative_to(ROOT))]):
        return 1
    if not run_git(["commit", "-m", f"chore: 课表数据更新 {payload['fetchedAt'][:16]}"]):
        return 1
    if not run_git(["push"]):
        log("推送失败：数据已保存在本地，网络恢复后重新运行本脚本即可。")
        return 1
    log("推送成功，GitHub Pages 会在 1 分钟左右自动更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
