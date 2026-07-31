"""
Lesson 2: 随机白键旋律 MIDI 生成
===============================
生成 N 个范围内随机白键组成的旋律，按序播放。
训练听辨一串音高的能力。

参数：
  - 最低音（low_note）：随机白键范围下限，默认 "A3"
  - 最高音（high_note）：随机白键范围上限，默认 "D5"
  - 音符数量（note_count）：每条旋律包含几个音，默认 4
  - 旋律重复（melody_repeat）：整段旋律重复次数，默认 1
  - 练习条数（max_exercises）：生成练习条数上限，默认 10

示例（note_count=4）：
  随机到 [C4, E4, G4, C5] → MIDI 播放 C4→E4→G4→C5

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
NOTE_DURATION = 480        # 每个音符的 tick 时长
TEMPO = 500000             # 120 BPM
VELOCITY = 80
DEFAULT_CHANNEL = 0

# -------------------- 白键工具 --------------------

WHITE_KEY_NAMES = ["C", "D", "E", "F", "G", "A", "B"]

WHITE_KEY_OFFSETS_FROM_C = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}


def midi_note(name: str, octave: int) -> int:
    if name not in WHITE_KEY_OFFSETS_FROM_C:
        raise ValueError(f"无效音名: {name}")
    return (octave + 1) * 12 + WHITE_KEY_OFFSETS_FROM_C[name]


def parse_note_str(note_str: str):
    match = re.match(r"^([A-G])([b#]?)(-?\d+)$", note_str.upper())
    if not match:
        raise ValueError(f"无法解析音符: {note_str}")
    name, accidental, octave = match.group(1), match.group(2), int(match.group(3))
    if accidental:
        raise ValueError(f"暂不支持升降号: {note_str}")
    return (name, octave, midi_note(name, octave))


def midi_to_frequency(note: int) -> float:
    return 440.0 * (2 ** ((note - 69) / 12))


# -------------------- 白键范围 --------------------


def build_white_keys_in_range(low_note_str: str, high_note_str: str):
    """获取两个音符之间（含）的所有白键，按音高排序。"""
    _, _, low_midi = parse_note_str(low_note_str)
    _, _, high_midi = parse_note_str(high_note_str)
    lo = min(low_midi, high_midi)
    hi = max(low_midi, high_midi)

    keys = []
    for octave in range(0, 9):
        for name in WHITE_KEY_NAMES:
            n = midi_note(name, octave)
            if lo <= n <= hi and n <= 127:
                keys.append((name, octave, n))
    return keys


# -------------------- 旋律生成 --------------------


def build_melody_exercises(
    low_note: str = "A3",
    high_note: str = "D5",
    note_count: int = 4,
    melody_repeat: int = 1,
    max_exercises: int = 10,
    seed: int = None,
):
    """生成旋律练耳练习：每条练习是一串随机白键。

    Args:
        low_note: 随机白键范围下限
        high_note: 随机白键范围上限
        note_count: 每条旋律包含几个音
        melody_repeat: 整段旋律重复次数
        max_exercises: 最多生成几条练习
        seed: 随机种子

    Returns:
        (exercises, answers)
        - exercises: List[List[Tuple[str,int,int]]]，每条是一个音符列表
        - answers: List[List[str]]，每条是音名列表如 ["C4","E4","G4","C5"]
    """
    if seed is not None:
        random.seed(seed)

    candidates = build_white_keys_in_range(low_note, high_note)
    if not candidates:
        raise ValueError(f"范围 [{low_note}~{high_note}] 内没有白键")

    num_pick = min(max_exercises, len(candidates) ** note_count)

    exercises = []
    answers = []

    for _ in range(max_exercises):
        # 随机选 N 个音（可重复）
        melody = [random.choice(candidates) for _ in range(note_count)]

        # 构建完整序列（含重复）
        pattern = []
        for _ in range(melody_repeat):
            pattern.extend(melody)

        exercises.append(pattern)
        answers.append([f"{name}{octave}" for name, octave, _ in melody])

    return exercises, answers


# -------------------- MIDI 文件生成 --------------------


def create_melody_midi(
    exercises: list,
    filename: str = "lesson2_exercises.mid",
    note_duration: int = NOTE_DURATION,
    tempo: int = TEMPO,
    velocity: int = VELOCITY,
    channel: int = DEFAULT_CHANNEL,
    gap_duration: int = None,
) -> str:
    """将旋律练习列表生成 MIDI 文件。"""
    if gap_duration is None:
        gap_duration = note_duration * 2

    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("track_name", name="Lesson2 Melody", time=0))
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


def save_answers(answers: list, filename: str = "lesson2_answers.json"):
    """保存答案到 JSON。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"answers": answers}, f, ensure_ascii=False, indent=2)
    return filepath


# -------------------- 打印 --------------------


def print_exercises(exercises, answers):
    """打印旋律列表。"""
    print(f"\n{'序号':<5} {'音符数':<7} {'旋律'}")
    print("-" * 60)
    for idx, (ex, ans) in enumerate(zip(exercises, answers), 1):
        melody = " → ".join(ans)
        print(f"{idx:<5} {len(ans):<7} {melody}")
    print("-" * 60)
    print(f"共 {len(exercises)} 条旋律")


# -------------------- 主程序 --------------------


def main(
    low_note: str = "A3",
    high_note: str = "D5",
    note_count: int = 4,
    melody_repeat: int = 1,
    max_exercises: int = 10,
    seed: int = None,
):
    print("\n╔══════════════════════════════════════════╗")
    print("║   Lesson 2: 随机白键旋律 MIDI 生成       ║")
    print("╚══════════════════════════════════════════╝\n")

    print(f"参数: 范围 {low_note}~{high_note}, 每旋律 {note_count} 音, "
          f"重复 {melody_repeat} 次, 共 {max_exercises} 条")

    exercises, answers = build_melody_exercises(
        low_note=low_note, high_note=high_note,
        note_count=note_count, melody_repeat=melody_repeat,
        max_exercises=max_exercises, seed=seed,
    )

    print_exercises(exercises, answers)

    midi_path = create_melody_midi(exercises)
    ans_path = save_answers(answers)

    print(f"\n✅ MIDI: {midi_path}")
    print(f"✅ 答案: {ans_path}")
    print(f"\n🎵 Lesson 2 完成！")


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
        kwargs["melody_repeat"] = int(sys.argv[4])
    if len(sys.argv) > 5:
        kwargs["max_exercises"] = int(sys.argv[5])
    if len(sys.argv) > 6:
        kwargs["seed"] = int(sys.argv[6])
    main(**kwargs)
