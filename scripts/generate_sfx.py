#!/usr/bin/env python3
import math
import struct
import wave
from pathlib import Path

SOUNDS_DIR = Path(__file__).resolve().parents[1] / "assets" / "sounds"
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)

def write_wav(path, samples, sample_rate=44100):
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        packed = bytearray()
        for s in samples:
            val = int(max(-32768, min(32767, s * 32767)))
            packed.extend(struct.pack("<h", val))
        wf.writeframes(packed)

def make_move_sound():
    # Crisp wood click / knock sound
    sr = 44100
    dur = 0.08
    n_samples = int(sr * dur)
    samples = []
    for i in range(n_samples):
        t = i / sr
        freq = 600 * math.exp(-t * 40) + 150
        env = math.exp(-t * 50)
        s = math.sin(2 * math.pi * freq * t) * env
        # add noise burst for wooden click
        noise = (hash(i) % 1000 / 1000.0 - 0.5) * 0.3 * math.exp(-t * 80)
        samples.append(s + noise)
    write_wav(SOUNDS_DIR / "move.wav", samples)

def make_capture_sound():
    # Heavy wooden impact thud sound
    sr = 44100
    dur = 0.12
    n_samples = int(sr * dur)
    samples = []
    for i in range(n_samples):
        t = i / sr
        freq = 350 * math.exp(-t * 30) + 90
        env = math.exp(-t * 35)
        s = math.sin(2 * math.pi * freq * t) * env
        noise = (hash(i) % 1000 / 1000.0 - 0.5) * 0.5 * math.exp(-t * 60)
        samples.append(s + noise)
    write_wav(SOUNDS_DIR / "capture.wav", samples)

def make_check_sound():
    # Warning bell / tone chime
    sr = 44100
    dur = 0.25
    n_samples = int(sr * dur)
    samples = []
    for i in range(n_samples):
        t = i / sr
        env = math.exp(-t * 12)
        s = (math.sin(2 * math.pi * 880 * t) * 0.6 + math.sin(2 * math.pi * 1760 * t) * 0.4) * env
        samples.append(s)
    write_wav(SOUNDS_DIR / "check.wav", samples)

def make_brilliant_sound():
    # Triumphant bright shimmer / arpeggio chime
    sr = 44100
    dur = 0.5
    n_samples = int(sr * dur)
    samples = []
    freqs = [523.25, 659.25, 783.99, 1046.50] # C5, E5, G5, C6
    for i in range(n_samples):
        t = i / sr
        step = int(t / 0.08)
        f = freqs[min(step, len(freqs)-1)]
        env = math.exp(-(t % 0.08) * 15) * math.exp(-t * 3)
        s = math.sin(2 * math.pi * f * t) * env
        samples.append(s)
    write_wav(SOUNDS_DIR / "brilliant.wav", samples)

def make_game_over_sound():
    # Victory celebratory chime sequence
    sr = 44100
    dur = 0.7
    n_samples = int(sr * dur)
    samples = []
    chords = [523.25, 659.25, 783.99, 1046.50, 1318.51] # C maj 7
    for i in range(n_samples):
        t = i / sr
        env = math.exp(-t * 4)
        s = sum(math.sin(2 * math.pi * f * t) for f in chords) / len(chords) * env
        samples.append(s)
    write_wav(SOUNDS_DIR / "game_over.wav", samples)
    write_wav(SOUNDS_DIR / "chime.wav", samples)

def make_error_sound():
    # Low buzz error
    sr = 44100
    dur = 0.2
    n_samples = int(sr * dur)
    samples = []
    for i in range(n_samples):
        t = i / sr
        env = math.exp(-t * 10)
        s = (math.sin(2 * math.pi * 150 * t) + math.sin(2 * math.pi * 155 * t)) * 0.5 * env
        samples.append(s)
    write_wav(SOUNDS_DIR / "error.wav", samples)

if __name__ == "__main__":
    make_move_sound()
    make_capture_sound()
    make_check_sound()
    make_brilliant_sound()
    make_game_over_sound()
    make_error_sound()
    print(f"Generated sound effects in {SOUNDS_DIR}")
