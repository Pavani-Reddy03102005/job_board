"""
Job-description matching.

Three separate measures are reported, never blended silently:
  * skill coverage  - skills named in the job description vs. skills in the resume
  * text similarity - TF-IDF cosine similarity of the two documents (shared vocabulary only)
  * overall estimate - a fixed-weight combination of the two (documented in `method`)

A skill that is not mentioned in the resume is called "unverified", never "missing":
the resume may simply not mention something the candidate can do.
"""
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .resume_quality import SECTION_LABELS
from .skills_extractor import evidence_patterns, extract_skills, find_skills

PREFERRED_CUE = re.compile(
    r"preferred|nice[- ]to[- ]have|good to have|bonus|a plus|is a plus|desirable|optional|advantageous",
    re.IGNORECASE)
REQUIRED_HEAD = re.compile(
    r"requirements?|qualifications?|responsibilit(?:y|ies)|must[- ]have|required|"
    r"what you.?ll (?:need|bring)|skills", re.IGNORECASE)

RELATED_GROUPS = [
    {"MySQL", "PostgreSQL", "SQLite", "SQL Server", "Oracle", "SQL"},
    {"MongoDB", "Redis", "Firebase"},
    {"React", "Angular", "Vue.js"},
    {"Django", "Flask", "FastAPI", "Django REST Framework"},
    {"Node.js", "Express.js"},
    {"AWS", "Azure", "GCP"},
    {"TensorFlow", "PyTorch", "Keras"},
    {"Docker", "Kubernetes"},
    {"Git", "GitHub", "GitLab"},
    {"Power BI", "Tableau"},
]

SIMILARITY_FULL_CREDIT = 0.30   # cosine similarity treated as "full" vocabulary overlap

METHOD_TEXT = (
    "Overall estimate = 65% required-skill coverage + 10% preferred-skill coverage + 25% text similarity "
    "(similarity of 0.30 or more counts as full credit). When no preferred skills are detected the "
    "preferred weight moves to required skills. If no skills are recognised in the job description, "
    "only text similarity is used and confidence is low."
)


def _jd_lines(jd_text):
    lines = []
    for raw in (jd_text or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        if len(raw) > 250:
            lines.extend(s.strip() for s in re.split(r"(?<=[.;!?])\s+", raw) if s.strip())
        else:
            lines.append(raw)
    return lines


def split_requirements(jd_text):
    """Skills named in the job description, split into (required, preferred)."""
    required, preferred, mode = [], [], "required"
    for line in _jd_lines(jd_text):
        short = len(line.split()) <= 6
        if short and PREFERRED_CUE.search(line):
            mode = "preferred"
            continue
        if short and REQUIRED_HEAD.search(line):
            mode = "required"
            continue
        target = "preferred" if PREFERRED_CUE.search(line) else mode
        bucket = required if target == "required" else preferred
        for _, skill in find_skills(line):
            if skill not in bucket:
                bucket.append(skill)
    preferred = [s for s in preferred if s not in required]
    return required, preferred


def text_similarity(a, b):
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        m = vec.fit_transform([a, b])
        return float(cosine_similarity(m[0:1], m[1:2])[0][0])
    except ValueError:      # empty vocabulary
        return 0.0


def _related(skill, have):
    rel = set()
    for group in RELATED_GROUPS:
        if skill in group:
            rel |= group
    return sorted((rel - {skill}) & have)


def _evidence(skill, parsed):
    patterns = evidence_patterns(skill)
    hits = []
    for line, sec in zip(parsed["lines"], parsed["line_sections"]):
        if sec != "heading" and any(p.search(line) for p in patterns):
            hits.append((sec, line))
    if not hits:
        return {"skill": skill, "where": [], "demonstrated": None, "snippet": ""}
    demo = [h for h in hits if h[0] in ("experience", "projects")]
    snippet_line = (demo or hits)[0][1]
    snippet = re.sub(r"^[\W_]+", "", snippet_line)
    snippet = snippet[:160] + ("…" if len(snippet) > 160 else "")
    where = []
    for sec, _ in hits:
        label = SECTION_LABELS.get(sec, "Header")
        if label not in where:
            where.append(label)
    return {"skill": skill, "where": where, "demonstrated": bool(demo), "snippet": snippet}


def _classify(skills, have, parsed):
    matched, unclear, unverified = [], [], []
    for skill in skills:
        if skill in have:
            matched.append(_evidence(skill, parsed))
        else:
            rel = _related(skill, have)
            if rel:
                unclear.append({"skill": skill, "related": rel})
            else:
                unverified.append(skill)
    return {"matched": matched, "unclear": unclear, "unverified": unverified}


def _coverage(group, total):
    return round(100 * len(group["matched"]) / total) if total else None


def _label(pct):
    return "Strong" if pct >= 80 else "Moderate" if pct >= 60 else "Partial" if pct >= 40 else "Low"


def analyze_job_match(parsed, resume_text, jd_text, job_title="", company=""):
    have = set(extract_skills(resume_text))
    required_skills, preferred_skills = split_requirements(jd_text)
    req = _classify(required_skills, have, parsed)
    pref = _classify(preferred_skills, have, parsed)

    req_cov = _coverage(req, len(required_skills))
    pref_cov = _coverage(pref, len(preferred_skills))
    sim = text_similarity(resume_text, jd_text)
    sim_pct = round(sim * 100)
    sim_credit = min(sim / SIMILARITY_FULL_CREDIT, 1.0) * 100

    if required_skills:
        if preferred_skills:
            overall = 0.65 * req_cov + 0.10 * pref_cov + 0.25 * sim_credit
        else:
            overall = 0.75 * req_cov + 0.25 * sim_credit
    else:
        overall = sim_credit
    overall = int(round(max(0, min(100, overall))))

    jd_words = len(re.findall(r"\w+", jd_text or ""))
    n_req = len(required_skills)
    if n_req >= 5:
        confidence, note = "high", "The job description names several recognised skills."
    elif n_req >= 3:
        confidence, note = "medium", "Only a few recognised skills were found in the job description."
    else:
        confidence, note = "low", (
            "Few or no recognised skills were found in the job description, so this estimate relies "
            "mostly on word overlap. Paste the full job description for a better estimate.")

    recs = []
    for skill in req["unverified"]:
        recs.append("The job description asks for %s, but your resume does not mention it. If you have "
                    "really used it, add it to a project or experience bullet; if not, it is a learning gap." % skill)
    for item in req["unclear"]:
        recs.append("%s is requested; your resume shows related skills (%s). If you have used %s itself, "
                    "say so explicitly." % (item["skill"], ", ".join(item["related"]), item["skill"]))
    for ev in req["matched"]:
        if ev["demonstrated"] is False:
            recs.append("%s appears only in your skills list. Show it inside a project or experience bullet." % ev["skill"])

    def names(group):
        return [e["skill"] for e in group["matched"]]

    return {
        "job_title": job_title, "company": company, "jd_words": jd_words,
        "required_skills": required_skills, "preferred_skills": preferred_skills,
        "required": req, "preferred": pref,
        "coverage": {"required": req_cov, "preferred": pref_cov, "similarity": sim_pct},
        "overall": overall, "label": _label(overall),
        "confidence": confidence, "confidence_note": note,
        "recommendations": recs[:12], "method": METHOD_TEXT,
        "matched_names": names(req) + names(pref),
        "unverified_names": req["unverified"] + [i["skill"] for i in req["unclear"]]
                            + pref["unverified"] + [i["skill"] for i in pref["unclear"]],
    }