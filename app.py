#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — SRT Translator Web Server
Translates SRT subtitle files from English to Hebrew using the OpenAI GPT API.
Supports: single SRT file, multiple SRT files, folder upload, ZIP archive.
"""

import re
import os
import time
import zipfile
import tempfile
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template
from openai import OpenAI

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
MODEL       = "gpt-4o"
TEMPERATURE = 0.1
CHUNK_SIZE  = 80
MAX_RETRIES = 3

# Right-to-Left Mark — forces correct RTL punctuation rendering
RLM = "\u200f"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload


# ──────────────────────────────────────────────
# SRT parsing
# ──────────────────────────────────────────────
def parse_srt(content: str) -> list[dict]:
    raw_blocks = re.split(r"\n\s*\n", content.strip())
    blocks = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        if len(lines) < 2:
            continue
        index_line = lines[0].strip()
        time_line  = lines[1].strip()
        if "-->" not in time_line:
            continue
        text_lines = [l.strip() for l in lines[2:] if l.strip()]
        blocks.append({"index": index_line, "time": time_line, "lines": text_lines})
    return blocks


def blocks_to_plain_text(blocks: list[dict]) -> str:
    parts = []
    for b in blocks:
        parts.append(f"[{b['index']}]")
        parts.append("\n".join(b["lines"]))
    return "\n".join(parts)


# ──────────────────────────────────────────────
# GPT translation
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a professional subtitle translator specializing in English to Hebrew translation.

Rules:
- Translate the provided subtitle text from English to Hebrew.
- Preserve the block markers exactly as-is: [1], [2], [3], etc. — do NOT translate or remove them.
- Translate naturally, considering the full context of all subtitles together, not word-for-word.
- Use modern, fluent Israeli Hebrew (not archaic or overly formal).
- Keep the same number of text lines per block as the original.
- Do NOT add, merge, split, or reorder blocks.
- Do NOT add any explanations or notes — output translated subtitle text only.
- Maintain proper RTL punctuation conventions for Hebrew.
"""

def translate_chunk(client: OpenAI, plain_text: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                temperature=TEMPERATURE,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": plain_text},
                ],
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(3 * attempt)
            else:
                raise RuntimeError(f"OpenAI API error after {MAX_RETRIES} attempts: {e}")


def translate_blocks(client: OpenAI, blocks: list[dict]) -> dict[str, list[str]]:
    translated = {}
    total = len(blocks)
    for start in range(0, total, CHUNK_SIZE):
        chunk  = blocks[start : start + CHUNK_SIZE]
        plain  = blocks_to_plain_text(chunk)
        result = translate_chunk(client, plain)

        current_idx  = None
        current_text = []
        for line in result.splitlines():
            line = line.strip()
            m = re.match(r"^\[(\d+)\]$", line)
            if m:
                if current_idx is not None:
                    translated[current_idx] = [l for l in current_text if l]
                current_idx  = m.group(1)
                current_text = []
            elif current_idx is not None:
                current_text.append(line)
        if current_idx is not None:
            translated[current_idx] = [l for l in current_text if l]

    return translated


def rebuild_srt(blocks: list[dict], translated: dict[str, list[str]]) -> str:
    output_parts = []
    for b in blocks:
        idx      = b["index"]
        he_lines = translated.get(idx)
        if he_lines:
            text = "\n".join(RLM + line for line in he_lines)
        else:
            text = "\n".join(b["lines"])
        output_parts.append(f"{idx}\n{b['time']}\n{text}")
    return "\n\n".join(output_parts) + "\n"


def translate_srt_content(client: OpenAI, content: str) -> str:
    """Translate SRT file content string, return translated SRT string."""
    blocks     = parse_srt(content)
    translated = translate_blocks(client, blocks)
    return rebuild_srt(blocks, translated)


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/translate", methods=["POST"])
def translate():
    api_key = request.form.get("api_key", "").strip()
    if not api_key:
        api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OpenAI API key is required."}), 400

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded."}), 400

    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        return jsonify({"error": f"Failed to initialize OpenAI client: {e}"}), 400

    srt_files = {}  # filename -> content string

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in files:
            filename = f.filename
            if not filename:
                continue

            # ZIP: extract and collect SRT files
            if filename.lower().endswith(".zip"):
                zip_path = os.path.join(tmpdir, filename)
                f.save(zip_path)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    for member in zf.namelist():
                        if member.lower().endswith(".srt") and not member.startswith("__MACOSX"):
                            data = zf.read(member).decode("utf-8-sig")
                            base = os.path.basename(member)
                            srt_files[base] = data

            # SRT file directly
            elif filename.lower().endswith(".srt"):
                data = f.read().decode("utf-8-sig")
                base = os.path.basename(filename)
                srt_files[base] = data

        if not srt_files:
            return jsonify({"error": "No SRT files found in the upload."}), 400

        # Translate all collected SRT files
        translated_files = {}
        for name, content in srt_files.items():
            try:
                translated_content = translate_srt_content(client, content)
                stem = Path(name).stem
                out_name = f"{stem}_hebrew.srt"
                translated_files[out_name] = translated_content
            except Exception as e:
                return jsonify({"error": f"Translation failed for '{name}': {e}"}), 500

        # Single file → return directly
        if len(translated_files) == 1:
            out_name, out_content = next(iter(translated_files.items()))
            out_path = os.path.join(tmpdir, out_name)
            with open(out_path, "w", encoding="utf-8") as fp:
                fp.write(out_content)
            return send_file(
                out_path,
                as_attachment=True,
                download_name=out_name,
                mimetype="text/plain",
            )

        # Multiple files → return as ZIP
        zip_path = os.path.join(tmpdir, "translated_hebrew.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for out_name, out_content in translated_files.items():
                zf.writestr(out_name, out_content.encode("utf-8"))

        return send_file(
            zip_path,
            as_attachment=True,
            download_name="translated_hebrew.zip",
            mimetype="application/zip",
        )


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  SRT Translator is running.")
    print("  Open your browser at: http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
