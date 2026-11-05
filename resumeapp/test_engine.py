"""
Tests for the analysis engine (no database or web server needed).

Run with:  python manage.py test resumeapp
"""
import json
import os
import tempfile
import unittest

from docx import Document
from PIL import Image

from resumeapp.services.analysis import compute_input_hash, run_analysis
from resumeapp.services.ats import calculate_ats_score
from resumeapp.services.job_match import split_requirements
from resumeapp.services.parser import ExtractionError, extract_with_meta
from resumeapp.services.resume_quality import looks_like_resume, parse_resume
from resumeapp.services.skills_extractor import extract_skills
from resumeapp.utils import clean_text

GOOD_RESUME = """Priya Sharma
priya.sharma@example.com | +91 98765 43210 | linkedin.com/in/priyasharma | github.com/priya-s
SUMMARY
Final-year B.Tech CSE student focused on backend development with Python and Django.
EDUCATION
B.Tech Computer Science and Engineering, JNTU Anantapur, 2022 - 2026
SKILLS
Python, Django, SQL, MySQL, HTML, CSS, JavaScript, Git, GitHub, Docker
PROJECTS
Resume AI - AI-powered resume matcher
- Built a Django web application that parses PDF and DOCX resumes and scores them
- Implemented TF-IDF similarity with scikit-learn to compare resumes with job descriptions
- Designed a REST API used by 3 front-end pages and reduced page load time by 40%
- Deployed the application using Docker
Library Management System
- Developed a MySQL-backed system handling 500 book records
- Created role-based login for students and librarians
EXPERIENCE
Python Intern, Acme Software, Jun 2025 - Aug 2025
- Automated report generation with Python, saving about 5 hours per week
- Wrote unit tests with pytest and fixed 12 reported bugs
CERTIFICATIONS
Python for Everybody - Coursera
""" + ("Collaborated with the team on weekly releases and documentation of every module. " * 12)

WEAK_RESUME = ("Rahul Kumar\nSkills\nJavaScript\nExperience\nResponsible for helping with tasks.\n"
               "Worked on various projects and was involved in testing.\n"
               "Responsible for the the team work.\n")

JD = """Python Developer - Backend
Requirements
- 2+ years of experience with Python and Django
- Strong knowledge of PostgreSQL and REST APIs
- Experience with Docker and Kubernetes
- Familiarity with AWS
Nice to have
- React or Vue.js experience
- Knowledge of Redis
"""


def make_pdf(items, width=612, height=792):
    """Minimal one-page text PDF. items = [(x, y, text)] (ASCII text only)."""
    content = "BT /F1 10 Tf\n"
    for x, y, t in items:
        esc = t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content += "1 0 0 1 %s %s Tm (%s) Tj\n" % (x, y, esc)
    content += "ET"
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R "
         "/Resources << /Font << /F1 5 0 R >> >> >>" % (width, height)).encode(),
        ("<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)).encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += ("%d 0 obj\n" % i).encode() + o + b"\nendobj\n"
    xref = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)).encode()
    return out


class TempFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def path(self, name):
        return os.path.join(self.dir.name, name)


class SkillTests(unittest.TestCase):
    def test_java_does_not_match_javascript(self):
        self.assertEqual(extract_skills("Worked with JavaScript and React"), ["JavaScript", "React"])

    def test_git_does_not_match_github_or_digital(self):
        self.assertEqual(extract_skills("digital marketing, GitHub projects"), ["GitHub"])

    def test_database_tool_implies_sql(self):
        self.assertIn("SQL", extract_skills("Used MySQL daily"))

    def test_symbols_and_react_native(self):
        found = extract_skills("C++, C# and React Native apps")
        self.assertIn("C++", found); self.assertIn("C#", found)
        self.assertIn("React Native", found); self.assertNotIn("React", found)

    def test_old_skill_names_preserved(self):
        text = "Python Django React SQL Java Machine Learning HTML CSS JavaScript Bootstrap Git GitHub"
        self.assertEqual(set(extract_skills(text)), {
            "Python", "Django", "React", "SQL", "Java", "Machine Learning", "HTML", "CSS",
            "JavaScript", "Bootstrap", "Git", "GitHub"})


class CleanTextTests(unittest.TestCase):
    def test_keeps_line_breaks_and_collapses_spaces(self):
        self.assertEqual(clean_text("A  b\t c\r\n\n\n\nD "), "A b c\n\nD")


