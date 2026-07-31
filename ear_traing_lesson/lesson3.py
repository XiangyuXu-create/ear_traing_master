"""
Lesson 3: 钢琴全音阶（白键+黑键）MIDI 练耳音轨生成
=================================================
和 Lesson 1 结构相同（A4 与随机音交替），但候选音包含所有半音（黑键+白键）。

参数：
  - 最低音（low_note）：随机音范围下限，默认 "A3"
  - 最高音（high_note）：随机音范围上限，默认 "D5"
  - 重复次数（repeat_count）：A4-随机音 交替次数，默认 3
  - 练习条数（max_exercises）：生成练习条数上限，默认 10

练习示例（repeat_count=3）：
  随机到 C#4 → A4 C#4 A4 C#4 A4 C#4
  随机到 A3  → A4 A3 A4 A3 A4 A3

A4 = MIDI 69 = 440Hz（国际标准音高）
"""

import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage
import os
import random
import re
import json

# -------------------- 配置 --------------------

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media")
NOTE_DURATION = 480
TEMPO = 500000
VELOCITY = 80
DEFAULT_CHANNEL = 0

A4_MIDI = 69
A4_NOTE = ("A", 4, A4_MIDI)

# -------------------- 半音系统 --------------------

# 所有音名（包括黑键）
CHROMATIC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 半音偏移量（相对于 C）
CHROMATIC_OFFSETS = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}


def midi_note(name: str, octave: int) -> int:
    """根据音名（含升降号）和八度返回 MIDI 音符编号。"""
    if name not in CHROMATIC_OFFSETS:
        raise ValueError(f"无效音名: {name}")
    return (octave + 1) * 12 + CHROMATIC_OFFSETS[name]


def parse_note_str(note_str: str):
    """解析 "C#4", "A3", "Bb2" 格式的音符字符串。"""
    match = re.match(r"^([A-G])([#b]?)(-?\d+)$", note_str.strip())
    if not match:
        raise ValueError(f"无法解析音符: {note_str}")
    name = match.group(1)
    acc = match.group(2)
    octave = int(match.group(3))

    # 降号转升号: Db→C#, Eb→D#, Gb→F#, Ab→G#, Bb→A#
    flat_to_sharp = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    full = name + acc
    if acc == "b" and full in flat_to_sharp:
        sharp_name = flat_to_sharp[full]
        if sharp_name == "C#":
            octave += 1
        name = sharp_name[0]
        # 重新计算
    elif acc == "b":
        raise ValueError(f"不支持的降号: {note_str}，请用升号如 C#")

    if full not in CHROMATIC_OFFSETS:
        full = name  # no accidental, just the letter
        if full not in CHROMATIC_OFFSETS:
            raise ValueError(f"无法解析: {note_str}")

    return (name, octave, midi_note(full if full in CHROMATIC_OFFSETS else name, octave))


def note_to_str(name: str, octave: int) -> str:
    """ (A, 4) -> 'A4', (C, 4, '#') -> 'C#4' """
    return f"{name}{octave}"


def midi_to_frequency(note: int) -> float:
    return 440.0 * (2 ** ((note - 69) / 12))


# -------------------- 全音阶范围构建 --------------------


def build_chromatic_keys_in_range(low_note_str: str, high_note_str: str):
    """获取两个音符之间（含）的所有半音。"""
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


# -------------------- 练习模式生成 --------------------


def build_exercise_patterns(
    low_note: str = "A3",
    high_note: str = "D5",
    repeat_count: int = 3,
    max_exercises: int = 10,
    seed: int = None,
):
    """生成练耳练习：每条以 A4 开头，与范围内随机半音交替重复。"""
    if seed is not None:
        random.seed(seed)

    candidates = build_chromatic_keys_in_range(low_note, high_note)
    candidates = [k for k in candidates if k[2] != A4_MIDI]

    if not candidates:
        raise ValueError(f"范围 [{low_note}~{high_note}] 内没有可用音（排除A4后）")

    num_pick = min(max_exercises, len(candidates))
    selected = random.sample(candidates, num_pick)

    exercises = []
    answers = []
    for target_key in selected:
        pattern = []
        for _ in range(repeat_count):
            pattern.append(A4_NOTE)
            pattern.append(target_key)
        exercises.append(pattern)
        answers.append(f"{target_key[0]}{target_key[1]}")

    return exercises, answers


# -------------------- MIDI 文件生成 --------------------


def create_exercise_midi(
    exercises: list,
    filename: str = "lesson3_exercises.mid",
    note_duration: int = NOTE_DURATION,
    tempo: int = TEMPO,
    velocity: int = VELOCITY,
    channel: int = DEFAULT_CHANNEL,
    gap_duration: int = None,
) -> str:
    if gap_duration is None:
        gap_duration = note_duration * 2

    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("track_name", name="Lesson3", time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(Message("program_change", channel=channel, program=0, time=0))

    for ex_idx, exercise in enumerate(exercises):
        for i, (_name, _oct, note_num) in enumerate(exercise):
            if ex_idx == 0 and i == 0:
                dt = 0
            elif i == 0:
                dt = note_duration + gap_duration
            else:
                dt = note_duration
            track.append(Message("note_on", channel=channel, note=note_num,
                                 velocity=velocity, time=dt))
            track.append(Message("note_off", channel=channel, note=note_num,
                                 velocity=0, time=note_duration))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    mid.save(filepath)
    return filepath


def save_answers(answers: list, filename: str = "lesson3_answers.json"):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"answers": answers}, f, ensure_ascii=False, indent=2)
    return filepath


# -------------------- 打印 --------------------


def print_exercises(exercises, answers):
    print(f"\n{'序号':<5} {'随机音':<8} {'练习序列'}")
    print("-" * 60)
    for idx, (ex, ans) in enumerate(zip(exercises, answers), 1):
        seq = " → ".join(f"{n}{o}" for n, o, _ in ex)
        print(f"{idx:<5} {ans:<8} {seq}")


# -------------------- 主程序 --------------------


def main(
    low_note: str = "A3",
    high_note: str = "D5",
    repeat_count: int = 3,
    max_exercises: int = 10,
    seed: int = None,
):
    print("\n╔══════════════════════════════════════════╗")
    print("║   Lesson 3: 全音阶（白键+黑键）MIDI 生成 ║")
    print("║        A4 = 440Hz 标准音高              ║")
    print("╚══════════════════════════════════════════╝\n")

    print(f"参数: 范围 {low_note}~{high_note}, 重复 {repeat_count} 次, 共 {max_exercises} 条")

    exercises, answers = build_exercise_patterns(
        low_note=low_note, high_note=high_note,
        repeat_count=repeat_count, max_exercises=max_exercises, seed=seed,
    )
    print_exercises(exercises, answers)

    midi_path = create_exercise_midi(exercises)
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
        kwargs["repeat_count"] = int(sys.argv[3])
    if len(sys.argv) > 4:
        kwargs["max_exercises"] = int(sys.argv[4])
    if len(sys.argv) > 5:
        kwargs["seed"] = int(sys.argv[5])
    main(**kwargs)
