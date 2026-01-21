from groq import Groq

client = Groq(api_key="xxxxx")

def query_llama(prompt):
    print(prompt)
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_completion_tokens=512,
        stream=False
    )

    return completion.choices[0].message.content
