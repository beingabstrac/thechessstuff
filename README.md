# thechessstuff

Automated daily Chess.com puzzle reel renderer and Instagram publisher matching the official Chess.com visual animation style (Green board, Neo pieces, move badges, smooth sliding piece animations, checkmate confetti particle FX, TTS voiceover narration, and chess SFX).

## Quick Start

Run:

```bash
python3 -m pip install -r requirements.txt
./scripts/render.sh
```

Output:

```text
outputs/thechessstuff_mvp.mp4
```

Render a specific date or puzzle ID:

```bash
CHESS_DATE=2026-07-27 ./scripts/render.sh
```

Advance progress (old-to-new / difficulty rotation):

```bash
python3 scripts/advance_progress.py
```
