
import numpy as np

def recommend_for_user(user_id, model, ratings, movies, links, catalog, movie_rating_counts,
                        min_rating_count = 100, top_n = 10):
    all_movie_ids = ratings['movieId'].unique()
    watched = ratings[ratings['userId'] == user_id]['movieId'].values
    unwatched = np.setdiff1d(all_movie_ids, watched)

    reliable_items = movie_rating_counts[movie_rating_counts >= min_rating_count].index
    unwatched = np.intersect1d(unwatched, reliable_items)

    predictions = [(m, model.predict(user_id, m, clip=False).est) for m in unwatched]
    predictions.sort(key=lambda x: x[1], reverse = True)
    top_movie_ids = [m for m, score in predictions[:top_n]]
    top_scores = {m: score for m, score in predictions[:top_n]}

    result = movies[movies['movieId'].isin(top_movie_ids)].copy()
    result['predicted_rating'] = result['movieId'].map(top_scores)
    result = result.merge(links[['movieId', 'content_id']], on = 'movieId', how = 'left')
    result = result.merge(catalog[['content_id', 'rating_normalized', 'popularity_percentile']], on = 'content_id', how = 'left')

    return result.sort_values('predicted_rating', ascending = False)
