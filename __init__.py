import asyncio
import os

import websockets
import json
import Utils
from dataclasses import dataclass
from worlds.LauncherComponents import Component, components, Type
from worlds.pokemon_emerald_icons.llm import call_claude


@dataclass
class LocationItemMapping:
    game: str
    item_name: str
    location_id: int

async def get_locations_to_items(address: str, slot_name: str, password: str) -> list[LocationItemMapping]:
    async with websockets.connect(f"ws://{address}", ping_timeout=None, ping_interval=None, max_size=None) as ws:
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
            "items_handling": 0b000,  # don't worry about sending items as they come in since this is a one time script
            "tags": ["NoText"],
            "uuid": Utils.get_unique_identifier()
        }]))

        connection_results = json.loads(await ws.recv())
        if connection_results[0]["cmd"] != "Connected":
            raise Exception("Connection failed")

        location_name_to_id = data[0]['data']['games']['Pokemon Emerald']['location_name_to_id']
        pokedex_location_ids = [value for key, value in location_name_to_id.items() if key.startswith("Pokedex")]

        await ws.send(json.dumps([{"cmd": "LocationScouts", "locations": pokedex_location_ids, "create_as_hint": 0}]))
        try:
            network_locations = json.loads(await ws.recv())
        except:
            # TODO: server doesn't send a response when any of the location checks aren't set
            raise

        player_to_game = {int(slot): info['game'] for slot, info in connection_results[0]['slot_info'].items()}
        location_ids_to_names = {
            game: {
                item_id: item_name
                for item_name, item_id in value['item_name_to_id'].items()
            }
            for game, value in data[0]['data']['games'].items()
        }

        def network_location_to_item(network_location):
            game = player_to_game[network_location['player']]
            return LocationItemMapping(
                game=game,
                item_name=location_ids_to_names[game][network_location['item']],
                location_id=network_location['location']
            )

        return [network_location_to_item(network_location) for network_location in network_locations[0]['locations']]

async def generate_pokemon_info(locations_to_items: list[LocationItemMapping], api_key: str) -> list[LocationItemMapping]:
    with open('moves.json') as f:
        moves = f.read().replace('\n', ' ')

    prompt = (f"For each item name below, output the single best generic search term to find a matching icon. "
              f"Additionally, generate a list of moves that it would have if it were a pokemon from the included list. "
              f"Possible moves:\n{moves}"
              f"Items:\n{[item.item_name for item in locations_to_items]}"
              )
    format = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "search_term": { "type": "string" },
                "moveset": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "level": { "type": "integer" },
                            "move": { "type": "integer"}
                        }
                    }
                }
            }
        }
    }
    return call_claude(prompt, format, api_key)

def get_cached_claude_key(new_key: str) -> str:
    cache_path = Utils.cache_path("claude_api_key.txt")
    os.makedirs(cache_path, exist_ok=True)

    if new_key:
        # Use the new key
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(new_key)
        return new_key

    elif os.path.exists(cache_path):
        # Use the cached key
        with open(cache_path) as f:
            cached = f.read().strip()
        if cached:
            return cached

    raise RuntimeError("No API key entered and no cached key found.")

def apply_patch():
    async def main():
        locations_to_items = await get_locations_to_items(address, slot_name, password)
        new_pokemon_info = await generate_pokemon_info(locations_to_items, claude_api_key)
        pass

    address = input("Server address (e.g. archipelago.gg:38281): ").strip()
    slot_name = input("Slot name: ").strip()
    password = input("Password (leave blank if none): ").strip()
    claude_api_key = input("Claude API key (leave blank to use previous key): ").strip()
    claude_api_key = get_cached_claude_key(claude_api_key.strip())

    asyncio.run(main())

def add_client_to_launcher() -> None:
    version = "0.1.0"
    found = False
    for c in components:
        if c.display_name == "Pokemon Emerald Icon Patcher":
            found = True
            if getattr(c, "version", 0) < version:
                c.version = version
                c.func = apply_patch
                return
    if not found:
        components.append(Component(
            "Pokemon Emerald Icon Patcher",
            cli=True,
            func=apply_patch,
            component_type=Type.TOOL))

if __name__ == "__main__":
    apply_patch()
else:
    add_client_to_launcher()