import gradio as gr

from seedvr_studio.ui import CSS, build_app
from seedvr_studio.paths import OUTPUTS


if __name__ == "__main__":
    build_app().queue(default_concurrency_limit=1).launch(
        inbrowser=True,
        server_name="127.0.0.1",
        server_port=7860,
        allowed_paths=[str(OUTPUTS)],
        show_error=True,
        css=CSS,
        theme=gr.themes.Base(),
    )
