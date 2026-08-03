import urllib.request
import zipfile

from tqdm import tqdm

from pathlib import Path

ICONIFY_REPO_URL = 'https://codeload.github.com/iconify/icon-sets/zip/refs/heads/master'
DOWNLOAD_CHUNK_SIZE = 8192

DOWNLOAD_PATH = Path(__file__).parent
ZIP_FILE_NAME = 'icons.zip'

def download_icons():
    zip_path = DOWNLOAD_PATH / ZIP_FILE_NAME

    # download the zip file
    with urllib.request.urlopen(ICONIFY_REPO_URL) as response:
        total = int(response.headers.get("Content-Length", 0))
        with open(zip_path, "wb") as f, tqdm(total=total, unit="B", unit_scale=True, desc="Downloading icon-sets") as bar:
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                f.write(chunk)
                bar.update(len(chunk))

    # extract the zip file
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(DOWNLOAD_PATH)