import json
from io import BytesIO
from pathlib import Path

import resvg_py
import numpy as np
import open_clip
import torch
from PIL import Image
from PIL.ImageFile import ImageFile
from tqdm import tqdm

JSON_ICON_PATH = Path(__file__).parent / 'out' / 'icon-sets-master' / 'json'
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

def json_to_svg(root, icon):
    width = icon.get("width", root.get("width", 16))
    height = icon.get("height", root.get("height", 16))
    left = icon.get("left", root.get("left", 0))
    top = icon.get("top", root.get("top", 0))

    rotate = icon.get("rotate", root.get("rotate", 0))
    hFlip = icon.get("hFlip", root.get("hFlip", False))
    vFlip = icon.get("vFlip", root.get("vFlip", False))

    cx, cy = left + width / 2, top + height / 2
    transforms = []
    if hFlip or vFlip:
        sx, sy = (-1 if hFlip else 1), (-1 if vFlip else 1)
        transforms.append(f"translate({cx} {cy}) scale({sx} {sy}) translate({-cx} {-cy})")
    if rotate:
        transforms.append(f"rotate({90 * rotate} {cx} {cy})")
    transform_attr = f' transform="{" ".join(transforms)}"' if transforms else ""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{left} {top} {width} {height}" style="color:#000000">'
        f'<g{transform_attr}>{icon["body"]}</g></svg>'
    )

def load_pngs() -> list[ImageFile]:
    json_dir = Path(JSON_ICON_PATH)
    svgs: list[ImageFile] = []
    json_files = list(json_dir.glob("*.json"))
    for json_file in tqdm(json_files, desc="Loading icon sets"):
        with open(json_file, encoding="utf-8") as f:
            root = json.load(f)
            for icon in root['icons'].values():
                svg = json_to_svg(root, icon)
                png_bytes = resvg_py.svg_to_bytes(svg_string=svg, width=224, height=224)
                img = Image.open(BytesIO(png_bytes)).convert("RGB")
                svgs.append(img)
    return svgs

def embed(images, model, device):
    with torch.no_grad():
        batch_tensor = torch.stack(images).to(device)
        features = model.encode_image(batch_tensor)
        features = features / features.norm(dim=-1, keepdim=True)
    return features.to(torch.float16).cpu().numpy()

def preembed():
    model, preprocess, device = setup()
    pngs = load_pngs()

    torch_formatted_images = [preprocess(img) for img in pngs]

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