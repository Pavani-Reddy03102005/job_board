from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from resumeapp.models import CompanyRequirement 
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import (
    render,
    redirect,
    get_object_or_404
)
from .forms import ResumeForm
from .models import (
    Resume,
    CompanyRequirement
)
from .services.parser import (
    extract_pdf_text,
    extract_docx_text
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
from .utils import clean_text
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
    resumes = Resume.objects.all()
    total_resumes = resumes.count()
    avg_ats = 0
    if total_resumes > 0:
        avg_ats = sum(
            r.ats_score for r in resumes
        ) / total_resumes

    context = {
        'resumes': resumes,
        'total_resumes': total_resumes,
        'avg_ats': round(avg_ats)
    }
    return render(
        request,
        'resumeapp/dashboard.html',
        context
    )

# UPLOAD RESUME VIEW
@login_required
def upload_resume(request):
    # CHECK POST REQUEST
    if request.method == 'POST':
        form = ResumeForm(
            request.POST,
            request.FILES
        )
        # VALIDATE FORM
        if form.is_valid():
            # CREATE OBJECT
            resume = form.save(commit=False)
            # ASSIGN USER
            resume.user = request.user
            # SAVE FILE
            resume.save()
            # GET FILE PATH
            file_path = resume.resume_file.path
            # PDF EXTRACTION
            if file_path.endswith('.pdf'):
                extracted_text = extract_pdf_text(
                    file_path
                )
            # DOCX EXTRACTION
            elif file_path.endswith('.docx'):
                extracted_text = extract_docx_text(
                    file_path
                )
            else:
                extracted_text = ""
            # CLEAN EXTRACTED TEXT
            extracted_text = clean_text(
                extracted_text
            )
            # SAVE EXTRACTED TEXT
            resume.extracted_text = extracted_text
            # SKILL EXTRACTION
            skills = extract_skills(
                extracted_text
            )
            resume.skills = ",".join(skills)
            # ATS SCORE
            resume.ats_score = calculate_ats_score(
                extracted_text
            )
            # COMPANY MATCHING
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
            # SUMMARY GENERATION
            resume.summary = generate_summary(
                skills
            )
            # FINAL SAVE
            resume.save()
            # REDIRECT TO RESULTS PAGE
            return redirect(
                'results',
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

# RESULTS PAGE
@login_required
def results(request, id):
    resume = get_object_or_404(
        Resume,
        id=id
    )
    skills = []
    if resume.skills:
        skills = resume.skills.split(",")
    context = {
        'resume': resume,
        'skills': skills
    }
    return render(
        request,
        'resumeapp/results.html',
        context
    )

# ANALYTICS PAGE
@login_required
def analytics(request):
    resumes = Resume.objects.all()
    total_resumes = resumes.count()
    highest_score = 0
    avg_match = 0
    if resumes.exists():
        highest_score = max(
            r.ats_score for r in resumes
        )
        avg_match = sum(
            r.google_score
            for r in resumes
        ) / total_resumes

    context = {
        'total_resumes': total_resumes,
        'highest_score': highest_score,
        'avg_match': round(avg_match)
    }
    return render(
        request,
        'resumeapp/analytics.html',
        context
    )