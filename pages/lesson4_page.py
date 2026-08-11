"""Lesson 4 UI: 旋律辨听（全音阶，含黑键）。"""

import gradio as gr
from ear_traing_lesson.lesson4 import build_melody_exercises
from pages.common import (
    ALL_CHROMATIC, chromatic_notes_in_range, render_exercise_wav, render_a4_wav,
    add_mistakes, format_mistakes,
)


def build_ui(mistake_display):
    state = gr.State(None)

    gr.Markdown("""
> 🎹 **训练目标**：与 Lesson 2 相同模式，但候选音包含**所有黑键**（半音阶）。
> 先完整播放旋律 → 逐音填入答案框 → 提交整条旋律
    """)

    with gr.Row():
        l4_low = gr.Dropdown(choices=ALL_CHROMATIC, value="A3", label="最低音", scale=1)
        l4_high = gr.Dropdown(choices=ALL_CHROMATIC, value="D5", label="最高音", scale=1)
        l4_note_cnt = gr.Slider(2, 8, value=5, step=1, label="音符数量", scale=1)
        l4_gap = gr.Dropdown(choices=["100", "300", "500", "800", "1000", "1500", "2000"], value="500", label="音符间隔(ms)", scale=1)
        l4_count = gr.Slider(1, 20, value=1, step=1, label="练习条数", scale=1)

    with gr.Row():
        l4_preset = gr.Radio(choices=["piano", "guitar", "voice"], value="piano", label="音色")

    l4_gen = gr.Button("🎵 生成新练习", variant="primary")

    with gr.Column(visible=True) as l4_exercise:
        l4_progress = gr.Textbox(value="等待生成...", label="进度", interactive=False)
        with gr.Row():
            l4_a4_btn = gr.Button("🔔 标准音 A4", scale=1, variant="secondary")
            l4_replay_btn = gr.Button("🔄 重播整段旋律", scale=2)
        with gr.Row(visible=False) as l4_a4_row:
            l4_a4_player = gr.Audio(label="🔔 A4=440Hz", type="filepath", interactive=False, autoplay=True, scale=4)
            l4_a4_close = gr.Button("✕ 收起", scale=1)
        l4_audio = gr.Audio(label="🎧 点击播放", type="filepath", interactive=False)
        l4_radio = gr.Radio(
            choices=chromatic_notes_in_range("A3", "D5"),
            label="🎯 点击选音（自动填入下方答案框）", interactive=True, value=None,
        )
        l4_answer_box = gr.Textbox(label="📝 答案框", interactive=False, placeholder="点击上方音名填充...")
        with gr.Row():
            l4_undo_btn = gr.Button("↩ 撤销", scale=1, variant="secondary")
            l4_submit = gr.Button("✅ 提交此旋律", variant="primary", scale=2)

    with gr.Column(visible=False) as l4_result:
        l4_result_md = gr.Markdown("")
        l4_result_df = gr.Dataframe(
            headers=["旋律", "你的答案", "正确答案", "正确数"], label="详情", interactive=False,
        )
        with gr.Row():
            l4_replay_dd = gr.Dropdown(choices=[], label="重听旋律", scale=2, visible=False)
            l4_replay_btn2 = gr.Button("🔊 播放", scale=1)
        l4_result_audio = gr.Audio(label="🎧 重听", type="filepath", interactive=False)

    # ---- 逻辑 ----

    def gen(low, high, note_cnt, gap, count, preset):
        exercises, answers = build_melody_exercises(
            low_note=low, high_note=high,
            note_count=int(note_cnt), melody_repeat=1,
            max_exercises=int(count), seed=None,
        )
        total = len(exercises)
        wavs = [None] * total
        wavs[0] = render_exercise_wav(exercises[0], preset, 0, "l4", gap_ms=int(gap))
        npe = len(answers[0])
        st = {"answers": answers, "exercises": exercises, "wav_paths": wavs,
              "ex_idx": 0, "total_ex": total, "notes_per_ex": npe,
              "preset": preset, "gap_ms": int(gap),
              "user_answers": [], "is_finished": False,
              "current_selections": [], "low": low, "high": high}
        ans_text = _fmt_answer([], npe)
        return (st, wavs[0], f"旋律 1/{total}", ans_text,
                gr.update(choices=chromatic_notes_in_range(low, high), value=None, interactive=True),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def _fmt_answer(selections, npe):
        parts = selections + ["_"] * (npe - len(selections))
        return " → ".join(parts)

    def add_note(st, note):
        if st is None or st.get("_busy") or st["is_finished"] or note is None:
            if st is None:
                return (None, gr.update(), "⚠️ 请先生成", "",
                        gr.update(interactive=False),
                        gr.update(visible=True), gr.update(visible=False),
                        "", [], gr.update(choices=[], visible=False), format_mistakes())
            return (st, gr.update(),
                    f"旋律 {st['ex_idx']+1}/{st['total_ex']}",
                    _fmt_answer(st["current_selections"], st["notes_per_ex"]),
                    gr.update(),
                    gr.update(visible=True), gr.update(visible=False),
                    "", [], gr.update(choices=[], visible=False), format_mistakes())
        if len(st["current_selections"]) >= st["notes_per_ex"]:
            return (st, gr.update(),
                    f"旋律 {st['ex_idx']+1}/{st['total_ex']}",
                    _fmt_answer(st["current_selections"], st["notes_per_ex"]),
                    gr.update(),
                    gr.update(visible=True), gr.update(visible=False),
                    "", [], gr.update(choices=[], visible=False), format_mistakes())
        st["_busy"] = True
        st["current_selections"].append(note.strip().upper())
        result = (st, gr.update(),
                  f"旋律 {st['ex_idx']+1}/{st['total_ex']}",
                  _fmt_answer(st["current_selections"], st["notes_per_ex"]),
                  gr.update(value=None),
                  gr.update(visible=True), gr.update(visible=False),
                  "", [], gr.update(choices=[], visible=False), format_mistakes())
        st["_busy"] = False
        return result

    def undo_note(st):
        if st is None or st["is_finished"]:
            return (st, gr.update(), "", "", gr.update(), gr.update(), gr.update(), "", [], gr.update(), format_mistakes())
        if st["current_selections"]:
            st["current_selections"].pop()
        return (st, gr.update(), f"旋律 {st['ex_idx']+1}/{st['total_ex']}",
                _fmt_answer(st["current_selections"], st["notes_per_ex"]),
                gr.update(),
                gr.update(visible=True), gr.update(visible=False),
                "", [], gr.update(choices=[], visible=False), format_mistakes())

    def submit_melody(st):
        if st is None or st["is_finished"]:
            return (st, None, "", "", gr.update(), gr.update(), gr.update(), "", [], gr.update(), format_mistakes())
        selections = st["current_selections"]
        npe = st["notes_per_ex"]
        if len(selections) < npe:
            return (st, st["wav_paths"][st["ex_idx"]], f"旋律 {st['ex_idx']+1}/{st['total_ex']}",
                    _fmt_answer(selections, npe),
                    gr.update(value=None, interactive=True),
                    gr.update(visible=True), gr.update(visible=False),
                    "", [], gr.update(choices=[], visible=False), format_mistakes())
        ex = st["ex_idx"]
        corrects = st["answers"][ex]
        ans_list = [{"note_idx": i, "guess": s, "correct": c, "is_correct": (s == c)}
                    for i, (s, c) in enumerate(zip(selections, corrects))]
        st["user_answers"].append(ans_list)
        st["current_selections"] = []
        ex += 1
        if ex >= st["total_ex"]:
            st["ex_idx"] = ex
            return _finish(st)
        st["ex_idx"] = ex
        if st["wav_paths"][ex] is None:
            st["wav_paths"][ex] = render_exercise_wav(st["exercises"][ex], st["preset"], ex, "l4", gap_ms=st["gap_ms"])
        return (st, st["wav_paths"][ex], f"旋律 {ex+1}/{st['total_ex']}",
                _fmt_answer([], npe),
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
        return st["wav_paths"][st["ex_idx"]] if st["wav_paths"][st["ex_idx"]] else None

    def replay_result(st, sel):
        if st is None or not st["is_finished"]:
            return None
        try:
            idx = int(sel.replace("旋律", "")) - 1
            if 0 <= idx < st["total_ex"]:
                if st["wav_paths"][idx] is None:
                    st["wav_paths"][idx] = render_exercise_wav(st["exercises"][idx], st["preset"], idx, "l4", gap_ms=st["gap_ms"])
                return st["wav_paths"][idx]
        except (ValueError, IndexError):
            pass
        return None

    def play_a4(preset):
        return render_a4_wav(preset), gr.update(visible=True), gr.update(interactive=False)

    out = [state, l4_audio, l4_progress, l4_answer_box, l4_radio,
           l4_exercise, l4_result, l4_result_md, l4_result_df, l4_replay_dd, mistake_display]

    l4_gen.click(fn=gen, inputs=[l4_low, l4_high, l4_note_cnt, l4_gap, l4_count, l4_preset], outputs=out)
    l4_radio.change(fn=add_note, inputs=[state, l4_radio], outputs=out)
    l4_undo_btn.click(fn=undo_note, inputs=[state], outputs=out)
    l4_submit.click(fn=submit_melody, inputs=[state], outputs=out)
    l4_replay_btn.click(fn=replay, inputs=[state], outputs=[l4_audio])
    l4_replay_btn2.click(fn=replay_result, inputs=[state, l4_replay_dd], outputs=[l4_result_audio])
    l4_a4_btn.click(fn=play_a4, inputs=[l4_preset], outputs=[l4_a4_player, l4_a4_row, l4_a4_btn])
    l4_a4_close.click(fn=lambda: (gr.update(visible=False), gr.update(interactive=True)),
                      outputs=[l4_a4_row, l4_a4_btn])
