"""Swift AST 기반 청킹."""

import tree_sitter_swift as ts_swift
from tree_sitter import Language, Parser

from analysis.chunkers.base import CodeChunk, extract_chunks_from_tree

# ─── 파서 ───

SWIFT_LANGUAGE = Language(ts_swift.language())
swift_parser = Parser(SWIFT_LANGUAGE)

# ─── 노드 타입 ───

CLASS_NODE_TYPES = {
    "class_declaration",
    "struct_declaration",
    "protocol_declaration",
    "enum_declaration",
    "extension_declaration",
    "actor_declaration",
}

MEMBER_TYPES = {
    "function_declaration",
    "variable_declaration",
    "init_declaration",
    "subscript_declaration",
    "typealias_declaration",
    "class_declaration",
    "struct_declaration",
    "enum_declaration",
}

TOP_LEVEL_TYPES = {
    "function_declaration",
    "variable_declaration",
} | CLASS_NODE_TYPES

BODY_TYPES = {"class_body", "protocol_body", "enum_class_body"}


# ─── 청킹 함수 ───

def chunk_swift(file_path: str) -> list[CodeChunk]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source_bytes = f.read().encode("utf-8")
    tree = swift_parser.parse(source_bytes)
    return extract_chunks_from_tree(
        tree, source_bytes, file_path,
        CLASS_NODE_TYPES, TOP_LEVEL_TYPES, MEMBER_TYPES, BODY_TYPES,
    )
