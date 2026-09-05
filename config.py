import os

# ============================================================
# GOOGLE GEMINI API SOZLAMALARI
# ============================================================

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

