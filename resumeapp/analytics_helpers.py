"""
Shared statistics for the Dashboard and Analytics pages.

Both views call build_resume_stats(), so every number is calculated in one
place and the two pages can never disagree.

Counting rules
--------------
* Only the logged-in user's resumes are used.
* Resume.ats_score is a non-null IntegerField (default 0) that the upload view
  fills in immediately, so every uploaded resume is counted as analyzed.
* Match success = ats_score >= SUCCESS_THRESHOLD (70, the same threshold the
  original dashboard view used).
"""
import os
from collections import Counter
from datetime import datetime, timedelta

SUCCESS_THRESHOLD = 70
HIGH_THRESHOLD = 80
MODERATE_THRESHOLD = 60
MAX_PERFORMANCE_BARS = 15
TOP_SKILLS = 10


def _round(value):
    """Round half up (avoids Python's banker's rounding surprises)."""
    return int(value + 0.5)


def _local(dt):
    """Convert aware datetimes to local time; leave naive ones untouched."""
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt
    from django.utils import timezone
    return timezone.localtime(dt)


def _score(resume):
    return resume.ats_score or 0


def _display_name(resume, number):
    name = getattr(resume.resume_file, "name", "") or ""
    return os.path.basename(name) or f"Resume {number}"


def _short(name, limit=18):
    return name if len(name) <= limit else name[: limit - 1] + "…"


def score_category(score):
    """(css colour, label). Labels describe the score only - no hiring promise."""
    if score >= HIGH_THRESHOLD:
        return "green", "High match"
    if score >= MODERATE_THRESHOLD:
        return "orange", "Moderate match"
    return "red", "Low match"


def _upload_buckets(dates):
    """Daily buckets for short histories, monthly buckets for long ones."""
    if not dates:
        return {"labels": [], "counts": [], "granularity": "day"}

    days = sorted(d.date() for d in dates)
    first, last = days[0], days[-1]

    if (last - first).days <= 31:
        counter = Counter(days)
        labels, counts = [], []
        day = first
        while day <= last:
            labels.append(day.strftime("%d %b"))
            counts.append(counter.get(day, 0))
            day += timedelta(days=1)
        return {"labels": labels, "counts": counts, "granularity": "day"}

    counter = Counter((d.year, d.month) for d in days)
    labels, counts = [], []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        labels.append(datetime(year, month, 1).strftime("%b %Y"))
        counts.append(counter.get((year, month), 0))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return {"labels": labels, "counts": counts, "granularity": "month"}


def _skill_counts(resumes):
    """Top skills, counted once per resume. Skills are stored comma-separated."""
    counts, display = Counter(), {}
    for resume in resumes:
        seen = set()
        for part in (resume.skills or "").split(","):
            name = part.strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            display.setdefault(key, name)
            counts[key] += 1
    top = counts.most_common(TOP_SKILLS)
    return {
        "labels": [display[k] for k, _ in top],
        "counts": [c for _, c in top],
    }


def _insights(resumes, names, scores, avg, success_rate, skills):
    if not resumes:
        return []

    out = []
    best = max(range(len(scores)), key=lambda i: scores[i])
    out.append(f"Your highest-scoring resume is “{names[best]}” with an ATS score of {scores[best]}%.")

    if len(scores) >= 2:
        diff = scores[-1] - scores[-2]
        if diff > 0:
            out.append(f"Your latest upload scored {diff} point(s) higher than the one before it.")
        elif diff < 0:
            out.append(f"Your latest upload scored {abs(diff)} point(s) lower than the one before it.")
        else:
            out.append("Your latest upload scored the same as the one before it.")

    low = sum(1 for s in scores if s < MODERATE_THRESHOLD)
    if low:
        out.append(f"{low} resume(s) fall in the low-match range (below {MODERATE_THRESHOLD}%).")

    out.append(
        f"{success_rate}% of your resumes scored {SUCCESS_THRESHOLD}% or higher "
        f"(average score {avg}%)."
    )

    if skills["labels"]:
        out.append(
            f"Your most frequently detected skill is {skills['labels'][0]} "
            f"(found in {skills['counts'][0]} of {len(resumes)} resume(s))."
        )
    return out


def compute_stats(resumes):
    """
    resumes: list of Resume-like objects ordered oldest -> newest.
    Sets display attributes on each object and returns the template context.
    """
    total = len(resumes)
    scores = [_score(r) for r in resumes]
    names = [_display_name(r, i) for i, r in enumerate(resumes, start=1)]
    dates = [_local(r.uploaded_at) for r in resumes]

    avg = _round(sum(scores) / total) if total else 0
    highest = max(scores) if scores else 0
    success = sum(1 for s in scores if s >= SUCCESS_THRESHOLD)
    success_rate = _round(success * 100 / total) if total else 0

    high = sum(1 for s in scores if s >= HIGH_THRESHOLD)
    moderate = sum(1 for s in scores if MODERATE_THRESHOLD <= s < HIGH_THRESHOLD)
    low = sum(1 for s in scores if s < MODERATE_THRESHOLD)

    distribution = [
        {"label": "High match (80–100)", "color": "green", "count": high},
        {"label": "Moderate match (60–79)", "color": "orange", "count": moderate},
        {"label": "Low match (below 60)", "color": "red", "count": low},
    ]
    for row in distribution:
        row["pct"] = _round(row["count"] * 100 / total) if total else 0

    # Trend labels: add the time only when several uploads share one date.
    per_day = Counter(d.date() for d in dates)
    trend_labels = []
    for d in dates:
        label = d.strftime("%d %b %Y")
        if per_day[d.date()] > 1:
            label += d.strftime(" %H:%M")
        trend_labels.append(label)

    start = max(0, total - MAX_PERFORMANCE_BARS)
    skills = _skill_counts(resumes)

    chart_data = {
        "trend": {"labels": trend_labels, "scores": scores, "names": names},
        "distribution": {
            "labels": [row["label"] for row in distribution],
            "counts": [row["count"] for row in distribution],
        },
        "uploads": _upload_buckets(dates),
        "performance": {
            "labels": [_short(n) for n in names[start:]],
            "full_names": names[start:],
            "scores": scores[start:],
        },
        "skills": skills,
    }

    # Per-card display attributes (newest first for the dashboard grid)
    for resume, name, score in zip(resumes, names, scores):
        resume.display_name = name
        resume.score_color, resume.score_label = score_category(score)
        resume.score_pct = max(0, min(100, score))

    return {
        "resumes": list(reversed(resumes)),
        "total_resumes": total,
        "avg_ats": avg,
        "highest_ats": highest,
        "success_rate": success_rate,
        "success_threshold": SUCCESS_THRESHOLD,
        "distribution": distribution,
        "insights": _insights(resumes, names, scores, avg, success_rate, skills),
        "has_skills": bool(skills["labels"]),
        "chart_data": chart_data,
    }


def build_resume_stats(user):
    """Single entry point used by the dashboard and analytics views."""
    from .models import Resume

    resumes = list(
        Resume.objects.filter(user=user)
        .defer("extracted_text", "summary")   # large text, not needed here
        .order_by("uploaded_at", "id")
    )
    return compute_stats(resumes)