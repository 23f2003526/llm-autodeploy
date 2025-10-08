import os
import shutil
import base64
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

from config import APP_SECRET
from llm_utils import generate_app_code
from github_utils import create_and_push_repo

TMP_DIR = "/tmp/hello-world"

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


@app.post("/task")
def handle_task(req: TaskRequest):
    # Step 0: Clean TMP_DIR
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR, exist_ok=True)

    # Step 1: Write LLM-generated files
    files = generate_app_code(req.brief, req.checks)

    for filename, content in files.items():
        path = os.path.join(TMP_DIR, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # Step 2: Optional fallback (ONLY if files like index.html do not exist)
    if "index.html" not in files:
        with open(os.path.join(TMP_DIR, "index.html"), "w", encoding="utf-8") as f:
            f.write("<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>")

    # Step 3: Push TMP_DIR to GitHub
    repo_url, pages_url, commit_sha = create_and_push_repo(req.task, files, req.email)

    # --- Step 5: Notify evaluation server ---
    payload = {
        "email": req.email,
        "task": req.task,
        "round": req.round,
        "nonce": req.nonce,
        "repo_url": repo_url,
        "commit_sha": commit_sha,
        "pages_url": pages_url,
        # attachments: [{}]
    }

    resp = requests.post(
        req.evaluation_url,
        json=payload,
        headers={"Content-Type": "application/json"}
    )

    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Evaluation server error: {resp.text}")

    return {
        "message": "✅ Build complete",
        "repo_url": repo_url,
        "pages_url": pages_url,
        "evaluation_status": resp.status_code
    }
