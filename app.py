import os
import shutil
import base64
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from config import APP_SECRET
from llm_utils import generate_app_code
from github_utils import create_and_push_repo

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
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------


def ensure_tmp_dir(task_name: str) -> str:
    """Create tmp/<task> structure relative to project root."""
    # Find project root (where this script is)
    project_root = os.path.dirname(os.path.abspath(__file__))
    root_tmp = os.path.join(project_root, "tmp")
    os.makedirs(root_tmp, exist_ok=True)

    tmp_dir = os.path.join(root_tmp, task_name)
    os.makedirs(tmp_dir, exist_ok=True)

    print(f"📁 Ensured tmp folder: {tmp_dir}")
    return tmp_dir

def cleanup_tmp():
    """Delete all previous tmp directories before round 1 (relative to project root)."""
    # Always resolve relative to project root, not current working directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    root_tmp = os.path.join(project_root, "tmp")

    if os.path.exists(root_tmp):
        try:
            shutil.rmtree(root_tmp)
            print("🧹 Cleared all previous tmp folders.")
        except Exception as e:
            print(f"⚠️ Failed to clear tmp folder: {e}")
    else:
        print("ℹ️ No previous tmp folders found.")

def save_attachments(attachments: list[dict], attach_dir: str):
    """Save all attachments (supports base64 and HTTP URLs)."""
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
                if resp.status_code == 200:
                    with open(path, "wb") as f:
                        f.write(resp.content)
                    print(f"🌐 Downloaded attachment: {path}")
                else:
                    print(f"⚠️ Failed to fetch {url} ({resp.status_code})")
        except Exception as e:
            print(f"⚠️ Failed to save {name}: {e}")

def setup_git_repo(tmp_dir: str, repo_url: str):
    """Ensure a git repo is initialized and connected to remote."""
    os.chdir(tmp_dir)
    git_dir = os.path.join(tmp_dir, ".git")

    if not os.path.exists(git_dir):
        os.system("git init")
        os.system(f"git remote add origin {repo_url}")
    else:
        remote = os.popen("git config --get remote.origin.url").read().strip()
        if not remote:
            os.system(f"git remote add origin {repo_url}")
        elif remote != repo_url:
            print(f"⚠️ Remote mismatch ({remote}) → resetting to {repo_url}")
            os.system("git remote remove origin")
            os.system(f"git remote add origin {repo_url}")

    return repo_url

def git_commit_and_push(round_num: int, brief: str):
    """Commit and push changes to GitHub."""
    os.system("git add .")
    os.system(f'git commit -m "Round {round_num}: {brief[:60]}" || echo "⚠️ Nothing to commit"')
    os.system("git branch -M main")
    os.system("git push -u origin main")
    sha = os.popen("git rev-parse HEAD").read().strip()
    return sha

def notify_evaluation(req: TaskRequest, repo_url: str, pages_url: str, commit_sha: str):
    """Send payload to evaluation server."""
    payload = {
        "email": req.email,
        "task": req.task,
        "round": req.round,
        "nonce": req.nonce,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
    }

    resp = requests.post(req.evaluation_url, json=payload, headers={"Content-Type": "application/json"})
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Evaluation server error: {resp.text}")
    return resp.status_code


# ---------------------------------------------------------------------
# ROUND 1
# ---------------------------------------------------------------------

def round1(req: TaskRequest):
    cleanup_tmp()

    tmp_dir = ensure_tmp_dir(req.task)
    attach_dir = os.path.join(tmp_dir, "attachments")
    save_attachments(req.attachments, attach_dir)

    # Generate files via LLM
    files = generate_app_code(req.brief, req.checks, tmp_dir, round_num=req.round)

    # Ensure index.html exists
    if "index.html" not in files:
        index_path = os.path.join(tmp_dir, "index.html")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>")

    # Push to GitHub
    repo_url, pages_url, commit_sha = create_and_push_repo(req.task, files, req.email)

    status = notify_evaluation(req, repo_url, pages_url, commit_sha)

    return {
        "message": "✅ Round 1 complete",
        "repo_url": repo_url,
        "pages_url": pages_url,
        "commit_sha": commit_sha,
        "evaluation_status": status
    }


# ---------------------------------------------------------------------
# ROUND 2
# ---------------------------------------------------------------------

def round2(req: TaskRequest):
    tmp_dir = ensure_tmp_dir(req.task)
    attach_dir = os.path.join(tmp_dir, "attachments")

    repo_url = f"https://github.com/{req.email.split('@')[0]}/{req.task}.git"
    setup_git_repo(tmp_dir, repo_url)

    os.chdir(tmp_dir)

    print("📥 Fetching latest main branch...")
    os.system("git fetch origin main")

    print("🔄 Resetting local repo to match remote (avoids merge conflicts)...")
    os.system("git checkout main || git checkout -b main")
    os.system("git reset --hard origin/main || echo '⚠️ Remote empty or no commits yet'")

    # --- Step 1: Capture previous version (README.md, index.html, etc.)
    prev_files = {}
    for root, _, files in os.walk(tmp_dir):
        for file in files:
            if file.startswith(".git"):  # skip git internals
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, tmp_dir)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                prev_files[rel_path] = f.read()
    print(f"📦 Collected {len(prev_files)} previous files for context.")
    print(prev_files.keys())

    # --- Step 2: Clean everything EXCEPT .git and attachments
    for item in os.listdir(tmp_dir):
        path = os.path.join(tmp_dir, item)
        if item not in [".git", "attachments"]:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

    # --- Step 3: Restore attachments or recreate if missing
    os.makedirs(attach_dir, exist_ok=True)
    save_attachments(req.attachments, attach_dir)

    # Ensure attachments folder stays in repo (even if empty)
    keep_file = os.path.join(attach_dir, ".keep")
    if not os.path.exists(keep_file):
        with open(keep_file, "w", encoding="utf-8") as f:
            f.write("Keep this folder to preserve attachments across rounds.\n")

    # --- Step 4: Generate new or improved code
    print("🧠 Generating new round 2 files...")
    updated_files = generate_app_code(
        req.brief,
        req.checks,
        tmp_dir,
        round_num=req.round,
        prev_files=prev_files
    )

    for name, content in updated_files.items():
        file_path = os.path.join(tmp_dir, name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✏️ Updated: {name}")

    # --- Step 5: Commit and push
    os.system("git add .")
    os.system(f'git commit -m "Round {req.round}: {req.brief[:60]}" || echo "⚠️ Nothing to commit"')

    print("🚀 Pushing clean round 2 update...")
    push_result = os.system("git push origin main")

    if push_result != 0:
        print("⚠️ Normal push failed — trying force push as last resort")
        os.system("git push origin main --force")

    commit_sha = os.popen("git rev-parse HEAD").read().strip()
    pages_url = f"https://{req.email.split('@')[0]}.github.io/{req.task}/"

    status = notify_evaluation(req, repo_url, pages_url, commit_sha)

    return {
        "message": f"✅ Round {req.round} complete (attachments preserved)",
        "repo_url": repo_url,
        "pages_url": pages_url,
        "commit_sha": commit_sha,
        "evaluation_status": status
    }

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
