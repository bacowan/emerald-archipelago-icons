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
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{left} {top} {width} {height}" style="color:#000000">'
        f'<g{transform_attr}>{icon["body"]}</g></svg>'
    )

def convert_icons_to_png():
    json_dir = Path(JSON_ICON_PATH)
    json_files = list(json_dir.glob("*.json"))

    roots = {}
    total_icons = 0
    for json_file in json_files:
        with open(json_file, encoding="utf-8") as f:
            root = json.load(f)
            roots[json_file] = root
            total_icons += len(root['icons'])

    # Back the output buffer with a disk-mapped .npy file instead of a plain
    # in-memory array: at 224x224x3 uint8, hundreds of thousands of icons add
    # up to tens of GB, more than fits in RAM on most machines. The memmap
    # lets the OS page data to/from disk instead of holding it all resident.
    stacked = np.lib.format.open_memmap(
        PNG_PATH, mode="w+", dtype=np.uint8, shape=(total_icons, 224, 224, 3)
    )

    count = 0
    with tqdm(total=total_icons, desc="Converting icons to PNG") as pbar:
        for json_file, root in roots.items():
            for icon_name, icon in root['icons'].items():
                try:
                    svg = json_to_svg(root, icon)
                    png_bytes = resvg_py.svg_to_bytes(svg_string=svg, width=224, height=224)
                    img = Image.open(BytesIO(png_bytes)).convert("RGB")
                    if img.size != (224, 224):
                        # resvg preserves aspect ratio, so non-square icons render smaller
                        # than 224 in one dimension; pad to a square canvas to match the rest.
                        canvas = Image.new("RGB", (224, 224))
                        canvas.paste(img, ((224 - img.width) // 2, (224 - img.height) // 2))
                        img = canvas
                    stacked[count] = np.asarray(img)
                    count += 1
                except Exception as e:
                    print(f"Failed to convert icon '{icon_name}' in file '{json_file}': {e}")
                pbar.update(1)

    stacked.flush()
    if count < total_icons:
        # some icons failed to convert; shrink the file to drop the unused
        # trailing rows, copying in chunks to keep memory usage bounded
        del stacked
        src = np.lib.format.open_memmap(PNG_PATH, mode="r")
        tmp_path = PNG_PATH.with_suffix(".tmp.npy")
        dst = np.lib.format.open_memmap(
            tmp_path, mode="w+", dtype=np.uint8, shape=(count, 224, 224, 3)
        )
        chunk = 1000
        for start in range(0, count, chunk):
            end = min(start + chunk, count)
            dst[start:end] = src[start:end]
        dst.flush()
        del src, dst
        tmp_path.replace(PNG_PATH)

if __name__ == "__main__":
    convert_icons_to_png()
