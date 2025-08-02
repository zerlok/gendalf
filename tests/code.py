from astlab.reader import parse_module
from astlab.writer import render_module


def code_content(value: str) -> str:
    return render_module(parse_module(value, indented=True))
