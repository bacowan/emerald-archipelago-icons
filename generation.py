import json
from typing import TypedDict

import numpy
import websockets
import Utils
from worlds.pokemon_emerald_icons.moveset import get_movesets
from worlds.pokemon_emerald_icons.patch import patch
from worlds.pokemon_emerald_icons.pokemon import Pokemon
from worlds.pokemon_emerald_icons.retrieve_icon import retrieve_icons
from pathlib import Path


class ItemLocation(TypedDict):
    pokemon_id: int
    item_name: str
    game: str

async def _get_item_data(address: str, slot_name: str, password: str) -> list[ItemLocation]:
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
            raise Exception("Connection failed")

        location_name_to_id = data[0]['data']['games']['Pokemon Emerald']['location_name_to_id']
        location_ids_to_pokemon_ids = { value: int(key[-3]) for key, value in location_name_to_id.items() if key.startswith("Pokedex") }
        pokedex_location_ids = [value for key, value in location_name_to_id.items() if key.startswith("Pokedex")]

        await ws.send(json.dumps([{"cmd": "LocationScouts", "locations": pokedex_location_ids, "create_as_hint": 0}]))
        try:
            network_locations = json.loads(await ws.recv())
        except:
            # TODO: server doesn't send a response when any of the location checks aren't set
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

        return [network_location_to_item(network_location) for network_location in network_locations[0]['locations']]

def _select_icons(items: list[ItemLocation]) -> list[numpy.ndarray]:
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
    item_data = await _get_item_data(address, slot_name, password)
    icons = _select_icons(item_data)
    movesets = get_movesets(item_data)
    updated_pokemon = [
        Pokemon(
            id=item["pokemon_id"],
            name=item["item_name"],
            moveset=movesets[i],
            sprite=icons[i]
        ) for i, item in enumerate(item_data)
    ]

    with rom_path.open("rb") as file:
        rom_data = bytearray(file.read())

    patch(rom_data, updated_pokemon)

    with rom_path.open("wb") as file:
        file.write(rom_data)
