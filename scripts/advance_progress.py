#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROGRESS_FILE = ROOT / "data" / "progress.json"
STORY_FILE = ROOT / "outputs" / "thechessstuff_storyboard.json"

def main():
    progress = json.loads(PROGRESS_FILE.read_text(encoding="utf-8")) if PROGRESS_FILE.exists() else {}
    story = json.loads(STORY_FILE.read_text(encoding="utf-8")) if STORY_FILE.exists() else {}
    
    current_offset = int(progress.get("next_offset", 0))
    current_diff = story.get("difficulty", progress.get("difficulty", "easy")).lower()
    
    next_offset = current_offset + 1
    
    progress["next_offset"] = next_offset
    progress["last_puzzle_id"] = story.get("puzzle_id")
    progress["last_title"] = story.get("title")
    
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2) + "\n", encoding="utf-8")
    print(f"Advanced Progress -> Puzzle Offset: {next_offset}")
    print(json.dumps(progress, indent=2))

if __name__ == "__main__":
    main()
