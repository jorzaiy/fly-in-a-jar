"""Turn execution orchestrator (tasks.md 12.1 & design §4).

Connects the full 10-step turn loop:
1. Validate & check ended
2. Handle system commands (cost 0 turns)
3. Fixed server terminal Q&A (when in server_room with power)
4. Neuro-hijack check (at sync >= 70% using last_spikes)
5. Call judge (Jev or mock) with safe timeout
6. Resolve turn effects & state updates (rules.py)
7. Update sensory feeding fatigue & build connectome stimulus
8. Run LIF simulation on connectome & record last_spikes
9. Derive story elements & assemble narrative fragments
10. Check endings and return {state, output, ended}
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import logging
from typing import Any

from app.brain.groups import BrainGroups
from app.brain.lif import LIFSimulator, derive_seed
from app.content.loader import Content, World
from app.content.schema import HIJACK_KEYS, TARGET_NONE, tier_for_sync
from app.engine.commands import run_command
from app.engine.rules import RulesConfig, load_rules_config, resolve_turn
from app.engine.state import GameState
from app.judge.base import Judge, JudgeCall, JudgeResult, safe_judge
from app.narrator.compose import compose_turn, resolve_fragment_text
from app.narrator.elements import StoryElements, derive_story_elements
from app.narrator.select import select_fragment

log = logging.getLogger("fly.engine.turn")


@dataclass
class TurnResult:
    """The outcome of a turn sent back to client."""

    state: GameState
    output: list[dict[str, str]]
    ended: str | None = None
    is_system_command: bool = False
    trace: dict = field(default_factory=dict)


def check_server_terminal(state: GameState, text: str, lang: str) -> list[dict[str, str]] | None:
    """Fixed terminal Q&A when in server_room with power (story ch. 5.4 & tasks.md 9.7)."""
    if state.scene != "server_room" or not state.has_flag("power_on"):
        return None

    cleaned = text.strip().lower()

    if cleaned == "status":
        host_name = "You" if state.sync >= 50 else "Human_Host_02"
        if lang == "zh":
            msg = (
                f"[机房终端] 进程监控:\n"
                f"  PID 001: FlyWire_v783_LIF [RUNNING]\n"
                f"  PID 002: Swarm_Coordination [RUNNING]\n"
                f"  PID 003: {host_name} (突触连接率: {state.sync}%)\n"
                f"  系统告警: 神经载体已被锁定，请勿强行断开连接。"
            )
        else:
            msg = (
                f"[TERMINAL] Active processes:\n"
                f"  PID 001: FlyWire_v783_LIF [RUNNING]\n"
                f"  PID 002: Swarm_Coordination [RUNNING]\n"
                f"  PID 003: {host_name} (Sync: {state.sync}%)\n"
                f"  SYSTEM ALERT: Neural substrate locked to host. Do not disconnect."
            )
        return [{"kind": "system", "text": msg}]

    if cleaned in ("kill -9 specimen_f", "kill specimen_f", "kill -9 specimen-f"):
        if lang == "zh":
            msg = "[机房终端] 权限被拒绝: 你无法终止自己正在运行的进程。"
        else:
            msg = "[TERMINAL] Permission denied: You cannot terminate the process you are running on."
        return [{"kind": "system", "text": msg}]

    if cleaned in ("stimulate pam", "stimulate_pam"):
        state.sync = min(100, state.sync + 15)
        state.monster_block = max(state.monster_block, 2)
        if lang == "zh":
            msg = (
                "[机房终端] PAM 多巴胺刺激已注入。门外的人形蜂群发出愉悦而剧烈的震颤，"
                "本能地退散开来，在通道中让出了一条路。（同化率 +15%）"
            )
        else:
            msg = (
                "[TERMINAL] PAM dopamine stimulus injected. A violent, pleasurable tremor "
                "ripples through the swarm outside as it parts, clearing a passage. (Sync +15%)"
            )
        return [{"kind": "system", "text": msg}]

    return None


def roll_hijack(state: GameState, cfg: RulesConfig) -> str | None:
    """Determine if player action is hijacked by insect instinct (design §4 step 3).

    Only triggers at sync >= 70%. Uses last_spikes and deterministic seed roll.
    """
    if state.sync < cfg.hijack_sync_min or not state.last_spikes:
        return None

    # Probability increases from 15% at 70 sync to 70% at 100 sync
    p_hijack = 0.15 + (state.sync - cfg.hijack_sync_min) / 30.0 * 0.55

    # Deterministic roll using turn seed
    token = f"hijack:{state.seed}:{state.turn}:{state.sync}".encode()
    digest = hashlib.sha256(token).digest()
    roll_val = int.from_bytes(digest[:4], "big") / (2**32)

    if roll_val >= p_hijack:
        return None

    # Pick instinct based on which neural readout spiked strongest in last turn
    spk = state.last_spikes
    feed_spk = spk.get("monster.feed", 0)
    attack_spk = spk.get("monster.attack", 0)
    retreat_spk = spk.get("monster.retreat", 0)

    if feed_spk >= attack_spk and feed_spk >= retreat_spk and feed_spk > 0:
        return "eat"
    elif attack_spk >= retreat_spk and attack_spk > 0:
        return "flinch"
    else:
        return "freeze"


def update_feeding_fatigue(action_text: str, state: GameState, brain_groups: BrainGroups) -> None:
    """Track consecutive usage of sensory feeding pathways (design §5.3 & tasks.md 9.5)."""
    lower = action_text.lower()
    used_pathway: str | None = None

    for kw, rule in brain_groups.feeding_rules.items():
        if kw in lower:
            used_pathway = rule["pathway"]
            break

    if used_pathway:
        # Increment fatigue for used pathway
        state.stim_fatigue[used_pathway] = state.stim_fatigue.get(used_pathway, 0) + 1
        # Clear fatigue for other pathways
        for p in list(state.stim_fatigue.keys()):
            if p != used_pathway:
                del state.stim_fatigue[p]
    else:
        # If no feeding keyword used, clear or decay fatigue
        state.stim_fatigue.clear()


async def execute_turn(
    state: GameState,
    player_input: str,
    world: World,
    content: Content,
    judge: Judge,
    brain_groups: BrainGroups,
    simulator: LIFSimulator,
    cfg: RulesConfig | None = None,
) -> TurnResult:
    """Execute one full turn of Fly in a Jar."""
    cfg = cfg or load_rules_config()
    lang = state.lang

    # 1. Check if game already ended
    if state.ended is not None:
        return TurnResult(
            state=state,
            output=[{"kind": "system", "text": content.text("errors.already_ended", lang)}],
            ended=state.ended,
        )

    # 2. Fixed server terminal Q&A (in server_room with power, catches 'status', 'kill -9', etc.)
    terminal_out = check_server_terminal(state, player_input, lang)
    if terminal_out:
        return TurnResult(state=state, output=terminal_out, ended=state.ended, is_system_command=True)

    # 3. Check system commands (cost 0 turns)
    cmd_out = run_command(state, player_input, content)
    if cmd_out is not None:
        return TurnResult(
            state=state,
            output=cmd_out.output,
            ended=state.ended,
            is_system_command=True,
        )

    # 4. Neuro-hijack check (sync >= 70%)
    hijacked_instinct = roll_hijack(state, cfg)
    effective_input = player_input
    if hijacked_instinct:
        # Override action with instinct
        if hijacked_instinct == "eat":
            effective_input = "eat"
        elif hijacked_instinct == "flinch":
            effective_input = "hide"
        else:
            effective_input = "wait"

    # 5. Call Judge (with safe_judge hard timeout)
    judge_call = await safe_judge(judge, state, world, effective_input, timeout_s=cfg.judge_timeout_s)

    if not judge_call.ok or judge_call.result is None:
        # Judge timed out or failed: state remains untouched, no sync penalty (design §14)
        from app.judge.base import silent_output
        return TurnResult(
            state=state,
            output=silent_output(lang, content),
            ended=state.ended,
            trace={"hijack": hijacked_instinct, "judge_ok": False, "judge_error": judge_call.error, "judge_ms": judge_call.ms},
        )

    j_res = judge_call.result

    # 6. Resolve turn effects on state (advances turn, applies move/take/use/fail sync)
    action_outcome = resolve_turn(
        state,
        world,
        feasible=j_res.feasible,
        reason=j_res.reason,
        category=j_res.category,
        target=j_res.target,
        danger=j_res.danger,
        cfg=cfg,
    )

    # 7. Update sensory feeding fatigue
    update_feeding_fatigue(player_input, state, brain_groups)

    # 8. Build stimulus and run connectome LIF simulation
    stimulus = brain_groups.build_stimulus(
        category=j_res.category,
        action_text=player_input,
        scene=state.scene,
        danger=j_res.danger,
        stim_fatigue=state.stim_fatigue,
    )
    sim_seed = derive_seed(state.seed, state.turn)
    sim_res = simulator.simulate(stimulus, seed=sim_seed)

    # 9. Derive story elements & save last_spikes
    elements = derive_story_elements(sim_res, brain_groups, state, world)
    state.last_spikes = dict(elements.spikes)

    # 10. Assemble turn narrative output
    output = compose_turn(
        elements=elements,
        judge_call=judge_call,
        state=state,
        world=world,
        content=content,
        rule_triggered=action_outcome.rule_id,
        rule_clue_id=action_outcome.clue,
        hijacked_action=hijacked_instinct,
        moved_scene=action_outcome.moved_to,
        took=action_outcome.took,
        target=j_res.target,
        lang=lang,
    )

    # 11. Check ending and attach ending fragment if ended
    if state.ended:
        ending_frag = select_fragment("ending", state.ended, elements.intensity, state, content, sim_res.total_spikes)
        ending_text = resolve_fragment_text(ending_frag, state, lang, j_res.target, world, content)
        output.append({"kind": "ending", "text": ending_text})

    trace = {
        "hijack": hijacked_instinct,
        "judge_ok": True,
        "judge_ms": judge_call.ms,
        "judge": j_res.model_dump(),
        "rule": action_outcome.rule_id,
        "moved_to": action_outcome.moved_to,
        "took": action_outcome.took,
        "clue": action_outcome.clue,
        "spikes": sim_res.total_spikes,
        "intensity": elements.intensity,
    }
    return TurnResult(state=state, output=output, ended=state.ended, trace=trace)
