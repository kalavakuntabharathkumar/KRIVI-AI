import os
import fitz  # PyMuPDF
import re

def extract_text_from_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        return ""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
    return text

def clean_line(line):
    return re.sub(r'^[•\-\.\u2022\s]+', '', line.strip())

def normalize(line):
    return ''.join(line.lower().split())

def extract_section(lines, start_index, stop_words, limit=25):
    section = []
    for line in lines[start_index+1:]:
        norm = normalize(line)
        if any(norm.startswith(sw) for sw in stop_words):
            break
        if line:
            section.append(clean_line(line))
        if len(section) >= limit:
            break
    return section

def parse_resume_text(raw_text):
    lines = [clean_line(line) for line in raw_text.splitlines() if line.strip()]
    info = {
        "name": "Your Name",
        "title": "Your Role",
        "email": "Not Available",
        "phone": "Not Available",
        "skills": [],
        "projects": [],
        "experience": [],
        "certificates": [],
        "education": [],
        "languages": [],
        "links": [],
        "photo": None
    }

    stop_words = [
        "skills", "projects", "experience", "certificates", "education",
        "languages", "awards", "links", "summary", "objectives", "profile"
    ]

    for i, line in enumerate(lines[:5]):
        if info["name"] == "Your Name" and len(line.split()) >= 2:
            info["name"] = line
        elif info["title"] == "Your Role" and not any(x in line.lower() for x in ["@", "+91", "phone", "http", "www"]):
            info["title"] = str(line).title()

    for i, line in enumerate(lines):
        norm = normalize(line)

        if info["email"] == "Not Available":
            match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line)
            if match:
                info["email"] = match.group(0)

        if info["phone"] == "Not Available":
            match = re.search(r'(\+91[-\s]?)?(\(?\d{2,5}\)?[-\s]?)?\d{3,5}[-\s]?\d{4,6}', line)
            if match:
                info["phone"] = match.group(0)

        if "skill" in norm and not info["skills"]:
            info["skills"] = extract_section(lines, i, stop_words)

        elif "language" in norm and not info["languages"]:
            info["languages"] = extract_section(lines, i, stop_words)

        elif any(k in norm for k in ["certificate", "award", "achievement"]) and not info["certificates"]:
            raw_certs = extract_section(lines, i, stop_words)
            info["certificates"] = [{"title": c, "issuer": "", "date": ""} for c in raw_certs]

        elif "education" in norm and not info["education"]:
            raw_edu = extract_section(lines, i, stop_words)
            structured = []
            for edu_line in raw_edu:
                degree = edu_line
                institution = ""
                year = ""
                description = ""
                if '-' in edu_line:
                    parts = edu_line.split('-')
                    degree = parts[0].strip()
                    if len(parts) > 1:
                        institution = parts[1].strip()
                structured.append({
                    "degree": degree,
                    "institution": institution,
                    "year": year,
                    "description": description
                })
            info["education"] = structured

        elif "experience" in norm and not info["experience"]:
            raw_exp = extract_section(lines, i, stop_words)
            info["experience"] = [str(e) for e in raw_exp]

        elif not info["projects"]:
            project_lines = [l for l in lines if re.search(r'(technolog|source|github|project|system|application|api|model)', l, re.IGNORECASE)]
            structured = []
            current = {"title": "", "description": "", "tech": "", "link": ""}
            for pline in project_lines:
                if re.search(r'(github|http|www\.)', pline, re.IGNORECASE):
                    current["link"] = pline
                elif re.search(r'technolog|stack|tools', pline, re.IGNORECASE):
                    current["tech"] = pline.split(":")[-1].strip()
                elif ":" in pline:
                    if current["title"]:
                        structured.append(current)
                        current = {"title": "", "description": "", "tech": "", "link": ""}
                    parts = pline.split(":", 1)
                    current["title"] = parts[0].strip()
                    current["description"] = parts[1].strip()
                else:
                    current["description"] += " " + pline

            if current["title"]:
                structured.append(current)
            info["projects"] = structured

        urls = re.findall(r'(https?://\S+|www\.\S+)', line)
        for u in urls:
            clean = u.strip().rstrip('.')
            if clean not in info["links"]:
                info["links"].append(clean)

    return info
