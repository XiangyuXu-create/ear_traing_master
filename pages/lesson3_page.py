"""Lesson 3 UI: 单音辨听（全音阶，含黑键）。"""

import gradio as gr
from ear_traing_lesson.lesson3 import build_exercise_patterns
from pages.common import (
    ALL_CHROMATIC, chromatic_notes_in_range, render_exercise_wav,
    add_mistakes, format_mistakes,
)


def build_ui(mistake_display):
    state = gr.State(None)

    gr.Markdown("""
> 🎹 **训练目标**：与 Lesson 1 相同模式，但候选音包含**所有黑键**（半音阶）。
> 模式：`A4 → X → A4 → X → A4 → X`（X 为范围内任意半音，含 C# D# F# G# A#）
    """)

    with gr.Row():
        l3_low = gr.Dropdown(choices=ALL_CHROMATIC, value="A3", label="最低音", scale=1)
        l3_high = gr.Dropdown(choices=ALL_CHROMATIC, value="D5", label="最高音", scale=1)
        l3_repeat = gr.Slider(1, 10, value=3, step=1, label="重复次数", scale=1)
        l3_count = gr.Slider(1, 20, value=10, step=1, label="练习条数", scale=1)

    with gr.Row():
        l3_preset = gr.Radio(choices=["piano", "guitar", "voice"], value="piano", label="音色")

    l3_gen = gr.Button("🎵 生成新练习", variant="primary")

    with gr.Column(visible=True) as l3_exercise:
        l3_progress = gr.Textbox(value="等待生成...", label="进度", interactive=False)
        l3_replay_btn = gr.Button("🔄 重播", scale=0)
        l3_audio = gr.Audio(label="🎧 点击播放", type="filepath", interactive=False)
        l3_radio = gr.Radio(
            choices=chromatic_notes_in_range("A3", "D5"),
            label="🎯 选择你听到的音（含黑键）", interactive=True, value=None,
        )
        l3_submit = gr.Button("✅ 提交答案", variant="primary")

    with gr.Column(visible=False) as l3_result:
        l3_result_md = gr.Markdown("")
        l3_result_df = gr.Dataframe(
            headers=["题号", "你的答案", "正确答案", "结果"], label="每题详情", interactive=False,
        )
        with gr.Row():
            l3_replay_dd = gr.Dropdown(choices=[], label="重听题目", scale=2, visible=False)
            l3_replay_btn2 = gr.Button("🔊 播放", scale=1)
        l3_result_audio = gr.Audio(label="🎧 重听", type="filepath", interactive=False)

    # ---- 逻辑（与 Lesson 1 相同，仅数据源不同） ----

    def gen(low, high, repeat, count, preset):
        exercises, answers = build_exercise_patterns(
            low_note=low, high_note=high,
            repeat_count=int(repeat), max_exercises=int(count), seed=None,
        )
        total = len(exercises)
        wavs = [None] * total
        wavs[0] = render_exercise_wav(exercises[0], preset, 0, "l3")
        st = {"answers": answers, "exercises": exercises, "wav_paths": wavs,
              "current": 0, "total": total, "preset": preset,
              "user_answers": [], "is_finished": False}
        return (st, wavs[0], f"第 1/{total} 题",
                gr.update(choices=chromatic_notes_in_range(low, high), value=None, interactive=True),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def submit(st, guess):
        if st is None or guess is None:
            if st is None:
                return (None, None, "⚠️ 请先生成练习",
                        gr.update(interactive=False),
                        gr.update(visible=True), gr.update(visible=False),
                        "", [], gr.update(choices=[], visible=False), format_mistakes())
            return (st, st["wav_paths"][st["current"]], f"第 {st['current']+1}/{st['total']} 题",
                    gr.update(interactive=True),
                    gr.update(visible=True), gr.update(visible=False),
                    "", [], gr.update(choices=[], visible=False), format_mistakes())

        idx = st["current"]
        correct = st["answers"][idx]
        st["user_answers"].append({"index": idx, "guess": guess.strip().upper(),
                                   "correct": correct, "is_correct": (guess.strip().upper() == correct)})
        if idx + 1 >= st["total"]:
            return _finish(st)
        st["current"] += 1
        n = st["current"]
        if st["wav_paths"][n] is None:
            st["wav_paths"][n] = render_exercise_wav(st["exercises"][n], st["preset"], n, "l3")
        return (st, st["wav_paths"][n], f"第 {n+1}/{st['total']} 题",
                gr.update(value=None, interactive=True),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def _finish(st):
        total = st["total"]
        correct_count = sum(1 for a in st["user_answers"] if a["is_correct"])
        wrong_count = total - correct_count
        acc = correct_count / total * 100 if total > 0 else 0
        st["is_finished"] = True
        wrong_notes = [a["correct"] for a in st["user_answers"] if not a["is_correct"]]
        wrong_str = ", ".join(wrong_notes) if wrong_notes else "无"
        table = [[f"第{a['index']+1}题", a["guess"], a["correct"],
                  "✅" if a["is_correct"] else "❌"] for a in st["user_answers"]]
        md = (f"## 🎉 练习完成！\n\n| 指标 | 值 |\n|------|----|\n"
              f"| 正确 | {correct_count} / {total} |\n"
              f"| 正确率 | **{acc:.0f}%** |\n"
              f"| 错误 | {wrong_count} 题 ({wrong_str}) |")
        replay_choices = [f"第{i+1}题" for i in range(total)]
        if wrong_notes:
            add_mistakes(wrong_notes)
        return (st, None, f"第 {total}/{total} 题 (已完成)",
                gr.update(choices=[], interactive=False),
                gr.update(visible=False), gr.update(visible=True),
                md, table,
                gr.update(choices=replay_choices, value=replay_choices[0], visible=True),
                format_mistakes())

    def replay(st):
        if st is None or st["is_finished"]:
            return None
        idx = st["current"]
        return st["wav_paths"][idx] if st["wav_paths"][idx] else None

    def replay_result(st, sel):
        if st is None or not st["is_finished"]:
            return None
        try:
            idx = int(sel.replace("第", "").replace("题", "")) - 1
            if 0 <= idx < st["total"]:
                if st["wav_paths"][idx] is None:
                    st["wav_paths"][idx] = render_exercise_wav(st["exercises"][idx], st["preset"], idx, "l3")
                return st["wav_paths"][idx]
        except (ValueError, IndexError):
            pass
        return None

    out = [state, l3_audio, l3_progress, l3_radio,
           l3_exercise, l3_result, l3_result_md, l3_result_df, l3_replay_dd, mistake_display]

    l3_gen.click(fn=gen, inputs=[l3_low, l3_high, l3_repeat, l3_count, l3_preset], outputs=out)
    l3_submit.click(fn=submit, inputs=[state, l3_radio], outputs=out)
    l3_replay_btn.click(fn=replay, inputs=[state], outputs=[l3_audio])
    l3_replay_btn2.click(fn=replay_result, inputs=[state, l3_replay_dd], outputs=[l3_result_audio])
