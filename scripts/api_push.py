#!/usr/bin/env python3
"""当 git push 连不上 GitHub 时，改用 GitHub REST API 推送。

国内网络访问 github.com 的 443 端口经常被重置，但 api.github.com 通常仍然可用，
所以这里用 Git Data API 手工构造一次提交（内容与 git push 完全一致）。

Token 来源：

1. 环境变量 GITHUB_TOKEN
2. 从 git 凭据管理器读取（git credential fill，即之前 push 时保存的那份）

用法::

    python scripts/api_push.py [--branch main] [--remote origin]
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

API = "https://api.github.com"


def run_git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token
    result = subprocess.run(["git", "credential", "fill"], cwd=ROOT, input="protocol=https\nhost=github.com\n\n",
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in (result.stdout or "").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("找不到 GitHub token：请设置环境变量 GITHUB_TOKEN，或先用 git 登录过该仓库。")


def api(token: str, method: str, path: str, payload=None):
    request = urllib.request.Request(API + path, method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "User-Agent": "hhu-schedule", "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise SystemExit(f"GitHub API {method} {path} 失败：HTTP {error.code} {detail[:200]}") from None


def remote_slug(remote: str) -> tuple[str, str]:
    url = run_git(["remote", "get-url", remote]).stdout.strip()
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$", url)
    if not match:
        raise SystemExit(f"无法从远端地址解析仓库：{url}")
    return match.group(1), match.group(2)


def local_tree() -> dict[str, dict]:
    result = run_git(["ls-tree", "-r", "HEAD"])
    if result.returncode != 0:
        raise SystemExit("读取本地 git 树失败：" + (result.stderr or "").strip())
    entries = {}
    for line in result.stdout.splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, sha = meta.split()
        if kind == "blob":
            entries[path] = {"sha": sha, "mode": mode}
    return entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 GitHub API 推送当前提交")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="")
    args = parser.parse_args(argv)

    token = get_token()
    owner, repo = remote_slug(args.remote)
    branch = args.branch or run_git(["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip() or "main"
    message = run_git(["log", "-1", "--pretty=%s"]).stdout.strip() or "sync"
    print(f"仓库：{owner}/{repo} | 分支：{branch} | 提交信息：{message}")

    ref = api(token, "GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}")
    base_sha = ref["object"]["sha"]
    base_tree = api(token, "GET", f"/repos/{owner}/{repo}/git/commits/{base_sha}")["tree"]["sha"]
    remote_entries = {item["path"]: item for item in
                      api(token, "GET", f"/repos/{owner}/{repo}/git/trees/{base_tree}?recursive=1")["tree"]
                      if item["type"] == "blob"}

    mine = local_tree()
    changes = []
    for path, info in mine.items():
        remote = remote_entries.get(path)
        if remote and remote["sha"] == info["sha"]:
            continue
        # 直接取 git 对象里的原始字节，保证与 git push 上传的内容完全一致
        content = subprocess.run(["git", "cat-file", "blob", info["sha"]], cwd=ROOT,
                                 capture_output=True, check=True).stdout
        created = api(token, "POST", f"/repos/{owner}/{repo}/git/blobs",
                      {"content": base64.b64encode(content).decode(), "encoding": "base64"})
        changes.append({"path": path, "mode": info["mode"], "type": "blob", "sha": created["sha"]})
        print(f"  新增/更新：{path}")
    for path in remote_entries:
        if path not in mine:
            changes.append({"path": path, "mode": "100644", "type": "blob", "sha": None})
            print(f"  删除：{path}")

    if not changes:
        print("远端已是最新，无需推送。")
        return 0

    tree = api(token, "POST", f"/repos/{owner}/{repo}/git/trees", {"base_tree": base_tree, "tree": changes})
    commit = api(token, "POST", f"/repos/{owner}/{repo}/git/commits",
                 {"message": message, "tree": tree["sha"], "parents": [base_sha]})
    api(token, "PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch}", {"sha": commit["sha"], "force": False})
    print(f"推送完成，新提交：{commit['sha'][:10]}")

    # API 推送产生的提交对象在本地不存在，需要 fetch 回来才能对齐引用。
    # git 端口不通时 fetch 会失败，此时本地提交号与远端不同（文件内容一致），
    # 后续仍然走 API 推送，不影响使用。
    if run_git(["fetch", args.remote, branch]).returncode == 0:
        run_git(["update-ref", f"refs/heads/{branch}", commit["sha"]])
        run_git(["update-ref", f"refs/remotes/{args.remote}/{branch}", commit["sha"]])
        print("本地引用已与远端对齐。")
    else:
        print("提示：git 端口当前不通，本地提交号与远端不同（文件内容完全一致）。")
        print("      网络恢复后跑一次 git fetch origin 即可对齐；不影响每天的自动同步。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
