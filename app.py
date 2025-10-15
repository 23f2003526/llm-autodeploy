import os
import shutil
import base64
from time import time
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from github import Github, GithubException

from config import APP_SECRET, GITHUB_TOKEN
from llm_utils import generate_app_code

app = FastAPI()


class TaskRequest(BaseModel):
    email: str
    secret: str
    task: str
    round: int
    nonce: str
    brief: str
    checks: list[str]
    evaluation_url: str
    attachments: list[dict] = []


# ---------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------

def ensure_tmp_dir(task_name: str) -> str:
    """Create tmp/<task> directory relative to project root."""
    root = os.path.dirname(os.path.abspath(__file__))
    tmp_root = os.path.join(root, "tmp")
    os.makedirs(tmp_root, exist_ok=True)

    tmp_dir = os.path.join(tmp_root, task_name)
    os.makedirs(tmp_dir, exist_ok=True)
    print(f"📁 Ensured tmp folder: {tmp_dir}")
    return tmp_dir


def cleanup_tmp():
    """Delete all previous tmp directories before round 1."""
    root = os.path.dirname(os.path.abspath(__file__))
    tmp_root = os.path.join(root, "tmp")

    if os.path.exists(tmp_root):
        shutil.rmtree(tmp_root, ignore_errors=True)
        print("🧹 Cleared all previous tmp folders.")
    else:
        print("ℹ️ No previous tmp folders found.")


def save_attachments(attachments: list[dict], attach_dir: str):
    """Save attachments (supports base64 and HTTP URLs)."""
    os.makedirs(attach_dir, exist_ok=True)
    for att in attachments:
        name, url = att.get("name"), att.get("url")
        if not name or not url:
            continue

        path = os.path.join(attach_dir, name)
        try:
            if url.startswith("data:"):
                header, b64data = url.split(",", 1)
                data = base64.b64decode(b64data)
                with open(path, "wb") as f:
                    f.write(data)
                print(f"📎 Saved attachment: {path}")
            elif url.startswith("http"):
                resp = requests.get(url)
                if resp.ok:
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    print(f"🌐 Downloaded attachment: {path}")
                else:
                    print(f"⚠️ Failed to fetch {url} ({resp.status_code})")
        except Exception as e:
            print(f"⚠️ Failed to save {name}: {e}")


# ---------------------------------------------------------------------
# GITHUB OPERATIONS VIA PyGithub
# ---------------------------------------------------------------------

def get_github_client():
    """Authenticate with GitHub using PyGithub."""
    return Github(GITHUB_TOKEN)


def create_or_get_repo(task_name: str):
    """Create or fetch a GitHub repo for the task."""
    g = get_github_client()
    user = g.get_user()

    repo_name = task_name.replace(" ", "-")
    try:
        repo = user.create_repo(
            name=repo_name,
            private=False,
            auto_init=True,
            description=f"Auto-generated repo for task: {task_name}",
        )
        print(f"🆕 Created repo: {repo.full_name}")
    except GithubException as e:
        if e.status == 422:  # already exists
            repo = user.get_repo(repo_name)
            print(f"ℹ️ Using existing repo: {repo.full_name}")
        else:
            raise

    return repo


def push_files(repo, files: dict, commit_msg: str):
    """Push dictionary of files to GitHub repo."""
    for name, content in files.items():
        try:
            # Try updating existing file
            existing = repo.get_contents(name)
            repo.update_file(
                path=existing.path,
                message=commit_msg,
                content=content,
                sha=existing.sha,
            )
            print(f"✏️ Updated {name}")
        except GithubException as e:
            if e.status == 404:
                repo.create_file(path=name, message=commit_msg, content=content)
                print(f"🆕 Created {name}")
            else:
                raise

    commit_sha = repo.get_commits()[0].sha
    print(f"✅ Commit SHA: {commit_sha}")
    return commit_sha


