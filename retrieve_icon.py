from pathlib import Path

import numpy as np
import open_clip
import torch
from embedding_common import setup

EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'

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
    pngs = np.load(PNG_PATH)  # same order as icon_vectors, so indices line up

    scores = icon_vectors @ query_vectors.T  # shape: (num_icons, num_queries)

    results = []
    for i in range(len(queries)):
        top_indices = np.argsort(scores[:, i])[::-1][:top_k]
        results.append([(pngs[j], scores[j, i], j) for j in top_indices])
    return results
