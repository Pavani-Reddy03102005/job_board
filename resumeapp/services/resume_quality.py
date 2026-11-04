"""
Deterministic resume analysis: structure, wording, readability and
machine-readability (ATS) indicators.

Nothing here calls an AI model or invents data. Every finding is computed from
the text extracted from the uploaded file, and every score is the sum of
visible checks (points earned / points available).
"""
import re

from .skills_extractor import (
    extract_skills,
    extract_skills_by_category,
    find_skills,
    skill_pattern,
)

# --------------------------------------------------------------- sections

SECTION_ORDER = ["summary", "education", "experience", "projects", "skills",
                 "certifications", "achievements"]

SECTION_LABELS = {
    "summary": "Summary",
    "education": "Education",
    "experience": "Experience",
    "projects": "Projects",
    "skills": "Skills",
    "certifications": "Certifications",
    "achievements": "Achievements",
}

SECTION_ALIASES = {
    "summary": ["summary", "professional summary", "career summary", "profile",
                "professional profile", "objective", "career objective", "about me"],
    "education": ["education", "academic background", "academic qualifications",
                  "academics", "educational qualifications", "qualifications"],
    "experience": ["experience", "work experience", "professional experience",
                   "employment history", "work history", "employment", "internship",
                   "internships", "internship experience"],
    "projects": ["projects", "academic projects", "personal projects", "project work",
                 "key projects", "major projects"],
    "skills": ["skills", "technical skills", "key skills", "core competencies",
               "technologies", "technical proficiency", "skills & tools",
               "skills and tools", "technical skills & tools"],
    "certifications": ["certifications", "certification", "certificates",
                       "licenses & certifications", "courses", "training"],
    "achievements": ["achievements", "awards", "honors", "accomplishments",
                     "awards and achievements", "awards & achievements"],
}

_HEADING_LOOKUP = {a: key for key, aliases in SECTION_ALIASES.items() for a in aliases}

BULLET_RE = re.compile(
    r"^\s*(?:[•●▪■◦‣∙·\u2022\uf000-\uf8ff]\s*|[\-–—*]\s+|\d{1,2}[.)]\s+)"
)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{8,16}\d")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
WEAK_PHRASE_RE = re.compile(
    r"responsible for|worked on|helped (?:with|in)|duties included|involved in|"
    r"assisted (?:with|in)|tasked with", re.IGNORECASE)
ICON_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\ue000-\uf8ff]")

ACTION_VERBS = set("""
achieved analyzed analysed architected automated built collaborated configured
contributed coordinated created debugged delivered deployed designed developed
documented drove engineered enhanced established evaluated executed extracted
generated implemented improved increased initiated integrated launched led
leveraged maintained managed mentored migrated optimized optimised organized
organised performed presented produced reduced refactored researched resolved
scaled secured simplified spearheaded streamlined tested trained utilized
utilised visualized wrote applied authored deployed orchestrated programmed
""".split())


