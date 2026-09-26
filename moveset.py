import json
import logging
import re
import time
from enum import Enum
from pathlib import Path

from google import genai
from google.genai._gaos.lib.compat_errors import APIStatusError
from pydantic import BaseModel, Field

from pokemon import LevelUpMove, Moveset

logger = logging.getLogger("PokemonEmeraldIcons")

MOVE_DATA_PATH = Path(__file__).parent / 'data' / 'moves.json'

MODEL = "gemini-3.6-flash"

# Gemini's free tier throws transient 503s and 429s under load; both are worth retrying
# rather than aborting the whole (potentially long) generation run.
MAX_RETRIES = 5
DEFAULT_RETRY_DELAY_SECONDS = 30
RETRY_DELAY_PATTERN = re.compile(r"retry in (\d+)s", re.IGNORECASE)

def _is_retryable(error: APIStatusError) -> bool:
    return error.status_code == 429 or (error.status_code is not None and error.status_code >= 500)

def _retry_delay_seconds(error: APIStatusError) -> float:
    match = RETRY_DELAY_PATTERN.search(str(error))
    return float(match.group(1)) if match else DEFAULT_RETRY_DELAY_SECONDS

def _create_interaction_with_retry(client, **kwargs):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return client.interactions.create(**kwargs)
        except APIStatusError as error:
            if not _is_retryable(error) or attempt == MAX_RETRIES:
                raise
            delay = _retry_delay_seconds(error)
            logger.warning(
                f"Gemini request failed ({error.status_code}), retrying in {delay:.0f}s "
                f"(attempt {attempt}/{MAX_RETRIES}): {error}"
            )
            time.sleep(delay)

def _load_move_data():
    with open(MOVE_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["moves"], data["tmhm_moves"]

MOVE_NAMES, TMHM_MOVES = _load_move_data()

def _tmhm_label(index: int) -> str:
    # ROM TM/HM bit index: 0-49 are TM01-TM50, 50-57 are HM01-HM08
    return f"TM{index + 1:02d}" if index < 50 else f"HM{index - 49:02d}"

# Gemini's structured output has an undocumented schema complexity limit that a 355-value
# enum (one per Emerald move) blows past, so moves/TMs are plain strings here and validated
# against these lookups after the fact instead of being constrained via enum in the schema.
TmHmLabel = Enum("TmHmLabel", {_tmhm_label(index): name for name, index in TMHM_MOVES.items()})
TMHM_LABEL_TO_MOVE_NAME = {member.name: member.value for member in TmHmLabel}

class LevelUpMoveResponse(BaseModel):
    move: str
    level: int = Field(ge=1, le=100)

class MovesetResponse(BaseModel):
    pokemon_name: str
    level_up_moves: list[LevelUpMoveResponse]
    tm_hm_moves: list[str]

class MovesetBatchResponse(BaseModel):
    movesets: list[MovesetResponse]

DEFAULT_BATCH_SIZE = 20

def _to_moveset(response: MovesetResponse) -> Moveset:
    invalid_moves = [m.move for m in response.level_up_moves if m.move not in MOVE_NAMES]
    invalid_labels = [t for t in response.tm_hm_moves if t not in TMHM_LABEL_TO_MOVE_NAME]
    if invalid_moves or invalid_labels:
        raise ValueError(
            f"Gemini returned move(s)/TM(s) that don't exist in Emerald for "
            f"{response.pokemon_name}: moves={invalid_moves} tm_hm={invalid_labels}"
        )

    return Moveset(
        level_up_moves=[
            LevelUpMove(level=m.level, move_id=MOVE_NAMES[m.move])
            for m in response.level_up_moves
        ],
        tm_hm_moves=[TMHM_MOVES[TMHM_LABEL_TO_MOVE_NAME[t]] for t in response.tm_hm_moves],
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

    interaction = _create_interaction_with_retry(
        client,
        model=MODEL,
        input=prompt,
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": MovesetBatchResponse.model_json_schema(),
        },
    )
    parsed = MovesetBatchResponse.model_validate_json(interaction.output_text)

    movesets_by_name = {m.pokemon_name: _to_moveset(m) for m in parsed.movesets}

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
