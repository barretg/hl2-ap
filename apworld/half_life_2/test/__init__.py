"""World tests. They run under an Archipelago source checkout with the world
linked into `worlds/` (`pytest worlds/half_life_2/test`), and are left out of
the packaged .apworld."""

from test.bases import WorldTestBase

from .. import GAME_NAME


class HalfLife2TestBase(WorldTestBase):
    game = GAME_NAME
    player: int = 1
