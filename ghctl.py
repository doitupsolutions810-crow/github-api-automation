#!/usr/bin/env python3
"""List GitHub repos and latest Actions conclusions.

Auth order (fail closed if none):
  1. GITHUB_APP_ID + GITHUB_APP_INSTALLATION_ID + GITHUB_APP_PRIVATE_KEY[_PATH]
  2. GITHUB_TOKEN / GH_TOKEN
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.github.com"


class AuthError(RuntimeError):
    pass


def _request(url: str, token: str, method: str = "GET", body: dict | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ghctl-capability-authority",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode()) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{method} {url} -> {exc.code}: {detail[:400]}") from exc


def _paginate(url: str, token: str) -> list[dict]:
    items: list[dict] = []
    while url:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "ghctl-capability-authority",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
            if isinstance(payload, list):
                items.extend(payload)
            elif isinstance(payload, dict) and "items" in payload:
                items.extend(payload["items"])
            else:
                raise RuntimeError(f"unexpected page shape from {url}")
            link = resp.headers.get("Link", "")
        next_url = None
        for part in link.split(","):
            if 'rel="next"' in part:
                next_url = part.split(";")[0].strip().strip("<>")
        url = next_url or ""
    return items


def _b64url(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def github_app_jwt(app_id: str, pem: str) -> str:
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError as exc:
        raise AuthError("cryptography is required for GitHub App JWT") from exc

    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"iat": now - 60, "exp": now + 540, "iss": app_id}).encode())
    signing_input = f"{header}.{payload}".encode()
    key = serialization.load_pem_private_key(pem.encode(), password=None)
    sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{header}.{payload}.{_b64url(sig)}"


def installation_token(app_id: str, installation_id: str, pem: str) -> str:
    jwt = github_app_jwt(app_id, pem)
    out = _request(
        f"{API}/app/installations/{installation_id}/access_tokens",
        jwt,
        method="POST",
        body={},
    )
    token = out.get("token")
    if not token:
        raise AuthError("GitHub App installation token missing from response")
    return token


def resolve_token() -> tuple[str, str]:
    app_id = os.environ.get("GITHUB_APP_ID", "").strip()
    inst = os.environ.get("GITHUB_APP_INSTALLATION_ID", "").strip()
    pem = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").strip()
    pem_path = os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "").strip()
    if pem_path and not pem:
        pem = open(pem_path, encoding="utf-8").read()
    pem = pem.replace("\\n", "\n")
    if app_id and inst and pem:
        return installation_token(app_id, inst, pem), "github-app"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    if token:
        return token, "pat"
    raise AuthError(
        "no credentials: set GITHUB_APP_ID + GITHUB_APP_INSTALLATION_ID + "
        "GITHUB_APP_PRIVATE_KEY[_PATH], or GITHUB_TOKEN"
    )


def latest_run(token: str, owner: str, repo: str) -> dict[str, Any] | None:
    url = f"{API}/repos/{owner}/{repo}/actions/runs?per_page=1"
    data = _request(url, token)
    runs = data.get("workflow_runs") or []
    return runs[0] if runs else None


def cmd_inventory(args: argparse.Namespace) -> int:
    token, mode = resolve_token()
    user = _request(f"{API}/user", token)
    login = user.get("login") or args.user
    q = urllib.parse.quote(f"user:{login}")
    repos = _paginate(f"{API}/search/repositories?q={q}&per_page=100", token)
    rows = []
    for repo in repos:
        full = repo["full_name"]
        owner, name = full.split("/", 1)
        run = None
        try:
            run = latest_run(token, owner, name)
        except Exception as exc:
            run = {"conclusion": f"error:{exc}"}
        rows.append(
            {
                "full_name": full,
                "private": repo.get("private"),
                "html_url": repo.get("html_url"),
                "pushed_at": repo.get("pushed_at"),
                "workflow": None
                if not run
                else {
                    "name": run.get("name"),
                    "conclusion": run.get("conclusion") or run.get("status"),
                    "html_url": run.get("html_url"),
                    "updated_at": run.get("updated_at"),
                },
            }
        )
    payload = {"auth": mode, "login": login, "count": len(rows), "repos": rows}
    if args.json:
        json.dump(payload, sys.stdout, indent=2)
        print()
    else:
        print(f"auth={mode} login={login} repos={len(rows)}")
        for row in rows:
            wf = row["workflow"]
            conclusion = "-" if not wf else wf.get("conclusion") or "-"
            print(f"{conclusion:16} {row['full_name']}")
    return 0


def cmd_dispatch(args: argparse.Namespace) -> int:
    token, mode = resolve_token()
    owner, repo = args.repo.split("/", 1)
    inputs = json.loads(args.inputs) if args.inputs else {}
    _request(
        f"{API}/repos/{owner}/{repo}/actions/workflows/{args.workflow}/dispatches",
        token,
        method="POST",
        body={"ref": args.ref, "inputs": inputs},
    )
    print(f"dispatched {args.workflow} on {args.repo}@{args.ref} via {mode}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="GitHub API automation CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("inventory", help="list repos + latest workflow conclusion")
    inv.add_argument("--user", default="")
    inv.add_argument("--json", action="store_true")
    inv.set_defaults(func=cmd_inventory)
    d = sub.add_parser("dispatch", help="workflow_dispatch")
    d.add_argument("repo", help="owner/name")
    d.add_argument("workflow", help="filename or id")
    d.add_argument("--ref", default="main")
    d.add_argument("--inputs", default="")
    d.set_defaults(func=cmd_dispatch)
    args = p.parse_args()
    try:
        return args.func(args)
    except AuthError as exc:
        print(f"FAIL_CLOSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
