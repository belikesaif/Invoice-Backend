import re

def normalize_hyphens(text: str) -> str:
    """
    Remove spaces around hyphens between words, e.g., 'A - B' -> 'A-B'.
    Also collapses multiple spaces to a single space elsewhere.
    """
    if not isinstance(text, str):
        return text
    # Remove spaces around hyphens
    text = re.sub(r'\s*-\s*', '-', text)
    # Optionally, collapse multiple spaces elsewhere
    text = re.sub(r' +', ' ', text)
    return text.strip() 