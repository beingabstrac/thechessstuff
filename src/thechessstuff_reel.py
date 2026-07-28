#!/usr/bin/env python3
import asyncio
import hashlib
import html
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import wave
import struct
from array import array
from datetime import datetime, timedelta, date, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPS_VENV = ROOT / ".deps" / "venv"
if DEPS_VENV.exists():
    for site_pkg in DEPS_VENV.glob("lib/python*/site-packages"):
        if str(site_pkg) not in sys.path:
            sys.path.insert(0, str(site_pkg))

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import chess
import chess.pgn

OUT = ROOT / "outputs"
VIDEO_OUT = OUT / "thechessstuff_mvp.mp4"
STORY_OUT = OUT / "thechessstuff_storyboard.json"
DATA_DIR = ROOT / "data"
PROGRESS_FILE = DATA_DIR / "progress.json"
PUZZLES_FILE = DATA_DIR / "puzzles.json"
FONTS_DIR = ROOT / "assets" / "fonts"
PIECES_DIR = ROOT / "assets" / "pieces"
BADGES_DIR = ROOT / "assets" / "badges"
SOUNDS_DIR = ROOT / "assets" / "sounds"

W, H = 1080, 1920
FPS = 30

# Colors (Exact Chess.com #312E2B Dark Theme & Green Board)
COLOR_BG = (49, 46, 43)                     # Pure #312E2B
COLOR_CARD = (38, 35, 33)
COLOR_SQUARE_LIGHT = (238, 238, 210)        # Chess.com light square #EEEEE2
COLOR_SQUARE_DARK = (118, 150, 86)          # Chess.com dark square #769656
COLOR_HIGHLIGHT_ORIG = (247, 247, 105, 180)  # Move origin yellow highlight
COLOR_HIGHLIGHT_DEST = (186, 202, 68, 220)   # Move target green highlight
COLOR_RED_CHECK = (224, 56, 56, 255)         # Solid Chess.com Red Checkmate King square highlight #E03838
COLOR_TEXT = (255, 255, 255)
COLOR_MUTED = (160, 170, 185)
COLOR_ACCENT = (118, 187, 72)               # Chess.com Green accent #76BB48

EDGE_VOICES = [
    "en-US-AndrewNeural",
    "en-US-BrianNeural",
    "en-US-AvaNeural",
    "en-US-EmmaNeural",
]

