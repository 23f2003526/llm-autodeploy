# llm_utils.py
import requests
from config import AIPIPE_TOKEN
import re
import os

AIPIPE_URL = "https://aipipe.org/openrouter/v1/chat/completions"

import re
import os

import re
import os

import re
import os

def parse_ai_output(ai_output: str) -> dict:
    """
    Parses AI output with ```filename blocks, safely capturing multi-line content
    including internal ``` code blocks, and writes files to disk.
    """
    files = {}
    text = ai_output.replace('\r\n', '\n')

    # Regex: filename after ```filename, then all content until next ```filename or end
    pattern = re.compile(
        r'```(?:filename\s+)?([^\n`]+)\n(.*?)(?=```[A-Za-z0-9_.-]*|\Z)',
        re.DOTALL
    )

    matches = pattern.findall(text)

    for filename, content in matches:
        content = content.strip()

        # Create directories if needed
        if '/' in filename:
            os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Write file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)

        files[filename] = content
        print(f"Created {filename}")

    # Fallback if nothing found
    if not files:
        files['index.html'] = text.strip()
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(text.strip())
        print("Created fallback index.html")
    
    print(files)
    print(files.keys())
    return files



def generate_app_code(brief, checks) -> dict:
    """
    Generate app code using AIpipe's OpenRouter-compatible API.
    Returns dict of {filename: content}.
    """
    if not AIPIPE_TOKEN:
        raise ValueError("AIPIPE_TOKEN not set in environment.")

    prompt = f"""Generate scripts for this task. Do keep in mind that these will be deployed on Github Pages and should work from there:
{brief}

Attachments (if any) are available in /tmp/hello-world/
Checks: {checks}

Return code files with filenames in the following format:
```filename
<content>
```
The first line after ```filename must always be the actual filename (e.g., README.md, index.html, script.js, LICENSE, main.py, etc.).
Include at least one HTML file (preferably index.html).
Include LICENSE with MIT License.
Include a professional README.md explaining the project, usage, and license.
Do not include explanations or extra text outside the blocks.
Ensure all dependencies are included.
Do not nest triple backticks inside file content. If necessary, escape them or avoid them.
"""

    response = requests.post(
        AIPIPE_URL,
        headers={
            "Authorization": f"Bearer {AIPIPE_TOKEN}",
            "Content-Type": "application/json",
        },
        json={
            "model": "openai/gpt-4.1-nano",
            "messages": [
                {"role": "system", "content": "You are a helpful web app code generator."},
                {"role": "user", "content": prompt}
            ]
        },
        timeout=60
    )

    if response.status_code != 200:
        raise RuntimeError(f"AIpipe API Error {response.status_code}: {response.text}")

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    print(content)

    # --- Parse and return files dict ---
    files = parse_ai_output(content)
    return files


# test2 = """
# ```filename
# LICENSE
# MIT License

# Copyright (c) 2023

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLYING OR OTHERWISE, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
# ```

# ```filename
# README.md
# # CAPTCHA Solver Web App

# ## Overview
# This is a simple web application designed to display a CAPTCHA image from a URL passed as a URL parameter `?url=...`, and automatically attempts to solve it by sending it to an external OCR API. The solution appears on the webpage within 15 seconds.

# ## Features
# - Reads the CAPTCHA image URL from the URL parameter `?url=...`.
# - Displays the CAPTCHA image on the page.
# - Automatically sends the image to an OCR API for solving.
# - Displays the solved text on the page.
# - Designed to work seamlessly on GitHub Pages.

# ## Usage
# 1. Deploy this project on GitHub Pages.
# 2. Open the webpage with a CAPTCHA URL parameter, for example:
#    ```
#    https://<your-github-username>.github.io/your-repo-name/index.html?url=https://example.com/captcha.png
#    ```
# 3. The page will display the CAPTCHA image and its recognized text within 15 seconds.

# ## License
# This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
# ```

# ```filename
# index.html
# <!DOCTYPE html>
# <html lang="en">
# <head>
#   <meta charset="UTF-8" />
#   <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
#   <title>Captcha Solver</title>
#   <style>
#     body { font-family: Arial, sans-serif; padding: 20px; max-width: 600px; margin: auto; }
#     img { max-width: 100%; border: 1px solid #ccc; margin-bottom: 20px; }
#     #result { font-size: 1.2em; color: green; }
#     #status { font-size: 1em; margin-top: 10px; }
#   </style>
# </head>
# <body>
#   <h1>Captcha Solver</h1>
#   <div id="captcha-container">
#     <img id="captcha-image" src="" alt="Loading CAPTCHA..." />
#   </div>
#   <div id="status">Loading...</div>
#   <div id="result"></div>

#   <script src="script.js"></script>
# </body>
# </html>
# ```

# ```filename
# script.js
# // script.js
# // This script fetches the CAPTCHA image URL from the ?url= parameter,
# // displays it, then sends it to a simple OCR API (Tesseract.js) locally
# // for solving, then displays the result within 15 seconds.

# (function() {
#   // Utility function to get URL parameter
#   function getQueryParam(param) {
#     const params = new URLSearchParams(window.location.search);
#     return params.get(param);
#   }

#   const captchaUrl = getQueryParam('url') || 'https://tmpfiles.org/api/file/5IH1nrd4hTeh/captcha_sample.png';

#   const imgElement = document.getElementById('captcha-image');
#   const statusDiv = document.getElementById('status');
#   const resultDiv = document.getElementById('result');

#   // Set the CAPTCHA image source
#   imgElement.src = captchaUrl;

#   // Function to perform OCR using Tesseract.js
#   function solveCaptcha(imageUrl) {
#     // Load Tesseract.js dynamically
#     if (!window.Tesseract) {
#       return new Promise((resolve, reject) => {
#         const script = document.createElement('script');
#         script.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@4/dist/tesseract.min.js';
#         script.onload = () => {
#           doOCR();
#         };
#         script.onerror = () => reject('Failed to load OCR library.');
#         document.head.appendChild(script);
#       });
#     } else {
#       return doOCR();
#     }

#     function doOCR() {
#       return Tesseract.recognize(
#         imageUrl,
#         'eng',
#         { logger: m => console.log(m) }
#       ).then(({ data: { text } }) => {
#         return text.trim();
#       });
#     }
#   }

#   // When the image loads, start OCR
#   imgElement.onload = () => {
#     statusDiv.textContent = 'Solving CAPTCHA...';

#     // Set a timeout for 15 seconds
#     const timeoutId = setTimeout(() => {
#       statusDiv.textContent = 'Timeout: Could not solve CAPTCHA within 15 seconds.';
#     }, 15000);

#     solveCaptcha(captchaUrl).then(text => {
#       clearTimeout(timeoutId);
#       resultDiv.textContent = 'Solved Text: ' + text;
#       statusDiv.textContent = 'Done.';
#     }).catch(err => {
#       clearTimeout(timeoutId);
#       statusDiv.textContent = 'Error during OCR: ' + err;
#     });
#   };

#   // Handle image error
#   imgElement.onerror = () => {
#     statusDiv.textContent = 'Failed to load CAPTCHA image.';
#   };
# })();
# ```
# """
# parse_ai_output(test2)