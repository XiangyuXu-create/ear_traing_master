"""
练耳训练 Web 服务
=================
基于 Gradio 的钢琴白键练耳交互界面。
支持三种音色（piano/guitar/voice），全部答完后统一出结果，错题进入易错题集。
"""

import gradio as gr
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ear_traing_lesson.lesson1 import build_exercise_patterns
from midi2wav import midi_to_wav

MEDIA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media")
MISTAKE_FILE = os.path.join(MEDIA_DIR, "mistake_collection.json")
os.makedirs(MEDIA_DIR, exist_ok=True)

# 完整白键 A1~A6（供下拉框选择范围）


def _build_all_white_keys():
    """生成 A1~A6 所有白键列表（按音高排序）。"""
    from ear_traing_lesson.lesson1 import midi_note
    notes = []
    for octave in range(1, 7):
        for name in ["C", "D", "E", "F", "G", "A", "B"]:
            n = midi_note(name, octave)
            if 21 <= n <= 108:
                notes.append(f"{name}{octave}")
    # 按 MIDI 音高排序
    notes.sort(key=lambda x: midi_note(x[0], int(x[1:])))
    return notes


ALL_NOTES = _build_all_white_keys()


def _notes_in_range(low: str, high: str):
    """返回范围内所有白键。"""
    if low not in ALL_NOTES or high not in ALL_NOTES:
        return ALL_NOTES
    lo = ALL_NOTES.index(low)
    hi = ALL_NOTES.index(high)
    if lo > hi:
        lo, hi = hi, lo
    return ALL_NOTES[lo:hi + 1]


# -------------------- 渲染单个练习 --------------------

def _render_exercise_wav(exercise: list, preset: str, index: int) -> str:
    from mido import MidiFile, MidiTrack, Message, MetaMessage
    mid = MidiFile(ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage("track_name", name="Ex", time=0))
    track.append(MetaMessage("set_tempo", tempo=500000, time=0))
    track.append(Message("program_change", channel=0, program=0, time=0))
    for i, (_name, _oct, note_num) in enumerate(exercise):
        dt = 0 if i == 0 else 480
        track.append(Message("note_on", channel=0, note=note_num, velocity=80, time=dt))
        track.append(Message("note_off", channel=0, note=note_num, velocity=0, time=480))
    tmp_mid = os.path.join(MEDIA_DIR, f"_tmp_{index}.mid")
    mid.save(tmp_mid)
    wav_path = os.path.join(MEDIA_DIR, f"_tmp_{index}_{preset}.wav")
    result = midi_to_wav(tmp_mid, wav_path, preset=preset)
    os.remove(tmp_mid)
    return result


# -------------------- 易错题集 --------------------

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


# -------------------- 会话管理 --------------------

def generate_session(low_note, high_note, repeat_count, max_exercises, preset):
    exercises, answers = build_exercise_patterns(
        low_note=low_note, high_note=high_note,
        repeat_count=int(repeat_count), max_exercises=int(max_exercises), seed=None,
    )
    total = len(exercises)
    wav_paths = [None] * total
    wav_paths[0] = _render_exercise_wav(exercises[0], preset, 0)

    state = {
        "answers": answers, "exercises": exercises,
        "wav_paths": wav_paths, "current": 0,
        "total": total, "preset": preset,
        "user_answers": [], "is_finished": False,
    }
    progress = f"第 1/{total} 题"
    range_choices = _notes_in_range(low_note, high_note)
    return (
        state, wav_paths[0], progress,
        gr.update(choices=range_choices, value=None, interactive=True),
        gr.update(visible=True), gr.update(visible=False),
        "", [], gr.update(choices=[], visible=False),
        format_mistakes(),
    )


def submit_and_continue(state, guess):
    if state is None:
        return (None, None, "⚠️ 请先生成练习",
                gr.update(interactive=False),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False),
                format_mistakes())

    idx = state["current"]
    correct = state["answers"][idx]
    guess = guess.strip().upper()

    state["user_answers"].append({
        "index": idx, "guess": guess,
        "correct": correct, "is_correct": (guess == correct),
    })

    is_last = (idx + 1 >= state["total"])

    if is_last:
        return finish_session(state)
    else:
        state["current"] += 1
        new_idx = state["current"]
        if state["wav_paths"][new_idx] is None:
            state["wav_paths"][new_idx] = _render_exercise_wav(
                state["exercises"][new_idx], state["preset"], new_idx)
        progress = f"第 {new_idx+1}/{state['total']} 题"
        return (
            state, state["wav_paths"][new_idx], progress,
            gr.update(value=None, interactive=True),
            gr.update(visible=True), gr.update(visible=False),
            "", [], gr.update(choices=[], visible=False),
            format_mistakes(),
        )


