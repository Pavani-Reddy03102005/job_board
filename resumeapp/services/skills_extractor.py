"""
Skill detection with a categorised catalogue.

Matching uses word boundaries, so "Java" no longer matches inside "JavaScript",
and "Git" no longer matches inside "GitHub" or "digital".  extract_skills()
keeps its original signature (text -> list of skill names) and every skill from
the old list keeps its old spelling.
"""
import re

SKILL_CATALOG = {
    "Programming languages": {
        "Python": ["Python", "Python3"],
        "Java": ["Java"],
        "JavaScript": ["JavaScript", "ECMAScript"],
        "TypeScript": ["TypeScript"],
        "C++": ["C++"],
        "C#": ["C#"],
        "PHP": ["PHP"],
        "Kotlin": ["Kotlin"],
        "Swift": ["Swift"],
        "Go": ["Golang"],
        "Ruby": ["Ruby"],
        "HTML": ["HTML", "HTML5"],
        "CSS": ["CSS", "CSS3"],
        "Bash": ["Bash", "Shell scripting"],
    },
    "Frameworks and libraries": {
        "Django": ["Django"],
        "Django REST Framework": ["Django REST Framework", "DRF"],
        "Flask": ["Flask"],
        "FastAPI": ["FastAPI"],
        "React": ["React", "React.js", "ReactJS"],
        "React Native": ["React Native"],
        "Angular": ["Angular", "AngularJS"],
        "Vue.js": ["Vue.js", "VueJS", "Vue"],
        "Node.js": ["Node.js", "NodeJS"],
        "Express.js": ["Express.js", "ExpressJS"],
        "Spring Boot": ["Spring Boot", "SpringBoot"],
        "Hibernate": ["Hibernate"],
        "Bootstrap": ["Bootstrap"],
        "Tailwind CSS": ["Tailwind CSS", "TailwindCSS", "Tailwind"],
        "jQuery": ["jQuery"],
        "Flutter": ["Flutter"],
    },
    "Databases": {
        "SQL": ["SQL"],
        "MySQL": ["MySQL"],
        "PostgreSQL": ["PostgreSQL", "Postgres"],
        "SQLite": ["SQLite"],
        "SQL Server": ["SQL Server", "MS SQL", "MSSQL"],
        "Oracle": ["Oracle"],
        "MongoDB": ["MongoDB"],
        "Redis": ["Redis"],
        "Firebase": ["Firebase"],
    },
    "Developer tools": {
        "Git": ["Git"],
        "GitHub": ["GitHub"],
        "GitLab": ["GitLab"],
        "Docker": ["Docker"],
        "Kubernetes": ["Kubernetes", "K8s"],
        "Linux": ["Linux"],
        "AWS": ["AWS", "Amazon Web Services"],
        "Azure": ["Azure"],
        "GCP": ["GCP", "Google Cloud"],
        "Jenkins": ["Jenkins"],
        "CI/CD": ["CI/CD", "CICD"],
        "REST API": ["REST API", "REST APIs", "RESTful API", "RESTful APIs", "RESTful"],
        "Postman": ["Postman"],
        "Jira": ["Jira"],
        "Maven": ["Maven"],
        "pytest": ["pytest"],
        "Selenium": ["Selenium"],
        "Microsoft Excel": ["Microsoft Excel", "MS Excel", "Advanced Excel"],
        "Power BI": ["Power BI", "PowerBI"],
        "Tableau": ["Tableau"],
    },
    "AI/ML and data": {
        "Machine Learning": ["Machine Learning", "ML"],
        "Deep Learning": ["Deep Learning"],
        "NLP": ["NLP", "Natural Language Processing"],
        "Computer Vision": ["Computer Vision"],
        "Generative AI": ["Generative AI", "GenAI", "LLM", "LLMs", "Large Language Model", "Large Language Models"],
        "Data Analysis": ["Data Analysis", "Data Analytics"],
        "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
        "TensorFlow": ["TensorFlow"],
        "PyTorch": ["PyTorch"],
        "Keras": ["Keras"],
        "OpenCV": ["OpenCV"],
        "pandas": ["pandas"],
        "NumPy": ["NumPy"],
        "Matplotlib": ["Matplotlib"],
        "spaCy": ["spaCy"],
        "NLTK": ["NLTK"],
    },
    "Domain knowledge": {
        "Data Structures": ["Data Structures", "DSA"],
        "Algorithms": ["Algorithms"],
        "OOP": ["OOP", "OOPs", "Object-Oriented Programming", "Object Oriented Programming"],
        "Microservices": ["Microservices"],
        "Agile": ["Agile", "Scrum"],
        "System Design": ["System Design"],
        "Web Development": ["Web Development"],
    },
}

# Listing a specific tool is evidence for the broader skill it implies.
IMPLIES = {
    "MySQL": ["SQL"],
    "PostgreSQL": ["SQL"],
    "SQLite": ["SQL"],
    "SQL Server": ["SQL"],
    "Django REST Framework": ["Django"],
    "Spring Boot": ["Java"],
    "Express.js": ["Node.js"],
}
IMPLIED_BY = {}
for _tool, _broader in IMPLIES.items():
    for _b in _broader:
        IMPLIED_BY.setdefault(_b, []).append(_tool)

_EXCLUDE_AFTER = {"React": r"\s+Native"}   # "React Native" is not plain React


def _build_pattern(skill, aliases):
    body = "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
    tail = _EXCLUDE_AFTER.get(skill)
    neg = "(?!%s)" % tail if tail else ""
    return re.compile(r"(?<![\w+#])(?:%s)%s(?![\w+#])" % (body, neg), re.IGNORECASE)


_SKILLS = []      # (category, skill, compiled pattern) in catalogue order
_PATTERNS = {}
_CATEGORY = {}
for _cat, _skills in SKILL_CATALOG.items():
    for _skill, _aliases in _skills.items():
        _p = _build_pattern(_skill, _aliases)
        _SKILLS.append((_cat, _skill, _p))
        _PATTERNS[_skill] = _p
        _CATEGORY[_skill] = _cat


def find_skills(text):
    """Directly mentioned skills as [(category, skill)] in catalogue order."""
    return [(cat, skill) for cat, skill, pattern in _SKILLS if pattern.search(text or "")]


def extract_skills(text):
    """Skill names found in the text (plus the broader skills they imply)."""
    direct = {skill for _, skill in find_skills(text)}
    allowed = set(direct)
    for skill in direct:
        allowed.update(IMPLIES.get(skill, []))
    return [skill for _, skill, _ in _SKILLS if skill in allowed]


def extract_skills_by_category(text):
    names = set(extract_skills(text))
    grouped = {}
    for cat, skill, _ in _SKILLS:
        if skill in names:
            grouped.setdefault(cat, []).append(skill)
    return grouped


def skill_category(skill):
    return _CATEGORY.get(skill)


def skill_pattern(skill):
    return _PATTERNS[skill]


def evidence_patterns(skill):
    """Patterns whose matches count as evidence for a skill (including implying tools)."""
    return [_PATTERNS[skill]] + [_PATTERNS[s] for s in IMPLIED_BY.get(skill, [])]