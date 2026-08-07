import json
from io import BytesIO
from pathlib import Path

import resvg_py
import numpy as np
from PIL import Image
from tqdm import tqdm

JSON_ICON_PATH = Path(__file__).parent / 'out' / 'icon-sets-master' / 'json'
PNG_PATH = Path(__file__).parent / 'out' / 'pngs.npy'

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

def convert_icons_to_png():
    json_dir = Path(JSON_ICON_PATH)
    json_files = list(json_dir.glob("*.json"))

    images = []
    for json_file in tqdm(json_files, desc="Converting icon sets to PNG"):
        with open(json_file, encoding="utf-8") as f:
            root = json.load(f)
            for icon in root['icons'].values():
                svg = json_to_svg(root, icon)
                png_bytes = resvg_py.svg_to_bytes(svg_string=svg, width=224, height=224)
                img = Image.open(BytesIO(png_bytes)).convert("RGB")
                images.append(np.array(img))

    stacked = np.stack(images, axis=0)
    np.save(PNG_PATH, stacked)

if __name__ == "__main__":
    convert_icons_to_png()
