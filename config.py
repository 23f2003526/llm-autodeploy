# config.py
import os
from dotenv import load_dotenv

load_dotenv()

APP_SECRET = os.getenv("APP_SECRET")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
AIPIPE_TOKEN = os.getenv("AIPIPE_TOKEN")
