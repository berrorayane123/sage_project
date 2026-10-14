# ===== hello_gemini.py: checks that Gemini works on this computer =====
import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

response = client.models.generate_content(model=MODEL, contents="Say hello in one short sentence.")
print("Model:", MODEL)
print("Gemini says:", response.text)