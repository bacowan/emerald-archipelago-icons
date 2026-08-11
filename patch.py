import json
import pkgutil

from pokemon import Pokemon
from worlds.pokemon_emerald_icons.pokemon import Moveset

rom_locations = json.loads(pkgutil.get_data(__name__, "data/rom_locations.json").decode("utf-8-sig"))


def _patch_moveset(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_sprite(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_name(rom_data: bytearray, pokemon: Pokemon):
    name_offset = rom_locations["offsets"]["pokemon_names"]

def _patch_single_pokemon(rom_data: bytearray, pokemon: Pokemon):
    _patch_name(rom_data, pokemon)
    _patch_sprite(rom_data, pokemon)
    _patch_moveset(rom_data, pokemon)

def patch(rom_data: bytearray, pokemon: list[Pokemon]) -> None:
    for pokemon in pokemon:
        _patch_single_pokemon(rom_data, pokemon)