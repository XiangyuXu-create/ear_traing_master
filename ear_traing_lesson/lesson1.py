"""
Lesson 1: 钢琴白键 MIDI 练耳音轨生成
=====================================
从 A4=440Hz（标准音）开始，每个练习以 A4 开头，
然后 A4 与范围内随机白键交替重复，训练音高辨别能力。

参数：
  - 最低音（low_note）：随机白键范围下限，默认 "A3"
  - 最高音（high_note）：随机白键范围上限，默认 "D5"
  - 重复次数（repeat_count）：A4-随机音 交替次数，默认 3
  - 练习条数（max_exercises）：生成练习条数上限，默认 10

练习示例（repeat_count=3）：
  随机到 D5 → A4 D5 A4 D5 A4 D5
  随机到 A3 → A4 A3 A4 A3 A4 A3

白键 MIDI 音符编号（标准钢琴 88 键，A0~C8）：
  八度 →  0   1   2   3   4   5   6   7   8
  A      21  33  45  57  69  81  93  105
  B      23  35  47  59  71  83  95  107
  C      24  36  48  60  72  84  96  108
  D      26  38  50  62  74  86  98
  E      28  40  52  64  76  88  100
  F      29  41  53  65  77  89  101
  G      31  43  55  67  79  91  103

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
NOTE_DURATION = 480        # 每个音符的 tick 时长（480 = 四分音符）
TEMPO = 500000             # 微秒/拍（500000 = 120 BPM）
VELOCITY = 80              # 按键力度 (0~127)
DEFAULT_CHANNEL = 0        # MIDI 通道（钢琴通常用通道 0）

# A4 标准音
A4_MIDI = 69
A4_NOTE = ("A", 4, A4_MIDI)

# -------------------- 钢琴白键 --------------------

# 白键名（自然音）
WHITE_KEY_NAMES = ["A", "B", "C", "D", "E", "F", "G"]

# 白键在八度内的半音偏移量（相对于 C）
# C=0, D=2, E=4, F=5, G=7, A=9, B=11
WHITE_KEY_OFFSETS_FROM_C = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def midi_note(name: str, octave: int) -> int:
    """根据音名和八度返回 MIDI 音符编号。"""
    if name not in WHITE_KEY_OFFSETS_FROM_C:
        raise ValueError(f"无效音名: {name}，只支持 {WHITE_KEY_NAMES}")
    offset = WHITE_KEY_OFFSETS_FROM_C[name]
    return (octave + 1) * 12 + offset


def parse_note_str(note_str: str):
    """解析 "A3", "D5" 格式的音符字符串。

    Returns:
        (音名, 八度, MIDI编号)
    """
    match = re.match(r"^([A-G])([b#]?)(-?\d+)$", note_str.upper())
    if not match:
        raise ValueError(f"无法解析音符字符串: {note_str}")
    name = match.group(1)
    accidental = match.group(2)
    octave = int(match.group(3))
    if accidental:
        raise ValueError(f"暂时只支持白键（无升降号），收到: {note_str}")
    return (name, octave, midi_note(name, octave))


def midi_to_frequency(note: int) -> float:
    """将 MIDI 音符编号转换为频率 (Hz)。"""
    return 440.0 * (2 ** ((note - 69) / 12))


def frequency_to_midi(freq: float) -> float:
    """将频率 (Hz) 转换为 MIDI 音符编号。"""
    import math
    return 69 + 12 * math.log2(freq / 440)


# -------------------- 白键范围构建 --------------------


def build_white_keys_in_range(low_note_str: str, high_note_str: str):
    """获取两个音符之间（含）的所有白键。

    Returns:
        List[Tuple[str, int, int]]: 白键列表
    """
    _, _, low_midi = parse_note_str(low_note_str)
    _, _, high_midi = parse_note_str(high_note_str)
    actual_low = min(low_midi, high_midi)
    actual_high = max(low_midi, high_midi)

    keys = []
    for octave in range(0, 9):
        for name in WHITE_KEY_NAMES:
            note_num = midi_note(name, octave)
            if actual_low <= note_num <= actual_high and note_num <= 127:
                keys.append((name, octave, note_num))
    return keys


def build_white_keys(start_note="A", start_octave=0, end_octave=8):
    """构建从指定音开始到指定八度的白键列表。"""
    keys = []
    start_idx = WHITE_KEY_NAMES.index(start_note)
    for octave in range(start_octave, end_octave + 1):
        for i, name in enumerate(WHITE_KEY_NAMES):
            if octave == start_octave and i < start_idx:
                continue
            note_num = midi_note(name, octave)
            if note_num > 127:
                continue
            keys.append((name, octave, note_num))
    return keys


# -------------------- 练习模式生成 --------------------


def build_exercise_patterns(
    low_note: str = "A3",
    high_note: str = "D5",
    repeat_count: int = 3,
    max_exercises: int = 10,
    seed: int = None,
):
    """生成练耳练习：每条以 A4 开头，与范围内随机白键交替重复。

    练习结构（repeat_count=3 为例）：
        A4 → 随机音 → A4 → 随机音 → A4 → 随机音

    Args:
        low_note: 随机白键范围下限，默认 "A3"
        high_note: 随机白键范围上限，默认 "D2"
        repeat_count: A4-随机音 交替重复次数，默认 3
        max_exercises: 最多生成几条练习，默认 10
        seed: 随机种子（用于复现），None 则每次不同

    Returns:
        Tuple[List[List[Tuple]], List[str]]:
        (exercises, answers)
        - exercises: 每条练习的音符序列
        - answers: 每条练习对应的随机音名，如 ["A3", "D4", "C4", ...]
    """
    if seed is not None:
        random.seed(seed)

    # 获取范围内的候选白键
    candidates = build_white_keys_in_range(low_note, high_note)

    # 排除 A4 本身
    candidates = [k for k in candidates if k[2] != A4_MIDI]

    if not candidates:
        raise ValueError(
            f"范围 [{low_note}~{high_note}] 内没有可用的白键（排除A4后）"
        )

    # 随机选取 max_exercises 个（去重），保持随机顺序
    num_pick = min(max_exercises, len(candidates))
    selected = random.sample(candidates, num_pick)

    # 构建每条练习：A4 开头，交替 repeat_count 次
    exercises = []
    answers = []
    for target_key in selected:
        pattern = []
        for i in range(repeat_count):
            pattern.append(A4_NOTE)       # A4
            pattern.append(target_key)    # 随机白键
        exercises.append(pattern)
        # 答案格式: "A3", "D4" 等
        answers.append(f"{target_key[0]}{target_key[1]}")

    return exercises, answers


def create_exercise_midi(
    exercises: list,
    filename: str = "lesson1_exercises.mid",
    note_duration: int = NOTE_DURATION,
    tempo: int = TEMPO,
    velocity: int = VELOCITY,
    channel: int = DEFAULT_CHANNEL,
    gap_duration: int = None,
) -> str:
    """将练习列表生成 MIDI 文件，每条练习之间插入休止间隔。

    Returns:
        输出文件路径
    """
    if gap_duration is None:
        gap_duration = note_duration * 2  # 练习间休止两拍

    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)

    track.append(MetaMessage("track_name", name="Lesson1 Exercises", time=0))
    track.append(MetaMessage("set_tempo", tempo=tempo, time=0))
    track.append(Message("program_change", channel=channel, program=0, time=0))

    for ex_idx, exercise in enumerate(exercises):
        for i, (name, octave, note_num) in enumerate(exercise):
            if ex_idx == 0 and i == 0:
                time_delta = 0
            elif i == 0:
                # 新练习开始，多加休止间隔
                time_delta = note_duration + gap_duration
            else:
                time_delta = note_duration

            track.append(Message("note_on", channel=channel, note=note_num,
                                 velocity=velocity, time=time_delta))
            track.append(Message("note_off", channel=channel, note=note_num,
                                 velocity=0, time=note_duration))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    mid.save(filepath)
    return filepath


def save_answers(answers: list, filename: str = "lesson1_answers.json"):
    """保存答案到 JSON 文件。

    Args:
        answers: 音名列表，如 ["D4", "B4", "A3", ...]
        filename: JSON 文件名

    Returns:
        文件路径
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump({"answers": answers}, f, ensure_ascii=False, indent=2)
    return filepath


