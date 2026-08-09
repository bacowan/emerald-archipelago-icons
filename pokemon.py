from dataclasses import dataclass

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
    name: str
    moveset: Moveset
    icon: bytes
