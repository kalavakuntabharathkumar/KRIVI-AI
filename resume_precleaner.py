import re
from urllib.parse import urlparse

__all__ = ["standardize_resume_text"]

SECTION_ALIASES = {
    "name": ["name"],
    "title": ["title", "profile", "designation", "objective"],
    "summary": ["summary", "career summary", "professional summary", "about me", "objective"],
    "contact": ["contact", "contact information", "contact info", "personal info"],
    "skills": ["skills", "technical skills", "core competencies"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history"],
    "projects": ["projects", "project experience", "personal projects", "professional projects"],
    "education": ["education", "academic", "education background", "academic qualifications"],
    "certificates": ["certificates", "certifications", "licenses"],
    "languages": ["languages", "language proficiency"],
    "links": ["links", "profiles", "social", "social links", "social profiles"],
}

BULLET_REGEX = re.compile(r"^[\s\u2022\u2023\u25E6\u2043\u2219\-]+")
HYPERLINK_REGEX = re.compile(r"(?P<url>https?://[\w./#?&:=+-]+)")


# ---------------------------------------------------------------------------
# 1. Clean individual lines
# ---------------------------------------------------------------------------

def _clean_line(line: str) -> str:
    """Remove bullets, excessive whitespace, and trailing punctuation."""
    # Remove leading bullet characters and whitespace
    line = BULLET_REGEX.sub("", line)
    # Collapse multiple spaces
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip()


# ---------------------------------------------------------------------------
# 2. Detect section headings and relabel consistently
# ---------------------------------------------------------------------------

def _standard_section(line: str) -> str | None:
    """Return canonical section name if line matches an alias."""
    lower = line.lower().rstrip(":")
    for canonical, aliases in SECTION_ALIASES.items():
        if any(lower == a for a in aliases):
            return canonical.upper()
    return None


# ---------------------------------------------------------------------------
# 3. Main cleaning function
# ---------------------------------------------------------------------------

def standardize_resume_text(text: str) -> str:
    """Return a perfectly formatted, ATS‑friendly résumé string."""
    text = text.replace("\r", "\n")  # Normalize EOL
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    output_lines: list[str] = []
    current_section = None

    for raw in lines:
        # Replace fancy bullets with hyphen, strip
        line = _clean_line(raw)

        # Section heading?
        canon = _standard_section(line)
        if canon:
            current_section = canon
            output_lines.append(f"\n{canon}:")
            continue

        # Hyperlink detection – wrap in angle brackets for ATS friendliness
        line = HYPERLINK_REGEX.sub(lambda m: f"<{m.group('url')}>", line)

        # Append under current section or Misc
        if current_section:
            output_lines.append(f"- {line}")
        else:
            # Anything before first recognized section goes to SUMMARY by default
            if output_lines and output_lines[-1].startswith("SUMMARY:"):
                output_lines.append(f"- {line}")
            else:
                output_lines.append("\nSUMMARY:")
                output_lines.append(f"- {line}")
                current_section = "SUMMARY"

    # Collapse excessive blank lines
    clean = "\n".join(output_lines)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()
