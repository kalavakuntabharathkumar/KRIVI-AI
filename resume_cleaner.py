# resume_precleaner.py
import re
from urllib.parse import urlparse

__all__ = ["standardize_resume_text"]

# ------------------------------------------------------------------
# Canonical section map  (add aliases if you like)
# ------------------------------------------------------------------
SECTION_MAP = {
    "SUMMARY":      ["summary", "profile", "objective", "about"],
    "CONTACT":      ["contact", "contact info", "contact information"],
    "SKILLS":       ["skills", "technical skills", "competencies"],
    "EXPERIENCE":   ["experience", "work experience", "professional experience",
                     "employment", "employment history", "work history"],
    "PROJECTS":     ["projects", "project experience"],
    "EDUCATION":    ["education", "academic", "academics"],
    "CERTIFICATES": ["certificates", "certifications", "licenses"],
    "LANGUAGES":    ["languages", "language proficiency"],
}

BULLET = re.compile(r"^[\s\u2022\u2023\u25E6\u2043\u2219•·●\-]+")
MULTI_SPACE = re.compile(r"\s{2,}")
URL_RX = re.compile(r"(https?://[^\s]+|www\.[^\s]+)", re.I)

def _canonical_heading(line: str) -> str | None:
    txt = line.lower().rstrip(":")
    for canon, aliases in SECTION_MAP.items():
        if txt in aliases:
            return canon
    return None

def _clean_line(line: str) -> str:
    """Strip leading bullets & excessive spaces."""
    line = BULLET.sub("", line)
    line = MULTI_SPACE.sub(" ", line)
    return line.strip()

# ------------------------------------------------------------------
# Main cleaner
# ------------------------------------------------------------------
def standardize_resume_text(text: str) -> str:
    """Return a bullet‑clean, ATS‑friendly résumé string."""
    # Normalise line endings & remove blank lines
    lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]

    output: list[str] = []
    section = None

    for raw in lines:
        line = _clean_line(raw)

        # Is it a section header?
        canon = _canonical_heading(line)
        if canon:
            section = canon
            output.append(f"\n{canon}:")
            continue

        # First line becomes SUMMARY if no section yet
        if section is None:
            section = "SUMMARY"
            output.append(f"\nSUMMARY:")

        # Wrap any URL in angle‑brackets (<…>) for ATS parsers
        line = URL_RX.sub(lambda m: f"<{m.group(0)}>", line)

        # Avoid duplicate bullets
        if line.startswith("- "):
            output.append(line)
        else:
            output.append(f"- {line}")

    # Collapse triplicate newlines
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()
    return cleaned
