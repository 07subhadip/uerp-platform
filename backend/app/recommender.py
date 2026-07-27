
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def get_popular(catalog, content_type = None, is_anime = None, genre = None, top_n = 10):
    df = catalog.copy()
    if content_type is not None:
        df = df[df['content_type'] == content_type]
    if is_anime is not None:
        df = df[df['is_anime'] == is_anime]
    if genre is not None:
        df = df[df['genres'].apply(lambda g: genre in g)]
    df = df.sort_values(['popularity_percentile', 'rating_normalized'], ascending = False)
    return df.head(top_n)

def get_similar(content_id, catalog, structured_features, text_embeddings,
                genre_weight = 0.3, text_weight = 0.7,
                min_popularity_percentile = 0.7, min_rating = 6.0, top_n = 10):
    idx_matches = catalog.index[catalog['content_id'] == content_id]
    if len(idx_matches) == 0:
        return None
    idx = idx_matches[0]

    genre_vec = structured_features[idx, :32].reshape(1, -1)
    genre_sims = cosine_similarity(genre_vec, structured_features[:, :32])[0]

    text_vec = text_embeddings[idx].reshape(1, -1)
    text_sims = cosine_similarity(text_vec, text_embeddings)[0]

    hybrid_scores = (genre_weight * genre_sims) + (text_weight * text_sims)

    result_df = catalog.copy()
    result_df['similarity_score'] = hybrid_scores
    result_df = result_df[result_df['content_id'] != content_id]
    result_df = result_df[result_df['popularity_percentile'] >= min_popularity_percentile]
    result_df = result_df[result_df['rating_normalized'] >= min_rating]
    result_df = result_df.sort_values('similarity_score', ascending = False)

    return result_df.head(top_n)
