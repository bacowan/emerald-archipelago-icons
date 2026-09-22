# emerald-archipelago-icons

## Move data

`moveset.py` reads valid move names and TM/HM-to-move mappings from `data/moves.json`, a static
snapshot generated from Pokemon Emerald's move list. It's self-contained within this repo — no
dependency on the main Archipelago repo or its `pokemon_emerald` world.

## API keys

`moveset.py` calls the Gemini API via `genai.Client()`, which reads its API key from the
`GEMINI_API_KEY` (or `GOOGLE_API_KEY`) environment variable — there's no config file for it. Get a
key from [Google AI Studio](https://aistudio.google.com/apikey) and set it permanently before
running `generation.py` (open a new terminal afterward for it to take effect):

```powershell
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "your-key-here", "User")
```

```cmd
setx GEMINI_API_KEY "your-key-here"
```

```bash
echo 'export GEMINI_API_KEY="your-key-here"' >> ~/.bashrc
source ~/.bashrc
```
