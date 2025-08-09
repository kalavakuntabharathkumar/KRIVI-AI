# resume_parser.py  – enhanced to fix certificate parsing issue
# -------------------------------------------------------------------

import re
from pathlib import Path
from typing import List, Dict, Any

# -------- Regex helpers ---------------------------------------------------
EMAIL_RX  = re.compile(r"[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}")
PHONE_RX  = re.compile(r"(\+?\d[\d\s\-.]{7,}\d)")
URL_RX    = re.compile(r"(https?://\S+|www\.\S+)")
BULLET_RX = re.compile(r"^[•\-\u2022\d.\s]+")

# -------- Canonical section names & aliases -------------------------------

SECTION_MAP = {
    "summary": [
        "summary", "objective", "profile", "professional summary"
    ],
    "skills": [
        "skills", "technical skills", "key skills", "expertise"
    ],
    "projects": [
        "projects", "project", "personal projects", "notable projects"
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment history", "work history"
    ],
    "education": [
        "education", "academic", "qualifications", "academic background"
    ],
    "certificates": [
        "certificates", "certificate", "certifications", "certification",
        "awards", "award", "achievements", "recognitions", "certifications & awards"
    ],
    "languages": [
        "languages", "language", "spoken languages"
    ],
    "links": [
        "links", "contact", "social", "profiles", "online presence"
    ]
}

HEADER_LOOKUP = {alias: canon for canon, aliases in SECTION_MAP.items() for alias in aliases}

# -------- Public API -------------------------------------------------------

def parse_resume_text(raw_text: str) -> Dict[str, Any]:
    lines = _preprocess(raw_text)

    # containers
    buckets: Dict[str, List[str]] = {k: [] for k in SECTION_MAP}
    misc: List[str] = []

    current = None

    for line in lines:
        key = HEADER_LOOKUP.get(line.lower().rstrip(':'))
        if key:
            current = key
            continue

        if current:
            if current == "certificates":
                cleaned_line = line.strip("•*-· \t").strip()
                if cleaned_line:
                    buckets[current].append(cleaned_line)
            else:
                buckets[current].append(line)
        else:
            misc.append(line)

        if URL_RX.search(line):
            url = URL_RX.search(line).group(0).rstrip(".,)")
            if url not in buckets["links"]:
                buckets["links"].append(url)

    data: Dict[str, Any] = {
        "name"       : _guess_name(misc + buckets["summary"]),
        "title"      : _guess_title(misc + buckets["summary"]),
        "email"      : _first_match(EMAIL_RX, raw_text, default="Not Available"),
        "phone"      : _first_match(PHONE_RX,  raw_text, default="Not Available"),
        "summary"    : " ".join(buckets["summary"]).strip(),
        "skills"     : _split_skills(buckets["skills"]),
        "projects"   : _structure_projects(buckets["projects"]),
        "experience" : _structure_experience(buckets["experience"]),
        "education"  : _structure_education(buckets["education"]),
        "certificates": [{"title": l} for l in buckets["certificates"]],
        "languages"  : _split_simple(buckets["languages"]),
        "links"      : buckets["links"],
        "photo"      : None,
        "misc"       : misc
    }

    if not data["summary"]:
        data["summary"] = "Experienced professional with a passion for excellence."

    return data

# -------- Helper functions -------------------------------------------------

def _preprocess(text: str) -> List[str]:
    cleaned = []
    for raw in text.splitlines():
        line = BULLET_RX.sub("", raw).strip()
        if line:
            cleaned.append(line)
    return cleaned

def _first_match(rx: re.Pattern, text: str, *, default=""):
    m = rx.search(text)
    return m.group(0) if m else default

def _guess_name(lines: List[str]) -> str:
    for l in lines[:6]:
        if 2 <= len(l.split()) <= 5 and not any(ch.isdigit() or ch in "@" for ch in l):
            return l.title()
    return "Your Name"

def _guess_title(lines: List[str]) -> str:
    for l in lines[:6]:
        if any(k in l.lower() for k in ("developer", "engineer", "manager", "intern", "student")):
            return l.title()
    return "Professional"

def _split_skills(sk_lines: List[str]) -> List[str]:
    if not sk_lines:
        return []
    blob = " ".join(sk_lines)
    parts = re.split(r",|/|;|\|", blob)
    return [p.strip() for p in parts if p.strip()]

def _split_simple(lines: List[str]) -> List[str]:
    res: List[str] = []
    for l in lines:
        res.extend([p.strip() for p in re.split(r",|/|;", l) if p.strip()])
    return res

def _structure_projects(lines: List[str]) -> List[Dict[str, str]]:
    projects: List[Dict[str, str]] = []
    current = None
    for l in lines:
        url = URL_RX.search(l)
        if url:
            if current:
                current.setdefault("link", url.group(0))
            continue
        if l.endswith(":" ) or l.isupper():
            if current:
                projects.append(current)
            current = {"title": l.rstrip(":"), "description": ""}
        else:
            if current is None:
                current = {"title": l, "description": ""}
            else:
                current["description"] += ("\n" if current["description"] else "") + l
    if current:
        projects.append(current)
    return projects

def _structure_experience(lines: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    current = None
    for l in lines:
        if any(k in l.lower() for k in ("intern", "developer", "engineer", "manager", "analyst", "consultant")):
            if current:
                out.append(current)
            current = {"title": l, "company": "", "duration": "", "location": "", "description": ""}
        elif re.search(r"\d{4}", l):
            if current:
                current["duration"] = l
        elif any(w in l.lower() for w in ("city", "remote", "onsite", "hybrid")):
            if current:
                current["location"] = l
        else:
            if current is None:
                current = {"title": l, "company": "", "duration": "", "location": "", "description": ""}
            else:
                current["description"] += ("\n" if current["description"] else "") + l
    if current:
        out.append(current)
    return out

def _structure_education(lines: List[str]) -> List[Dict[str, str]]:
    edu: List[Dict[str, str]] = []
    for l in lines:
        parts = re.split(r" - | – | — ", l, maxsplit=2)
        degree = parts[0].strip()
        institution = parts[1].strip() if len(parts) > 1 else ""
        year = parts[2].strip() if len(parts) > 2 else ""
        edu.append({"degree": degree, "institution": institution, "year": year})
    return edu

def extract_text_from_pdf(pdf_path: str) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(pdf_path)
