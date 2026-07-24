from CommonClient import CommonContext


class PokemonEmeraldIconsClient(CommonContext):
    game = None  # not tied to a specific game's client logic, we just need the network layer
    items_handling = 0b000  # we don't need items delivered to us

    async def server_auth(self, password_requested: bool = False):
        if password_requested and not self.password:
            await super(PokemonEmeraldIconsClient, self).server_auth(password_requested)
        await self.get_username()   # prompts for slot name if self.auth is None
        await self.send_connect()   # sends Connect packet with that slot name