# -------------------- 打印信息 --------------------


def print_white_key_table():
    """打印白键对照表（MIDI 编号 ↔ 频率）。"""
    print("=" * 55)
    print("  钢琴白键对照表（A0 ~ C8）")
    print("=" * 55)
    print(f"  {'音名':<6} {'MIDI':<6} {'频率(Hz)':<12} {'说明'}")
    print("-" * 55)
    all_keys = build_white_keys("A", 0, 8)
    for name, octave, note_num in all_keys:
        freq = midi_to_frequency(note_num)
        marker = " ← A4=440Hz 标准音" if (name == "A" and octave == 4) else ""
        print(f"  {name}{octave:<4} {note_num:<6} {freq:<12.2f} {marker}")
    print("-" * 55)
    print(f"  共 {len(all_keys)} 个白键")


def print_exercises(exercises: list):
    """打印练习内容。"""
    print(f"\n{'序号':<5} {'随机音':<8} {'MIDI':<6} {'频率(Hz)':<10} {'练习序列'}")
    print("-" * 70)
    for idx, exercise in enumerate(exercises, 1):
        target = exercise[1]  # 第2个音符就是随机音
        t_name, t_oct, t_midi = target
        t_freq = midi_to_frequency(t_midi)
        seq_parts = []
        for name, octave, note_num in exercise:
            marker = "★" if note_num == A4_MIDI else ""
            seq_parts.append(f"{name}{octave}{marker}")
        seq_str = " → ".join(seq_parts)
        print(f"{idx:<5} {t_name}{t_oct:<7} {t_midi:<6} {t_freq:<10.1f} {seq_str}")