def ensure_inter_fonts():
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    bold_path = FONTS_DIR / "Inter-Bold.ttf"
    reg_path = FONTS_DIR / "Inter-Regular.ttf"
    if bold_path.exists() and reg_path.exists() and bold_path.stat().st_size > 0:
        return
    try:
        css_url = "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap"
        req = urllib.request.Request(css_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            css = resp.read().decode("utf-8")
        ttf_urls = re.findall(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", css)
        if len(ttf_urls) >= 2:
            urllib.request.urlretrieve(ttf_urls[0], reg_path)
            urllib.request.urlretrieve(ttf_urls[1], bold_path)
    except Exception:
        pass

ensure_inter_fonts()

def font(size, bold=False):
    chess_sans = FONTS_DIR / "ChessSans-Bold.ttf"
    if chess_sans.exists():
        try:
            return ImageFont.truetype(str(chess_sans), size)
        except Exception:
            pass
    target = FONTS_DIR / ("Inter-Bold.ttf" if bold else "Inter-Regular.ttf")
    if target.exists():
        try:
            return ImageFont.truetype(str(target), size)
        except Exception:
            pass
    for cand in ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"]:
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                pass
    return ImageFont.load_default()

def load_progress():
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"next_offset": 0, "difficulty": "easy"}

def fetch_chess_com_puzzle():
    for endpoint in ["https://api.chess.com/pub/puzzle/random", "https://api.chess.com/pub/puzzle"]:
        try:
            req = urllib.request.Request(
                endpoint,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and "fen" in data and "pgn" in data:
                    return data
        except Exception as e:
            print(f"Notice: Chess.com API {endpoint} ({e})")
    return None

def speakable_square(sq_name):
    if len(sq_name) == 2:
        return f"{sq_name[0]} {sq_name[1]}"
    return sq_name

def generate_human_narration(fen, solution_moves):
    b = chess.Board(fen)
    turn_str = "White" if b.turn == chess.WHITE else "Black"
    opp_str = "Black" if b.turn == chess.WHITE else "White"
    
    # 1. Realistic Human Player Openers (Hooking & Natural)
    opener_hooks = [
        f"Wait, {opp_str} left their position open here... Can you spot the win?",
        f"Okay, look at this position... {opp_str} thinks they're fine, but they're not.",
        f"Hold on, {turn_str} has a crazy winning sequence right here! Can you find it?",
        f"Wait, can {turn_str} just force a win here? Take a look!"
    ]
    opener = random.choice(opener_hooks)
    
    steps = []
    curr_b = b.copy()
    
    for idx, move_item in enumerate(solution_moves):
        move = None
        if isinstance(move_item, str):
            try:
                move = curr_b.parse_uci(move_item)
            except Exception:
                try:
                    move = curr_b.parse_san(move_item)
                except Exception:
                    pass
        
        if not move:
            steps.append(f"And then {move_item}.")
            continue

        is_capture = curr_b.is_capture(move)
        piece = curr_b.piece_at(move.from_square)
        from_name = chess.square_name(move.from_square)
        to_name = chess.square_name(move.to_square)
        to_sp = speakable_square(to_name)
        
        p_type = piece.piece_type if piece else chess.PAWN
        
        if p_type == chess.QUEEN:
            p_name = "the queen"
        elif p_type == chess.ROOK:
            p_name = "the rook"
        elif p_type == chess.BISHOP:
            p_name = "the bishop"
        elif p_type == chess.KNIGHT:
            p_name = "the knight"
        elif p_type == chess.KING:
            p_name = "the king"
        else:
            file_char = from_name[0].upper()
            p_name = f"the {file_char}-pawn"

        temp_b = curr_b.copy()
        temp_b.push(move)
        is_mate = temp_b.is_checkmate()
        is_check = temp_b.is_check()
        is_last = (idx == len(solution_moves) - 1)
        is_my_turn = (curr_b.turn == b.turn)

        if is_mate or is_last:
            if is_my_turn:
                if is_capture:
                    m_text = f"And we just take on {to_sp} with {p_name} for the win!"
                else:
                    m_text = f"And {p_name} to {to_sp} finishes the game!"
            else:
                m_text = f"They step to {to_sp}, but it's completely winning for us."
        elif idx == 0:
            if is_capture:
                m_text = f"First, we take on {to_sp} with {p_name}."
            elif p_type == chess.KNIGHT:
                m_text = f"First, we hop {p_name} to {to_sp}."
            elif p_type == chess.PAWN:
                m_text = f"First, we push {p_name} to {to_sp}."
            else:
                m_text = f"First, we bring {p_name} to {to_sp}."
        else:
            if is_my_turn:
                if is_capture:
                    m_text = f"Then we capture on {to_sp} with {p_name}!"
                elif is_check:
                    m_text = f"Now we check them on {to_sp} with {p_name}!"
                else:
                    m_text = f"Next, we slide {p_name} to {to_sp}."
            else:
                if is_capture:
                    m_text = f"They capture back on {to_sp}..."
                elif is_check:
                    m_text = f"They check us on {to_sp}..."
                else:
                    m_text = f"They step to {to_sp}..."
                
        steps.append(m_text)
        curr_b.push(move)

    outro_choices = [
        "What a clean tactical sequence!",
        "That is how you punish a weak position!",
        "Spotting those moves makes all the difference!",
        "Beautiful tactic!"
    ]
    outro = random.choice(outro_choices)
    return [opener] + steps, outro

HISTORICAL_PUZZLES_FILE = DATA_DIR / "historical_puzzles.json"
START_DATE = date(2007, 5, 8)

def format_pretty_date(d):
    return d.strftime("%B %d, %Y").replace(" 0", " ")

def fetch_historical_puzzle(target_date_str, fallback_index=0):
    parts = target_date_str.split('-')
    year, month = parts[0], parts[1]
    url = f"https://raw.githubusercontent.com/samuraitruong/chess.com-daily-puzzle/main/puzzle/{year}/{year}-{month}.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for item in data:
                if item.get("date") == target_date_str or (item.get("url") and target_date_str in item.get("url")):
                    return item
            if data and fallback_index < len(data):
                return data[fallback_index]
    except Exception as e:
        print(f"Notice: Historical fetch for {target_date_str} ({e})")
    return None

def parse_pgn_solution(pgn_str):
    if not pgn_str:
        return None, [], []
        
    clean_str = re.sub(r'\$\d+', '', pgn_str)
    
    try:
        game = chess.pgn.read_game(io.StringIO(clean_str))
        if game:
            b = game.board()
            moves_san = []
            moves_uci = []
            for move in game.mainline_moves():
                moves_san.append(b.san(move))
                moves_uci.append(move.uci())
                b.push(move)
            if moves_san and moves_uci:
                return game.board().fen(), moves_san, moves_uci
    except Exception:
        pass
        
    fen_match = re.search(r'\[FEN \"([^\"]+)\"\]', pgn_str)
    fen = fen_match.group(1) if fen_match else None
    if not fen:
        return None, [], []
        
    b = chess.Board(fen)
    b_init = chess.Board(fen)
    
    body = re.sub(r'\{[^}]*\}', '', clean_str)
    body = re.sub(r'\([^)]*\)', '', body)
    lines = [line for line in body.splitlines() if not line.startswith('[')]
    text = ' '.join(lines)
    
    moves_san = []
    moves_uci = []
    
    tokens = text.split()
    for token in tokens:
        token = re.sub(r'^\d+\.+', '', token)
        token = token.strip('.*#+$ \t\r\n')
        if not token or token in ['*', '1-0', '0-1', '1/2-1/2']:
            continue
        try:
            m = b.parse_san(token)
            moves_san.append(b.san(m))
            moves_uci.append(m.uci())
            b.push(m)
        except Exception:
            try:
                m = b.parse_uci(token)
                moves_san.append(b.san(m))
                moves_uci.append(m.uci())
                b.push(m)
            except Exception:
                pass
                
    if moves_san and moves_uci:
        return b_init.fen(), moves_san, moves_uci
    return None, [], []

def load_puzzle_data():
    prog = load_progress()
    next_offset = prog.get("next_offset", 0)
    
    force_val = os.getenv("FORCE_PUZZLE")
    if force_val is not None and force_val.strip().isdigit():
        val = int(force_val.strip())
        idx = val - 1 if val >= 1 else val
    else:
        idx = next_offset
        
    p_num = idx + 1
    p_date = START_DATE + timedelta(days=idx)
    p_date_str = format_pretty_date(p_date)
    target_date_str = p_date.strftime("%Y-%m-%d")
    
    hist_puzzle = None
    
    # 1. Load from bundled local historical dataset first
    if HISTORICAL_PUZZLES_FILE.exists():
        try:
            h_data = json.loads(HISTORICAL_PUZZLES_FILE.read_text(encoding="utf-8"))
            if 0 <= idx < len(h_data):
                hist_puzzle = h_data[idx]
        except Exception as e:
            print(f"Notice: local historical load ({e})")
            
    # 2. If not found locally, fetch online for target date
    if not hist_puzzle:
        hist_puzzle = fetch_historical_puzzle(target_date_str, fallback_index=idx)
        
    if hist_puzzle and hist_puzzle.get("pgn"):
        pgn = hist_puzzle["pgn"]
        title = hist_puzzle.get("title", f"Tactical Puzzle #{p_num}")
        fen, moves_san, moves_uci = parse_pgn_solution(pgn)
            
        if fen and moves_san and moves_uci:
            commentary, outro_text = generate_human_narration(fen, moves_san)
            real_date_str = hist_puzzle.get("date", target_date_str)
            try:
                pretty_d = format_pretty_date(datetime.strptime(real_date_str, "%Y-%m-%d").date())
            except Exception:
                pretty_d = p_date_str
            return {
                "id": p_num,
                "num": p_num,
                "date": real_date_str,
                "date_str": pretty_d,
                "title": title,
                "difficulty": "Daily",
                "fen": fen,
                "pgn": pgn,
                "solution_moves": moves_uci,
                "solution_moves_san": moves_san,
                "commentary": commentary,
                "outro_text": outro_text
            }

    # 2. Try Live/Random Chess.com API
    live = fetch_chess_com_puzzle()
    if live and "fen" in live and "pgn" in live:
        fen = live["fen"]
        pgn = live["pgn"]
        title = live.get("title", f"Tactical Puzzle #{p_num}")
        moves_uci = []
        moves_san = []
        try:
            game = chess.pgn.read_game(io.StringIO(pgn))
            if game:
                b = game.board()
                for move in game.mainline_moves():
                    moves_san.append(b.san(move))
                    moves_uci.append(move.uci())
                    b.push(move)
        except Exception as e:
            print(f"Error parsing PGN: {e}")
            
        if moves_san and moves_uci:
            commentary, outro_text = generate_human_narration(fen, moves_san)
            return {
                "id": p_num,
                "num": p_num,
                "date": target_date_str,
                "date_str": p_date_str,
                "title": title,
                "difficulty": "Daily",
                "fen": fen,
                "pgn": pgn,
                "solution_moves": moves_uci,
                "solution_moves_san": moves_san,
                "commentary": commentary,
                "outro_text": outro_text
            }

    # 3. Fallback to local curated puzzles pool
    puzzles = json.loads(PUZZLES_FILE.read_text(encoding="utf-8"))
    p_item = puzzles[idx % len(puzzles)]
    fen = p_item.get("setup_fen", p_item.get("fen", chess.STARTING_FEN))
    solution_moves = p_item.get("solution_moves_san", p_item.get("solution_moves", []))
    commentary, outro_text = generate_human_narration(fen, solution_moves)
    
    return {
        "id": p_item.get("id", p_num),
        "num": p_num,
        "date": target_date_str,
        "date_str": p_date_str,
        "title": p_item["title"],
        "difficulty": p_item.get("difficulty", "Easy"),
        "fen": fen,
        "pgn": p_item.get("pgn", ""),
        "solution_moves": p_item.get("solution_moves", []),
        "solution_moves_san": solution_moves,
        "commentary": commentary,
        "outro_text": outro_text
    }

def load_piece_images():
    pieces = {}
    theme = os.getenv("PIECE_THEME", "neo").lower()
    names = ["wp", "wn", "wb", "wr", "wq", "wk", "bp", "bn", "bb", "br", "bq", "bk"]
    theme_dir = PIECES_DIR / theme
    target_dir = theme_dir if theme_dir.exists() else PIECES_DIR
    
    for name in names:
        path = target_dir / f"{name}.png"
        if not path.exists():
            path = PIECES_DIR / f"{name}.png"
        if path.exists():
            pieces[name] = Image.open(path).convert("RGBA")
    return pieces

def load_badge_images():
    badges = {}
    names = ["brilliant", "inaccuracy", "mistake", "winner", "loser"]
    for name in names:
        path = BADGES_DIR / f"{name}.png"
        if path.exists():
            badges[name] = Image.open(path).convert("RGBA")
    return badges

PIECE_IMGS = load_piece_images()
BADGE_IMGS = load_badge_images()

def square_to_coords(square_idx, board_rect, flipped=False):
    left, top, size = board_rect
    sq_size = size / 8
    file_idx = chess.square_file(square_idx)
    rank_idx = chess.square_rank(square_idx)
    if flipped:
        col = 7 - file_idx
        row = rank_idx
    else:
        col = file_idx
        row = 7 - rank_idx
    x = left + col * sq_size
    y = top + row * sq_size
    return x, y, sq_size

import asyncio
import edge_tts

def make_voice_clip(text, out_wav, voice_index=0):
    primary_voice = EDGE_VOICES[voice_index % len(EDGE_VOICES)]
    mp3_tmp = str(out_wav).replace(".wav", ".mp3")
    
    # Add subtle spacing around punctuation for natural human pauses
    formatted_text = text.replace("...", "... ").replace("!", "! ").replace("?", "? ")
    
    candidate_voices = [primary_voice] + [v for v in EDGE_VOICES if v != primary_voice] + ["en-US-ChristopherNeural", "en-US-GuyNeural"]
    
    # 1. Try direct asyncio Python API with retries across candidate voices
    for v_name in candidate_voices:
        for attempt in range(2):
            try:
                async def _generate():
                    communicate = edge_tts.Communicate(formatted_text, v_name, rate="-4%", pitch="-1Hz")
                    await communicate.save(mp3_tmp)
                asyncio.run(_generate())
                if os.path.exists(mp3_tmp) and os.path.getsize(mp3_tmp) > 500:
                    res = subprocess.run(["ffmpeg", "-y", "-i", mp3_tmp, "-ar", "44100", "-ac", "1", str(out_wav)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.path.exists(mp3_tmp):
                        os.remove(mp3_tmp)
                    if res.returncode == 0 and os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                        return True
            except Exception as e:
                print(f"TTS Notice ({v_name} attempt {attempt+1}): {e}")
                time.sleep(0.5)

    # 2. Try CLI subprocess fallback
    for v_name in [primary_voice, "en-US-GuyNeural"]:
        try:
            cmd = [sys.executable, "-m", "edge_tts", "--text", formatted_text, "--voice", v_name, "--rate=-4%", "--pitch=-1Hz", "--write-media", mp3_tmp]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(mp3_tmp) and os.path.getsize(mp3_tmp) > 500:
                subprocess.run(["ffmpeg", "-y", "-i", mp3_tmp, "-ar", "44100", "-ac", "1", str(out_wav)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.path.exists(mp3_tmp):
                    os.remove(mp3_tmp)
                if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                    return True
        except Exception:
            pass

    # 3. macOS native TTS fallback if on Mac
    if sys.platform == "darwin":
        try:
            aiff_tmp = str(out_wav).replace(".wav", ".aiff")
            subprocess.run(["say", "-v", "Samantha", "-o", aiff_tmp, text], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.path.exists(aiff_tmp):
                subprocess.run(["ffmpeg", "-y", "-i", aiff_tmp, "-ar", "44100", "-ac", "1", str(out_wav)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                os.remove(aiff_tmp)
                if os.path.exists(out_wav) and os.path.getsize(out_wav) > 1000:
                    return True
        except Exception:
            pass

    print(f"WARNING: All TTS options failed for text: '{text}'")
    return False

def wav_duration(wav_path):
    try:
        with wave.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return 1.5

def write_audio_timeline(audio_events, output_wav, total_duration_sec, sample_rate=44100):
    total_samples = int(total_duration_sec * sample_rate) + sample_rate
    timeline = array("i", [0] * total_samples)
    
    for start_sec, sound_file in audio_events:
        if not sound_file or not os.path.exists(sound_file):
            continue
        try:
            with wave.open(str(sound_file), "rb") as wf:
                n_channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                
                # Unpack 16-bit PCM
                if sampwidth == 2:
                    raw_samples = array("h", frames)
                    start_idx = int(start_sec * sample_rate)
                    
                    # Convert channels to mono if needed
                    step = n_channels
                    for i in range(0, len(raw_samples) // step):
                        out_i = start_idx + i
                        if out_i < total_samples:
                            sample_val = raw_samples[i * step]
                            timeline[out_i] += sample_val
        except Exception as e:
            print(f"Audio read error on {sound_file}: {e}")
            
    # Clamp and pack to 16-bit
    with wave.open(str(output_wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        packed = bytearray()
        for val in timeline:
            clamped = max(-32768, min(32767, val))
            packed.extend(struct.pack("<h", clamped))
        wf.writeframes(packed)

def create_board_shadow(board_size=960, radius=28):
    padding = 120
    sw = board_size + padding * 2
    sh = board_size + padding * 2
    
    shadow_layer = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    
    # Layer 1: Soft wide ambient shadow (offset_y=12, blur=36, fill=50)
    ambient_mask = Image.new("L", (sw, sh), 0)
    a_draw = ImageDraw.Draw(ambient_mask)
    a_draw.rounded_rectangle(
        [padding, padding + 12, padding + board_size, padding + 12 + board_size],
        radius=radius,
        fill=50
    )
    ambient_blur = ambient_mask.filter(ImageFilter.GaussianBlur(36))
    ambient_img = Image.new("RGBA", (sw, sh), (10, 9, 8, 255))
    shadow_layer.paste(ambient_img, (0, 0), ambient_blur)
    
    # Layer 2: Tight contact shadow (offset_y=4, blur=14, fill=35)
    contact_mask = Image.new("L", (sw, sh), 0)
    c_draw = ImageDraw.Draw(contact_mask)
    c_draw.rounded_rectangle(
        [padding, padding + 4, padding + board_size, padding + 4 + board_size],
        radius=radius,
        fill=35
    )
    contact_blur = contact_mask.filter(ImageFilter.GaussianBlur(14))
    contact_img = Image.new("RGBA", (sw, sh), (5, 4, 4, 255))
    shadow_layer.paste(contact_img, (0, 0), contact_blur)
    
    return shadow_layer, padding

BOARD_SHADOW, SHADOW_PAD = create_board_shadow(960, 28)

def get_puzzle_objective(title_info):
    title = title_info.get("title", "") if isinstance(title_info, dict) else str(title_info)
    turn_str = title_info.get("turn", "White") if isinstance(title_info, dict) else "White"
    title_lower = title.lower()
    
    if "blindspot" in title_lower or "castle" in title_lower:
        return f"{turn_str} to play. Exploit the back-rank weakness."
    elif "smothered" in title_lower:
        return f"{turn_str} to play. Spot the smothered knight mate."
    elif "sacrifice" in title_lower:
        return f"{turn_str} to play. Find the winning sacrifice."
    else:
        return f"{turn_str} to play. Find the winning move."

def draw_chess_frame(board, board_rect, highlights=None, moving_piece=None, badges=None, particles=None, title_info=None, move_pgn_text="", flipped=False):
    img = Image.new("RGBA", (W, H), COLOR_BG)
    
    left, top, board_size = board_rect
    sq_size = board_size / 8
    
    # 1. Soft Elevation Drop Shadow below the board
    img.paste(BOARD_SHADOW, (int(left - SHADOW_PAD), int(top - SHADOW_PAD)), BOARD_SHADOW)
    
    # Create Board Surface for Rounded Masking
    board_surface = Image.new("RGBA", (int(board_size), int(board_size)), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(board_surface)
    
    # 2. Draw Board Squares
    for rank in range(8):
        for file in range(8):
            sq_idx = chess.square(file, rank)
            col = 7 - file if flipped else file
            row = rank if flipped else 7 - rank
            x = col * sq_size
            y = row * sq_size
            is_light = (rank + file) % 2 == 0
            color = COLOR_SQUARE_LIGHT if is_light else COLOR_SQUARE_DARK
            b_draw.rectangle([x, y, x + sq_size, y + sq_size], fill=color)

    # 3. Draw Highlights (local coordinates)
    if highlights:
        for sq, h_type in highlights.items():
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            col = 7 - file_idx if flipped else file_idx
            row = rank_idx if flipped else 7 - rank_idx
            hx = col * sq_size
            hy = row * sq_size
            if h_type == "orig":
                b_draw.rectangle([hx, hy, hx + sq_size, hy + sq_size], fill=COLOR_HIGHLIGHT_ORIG)
            elif h_type == "dest":
                b_draw.rectangle([hx, hy, hx + sq_size, hy + sq_size], fill=COLOR_HIGHLIGHT_DEST)
            elif h_type == "check":
                b_draw.rectangle([hx, hy, hx + sq_size, hy + sq_size], fill=COLOR_RED_CHECK)

    # 4. Draw Stationary Pieces
    for sq in chess.SQUARES:
        if moving_piece and sq == moving_piece.get("skip_sq"):
            continue
        p = board.piece_at(sq)
        if p:
            file_idx = chess.square_file(sq)
            rank_idx = chess.square_rank(sq)
            col = 7 - file_idx if flipped else file_idx
            row = rank_idx if flipped else 7 - rank_idx
            px = col * sq_size
            py = row * sq_size
            p_key = f"{'w' if p.color == chess.WHITE else 'b'}{p.symbol().lower()}"
            if p_key in PIECE_IMGS:
                p_img = PIECE_IMGS[p_key].resize((int(sq_size), int(sq_size)), Image.LANCZOS)
                board_surface.paste(p_img, (int(px), int(py)), p_img)

    # 5. Draw Interpolated Moving Piece with Motion Blur
    if moving_piece:
        mx = moving_piece["x"] - left
        my = moving_piece["y"] - top
        p_key = moving_piece["key"]
        if p_key in PIECE_IMGS:
            p_img = PIECE_IMGS[p_key].resize((int(sq_size), int(sq_size)), Image.LANCZOS)
            
            # Directional motion blur trails along velocity vector
            prev_x = moving_piece.get("prev_x", moving_piece["x"]) - left
            prev_y = moving_piece.get("prev_y", moving_piece["y"]) - top
            dx = mx - prev_x
            dy = my - prev_y
            dist = math.hypot(dx, dy)
            
            if dist > 3:
                # Render 3 smooth directional motion ghost trails
                for step in [0.75, 0.5, 0.25]:
                    ghost_x = mx - dx * step
                    ghost_y = my - dy * step
                    ghost_alpha = int(130 * (1.0 - step))
                    
                    ghost_img = p_img.copy()
                    r, g, b, a = ghost_img.split()
                    a = a.point(lambda p: int(p * (ghost_alpha / 255.0)))
                    ghost_img.putalpha(a)
                    board_surface.paste(ghost_img, (int(ghost_x), int(ghost_y)), ghost_img)
                    
            board_surface.paste(p_img, (int(mx), int(my)), p_img)

    # 6. Draw Coordinate Labels ON TOP (1-8 on left, a-h on bottom)
    coord_font = font(26, bold=True)
    
    # Rank Numbers (1-8 on left edge)
    for row in range(8):
        rank_num = row + 1 if flipped else 8 - row
        r_str = str(rank_num)
        x_local = 14 if row == 0 else 10
        y_local = row * sq_size + (10 if row == 0 else 6)
        file_for_color = 7 if flipped else 0
        rank_for_color = row if flipped else 7 - row
        is_light = (rank_for_color + file_for_color) % 2 == 0
        text_color = COLOR_SQUARE_DARK if is_light else COLOR_SQUARE_LIGHT
        b_draw.text((x_local, y_local), r_str, fill=text_color, font=coord_font)
        
    # File Letters (a-h on bottom edge)
    files = ["h", "g", "f", "e", "d", "c", "b", "a"] if flipped else ["a", "b", "c", "d", "e", "f", "g", "h"]
    for col, f_char in enumerate(files):
        x_offset = 32 if col == 7 else 26
        y_offset = 36 if col == 7 else 32
        x_local = (col + 1) * sq_size - x_offset
        y_local = 8 * sq_size - y_offset
        row_for_color = 7
        file_for_color = 7 - col if flipped else col
        rank_for_color = row_for_color if flipped else 7 - row_for_color
        is_light = (rank_for_color + file_for_color) % 2 == 0
        text_color = COLOR_SQUARE_DARK if is_light else COLOR_SQUARE_LIGHT
        b_draw.text((x_local, y_local), f_char, fill=text_color, font=coord_font)

    # 7. Anti-aliased 4x supersampled mask for 100% butter-smooth rounded corners
    scale = 4
    mask_high = Image.new("L", (int(board_size) * scale, int(board_size) * scale), 0)
    m_draw = ImageDraw.Draw(mask_high)
    m_draw.rounded_rectangle([0, 0, int(board_size) * scale - 1, int(board_size) * scale - 1], radius=28 * scale, fill=255)
    board_mask = mask_high.resize((int(board_size), int(board_size)), Image.LANCZOS)
    
    # Paste Board onto Centered Canvas
    img.paste(board_surface, (int(left), int(top)), board_mask)

    # 8. Render Top Header, Puzzle Title Subtext & Bottom Handle Text
    draw_canvas = ImageDraw.Draw(img)
    
    # Top Title: "Chess #1  •  May 1, 2007"
    p_num = title_info.get("num", 1) if title_info else 1
    p_date_str = title_info.get("date_str", "May 1, 2007") if title_info else "May 1, 2007"
    header_text = f"Chess #{p_num}  •  {p_date_str}"
    header_font = font(36, bold=True)
    header_y = int(top - 135)
    draw_canvas.text((W // 2, header_y), header_text, fill=(255, 255, 255, 255), font=header_font, anchor="mm")

    # Subtext: Puzzle Title (e.g. "The Castle's Blindspot")
    p_title = title_info.get("title", "Daily Chess Puzzle") if title_info else "Daily Chess Puzzle"
    sub_font = font(24, bold=False)
    sub_y = int(top - 75)
    draw_canvas.text((W // 2, sub_y), p_title, fill=(160, 170, 185), font=sub_font, anchor="mm")

    # Bottom Handle: "@thechessstuff" (muted slate grey)
    handle_text = "@thechessstuff"
    handle_font = font(28, bold=True)
    handle_y = int(top + board_size + 115)
    draw_canvas.text((W // 2, handle_y), handle_text, fill=(160, 167, 180), font=handle_font, anchor="mm")

    return img

def generate_reel_timeline(puzzle):
    fen = puzzle.get("setup_fen", puzzle.get("fen", chess.STARTING_FEN))
    board = chess.Board(fen)
    b_start = chess.Board(fen)
    flipped = (b_start.turn == chess.BLACK)
    
    voice_index = random.randint(0, len(EDGE_VOICES) - 1)
    
    left = (W - 954) // 2
    top = (H - 954) // 2
    board_rect = (left, top, 954)
    
    frame_actions = []
    audio_events = []
    
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        
        move_sfx = SOUNDS_DIR / "move.wav"
        capture_sfx = SOUNDS_DIR / "capture.wav"
        check_sfx = SOUNDS_DIR / "check.wav"
        brilliant_sfx = SOUNDS_DIR / "brilliant.wav"
        game_over_sfx = SOUNDS_DIR / "game_over.wav"

        current_frame = 0
        storyboard_segments = []

        # 1. Opener Intro
        commentary = puzzle.get("commentary", [])
        opener_text = commentary[0] if len(commentary) > 0 else "Alright, White to play here. Let's see what we've got."
        opener_wav = tmp_dir / "opener.wav"
        make_voice_clip(opener_text, opener_wav, voice_index)
        opener_dur = wav_duration(opener_wav)
        opener_frames = int(round(max(2.0, opener_dur) * FPS))

        audio_events.append((0.0, opener_wav))
        for _ in range(opener_frames):
            frame_actions.append({
                "board": board.copy(),
                "highlights": None,
                "moving_piece": None,
                "badges": None,
                "text": opener_text
            })
        current_frame += opener_frames
        storyboard_segments.append({"type": "opener", "text": opener_text, "duration": opener_dur})

        # 2. Parse & Animate Solution Moves
        solution_moves = puzzle.get("solution_moves", puzzle.get("solution_moves_san", []))
        commentary_idx = 1
        
        for move_str in solution_moves:
            try:
                move = board.parse_uci(move_str)
            except Exception:
                try:
                    move = board.parse_san(move_str)
                except Exception as e:
                    print(f"Skipping unparseable move {move_str}: {e}")
                    continue
                    
            from_sq = move.from_square
            to_sq = move.to_square
            is_capture = board.is_capture(move)
            
            p_moving = board.piece_at(from_sq)
            if not p_moving:
                continue
                
            p_key = f"{'w' if p_moving.color == chess.WHITE else 'b'}{p_moving.symbol().lower()}"
            
            # Narration for move
            step_text = commentary[commentary_idx] if commentary_idx < len(commentary) else f"And then, {board.san(move)}."
            commentary_idx += 1
            
            step_wav = tmp_dir / f"step_{current_frame}.wav"
            make_voice_clip(step_text, step_wav, voice_index)
            step_dur = wav_duration(step_wav)
            
            audio_events.append((current_frame / FPS, step_wav))
            
            # Fast, smooth slide animation with Motion Blur (6 frames)
            x1, y1, sq_sz = square_to_coords(from_sq, board_rect, flipped=flipped)
            x2, y2, _ = square_to_coords(to_sq, board_rect, flipped=flipped)
            
            num_move_frames = 6
            prev_x, prev_y = x1, y1
            for f_i in range(num_move_frames):
                t = f_i / float(num_move_frames - 1)
                ease_t = t * t * (3.0 - 2.0 * t)  # SmoothStep curve
                curr_x = x1 + (x2 - x1) * ease_t
                curr_y = y1 + (y2 - y1) * ease_t
                
                frame_actions.append({
                    "board": board.copy(),
                    "highlights": {from_sq: "orig", to_sq: "dest"},
                    "moving_piece": {
                        "key": p_key,
                        "x": curr_x,
                        "y": curr_y,
                        "prev_x": prev_x,
                        "prev_y": prev_y,
                        "skip_sq": from_sq
                    },
                    "text": step_text
                })
                prev_x, prev_y = curr_x, curr_y
            current_frame += num_move_frames
            
            # Play move SFX at impact
            sfx_to_play = capture_sfx if is_capture else move_sfx
            audio_events.append((current_frame / FPS, sfx_to_play))
            
            # Push move to board state
            board.push(move)
            
            is_check = board.is_check()
            is_mate = board.is_checkmate()
            
            if is_check:
                sfx_to_play = check_sfx
                audio_events.append((current_frame / FPS, sfx_to_play))

            # Hold pose for voice clip duration
            hold_frames = max(15, int(round(step_dur * FPS)) - num_move_frames)
            highlights = {from_sq: "orig", to_sq: "dest"}
            if is_mate or is_check:
                k_sq = board.king(board.turn)
                if k_sq is not None:
                    highlights[k_sq] = "check"

            for _ in range(hold_frames):
                frame_actions.append({
                    "board": board.copy(),
                    "highlights": highlights,
                    "moving_piece": None,
                    "text": step_text
                })
            current_frame += hold_frames
            
            storyboard_segments.append({"type": "move", "move": move_str, "text": step_text, "duration": step_dur})

        # 3. Outro (Clean, zero confetti)
        outro_text = puzzle.get("outro_text", "What a clean tactical sequence!")
        outro_wav = tmp_dir / "outro.wav"
        make_voice_clip(outro_text, outro_wav, voice_index)
        outro_dur = wav_duration(outro_wav)
        outro_frames = max(45, int(round(outro_dur * FPS)))
        
        audio_events.append((current_frame / FPS, outro_wav))
        audio_events.append((current_frame / FPS, game_over_sfx))
        
        # Checkmate King Red Background Highlight for Outro
        final_highlights = {}
        if board.is_checkmate() or board.is_check():
            k_sq = board.king(board.turn)
            if k_sq is not None:
                final_highlights[k_sq] = "check"
        if len(solution_moves) > 0:
            try:
                last_move = board.peek()
                final_highlights[last_move.from_square] = "orig"
                final_highlights[last_move.to_square] = "dest"
            except Exception:
                pass

        for _ in range(outro_frames):
            frame_actions.append({
                "board": board.copy(),
                "highlights": final_highlights,
                "moving_piece": None,
                "text": outro_text
            })
        current_frame += outro_frames
        
        total_duration = current_frame / FPS
        return frame_actions, audio_events, total_duration, voice_index, storyboard_segments, board_rect, fen

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    puzzle = load_puzzle_data()
    
    print(f"Loaded Chess Puzzle: {puzzle['title']} (ID: {puzzle['id']})")
    
    frame_actions, audio_events, total_duration, voice_index, storyboard_segments, board_rect, fen = generate_reel_timeline(puzzle)
    
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        master_wav = tmp_dir / "master_mix.wav"
        write_audio_timeline(audio_events, master_wav, total_duration)
        
        frames_dir = tmp_dir / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)
        b_init = chess.Board(fen)
        turn_str = "White" if b_init.turn == chess.WHITE else "Black"
        title_info = {
            "num": puzzle.get("num", 1),
            "title": puzzle["title"],
            "date_str": puzzle.get("date_str", "May 1, 2007"),
            "date": puzzle.get("date", "2007-05-01"),
            "turn": turn_str,
            "difficulty": puzzle.get("difficulty", "Easy")
        }
        
        for idx, act in enumerate(frame_actions):
            img = draw_chess_frame(
                board=act["board"],
                board_rect=board_rect,
                highlights=act.get("highlights"),
                moving_piece=act.get("moving_piece"),
                badges=act.get("badges"),
                particles=act.get("particles"),
                title_info=title_info,
                move_pgn_text=act.get("text", ""),
                flipped=(b_init.turn == chess.BLACK)
            )
            img.save(frames_dir / f"frame_{idx:05d}.png")
            
        storyboard_data = {
            "puzzle_id": puzzle["id"],
            "puzzle_num": puzzle.get("num", 1),
            "date": puzzle.get("date", "2007-05-01"),
            "date_str": puzzle.get("date_str", "May 1, 2007"),
            "title": puzzle["title"],
            "difficulty": puzzle.get("difficulty", "Easy"),
            "fen": puzzle["fen"],
            "total_duration": total_duration,
            "voice": EDGE_VOICES[voice_index],
            "segments": storyboard_segments
        }
        STORY_OUT.write_text(json.dumps(storyboard_data, indent=2), encoding="utf-8")
        
        cmd_video = [
            "ffmpeg", "-y",
            "-r", str(FPS),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-i", str(master_wav),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(VIDEO_OUT)
        ]
        res = subprocess.run(cmd_video, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"FFmpeg Error (exit code {res.returncode}): {res.stderr}")
        else:
            print(f"SUCCESS: Generated Chess Reel -> {VIDEO_OUT} ({total_duration:.1f}s)")

if __name__ == "__main__":
    main()
