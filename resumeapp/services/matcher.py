from sklearn.feature_extraction.text import (
    TfidfVectorizer
)

from sklearn.metrics.pairwise import (
    cosine_similarity
)


def calculate_match(
        resume_text,
        company_text):

    tfidf = TfidfVectorizer()

    vectors = tfidf.fit_transform([
        resume_text,
        company_text
    ])

    similarity = cosine_similarity(
        vectors[0:1],
        vectors[1:2]
    )

    return round(
        similarity[0][0] * 100
    )