class ParserTests(TempFiles):
    def test_docx_lines_bullets_tables_header(self):
        doc = Document()
        doc.sections[0].header.paragraphs[0].text = "Jane Doe jane@example.com"
        doc.add_paragraph("Skills")
        doc.add_paragraph("Python developed APIs", style="List Bullet")
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].text = "Left"; table.rows[0].cells[1].text = "Right"
        doc.add_paragraph("Education")
        p = self.path("r.docx"); doc.save(p)
        text, meta = extract_with_meta(p)
        self.assertIn("Jane Doe jane@example.com", text)
        self.assertIn("Skills\n• Python developed APIs", text)   # paragraphs no longer glued together
        self.assertIn("Left | Right", text)
        self.assertEqual(meta["tables"], 1)
        self.assertEqual(meta["problem"], "too_short")

    def test_text_pdf(self):
        items = [(72, 720 - 14 * i, line) for i, line in enumerate(GOOD_RESUME.splitlines()[:35]) if line.isascii()]
        p = self.path("r.pdf")
        with open(p, "wb") as f:
            f.write(make_pdf(items))
        text, meta = extract_with_meta(p)
        self.assertIn("EDUCATION", text); self.assertIsNone(meta["problem"])
        self.assertFalse(meta["multi_column"])

    def test_scanned_pdf_is_reported_not_silently_scored(self):
        p = self.path("scan.pdf")
        Image.new("RGB", (600, 800), "white").save(p, "PDF")
        text, meta = extract_with_meta(p)
        self.assertEqual(meta["problem"], "scanned")

    def test_corrupt_files_raise_friendly_error(self):
        for name, data in (("bad.pdf", b"not a pdf"), ("bad.docx", b"not a docx")):
            p = self.path(name)
            with open(p, "wb") as f:
                f.write(data)
            with self.assertRaises(ExtractionError):
                extract_with_meta(p)

    def test_two_column_pdf_flagged_but_right_aligned_dates_are_not(self):
        two_col = []
        for i in range(24):
            y = 740 - 14 * i
            two_col.append((50, y, "Left column text number %d here" % i))
            two_col.append((330, y, "Right column text number %d here" % i))
        single = []
        for i in range(24):
            y = 740 - 14 * i
            single.append((50, y, "Built and deployed service number %d for the team" % i))
            if i % 6 == 0:
                single.append((420 + (i % 4) * 9, y, "Jan 20%02d - Dec 20%02d" % (i, i + 1)))
        results = {}
        for name, items in (("two", two_col), ("single", single)):
            p = self.path(name + ".pdf")
            with open(p, "wb") as f:
                f.write(make_pdf(items))
            results[name] = extract_with_meta(p)[1]["multi_column"]
        self.assertTrue(results["two"]); self.assertFalse(results["single"])


class QualityTests(unittest.TestCase):
    def test_good_resume_scores_high_and_finds_sections(self):
        r = run_analysis(GOOD_RESUME, {"tables": 0, "text_boxes": 0, "multi_column": False})
        self.assertGreaterEqual(r["quality"]["score"], 80)
        self.assertGreaterEqual(r["ats"]["score"], 85)
        for name in ("Education", "Skills", "Projects", "Experience", "Certifications", "Summary"):
            self.assertIn(name, r["overview"]["sections_found"])
        self.assertTrue(all(c["found"] for c in r["overview"]["contact"]))
        self.assertTrue(r["strengths"])

    def test_weak_resume_scores_low_with_actionable_weaknesses(self):
        r = run_analysis(WEAK_RESUME, {})
        self.assertLess(r["quality"]["score"], 50)
        texts = " ".join(w["text"] + w["recommendation"] for w in r["weaknesses"])
        self.assertIn("vague phrase", texts)
        self.assertEqual(r["weaknesses"][0]["priority"], "high")

    def test_scores_equal_sum_of_checks_and_max_100(self):
        r = run_analysis(GOOD_RESUME, {})
        for key in ("quality", "ats"):
            self.assertEqual(sum(c["max_points"] for c in r[key]["checks"]), 100)
            self.assertEqual(r[key]["score"], sum(c["points"] for c in r[key]["checks"]))

    def test_layout_risks_lower_ats_score(self):
        clean = calculate_ats_score(GOOD_RESUME, {"tables": 0, "text_boxes": 0, "multi_column": False})
        risky = calculate_ats_score(GOOD_RESUME, {"tables": 2, "text_boxes": 1, "multi_column": True})
        self.assertLess(risky, clean)

    def test_flattened_text_is_detected(self):
        parsed = parse_resume(" ".join(GOOD_RESUME.splitlines()))
        self.assertTrue(parsed["flattened"])

    def test_looks_like_resume(self):
        self.assertTrue(looks_like_resume(GOOD_RESUME))
        self.assertFalse(looks_like_resume("The quick brown fox jumps over the lazy dog. " * 20))

    def test_skills_listed_but_not_demonstrated_are_reported(self):
        r = run_analysis(GOOD_RESUME, {})
        self.assertIn("Git", r["missing_evidence"][0]["text"])

    def test_role_suggestions_only_in_general_mode(self):
        self.assertTrue(run_analysis(GOOD_RESUME, {})["role_suggestions"])
        self.assertEqual(run_analysis(GOOD_RESUME, {}, "job", "Dev", "", JD)["role_suggestions"], [])


