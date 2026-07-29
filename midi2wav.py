"""
MIDI → WAV 渲染接口
====================
通过 FluidSynth + GM SoundFont 将 MIDI 渲染为 WAV 音频。

支持三种音色预设：
  - piano  : 原声大钢琴 (program 0)
  - guitar : 尼龙弦吉他 (program 24)
  - voice  : 合唱人声 (program 53)

使用 pretty_midi 自带的 TimGM6mb.sf2 作为默认音源。
可替换为更高质量的 SoundFont（如 FluidR3_GM.sf2）。
"""

# 必须在 import pretty_midi 之前设置，静音 SDL3 警告
import os
os.environ["SDL_AUDIODRIVER"] = "dummy"

import warnings
import mido
from mido import Message, MidiFile, MidiTrack
import pretty_midi

# -------------------- 配置 --------------------

# 默认 SoundFont 路径（pretty_midi 自带的）
DEFAULT_SOUNDFONT = os.path.join(
    os.path.dirname(pretty_midi.__file__), "TimGM6mb.sf2"
)

# 媒体输出目录
MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")

# 预设 → MIDI Program Number 映射
PRESET_MAP = {
    "piano":  0,   # Acoustic Grand Piano
    "guitar": 24,  # Acoustic Guitar (nylon)
    "voice":  53,  # Choir Aahs
}

# 支持的预设列表
VALID_PRESETS = list(PRESET_MAP.keys())


# -------------------- 渲染核心 --------------------


def midi_to_wav(
    midi_path: str,
    output_path: str = None,
    preset: str = "piano",
    soundfont: str = None,
    sample_rate: int = 44100,
) -> str:
    """将 MIDI 文件渲染为 WAV 音频。

    Args:
        midi_path: 输入 MIDI 文件路径
        output_path: 输出 WAV 路径，None 则自动生成
        preset: 音色预设（"piano" / "guitar" / "voice"）
        soundfont: SoundFont 路径，None 则使用默认
        sample_rate: 采样率 (Hz)

    Returns:
        输出 WAV 文件路径

    Raises:
        ValueError: preset 不合法
        FileNotFoundError: MIDI 或 SoundFont 不存在
    """
    if preset not in PRESET_MAP:
        raise ValueError(
            f"无效预设: '{preset}'，可选: {VALID_PRESETS}"
        )
    program = PRESET_MAP[preset]

    if soundfont is None:
        soundfont = DEFAULT_SOUNDFONT

    if not os.path.exists(midi_path):
        raise FileNotFoundError(f"MIDI 文件不存在: {midi_path}")
    if not os.path.exists(soundfont):
        raise FileNotFoundError(f"SoundFont 不存在: {soundfont}")
    if not midi_path.endswith(('.mid', '.midi')):
        raise ValueError(f"不是 MIDI 文件: {midi_path}")

    # 生成输出路径
    if output_path is None:
        base = os.path.splitext(os.path.basename(midi_path))[0]
        output_path = os.path.join(MEDIA_DIR, f"{base}_{preset}.wav")

    os.makedirs(os.path.dirname(output_path) or MEDIA_DIR, exist_ok=True)

    # 加载 MIDI，替换所有通道的乐器为指定 preset
    mid = MidiFile(midi_path)
    for track in mid.tracks:
        new_messages = []
        for msg in track:
            # 拦截 program_change，替换为指定音色
            if msg.type == "program_change":
                new_messages.append(
                    msg.copy(program=program)
                )
            else:
                new_messages.append(msg)
        track.clear()
        track.extend(new_messages)

    # 写入临时 MIDI（带修改后的 program）
    tmp_midi = os.path.join(MEDIA_DIR, "_tmp_render.mid")
    os.makedirs(MEDIA_DIR, exist_ok=True)
    mid.save(tmp_midi)

    # 用 pretty_midi 合成 WAV（内部调用 FluidSynth）
    try:
        pm = pretty_midi.PrettyMIDI(tmp_midi)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            # 重定向 fd 2 静音 FluidSynth C 层 SDL3 警告
            import sys
            devnull = os.open(os.devnull, os.O_WRONLY)
            old_stderr_fd = os.dup(2)
            os.dup2(devnull, 2)
            os.close(devnull)
            try:
                audio = pm.fluidsynth(fs=sample_rate, sf2_path=soundfont)
            finally:
                os.dup2(old_stderr_fd, 2)
                os.close(old_stderr_fd)

        # pretty_midi 返回 stereo，形状 (2, n_samples) 或 mono (n_samples,)
        import soundfile as sf
        if audio.ndim == 2:
            audio = audio.T  # soundfile 需要 (samples, channels)

        sf.write(output_path, audio, sample_rate)
    finally:
        # 清理临时文件
        if os.path.exists(tmp_midi):
            os.remove(tmp_midi)

    return output_path


