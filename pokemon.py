from dataclasses import dataclass

import numpy


@dataclass
class LevelUpMove:
    level: int
    move_id: int

@dataclass
class Moveset:
    level_up_moves: list[LevelUpMove]
    tm_hm_moves: list[int]

@dataclass
class Pokemon:
    id: int
    name: str
    moveset: Moveset
    sprite: bytearray
    sprite_palette: bytearray