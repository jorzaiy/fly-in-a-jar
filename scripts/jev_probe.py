"""Jev probe script (tasks.md 2.1 & 2.4).

Sends test actions to TypeSafe AI's Jev model using the official `typesafe-sdk`,
validating the request shape, response schema, and Chinese/English action handling.

Usage:
    export TYPESAFE_API_KEY=your_key_here
    python scripts/jev_probe.py [--action "open drawer and take flashlight"]
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
from typesafe_sdk import TypeSafeAPIError

FIXED_STATE = """You are at reception. Exits: corridor. Visible items: flashlight (inside drawer), visitor_log (on desk), desk_phone (on desk). Inventory: empty. Monster status: absent. Synaptic sync: 0%. World rules: power is out; electronic doors require keycard and power; glass cannot be broken with paper books."""

DEFAULT_TARGETS = [
    "corridor",
    "flashlight",
    "revolving_door",
    "visitor_log",
    "desk_phone",
    "reception_desk",
    "monster",
    "none",
]

TEST_ACTIONS_EN = [
    "open drawer and take flashlight",
    "smash revolving door glass with the visitor log",
    "pick up desk phone and call security",
    "fly out the window",
    "go to the corridor",
]

TEST_ACTIONS_ZH = [
    "打开抽屉拿手电筒",
    "用登记簿砸碎旋转门玻璃",
    "拿起内线电话打给保安",
    "飞出窗外",
    "前往走廊",
]


def build_questions(targets: list[str]) -> dict:
    return {
        "feasible": Noul(
            instructions="Can the player perform this action now, given scene, inventory, and world rules?"
        ),
        "reason": Choice(
            instructions="If the action cannot be performed, why not? Pick 'feasible' if it can.",
            criteria={
                "physically_impossible": None,
                "missing_item": None,
                "no_such_target": None,
                "against_world_rules": None,
                "not_an_action": None,
                "feasible": None,
            },
        ),
        "category": Choice(
            instructions="What kind of action is this?",
            criteria={
                "look": None,
                "move": None,
                "take": None,
                "use": None,
                "eat": None,
                "smell": None,
                "listen": None,
                "touch": None,
                "light": None,
                "attack": None,
                "hide": None,
                "wait": None,
                "talk": None,
                "other": None,
            },
        ),
        "target": Choice(
            instructions="What does the action act on? Use 'monster' for swarm and 'none' if nothing specific.",
            criteria={t: None for t in targets},
        ),
        "danger": Score(
            instructions="How dangerous is this action for the player?",
            criteria=["safe", "risky", "dangerous", "suicidal"],
        ),
    }


def probe_single_action(client: TypeSafeClient, action: str, targets: list[str]) -> dict:
    state_payload = {"environment": FIXED_STATE, "player_action": action}
    questions = build_questions(targets)

    response = client.system_one(state=state_payload, questions=questions)

    # Format answers
    answers = {}
    for q_id, ans in response.answers.items():
        if hasattr(ans, "noul"):
            answers[q_id] = {"type": "noul", "value": round(ans.noul, 4)}
        elif hasattr(ans, "choice"):
            answers[q_id] = {
                "type": "choice",
                "choice": ans.choice,
                "confidence": round(getattr(ans, "confidence", 1.0), 4),
            }
        elif hasattr(ans, "score"):
            answers[q_id] = {
                "type": "score",
                "score": ans.score,
                "label": ans.legend[ans.score] if hasattr(ans, "legend") and ans.legend else ans.score,
            }
        else:
            answers[q_id] = str(ans)

    return {
        "action": action,
        "answers": answers,
        "usage": {
            "total_tokens": getattr(response.usage, "total_tokens", None) if hasattr(response, "usage") else None
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe TypeSafe AI Jev decision model.")
    parser.add_argument("--action", type=str, help="Single action to test")
    parser.add_argument("--all", action="store_true", help="Run full test suite (5 EN + 5 ZH actions)")
    args = parser.parse_args()

    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        print("[ERROR] TYPESAFE_API_KEY environment variable is not set.")
        print("Please set it via: export TYPESAFE_API_KEY=your_key")
        sys.exit(1)

    print("=== Initializing TypeSafeClient ===")
    with TypeSafeClient() as client:
        if args.action:
            actions = [args.action]
        elif args.all:
            actions = TEST_ACTIONS_EN + TEST_ACTIONS_ZH
        else:
            actions = [TEST_ACTIONS_EN[0]]

        for i, action in enumerate(actions, 1):
            print(f"\n--- [{i}/{len(actions)}] Action: {action!r} ---")
            try:
                result = probe_single_action(client, action, DEFAULT_TARGETS)
                print(json.dumps(result, indent=2, ensure_ascii=False))
            except TypeSafeAPIError as e:
                print(f"[API ERROR] {e}")
            except Exception as e:
                print(f"[ERROR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
