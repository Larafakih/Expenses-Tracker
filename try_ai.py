import os
import requests


# r = requests.get(
#     "https://api.groq.com/openai/v1/models",
#     headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
#     timeout=15,
# )
# for model in r.json()["data"]:
#     print(model)



response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
    json={
        "model": "openai/gpt-oss-20b",   # pick one from Groq's model list
        "messages": [{"role": "user", "content": "Say hello in 3 words"}],
    },
    timeout=15,
)
print(response.status_code)
print(response.json()["choices"][0]["message"]["content"])
