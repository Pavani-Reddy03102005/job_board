"""
Orchestrates the deterministic analysis and returns one JSON-serialisable report.
"""
import hashlib
import re

from .job_match import analyze_job_match
from .resume_quality import (
    SECTION_LABELS,
    SECTION_ORDER,
    build_findings,
    evaluate_ats,
    evaluate_quality,
    parse_resume,
    suggest_roles,
)
from .skills_extractor import extract_skills, extract_skills_by_category

ENGINE_VERSION = "1.0"
MODE_GENERAL = "general"
MODE_JOB = "job"

LIMITATIONS = [
    "Resume quality (0-100) is a checklist score defined in this application: it counts sections, "
    "contact details, bullet wording and length. It is not a scientifically validated measure.",
    "ATS compatibility (0-100) estimates how easily software can read your file (text extraction, "
    "headings, layout risks). It is not the score any employer's ATS would assign.",
    "Skill coverage compares skills named in the job description with skills found in your resume. "
    "A skill that is not mentioned is 'unverified', not proof that you lack it.",
    "Text similarity is TF-IDF cosine similarity. It measures shared vocabulary only and ignores meaning.",
    "The overall job-match percentage combines the measures above with fixed weights. It is an estimate, "
    "not a prediction of any hiring decision.",
    "Spelling and grammar are not checked automatically.",
]


def _norm(value):
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def compute_input_hash(raw_text, mode, job_title="", company="", jd_text=""):
    """Same inputs + same engine version -> same hash, so results can be reused."""
    parts = [ENGINE_VERSION, mode, _norm(job_title), _norm(company), _norm(jd_text),
             hashlib.sha256((raw_text or "").encode("utf-8")).hexdigest()]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def run_analysis(raw_text, meta, mode=MODE_GENERAL, job_title="", company="", jd_text=""):
    meta = meta or {}
    parsed = parse_resume(raw_text)
    skills = extract_skills(raw_text)
    by_category = extract_skills_by_category(raw_text)

    quality = evaluate_quality(parsed)
    ats = evaluate_ats(parsed, meta)
    findings = build_findings(parsed, quality, ats, skills, by_category)

    contact_labels = [("email", "Email address"), ("phone", "Phone number"),
                      ("linkedin", "LinkedIn link"), ("github", "GitHub link")]
    overview = {
        "sections_found": [SECTION_LABELS[k] for k in SECTION_ORDER if k in parsed["found_sections"]],
        "sections_missing": [SECTION_LABELS[k] for k in SECTION_ORDER[1:6]
                             if k not in parsed["found_sections"]],
        "section_text": {SECTION_LABELS[k]: "\n".join(parsed["sections"].get(k, []))[:1200]
                         for k in SECTION_ORDER if parsed["sections"].get(k)},
        "contact": [{"label": label, "found": parsed["contact"][key]} for key, label in contact_labels],
        "skills": skills,
        "skills_by_category": by_category,
        "stats": {k: v for k, v in parsed["stats"].items() if k != "non_verb_examples"},
        "file_type": meta.get("file_type"),
        "pages": meta.get("pages"),
        "text_only_fallback": bool(meta.get("fallback")),
        "flattened_text": parsed["flattened"],
    }

    job = None
    if mode == MODE_JOB:
        job = analyze_job_match(parsed, raw_text, jd_text, job_title, company)

    return {
        "engine_version": ENGINE_VERSION,
        "mode": mode,
        "overview": overview,
        "quality": quality,
        "ats": ats,
        "job_match": job,
        "role_suggestions": suggest_roles(skills) if mode == MODE_GENERAL else [],
        "strengths": findings["strengths"],
        "weaknesses": findings["weaknesses"],
        "missing_evidence": findings["missing_evidence"],
        "limitations": LIMITATIONS,
    }