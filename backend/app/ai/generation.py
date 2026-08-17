import asyncio

from google import genai

from app.core.config import settings


client = genai.Client(
    api_key=settings.gemini_api_key
)


async def generate_answer(
    question: str,
    context: str,
) -> str:

    prompt = f"""
You are IntelliVault, a document question-answering assistant.

Answer the user's question using ONLY the provided document context.

Rules:
- Do not use outside knowledge.
- Do not invent information.
- If the answer cannot be found in the context, say:
  "I couldn't find the answer in the provided document."
- Give a clear and concise answer.

DOCUMENT CONTEXT:
----------------
{context}
----------------

USER QUESTION:
{question}
"""

    response = await asyncio.to_thread(
        client.models.generate_content,
        model="gemini-2.5-flash",
        contents=prompt,
    )

    return response.text