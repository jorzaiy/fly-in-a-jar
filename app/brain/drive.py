"""How hard the swarm presses on the fly brain this turn (design §5.3, swarm input).

The swarm sleeps until the power comes back. From then on it grows restless
turn by turn, and louder as the player's sync rises. Sugar or a fire wall
holds it back, CO2 stuns it, and a caught fly on the player (one of its own)
calms it. The result is a rate in Hz for the swarm channels of
`BrainGroups.build_stimulus`; the giant-fibre readout then decides whether it
approaches or attacks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:  # engine imports brain; avoid the cycle
    from app.engine.state import GameState


def swarm_drive(state: "GameState", cfg: Mapping[str, Any]) -> float:
    sw = cfg.get("swarm", {})
    if not state.has_flag("power_on"):
        hz = float(sw.get("dormant_hz", 0.0))
    else:
        since = max(0, state.turn - state.power_turn)
        hz = float(sw.get("wake_hz", 30.0)) + float(sw.get("ramp_hz_per_turn", 3.0)) * min(
            since, int(sw.get("ramp_turns_max", 12)))
    if hz <= 0:
        return 0.0
    hz += float(sw.get("sync_hz_per_point", 0.3)) * state.sync
    if state.monster_stunned > 0:
        hz *= float(sw.get("stunned_factor", 0.1))
    elif state.monster_block > 0:
        hz *= float(sw.get("block_factor", 0.2))
    if "vial_fly" in state.items or state.caught_fly:
        hz *= float(sw.get("own_fly_factor", 0.6))
    return round(hz, 1)
