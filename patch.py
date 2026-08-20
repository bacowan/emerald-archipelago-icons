import json
import pkgutil

from pokemon import Pokemon
from worlds.pokemon_emerald_icons.pokemon import Moveset

rom_locations = json.loads(pkgutil.get_data(__name__, "data/rom_locations.json").decode("utf-8-sig"))
characters = json.loads(pkgutil.get_data(__name__, "data/characters.json").decode("utf-8-sig"))

base_name_offset = int(rom_locations["offsets"]["pokemon_names"], 0)
pokemon_name_length = int(rom_locations["sizes"]["pokemon_names"], 0)
address_length = int(rom_locations["lengths"]["address"])
base_sprite_table_offset = int(rom_locations["offsets"]["sprite_table"], 0)
sprite_table_entry_length = int(rom_locations["lengths"]["sprite_table_entry"], 0)


def _patch_moveset(rom_data: bytearray, pokemon: Pokemon):
    pass

def _patch_sprite(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # write the new sprite data
    rom_data[free_space_start:free_space_start + len(pokemon.sprite)] = pokemon.sprite

    # find the pointer in the sprite table and overwrite it with the new location
    sprite_table_entry_offset = base_sprite_table_offset + pokemon.id * sprite_table_entry_length
    rom_data[sprite_table_entry_offset:sprite_table_entry_offset + address_length] = free_space_start.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.sprite)

def _patch_palette(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    pass

def _patch_name(rom_data: bytearray, pokemon: Pokemon):
    name_offset = base_name_offset + pokemon.id * pokemon_name_length
    for i in range(min(pokemon_name_length - 1, len(pokemon.name))):
        char = pokemon.name[i]
        code = characters.get(char, characters.get("?"))
        rom_data[name_offset + i] = code

def _patch_single_pokemon(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    _patch_name(rom_data, pokemon)
    free_space_start = _patch_sprite(rom_data, pokemon, free_space_start)
    free_space_start = _patch_palette(rom_data, pokemon, free_space_start)
    _patch_moveset(rom_data, pokemon)
    return free_space_start

def patch(rom_data: bytearray, pokemon: list[Pokemon]) -> None:
    free_space_start = int(rom_locations["offsets"]["free_space"], 0)
    for pokemon in pokemon:
        free_space_start = _patch_single_pokemon(rom_data, pokemon, free_space_start)