import asyncio
from openai import AsyncOpenAI

async def test():
    client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    
    system_prompt = """You are an expert at creating internship subjects for a Tunisian telecom company called SOTETEL.
Analyze the provided student CV(s) and generate one internship subject that matches their skills and level.
Respond only in valid JSON with exactly these fields and no other text:
{
  "titre": "subject title in French",
  "description": "2-3 sentence description in French",
  "techno": ["tech1", "tech2", "tech3"],
  "prerequis": "prerequisites in French",
  "niveau": "one of: L1, L2, L3, M1, M2, ING1, ING2, ING3"
}"""
    
    cv_text = "Full Stack Developer with expertise in JavaScript and Python"
    user_prompt = f"Student CV(s):\n{cv_text}\n\nGenerate the internship subject JSON:"
    
    print("Calling Ollama chat completions...")
    response = await client.chat.completions.create(
        model="llama3.2",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    raw = response.choices[0].message.content
    print("RAW RESPONSE:")
    print(raw)
    print("REPR:")
    print(repr(raw))

if __name__ == "__main__":
    asyncio.run(test())
