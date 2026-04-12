"""리소스 XML 청킹 — Android values XML, layout XML 등."""

import os
import re

from analysis.chunkers.base import CodeChunk


# values 계열 디렉토리 (항목별 분리)
VALUES_DIR_PREFIXES = ("values",)

# 파일 통째로 저장할 리소스 디렉토리
WHOLE_FILE_RES_DIRS = {
    "layout", "menu", "navigation", "xml",
    "drawable", "anim", "animator",
}


def get_res_dir_name(file_path: str) -> str:
    """res/ 하위 디렉토리 이름을 반환한다."""
    parts = file_path.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part == "res" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def is_values_dir(dir_name: str) -> bool:
    return dir_name.startswith("values")


def is_whole_file_res_dir(dir_name: str) -> bool:
    base = dir_name.split("-")[0]
    return base in WHOLE_FILE_RES_DIRS


def chunk_resource_xml_by_item(file_path: str, relative_path: str) -> list[CodeChunk]:
    """values 계열 XML을 리소스 항목별 청크로 분리한다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    items = []
    current_item_lines = []
    depth = 0

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if stripped.startswith("<?") or stripped == "<resources>" or stripped == "</resources>" or stripped == "":
            continue

        if depth == 0 and stripped.startswith("<"):
            current_item_lines = [(line_no, line)]
            if "/>" in stripped or ("</" in stripped and ">" in stripped):
                items.append(current_item_lines)
                current_item_lines = []
            else:
                depth = 1
        elif depth > 0:
            current_item_lines.append((line_no, line))
            if stripped.startswith("<") and not stripped.startswith("</") and not stripped.startswith("<!--") and "/>" not in stripped:
                depth += 1
            if stripped.startswith("</") or stripped.endswith("/>"):
                depth -= 1
                if depth <= 0:
                    items.append(current_item_lines)
                    current_item_lines = []
                    depth = 0

    if len(items) <= 5:
        return [CodeChunk(
            file_path=relative_path, chunk_type="resource_file",
            name=os.path.basename(file_path), content=content,
            start_line=1, end_line=content.count("\n") + 1, parent_class="",
        )]

    chunks = []
    for item_lines in items:
        item_text = "\n".join(line for _, line in item_lines)
        if len(item_text.strip()) < 10:
            continue
        name_match = re.search(r'name\s*=\s*"([^"]*)"', item_text)
        item_name = name_match.group(1) if name_match else "(unnamed)"
        chunks.append(CodeChunk(
            file_path=relative_path, chunk_type="resource_item",
            name=item_name,
            content=f"<!-- File: {relative_path} -->\n{item_text}",
            start_line=item_lines[0][0], end_line=item_lines[-1][0],
            parent_class="",
        ))

    return chunks


def chunk_resource_xml_whole(file_path: str, relative_path: str) -> list[CodeChunk]:
    """레이아웃, 네비게이션 등 XML 파일을 통째로 하나의 청크로 만든다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if len(content.strip()) < 10:
        return []
    return [CodeChunk(
        file_path=relative_path, chunk_type="resource_file",
        name=os.path.basename(file_path), content=content,
        start_line=1, end_line=content.count("\n") + 1, parent_class="",
    )]
