# ===== list_models.py: shows which Gemini models your key can use =====
import os
from google import genai

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
for model in client.models.list():
    actions = getattr(model, "supported_actions", None) or []
    if "generateContent" in actions and "flash" in model.name:
        print(model.name)