"""The Half-Life 2 client.

Registered as a Launcher component in the world's `__init__.py`. It connects
to the server, and pumps the file bridge (`client/bridge.py`,
`docs/protocol.md`): game events in, one snapshot of the run out.

The game side is stateless across loads: everything it gates or reports is
decided from the snapshot this writes, so a quickload or a client restart
cannot desync the two.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import Utils
from CommonClient import (
    ClientCommandProcessor,
    CommonContext,
    get_base_parser,
    gui_enabled,
    handle_url_arg,
    logger,
    server_loop,
)
from NetUtils import ClientStatus

# Universal Tracker, when installed: inheriting its context adds the Tracker
# tab. The world's `interpret_slot_data` hands it the seed's rolled answers.
try:
    from worlds.tracker.TrackerClient import TrackerGameContext as SuperContext

    TRACKER_LOADED = True
except ModuleNotFoundError:
    SuperContext = CommonContext
    TRACKER_LOADED = False

from .. import mod
from ..data import load_campaign
from .bridge import Bridge, store_dir

GAME_NAME = "Half-Life 2"
HALF_LIFE_2 = "hl2"
POLL_INTERVAL = 0.2

# Typed in the game, not here; printed on connect because they are easy to
# forget between sessions. Chat (Y) or the console (`ap <command>`).
IN_GAME_COMMANDS = (
    ("!ap", "every chapter and its status"),
    ("!warp <number or name>", "start an unlocked chapter"),
    ("!warp <chapter> <part>", "back to a part you have reached"),
    ("!hub", "return to the hub"),
    ("!tracker", "checks found and missing on this map"),
    ("!status", "where the client and this map stand"),
    ("!help", "these commands, in game"),
)


class HalfLife2CommandProcessor(ClientCommandProcessor):
    def _cmd_moddir(self, path: str = "") -> bool:
        """Show or set the installed mod folder (normally found by itself)."""
        if path:
            self.ctx.set_mod_dir(path)
        logger.info(f"Mod folder: {self.ctx.mod_dir or '(not found)'}")
        return True

    def _cmd_install(self) -> bool:
        """Install the hl2ap mod as a Steam sourcemod (restart Steam after)."""
        try:
            steam_dir = mod.sourcemod_dir()
            game_dir, written, has_dll = mod.install_sourcemod(steam_dir)
        except (OSError, ValueError) as exc:
            logger.error(f"Install failed: {exc}")
            return True
        logger.info(f"Installed {written} files into {game_dir}.")
        if not has_dll:
            logger.warning("This apworld carries no server dll, so the mod cannot run. "
                           "Get a release build of the apworld.")
            return True
        logger.info('Restart Steam, then launch "Half-Life 2 Archipelago" from the library.')
        if sys.platform != "win32":
            logger.info("On Linux, set that entry's Properties > Compatibility to Proton.")
        self.ctx.set_mod_dir(str(game_dir))
        return True

    def _cmd_uninstall(self) -> bool:
        """Remove the hl2ap mod (your own saves stay)."""
        try:
            removed = mod.uninstall_sourcemod(mod.sourcemod_dir())
        except (OSError, ValueError) as exc:
            logger.error(f"Uninstall failed: {exc}")
            return True
        logger.info(f"Removed {removed} files. Your Half-Life 2 install was never touched.")
        return True

    def _cmd_chapters(self) -> bool:
        """Show chapter unlock status."""
        self.ctx.print_chapters()
        return True

    def _cmd_deathlink(self) -> bool:
        """Toggle DeathLink."""
        self.ctx.death_link_enabled = not self.ctx.death_link_enabled
        asyncio.create_task(self.ctx.update_death_link(self.ctx.death_link_enabled),
                            name="UpdateDeathLink")
        logger.info(f"DeathLink {'enabled' if self.ctx.death_link_enabled else 'disabled'}.")
        return True

    def _cmd_chat(self) -> bool:
        """Toggle relaying chat between the game and the multiworld."""
        self.ctx.chat_relay = not self.ctx.chat_relay
        logger.info(f"Chat relay {'enabled' if self.ctx.chat_relay else 'disabled'}.")
        return True

    def _cmd_commands(self) -> bool:
        """List the commands you type inside the game."""
        self.ctx.print_in_game_commands()
        return True


class HalfLife2Context(SuperContext):
    game = GAME_NAME
    command_processor = HalfLife2CommandProcessor
    items_handling = 0b111  # everything, our own placements included
    # UT's context adds a "Tracker" tag; a game client must not claim it.
    tags = {"AP"}

    def __init__(self, server_address: str | None, password: str | None,
                 mod_dir: str = "") -> None:
        super().__init__(server_address, password)
        self.campaign = load_campaign()
        self.item_by_id = {entry["id"]: entry for entry in self.campaign["items"]}
        self.location_name_by_id = {e["id"]: e["name"] for e in self.campaign["locations"]}
        self.chapter_names = {c["key"]: c["name"] for c in self.campaign["chapters"]}
        self.campaign_of_chapter = {c["key"]: c.get("campaign", HALF_LIFE_2)
                                    for c in self.campaign["chapters"]}
        self.complete_location = {
            e["trigger"]["chapter"]: e["id"] for e in self.campaign["locations"]
            if e["trigger"]["type"] == "chapter_complete"
        }
        self.data_version = str(self.campaign.get("data_version", ""))

        self.mod_dir = ""
        self.bridge: Bridge | None = None

        # From slot data; defaults are a seed with nothing said.
        self.campaigns: list[str] = [HALF_LIFE_2]
        self.goal_chapters: dict[str, str] = {
            c["key"]: c["goal_chapter"] for c in self.campaign["campaigns"]
        }
        self.missions_required_by_campaign: dict[str, int] = {}
        self.excluded_chapters: set[str] = set()
        self.starting_items: list[str] = []
        self.melee_throw = False
        self.death_link_enabled = False
        self.death_link_amnesty = 4

        # From the item stream.
        self.unlocked_chapters: set[str] = set()
        self.received_counts: dict[str, int] = {}
        self.completed: set[str] = set()
        self.goal_sent = False
        self.state_slot = ""
        self.chat_relay = True
        self.bridge_failures = 0
        # How far through the server's item history this run has got, and
        # whether the backlog the server resends on connect is in yet. Filler
        # is a one-shot effect and must never be redelivered from it.
        self.items_seen = 0
        self.items_synced = False

        self.resolve_mod_dir(mod_dir)

    # -- setup -----------------------------------------------------------

    def resolve_mod_dir(self, forced: str) -> None:
        for source, candidate in (
            ("--moddir", forced),
            ("HL2AP_MOD_DIR", os.environ.get("HL2AP_MOD_DIR", "")),
            ("Steam's sourcemods", str(mod.installed_game_dir() or "")),
        ):
            if candidate and (Path(candidate) / "gameinfo.txt").is_file():
                logger.info(f"Using the mod folder from {source}.")
                self.set_mod_dir(candidate)
                return
        logger.warning("The hl2ap mod is not installed. Run /install, then restart Steam.")

    def set_mod_dir(self, path: str) -> None:
        if not (Path(path) / "gameinfo.txt").is_file():
            logger.error(f"{path} is not an installed hl2ap mod folder (no gameinfo.txt).")
            return
        self.mod_dir = path
        store = store_dir(path)
        store.mkdir(parents=True, exist_ok=True)
        self.bridge = Bridge(store)
        self.bridge.clear_log()
        logger.info(f"Bridging through {store}")

    # -- Archipelago -----------------------------------------------------

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        super().on_package(cmd, args)
        if cmd == "Connected":
            self.forget_other_slot()
            self.items_synced = False
            self.apply_slot_data(args.get("slot_data", {}))
            if self.death_link_enabled:
                asyncio.create_task(self.update_death_link(True), name="UpdateDeathLink")
            for key in self.campaigns:
                logger.info(f"Connected. {self.missions_required_by_campaign.get(key, 0)} "
                            f"chapters open {self.chapter_names.get(self.goal_chapters[key], '')}.")
            self.print_in_game_commands()
        if cmd in ("Connected", "RoomUpdate", "ReceivedItems"):
            self.sync_completed()
        if cmd == "ReceivedItems":
            self.receive_items(args)
        elif cmd == "PrintJSON":
            self.relay_to_game(args)
        elif cmd == "Bounced":
            tags = args.get("tags", [])
            if "DeathLink" in tags and self.death_link_enabled and self.bridge:
                data = args.get("data", {})
                source = str(data.get("source", "someone")).replace("~", "-")
                cause = data.get("cause") or "an unknown fate"
                self.bridge.queue_event("DEATHLINK", f"{source}~{cause}")

    def apply_slot_data(self, slot_data: dict) -> None:
        self.campaigns = list(slot_data.get("campaigns", [HALF_LIFE_2]))
        self.goal_chapters.update(slot_data.get("goal_chapters", {}))
        self.goal_chapters = {k: v for k, v in self.goal_chapters.items() if k in self.campaigns}
        self.missions_required_by_campaign = {
            k: int(v) for k, v in slot_data.get("missions_required_by_campaign", {}).items()
        }
        self.excluded_chapters = set(slot_data.get("excluded_chapters", ())) | {
            key for key, owner in self.campaign_of_chapter.items() if owner not in self.campaigns
        }
        self.starting_items = list(slot_data.get("starting_items", ()))
        self.melee_throw = bool(slot_data.get("melee_throw", False))
        self.death_link_enabled = bool(slot_data.get("death_link", False))
        self.death_link_amnesty = int(slot_data.get("death_link_amnesty", 4))

    def relay_to_game(self, args: dict) -> None:
        """Multiworld chat into the game; never our own, never the item feed."""
        if not self.chat_relay or self.bridge is None:
            return
        if args.get("type") != "Chat" or args.get("slot") == self.slot:
            return
        text = "".join(part.get("text", "") for part in args.get("data", []))
        text = text.replace("|", "/").replace("\n", " ").strip()
        if text:
            self.bridge.queue_event("CHAT", text)  # the game prefixes "[AP] " itself

    def receive_items(self, args: dict) -> None:
        """Apply an item packet. Unlocks are rebuilt from the full history the
        server resends on every connect; filler fires only for items that
        arrive after it, never from that backlog."""
        start = int(args.get("index", 0))
        if start == 0:
            self.unlocked_chapters.clear()
            self.received_counts.clear()
        backlog = not self.items_synced
        for offset, item in enumerate(args["items"]):
            is_new = not backlog and (start + offset) >= self.items_seen
            self.apply_item(item.item, deliver=is_new)
        self.items_seen = max(self.items_seen, start + len(args["items"]))
        self.items_synced = True

    def apply_item(self, item_id: int, deliver: bool = True) -> None:
        entry = self.item_by_id.get(item_id)
        if entry is None:
            return
        group = entry.get("group")
        if group == "chapter":
            self.unlocked_chapters.add(entry["chapter"])
        elif group in ("filler", "trap"):
            if deliver and self.bridge:
                self.bridge.queue_event("ITEM" if group == "filler" else "TRAP", entry["name"])
        else:
            self.received_counts[entry["name"]] = self.received_counts.get(entry["name"], 0) + 1

    # -- run state ---------------------------------------------------------

    @property
    def slot_identity(self) -> str:
        """`<seed>:<slot>`, what the game resets its run on. Empty while no
        slot is connected, which the game reads as no news."""
        if self.slot is None:
            return ""
        # `server_seed_name` is what RoomInfo reported; `seed_name` is only
        # set once a connection has been checked against it.
        return f"{self.server_seed_name or self.seed_name or ''}:{self.slot}"

    def forget_other_slot(self) -> None:
        """A different slot connected: drop what was learned about the last."""
        identity = self.slot_identity
        if identity == self.state_slot:
            return
        self.state_slot = identity
        self.completed.clear()
        self.goal_sent = False

    def sync_completed(self) -> None:
        """Finished chapters from the server's checked locations: a completion
        collected or released elsewhere counts as much as one played."""
        by_location = {v: k for k, v in self.complete_location.items()}
        self.completed |= {by_location[i] for i in self.checked_locations if i in by_location}

    def completed_in(self, campaign: str) -> int:
        finales = set(self.goal_chapters.values())
        return len([k for k in self.completed - finales
                    if self.campaign_of_chapter.get(k) == campaign])

    def seal_open(self, campaign: str) -> bool:
        # No seal known (no slot data yet) is a closed one, never an open one.
        if campaign not in self.missions_required_by_campaign:
            return False
        return self.completed_in(campaign) >= self.missions_required_by_campaign[campaign]

    @property
    def open_chapters(self) -> set[str]:
        chapters = set(self.unlocked_chapters)
        for campaign, finale in self.goal_chapters.items():
            if self.seal_open(campaign) and finale not in self.excluded_chapters:
                chapters.add(finale)
        return chapters

    @property
    def run_complete(self) -> bool:
        return all(goal in self.completed for goal in self.goal_chapters.values())

    @property
    def starting_classnames(self) -> list[str]:
        """Classnames of the starting items, which the game never takes away."""
        names = []
        for entry in self.campaign["items"]:
            if entry["name"] in self.starting_items:
                names += [c for c in entry.get("classnames", ()) if c.startswith("weapon_")]
        return names

    @property
    def held_items(self) -> set[str]:
        return set(self.received_counts)

    @property
    def counts(self) -> dict[str, int]:
        """Copies of the items that come in copies (the gravity gun stages)."""
        return {name: n for name, n in self.received_counts.items()
                if any(e["name"] == name and "count" in e for e in self.campaign["items"])}

    def print_chapters(self) -> None:
        for chapter in self.campaign["chapters"]:
            key = chapter["key"]
            if self.campaign_of_chapter.get(key) not in self.campaigns:
                continue
            if key in self.excluded_chapters:
                status = "not in this seed"
            elif key in self.completed:
                status = "complete"
            elif chapter["is_goal"]:
                owner = self.campaign_of_chapter[key]
                status = "OPEN" if self.seal_open(owner) else (
                    f"sealed ({self.completed_in(owner)}/"
                    f"{self.missions_required_by_campaign.get(owner, 0)})")
            elif key in self.unlocked_chapters:
                status = "unlocked"
            else:
                status = "locked"
            logger.info(f"  {chapter['number']:>3}. {chapter['name']:30} [{status}]")

    @staticmethod
    def print_in_game_commands() -> None:
        logger.info("In-game commands, in chat (press Y in Half-Life 2) or the console as `ap <name>`:")
        for command, description in IN_GAME_COMMANDS:
            logger.info(f"  {command:26} {description}")

    def clear_warp_saves(self) -> None:
        key = mod.warp_save_key(self.slot_identity)
        if key and self.mod_dir:
            try:
                removed = mod.clear_warp_saves(Path(self.mod_dir), key)
            except OSError as exc:
                logger.warning(f"Could not clear this run's warp saves ({exc}).")
                return
            if removed:
                logger.info(f"Cleared {removed} warp saves for this run.")

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = f"Archipelago {GAME_NAME} Client"
        return ui


def publish(ctx: HalfLife2Context, force: bool = False) -> None:
    if ctx.bridge is None:
        return
    ctx.bridge.write_snapshot(
        connected=ctx.server is not None and not ctx.server.socket.closed,
        chapters=sorted(ctx.open_chapters),
        items=sorted(ctx.held_items),
        death_link=ctx.death_link_enabled,
        death_link_amnesty=ctx.death_link_amnesty,
        excluded=sorted(ctx.excluded_chapters),
        starting=ctx.starting_classnames,
        counts=ctx.counts,
        checked=sorted(ctx.checked_locations),
        missing=sorted(ctx.missing_locations),
        options={"melee_throw": ctx.melee_throw},
        data_version=ctx.data_version,
        slot=ctx.slot_identity,
        force=force,
    )


def outgoing_chat(args: list[str]) -> dict | None:
    """The `Say` for a line of game chat (`CHAT|player|text`), or None."""
    text = args[1].strip() if len(args) > 1 else ""
    return {"cmd": "Say", "text": text} if text else None


async def pump(ctx: HalfLife2Context) -> None:
    """One poll: the game's events in, then the snapshot out."""
    if ctx.bridge is None:
        return
    try:
        events = ctx.bridge.read_events()
    except OSError as exc:
        logger.debug(f"bridge read failed: {exc}")
        events = []
    connected = ctx.server is not None and not ctx.server.socket.closed
    new_checks: list[int] = []
    for event in events:
        if event.kind == "CHECK":
            new_checks.append(int(event.arg))
        elif event.kind in ("COMPLETE", "GOAL"):
            ctx.completed.add(event.arg)
            if event.kind == "GOAL" and ctx.run_complete and not ctx.goal_sent and connected:
                ctx.goal_sent = True
                await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                logger.info("Goal complete!")
                ctx.clear_warp_saves()
        elif event.kind == "ACK":
            ctx.bridge.acknowledge(int(event.arg))
        elif event.kind == "DEATH":
            cause = event.args[1] if len(event.args) > 1 else "an unknown fate"
            forgiven = len(event.args) > 2 and event.args[2] == "1"
            if ctx.death_link_enabled and not forgiven and connected:
                await ctx.send_death(f"{ctx.player_names.get(ctx.slot, 'Freeman')} died to {cause}.")
        elif event.kind == "CHAT":
            if ctx.chat_relay and connected:
                say = outgoing_chat(event.args)
                if say:
                    await ctx.send_msgs([say])
        elif event.kind == "HELLO":
            logger.info(f"Game is on {event.arg}.")
            publish(ctx, force=True)
    if new_checks and connected:
        # The game fires every check checkdata knows; send only the seed's.
        in_seed = ctx.missing_locations | ctx.checked_locations
        unseen = [i for i in new_checks
                  if i not in ctx.checked_locations and (not in_seed or i in in_seed)]
        for location_id in unseen:
            logger.info(f"Check: {ctx.location_name_by_id.get(location_id, location_id)}")
        if unseen:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": unseen}])
    ctx.sync_completed()
    publish(ctx)


