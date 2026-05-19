skills_list = [

    "Python",
    "Django",
    "React",
    "SQL",
    "Java",
    "Machine Learning",
    "HTML",
    "CSS",
    "JavaScript",
    "Bootstrap",
    "Git",
    "GitHub",
]


def extract_skills(text):

    found_skills = []

    for skill in skills_list:

        if skill.lower() in text.lower():

            found_skills.append(skill)

    return found_skills