import json
import logging
from typing import TypedDict

import numpy
import websockets
import Utils
from worlds.pokemon_emerald_icons.moveset import get_movesets
from worlds.pokemon_emerald_icons.patch import patch
from worlds.pokemon_emerald_icons.png_to_lz77 import png_to_lz77
from worlds.pokemon_emerald_icons.pokemon import Pokemon
from worlds.pokemon_emerald_icons.retrieve_icon import retrieve_icons
from pathlib import Path

# Named logger (rather than the root logger) so this plays nicely whether it's run standalone
# (see __main__ below) or imported into an already-configured Archipelago process, e.g. the Launcher.
logger = logging.getLogger("PokemonEmeraldIcons")

POKEMON_NAME_TO_IDS_PATH = Path(__file__).parent / 'data' / 'pokemon_name_to_ids.json'

def _load_pokemon_name_to_ids():
    with open(POKEMON_NAME_TO_IDS_PATH, encoding="utf-8") as f:
        return json.load(f)

POKEMON_NAME_TO_IDS = _load_pokemon_name_to_ids()


class ItemLocation(TypedDict):
    pokemon_id: int
    item_name: str
    game: str

async def _get_item_data(address: str, slot_name: str, password: str) -> list[ItemLocation]:
    logger.info(f"Connecting to {address} as {slot_name}")
    async with websockets.connect(f"ws://{address}", ping_timeout=None, ping_interval=None, max_size=None) as ws:
        # Server sends RoomInfo first
        room_info = json.loads(await ws.recv())
        await ws.send(json.dumps([{"cmd": "GetDataPackage", "games": room_info[0]["games"]}]))
        data = json.loads(await ws.recv())

        await ws.send(json.dumps([{
            "cmd": "Connect",
            "password": password,
            "game": "Pokemon Emerald",
            "name": slot_name,
            "version": {
                "major": Utils.__version__.split(".")[0],
                "minor": Utils.__version__.split(".")[1],
                "build": Utils.__version__.split(".")[2],
                "class": "Version",
            },
            "items_handling": 0b000, # don't worry about sending items as they come in since this is a one time script
            "tags": ["NoText"],
            "uuid": Utils.get_unique_identifier()
        }]))

        connection_results = json.loads(await ws.recv())
        if connection_results[0]["cmd"] != "Connected":
            logger.error(f"Connection failed: {connection_results}")
            raise Exception("Connection failed")
        logger.info("Connected to server")

        location_name_to_id = data[0]['data']['games']['Pokemon Emerald']['location_name_to_id']
        location_ids_to_pokemon_ids = {
            value: POKEMON_NAME_TO_IDS[key.removeprefix("Pokedex - ")]["internal_id"]
            for key, value in location_name_to_id.items()
            if key.startswith("Pokedex")
        }
        pokedex_location_ids = [value for key, value in location_name_to_id.items() if key.startswith("Pokedex")]

        logger.info(f"Scouting {len(pokedex_location_ids)} Pokedex location(s)")
        await ws.send(json.dumps([{"cmd": "LocationScouts", "locations": pokedex_location_ids, "create_as_hint": 0}]))
        try:
            network_locations = json.loads(await ws.recv())
        except Exception as e:
            # TODO: server doesn't send a response when any of the location checks aren't set
            logger.exception("Failed to receive location scouts from server. Check the server logs; "
                             "does the given player have pokemon catch checks enabled?")
            raise

        player_to_game = {int(slot): info['game'] for slot, info in connection_results[0]['slot_info'].items()}
        item_ids_to_names = {
            game: {
                item_id: item_name
                for item_name, item_id in value['item_name_to_id'].items()
            }
            for game, value in data[0]['data']['games'].items()
        }
        def network_location_to_item(network_location) -> ItemLocation:
            game = player_to_game[network_location['player']]
            return {
                'pokemon_id': location_ids_to_pokemon_ids[network_location['location']],
                'item_name': item_ids_to_names[game][network_location['item']],
                'game': game
            }

        items = [network_location_to_item(network_location) for network_location in network_locations[0]['locations']]
        logger.info(f"Retrieved {len(items)} item(s) to generate icons for")
        return items

def _select_icons(items: list[ItemLocation]) -> list[numpy.ndarray]:
    logger.info(f"Selecting icons for {len(items)} item(s)")
    options = retrieve_icons([item['item_name'] for item in items])

    selected_indices: set[int] = set()
    icons: list[numpy.ndarray] = []
    # The top 5 options were retrieved for each icon with `retrieve_icons`.
    # Select the best one that has not already been selected.
    for item_options in options:
        # Filter out options that have been selected (but grab the top one if all have been selected)
        icon, score, index = next(
            (option for option in item_options if option[2] not in selected_indices),
            item_options[0],
        )
        selected_indices.add(index)
        icons.append(icon)

    return icons

async def generate(address: str, slot_name: str, password: str, rom_path: Path):
    logger.info("Starting Pokemon Emerald icon generation")
    item_data = await _get_item_data(address, slot_name, password)
    icons = _select_icons(item_data)
    logger.info("Compressing icons and generating movesets")
    compressed_icons = [png_to_lz77(icon) for icon in icons]
    movesets = get_movesets(item_data)
    updated_pokemon = [
        Pokemon(
            id=item["pokemon_id"],
            name=item["item_name"],
            moveset=moveset,
            front_sprite=compressed.front,
            back_sprite=compressed.back,
            sprite_palette=compressed.palette,
        )
        for item, moveset, compressed in zip(item_data, movesets, compressed_icons)
    ]

    logger.info(f"Reading ROM from {rom_path}")
    with rom_path.open("rb") as file:
        rom_data = bytearray(file.read())

    logger.info(f"Patching {len(updated_pokemon)} Pokemon entries")
    patch(rom_data, updated_pokemon)

    with rom_path.open("wb") as file:
        file.write(rom_data)
    logger.info(f"Wrote patched ROM to {rom_path}")


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Generate a Pokemon Emerald ROM with icons pulled from an Archipelago server.")
    parser.add_argument("address", help="Archipelago server address, e.g. localhost:38281")
    parser.add_argument("slot_name", help="Slot name to connect as")
    parser.add_argument("rom", type=Path, help="Path to the ROM to patch")
    parser.add_argument("--password", default="", help="Server password, if any")
    parser.add_argument("--loglevel", default="info", choices=["debug", "info", "warning", "error", "critical"],
                         help="Log level for console/file output")
    args = parser.parse_args()

    # Sets up the same file+console logging (under Utils.user_path("logs")) that Archipelago's own
    # clients use, and routes uncaught exceptions through our logger instead of a bare traceback.
    Utils.init_logging("PokemonEmeraldIcons", loglevel=args.loglevel, exception_logger="PokemonEmeraldIcons")

    asyncio.run(generate(args.address, args.slot_name, args.password, args.rom))
