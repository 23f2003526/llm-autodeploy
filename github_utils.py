from github import Github
from config import GITHUB_TOKEN
import requests
import os

def create_and_push_repo(task: str, files: dict[str, str], email: str):
    g = Github(GITHUB_TOKEN)
    user = g.get_user()
    repo_name = f"{task}"
    repo = user.create_repo(
        repo_name,
        private=False,
        description=f"Auto-generated app for {email}",
        license_template="mit"
    )

    TMP_DIR = os.path.join(os.getcwd(), "tmp", task)

    # --- Sanity check ---
    if not os.path.exists(TMP_DIR):
        raise FileNotFoundError(f"TMP_DIR not found: {TMP_DIR}")

    # --- Ensure at least one HTML file exists ---
    if "index.html" not in files:
        html_file = next((name for name in files if name.endswith(".html")), None)
        if html_file:
            files["index.html"] = files[html_file]
        else:
            files["index.html"] = "<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>"

    # --- Push all files from TMP_DIR (LLM + attachments) ---
    for root, _, filenames in os.walk(TMP_DIR):
        for fname in filenames:
            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, TMP_DIR)  # relative to tmp/<task>
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                repo.create_file(rel_path, f"Add {rel_path}", content)
                print(f"📤 Uploaded: {rel_path}")
            except Exception as e:
                print(f"⚠️ Skipped {rel_path}: {e}")

    # --- Enable GitHub Pages ---
    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })

    pages_api = f"https://api.github.com/repos/{user.login}/{repo_name}/pages"
    print("pages_api:", pages_api)
    payload = {"source": {"branch": "main", "path": "/"}}

    try:
        r = session.post(pages_api, json=payload)
        if r.status_code not in (201, 204):
            print(f"⚠️ Failed to enable Pages: {r.status_code} {r.text}")
    except Exception as e:
        print(f"⚠️ Error enabling GitHub Pages: {e}")

    repo_url = repo.html_url
    pages_url = f"https://{user.login}.github.io/{repo.name}/"
    commit_sha = repo.get_commits()[0].sha

    return repo_url, pages_url, commit_sha
