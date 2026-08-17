from pathlib import Path
import io

from pypdf import PdfReader


ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
}


def extract_text(
    filename: str,
    contents: bytes,
) -> str:

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Only PDF, TXT and Markdown files are supported"
        )

    if extension in {".txt", ".md"}:
        return contents.decode("utf-8")

    if extension == ".pdf":
        reader = PdfReader(
            io.BytesIO(contents)
        )

        pages = []

        for page in reader.pages:
            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n\n".join(pages)

    raise ValueError("Unsupported file type")