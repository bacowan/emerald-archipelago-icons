import json
from enum import Enum
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

MOVE_DATA_PATH = Path(__file__).parent / 'data' / 'moves.json'

MODEL = "gemini-2.5-flash"

def _load_move_data():
    with open(MOVE_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["moves"], data["tmhm_moves"]

MOVE_NAMES, TMHM_MOVES = _load_move_data()

# enums constrain Gemini's structured output to moves/TMs that actually exist in Emerald
MoveName = Enum("MoveName", {name.upper().replace(" ", "_"): name for name in MOVE_NAMES})
TmHmLabel = Enum("TmHmLabel", {label: label for label in TMHM_MOVES})

class LevelUpMove(BaseModel):
    move: MoveName
    level: int = Field(ge=1, le=100)

class Moveset(BaseModel):
    pokemon_name: str
    level_up_moves: list[LevelUpMove]
    tm_hm_moves: list[TmHmLabel]

class MovesetBatch(BaseModel):
    movesets: list[Moveset]

DEFAULT_BATCH_SIZE = 10

def _format_moveset(moveset):
    return {
        "level_up_moves": [
            {"move": m.move.value, "move_id": MOVE_NAMES[m.move.value], "level": m.level}
            for m in moveset.level_up_moves
        ],
        "tm_hm_moves": [
            {"label": t.value, "move": TMHM_MOVES[t.value]["name"], "move_id": TMHM_MOVES[t.value]["id"]}
            for t in moveset.tm_hm_moves
        ],
    }

def _get_moveset_batch(names, client):
    move_list = ", ".join(sorted(MOVE_NAMES))
    tmhm_list = ", ".join(f"{label} ({info['name']})" for label, info in TMHM_MOVES.items())
    name_list = "\n".join(f"- {name}" for name in names)

    prompt = f"""You are designing movesets for {len(names)} fictional Pokemon in Pokemon Emerald.
For EACH Pokemon name below, infer a theme from its name (for example, a Pokemon named "Star" should lean
toward space, light, or shine-related moves) and choose moves that fit that theme as closely as possible,
using ONLY moves from the lists below (these are the only moves that exist in Pokemon Emerald). Treat each
Pokemon independently and give it the same amount of thought you would if it were the only one.

For each Pokemon, provide:
1. Level-up moves: moves it learns as it levels up, each with a level from 1-100. A typical Pokemon learns
   around 10-15 moves this way (a couple at level 1, then roughly every 3-8 levels after), generally
   getting stronger/more thematic as level increases.
2. TM/HM moves: TMs/HMs it can learn, chosen by label (e.g. "TM06", "HM02"). A typical Pokemon can learn
   around 15-30 of these, picked for thematic and type fit.

Return one entry per Pokemon name, in the order given, with "pokemon_name" set to the exact name below.

Pokemon names:
{name_list}

Valid moves: {move_list}

Valid TMs/HMs: {tmhm_list}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MovesetBatch,
        ),
    )

    movesets_by_name = {m.pokemon_name: _format_moveset(m) for m in response.parsed.movesets}

    missing = [name for name in names if name not in movesets_by_name]
    if missing:
        raise ValueError(f"Gemini did not return movesets for: {missing}")

    return movesets_by_name

def get_moveset(names, batch_size=DEFAULT_BATCH_SIZE):
    client = genai.Client()

    results = {}
    for batch_start in range(0, len(names), batch_size):
        batch = names[batch_start:batch_start + batch_size]
        results.update(_get_moveset_batch(batch, client))

    return results
