# pokemon_emerald_icons

## Protected generated artifacts — do not delete without explicit confirmation

`out/` is gitignored (not tracked by git), so anything deleted there cannot be
recovered from git history. Several files in `out/` are expensive to regenerate:

- `out/pngs.npy` — ~46GB, all icon PNGs decoded into a single array (built by
  `convert_icons_to_png.py`).
- `out/embedding.npy` — CLIP embeddings for every image in `pngs.npy`, produced
  by `embed_icons.py`. Takes a long time to regenerate (batched model inference
  over the full `pngs.npy` dataset).

These look like disposable build output during a generic "clean up temp files"
pass, but they are not — they represent significant compute time. Never delete
files under `out/` as part of a cleanup task. If a file here looks stale or
unused, ask before removing it.
