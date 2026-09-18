"""河海大学统一身份认证（authserver，金智 CAS）登录。

关键点（实测）：

* 登录页密码由前端 AES-CBC 加密后再提交：明文是随机 64 字符加真实密码，
  key 是页面里的 pwdEncryptSalt（16 字符），iv 是随机 16 字符，输出 Base64。
* 学校 WAF 会识别并拦截 Python 默认 TLS 指纹（requests 会被直接断连），
  因此这里统一使用 curl_cffi 模拟 Chrome 指纹。
"""

from __future__ import annotations

import base64
import random
import re
from urllib.parse import quote

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from curl_cffi import requests as cffi_requests

AUTHSERVER = "https://authserver.hhu.edu.cn"
JWXT = "https://jwxt.hhu.edu.cn"
SERVICE_URL = f"{JWXT}/jsxsd/sso.jsp"
LOGIN_URL = f"{AUTHSERVER}/authserver/login?service={quote(SERVICE_URL, safe='')}"

SCHEDULE_PATH = "/jsxsd/xskb/xskb_list.do"
CALENDAR_PATH = "/jsxsd/jxzl/jxzl_query"

#: 与登录页 encrypt.js 中 randomString() 使用的字符集保持一致。
_SALT_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
_EXECUTION_RE = re.compile(r'name=["\']execution["\'][^>]*value=["\']([^"\']+)["\']')
_SALT_RE = re.compile(r'id=["\']pwdEncryptSalt["\'][^>]*value=["\']([^"\']+)["\']')
_ERROR_RE = re.compile(r'id=["\']showErrorTip["\'][^>]*>(.*?)</span>', re.S)


class LoginError(RuntimeError):
    """登录失败（账号密码错误、需要验证码、网络异常等）。"""


def _random_string(length: int) -> str:
    return "".join(random.choice(_SALT_CHARS) for _ in range(length))


def encrypt_password(password: str, salt: str) -> str:
    """按登录页前端逻辑加密密码。"""
    plaintext = (_random_string(64) + password).encode("utf-8")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(salt.encode("utf-8")), modes.CBC(_random_string(16).encode("utf-8")))
    encrypted = cipher.encryptor().update(padded)
    return base64.b64encode(encrypted).decode("ascii")


def new_session(impersonate: str = "chrome"):
    """创建一个带浏览器指纹的会话。"""
    session = cffi_requests.Session(impersonate=impersonate)
    session.headers.update({"Accept-Language": "zh-CN,zh;q=0.9"})
    return session


def login(username: str, password: str, impersonate: str = "chrome"):
    """登录统一身份认证并返回已进入教务系统的会话。"""
    session = new_session(impersonate)
    page = session.get(LOGIN_URL, timeout=30, verify=False)
    html = page.text

    execution = _EXECUTION_RE.search(html)
    salt = _SALT_RE.search(html)
    if not execution or not salt:
        raise LoginError("登录页结构异常：找不到 execution 或 pwdEncryptSalt")

    payload = {
        "username": username,
        "password": encrypt_password(password, salt.group(1)),
        "_eventId": "submit",
        "cllt": "userNameLogin",
        "dllt": "generalLogin",
        "execution": execution.group(1),
        "lt": "",
        "rmShown": "1",
    }
    response = session.post(LOGIN_URL, data=payload, timeout=30, verify=False, allow_redirects=False)
    location = response.headers.get("Location")
    if response.status_code not in (301, 302, 303) or not location:
        tip = _ERROR_RE.search(response.text)
        message = re.sub(r"<[^>]+>", "", tip.group(1)).strip() if tip else "登录未跳转，可能是账号密码错误或需要验证码"
        raise LoginError(message or "登录失败")

    entry = session.get(location, timeout=30, verify=False)
    if entry.status_code != 200:
        raise LoginError(f"进入教务系统失败：HTTP {entry.status_code}")
    return session


def fetch_schedule_html(session) -> str:
    """抓取学期理论课表页（页面未声明 charset，实际为 UTF-8）。"""
    response = session.get(JWXT + SCHEDULE_PATH, timeout=30, verify=False)
    if response.status_code != 200:
        raise LoginError(f"课表页请求失败：HTTP {response.status_code}")
    return response.content.decode("utf-8", "replace")


def fetch_calendar_html(session) -> str:
    """抓取教学周历页。"""
    response = session.get(JWXT + CALENDAR_PATH, timeout=30, verify=False)
    if response.status_code != 200:
        raise LoginError(f"教学周历页请求失败：HTTP {response.status_code}")
    return response.content.decode("utf-8", "replace")
