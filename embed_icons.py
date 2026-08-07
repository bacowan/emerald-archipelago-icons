from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image
from tqdm import tqdm

PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'
EMBEDDING_PATH = Path(__file__).parent / 'out' / 'embedding.npy'
BATCH_SIZE = 256

def setup():
    # use GPU if available, CPU otherwise
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # load the model and preprocessor
    model, _, preprocess = open_clip.create_model_and_transforms(
        "ViT-B-32",
        # a good size/accuracy tradeoff; bigger models exist (ViT-L-14) if you want more accuracy at the cost of speed/size
        pretrained="laion2b_s34b_b79k",  # which trained checkpoint to use for that architecture
    )

    # use inference mode instead of training mode
    model = model.to(device).eval()

    return model, preprocess, device

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