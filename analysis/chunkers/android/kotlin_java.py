"""Kotlin/Java AST 기반 청킹."""

import tree_sitter_kotlin as ts_kotlin
import tree_sitter_java as ts_java
from tree_sitter import Language, Parser

from analysis.chunkers.base import CodeChunk, extract_chunks_from_tree

# ─── 파서 ───

KOTLIN_LANGUAGE = Language(ts_kotlin.language())
JAVA_LANGUAGE = Language(ts_java.language())

kotlin_parser = Parser(KOTLIN_LANGUAGE)
java_parser = Parser(JAVA_LANGUAGE)

# ─── 노드 타입 ───

CLASS_NODE_TYPES = {
    "class_declaration",
    "interface_declaration",
    "object_declaration",
    "companion_object",
}

KOTLIN_MEMBER_TYPES = {
    "function_declaration",
    "property_declaration",
    "companion_object",
    "class_declaration",
    "object_declaration",
}

JAVA_MEMBER_TYPES = {
    "method_declaration",
    "constructor_declaration",
    "field_declaration",
    "enum_declaration",
    "class_declaration",
    "interface_declaration",
}

KOTLIN_TOP_LEVEL_TYPES = {
    "function_declaration",
    "property_declaration",
} | CLASS_NODE_TYPES

JAVA_TOP_LEVEL_TYPES = {
    "method_declaration",
    "field_declaration",
    "enum_declaration",
    "constructor_declaration",
} | CLASS_NODE_TYPES

BODY_TYPES = {"class_body", "interface_body", "enum_body"}


# ─── 청킹 함수 ───

def chunk_kotlin(file_path: str) -> list[CodeChunk]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source_bytes = f.read().encode("utf-8")
    tree = kotlin_parser.parse(source_bytes)
    return extract_chunks_from_tree(
        tree, source_bytes, file_path,
        CLASS_NODE_TYPES, KOTLIN_TOP_LEVEL_TYPES, KOTLIN_MEMBER_TYPES, BODY_TYPES,
    )


def chunk_java(file_path: str) -> list[CodeChunk]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source_bytes = f.read().encode("utf-8")
    tree = java_parser.parse(source_bytes)
    return extract_chunks_from_tree(
        tree, source_bytes, file_path,
        CLASS_NODE_TYPES, JAVA_TOP_LEVEL_TYPES, JAVA_MEMBER_TYPES, BODY_TYPES,
    )
