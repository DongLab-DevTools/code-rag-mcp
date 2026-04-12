"""공통 데이터 구조 및 AST 유틸리티."""

import os
from dataclasses import dataclass


@dataclass
class CodeChunk:
    """쪼개진 코드 조각 하나를 나타냄"""
    file_path: str
    chunk_type: str
    name: str
    content: str
    start_line: int
    end_line: int
    parent_class: str

    def to_text_for_embedding(self) -> str:
        header = f"// File: {self.file_path}\n"
        if self.parent_class:
            header += f"// Class: {self.parent_class}\n"
        header += f"// Type: {self.chunk_type} | Name: {self.name}\n"
        return header + self.content


# 이 줄 수를 넘는 클래스는 내부 멤버를 개별 청크로 분해한다
CLASS_LINE_THRESHOLD = 50
# 이 글자 수 미만의 코드는 건너뛴다
MIN_CONTENT_LENGTH = 30


def get_node_name(node) -> str:
    """AST 노드에서 이름을 추출한다."""
    for child in node.children:
        if child.type in ("simple_identifier", "identifier"):
            return child.text.decode("utf-8")
    return "(anonymous)"


def get_node_lines(node) -> int:
    """AST 노드의 줄 수를 계산한다."""
    return node.end_point[0] - node.start_point[0] + 1


def get_class_signature(node, source_bytes: bytes, body_types: set[str]) -> str:
    """클래스의 시그니처(본문 제외)를 추출한다."""
    for child in node.children:
        if child.type in body_types:
            sig = source_bytes[node.start_byte:child.start_byte].decode(
                "utf-8", errors="replace"
            ).rstrip()
            return sig + " { ... }"
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def get_class_body_node(node, body_types: set[str]):
    """클래스 노드에서 본문 노드를 찾는다."""
    for child in node.children:
        if child.type in body_types:
            return child
    return None


def extract_chunks_from_tree(
    tree, source_bytes: bytes, file_path: str,
    class_node_types: set, top_level_types: set, member_types: set,
    body_types: set[str],
) -> list[CodeChunk]:
    """AST 트리에서 청크를 추출하는 공통 로직."""
    chunks = []

    def make_chunk(node, chunk_type: str, name: str, parent_class: str = ""):
        content = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        if len(content.strip()) < MIN_CONTENT_LENGTH:
            return
        chunks.append(CodeChunk(
            file_path=file_path,
            chunk_type=chunk_type,
            name=name,
            content=content,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            parent_class=parent_class,
        ))

    def process_class(node, parent_class: str = ""):
        class_name = get_node_name(node)
        full_class_name = f"{parent_class}.{class_name}" if parent_class else class_name
        lines = get_node_lines(node)

        if lines <= CLASS_LINE_THRESHOLD:
            make_chunk(node, node.type, class_name, parent_class)
        else:
            signature = get_class_signature(node, source_bytes, body_types)
            if len(signature.strip()) >= MIN_CONTENT_LENGTH:
                chunks.append(CodeChunk(
                    file_path=file_path,
                    chunk_type="class_signature",
                    name=class_name,
                    content=signature,
                    start_line=node.start_point[0] + 1,
                    end_line=node.start_point[0] + 1,
                    parent_class=parent_class,
                ))

            body = get_class_body_node(node, body_types)
            if body:
                for child in body.children:
                    if child.type in class_node_types:
                        process_class(child, parent_class=full_class_name)
                    elif child.type in member_types:
                        make_chunk(child, child.type, get_node_name(child), parent_class=full_class_name)

    def visit(node):
        if node.type in class_node_types:
            process_class(node)
        elif node.type in top_level_types:
            make_chunk(node, node.type, get_node_name(node))
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return chunks