def enable_pages(repo):
    """Enable GitHub Pages on the repo."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    })

    url = f"https://api.github.com/repos/{repo.owner.login}/{repo.name}/pages"
    payload = {"source": {"branch": "main", "path": "/"}}
    r = session.post(url, json=payload)
    if r.status_code not in (201, 204):
        print(f"⚠️ Failed to enable GitHub Pages: {r.status_code} {r.text}")
    else:
        print("✅ GitHub Pages enabled.")


# ---------------------------------------------------------------------
# EVALUATION NOTIFICATION
# ---------------------------------------------------------------------

def notify_evaluation(req: TaskRequest, repo, commit_sha: str, max_retries: int = 5):
    pages_url = f"https://{repo.owner.login}.github.io/{repo.name}/"
    print(pages_url)

    payload = {
        "email": req.email,
        "task": req.task,
        "round": req.round,
        "nonce": req.nonce,
        "repo_url": repo.html_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
    }

    print("⏳ Waiting 60 seconds for GitHub Pages to deploy...")
    time.sleep(60)
    delay = 1
    for attempt in range(max_retries):
        try:
            resp = requests.post(req.evaluation_url, json=payload, timeout=10)
            if resp.ok:
                return {
                    "email": req.email,
                    "task": req.task,
                    "round": req.round,
                    "nonce": req.nonce,
                    "repo_url": repo.html_url,
                    "pages_url": pages_url,
                    "commit_sha": commit_sha,
                    "status": resp.status_code,
                }
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1}: Request failed - {e}")

        print(f"Attempt {attempt + 1} failed (status: {getattr(resp, 'status_code', 'N/A')}). Retrying in {delay}s...")
        time.sleep(delay)
        delay *= 2  # exponential backoff

    raise HTTPException(status_code=500, detail=f"Eval error after {max_retries} retries: {resp.text if 'resp' in locals() else 'no response'}")


# ---------------------------------------------------------------------
# ROUND LOGIC
# ---------------------------------------------------------------------

def round1(req: TaskRequest):
    cleanup_tmp()
    tmp_dir = ensure_tmp_dir(req.task)
    attach_dir = os.path.join(tmp_dir, "attachments")
    save_attachments(req.attachments, attach_dir)

    files = generate_app_code(req.brief, req.checks, tmp_dir, round_num=req.round)
    if "index.html" not in files:
        files["index.html"] = "<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>"

    # ✅ Include all attachments in files dict so they get pushed
    for root, _, filenames in os.walk(attach_dir):
        for filename in filenames:
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, tmp_dir)  # e.g. "attachments/data.csv"
            with open(path, "r", encoding="utf-8") as f:
                files[rel_path] = f.read()
            print(f"📎 Added attachment to push: {rel_path}")


    repo = create_or_get_repo(req.task)
    commit_sha = push_files(repo, files, f"Round 1: {req.brief[:60]}")
    enable_pages(repo)
    return notify_evaluation(req, repo, commit_sha)


def round2(req: TaskRequest):
    tmp_dir = ensure_tmp_dir(req.task)
    attach_dir = os.path.join(tmp_dir, "attachments")
    save_attachments(req.attachments, attach_dir)

    repo = create_or_get_repo(req.task)

    prev_files = {}
    for file in repo.get_contents(""):
        try:
            prev_files[file.path] = file.decoded_content.decode()
        except Exception:
            continue

    new_files = generate_app_code(req.brief, req.checks, tmp_dir, req.round, prev_files)

    # ✅ Include attachments in push
    for root, _, filenames in os.walk(attach_dir):
        for filename in filenames:
            path = os.path.join(root, filename)
            rel_path = os.path.relpath(path, tmp_dir)  # e.g. "attachments/data.csv"
            with open(path, "r", encoding="utf-8") as f:
                new_files[rel_path] = f.read()
            print(f"📎 Added attachment to push: {rel_path}")


    commit_sha = push_files(repo, new_files, f"Round 2: {req.brief[:60]}")

    return notify_evaluation(req, repo, commit_sha)


# ---------------------------------------------------------------------
# ROUTE
# ---------------------------------------------------------------------

@app.post("/task")
def handle_task(req: TaskRequest):
    if req.secret != APP_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret")

    if req.round == 1:
        return round1(req)
    elif req.round == 2:
        return round2(req)
    else:
        raise HTTPException(status_code=400, detail="Invalid round")
