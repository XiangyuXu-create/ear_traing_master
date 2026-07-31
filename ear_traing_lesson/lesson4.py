"""
Lesson 4: 全音阶（白键+黑键）旋律 MIDI 生成
===========================================
和 Lesson 2 结构相同，但候选音包含所有半音（黑键+白键）。

参数：
  - 最低音（low_note）：随机音范围下限，默认 "A3"
  - 最高音（high_note）：随机音范围上限，默认 "D5"
  - 音符数量（note_count）：每条旋律包含几个音，默认 5
  - 练习条数（max_exercises）：生成练习条数上限，默认 10
"""

import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage
import os
import random
import re
import json

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media")
NOTE_DURATION = 480
TEMPO = 500000
VELOCITY = 80
DEFAULT_CHANNEL = 0

CHROMATIC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
CHROMATIC_OFFSETS = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}


def midi_note(name: str, octave: int) -> int:
    if name not in CHROMATIC_OFFSETS:
        raise ValueError(f"无效音名: {name}")
    return (octave + 1) * 12 + CHROMATIC_OFFSETS[name]


def parse_note_str(note_str: str):
    match = re.match(r"^([A-G])([#b]?)(-?\d+)$", note_str.strip())
    if not match:
        raise ValueError(f"无法解析音符: {note_str}")
    name, acc, octave = match.group(1), match.group(2), int(match.group(3))
    if acc == "b":
        flat_map = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
        flat = name + acc
        if flat in flat_map:
            name = flat_map[flat]
        else:
            raise ValueError(f"不支持的降号: {note_str}")
    elif acc == "#":
        name = name + "#"
    return (name, octave, midi_note(name, octave))


def build_chromatic_keys_in_range(low_note_str: str, high_note_str: str):
    _, _, low_midi = parse_note_str(low_note_str)
    _, _, high_midi = parse_note_str(high_note_str)
    lo = min(low_midi, high_midi)
    hi = max(low_midi, high_midi)
    keys = []
    for octave in range(0, 9):
        for name in CHROMATIC_NAMES:
            n = midi_note(name, octave)
            if lo <= n <= hi and n <= 127:
                keys.append((name, octave, n))
    return keys


def build_melody_exercises(
    low_note: str = "A3", high_note: str = "D5",
    note_count: int = 5, melody_repeat: int = 1,
    max_exercises: int = 10, seed: int = None,
):
    if seed is not None:
        random.seed(seed)
    candidates = build_chromatic_keys_in_range(low_note, high_note)
    if not candidates:
        raise ValueError(f"范围 [{low_note}~{high_note}] 内没有可用音")
    exercises = []
    answers = []
    for _ in range(max_exercises):
        melody = [random.choice(candidates) for _ in range(note_count)]
        pattern = []
        for _ in range(melody_repeat):
            pattern.extend(melody)
        exercises.append(pattern)
        answers.append([f"{name}{octave}" for name, octave, _ in melody])
    return exercises, answers


def create_melody_midi(exercises, filename="lesson4_exercises.mid",
                       note_duration=NOTE_DURATION, tempo=TEMPO,
                       velocity=VELOCITY, channel=DEFAULT_CHANNEL,
                       gap_duration=None):
    if gap_duration is None:
        gap_duration = note_duration * 2
    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("track_name", name="Lesson4", time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(Message("program_change", channel=channel, program=0, time=0))
    for ex_idx, exercise in enumerate(exercises):
        for i, (_name, _oct, note_num) in enumerate(exercise):
            dt = 0 if ex_idx == 0 and i == 0 else (note_duration if i > 0 else note_duration + gap_duration)
            track.append(Message("note_on", channel=channel, note=note_num, velocity=velocity, time=dt))
            track.append(Message("note_off", channel=channel, note=note_num, velocity=0, time=note_duration))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    mid.save(filepath)
    return filepath


def save_answers(answers, filename="lesson4_answers.json"):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"answers": answers}, f, ensure_ascii=False, indent=2)
    return filepath


def main(low_note="A3", high_note="D5", note_count=5, max_exercises=10, seed=None):
    print("\n╔══════════════════════════════════════════╗")
    print("║   Lesson 4: 全音阶旋律 MIDI 生成         ║")
    print("╚══════════════════════════════════════════╝\n")
    exercises, answers = build_melody_exercises(
        low_note=low_note, high_note=high_note,
        note_count=note_count, max_exercises=max_exercises, seed=seed,
    )
    for idx, ans in enumerate(answers, 1):
        print(f"  {idx}. {' → '.join(ans)}")
    midi_path = create_melody_midi(exercises)
    ans_path = save_answers(answers)
    print(f"\n✅ MIDI: {midi_path}")
    print(f"✅ 答案: {ans_path}")


if __name__ == "__main__":
    import sys
    kwargs = {}
    if len(sys.argv) > 1:
        kwargs["low_note"] = sys.argv[1]
    if len(sys.argv) > 2:
        kwargs["high_note"] = sys.argv[2]
    if len(sys.argv) > 3:
        kwargs["note_count"] = int(sys.argv[3])
    if len(sys.argv) > 4:
        kwargs["max_exercises"] = int(sys.argv[4])
    main(**kwargs)
