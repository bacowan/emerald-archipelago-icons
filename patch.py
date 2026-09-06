import json
import pkgutil
from pathlib import Path

from pokemon import Pokemon, Moveset, LevelUpMove

DATA_DIR = Path(__file__).parent / "data"

def _load_json(file_name: str):
    try:
        # Normal path: works when this module has a real package (e.g. imported
        # as worlds.pokemon_emerald_icons.patch), including from a frozen build.
        data = pkgutil.get_data(__name__, f"data/{file_name}")
    except ValueError:
        # Running this file directly (python patch.py) has no package spec to
        # resolve, so fall back to reading straight off disk for local dev.
        data = None
    if data is None:
        with open(DATA_DIR / file_name, encoding="utf-8-sig") as f:
            return json.load(f)
    return json.loads(data.decode("utf-8-sig"))

rom_locations = _load_json("rom_locations.json")
characters = _load_json("characters.json")

base_name_offset = int(rom_locations["offsets"]["pokemon_names"], 0)
pokemon_name_length = int(rom_locations["sizes"]["pokemon_name"])
address_length = int(rom_locations["sizes"]["address"])
base_front_sprite_table_offset = int(rom_locations["offsets"]["front_sprite_table"], 0)
base_back_sprite_table_offset = int(rom_locations["offsets"]["back_sprite_table"], 0)
sprite_table_entry_length = int(rom_locations["sizes"]["sprite_table_entry"])
base_palette_table_offset = int(rom_locations["offsets"]["palette_table"], 0)
palette_table_entry_length = int(rom_locations["sizes"]["palette_table_entry"])
moves_learnable_offset = int(rom_locations["offsets"]["moves_learnable"], 0)
level_up_move_size = int(rom_locations["sizes"]["level_up_move"])
hm_tm_learnset_offset = int(rom_locations["offsets"]["tm_hm_learnset"], 0)
hm_tm_learnset_size = rom_locations["sizes"]["tm_hm_learnset"]


