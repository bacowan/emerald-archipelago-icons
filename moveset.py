import json
from enum import Enum
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from pokemon import LevelUpMove, Moveset

MOVE_DATA_PATH = Path(__file__).parent / 'data' / 'moves.json'

MODEL = "gemini-2.5-flash"

def _load_move_data():
    with open(MOVE_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["moves"], data["tmhm_moves"]

MOVE_NAMES, TMHM_MOVES = _load_move_data()

def _tmhm_label(index: int) -> str:
    # ROM TM/HM bit index: 0-49 are TM01-TM50, 50-57 are HM01-HM08
    return f"TM{index + 1:02d}" if index < 50 else f"HM{index - 49:02d}"

# enums constrain Gemini's structured output to moves/TMs that actually exist in Emerald
MoveName = Enum("MoveName", {name.upper().replace(" ", "_"): name for name in MOVE_NAMES})
TmHmLabel = Enum("TmHmLabel", {_tmhm_label(index): name for name, index in TMHM_MOVES.items()})

class LevelUpMoveResponse(BaseModel):
    move: MoveName
    level: int = Field(ge=1, le=100)

class MovesetResponse(BaseModel):
    pokemon_name: str
    level_up_moves: list[LevelUpMoveResponse]
    tm_hm_moves: list[TmHmLabel]

class MovesetBatchResponse(BaseModel):
    movesets: list[MovesetResponse]

DEFAULT_BATCH_SIZE = 10

def _to_moveset(response: MovesetResponse) -> Moveset:
    return Moveset(
        level_up_moves=[
            LevelUpMove(level=m.level, move_id=MOVE_NAMES[m.move.value])
            for m in response.level_up_moves
        ],
        tm_hm_moves=[TMHM_MOVES[t.value] for t in response.tm_hm_moves],
    )

def _get_moveset_batch(names, client):
    move_list = ", ".join(sorted(MOVE_NAMES))
    tmhm_list = ", ".join(f"{member.name} ({member.value})" for member in TmHmLabel)
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
            response_schema=MovesetBatchResponse,
        ),
    )

    movesets_by_name = {m.pokemon_name: _to_moveset(m) for m in response.parsed.movesets}

    missing = [name for name in names if name not in movesets_by_name]
    if missing:
        raise ValueError(f"Gemini did not return movesets for: {missing}")

    return movesets_by_name

def get_movesets(names, batch_size=DEFAULT_BATCH_SIZE) -> list[Moveset]:
    client = genai.Client()

    movesets_by_name = {}
    for batch_start in range(0, len(names), batch_size):
        batch = names[batch_start:batch_start + batch_size]
        movesets_by_name.update(_get_moveset_batch(batch, client))

    return [movesets_by_name[name] for name in names]
