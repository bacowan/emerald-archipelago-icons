from pathlib import Path

import numpy as np
import torch
from PIL import Image
from tqdm import tqdm

from embedding_common import setup

PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'
EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
BATCH_SIZE = 256

def load_pngs() -> list[Image.Image]:
    array = np.load(PNG_PATH)
    return [Image.fromarray(img) for img in array]

def embed(images, model, device):
    with torch.no_grad():
        batch_tensor = torch.stack(images).to(device)
        features = model.encode_image(batch_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.to(torch.float16).cpu().numpy()

def preembed():
    model, preprocess, device = setup()
    pngs = load_pngs()

    torch_formatted_images = [preprocess(img) for img in tqdm(pngs, desc="Preprocessing images")]

    all_vectors = []
    batch_starts = range(0, len(torch_formatted_images), BATCH_SIZE)
    for batch_start in tqdm(batch_starts, desc="Embedding batches"):
        batch_end = batch_start + BATCH_SIZE
        vector = embed(torch_formatted_images[batch_start:batch_end], model, device)
        all_vectors.append(vector)

    final_vectors = np.concatenate(all_vectors, axis=0)

    np.save(EMBEDDING_PATH, final_vectors)

if __name__ == "__main__":
    preembed()