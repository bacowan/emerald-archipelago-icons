import os
from pathlib import Path

from worlds.pokemon_emerald_icons.convert_icons_to_png import convert_icons_to_png
from worlds.pokemon_emerald_icons.download_icons import download_icons
from worlds.pokemon_emerald_icons.embed_icons import preembed

OUTPUT_PATH = Path(__file__).parent / 'out'
DOWNLOAD_PATH = OUTPUT_PATH / 'icon-sets-master'
PNG_PATH = OUTPUT_PATH / 'pngs.npy'
EMBEDDINGS_PATH = OUTPUT_PATH / 'embeddings.npy'

def preprocess(force: bool = False):
    if force or not os.path.exists(DOWNLOAD_PATH):
        download_icons()
    if force or not os.path.exists(PNG_PATH):
        convert_icons_to_png()
    if force or not os.path.exists(EMBEDDINGS_PATH):
        preembed()