# github_utils.py
from github import Github
from config import GITHUB_TOKEN
import requests

def create_and_push_repo(task: str, files: dict[str, str], email: str):
    g = Github(GITHUB_TOKEN)
    user = g.get_user()
    repo_name = f"{task}"
    repo = user.create_repo(
        repo_name,
        private=False,
        description=f"Auto-generated app for {email}"
    )

    # Ensure at least one HTML file exists
    if "index.html" not in files:
        html_file = next((name for name in files if name.endswith(".html")), None)
        if html_file:
            files["index.html"] = files[html_file]
        else:
            files["index.html"] = "<!DOCTYPE html><html><body><h1>Hello World</h1></body></html>"

    # Add LICENSE only if missing
    if "LICENSE" not in files:
        files["LICENSE"] = "MIT License\n\nCopyright (c) 2025"


    # Add all files
    for path, content in files.items():
        try:
            repo.create_file(path, f"Add {path}", content)
        except Exception as e:
            print(f"⚠️ Skipped {path}: {e}")    

    # --- Enable GitHub Pages automatically ---
    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    })

    pages_api = f"https://api.github.com/repos/{user.login}/{repo_name}/pages"
    payload = {"source": {"branch": "main", "path": "/"}}

    try:
        r = session.post(pages_api, json=payload)
        if r.status_code not in (201, 204):
            print(f"⚠️ Failed to enable Pages: {r.status_code} {r.text}")
    except Exception as e:
        print(f"⚠️ Error enabling GitHub Pages: {e}")

    # Repo + Pages URLs
    repo_url = repo.html_url
    pages_url = f"https://{user.login}.github.io/{repo.name}/"
    commit_sha = repo.get_commits()[0].sha

    return repo_url, pages_url, commit_sha