# -------------------- 主程序 --------------------


def main(
    low_note: str = "A3",
    high_note: str = "D5",
    repeat_count: int = 3,
    max_exercises: int = 10,
    seed: int = None,
):
    """Lesson 1 主程序：生成钢琴白键练耳 MIDI 音轨。

    Args:
        low_note: 随机白键范围下限，默认 "A3"
        high_note: 随机白键范围上限，默认 "D5"
        repeat_count: A4-随机音 交替重复次数，默认 3
        max_exercises: 最多生成练习条数，默认 10
        seed: 随机种子，None 则每次不同
    """
    print("\n╔══════════════════════════════════════════╗")
    print("║   Lesson 1: 钢琴白键练耳 MIDI 音轨生成 ║")
    print("║        A4 = 440Hz 标准音高              ║")
    print("╚══════════════════════════════════════════╝\n")

    # 参数摘要
    _, _, low_midi = parse_note_str(low_note)
    _, _, high_midi = parse_note_str(high_note)
    actual_low = min(low_midi, high_midi)
    actual_high = max(low_midi, high_midi)

    print(f"参数配置:")
    print(f"  随机白键范围: {low_note}~{high_note} "
          f"(MIDI {actual_low}~{actual_high})")
    print(f"  重复次数: {repeat_count}（每条练习 "
          f"{2 * repeat_count} 个音符）")
    print(f"  练习条数上限: {max_exercises}")
    if seed is not None:
        print(f"  随机种子: {seed}")
    print()

    # 1. 候选白键
    candidates = build_white_keys_in_range(low_note, high_note)
    candidates_no_a4 = [k for k in candidates if k[2] != A4_MIDI]
    print(f"范围内白键: {len(candidates)} 个，排除 A4 后可随机: {len(candidates_no_a4)} 个")
    print(f"候选音: ", end="")
    for name, octave, note_num in candidates:
        marker = "(A4标准音)" if note_num == A4_MIDI else ""
        print(f"{name}{octave}{marker}", end="  ")
    print()

    # 2. 生成练习
    print("\n" + "=" * 70)
    print("  练耳练习（每条以 ★A4 开头，交替重复）")
    print("=" * 70)

    exercises, answers = build_exercise_patterns(
        low_note=low_note,
        high_note=high_note,
        repeat_count=repeat_count,
        max_exercises=max_exercises,
        seed=seed,
    )
    print_exercises(exercises)

    # 3. 生成 MIDI 文件
    print("\n" + "=" * 70)
    print("  生成 MIDI 文件")
    print("=" * 70)

    filepath = create_exercise_midi(exercises, filename="lesson1_exercises.mid")
    print(f"\n✅ 练习 MIDI: {filepath}")
    print(f"   {len(exercises)} 条练习，共 {sum(len(e) for e in exercises)} 个音符")

    # 4. A4 参考音
    a4_exercise = [[A4_NOTE]]
    a4_ref_path = create_exercise_midi(a4_exercise, filename="lesson1_A4_reference.mid")
    print(f"✅ A4 参考音: {a4_ref_path}")

    # 5. 保存答案
    answer_path = save_answers(answers, filename="lesson1_answers.json")
    print(f"✅ 答案文件: {answer_path}")
    print(f"   答案序列: {answers}")

    print("\n🎹 Lesson 1 完成！")


if __name__ == "__main__":
    import sys

    # 支持命令行参数: python lesson1.py [low_note] [high_note] [repeat_count] [max_exercises] [seed]
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
