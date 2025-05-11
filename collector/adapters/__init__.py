import re


def parse_raw_title(raw_title):
    """
    Parse a raw title string into structured data.

    Args:
        raw_title (str): The raw title string to parse.

    Returns:
        dict: A dictionary containing extracted fields: player_name, card_year, set_name, card_number, grade,
              grading_company, and attributes.
    """
    # Define regex patterns for extracting information
    patterns = {
        "card_year": r"(19\d{2}|20\d{2})",
        "player_name": r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)",
        "set_name": r"(Topps|Bowman|Fleer|Upper Deck|Panini|Donruss|Score|Prizm|Chrome|Heritage)",
        "card_number": r"#(\d+)",
        "grade": r"(PSA|BGS|SGC|CGC)\s*(\d+(?:\.\d+)?)",
        "attributes": r"(RC|Refractor|Auto|Autograph|Patch|Jersey|Rookie)",
    }

    extracted = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, raw_title, re.IGNORECASE)
        if match:
            extracted[key] = match.group(0)

    # Post-process extracted data
    if "grade" in extracted:
        grading_match = re.match(patterns["grade"], extracted["grade"], re.IGNORECASE)
        if grading_match:
            extracted["grading_company"] = grading_match.group(1)
            extracted["grade"] = grading_match.group(2)

    return extracted