async def game_watcher(ctx: HalfLife2Context) -> None:
    """Pump the bridge forever. Nothing in here may raise: a dead watcher
    looks connected while the game silently receives nothing."""
    while not ctx.exit_event.is_set():
        await asyncio.sleep(POLL_INTERVAL)
        if ctx.bridge is None:
            continue
        try:
            await pump(ctx)
        except Exception as exc:  # noqa: BLE001
            ctx.bridge_failures += 1
            if ctx.bridge_failures in (1, 10, 100):
                logger.warning(f"Bridge error ({ctx.bridge_failures}): {exc}")
        else:
            if ctx.bridge_failures:
                logger.info("Bridge recovered.")
                ctx.bridge_failures = 0


async def main(args) -> None:
    ctx = HalfLife2Context(args.connect, args.password, args.moddir)
    if getattr(args, "name", None):
        ctx.username = args.name
    ctx.server_task = asyncio.create_task(server_loop(ctx), name="ServerLoop")
    if TRACKER_LOADED:
        ctx.run_generator()
    if gui_enabled:
        ctx.run_gui()
    ctx.run_cli()
    watcher = asyncio.create_task(game_watcher(ctx), name="GameWatcher")
    await ctx.exit_event.wait()
    watcher.cancel()
    await ctx.shutdown()


def launch(*args: str) -> None:
    parser = get_base_parser(description="Half-Life 2 Archipelago client")
    parser.add_argument("--moddir", default="", help="the installed hl2ap mod folder")
    parser.add_argument("url", nargs="?", help="Archipelago connection URI")
    parsed = parser.parse_args(args)
    # `archipelago://name:password@host:port`, from the Launcher or a link.
    parsed = handle_url_arg(parsed, parser=parser)
    Utils.init_logging("HalfLife2Client", exception_logger="Client")
    asyncio.run(main(parsed))


if __name__ == "__main__":
    launch(*sys.argv[1:])
