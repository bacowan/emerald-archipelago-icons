from pathlib import Path

import numpy as np
import open_clip
import torch
from embedding_common import setup

EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'

tokenizer = open_clip.get_tokenizer("ViT-B-32")

def embed_text(query, model, device):
    tokens = tokenizer([query]).to(device)
    with torch.no_grad():
        features = model.encode_text(tokens) # embed text
        features = features / features.norm(dim=-1, keepdim=True) # normalize the text
    return features.cpu().numpy()[0]

def retrieve_icon(query, top_k=5):
    model, preprocess, device = setup()
    query_vector = embed_text(query, model, device)

    icon_vectors = np.load(EMBEDDING_PATH)  # shape: (num_icons, 512)

    scores = icon_vectors @ query_vector  # @ is dot product: compare to each vector

    top_indices = np.argsort(scores)[::-1][:top_k]

    pngs = np.load(PNG_PATH)  # same order as icon_vectors, so indices line up
    return [(pngs[i], scores[i]) for i in top_indices]
