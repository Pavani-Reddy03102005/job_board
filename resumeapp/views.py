import os

from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)
from django.urls import reverse
from .forms import ResumeForm, AnalysisForm
from .models import (
    Resume,
    CompanyRequirement,
    JobDescription,
    AnalysisResult
)
from .services.parser import (
    ExtractionError,
    MIN_TEXT_CHARS,
    PROBLEM_MESSAGES,
    extract_with_meta
)
from .services.skills_extractor import (
    extract_skills
)
from .services.matcher import (
    calculate_match
)
from .services.ats import (
    calculate_ats_score
)
from .services.summarizer import (
    generate_summary
)
from .services.resume_quality import looks_like_resume
from .services.analysis import (
    MODE_JOB,
    compute_input_hash,
    run_analysis
)
from .utils import clean_text
from .analytics_helpers import build_resume_stats


# HOME PAGE
def home(request):
    return render(
        request,
        'resumeapp/home.html'
    )


# REGISTER PAGE
def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # PASSWORD CHECK
        if password != confirm_password:

            messages.error(
                request,
                'Passwords do not match'
            )
            return redirect('register')

        # USER EXISTS CHECK
        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                'Username already exists'
            )
            return redirect('register')

        # CREATE USER
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.save()
        messages.success(
            request,
            'Registration Successful'
        )
        return redirect('login')

    return render(
        request,
        'resumeapp/register.html'
    )


# LOGIN PAGE
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        # AUTHENTICATE USER
        user = authenticate(
            request,
            username=username,
            password=password
        )

        # IF USER EXISTS
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(
                request,
                'Invalid Username or Password'
            )
            return redirect('login')

    return render(
        request,
        'resumeapp/login.html'
    )


def logout_view(request):
    logout(request)
    return redirect('home')


# DASHBOARD VIEW
@login_required
def dashboard(request):
    context = build_resume_stats(request.user)

    return render(
        request,
        "resumeapp/dashboard.html",
        context,
    )


def _discard_upload(resume):
    """Remove a rejected upload (file and database row)."""
    if resume.resume_file:
        resume.resume_file.delete(save=False)
    resume.delete()


def _process_upload(resume):
    """
    Read the saved file, validate it and fill in the Resume fields.
    Returns an error message (str) when the file cannot be used, else None.
    """
    try:
        raw_text, meta = extract_with_meta(resume.resume_file.path)
    except ExtractionError as exc:
        return str(exc)

    # Unreadable / scanned files are reported, never silently scored as 0
    if meta["problem"]:
        return PROBLEM_MESSAGES[meta["problem"]]

    if not looks_like_resume(raw_text):
        return (
            "This document does not look like a resume. A resume normally contains "
            "contact details, section headings such as Education or Skills, and dates."
        )

    # SAVE EXTRACTED TEXT (line breaks are kept)
    extracted_text = clean_text(raw_text)
    resume.extracted_text = extracted_text

    # SKILL EXTRACTION
    skills = extract_skills(extracted_text)
    resume.skills = ",".join(skills)

    # ATS COMPATIBILITY INDICATOR
    resume.ats_score = calculate_ats_score(raw_text, meta)

    # COMPANY MATCHING (unchanged)
    companies = CompanyRequirement.objects.all()

    for company in companies:
        score = calculate_match(
            extracted_text,
            company.required_skills
        )

        if company.company_name == "Google":
            resume.google_score = score

        elif company.company_name == "Amazon":
            resume.amazon_score = score

        elif company.company_name == "TCS":
            resume.tcs_score = score

        elif company.company_name == "Infosys":
            resume.infosys_score = score

    # SUMMARY GENERATION (placeholder text until AI summaries are added)
    resume.summary = generate_summary(skills)

    # FINAL SAVE
    resume.save()

    return None


# UPLOAD RESUME VIEW
@login_required
def upload_resume(request):
    # CHECK POST REQUEST
    if request.method == 'POST':
        form = ResumeForm(
            request.POST,
            request.FILES
        )

        # VALIDATE FORM (file type, size and signature)
        if form.is_valid():

            # CREATE OBJECT
            resume = form.save(commit=False)

            # ASSIGN USER
            resume.user = request.user

            # SAVE FILE
            resume.save()

            error = _process_upload(resume)

            if error:
                _discard_upload(resume)
                form.add_error('resume_file', error)

            else:
                # NEXT STEP: choose the analysis mode
                return redirect(
                    'analyze',
                    id=resume.id
                )

    else:
        form = ResumeForm()

    # RENDER UPLOAD PAGE
    return render(
        request,
        'resumeapp/upload.html',
        {'form': form}
    )