def render_midi_all_presets(
    midi_path: str,
    output_dir: str = None,
    soundfont: str = None,
    sample_rate: int = 44100,
) -> dict:
    """用所有音色预设渲染同一个 MIDI 文件。

    Args:
        midi_path: MIDI 文件路径
        output_dir: 输出目录，默认 MEDIA_DIR
        soundfont: SoundFont 路径
        sample_rate: 采样率

    Returns:
        dict: {preset_name: wav_path}
    """
    if output_dir is None:
        output_dir = MEDIA_DIR

    results = {}
    for preset in VALID_PRESETS:
        base = os.path.splitext(os.path.basename(midi_path))[0]
        out_path = os.path.join(output_dir, f"{base}_{preset}.wav")
        results[preset] = midi_to_wav(
            midi_path, out_path, preset=preset,
            soundfont=soundfont, sample_rate=sample_rate,
        )
    return results


def render_lesson1(
    preset: str = "piano",
    soundfont: str = None,
    sample_rate: int = 44100,
) -> str:
    """便捷方法：渲染 lesson1 的练习 MIDI 为 WAV。

    Args:
        preset: 音色预设，默认 piano，传 "all" 渲染全部三种
        soundfont: SoundFont 路径
        sample_rate: 采样率

    Returns:
        str: WAV 文件路径（单预设时），或打印全部（all 时）
    """
    midi_path = os.path.join(MEDIA_DIR, "lesson1_exercises.mid")
    if not os.path.exists(midi_path):
        raise FileNotFoundError(
            f"找不到 {midi_path}，请先运行 lesson1.py 生成 MIDI"
        )

    if preset == "all":
        return render_midi_all_presets(
            midi_path, soundfont=soundfont, sample_rate=sample_rate,
        )
    else:
        base = os.path.splitext(os.path.basename(midi_path))[0]
        out_path = os.path.join(MEDIA_DIR, f"{base}_{preset}.wav")
        return midi_to_wav(
            midi_path, out_path, preset=preset,
            soundfont=soundfont, sample_rate=sample_rate,
        )


# -------------------- 信息 --------------------


def print_presets():
    """打印可用预设。"""
    print("可用音色预设:")
    print(f"  {'预设':<10} {'Program':<8} {'说明'}")
    print("-" * 40)
    descriptions = {
        "piano": "原声大钢琴",
        "guitar": "尼龙弦吉他",
        "voice": "合唱人声",
    }
    for name, prog in PRESET_MAP.items():
        print(f"  {name:<10} {prog:<8} {descriptions.get(name, '')}")


def print_soundfont_info(soundfont: str = None):
    """打印 SoundFont 信息。"""
    if soundfont is None:
        soundfont = DEFAULT_SOUNDFONT
    print(f"SoundFont: {soundfont}")
    if os.path.exists(soundfont):
        size_mb = os.path.getsize(soundfont) / (1024 * 1024)
        print(f"  大小: {size_mb:.1f} MB")
    else:
        print("  ⚠️  文件不存在")


# -------------------- 主程序 --------------------


def main():
    """渲染 lesson1 的 MIDI 为 WAV。

    用法:
        python midi2wav.py              # 默认 piano
        python midi2wav.py guitar       # 指定吉他
        python midi2wav.py voice        # 指定人声
        python midi2wav.py all          # 全部三种
        python midi2wav.py piano /path/to/file.mid  # 指定 MIDI 文件
    """
    import sys

    # 解析参数
    preset = sys.argv[1] if len(sys.argv) > 1 else "piano"
    midi_file = sys.argv[2] if len(sys.argv) > 2 else None

    if preset not in VALID_PRESETS and preset != "all":
        print(f"❌ 无效预设: '{preset}'，可选: {VALID_PRESETS} / all")
        sys.exit(1)

    print(f"\n🎵 MIDI → WAV 渲染  |  音色: {preset}")
    print(f"   SoundFont: {os.path.basename(DEFAULT_SOUNDFONT)}")

    try:
        if midi_file:
            # 渲染指定 MIDI 文件
            if preset == "all":
                results = render_midi_all_presets(midi_file)
                for p, path in results.items():
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    print(f"   ✅ {p:<8} → {os.path.basename(path)}  ({size_mb:.1f} MB)")
            else:
                path = midi_to_wav(midi_file, preset=preset)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"   ✅ {os.path.basename(path)}  ({size_mb:.1f} MB)")
        else:
            # 默认渲染 lesson1
            if preset == "all":
                results = render_lesson1(preset="all")
                for p, path in results.items():
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    print(f"   ✅ {p:<8} → {os.path.basename(path)}  ({size_mb:.1f} MB)")
            else:
                path = render_lesson1(preset=preset)
                size_mb = os.path.getsize(path) / (1024 * 1024)
                print(f"   ✅ {os.path.basename(path)}  ({size_mb:.1f} MB)")
    except FileNotFoundError as e:
        print(f"\n⚠️  {e}")
    except Exception as e:
        print(f"\n❌ 渲染失败: {e}")


if __name__ == "__main__":
    main()