def _patch_level_up_moves(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
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

def _patch_hm_tm(rom_data: bytearray, pokemon: Pokemon):
    offset = hm_tm_learnset_offset + pokemon.id * hm_tm_learnset_size
    current_moves = rom_data[offset:offset+hm_tm_learnset_size]

    # for now, we will just ignore HMs and use what's there already. HMs are 50-57.
    move_mask = (0b11111111 << 49) & int.from_bytes(current_moves, byteorder="little")

    for move in pokemon.moveset.tm_hm_moves:
        move_mask |= 1 << move

    rom_data[offset:offset+hm_tm_learnset_size] = move_mask.to_bytes(hm_tm_learnset_size, byteorder="little")

def _patch_moveset(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    free_space_start = _patch_level_up_moves(rom_data, pokemon, free_space_start)
    _patch_hm_tm(rom_data, pokemon)
    return free_space_start

def _patch_front_sprite(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # LZ77UnCompVram needs a 4-byte aligned source pointer
    free_space_start = (free_space_start + 3) & ~3

    # write the new sprite data
    rom_data[free_space_start:free_space_start + len(pokemon.front_sprite)] = pokemon.front_sprite

    # Find the pointer in the sprite table and overwrite it with the new location.
    # Add 0x8000 0000 to get the rom address rather than the ram address.
    sprite_table_entry_offset = base_front_sprite_table_offset + pokemon.id * sprite_table_entry_length
    sprite_ram_offset = free_space_start + 0x800_0000
    rom_data[sprite_table_entry_offset:sprite_table_entry_offset + address_length] = sprite_ram_offset.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.front_sprite)

def _patch_back_sprite(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # LZ77UnCompVram needs a 4-byte aligned source pointer
    free_space_start = (free_space_start + 3) & ~3

    # write the new sprite data
    rom_data[free_space_start:free_space_start + len(pokemon.back_sprite)] = pokemon.back_sprite

    # Find the pointer in the sprite table and overwrite it with the new location.
    # Add 0x8000 0000 to get the rom address rather than the ram address.
    sprite_table_entry_offset = base_back_sprite_table_offset + pokemon.id * sprite_table_entry_length
    sprite_ram_offset = free_space_start + 0x800_0000
    rom_data[sprite_table_entry_offset:sprite_table_entry_offset + address_length] = sprite_ram_offset.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.back_sprite)

def _patch_palette(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    # LZ77UnComp needs a 4-byte aligned source pointer
    free_space_start = (free_space_start + 3) & ~3

    # write the new palette data
    rom_data[free_space_start:free_space_start + len(pokemon.sprite_palette)] = pokemon.sprite_palette

    # Find the pointer in the palette table and overwrite it with the new location.
    # Add 0x8000000 to convert the file offset into a cartridge-mapped address.
    palette_table_entry_offset = base_palette_table_offset + pokemon.id * palette_table_entry_length
    palette_ram_offset = free_space_start + 0x800_0000
    rom_data[palette_table_entry_offset:palette_table_entry_offset + address_length] = palette_ram_offset.to_bytes(address_length, "little")

    return free_space_start + len(pokemon.sprite_palette)

def _patch_name(rom_data: bytearray, pokemon: Pokemon):
    name_offset = base_name_offset + pokemon.id * pokemon_name_length
    for i in range(min(pokemon_name_length - 1, len(pokemon.name))):
        char = pokemon.name[i]
        code = int(characters.get(char, characters.get("?")), 0)
        rom_data[name_offset + i] = code

def _patch_single_pokemon(rom_data: bytearray, pokemon: Pokemon, free_space_start: int) -> int:
    _patch_name(rom_data, pokemon)
    free_space_start = _patch_front_sprite(rom_data, pokemon, free_space_start)
    free_space_start = _patch_back_sprite(rom_data, pokemon, free_space_start)
    free_space_start = _patch_palette(rom_data, pokemon, free_space_start)
    free_space_start = _patch_moveset(rom_data, pokemon, free_space_start)
    return free_space_start

def patch(rom_data: bytearray, pokemon: list[Pokemon]) -> None:
    free_space_start = int(rom_locations["offsets"]["free_space"], 0)
    for pokemon in pokemon:
        free_space_start = _patch_single_pokemon(rom_data, pokemon, free_space_start)


if __name__ == "__main__":
    import argparse
    import random
    import string

    import numpy
    from PIL import Image

    from png_to_lz77 import png_to_lz77

    # Internal species count for Pokemon Emerald.
    NUM_POKEMON = 411

    parser = argparse.ArgumentParser(description="Patch a Pokemon Emerald ROM with a new icon sprite.")
    parser.add_argument("rom", type=Path, help="Path to the ROM to patch")
    parser.add_argument("png", type=Path, help="Path to the PNG sprite to insert")
    args = parser.parse_args()

    moves_data = _load_json("moves.json")
    move_ids = [move_id for move_id in moves_data["moves"].values() if move_id != 65535]
    tm_hm_indices = list(moves_data["tmhm_moves"].values())

    rom_path = args.rom
    png_path = args.png

    image = numpy.array(Image.open(png_path))
    front_sprite, back_sprite, sprite_palette = png_to_lz77(image)

    level_up_moves = sorted(
        (
            LevelUpMove(level=random.randint(1, 100), move_id=random.choice(move_ids))
            for _ in range(random.randint(4, 10))
        ),
        key=lambda move: move.level,
    )
    tm_hm_moves = random.sample(tm_hm_indices, k=random.randint(5, len(tm_hm_indices)))
    name = "".join(random.choices(string.ascii_uppercase, k=random.randint(4, pokemon_name_length - 1)))

    new_pokemon = Pokemon(
        id=283, # Mudkip
        name=name,
        moveset=Moveset(level_up_moves=level_up_moves, tm_hm_moves=tm_hm_moves),
        front_sprite=front_sprite,
        back_sprite=back_sprite,
        sprite_palette=sprite_palette,
    )

    with rom_path.open("rb") as rom_file:
        file_rom = bytearray(rom_file.read())

    patch(file_rom, [new_pokemon])

    output_dir = Path(__file__).parent / "out"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{rom_path.stem}_patched{rom_path.suffix}"
    with output_path.open("wb") as rom_file:
        rom_file.write(file_rom)

    print(f"Patched {new_pokemon.name} (id {new_pokemon.id}) and saved copy to {output_path}")