import os
import pandas as pd
import numpy as np
from huggingface_hub import hf_hub_download
from rich import print as rprint

REPO_ID = "Subhadip007/UERP_Dataset"

class DataStore:
    def __init__(self):
        self.catalog = None
        self.structured_features = None
        self.text_embeddings = None
        self.loaded = False

    def load(self, hf_token = None):
        rprint("Loading UERP data from HF Hub...")

        catalog_path = hf_hub_download(
            repo_id = REPO_ID,
            filename = "catalog_with_features_v1.parquet",
            repo_type = "dataset",
            token = hf_token
        )

        self.catalog = pd.read_parquet(catalog_path).reset_index(drop = True)

        structured_path = hf_hub_download(
            repo_id = REPO_ID,
            filename = "structured_features_v1.npy",
            repo_type = "dataset",
            token = hf_token
        )

        self.structured_features = np.load(structured_path)

        embed_path = hf_hub_download(
            repo_id = REPO_ID, 
            filename = "overview_embeddings_v1.npy", 
            repo_type = "dataset", 
            token = hf_token
        )

        self.text_embeddings = np.load(embed_path)

        assert len(self.catalog) == self.structured_features.shape[0] == self.text_embeddings.shape[0], "Row count mismatch on load!"

        self.loaded = True
        
        rprint(f"Loaded {len(self.catalog)} titles.")


data_store = DataStore()