import json
import pkgutil

from pokemon import Pokemon
from worlds.pokemon_emerald_icons.pokemon import Moveset

rom_locations = json.loads(pkgutil.get_data(__name__, "data/rom_locations.json").decode("utf-8-sig"))
characters = json.loads(pkgutil.get_data(__name__, "data/characters.json").decode("utf-8-sig"))


def _patch_moveset(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_sprite(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_palette(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_name(rom_data: bytearray, pokemon: Pokemon):
    base_name_offset = int(rom_locations["offsets"]["pokemon_names"], 0)
    pokemon_name_length = int(rom_locations["sizes"]["pokemon_names"], 0)
    name_offset = base_name_offset + pokemon.id * pokemon_name_length
    for i in range(min(pokemon_name_length - 1, len(pokemon.name))):
        char = pokemon.name[i]
        code = characters.get(char, characters.get("?"))
        rom_data[name_offset + i] = code

def _patch_single_pokemon(rom_data: bytearray, pokemon: Pokemon):
    _patch_name(rom_data, pokemon)
    _patch_sprite(rom_data, pokemon)
    _patch_palette(rom_data, pokemon)
    _patch_moveset(rom_data, pokemon)

def patch(rom_data: bytearray, pokemon: list[Pokemon]) -> None:
    for pokemon in pokemon:
        _patch_single_pokemon(rom_data, pokemon)