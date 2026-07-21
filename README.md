# UERP — Universal Entertainment Recommendation Platform

A zero-cost, production-style AI recommendation system for **Movies**, **TV Series**, and **Anime**, built end-to-end as a portfolio project.

> **Status:** Phase 1 (Data Foundation) — ✅ Complete

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture & Tech Stack](#architecture--tech-stack)
- [Data Pipeline — Phase 1: Data Foundation](#data-pipeline--phase-1-data-foundation)
  - [Data Sources](#data-sources)
  - [Key Engineering Decisions](#key-engineering-decisions)
  - [Unified Schema](#unified-schema)
  - [Known Data Characteristics](#known-data-characteristics)
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

## Repository Structure

```
uerp-platform/
├── kaggle-notebooks/
│   ├── uerp-data-ingestion.ipynb      # IMDb filtering, TMDB enrichment, AniList pull
│   └── uerp-unified-schema.ipynb      # Schema unification, genre canonicalization, HF push
├── backend/                           # FastAPI backend (coming soon)
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

# Backend (coming in Phase 3)
cd backend
# pip install -r requirements.txt
# uvicorn main:app --reload

# Frontend (coming in Phase 4)
cd frontend
# npm install && npm run dev
```

---

## Progress Log

| Phase | Milestone | Status | Notes |
| ----- | --------- | ------ | ----- |
| **1** | Data Foundation | ✅ Complete | 39,664 unified titles (34,763 IMDb+TMDB + 4,912 AniList). Catalog published to HF Hub. |
| **2** | Exploratory Data Analysis | 🔲 Not started | — |
| **3** | Backend + Recommendation Engine | 🔲 Not started | — |
| **4** | Frontend + UI | 🔲 Not started | — |
| **5** | Deployment | 🔲 Not started | — |

---

## Up Next

**Phase 2: Exploratory Data Analysis (EDA)**
- Missing value analysis across the unified catalog
- Genre distribution breakdown (overall and by content type)
- Year, rating, and popularity distributions
- Outlier detection and data quality validation

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <i>Built with ☕ and curiosity by <a href="https://github.com/07subhadip">Subhadip</a></i>
</p>

