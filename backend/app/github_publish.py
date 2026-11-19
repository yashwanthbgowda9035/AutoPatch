"""GitHub REST publisher. Never logs or stores authentication tokens."""
from __future__ import annotations
import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

SLUG = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
FILE = re.compile(r"^[A-Za-z0-9_.-]{1,100}\.(?:py|c|cpp|cc|cxx|java|txt|md|js|ts|html|css|json|formula)$")

class PublishRequest(BaseModel):
    token: str = Field(min_length=12, max_length=300)
    repository: str = Field(min_length=1, max_length=100)
    owner: str = Field(default="", max_length=100)
    filename: str = Field(min_length=3, max_length=100)
    code: str = Field(min_length=1, max_length=20000)
    create_new: bool = True
    private: bool = True
    message: str = Field(default="Publish source from AutoPatch", min_length=1, max_length=200)

    @field_validator("repository", "owner")
    @classmethod
    def slug(cls, v: str) -> str:
        if v and (not SLUG.fullmatch(v) or v in (".", "..")):
            raise ValueError("Use a simple GitHub username or repository name")
        return v

    @field_validator("filename")
    @classmethod
    def file(cls, v: str) -> str:
        if not FILE.fullmatch(v) or v.startswith("."):
            raise ValueError("Use a supported filename such as main.py; directories are not allowed")
        return v


def github_call(method: str, path: str, token: str, data: dict | None = None) -> dict:
    url = "https://api.github.com" + path
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "AutoPatch-GitHub-Studio"}
    body = json.dumps(data).encode() if data is not None else None
    if body is not None: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Avoid relaying arbitrary provider responses (or any credentials).
        messages = {401:"Invalid or expired GitHub token.",403:"GitHub denied this action. Check token permissions or rate limits.",404:"Repository not found, or token cannot access it.",409:"Repository has no initialized default branch.",422:"GitHub rejected the repository or file. It may already exist or have a conflicting name."}
        raise HTTPException(status_code=exc.code if exc.code in (401,403,404,409,422) else 502, detail=messages.get(exc.code,"GitHub API request failed.")) from None
    except (urllib.error.URLError, TimeoutError):
        raise HTTPException(status_code=502, detail="Cannot reach GitHub. Check internet access.") from None


def publish(req: PublishRequest) -> dict:
    # Authenticate before creating anything. No token ever persisted.
    me = github_call("GET", "/user", req.token)
    login = me["login"]
    owner = req.owner or login
    if req.create_new:
        if owner.lower() != login.lower():
            raise HTTPException(status_code=400, detail="New repositories can be created only in your personal account in this dashboard.")
        created = github_call("POST", "/user/repos", req.token, {"name":req.repository,"private":req.private,"auto_init":True,"description":"Published from AutoPatch"})
        owner = created["owner"]["login"]
    escaped = "/".join(urllib.parse.quote(part, safe="") for part in (owner,req.repository))
    filename = urllib.parse.quote(req.filename, safe="")
    endpoint = f"/repos/{escaped}/contents/{filename}"
    payload = {"message":req.message,"content":base64.b64encode(req.code.encode()).decode()}
    if not req.create_new:
        try:
            existing = github_call("GET",endpoint,req.token)
        except HTTPException as exc:
            if exc.status_code != 404:raise
        else:
            if existing.get("type") != "file":raise HTTPException(status_code=409,detail="That path is not a file.")
            payload["sha"] = existing["sha"]
    result = github_call("PUT",endpoint,req.token,payload)
    return {"success":True,"repository_url":f"https://github.com/{owner}/{req.repository}","file_url":result.get("content",{}).get("html_url"),"owner":owner,"repository":req.repository,"filename":req.filename,"commit_sha":result.get("commit",{}).get("sha")}
