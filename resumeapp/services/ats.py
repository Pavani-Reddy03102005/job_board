from .resume_quality import evaluate_ats, parse_resume


def calculate_ats_score(text, meta=None):
    """
    ATS-compatibility indicator (0-100) for the given resume text.

    Kept under its original name so the upload view still works. The old version
    awarded 20 points for each of five keywords; this one runs the transparent
    machine-readability checks defined in resume_quality.evaluate_ats().
    """
    return evaluate_ats(parse_resume(text), meta or {})["score"]