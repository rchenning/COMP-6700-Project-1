import re


def extract_json_block(text: str) -> str:
    """
    Extract first valid JSON array from messy LLM output.
    """
    if not text:
        return ""

    # Find first [ ... ]
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)

    return text.strip()