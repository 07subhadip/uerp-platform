# UERP — Universal Entertainment Recommendation Platform

A zero-cost, production-style AI recommendation system for **Movies**, **TV Series**, and **Anime**, built end-to-end as a portfolio project.

> **Status:** Phase 4 (Backend + Recommendation Engine) — ✅ Complete

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Data Pipeline — Phase 1: Data Foundation](#data-pipeline--phase-1-data-foundation)
  - [Data Sources](#data-sources)
  - [Key Engineering Decisions](#key-engineering-decisions)
  - [Unified Schema](#unified-schema)
  - [Known Data Characteristics](#known-data-characteristics)
- [Exploratory Data Analysis — Phase 2: EDA](#exploratory-data-analysis--phase-2-eda)
  - [Analysis Scope](#analysis-scope)
  - [Key Findings](#key-findings)
- [Feature Engineering — Phase 3](#feature-engineering--phase-3)
  - [Engineering Pipeline](#engineering-pipeline)
  - [Features Built](#features-built)
- [Repository Structure](#repository-structure)
- [Setup Notes](#setup-notes)
- [Progress Log](#progress-log)
- [Up Next](#up-next)
- [License](#license)

---

## Project Overview

UERP is a full-stack recommendation platform that surfaces personalized suggestions across three entertainment domains — movies, TV series, and anime — using a single unified catalog.

The project emphasizes **real-world engineering practices**: resumable pipelines, cross-source schema unification, genre canonicalization, and a modular architecture designed for independent deployment of each layer.

---

## Architecture & Tech Stack

| Layer              | Technology                                      |
| ------------------ | ----------------------------------------------- |
| **Backend**        | FastAPI (Python)                                |
| **Frontend**       | Next.js (React)                                 |
| **Database**       | Supabase (Postgres)                             |
| **Deployment**     | Vercel (frontend) · Render / HF Spaces (backend)|
| **Data Processing**| Kaggle Notebooks (Python, Pandas)               |
| **Model Training** | Kaggle (GPU)                                    |
| **Dataset Storage**| Hugging Face Hub → [`UERP_Dataset`](https://huggingface.co/datasets/Subhadip007/UERP_Dataset) repo |
| **Model Storage**  | Hugging Face Hub → [`UERP_Model`](https://huggingface.co/Subhadip007/UERP_Model) repo            |

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Kaggle      │────▶│  Hugging Face    │────▶│  FastAPI Backend  │
│  Notebooks   │     │  Hub (Dataset +  │     │  (Render / HF    │
│  (ETL +      │     │  Model repos)    │     │   Spaces)        │
│   Training)  │     └──────────────────┘     └────────┬─────────┘
└──────────────┘                                       │
                                                       ▼
                      ┌──────────────────┐     ┌──────────────────┐
                      │  Supabase        │◀───▶│  Next.js         │
                      │  (Postgres)      │     │  Frontend        │
                      └──────────────────┘     │  (Vercel)        │
                                               └──────────────────┘
```

---

## Data Pipeline — Phase 1: Data Foundation

### Data Sources

| Source | What It Provides | Access Method |
| ------ | --------------- | ------------- |
| **IMDb** (non-commercial datasets) | Core movie/TV metadata — titles, year, runtime, genres, ratings, vote counts | `title.basics.tsv.gz`, `title.ratings.tsv.gz` (bulk download) |
| **TMDB API** | Enrichment — overview (plot synopsis), poster URL, backdrop URL, vote average, genre IDs | REST `/find/{imdb_id}` endpoint, cross-referenced by IMDb ID |
| **AniList GraphQL API** | Anime-specific data — titles, format, genres, scores, popularity, episodes, cover images | `https://graphql.anilist.co` (GraphQL) |

> **Why AniList over Jikan (MyAnimeList)?** Jikan is an unofficial scraper of MAL's pages and returned persistent **504 Gateway Timeout** errors across multiple Kaggle sessions. AniList serves its own database directly — no live scraping — making it far more reliable for batch pulls.

### Key Engineering Decisions

#### IMDb Subsetting Strategy

Filtered to relevant title types (`movie`, `tvSeries`, `tvMiniSeries`, `tvMovie`, `tvSpecial`, `short`, `tvShort`), excluding `tvEpisode` and `videoGame`.

Used **per-type top-N selection by `numVotes`** (not a global vote threshold) to preserve catalog diversity across content types:

| Type           | Target Count |
| -------------- | ------------ |
| `movie`        | 20,000       |
| `tvSeries`     | 8,000        |
| `tvMiniSeries` | 2,000        |
| `tvMovie`      | 2,000        |
| `short`        | 1,500        |
| `tvSpecial`    | 1,000        |
| `tvShort`      | 500          |
| **Total**      | **~35,000**  |

#### TMDB Enrichment Pipeline

- **Threaded batch processing**: `ThreadPoolExecutor` with 8 workers.
- **Checkpoint-and-resume**: saves progress to a parquet checkpoint every 500 records, with done-ID tracking. Survives Kaggle session interruptions without redoing work.
- **Backfill pass**: types with low initial TMDB match rates (`tvSpecial`, `short`, `tvShort`) were backfilled in a second pass to restore target composition.
- **Final result**: **34,763 IMDb+TMDB titles** after removing 2 explicitly "Adult"-genre-tagged titles (pornographic content only — R-rated and mature mainstream content was retained).

#### AniList Pull

- Discovered a hard API limit: *"Page depth exceeds maximum allowed for API requests (5,000 entries)"*.
- Pulled **top 5,000 anime by `POPULARITY_DESC`** (AniList's own database sort).
- Filtered out `isAdult=True` and `format=MUSIC`.
- **Final result**: **4,912 anime titles**.

#### Cross-Source Genre Canonicalization

IMDb, TMDB, and AniList each use different genre taxonomies (e.g., `"Sci-Fi"` vs `"Science Fiction"`, TMDB's combined tags like `"Action & Adventure"`).

Built a **canonical genre mapping** — renames, splits, merges, and drops of content-type tags — resulting in **32 canonical genres** used consistently across all sources.

#### Content-Type Normalization

Unified IMDb's `titleType` and AniList's `format` into a single taxonomy:

| Canonical Type   | Maps From                                |
| ---------------- | ---------------------------------------- |
| `movie`          | IMDb `movie`, AniList `MOVIE`            |
| `tv_series`      | IMDb `tvSeries`, AniList `TV`            |
| `tv_miniseries`  | IMDb `tvMiniSeries`                      |
| `tv_movie`       | IMDb `tvMovie`                           |
| `tv_special`     | IMDb `tvSpecial`, AniList `OVA`/`ONA`/`SPECIAL` |
| `short`          | IMDb `short`/`tvShort`                   |

### Unified Schema

The final merged catalog uses the following columns:

| Column              | Description                                                      |
| ------------------- | ---------------------------------------------------------------- |
| `content_id`        | Unique identifier (IMDb `tconst` or AniList ID)                  |
| `is_anime`          | Boolean flag distinguishing anime from non-anime content          |
| `title`             | Primary title                                                    |
| `content_type`      | Canonical type (see table above)                                 |
| `year`              | Release year                                                     |
| `genres`            | List of canonical genres                                         |
| `overview`          | Plot synopsis (from TMDB or AniList)                             |
| `rating_normalized` | 0–10 scale (AniList's 0–100 `averageScore` divided by 10)        |
| `popularity_signal` | Relative popularity metric                                       |
| `poster_url`        | Poster image URL                                                 |
| `runtime_minutes`   | Runtime in minutes (movies only; null for TV-type entries)        |
| `episodes`          | Episode count (anime only; null for non-anime entries)            |

**Final unified catalog: 39,664 titles** → pushed to Hugging Face Hub as `unified_catalog_v1.parquet` in the [`UERP_Dataset`](https://huggingface.co/datasets/Subhadip007/UERP_Dataset) repo.

### Known Data Characteristics

These are expected nulls from source data limitations, not bugs:

| Column             | Null Count | Reason                                          |
| ------------------ | ---------- | ----------------------------------------------- |
| `year`             | 171        | Missing in original IMDb data                   |
| `overview`         | 4          | TMDB match found but overview field empty        |
| `rating_normalized`| 104        | Low-vote / niche titles with no rating           |
| `poster_url`       | 92         | No poster available on TMDB                      |
| `runtime_minutes`  | —          | Null for all TV-type entries (by design)         |
| `episodes`         | —          | Null for all non-anime entries (by design)       |

---

## Exploratory Data Analysis — Phase 2: EDA

Comprehensive exploratory analysis of the unified catalog (39,664 titles) to validate data quality, understand distributions, and inform feature engineering for the recommendation engine.

**Notebook:** [`uerp-eda.ipynb`](kaggle-notebooks/uerp-eda.ipynb)

### Analysis Scope

- **Missing value analysis** — quantified nulls across all columns, validated they match expected patterns from Phase 1 (e.g., `runtime_minutes` null for TV-type, `episodes` null for non-anime)
- **Genre distribution** — breakdown of canonical genres overall and by content type (movie vs. TV vs. anime), identification of dominant and underrepresented genres
- **Year distribution** — release year spread across content types, temporal coverage and gaps
- **Rating distribution** — `rating_normalized` (0–10 scale) distribution, comparison across content types and anime vs. non-anime
- **Popularity distribution** — `popularity_signal` spread, skewness analysis, long-tail patterns
- **Outlier detection** — statistical identification of anomalous values in ratings, popularity, runtime, and episodes
- **Content-type breakdown** — catalog composition across `movie`, `tv_series`, `tv_miniseries`, `tv_movie`, `tv_special`, `short`
- **Anime vs. non-anime split** — comparative analysis of the two catalog segments

### Key Findings

> Detailed charts and statistical breakdowns are in the notebook itself. Below is a high-level summary.

- The catalog is **movie-dominant** (~20K movies) with healthy TV series representation (~8K), and a dedicated anime segment (4,912 titles)
- Genre distribution shows **Drama** as the most common genre across all content types, with anime having a distinctly different genre profile (heavier on Action, Fantasy, Comedy)
- Rating distributions are roughly normal-shaped (centered ~6.5–7.0 for non-anime, ~6.5–7.5 for anime), with no suspicious spikes or artifacts
- Popularity follows a heavy **long-tail distribution** — a small number of titles account for the vast majority of popularity signal
- Missing values align with Phase 1 documentation — no unexpected data gaps discovered
- Year coverage spans from early cinema through 2026, with density increasing in recent decades

---

## Feature Engineering — Phase 3

Transformed the cleaned unified catalog into a model-ready feature set for the recommendation engine. Built text, categorical, and numerical features from raw fields.

**Notebook:** [`uerp-feature-engineering.ipynb`](kaggle-notebooks/uerp-feature-engineering.ipynb)

### Engineering Pipeline

- **Text features** — processed `overview` (plot synopsis) and `title` fields for downstream NLP-based similarity (e.g., TF-IDF, embeddings)
- **Genre encoding** — converted the canonical genre lists into multi-hot binary vectors across all 32 genres for content-based filtering
- **Numerical normalization** — scaled `rating_normalized`, `popularity_signal`, `runtime_minutes`, and `episodes` for model compatibility
- **Null handling** — imputed or flagged missing values identified during Phase 2 EDA (e.g., missing overviews, ratings, posters) using strategies appropriate to each field
- **Categorical encoding** — encoded `content_type` and `is_anime` for model consumption
- **Combined feature matrix** — assembled all engineered features into a single model-ready dataset

### Features Built

| Feature Category | Columns / Approach | Notes |
| ---------------- | ------------------ | ----- |
| **Text** | `overview`, `title` | Cleaned and prepared for TF-IDF / embedding generation |
| **Genre** | 32 binary columns (multi-hot) | One column per canonical genre |
| **Numerical** | `rating_normalized`, `popularity_signal`, `runtime_minutes`, `episodes` | Scaled / normalized |
| **Categorical** | `content_type`, `is_anime` | Encoded for model input |
| **Null flags** | Indicator columns for missing values | Preserves missingness signal |

> Detailed transformations, distribution checks, and output validation are in the notebook.

## Known Limitations

**Known limitation (Stage 2 content-based recommender):** Titles tagged with very few genres 
(e.g., single-tag "Drama") can rank exact single-tag matches above thematically-closer 
multi-tag titles, due to cosine similarity's sensitivity to tag-vector sparsity. Will be 
addressed by the learned ranking model (Stage 6) rather than hand-tuned further in the MVP.

---

## Repository Structure

```
uerp-platform/
├── kaggle-notebooks/
│   ├── uerp-data-ingestion.ipynb      # Phase 1: IMDb filtering, TMDB enrichment, AniList pull
│   ├── uerp-unified-schema.ipynb      # Phase 1: Schema unification, genre canonicalization, HF push
│   ├── uerp-eda.ipynb                 # Phase 2: Exploratory data analysis on unified catalog
│   ├── uerp-feature-engineering.ipynb  # Phase 3: Feature engineering for recommendation model
│   └── uerp-mvp-recommender.ipynb     # Phase 4: Content-based recommendation model and MVP
├── backend/                           # FastAPI backend
├── frontend/                          # Next.js frontend (coming soon)
├── docs/                              # Project documentation (coming soon)
├── LICENSE
└── README.md
```

---

## Setup Notes

### Data Pipeline (Kaggle Notebooks)

The data ingestion and schema unification notebooks are designed to run on **Kaggle** with the following requirements:

- **Kaggle Secrets**: TMDB API key and Hugging Face write token should be stored as Kaggle User Secrets (not hardcoded). The notebooks access them via Kaggle's secrets API at runtime.
- **Internet Access**: Must be enabled in the Kaggle notebook settings for API calls and HF Hub uploads.
- **Resumability**: All pipelines use parquet-based checkpointing. If a Kaggle session times out, simply re-run the notebook — it picks up where it left off.

### Local Development (Future Phases)

```bash
# Clone the repo
git clone https://github.com/07subhadip/uerp-platform.git
cd uerp-platform

# Backend (coming in Phase 4)
cd backend
# pip install -r requirements.txt
# uvicorn main:app --reload

# Frontend (coming in Phase 5)
cd frontend
# npm install && npm run dev
```

---

## Progress Log

| Phase | Milestone | Status | Notes |
| ----- | --------- | ------ | ----- |
| **1** | Data Foundation | ✅ Complete | 39,664 unified titles (34,763 IMDb+TMDB + 4,912 AniList). Catalog published to HF Hub. |
| **2** | Exploratory Data Analysis | ✅ Complete | Full EDA on unified catalog — distributions, missing values, outliers, genre/year/rating analysis. |
| **3** | Feature Engineering | ✅ Complete | Text, genre (multi-hot), numerical, and categorical features built from unified catalog. |
| **4** | Backend + Recommendation Engine | ✅ Complete | Content-based recommendation model training and FastAPI backend setup with endpoints. |
| **5** | Frontend + UI | 🔲 Not started | — |
| **6** | Deployment | 🔲 Not started | — |

---

## Up Next

**Phase 5: Frontend + UI**
- Next.js application setup and routing
- Implementation of landing page, search, and detail views
- Supabase integration for user auth and personalized lists

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <i>Built with ☕ and curiosity by <a href="https://github.com/07subhadip">Subhadip</a></i>
</p>

