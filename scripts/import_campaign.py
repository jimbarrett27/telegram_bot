#!/usr/bin/env python3
"""Interactive CLI tool for importing adventure PDFs into campaign markdown.

Uses an LLM to convert raw PDF text into the structured markdown format
expected by campaign_loader.py. The user reviews the output and can
request revisions before saving.

Usage:
    python scripts/import_campaign.py path/to/adventure.pdf
    python scripts/import_campaign.py path/to/adventure.pdf --name hangover
    python scripts/import_campaign.py path/to/adventure.pdf --model gemini-2.0-flash
"""

import argparse
import sys
from pathlib import Path

# Add repo root to path so we can import project modules
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

CAMPAIGNS_DIR = REPO_ROOT / "dnd" / "campaigns"

SYSTEM_PROMPT = """\
You are a D&D adventure formatter. Convert the raw PDF text into structured \
markdown using EXACTLY this format:

# Adventure Title

Brief overview/introduction paragraph(s).

## Section Heading

Section content...

## Another Section

More content...

Rules:
- Use a single # for the adventure title (level-1 heading)
- Use ## for all section headings (level-2 headings)
- Preserve all important content: NPCs, locations, encounters, DCs, treasure, etc.
- Use markdown formatting (bold, bullet lists, etc.) within sections
- Keep the original structure and flow of the adventure
- Do NOT add content that isn't in the source material
- Do NOT use ### or deeper headings — only # and ##
"""


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract raw text from a PDF using PyMuPDF."""
    import fitz

    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages)


def run_import(pdf_path: Path, name: str, model_name: str) -> None:
    """Run the interactive import loop."""
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    from gcp_util.secrets import get_gemini_api_key

    print(f"Extracting text from {pdf_path.name}...")
    raw_text = extract_pdf_text(pdf_path)
    print(f"Extracted {len(raw_text)} characters from {pdf_path.name}")

    api_key = get_gemini_api_key()
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
    )

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Convert this adventure PDF text to markdown:\n\n{raw_text}"),
    ]

    print(f"\nSending to {model_name} for conversion...")
    response = llm.invoke(messages)
    result = response.content
    messages.append(AIMessage(content=result))

    print("\n" + "=" * 60)
    print(result)
    print("=" * 60)

    output_path = CAMPAIGNS_DIR / f"{name}.md"

    while True:
        print(f"\nCommands: 'save' or 'ok' to write to {output_path}")
        print("          'quit' to abort")
        print("          anything else = feedback for revision")
        user_input = input("> ").strip()

        if not user_input:
            continue

        if user_input.lower() in ("quit", "q", "exit"):
            print("Aborted.")
            return

        if user_input.lower() in ("save", "ok", "yes", "y"):
            CAMPAIGNS_DIR.mkdir(parents=True, exist_ok=True)
            output_path.write_text(result)
            print(f"\nSaved to {output_path}")

            # Verify it parses correctly
            from dnd.campaign_loader import parse_campaign_markdown
            sections = parse_campaign_markdown(output_path)
            print(f"Parsed {len(sections)} sections:")
            for s in sections:
                preview = s["content"][:60].replace("\n", " ")
                print(f"  - {s['title']}: {preview}...")
            return

        # Send feedback for revision
        messages.append(HumanMessage(content=user_input))
        print(f"\nRevising...")
        response = llm.invoke(messages)
        result = response.content
        messages.append(AIMessage(content=result))

        print("\n" + "=" * 60)
        print(result)
        print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Import a PDF adventure into campaign markdown format"
    )
    parser.add_argument("pdf", type=Path, help="Path to the adventure PDF")
    parser.add_argument(
        "--name",
        help="Campaign name (used for filename). Defaults to PDF stem.",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model to use (default: gemini-2.0-flash)",
    )

    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: {args.pdf} not found", file=sys.stderr)
        sys.exit(1)

    name = args.name or args.pdf.stem
    run_import(args.pdf, name, args.model)


if __name__ == "__main__":
    main()
