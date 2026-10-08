#!/usr/bin/env python3
"""Parse a ctexart-style main.tex (the subset this workflow generates) into
content.json for build_docx.js.

Usage: python parse_tex.py <main.tex> [content.json]

Markers embedded in paragraph text (private-use chars):
  N  -> footnote reference N
   ...  -> bold span
   ...  -> explicit Chinese quote
   ...  -> explicit English quote
"""
import json
import re
import sys
from pathlib import Path

TEX = Path(sys.argv[1])
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("content.json")

src = TEX.read_text(encoding="utf-8")
body = src.split(r"\begin{document}", 1)[1].split(r"\end{document}", 1)[0]
body = body.replace("\\maketitle", "")

footnotes: dict[int, str] = {}
fn_counter = 0
Q_ZH_OPEN, Q_ZH_CLOSE = "\ue010", "\ue011"
Q_EN_OPEN, Q_EN_CLOSE = "\ue012", "\ue013"


def extract_braced(text: str, start: int) -> tuple[str, int]:
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ValueError("unbalanced braces")


def replace_footnotes(text: str) -> str:
    global fn_counter
    out, i = [], 0
    while True:
        j = text.find(r"\footnote{", i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        content, after = extract_braced(text, j + len(r"\footnote"))
        fn_counter += 1
        footnotes[fn_counter] = clean_inline(content)
        out.append(f"{fn_counter}")
        i = after
    return "".join(out)


def replace_textbf(text: str) -> str:
    out, i = [], 0
    while True:
        j = text.find(r"\textbf{", i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        content, after = extract_braced(text, j + len(r"\textbf"))
        out.append("" + content + "")
        i = after
    return "".join(out)


def replace_quote_macros(text: str) -> str:
    """Replace explicit language quote macros while preserving nested inline markup."""
    markers = {
        r"\zhquote": (Q_ZH_OPEN, Q_ZH_CLOSE),
        r"\enquote": (Q_EN_OPEN, Q_EN_CLOSE),
    }
    out, i = [], 0
    while i < len(text):
        matches = [(text.find(command + "{", i), command) for command in markers]
        matches = [(position, command) for position, command in matches if position >= 0]
        if not matches:
            out.append(text[i:])
            break
        position, command = min(matches)
        out.append(text[i:position])
        content, after = extract_braced(text, position + len(command))
        opening, closing = markers[command]
        out.extend((opening, replace_quote_macros(content), closing))
        i = after
    return "".join(out)


def clean_inline(text: str) -> str:
    text = replace_quote_macros(text)
    text = replace_textbf(text)
    text = text.replace(r"\quad", "　").replace(r"\noindent", "").replace(r"\\", " ")
    text = re.sub(r"\\(large|Large|medskip|bigskip|item)\b", "", text)
    return re.sub(r"[ \t]+", " ", text).strip()


# title block from preamble
pre = src.split(r"\begin{document}", 1)[0]
title_at = pre.find(r"\title{")
title_raw = extract_braced(pre, title_at + len(r"\title"))[0] if title_at >= 0 else ""
title_bold_at = title_raw.find(r"\textbf{")
title_text = extract_braced(title_raw, title_bold_at + len(r"\textbf"))[0] if title_bold_at >= 0 else title_raw.split(r"\\", 1)[0]
subtitle = re.search(r"\\large\s*([^\\}]+)", title_raw)
author_at = pre.find(r"\author{")
author_raw = extract_braced(pre, author_at + len(r"\author"))[0] if author_at >= 0 else ""

blocks: list[dict] = []
sec_no = sub_no = 0
CN = "一二三四五六七八九十"
para_buf: list[str] = []


def flush_para():
    global para_buf
    if para_buf:
        raw = " ".join(para_buf).strip()
        para_buf = []
        if raw:
            text = clean_inline(replace_footnotes(raw))
            if text:
                blocks.append({"type": "para", "text": text})


lines = body.splitlines()
i = 0
while i < len(lines):
    line = lines[i].strip()
    if not line or line in (r"\medskip", r"\bigskip"):
        flush_para(); i += 1; continue
    m = re.match(r"\\section\*\{(.+)\}\s*$", line)
    if m:
        flush_para(); sub_no = 0
        blocks.append({"type": "h1s", "text": clean_inline(m.group(1))}); i += 1; continue
    m = re.match(r"\\section\{(.+)\}\s*$", line)
    if m:
        flush_para(); sec_no += 1; sub_no = 0
        blocks.append({"type": "h1", "text": f"{CN[sec_no-1]}、{clean_inline(m.group(1))}"}); i += 1; continue
    m = re.match(r"\\subsection\{(.+)\}\s*$", line)
    if m:
        flush_para(); sub_no += 1
        blocks.append({"type": "h2", "text": f"（{CN[sub_no-1]}）{clean_inline(m.group(1))}"}); i += 1; continue
    if line == r"\begin{itemize}":
        flush_para(); i += 1
        while i < len(lines) and lines[i].strip() != r"\end{itemize}":
            it = lines[i].strip()
            if it.startswith(r"\item"):
                blocks.append({"type": "li", "text": clean_inline(replace_footnotes(it[len(r"\item"):]))})
            i += 1
        i += 1; continue
    if line.startswith("%"):
        i += 1; continue
    para_buf.append(line); i += 1
flush_para()

doc = {
    "title": clean_inline(title_text),
    "subtitle": clean_inline(subtitle.group(1).strip()) if subtitle else "",
    "author": clean_inline(author_raw),
    "blocks": blocks,
    "footnotes": footnotes,
}
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"blocks={len(blocks)} footnotes={len(footnotes)} -> {OUT}")