def _heading_key(line):
    if len(line) > 45 or len(line.split()) > 6:
        return None
    norm = re.sub(r"[^a-z& ]+", " ", line.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return _HEADING_LOOKUP.get(norm)


def _plausible_phone(text):
    for cand in PHONE_CANDIDATE_RE.findall(text):
        digits = re.sub(r"\D", "", cand)
        if 10 <= len(digits) <= 13 and len(YEAR_RE.findall(cand)) < 2:
            return True
    return False


def parse_resume(raw_text):
    """Split the text into lines and sections and collect basic statistics."""
    lines = [l.strip() for l in (raw_text or "").splitlines() if l.strip()]
    text = "\n".join(lines)
    flattened = len(lines) < 6 and len(text) > 500

    headings, sections, line_sections = {}, {}, []
    current = "header"
    for i, line in enumerate(lines):
        key = None if flattened else _heading_key(line)
        if key:
            current = key
            headings.setdefault(key, i)
            line_sections.append("heading")
            continue
        line_sections.append(current)
        sections.setdefault(current, []).append(line)

    if flattened:
        found = [k for k in SECTION_ORDER
                 if any(re.search(r"\b%s\b" % re.escape(a), text, re.IGNORECASE)
                        for a in SECTION_ALIASES[k])]
    else:
        found = [k for k in SECTION_ORDER if k in headings]

    bullets = [BULLET_RE.sub("", l).strip() for l in lines if BULLET_RE.match(l)]
    bullets = [b for b in bullets if b]

    def starts_with_verb(b):
        first = re.sub(r"[^a-z]", "", b.split()[0].lower()) if b.split() else ""
        return first in ACTION_VERBS

    def measurable(b):
        return bool(re.search(r"\d", YEAR_RE.sub("", b)))

    verb_bullets = [b for b in bullets if starts_with_verb(b)]
    non_verb = [b for b in bullets if not starts_with_verb(b)]
    long_bullets = [b for b in bullets if len(b.split()) > 35]
    words = len(re.findall(r"\w+", text))

    return {
        "lines": lines,
        "text": text,
        "flattened": flattened,
        "headings": headings,
        "found_sections": found,
        "sections": sections,
        "line_sections": line_sections,
        "bullets": bullets,
        "contact": {
            "email": bool(EMAIL_RE.search(text)),
            "phone": _plausible_phone(text),
            "linkedin": bool(re.search(r"linkedin\.com/", text, re.IGNORECASE)),
            "github": bool(re.search(r"github\.com/\w", text, re.IGNORECASE)),
        },
        "stats": {
            "words": words,
            "lines": len(lines),
            "bullets": len(bullets),
            "action_verb_bullets": len(verb_bullets),
            "measurable_bullets": sum(1 for b in bullets if measurable(b)),
            "long_bullets": len(long_bullets),
            "avg_bullet_words": round(sum(len(b.split()) for b in bullets) / len(bullets), 1)
                                if bullets else 0,
            "weak_phrases": len(WEAK_PHRASE_RE.findall(text)),
            "long_lines": sum(1 for l in lines if len(l.split()) > 45),
            "non_verb_examples": [b[:70] for b in non_verb[:3]],
        },
    }


def looks_like_resume(raw_text):
    """True when the text shows at least two typical resume signals."""
    parsed = parse_resume(raw_text)
    signals = [
        parsed["contact"]["email"],
        parsed["contact"]["phone"],
        len(parsed["found_sections"]) >= 2,
        bool(find_skills(raw_text)),
        len(YEAR_RE.findall(raw_text or "")) >= 2,
    ]
    return sum(signals) >= 2


# ------------------------------------------------------------------ checks

_STATUS_LABELS = {"pass": "Good", "warn": "Needs work", "fail": "Problem", "info": "Note"}


def _check(cid, category, title, points, max_points, detail, recommendation="", strength=""):
    points = int(round(points))
    if max_points == 0:
        status = "info"
    else:
        ratio = points / max_points
        status = "pass" if ratio >= 0.8 else "warn" if ratio >= 0.4 else "fail"
    if status in ("pass", "info"):
        priority = "low"
    elif status == "fail" and max_points >= 10:
        priority = "high"
    else:
        priority = "medium"
    return {
        "id": cid, "category": category, "title": title,
        "points": points, "max_points": max_points,
        "status": status, "status_label": _STATUS_LABELS[status],
        "priority": priority, "detail": detail,
        "recommendation": recommendation if status in ("warn", "fail") else "",
        "strength": strength if status == "pass" else "",
    }


def evaluate_quality(parsed):
    """Resume-quality checklist worth 100 points."""
    s, found, c = parsed["stats"], set(parsed["found_sections"]), parsed["contact"]
    checks = []

    # ---- Structure (40)
    for key, pts in (("education", 10), ("skills", 10)):
        label, ok = SECTION_LABELS[key], key in found
        checks.append(_check(
            "section_" + key, "Structure", label + " section", pts if ok else 0, pts,
            "A '%s' heading was found." % label if ok else "No '%s' heading was detected." % label,
            "Add a clearly labelled '%s' section." % label,
            "Your resume has a clear %s section." % label))
    has_exp, has_proj = "experience" in found, "projects" in found
    if has_exp or has_proj:
        names = " and ".join(SECTION_LABELS[k] for k in ("experience", "projects") if k in found)
        detail = "Found: %s." % names
    else:
        detail = "Neither an Experience/Internship nor a Projects heading was detected."
    checks.append(_check(
        "section_work", "Structure", "Experience or projects section",
        15 if (has_exp or has_proj) else 0, 15, detail,
        "Add a Projects or Experience (including internships) section describing what you built or did.",
        "You show practical work (%s)." % detail.replace("Found: ", "").rstrip(".")))
    checks.append(_check(
        "section_summary", "Structure", "Summary or objective",
        5 if "summary" in found else 0, 5,
        "A summary/objective heading was found." if "summary" in found
        else "No summary or objective heading was detected.",
        "Add a 2-3 line summary that describes your actual background and the roles you target.",
        "You include a professional summary."))

    # ---- Contact (15)
    checks.append(_check(
        "contact_email", "Contact", "Email address", 5 if c["email"] else 0, 5,
        "An email address was detected." if c["email"] else "No email address was detected.",
        "Add a professional email address near the top.", "Your email address is present."))
    checks.append(_check(
        "contact_phone", "Contact", "Phone number", 5 if c["phone"] else 0, 5,
        "A phone number was detected." if c["phone"] else "No phone number was detected.",
        "Add a phone number near the top.", "Your phone number is present."))
    link_ok = c["linkedin"] or c["github"]
    checks.append(_check(
        "contact_links", "Contact", "LinkedIn or GitHub link", 5 if link_ok else 0, 5,
        "A LinkedIn/GitHub link was detected." if link_ok else "No LinkedIn or GitHub link was detected.",
        "Add your LinkedIn and/or GitHub profile URL (as plain text) so recruiters can see your work.",
        "You link to an online profile."))

    # ---- Content (30)
    n = s["bullets"]
    if n == 0:
        none_msg = "No bullet points were detected, so this could not be evaluated."
        checks.append(_check("bullets", "Content", "Bullet-point descriptions", 0, 5, none_msg,
                             "Describe projects and experience as short bullet points."))
        checks.append(_check("action_verbs", "Content", "Action verbs", 0, 10, none_msg,
                             "Start each bullet with an action verb such as Built, Designed or Improved."))
        checks.append(_check("measurable", "Content", "Measurable results", 0, 10, none_msg,
                             "Where true, add real numbers such as users, size, speed or time saved."))
    else:
        checks.append(_check("bullets", "Content", "Bullet-point descriptions", 5, 5,
                             "%d bullet points were detected." % n, "",
                             "Your experience is written as scannable bullet points (%d found)." % n))
        rate = s["action_verb_bullets"] / n
        pts = 10 * min(rate / 0.6, 1)
        ex = s["non_verb_examples"]
        checks.append(_check(
            "action_verbs", "Content", "Action verbs", pts, 10,
            "%d of %d bullets (%d%%) start with an action verb.%s" % (
                s["action_verb_bullets"], n, round(rate * 100),
                " For example: \u201c%s\u201d." % ex[0] if ex else ""),
            "Begin more bullets with strong verbs (Built, Implemented, Reduced) and rewrite lines "
            "such as the example above.",
            "Most of your bullets start with action verbs (%d%%)." % round(rate * 100)))
        mrate = s["measurable_bullets"] / n
        pts = 10 * min(mrate / 0.3, 1)
        checks.append(_check(
            "measurable", "Content", "Measurable results", pts, 10,
            "%d of %d bullets (%d%%) contain a number or percentage." % (
                s["measurable_bullets"], n, round(mrate * 100)),
            "Where you have the real figure (users, records, speed, accuracy, time saved), add it. "
            "If you do not have one, describe the outcome without inventing a number.",
            "Many bullets include concrete numbers (%d%%)." % round(mrate * 100)))
    wp = s["weak_phrases"]
    checks.append(_check(
        "weak_phrases", "Content", "Passive or vague phrases",
        5 if wp == 0 else 2 if wp <= 2 else 0, 5,
        "No vague phrases such as 'responsible for' or 'worked on' were found." if wp == 0
        else "%d vague phrase(s) such as 'responsible for' or 'worked on' were found." % wp,
        "Replace phrases like 'responsible for' or 'worked on' with what you actually did and achieved.",
        "You avoid vague phrases such as 'responsible for'."))

    # ---- Readability (15)
    w = s["words"]
    if 250 <= w <= 900:
        pts = 8
    elif w < 250:
        pts = 8 * w / 250
    elif w <= 1200:
        pts = 5
    else:
        pts = 2
    checks.append(_check(
        "length", "Readability", "Resume length", pts, 8,
        "The resume contains about %d words." % w,
        "A one- to two-page resume usually falls between roughly 250 and 900 words; "
        "add detail if it is short, or trim older or less relevant content if it is long.",
        "Your resume length (about %d words) is in a readable range." % w))
    if n:
        pts = 7
        if s["avg_bullet_words"] > 25:
            pts -= 2
        long_ratio = s["long_bullets"] / n
        pts -= 5 if long_ratio > 0.4 else 3 if long_ratio > 0.2 else 0
        detail = "Bullets average %s words; %d are longer than 35 words." % (
            s["avg_bullet_words"], s["long_bullets"])
    else:
        pts = 7 if s["long_lines"] == 0 else 3 if s["long_lines"] <= 2 else 0
        detail = "%d line(s) are longer than 45 words." % s["long_lines"]
    checks.append(_check(
        "sentence_length", "Readability", "Concise bullets and lines", max(pts, 0), 7, detail,
        "Split long bullets into one achievement each; aim for about 15-25 words per bullet.",
        "Your bullets are concise."))

    # ---- Informational (no points)
    repeated = [m for m in re.findall(r"\b(\w{3,})\s+\1\b", parsed["text"], re.IGNORECASE)
                if m.lower() not in ("had", "that")]
    checks.append(_check(
        "repeated_words", "Language", "Repeated words", 0, 0,
        "No accidentally repeated words were found." if not repeated
        else "Repeated words found: %s." % ", ".join(sorted(set(repeated))[:4]),
        ""))
    checks.append(_check(
        "spelling", "Language", "Spelling and grammar", 0, 0,
        "Spelling and grammar are not checked automatically. Proofread your resume or ask someone to.", ""))

    return {"score": sum(ch["points"] for ch in checks), "max": 100, "checks": checks}


def evaluate_ats(parsed, meta=None):
    """Machine-readability checklist worth 100 points (not an employer ATS score)."""
    meta = meta or {}
    found = set(parsed["found_sections"])
    c, s = parsed["contact"], parsed["stats"]
    chars = meta.get("chars", len(parsed["text"]))
    checks = []

    from .parser import MIN_TEXT_CHARS
    readable = chars >= MIN_TEXT_CHARS
    checks.append(_check(
        "ats_text", "ATS", "Text can be extracted", 25 if readable else 0, 25,
        "%d characters of text were extracted from the file." % chars if readable
        else "Very little text could be extracted from the file.",
        "Use a text-based PDF or a DOCX file; scanned images cannot be read by software.",
        "Software can extract the text from your file."))

    core = sum([("education" in found), ("skills" in found), bool({"experience", "projects"} & found)])
    recognised = ", ".join(SECTION_LABELS[k] for k in SECTION_ORDER if k in found) or "none"
    checks.append(_check(
        "ats_headings", "ATS", "Standard section headings", 25 * core / 3, 25,
        "Recognised headings: %s." % recognised,
        "Use conventional headings (Education, Experience or Projects, Skills) so parsers can sort your content.",
        "Your headings are standard and recognisable."))

    both = c["email"] and c["phone"]
    one = c["email"] or c["phone"]
    checks.append(_check(
        "ats_contact", "ATS", "Contact details in plain text", 10 if both else 5 if one else 0, 10,
        "Email %s, phone %s in the extracted text." % (
            "found" if c["email"] else "not found", "found" if c["phone"] else "not found"),
        "Put your email and phone in the body of the document as plain text, not inside images or text boxes.",
        "Your contact details are readable as plain text."))

    risks = []
    if meta.get("tables"):
        risks.append("tables (%d)" % meta["tables"])
    if meta.get("text_boxes"):
        risks.append("text boxes")
    if meta.get("multi_column"):
        risks.append("a possible multi-column layout")
    inspected = "tables" in meta
    checks.append(_check(
        "ats_layout", "ATS", "Simple layout",
        max(0, 20 - 10 * len(risks)) if inspected else 20, 20,
        ("Possible layout risks: %s." % ", ".join(risks)) if risks
        else ("No tables, text boxes or columns were detected." if inspected
              else "Layout could not be inspected."),
        "Prefer a single-column layout without tables or text boxes; many parsers read these in the wrong order.",
        "Your layout looks simple and parser-friendly."))

    icons = sum(len(ICON_RE.findall(BULLET_RE.sub("", l))) for l in parsed["lines"])
    checks.append(_check(
        "ats_symbols", "ATS", "Special symbols and icons", 10 if icons == 0 else 5 if icons <= 3 else 0, 10,
        "No icons or unusual symbols were found." if icons == 0
        else "%d icon or special symbol(s) were found." % icons,
        "Replace icons and decorative symbols with plain text labels (for example 'Email:' instead of an envelope icon).",
        "You avoid icons and decorative symbols."))

    lines = parsed["lines"]
    fragments = sum(1 for l in lines if len(l.split()) <= 2)
    if parsed["flattened"] or len(lines) < 8:
        pts, detail = 0, "The text has almost no line breaks, so its structure may be lost."
    else:
        ratio = fragments / len(lines)
        pts = 10 if ratio <= 0.25 else 4
        detail = "%d%% of lines are one or two words long." % round(ratio * 100)
    checks.append(_check(
        "ats_structure", "ATS", "Readable line structure", pts, 10, detail,
        "Many very short lines can mean columns or tables were broken apart; use one column of normal lines.",
        "Your text keeps a clean line-by-line structure."))

    return {
        "score": sum(ch["points"] for ch in checks), "max": 100, "checks": checks,
        "warnings": [ch["detail"] for ch in checks if ch["status"] in ("warn", "fail")],
    }


# ---------------------------------------------------------------- findings

_PRIORITY_RANK = {"high": 0, "medium": 1, "low": 2}

ROLE_PROFILES = {
    "Backend / Python Developer": ["Python", "Django", "Flask", "FastAPI", "Django REST Framework",
                                   "SQL", "PostgreSQL", "MySQL", "REST API", "Docker", "Git"],
    "Frontend Developer": ["HTML", "CSS", "JavaScript", "TypeScript", "React", "Angular", "Vue.js",
                           "Bootstrap", "Tailwind CSS", "Git"],
    "Full-Stack Developer": ["HTML", "CSS", "JavaScript", "React", "Node.js", "Python", "Django",
                             "SQL", "MongoDB", "REST API", "Git"],
    "Data Analyst": ["SQL", "Python", "pandas", "NumPy", "Matplotlib", "Data Analysis",
                     "Power BI", "Tableau", "Microsoft Excel"],
    "Machine Learning Engineer": ["Python", "Machine Learning", "Deep Learning", "scikit-learn",
                                  "TensorFlow", "PyTorch", "Keras", "pandas", "NumPy", "NLP",
                                  "Computer Vision"],
    "Java Developer": ["Java", "Spring Boot", "Hibernate", "SQL", "MySQL", "Maven", "REST API",
                       "Git", "OOP"],
    "DevOps / Cloud Engineer": ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "Linux", "Jenkins",
                                "CI/CD", "Git", "Bash"],
}


