# Fly in a Jar 缸中之蝇

> Every scare is decided by the real neurons of a fruit fly's connectome. Jev judges what you can do. The longer you play, the less "you" there is.

A browser-playable text horror game for **Kiroween 2026**.

- **The story** is chosen by a leaky integrate-and-fire simulation of the real adult fruit fly brain (FlyWire connectome v783, ~139k neurons). Spikes in real neuron groups decide what the swarm does, which anomaly appears and when a clue surfaces.
- **The judge** is [Jev](https://typesafe.ai), TypeSafe AI's structured decision model. It decides whether your free-text action is possible. It never writes text.

🚧 Work in progress. Design docs live in [`.kiro/specs/fly-brain-horror/`](.kiro/specs/fly-brain-horror/).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional: add TYPESAFE_API_KEY
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/api/health
```

## Data & credits

Connectome data: FlyWire (FAFB v783). Licence to be confirmed before redistribution; see `data/DATA_LICENSE.md` once added.

- Dorkenwald et al., *Neuronal wiring diagram of an adult brain*, Nature 2024
- Schlegel et al., *Whole-brain annotation and multi-connectome cell typing of Drosophila*, Nature 2024
- Shiu et al., *A Drosophila computational brain model reveals sensorimotor processing*, Nature 2024

## License

Code: MIT (see [LICENSE](LICENSE)). Data keeps its original licence.
