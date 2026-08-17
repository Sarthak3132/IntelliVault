import asyncio

from google import genai
from google.genai import types

from app.core.config import settings


client = genai.Client(
    api_key=settings.gemini_api_key
)


async def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:

    if not texts:
        return []

    async def generate_one(text: str) -> list[float]:
        response = await asyncio.to_thread(
            client.models.embed_content,
            model="gemini-embedding-2",
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=768,
            ),
        )

        return response.embeddings[0].values

    embeddings = await asyncio.gather(
        *(generate_one(text) for text in texts)
    )

    return embeddings