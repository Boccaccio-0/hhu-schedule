"""口令加密：PBKDF2-SHA256 派生密钥 + AES-256-GCM。

与浏览器端 WebCrypto 的实现保持一致，网页可以直接用 crypto.subtle 解密。
密文文件（web/data/schedule.enc.json）结构：

    v           格式版本
    alg         "AES-256-GCM"
    kdf         "PBKDF2-SHA256"
    iter        迭代次数
    salt        base64，16 字节
    iv          base64，12 字节
    ct          base64，密文加 16 字节 GCM tag
    updated     最近一次成功同步时间（明文，便于未解锁时展示）
    payloadHash 明文 JSON 的 sha256（用于判断课表是否真的变化）
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_ITERATIONS = 200_000
SALT_BYTES = 16
IV_BYTES = 12
CHINA_TZ = _dt.timezone(_dt.timedelta(hours=8))


def canonical_json(obj) -> bytes:
    """稳定的 JSON 序列化，用于计算 payloadHash。"""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_hash(obj) -> str:
    return hashlib.sha256(canonical_json(obj)).hexdigest()


def derive_key(passphrase: str, salt: bytes, iterations: int = DEFAULT_ITERATIONS) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=iterations)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_json(obj, passphrase: str, iterations: int = DEFAULT_ITERATIONS, updated: str | None = None) -> dict:
    plaintext = canonical_json(obj)
    salt = os.urandom(SALT_BYTES)
    iv = os.urandom(IV_BYTES)
    ciphertext = AESGCM(derive_key(passphrase, salt, iterations)).encrypt(iv, plaintext, None)
    return {
        "v": 1,
        "alg": "AES-256-GCM",
        "kdf": "PBKDF2-SHA256",
        "iter": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "iv": base64.b64encode(iv).decode("ascii"),
        "ct": base64.b64encode(ciphertext).decode("ascii"),
        "updated": updated or _dt.datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
        "payloadHash": hashlib.sha256(plaintext).hexdigest(),
    }


def decrypt_json(envelope: dict, passphrase: str):
    """解密（主要给测试和本地排查用，网页端用 WebCrypto）。"""
    key = derive_key(passphrase, base64.b64decode(envelope["salt"]), int(envelope.get("iter", DEFAULT_ITERATIONS)))
    plaintext = AESGCM(key).decrypt(base64.b64decode(envelope["iv"]), base64.b64decode(envelope["ct"]), None)
    return json.loads(plaintext.decode("utf-8"))
