import json
import pkgutil

from pokemon import Pokemon
from worlds.pokemon_emerald_icons.pokemon import Moveset, LevelUpMove

rom_locations = json.loads(pkgutil.get_data(__name__, "data/rom_locations.json").decode("utf-8-sig"))
characters = json.loads(pkgutil.get_data(__name__, "data/characters.json").decode("utf-8-sig"))

base_name_offset = int(rom_locations["offsets"]["pokemon_names"], 0)
pokemon_name_length = int(rom_locations["sizes"]["pokemon_names"], 0)
address_length = int(rom_locations["lengths"]["address"])
base_sprite_table_offset = int(rom_locations["offsets"]["sprite_table"], 0)
sprite_table_entry_length = int(rom_locations["lengths"]["sprite_table_entry"], 0)
base_palette_table_offset = int(rom_locations["offsets"]["palette_table"], 0)
palette_table_entry_length = int(rom_locations["lengths"]["palette_table_entry"], 0)
moves_learnable_offset = int(rom_locations["offsets"]["moves_learnable"], 0)
level_up_move_size = int(rom_locations["sizes"]["level_up_move"], 0)


def _patch_moveset(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # write the new level up moves
    for move in pokemon.moveset.level_up_moves:
        # Note that the format for moves is the first 9 bits are the move id, and the next 7 are the level,
        # hence the bit shift of 9
        move_bytes = (move.level << 9 | move.move_id).to_bytes(level_up_move_size, byteorder="little")
        rom_data[free_space_start:free_space_start+level_up_move_size] = move_bytes
        free_space_start += level_up_move_size
    # add terminator characters
    rom_data[free_space_start:free_space_start+level_up_move_size] = 0xFF_FF.to_bytes(level_up_move_size)
    free_space_start += level_up_move_size
    return free_space_start

def _patch_sprite(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # write the new sprite data
    rom_data[free_space_start:free_space_start + len(pokemon.sprite)] = pokemon.sprite

    # find the pointer in the sprite table and overwrite it with the new location
    sprite_table_entry_offset = base_sprite_table_offset + pokemon.id * sprite_table_entry_length
    rom_data[sprite_table_entry_offset:sprite_table_entry_offset + address_length] = free_space_start.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.sprite)

def _patch_palette(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # write the new palette data
    rom_data[free_space_start:free_space_start + len(pokemon.sprite_palette)] = pokemon.sprite_palette

    # find the pointer in the sprite table and overwrite it with the new location
    palette_table_entry_offset = base_palette_table_offset + pokemon.id * palette_table_entry_length
    rom_data[palette_table_entry_offset:palette_table_entry_offset + address_length] = free_space_start.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.sprite_palette)

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
    free_space_start = _patch_moveset(rom_data, pokemon, free_space_start)
    return free_space_start

def patch(rom_data: bytearray, pokemon: list[Pokemon]) -> None:
    free_space_start = int(rom_locations["offsets"]["free_space"], 0)
    for pokemon in pokemon:
        free_space_start = _patch_single_pokemon(rom_data, pokemon, free_space_start)