"""
ear_traing_master 主页面
=======================
Tab 管理：Lesson 1 单音辨听 / Lesson 2 旋律辨听
"""

import gradio as gr
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pages.common import format_mistakes
from pages import lesson1_page, lesson2_page

CSS = """
.gradio-container { max-width: 800px !important; margin: 0 auto !important; }
#main-title { text-align: center; font-size: 2.2em !important; font-weight: 700 !important;
              font-family: 'DejaVu Sans Mono', 'Consolas', 'Menlo', 'Courier New', monospace !important;
              letter-spacing: 4px; }
#subtitle { text-align: center; }
"""

with gr.Blocks(title="ear_traing_master") as demo:
    gr.Markdown("""<h1 id='main-title'>EAR TRAING MASTER</h1>
        <p id='subtitle'>A4=440Hz 标准音</p>""")

    with gr.Accordion("📊 易错题集（历史错题统计）", open=False):
        mistake_display = gr.Textbox(
            value=format_mistakes(), label="错题记录", interactive=False, lines=8,
        )

    with gr.Tabs():
        with gr.Tab("Lesson 1: 单音辨听"):
            lesson1_page.build_ui(mistake_display)
        with gr.Tab("Lesson 2: 旋律辨听"):
            lesson2_page.build_ui(mistake_display)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False, css=CSS)
