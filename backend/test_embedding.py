import asyncio

from app.ai.embeddings import generate_embedding


async def main():
    text = """
    IntelliVault is an AI-powered developer workspace.
    It allows users to upload technical documents and
    analyze their contents using retrieval augmented generation.
    """

    embedding = await generate_embedding(text)

    print("Embedding generated successfully")
    print("Dimensions:", len(embedding))
    print("First 5 values:", embedding[:5])


if __name__ == "__main__":
    asyncio.run(main())