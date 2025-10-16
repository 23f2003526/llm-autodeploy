import requests
import re
import os
from config import AIPIPE_TOKEN

AIPIPE_URL = "https://aipipe.org/openrouter/v1/chat/completions"


def parse_ai_output(ai_output: str, TMP_DIR: str, brief: str = "", checks=None, round_num=1) -> dict:
    """
    Parse AI output into index.html and README.md using the new format.
    If missing README.md, auto-generate fallback.
    """
    def _strip_code_block(text: str) -> str:
        """
        Removes only the outermost ```...``` fences and optional language tag (like html, md, json, etc.)
        Keeps nested fenced blocks (e.g., ```json inside README.md).
        """
        text = text.strip()
        if not text.startswith("```"):
            return text

        # Find first and last code fence (```)
        matches = list(re.finditer(r"^```.*?$", text, re.MULTILINE))
        if len(matches) < 2:
            # not a proper fenced block
            return text.replace("```", "").strip()

        start = matches[0].end()
        end = matches[-1].start()
        inner = text[start:end].lstrip("\n")

        # Remove language tag from the first line if present
        first_newline = inner.find("\n")
        if first_newline != -1:
            maybe_lang = inner[:first_newline].strip()
            if re.fullmatch(r"[a-zA-Z0-9#+_\-]+", maybe_lang):
                inner = inner[first_newline + 1:]

        return inner.strip()


    def generate_readme_fallback(brief: str, checks=None, round_num=1):
        checks_text = "\n".join(checks or [])
        return f"""# Auto-generated README (Round {round_num})

            **Project brief:** {brief}

            **Checks to meet:**
            {checks_text}

            ## Setup
            1. Open `index.html` in a browser.
            2. No build steps required.

            ## Notes
            This README was generated as a fallback because the AI output did not include one.
            """

    text = ai_output.replace('\r\n', '\n').strip()
    if "---README.md---" in text:
        code_part, readme_part = text.split("---README.md---", 1)
        code_part = _strip_code_block(code_part)
        readme_part = _strip_code_block(readme_part)
    else:
        code_part = _strip_code_block(text)
        readme_part = generate_readme_fallback(brief, checks, round_num)

    files = {
        "index.html": code_part,
        "README.md": readme_part
    }

    for filename, content in files.items():
        file_path = os.path.join(TMP_DIR, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created {file_path}")

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
            f"### {name}\n{content[:1000]}"
            for name, content in prev_files.items()
            if (
                name not in ("README.md", "index.html")
                and not name.startswith(".")
                and not name.lower().startswith("git")
                and not any(part.startswith(".git") for part in name.split("/"))
                and os.path.splitext(name)[1].lower() in allowed_exts
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
        """

    ## ------- MAIN PROMPT ------
    prompt = f"""
        You are a professional web developer assistant.

        ### Round
        {round_num}

        ### Task
        {brief}

        {prev_context}

        Attachments (if any) are in attachments/ subfolder.

        ### Evaluation checks
        {checks or []}

        ### Output format rules:
        1. Produce a complete web app (HTML/JS/CSS inline if needed) satisfying the brief.
        2. Output must contain **two parts only**:
        - index.html (main app code)
        - README.md (starts after a line containing exactly: ---README.md---)
        3. README.md must include:
        - Overview
        - Setup
        - Usage
        - If Round 2, describe improvements made from the previous version.
        - License (MIT License)
        4. Do not include any commentary or explanations outside the code or README.
        5. Do not nest triple backticks inside code or README.
        6. Ensure all dependencies are included.
        7. Separate the two parts exactly with the line:
        ---README.md---
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
                {"role": "system", "content": "You are a helpful coding assistant that outputs runnable web apps"},
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

    # --- Parse and return files dict (pass brief, checks, round_num) ---
    files = parse_ai_output(content, TMP_DIR=TMP_DIR, brief=brief, checks=checks, round_num=round_num)
    print(files)
    print(files.keys())
    return files