def suggest_roles(skills):
    have = set(skills)
    out = []
    for role, wanted in ROLE_PROFILES.items():
        matched = [s for s in wanted if s in have]
        pct = round(100 * len(matched) / len(wanted))
        if len(matched) >= 2 and pct >= 25:
            out.append({"role": role, "match_percent": pct, "matched": matched})
    return sorted(out, key=lambda r: -r["match_percent"])[:3]


def _listed_only_skills(parsed, skills):
    """Skills that appear in the skills list/header but in no experience/project line."""
    if not ({"experience", "projects"} & set(parsed["found_sections"])) or parsed["flattened"]:
        return []
    demo_lines = [l for l, sec in zip(parsed["lines"], parsed["line_sections"])
                  if sec in ("experience", "projects")]
    demo_text = "\n".join(demo_lines)
    return [s for s in skills if not skill_pattern(s).search(demo_text)]


def build_findings(parsed, quality, ats, skills, skills_by_category):
    strengths, weaknesses = [], []
    for ch in quality["checks"] + [c for c in ats["checks"] if c["id"] != "ats_headings"]:
        if ch["status"] == "pass" and ch["strength"]:
            strengths.append(ch["strength"])
        elif ch["status"] in ("warn", "fail"):
            weaknesses.append({
                "text": ch["detail"], "recommendation": ch["recommendation"],
                "priority": ch["priority"], "area": ch["category"],
            })
    if len(skills) >= 6:
        strengths.append("%d recognised technical skills across %d categories." % (
            len(skills), len(skills_by_category)))
    weaknesses.sort(key=lambda w: _PRIORITY_RANK[w["priority"]])

    missing_evidence = []
    listed_only = _listed_only_skills(parsed, skills)
    if listed_only:
        missing_evidence.append({
            "text": "Skills appear in your resume but not in any project or experience line: %s." %
                    ", ".join(listed_only[:8]),
            "recommendation": "Where you really used them, mention the skill inside a project or "
                              "experience bullet to show how you applied it.",
        })
    return {
        "strengths": strengths[:8],
        "weaknesses": weaknesses,
        "missing_evidence": missing_evidence,
        "listed_only_skills": listed_only,
    }