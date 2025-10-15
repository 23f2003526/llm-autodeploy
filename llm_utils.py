import requests
import re
import os
from config import AIPIPE_TOKEN

AIPIPE_URL = "https://aipipe.org/openrouter/v1/chat/completions"


def parse_ai_output(ai_output: str, TMP_DIR: str) -> dict:
    """
    Parse AI output in ```filename blocks and write files inside TMP_DIR.
    Returns dict of {filename: content}.
    """
    files = {}
    text = ai_output.replace('\r\n', '\n')

    pattern = re.compile(
        r'```(?:filename\s+)?([^\n`]+)\n(.*?)(?=```[A-Za-z0-9_.-]*|\Z)',
        re.DOTALL
    )
    matches = pattern.findall(text)

    for filename, content in matches:
        content = content.strip()
        file_path = os.path.join(TMP_DIR, filename)

        # Ensure parent directories exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        files[filename] = content
        print(f"✅ Created {file_path}")

    # Fallback
    if not files:
        file_path = os.path.join(TMP_DIR, 'index.html')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text.strip())
        files['index.html'] = text.strip()
        print(f"✅ Created fallback {file_path}")

    return files


def generate_app_code(brief, checks, TMP_DIR: str, round_num=1, prev_files=None) -> dict:
    """
   Generate (or revise) app code using AIpipe's OpenRouter-compatible API.
    - round_num=1 → create from scratch
    - round_num=2 → improve based on previous version and new brief
    """
    if not AIPIPE_TOKEN:
        raise ValueError("AIPIPE_TOKEN not set in environment.")
    
    # --- Context prep for Round 2 ---
    prev_context = ""
    if round_num == 2 and prev_files:
        prev_readme = prev_files.get("README.md", "")
        prev_code = prev_files.get("index.html", "")

        allowed_exts = (".html", ".css", ".js", ".json", ".py", ".md", ".txt", ".yml", ".yaml")
        other_files = "\n".join(
            f"### {name}\n{content[:1000]}"  # only take first 1000 chars to stay within limits
            for name, content in prev_files.items()
            if (
                name not in ("README.md", "index.html")
                and not name.startswith(".")                # skip .git, .env, etc.
                and not name.lower().startswith("git")       # skip stray git-related files
                and not any(part.startswith(".git") for part in name.split("/"))
                and os.path.splitext(name)[1].lower() in allowed_exts  # only readable files
            )
        )

        prev_context = f"""
        ### Previous Version Context

        #### README.md
        {prev_readme[:2000]}

        #### index.html
        {prev_code[:2000]}

        {other_files}

        Revise and improve this project according to the new brief below.
        Focus on enhancing features, structure, UI, and documentation as needed.
        Ensure backward compatibility where possible.
        Do not nest triple backticks inside file content. If necessary, escape them or avoid them. Follow this instruction very strictly. 
        """

    ## ------- MAIN PROMPT ------
    prompt = f"""
    ### Round
    {round_num}

    ### Task
    Generate a single index.html file which contains internal css and javascript. Do not create separate css and js files. Generate an appropriate README.md file too. Do keep in mind that these will be deployed on Github Pages and should work from there:
    {brief}

    {prev_context}

    Attachments (if any) are available in attachments/ subfolder.

    Checks: {checks}

    Return code files with filenames in the following format:
    ```filename.file-extension
    <content>
    ```

    example-
    ```index.html
    <content of the files>
    ```

    The first line after ```filename must always be the actual filename (e.g., README.md, index.html, script.js, LICENSE, main.py, etc.) Adhere to this format very strictly. Seriously, do not deviate.
    Include at least one HTML file (preferably index.html).
    DO NOT include LICENSE file.
    Include a professional README.md explaining the project, usage, and license.
    Do not include explanations or extra text outside the blocks.
    Ensure all dependencies are included.
    Do not nest triple backticks inside file content. If necessary, escape them or avoid them. Follow this instruction very strictly. 
    """

    print(prompt)
    # --- API Request ---
    response = requests.post(
        AIPIPE_URL,
        headers={
            "Authorization": f"Bearer {AIPIPE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-4.1-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful web app code generator."},
                {"role": "user", "content": prompt}
            ]
        },
        timeout=200
    )

    if response.status_code != 200:
        raise RuntimeError(f"AIpipe API Error {response.status_code}: {response.text}")

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    print(TMP_DIR)
    print(content)

    # --- Parse and return files dict ---
    files = parse_ai_output(content, TMP_DIR=TMP_DIR)
    print(files)
    print(files.keys())
    return files