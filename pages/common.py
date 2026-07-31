"""共享工具：白键列表、渲染、易错题集。"""

import os
import json
from datetime import datetime

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media")
MISTAKE_FILE = os.path.join(MEDIA_DIR, "mistake_collection.json")
os.makedirs(MEDIA_DIR, exist_ok=True)


def build_all_white_keys():
    from ear_traing_lesson.lesson1 import midi_note
    notes = []
    for octave in range(1, 7):
        for name in ["C", "D", "E", "F", "G", "A", "B"]:
            n = midi_note(name, octave)
            if 21 <= n <= 108:
                notes.append(f"{name}{octave}")
    notes.sort(key=lambda x: midi_note(x[0], int(x[1:])))
    return notes


ALL_NOTES = build_all_white_keys()


def build_all_chromatic_keys():
    """生成所有半音 C1~B6（含黑键），按音高排序。"""
    import re
    from ear_traing_lesson.lesson3 import midi_note as cmidi
    notes = []
    for octave in range(1, 7):
        for name in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]:
            n = cmidi(name, octave)
            if 21 <= n <= 108:
                notes.append(f"{name}{octave}")

    def _parse(ns):
        m = re.match(r"^([A-G]#?)(\d+)$", ns)
        if not m:
            return 0
        return cmidi(m.group(1), int(m.group(2)))

    notes.sort(key=_parse)
    return notes


ALL_CHROMATIC = build_all_chromatic_keys()


def chromatic_notes_in_range(low: str, high: str):
    """返回两个半音之间（含）的所有半音。"""
    if low not in ALL_CHROMATIC or high not in ALL_CHROMATIC:
        return ALL_CHROMATIC
    lo = ALL_CHROMATIC.index(low)
    hi = ALL_CHROMATIC.index(high)
    if lo > hi:
        lo, hi = hi, lo
    return ALL_CHROMATIC[lo:hi + 1]


def notes_in_range(low: str, high: str):
    if low not in ALL_NOTES or high not in ALL_NOTES:
        return ALL_NOTES
    lo = ALL_NOTES.index(low)
    hi = ALL_NOTES.index(high)
    if lo > hi:
        lo, hi = hi, lo
    return ALL_NOTES[lo:hi + 1]


def render_exercise_wav(exercise: list, preset: str, index: int, suffix: str = "", gap_ms: int = 500) -> str:
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    from midi2wav import midi_to_wav
    note_ticks = 480  # 四分音符
    gap_ticks = int(gap_ms * 480 / 500)  # 500ms = 1拍 = 480 ticks
    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("track_name", name="Ex", time=0))
    track.append(MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(Message("program_change", channel=0, program=0, time=0))
    for i, (_name, _oct, note_num) in enumerate(exercise):
        dt = 0 if i == 0 else note_ticks + gap_ticks
        track.append(Message("note_on", channel=0, note=note_num, velocity=80, time=dt))
        track.append(Message("note_off", channel=0, note=note_num, velocity=0, time=note_ticks))
    tmp_mid = os.path.join(MEDIA_DIR, f"_tmp_{suffix}_{index}.mid")
    mid.save(tmp_mid)
    wav_path = os.path.join(MEDIA_DIR, f"_tmp_{suffix}_{index}_{preset}.wav")
    result = midi_to_wav(tmp_mid, wav_path, preset=preset)
    os.remove(tmp_mid)
    return result


def render_a4_wav(preset: str = "piano") -> str:
    """生成 A4=440Hz 标准音 WAV 文件（缓存）。"""
    import hashlib
    cache_key = hashlib.md5(f"a4_{preset}".encode()).hexdigest()
    cache_path = os.path.join(MEDIA_DIR, f"_a4_ref_{cache_key}.wav")
    if os.path.exists(cache_path):
        return cache_path
    from ear_traing_lesson.lesson1 import A4_NOTE
    return render_exercise_wav([A4_NOTE], preset, 0, cache_key[:8], gap_ms=0)


def load_mistakes():
    if os.path.exists(MISTAKE_FILE):
        with open(MISTAKE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def add_mistakes(wrong_notes: list):
    records = load_mistakes()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    for note in wrong_notes:
        found = False
        for r in records:
            if r["note"] == note:
                r["count"] = r.get("count", 1) + 1
                r["last_wrong"] = now
                found = True
                break
        if not found:
            records.append({"note": note, "count": 1, "first_wrong": now, "last_wrong": now})
    with open(MISTAKE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    return records


def format_mistakes():
    records = load_mistakes()
    if not records:
        return "暂无错题记录"
    records.sort(key=lambda r: -r["count"])
    lines = [f"{r['note']}: 错 {r['count']} 次  |  最近: {r.get('last_wrong', '?')}" for r in records]
    return "\n".join(lines)
