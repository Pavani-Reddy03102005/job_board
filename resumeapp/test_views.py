"""
Page and flow tests: every page renders, login protection works, upload
validation rejects bad files, analysis results are saved and reused, and one
user can never see another user's resumes.

Run with:  python manage.py test resumeapp
(run  python manage.py makemigrations resumeapp  and  python manage.py migrate  first)
"""
import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from docx import Document

from .models import AnalysisResult, JobDescription, Resume
from .test_engine import GOOD_RESUME, JD


def make_docx_bytes(text):
    doc = Document()
    for line in text.splitlines():
        if line.strip():
            doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


class PublicPageTests(TestCase):

    def test_public_pages_render(self):
        for name in ("home", "login", "register"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_protected_pages_redirect_to_the_login_page(self):
        pages = [
            ("dashboard", []), ("upload_resume", []), ("analytics", []),
            ("analyze", [1]), ("results", [1]), ("delete_resume", [1]),
        ]
        for name, args in pages:
            with self.subTest(page=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(
                    response["Location"].startswith(reverse("login")),
                    "Add  LOGIN_URL = 'login'  to settings.py (redirected to %s)" % response["Location"],
                )

    def test_logout_redirects_home(self):
        self.assertRedirects(self.client.get(reverse("logout")), reverse("home"))


class ResumeFlowTests(TestCase):

    def setUp(self):
        self._media = tempfile.mkdtemp()
        self._override = override_settings(MEDIA_ROOT=self._media)
        self._override.enable()
        self.addCleanup(self._cleanup)
        self.user = User.objects.create_user("priya", "priya@example.com", "pass12345")
        self.client.login(username="priya", password="pass12345")

    def _cleanup(self):
        self._override.disable()
        shutil.rmtree(self._media, ignore_errors=True)

    def upload(self, data=None, name="resume.docx"):
        data = make_docx_bytes(GOOD_RESUME) if data is None else data
        return self.client.post(
            reverse("upload_resume"),
            {"resume_file": SimpleUploadedFile(name, data)},
        )

    def uploaded_resume(self):
        response = self.upload()
        resume = Resume.objects.get(user=self.user)
        self.assertRedirects(response, reverse("analyze", args=[resume.id]))
        return resume

    # ---- pages for a user with no data
    def test_empty_dashboard_analytics_and_upload_pages_render(self):
        for name in ("dashboard", "analytics", "upload_resume"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    # ---- upload validation
    def test_wrong_extension_is_rejected(self):
        response = self.upload(b"hello", name="resume.txt")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Only PDF")
        self.assertEqual(Resume.objects.count(), 0)

    def test_fake_docx_is_rejected(self):
        response = self.upload(b"this is not a zip file", name="resume.docx")
        self.assertContains(response, "not a valid Word")
        self.assertEqual(Resume.objects.count(), 0)

    def test_almost_empty_document_is_rejected_and_not_stored(self):
        response = self.upload(make_docx_bytes("Hello"))
        self.assertContains(response, "not enough")
        self.assertEqual(Resume.objects.count(), 0)

    def test_document_that_is_not_a_resume_is_rejected(self):
        text = "The quick brown fox jumps over the lazy dog near the quiet river bank.\n" * 8
        response = self.upload(make_docx_bytes(text))
        self.assertContains(response, "does not look like a resume")
        self.assertEqual(Resume.objects.count(), 0)

    # ---- analysis flow
    def test_upload_then_general_analysis_then_results(self):
        resume = self.uploaded_resume()
        self.assertGreater(resume.ats_score, 0)
        self.assertIn("Python", resume.skills)

        # not analysed yet: results asks for the analysis mode first
        self.assertRedirects(
            self.client.get(reverse("results", args=[resume.id])),
            reverse("analyze", args=[resume.id]),
        )
        self.assertEqual(self.client.get(reverse("analyze", args=[resume.id])).status_code, 200)

        data = {"mode": "general", "job_title": "", "company": "", "job_description": ""}
        response = self.client.post(reverse("analyze", args=[resume.id]), data)
        self.assertEqual(response.status_code, 302)
        analysis = AnalysisResult.objects.get(resume=resume)
        self.assertEqual(analysis.mode, "general")
        self.assertIsNone(analysis.job_match_percentage)
        resume.refresh_from_db()
        self.assertEqual(resume.ats_score, analysis.ats_score)

        page = self.client.get(response["Location"])
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Resume quality")
        self.assertContains(page, "ATS compatibility")

        # identical inputs reuse the saved result instead of recalculating
        self.client.post(reverse("analyze", args=[resume.id]), data)
        self.assertEqual(AnalysisResult.objects.filter(resume=resume).count(), 1)

    def test_job_analysis_needs_a_real_job_description(self):
        resume = self.uploaded_resume()
        response = self.client.post(reverse("analyze", args=[resume.id]), {
            "mode": "job", "job_title": "", "company": "", "job_description": "too short",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter the job title")
        self.assertEqual(AnalysisResult.objects.count(), 0)

    def test_job_analysis_saves_job_description_and_shows_match(self):
        resume = self.uploaded_resume()
        response = self.client.post(reverse("analyze", args=[resume.id]), {
            "mode": "job", "job_title": "Python Developer", "company": "Acme",
            "job_description": JD,
        })
        self.assertEqual(response.status_code, 302)
        analysis = AnalysisResult.objects.get(resume=resume)
        self.assertEqual(analysis.mode, "job")
        self.assertTrue(0 <= analysis.job_match_percentage <= 100)
        self.assertEqual(JobDescription.objects.get(user=self.user).title, "Python Developer")
        page = self.client.get(response["Location"])
        self.assertContains(page, "Job match")
        self.assertContains(page, "Python Developer")

    def test_dashboard_and_analytics_show_the_uploaded_resume(self):
        self.uploaded_resume()
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "resume.docx")
        self.assertContains(dashboard, "Total Resumes")
        analytics = self.client.get(reverse("analytics"))
        self.assertEqual(analytics.status_code, 200)
        self.assertContains(analytics, "Insights")

    # ---- delete
    def test_delete_confirmation_and_delete(self):
        resume = self.uploaded_resume()
        url = reverse("delete_resume", args=[resume.id])
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Delete Resume")
        self.assertRedirects(self.client.post(url), reverse("dashboard"))
        self.assertEqual(Resume.objects.count(), 0)

    # ---- one user can never reach another user's data
    def test_other_users_get_404_for_your_resume(self):
        resume = self.uploaded_resume()
        self.client.post(reverse("analyze", args=[resume.id]),
                         {"mode": "general", "job_title": "", "company": "", "job_description": ""})
        self.client.logout()
        User.objects.create_user("other", "other@example.com", "pass12345")
        self.client.login(username="other", password="pass12345")

        for name in ("results", "analyze", "delete_resume"):
            with self.subTest(page=name):
                self.assertEqual(self.client.get(reverse(name, args=[resume.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("delete_resume", args=[resume.id])).status_code, 404)
        self.assertEqual(Resume.objects.filter(id=resume.id).count(), 1)
        self.assertNotContains(self.client.get(reverse("dashboard")), "resume.docx")