class JobMatchTests(unittest.TestCase):
    def test_required_vs_preferred_split(self):
        required, preferred = split_requirements(JD)
        self.assertEqual(required, ["Python", "Django", "PostgreSQL", "REST API", "Docker", "Kubernetes", "AWS"])
        self.assertEqual(preferred, ["React", "Vue.js", "Redis"])

    def test_matched_unclear_unverified(self):
        jm = run_analysis(GOOD_RESUME, {}, "job", "Python Developer", "Acme", JD)["job_match"]
        matched = {e["skill"] for e in jm["required"]["matched"]}
        self.assertTrue({"Python", "Django", "Docker", "REST API"} <= matched)
        unclear = {i["skill"]: i["related"] for i in jm["required"]["unclear"]}
        self.assertIn("MySQL", unclear["PostgreSQL"])          # related skill, not proof
        self.assertIn("Docker", unclear["Kubernetes"])          # related skill, not proof
        self.assertIn("AWS", jm["required"]["unverified"])
        self.assertNotIn("AWS", matched)

    def test_evidence_shows_where_skill_was_demonstrated(self):
        jm = run_analysis(GOOD_RESUME, {}, "job", "Python Developer", "", JD)["job_match"]
        django = next(e for e in jm["required"]["matched"] if e["skill"] == "Django")
        self.assertTrue(django["demonstrated"]); self.assertIn("Projects", django["where"])
        self.assertIn("Django", django["snippet"])

    def test_overall_in_range_and_confidence_reported(self):
        jm = run_analysis(GOOD_RESUME, {}, "job", "Python Developer", "", JD)["job_match"]
        self.assertTrue(0 <= jm["overall"] <= 100)
        self.assertEqual(jm["confidence"], "high")
        self.assertIn("%", jm["method"])

    def test_unrelated_resume_scores_lower(self):
        good = run_analysis(GOOD_RESUME, {}, "job", "Dev", "", JD)["job_match"]["overall"]
        weak = run_analysis(WEAK_RESUME, {}, "job", "Dev", "", JD)["job_match"]["overall"]
        self.assertLess(weak, good)

    def test_job_description_without_known_skills_is_low_confidence(self):
        jm = run_analysis(GOOD_RESUME, {}, "job", "Chef", "", "We need a friendly chef to cook meals daily.")["job_match"]
        self.assertEqual(jm["confidence"], "low"); self.assertIsNone(jm["coverage"]["required"])

    def test_report_is_json_serialisable(self):
        json.dumps(run_analysis(GOOD_RESUME, {}, "job", "Python Developer", "Acme", JD))
        json.dumps(run_analysis(GOOD_RESUME, {}))


class HashTests(unittest.TestCase):
    def test_hash_is_stable_and_sensitive(self):
        a = compute_input_hash("text", "job", "Dev", "Acme", "  Python  ")
        self.assertEqual(a, compute_input_hash("text", "job", "dev", "acme", "python"))
        self.assertNotEqual(a, compute_input_hash("text", "job", "Dev", "Acme", "Java"))
        self.assertNotEqual(a, compute_input_hash("text2", "job", "Dev", "Acme", "Python"))
        self.assertNotEqual(a, compute_input_hash("text", "general"))


if __name__ == "__main__":
    unittest.main()