"""문서 파일 청킹 — Markdown, 텍스트 등."""

import os

from analysis.chunkers.base import CodeChunk
from analysis.chunkers.common.config import chunk_whole_file


def chunk_markdown(file_path: str, relative_path: str) -> list[CodeChunk]:
    """마크다운 파일을 헤딩 기준 섹션별 청크로 분리한다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    lines = content.split("\n")
    sections = []
    current_heading = os.path.basename(file_path)
    current_lines = []
    current_start = 1

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            if current_lines:
                sections.append((current_heading, current_start, current_lines))
            current_heading = stripped.lstrip("#").strip()
            current_lines = [line]
            current_start = line_no
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_start, current_lines))

    if len(sections) <= 3:
        return [CodeChunk(
            file_path=relative_path, chunk_type="document",
            name=os.path.basename(file_path), content=content,
            start_line=1, end_line=len(lines), parent_class="",
        )]

    chunks = []
    for heading, start_line, section_lines in sections:
        section_text = "\n".join(section_lines)
        if len(section_text.strip()) < 20:
            continue
        chunks.append(CodeChunk(
            file_path=relative_path, chunk_type="document_section",
            name=heading, content=section_text,
            start_line=start_line, end_line=start_line + len(section_lines) - 1,
            parent_class="",
        ))

    return chunks


def chunk_plaintext(file_path: str, relative_path: str) -> list[CodeChunk]:
    """텍스트 파일을 빈 줄 기준 문단별 청크로 분리한다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    paragraphs = []
    current_para = []
    current_start = 1

    for line_no, line in enumerate(content.split("\n"), 1):
        if line.strip() == "" and current_para:
            paragraphs.append((current_start, current_para))
            current_para = []
        else:
            if not current_para:
                current_start = line_no
            current_para.append(line)

    if current_para:
        paragraphs.append((current_start, current_para))

    if len(paragraphs) <= 3:
        return chunk_whole_file(file_path, relative_path, chunk_type="document")

    chunks = []
    for start_line, para_lines in paragraphs:
        para_text = "\n".join(para_lines)
        if len(para_text.strip()) < 20:
            continue
        first_line = para_lines[0].strip()[:60]
        chunks.append(CodeChunk(
            file_path=relative_path, chunk_type="document_paragraph",
            name=first_line if first_line else "(paragraph)",
            content=para_text,
            start_line=start_line, end_line=start_line + len(para_lines) - 1,
            parent_class="",
        ))

    return chunks