def _load_raw_text(resume):
    """
    Re-read the original file so line breaks and layout details are available
    (also for resumes uploaded before this feature existed). Falls back to the
    stored text if the file is missing.
    """
    try:
        text, meta = extract_with_meta(resume.resume_file.path)
        if not meta.get("problem"):
            return text, meta
    except (ExtractionError, OSError, ValueError):
        pass

    stored = resume.extracted_text or ""
    return stored, {"fallback": True, "chars": len(stored.strip())}


# ANALYSIS MODE + JOB DESCRIPTION
@login_required
def analyze_resume(request, id):
    resume = get_object_or_404(
        Resume,
        id=id,
        user=request.user
    )

    if request.method == 'POST':
        form = AnalysisForm(request.POST)

        if form.is_valid():
            mode = form.cleaned_data['mode']
            job_title = form.cleaned_data['job_title'].strip()
            company = form.cleaned_data['company'].strip()
            jd_text = form.cleaned_data['job_description'].strip()

            if mode != MODE_JOB:
                job_title = company = jd_text = ""

            raw_text, meta = _load_raw_text(resume)

            if len(raw_text.strip()) < MIN_TEXT_CHARS:
                form.add_error(
                    None,
                    "No readable text could be found in this resume, so it cannot be "
                    "analysed. If it is a scanned document, upload a text-based PDF or "
                    "the DOCX version instead."
                )

            else:
                input_hash = compute_input_hash(
                    raw_text, mode, job_title, company, jd_text
                )

                analysis = resume.analyses.filter(
                    input_hash=input_hash
                ).first()

                if analysis is None:
                    report = run_analysis(
                        raw_text, meta, mode, job_title, company, jd_text
                    )
                    job = report["job_match"]

                    with transaction.atomic():

                        job_description = None

                        if job:
                            job_description = JobDescription.objects.create(
                                user=request.user,
                                title=job_title,
                                company=company,
                                description_text=jd_text,
                                required_skills=job["required_skills"],
                                preferred_skills=job["preferred_skills"],
                            )

                        analysis = AnalysisResult.objects.create(
                            resume=resume,
                            job_description=job_description,
                            mode=mode,
                            quality_score=report["quality"]["score"],
                            ats_score=report["ats"]["score"],
                            job_match_percentage=job["overall"] if job else None,
                            matched_skills=job["matched_names"] if job else report["overview"]["skills"],
                            missing_skills=job["unverified_names"] if job else [],
                            report=report,
                            input_hash=input_hash,
                            engine_version=report["engine_version"],
                        )

                        # keep the dashboard in step with the latest ATS indicator
                        resume.ats_score = analysis.ats_score
                        resume.save(update_fields=['ats_score'])

                    messages.success(request, "Analysis complete.")

                else:
                    messages.info(
                        request,
                        "Nothing has changed since your last identical analysis, "
                        "so the saved result is shown."
                    )

                return redirect(
                    "%s?a=%d" % (reverse('results', args=[resume.id]), analysis.id)
                )

    else:
        form = AnalysisForm()

    return render(
        request,
        'resumeapp/analyze.html',
        {
            'resume': resume,
            'form': form,
            'display_name': os.path.basename(resume.resume_file.name),
        }
    )


# RESULTS PAGE
@login_required
def results(request, id):
    # user=request.user: a user may only open their own results
    resume = get_object_or_404(
        Resume,
        id=id,
        user=request.user
    )

    history = list(resume.analyses.all()[:10])

    # Not analysed yet (for example an older upload): ask for the analysis mode
    if not history:
        return redirect('analyze', id=resume.id)

    selected = history[0]
    requested = request.GET.get('a', '')

    if requested.isdigit():
        match = resume.analyses.filter(id=int(requested)).first()
        if match:
            selected = match

    show_company_match = any([
        resume.google_score,
        resume.amazon_score,
        resume.tcs_score,
        resume.infosys_score,
    ])

    context = {
        'resume': resume,
        'analysis': selected,
        'report': selected.report,
        'history': history,
        'display_name': os.path.basename(resume.resume_file.name),
        'show_company_match': show_company_match,
    }

    return render(
        request,
        'resumeapp/results.html',
        context
    )


# ANALYTICS PAGE
@login_required
def analytics(request):
    context = build_resume_stats(request.user)

    return render(
        request,
        'resumeapp/analytics.html',
        context
    )


@login_required
def delete_resume(request, id):
    """
    Delete a resume uploaded by the currently logged-in user.
    """

    resume = get_object_or_404(
        Resume,
        id=id,
        user=request.user
    )

    if request.method == "POST":

        # Delete uploaded file from storage
        if resume.resume_file:
            resume.resume_file.delete(save=False)

        resume.delete()

        messages.success(
            request,
            "Resume deleted successfully."
        )

        return redirect("dashboard")

    return render(
        request,
        "resumeapp/delete.html",
        {"resume": resume}
    )