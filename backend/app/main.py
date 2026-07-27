from importlib.metadata import version
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
import json

from app.data_loader import data_store
from app.recommender import get_popular, get_similar

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

@asynccontextmanager
async def lifespan(app: FastAPI):
    data_store.load(hf_token = HF_TOKEN)
    yield

app = FastAPI(
    title = "UERP API",
    version = "0.1.0",
    lifespan = lifespan
)

@app.get("/")
def root():
    return {
        "status": "ok",
        "title_loaded": len(data_store.catalog) if data_store.loaded else 0
    }

@app.get("/popular")
def popular(
    content_type: str = None,
    is_anime: bool = None,
    genre: str = None,
    top_n: int = 10
):
    result = get_popular(
        data_store.catalog,
        content_type = content_type,
        is_anime = is_anime,
        genre = genre,
        top_n = top_n 
    )

    df_subset = result[
        [
            "content_id",
            "title",
            "content_type",
            "is_anime",
            "genres",
            "rating_normalized",
            "poster_url",
        ]
    ]
    return json.loads(df_subset.to_json(orient="records"))


@app.get("/similar/{content_id}")
def similar(content_id: str, top_n: int = 10):
    result = get_similar(content_id, data_store.catalog, data_store.structured_features, data_store.text_embeddings, top_n = top_n)
    if result is None:
        raise HTTPException(
            status_code = 404,
            detail = f"content_id '{content_id}' not found"
        )

    df_subset = result[
        [
            "content_id",
            "title",
            "content_type",
            "is_anime",
            "genres",
            "rating_normalized",
            "poster_url",
            "similarity_score"
        ]
    ]
    return json.loads(df_subset.to_json(orient="records"))