"""Debug: test Groq API directly."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv()

from groq import Groq

api_key = os.getenv("GROQ_API_KEY", "")
print(f"Key present: {bool(api_key)}")
print(f"Key prefix: {api_key[:10]}...")

try:
    client = Groq(api_key=api_key)
    r = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a JSON assistant."},
            {"role": "user", "content": 'Respond with: {"status": "ok"}'},
        ],
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        max_tokens=50,
        response_format={"type": "json_object"},
    )
    print(f"SUCCESS: {r.choices[0].message.content}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
