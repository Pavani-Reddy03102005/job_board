def calculate_ats_score(text):

    score = 0

    keywords = [

        "Python",
        "Projects",
        "Skills",
        "Education",
        "Experience",

    ]

    for keyword in keywords:

        if keyword.lower() in text.lower():

            score += 20

    return score