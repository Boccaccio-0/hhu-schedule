#!/usr/bin/env python3
"""生成演示用课表数据（tests/fixtures/sample.plain.json 与 sample.enc.json）。

数据来自脱敏样本页面，完全虚构，可安全提交；口令固定为 demo-pass，
用于加解密测试与本地网页预览。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from hhu import crypto, parse  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEMO_PASSPHRASE = "demo-pass"
FIXED_TIME = "2026-09-18T12:00:00+08:00"


def build_payload() -> dict:
    schedule = parse.parse_schedule_page((FIXTURES / "xskb_list.html").read_text(encoding="utf-8"))
    calendar = parse.parse_calendar_page((FIXTURES / "jxzl.html").read_text(encoding="utf-8"))
    return {
        "version": 1,
        "term": schedule["term"],
        "termName": calendar["termName"],
        "startDate": calendar["startDate"],
        "totalWeeks": calendar["totalWeeks"],
        "weeks": calendar["weeks"],
        "fetchedAt": FIXED_TIME,
        "periods": schedule["periods"],
        "courses": schedule["courses"],
        "otherCourses": schedule["otherCourses"],
    }


def main() -> int:
    payload = build_payload()
    (FIXTURES / "sample.plain.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    envelope = crypto.encrypt_json(payload, DEMO_PASSPHRASE, updated=FIXED_TIME)
    (FIXTURES / "sample.enc.json").write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"已生成演示数据：{len(payload['courses'])} 条课程安排，口令 {DEMO_PASSPHRASE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