def finish_session(state):
    total = state["total"]
    correct_count = sum(1 for a in state["user_answers"] if a["is_correct"])
    wrong_count = total - correct_count
    accuracy = correct_count / total * 100 if total > 0 else 0
    state["is_finished"] = True

    wrong_notes = [a["correct"] for a in state["user_answers"] if not a["is_correct"]]
    wrong_str = ", ".join(wrong_notes) if wrong_notes else "无"

    # 每题详情表
    table_data = []
    for a in state["user_answers"]:
        table_data.append([
            f"第{a['index']+1}题",
            a["guess"],
            a["correct"],
            "✅" if a["is_correct"] else "❌",
        ])

    result_md = (
        f"## 🎉 练习完成！\n\n"
        f"| 指标 | 值 |\n|------|----|\n"
        f"| 正确 | {correct_count} / {total} |\n"
        f"| 正确率 | **{accuracy:.0f}%** |\n"
        f"| 错误 | {wrong_count} 题 ({wrong_str}) |"
    )

    progress = f"第 {total}/{total} 题 (已完成)"

    replay_choices = [f"第{i+1}题" for i in range(total)]

    if wrong_notes:
        add_mistakes(wrong_notes)

    return (
        state, None, progress,
        gr.update(choices=[], interactive=False),
        gr.update(visible=False), gr.update(visible=True),
        result_md, table_data,
        gr.update(choices=replay_choices, value=replay_choices[0], visible=True),
        format_mistakes(),
    )


def replay_selected(state, selection):
    """在结果页重放指定题目。"""
    if state is None or not state["is_finished"]:
        return None
    # selection 格式: "第3题"
    try:
        idx = int(selection.replace("第", "").replace("题", "")) - 1
        if 0 <= idx < state["total"]:
            # 确保已渲染
            if state["wav_paths"][idx] is None:
                state["wav_paths"][idx] = _render_exercise_wav(
                    state["exercises"][idx], state["preset"], idx)
            return state["wav_paths"][idx]
    except (ValueError, IndexError):
        pass
    return None


def replay_current(state):
    if state is None or state["is_finished"]:
        return None
    idx = state["current"]
    if state["wav_paths"][idx]:
        return state["wav_paths"][idx]
    return None


# -------------------- Gradio UI --------------------

CSS = """
.gradio-container { max-width: 750px !important; margin: 0 auto !important; }
#main-title { text-align: center; font-size: 2.2em !important; font-weight: 700 !important;
              font-family: 'DejaVu Sans Mono', 'Consolas', 'Menlo', 'Courier New', monospace !important;
              letter-spacing: 4px; }
#subtitle { text-align: center; }
"""

with gr.Blocks(title="ear_traing_master") as demo:
    gr.Markdown("""<h1 id='main-title'>EAR TRAING MASTER</h1>
        <p id='subtitle'>A4=440Hz 标准音</p>""")

    state = gr.State(None)

    # ---- 配置区 ----
    with gr.Row():
        low_note = gr.Dropdown(choices=ALL_NOTES, value="A3", label="最低音", scale=1)
        high_note = gr.Dropdown(choices=ALL_NOTES, value="D5", label="最高音", scale=1)
        repeat_count = gr.Slider(1, 10, value=3, step=1, label="重复次数", scale=1)
        max_exercises = gr.Slider(1, 20, value=10, step=1, label="练习条数", scale=1)

    with gr.Row():
        preset = gr.Radio(choices=["piano", "guitar", "voice"], value="piano", label="音色")

    gen_btn = gr.Button("🎵 生成新练习", variant="primary", size="lg")
    gr.Markdown("---")

    # ---- 练习区（答题时可见） ----
    with gr.Column(visible=True) as exercise_panel:
        progress_text = gr.Textbox(value="等待生成...", label="进度", interactive=False)
        replay_btn = gr.Button("🔄 重播", scale=0)

        audio_player = gr.Audio(label="🎧 点击播放", type="filepath", interactive=False)

        answer_radio = gr.Radio(
            choices=_notes_in_range("A3", "D5"),
            label="🎯 选择你听到的音", interactive=True, value=None,
        )
        submit_btn = gr.Button("✅ 提交答案", variant="primary")

    # ---- 结果区（完成后可见） ----
    with gr.Column(visible=False) as result_panel:
        gr.Markdown("---")
        result_md = gr.Markdown("")
        result_df = gr.Dataframe(
            headers=["题号", "你的答案", "正确答案", "结果"],
            label="每题详情", interactive=False,
        )
        with gr.Row():
            replay_dropdown = gr.Dropdown(
                choices=[], label="选择题目重听", scale=2, visible=False,
            )
            replay_result_btn = gr.Button("🔊 播放此题", scale=1)
        result_audio = gr.Audio(label="🎧 重听", type="filepath", interactive=False)

    # ---- 易错题集 ----
    with gr.Accordion("📊 易错题集（历史错题统计）", open=False):
        mistake_display = gr.Textbox(
            value=format_mistakes(), label="错题记录", interactive=False, lines=8,
        )

    # ---- 事件绑定 ----
    outputs_all = [
        state, audio_player, progress_text, answer_radio,
        exercise_panel, result_panel,
        result_md, result_df, replay_dropdown,
        mistake_display,
    ]

    gen_btn.click(
        fn=generate_session,
        inputs=[low_note, high_note, repeat_count, max_exercises, preset],
        outputs=outputs_all,
    )

    submit_btn.click(
        fn=submit_and_continue,
        inputs=[state, answer_radio],
        outputs=outputs_all,
    )

    replay_btn.click(
        fn=replay_current, inputs=[state], outputs=[audio_player],
    )

    replay_result_btn.click(
        fn=replay_selected,
        inputs=[state, replay_dropdown],
        outputs=[result_audio],
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=CSS)
