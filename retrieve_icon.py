from pathlib import Path

import numpy as np
import open_clip
import torch
from embedding_common import setup
from PIL import Image

EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'
RETRIEVED_DIR = Path(__file__).parent / 'out' / 'retrieved'

tokenizer = open_clip.get_tokenizer("ViT-B-32")

def _embed_texts(queries, model, device):
    tokens = tokenizer(queries).to(device)
    with torch.no_grad():
        features = model.encode_text(tokens) # embed text
        features = features / features.norm(dim=-1, keepdim=True) # normalize the text
    return features.cpu().numpy()  # shape: (num_queries, 512)

def retrieve_icons(queries: list[str], top_k: int = 5) -> list[list[tuple[np.ndarray, float, int]]]:
    model, preprocess, device = setup()
    query_vectors = _embed_texts(queries, model, device)  # shape: (num_queries, 512)

    icon_vectors = np.load(EMBEDDING_PATH)  # shape: (num_icons, 512)
    # mmap so the (potentially tens-of-GB) array is paged in from disk on
    # demand instead of being loaded into RAM all at once
    pngs = np.load(PNG_PATH, mmap_mode="r")  # same order as icon_vectors, so indices line up

    scores = icon_vectors @ query_vectors.T  # shape: (num_icons, num_queries)

    results = []
    for i in range(len(queries)):
        top_indices = np.argsort(scores[:, i])[::-1][:top_k]
        results.append([(pngs[j], scores[j, i], j) for j in top_indices])
    return results

def save_results(queries: list[str], results: list[list[tuple[np.ndarray, float, int]]]) -> None:
    RETRIEVED_DIR.mkdir(parents=True, exist_ok=True)
    for query, matches in zip(queries, results):
        query_dir = RETRIEVED_DIR / query.replace(" ", "_")
        query_dir.mkdir(exist_ok=True)
        for rank, (png, score, index) in enumerate(matches):
            Image.fromarray(png).save(query_dir / f"{rank}_idx{index}_score{score:.4f}.png")

if __name__ == "__main__":
    queries = ["Unlock Tick Tock Clock", "TM11", "Never-Melt Ice", "Old Rod", "Rare Candy", "Dive"]
    results = retrieve_icons(queries, 5)
    print([[(score, index) for _, score, index in matches] for matches in results])
    save_results(queries, results)