def recommend(gaps: list[dict]):
    return [g["recommended_fix"] for g in gaps]
