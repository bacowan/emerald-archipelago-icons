from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

from embedding_common import setup

PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'
EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
BATCH_SIZE = 256

def embed(images, model, preprocess, device):
    torch_formatted_images = [preprocess(Image.fromarray(img)) for img in images]
    with torch.no_grad():
        batch_tensor = torch.stack(torch_formatted_images).to(device)
        features = model.encode_image(batch_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.to(torch.float16).cpu().numpy()

def preembed():
    model, preprocess, device = setup()
    # mmap so the (potentially tens-of-GB) array is paged in from disk on
    # demand instead of being loaded into RAM all at once
    pngs = np.load(PNG_PATH, mmap_mode="r")

    all_vectors = []
    batch_starts = range(0, len(pngs), BATCH_SIZE)
    for batch_start in tqdm(batch_starts, desc="Embedding batches"):
        batch_end = min(batch_start + BATCH_SIZE, len(pngs))
        # preprocess just this batch, not the whole dataset at once
        vector = embed(pngs[batch_start:batch_end], model, preprocess, device)
        all_vectors.append(vector)

    final_vectors = np.concatenate(all_vectors, axis=0)

    np.save(EMBEDDING_PATH, final_vectors)

if __name__ == "__main__":
    preembed()