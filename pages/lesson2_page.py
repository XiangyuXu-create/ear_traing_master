"""Lesson 2 UI: 旋律辨听（逐音作答）。"""

import gradio as gr
from ear_traing_lesson.lesson2 import build_melody_exercises
from pages.common import (
    ALL_NOTES, notes_in_range, render_exercise_wav,
    add_mistakes, format_mistakes,
)


def build_ui(mistake_display):
    """构建 Lesson 2 的 Gradio 组件并绑定事件。"""
    state = gr.State(None)

    with gr.Row():
        l2_low = gr.Dropdown(choices=ALL_NOTES, value="A3", label="最低音", scale=1)
        l2_high = gr.Dropdown(choices=ALL_NOTES, value="D5", label="最高音", scale=1)
        l2_note_cnt = gr.Slider(2, 8, value=4, step=1, label="音符数量", scale=1)
        l2_count = gr.Slider(1, 20, value=10, step=1, label="练习条数", scale=1)

    with gr.Row():
        l2_preset = gr.Radio(choices=["piano", "guitar", "voice"], value="piano", label="音色")

    l2_gen = gr.Button("🎵 生成新练习", variant="primary")

    with gr.Column(visible=True) as l2_exercise:
        l2_progress = gr.Textbox(value="等待生成...", label="进度", interactive=False)
        l2_replay_btn = gr.Button("🔄 重播整段旋律", scale=0)
        l2_audio = gr.Audio(label="🎧 先听完整旋律", type="filepath", interactive=False)
        l2_note_label = gr.Markdown("")
        l2_radio = gr.Radio(
            choices=notes_in_range("A3", "D5"),
            label="🎯 逐音选择", interactive=True, value=None,
        )
        l2_submit = gr.Button("✅ 提交", variant="primary")

    with gr.Column(visible=False) as l2_result:
        l2_result_md = gr.Markdown("")
        l2_result_df = gr.Dataframe(
            headers=["旋律", "你的答案", "正确答案", "正确数"], label="详情", interactive=False,
        )
        with gr.Row():
            l2_replay_dd = gr.Dropdown(choices=[], label="重听旋律", scale=2, visible=False)
            l2_replay_btn2 = gr.Button("🔊 播放", scale=1)
        l2_result_audio = gr.Audio(label="🎧 重听", type="filepath", interactive=False)

    # ---- 逻辑 ----

    def gen(low, high, note_cnt, count, preset):
        exercises, answers = build_melody_exercises(
            low_note=low, high_note=high,
            note_count=int(note_cnt), melody_repeat=1,
            max_exercises=int(count), seed=None,
        )
        total = len(exercises)
        wavs = [None] * total
        wavs[0] = render_exercise_wav(exercises[0], preset, 0, "l2")
        st = {"answers": answers, "exercises": exercises, "wav_paths": wavs,
              "ex_idx": 0, "note_idx": 0,
              "total_ex": total, "notes_per_ex": len(answers[0]),
              "preset": preset, "user_answers": [], "is_finished": False,
              "low": low, "high": high}
        label = f"### 🎯 旋律 1/{total} — 第 1/{st['notes_per_ex']} 个音"
        return (st, wavs[0], f"旋律 1/{total}", label,
                gr.update(choices=notes_in_range(low, high), value=None, interactive=True),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def submit(st, guess):
        if st is None or guess is None:
            if st is None:
                return (None, None, "⚠️ 请先生成", "",
                        gr.update(interactive=False),
                        gr.update(visible=True), gr.update(visible=False),
                        "", [], gr.update(choices=[], visible=False), format_mistakes())
            return (st, st["wav_paths"][st["ex_idx"]], f"旋律 {st['ex_idx']+1}/{st['total_ex']}", "",
                    gr.update(value=None, interactive=True),
                    gr.update(visible=True), gr.update(visible=False),
                    "", [], gr.update(choices=[], visible=False), format_mistakes())

        ex = st["ex_idx"]
        ni = st["note_idx"]
        correct = st["answers"][ex][ni]

        while len(st["user_answers"]) <= ex:
            st["user_answers"].append([])
        st["user_answers"][ex].append({
            "note_idx": ni, "guess": guess.strip().upper(),
            "correct": correct, "is_correct": (guess.strip().upper() == correct),
        })

        ni += 1
        if ni >= st["notes_per_ex"]:
            ex += 1
            ni = 0
            if ex >= st["total_ex"]:
                return _finish(st)
            st["ex_idx"] = ex
            st["note_idx"] = 0
            if st["wav_paths"][ex] is None:
                st["wav_paths"][ex] = render_exercise_wav(st["exercises"][ex], st["preset"], ex, "l2")
            audio = st["wav_paths"][ex]
        else:
            st["note_idx"] = ni
            audio = st["wav_paths"][ex]

        label = f"### 🎯 旋律 {st['ex_idx']+1}/{st['total_ex']} — 第 {st['note_idx']+1}/{st['notes_per_ex']} 个音"
        return (st, audio, f"旋律 {st['ex_idx']+1}/{st['total_ex']}", label,
                gr.update(value=None, interactive=True),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def _finish(st):
        total_melodies = st["total_ex"]
        total_notes = total_melodies * st["notes_per_ex"]
        correct_count = sum(1 for ans_list in st["user_answers"] for a in ans_list if a["is_correct"])
        acc = correct_count / total_notes * 100 if total_notes > 0 else 0
        st["is_finished"] = True

        table = []
        wrong_set = set()
        for ex_i in range(total_melodies):
            correct_melody = " → ".join(st["answers"][ex_i])
            user_ans = st["user_answers"][ex_i] if ex_i < len(st["user_answers"]) else []
            user_melody = " → ".join(a["guess"] for a in user_ans)
            num_correct = sum(1 for a in user_ans if a["is_correct"])
            for a in user_ans:
                if not a["is_correct"]:
                    wrong_set.add(a["correct"])
            table.append([f"旋律{ex_i+1}", user_melody, correct_melody, f"{num_correct}/{st['notes_per_ex']}"])

        md = (f"## 🎉 练习完成！\n\n| 指标 | 值 |\n|------|----|\n"
              f"| 总音数 | {total_notes} |\n"
              f"| 正确 | {correct_count} / {total_notes} |\n"
              f"| 正确率 | **{acc:.0f}%** |")

        replay_choices = [f"旋律{i+1}" for i in range(total_melodies)]
        if wrong_set:
            add_mistakes(list(wrong_set))

        return (st, None, f"全部完成 ({total_melodies} 条旋律)", "",
                gr.update(choices=[], interactive=False),
                gr.update(visible=False), gr.update(visible=True),
                md, table,
                gr.update(choices=replay_choices, value=replay_choices[0], visible=True),
                format_mistakes())

    def replay(st):
        if st is None or st["is_finished"]:
            return None
        idx = st["ex_idx"]
        return st["wav_paths"][idx] if st["wav_paths"][idx] else None

    def replay_result(st, sel):
        if st is None or not st["is_finished"]:
            return None
        try:
            idx = int(sel.replace("旋律", "")) - 1
            if 0 <= idx < st["total_ex"]:
                if st["wav_paths"][idx] is None:
                    st["wav_paths"][idx] = render_exercise_wav(st["exercises"][idx], st["preset"], idx, "l2")
                return st["wav_paths"][idx]
        except (ValueError, IndexError):
            pass
        return None

    out = [state, l2_audio, l2_progress, l2_note_label, l2_radio,
           l2_exercise, l2_result, l2_result_md, l2_result_df, l2_replay_dd, mistake_display]

    l2_gen.click(fn=gen, inputs=[l2_low, l2_high, l2_note_cnt, l2_count, l2_preset], outputs=out)
    l2_submit.click(fn=submit, inputs=[state, l2_radio], outputs=out)
    l2_replay_btn.click(fn=replay, inputs=[state], outputs=[l2_audio])
    l2_replay_btn2.click(fn=replay_result, inputs=[state, l2_replay_dd], outputs=[l2_result_audio])
