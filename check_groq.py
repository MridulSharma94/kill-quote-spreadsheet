import os
from openai import OpenAI
key=os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
if not key: raise SystemExit("Set GROQ_API_KEY first.")
client=OpenAI(base_url="https://api.groq.com/openai/v1",api_key=key)
models=client.models.list()
print("API authentication successful. Available models:",len(models.data))
print("First available model IDs:")
for m in models.data[:15]: print("-",m.id)
