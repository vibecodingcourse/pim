from openai import OpenAI
import os

# Replace this line with your real method of loading the key:
os.environ["OPENAI_API_KEY"] = "sk-proj-2RaWxuLKlPHGtTohDwf1T3BlbkFJkgujlSG5ym56OHjjnoyE"

client = OpenAI()

try:
    response = client.chat.completions.create(
        model="gpt-4.1",  # Use gpt-4.0-turbo or gpt-3.5-turbo if unsure
        messages=[{"role": "user", "content": "Hello, are you working?"}]
    )
    print("✅ Success:", response.choices[0].message.content)
except Exception as e:
    print("❌ Error:", e)