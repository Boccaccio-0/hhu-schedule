#!/usr/bin/env python3
"""加解密测试：验证口令加密与解密往返、错误口令拒绝、示例数据一致性。"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from hhu import crypto  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
DEMO_PASSPHRASE = "demo-pass"


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_roundtrip() -> None:
    payload = {"中文键": ["值", 1, None], "nested": {"b": 2, "a": [1, 2, 3]}}
    envelope = crypto.encrypt_json(payload, "口令-123", iterations=1000, updated="2026-01-01T00:00:00+08:00")
    check(crypto.decrypt_json(envelope, "口令-123") == payload, "解密结果与原文不一致")


def test_envelope_fields() -> None:
    envelope = crypto.encrypt_json({"a": 1}, "x", iterations=1000)
    for key in ["v", "alg", "kdf", "iter", "salt", "iv", "ct", "updated", "payloadHash"]:
        check(key in envelope, f"密文文件缺少字段 {key}")
    check(envelope["alg"] == "AES-256-GCM", f"算法标识错误：{envelope['alg']}")
    check(envelope["kdf"] == "PBKDF2-SHA256", f"KDF 标识错误：{envelope['kdf']}")
    check(len(base64.b64decode(envelope["salt"])) == 16, "salt 长度应为 16 字节")
    check(len(base64.b64decode(envelope["iv"])) == 12, "iv 长度应为 12 字节")


def test_wrong_passphrase_rejected() -> None:
    envelope = crypto.encrypt_json({"a": 1}, "正确口令", iterations=1000)
    try:
        crypto.decrypt_json(envelope, "错误口令")
    except Exception:
        return
    raise AssertionError("错误口令竟然解密成功")


def test_payload_hash_stable() -> None:
    check(
        crypto.payload_hash({"a": 1, "b": 2}) == crypto.payload_hash({"b": 2, "a": 1}),
        "payloadHash 应与字典键顺序无关",
    )
    check(crypto.payload_hash({"a": 1}) != crypto.payload_hash({"a": 2}), "内容变化时 payloadHash 应变化")


def test_sample_fixture() -> None:
    envelope = json.loads((FIXTURES / "sample.enc.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "sample.plain.json").read_text(encoding="utf-8"))
    decrypted = crypto.decrypt_json(envelope, DEMO_PASSPHRASE)
    check(decrypted == expected, "演示样本解密结果与 sample.plain.json 不一致")
    check(decrypted["startDate"] == "2026-09-07", f"演示样本起始日期错误：{decrypted['startDate']}")
    check(len(decrypted["courses"]) == 20, "演示样本课程数错误")


def main() -> int:
    tests = [
        test_roundtrip,
        test_envelope_fields,
        test_wrong_passphrase_rejected,
        test_payload_hash_stable,
        test_sample_fixture,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"  ✗ {test.__name__}: {exc}")
    print(f"加密测试：{len(tests) - failures}/{len(tests)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
