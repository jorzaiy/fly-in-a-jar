# Fly in a Jar 缸中之蝇

> Every scare is decided by the real neurons of a fruit fly's connectome. Jev judges what you can do. The longer you play, the less "you" there is.

A browser-playable, bilingual (English / 中文) text horror game. **Entry for [Kiroween 2026](https://kiroween.devpost.com/), category: Frankenstein.**

🚧 Work in progress. The content pipeline, game state, rules engine and judge layer are in place; the brain simulator, narrator, turn API and terminal front end are still being built (see [`tasks.md`](.kiro/specs/fly-brain-horror/tasks.md)).

## Why Frankenstein

The Frankenstein category asks for *"a chimera of technologies… seemingly incompatible elements"* stitched into one app. Fly in a Jar stitches together three parts that were never meant to meet:

1. **A real connectome simulation.** A leaky integrate-and-fire model runs on the FlyWire v783 adult fruit fly brain (~139k neurons), with parameters from Shiu et al. 2024. Spikes in real, named neuron groups decide what the swarm does, which anomaly appears, and when a clue surfaces.
2. **A decision model that never writes.** [Jev](https://typesafe.ai), TypeSafe AI's structured decision model, judges whether your free-text action is possible: feasibility probability, failure reason, action category, target and danger. It returns typed answers, never prose.
3. **A pre-written fragment library.** Every word of the story comes from hand-curated bilingual fragments. No language model generates text at runtime.

A neuroscience dataset, a typed AI judge and a hand-written horror script. The fly brain is the storyteller, Jev is the referee, and the fragments are the stitches.

## Gameplay

It is midnight. You are the last research assistant on night shift at a neuro-imaging institute that sliced one fruit fly brain into 7,000 sections and rebuilt every neuron. The power is out, the doors are locked, and something in the building is thinking with that fly's brain.

- **Free-text actions** in a fake terminal: `open the freezer`, `light the ethanol`, `listen at the door`. System commands (`help`, `look`, `status`, `inventory`, `notes`, `lang`, `brainlog`, `restart`) cost no turn.
- **Synaptic Sync** replaces sanity and runs the other way: bad things push it up. 0–30% you see as a human, 31–69% your senses split into compound-eye facets, 70–99% instinct takes over. At 100% the swarm has you.
- **Sensory feeding**: some actions push a neural pathway harder (tapping, sugar, strobing), with fatigue if you repeat them. The connectome still decides the outcome.
- **Neuro-hijack**: at high sync, last turn's spikes can replace your action with an instinct (eat, flinch, freeze).
- **Brain log**: after each turn the terminal shows which FlyWire cell types were stimulated, how many spikes each readout group fired, and what that decided, so you can see the story come from neural activity.
- **Four endings**: escaped, consumed, absorbed (hidden), disconnected.
- A run is designed for 25–40 turns (about 15–25 minutes).

## Architecture

```
Browser (hand-written HTML terminal)
   │  one POST per turn, carrying the full game state
   ▼
FastAPI (single process, Docker)
   ├─ api/        routes, validation, rate limiting
   ├─ engine/     turn flow: command → hijack → judge → state → simulate → narrate
   ├─ judge/      Jev judge + offline keyword mock judge
   ├─ brain/      numpy LIF simulator (process pool, connectome loaded once per worker)
   ├─ narrator/   spikes → story elements → fragment selection and assembly
   └─ content/    world, fragment library and UI text: loading and validation
```

One turn, in order: validate input → system command? → neuro-hijack roll (uses last turn's spikes) → Jev verdict → apply effects and sync → build stimulus (action category, sensory feeding, scene ambience, danger) → LIF simulation → spikes to story elements → monster rule overrides → assemble fragments by sync tier → check endings.

Design constraints:

- **Stateless server.** The game state lives in the browser (`localStorage`, ≤16 KB) and is sent with every turn.
- **Reproducible.** The Poisson seed is `hash(game seed, turn)`, and fragments are picked by `spike count mod candidates`, not `random`. The same seed and inputs replay the same game.
- **The judge can fail safely.** If Jev times out, the game says the judge is silent, and state and sync stay unchanged.

Full design: [`design.md`](.kiro/specs/fly-brain-horror/design.md).

## How Kiro was used

The `.kiro/` directory at the repo root is part of the submission.

### Spec-driven development: `.kiro/specs/fly-brain-horror/`

| File | Role |
|------|------|
| [`requirements.md`](.kiro/specs/fly-brain-horror/requirements.md) | 11 requirements, each with a user story and numbered acceptance criteria (terminal, bilingual, brain engine, spikes → story, fragment format, Jev judge, brain log, game loop, strong interaction, deployment, submission) |
| [`design.md`](.kiro/specs/fly-brain-horror/design.md) | Architecture, key decisions with rejected alternatives, turn flow, stimulus and readout maps, judge questions and thresholds, state schema, API |
| [`tasks.md`](.kiro/specs/fly-brain-horror/tasks.md) | Phased implementation plan; each task links back to the requirement numbers it satisfies, and checkboxes are only ticked once verified |
| [`story.md`](.kiro/specs/fly-brain-horror/story.md), [`fragment-guide.md`](.kiro/specs/fly-brain-horror/fragment-guide.md) | The script, and the fragment format and writing prompt; the validator enforces the guide's rules |
| [`research.md`](.kiro/specs/fly-brain-horror/research.md), [`kiroween-rules.md`](.kiro/specs/fly-brain-horror/kiroween-rules.md) | Prior-art survey and the verified 2026 hackathon rules |

The specs are written in Chinese; code, comments and this README are in English. Commits are small slices of `tasks.md`, and code comments cite the design section they implement (for example `design §6.3`).

### Steering: `.kiro/steering/`

| File | Inclusion | What it tells Kiro |
|------|-----------|--------------------|
| [`product.md`](.kiro/steering/product.md) | always | What the game is, the fly-brain / Jev split, and the rule that no LLM writes text at runtime |
| [`tech.md`](.kiro/steering/tech.md) | always | Pinned stack, hard constraints (stateless, reproducible, key handling, data size), and the commands to run |
| [`structure.md`](.kiro/steering/structure.md) | always | Repo layout, the shared vocabulary in `app/content/schema.py`, doc languages, and how `tasks.md` is ticked |
| [`content-fragments.md`](.kiro/steering/content-fragments.md) | fileMatch: `content/**/*.yaml`, content and narrator code | Fragment format rules, coverage targets (MVP and full), and the rule that the placeholder fragments are not to be replaced with invented prose |

### Hooks: `.kiro/hooks/`

| File | Trigger | Action |
|------|---------|--------|
| [`validate-content.json`](.kiro/hooks/validate-content.json) | `PostFileSave` on `content/fragments/*.yaml`, `world.yaml`, `ui.yaml` | Runs `python -m content.validate --quiet`; errors name the bad fragment ids |
| [`run-tests.json`](.kiro/hooks/run-tests.json) | `PostFileSave` on `app/`, `content/`, `tests/` Python files | Runs `pytest -q -x` |
| [`sync-tasks.json`](.kiro/hooks/sync-tasks.json) | `PostTaskExec` | Asks the agent to update `tasks.md` checkboxes honestly (no ticking 👤 or untested deploy tasks) |

> **TODO (zoey):** add your own Kiro workflow notes here: which Kiro surfaces you used (IDE / CLI / Web), vibe-coding sessions vs. spec-driven tasks, how steering changed Kiro's answers, and anything that surprised you. The judges ask for this specifically.

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: add TYPESAFE_API_KEY, otherwise JUDGE=mock
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/api/health
```

Checks:

```bash
pip install -r requirements-dev.txt   # adds pytest and httpx
python -m pytest -q                   # test suite
python -m content.validate            # content errors + coverage tables (must be 0 errors)
python -m content.validate --mvp      # also fail below the MVP fragment coverage target
```

The server refuses to start if the content does not validate, and it lists every bad fragment id.

## Data & credits

Connectome data: FlyWire (FAFB v783). Licence to be confirmed before redistribution; see `data/DATA_LICENSE.md` once added.

- Dorkenwald et al., *Neuronal wiring diagram of an adult brain*, Nature 2024
- Schlegel et al., *Whole-brain annotation and multi-connectome cell typing of Drosophila*, Nature 2024
- Shiu et al., *A Drosophila computational brain model reveals sensorimotor processing*, Nature 2024

## License

Code: MIT (see [LICENSE](LICENSE)). Data keeps its original licence.
