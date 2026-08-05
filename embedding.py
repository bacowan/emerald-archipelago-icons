import json
from io import BytesIO
from pathlib import Path

import cairosvg
import numpy as np
import open_clip
import torch
from PIL import Image
from PIL.ImageFile import ImageFile

JSON_ICON_PATH = Path(__file__).parent / 'icon-sets-master' / 'json'
EMBEDDING_PATH = Path(__file__).parent / 'embedding.npy'
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

def load_pngs() -> list[ImageFile]:
    json_dir = Path(JSON_ICON_PATH)
    svgs: list[ImageFile] = []
    for json_file in json_dir.glob("*.json"):
        with open(json_file, encoding="utf-8") as f:
            as_json = json.load(f)
            for icon in as_json.icons.values:
                png_bytes = cairosvg.svg2png(
                    bytestring=icon.body.encode("utf-8"),
                    output_width=224,
                    output_height=224,
                    background_color="white",
                )

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
    for batch_start in range(0, len(torch_formatted_images), BATCH_SIZE):
        batch_end = batch_start + BATCH_SIZE
        vector = embed(torch_formatted_images[batch_start:batch_end], model, device)
        all_vectors.append(vector)

    final_vectors = np.concatenate(all_vectors, axis=0)

    np.save(EMBEDDING_PATH, final_vectors)

if __name__ == "__main__":
    preembed()