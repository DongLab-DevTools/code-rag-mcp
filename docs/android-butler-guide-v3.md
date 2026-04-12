# 안드로이드 집사 (Android Butler) 만들기 - 완전 가이드

> RAG 시스템을 활용해 안드로이드 코드베이스를 이해하고 질문에 답변하는 MCP 도구 만들기
>
> **API Key 불필요** — 로컬 임베딩(jina-code-embeddings-1.5b) + Claude Code 구독으로 동작
>
> **Apple Silicon 최적화** — M4 Pro / M4 맥북·맥미니에서 MPS 가속 지원

---

## 목차

1. [사전 준비](#1-사전-준비)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [Step 1: 코드 청킹 — 코드를 의미 단위로 쪼개기](#3-step-1-코드-청킹)
4. [Step 2: 임베딩 & 벡터DB 저장 — 인덱싱](#4-step-2-임베딩--벡터db-저장)
5. [Step 3: 검색 모듈 — 관련 코드 찾기](#5-step-3-검색-모듈)
6. [Step 4: MCP 서버로 감싸기 — FastMCP](#6-step-4-mcp-서버로-감싸기)
7. [Step 5: Claude Code에 연결하기](#7-step-5-claude-code에-연결하기)
8. [실행 순서 요약](#8-실행-순서-요약)
9. [개선 아이디어](#9-개선-아이디어)
10. [트러블슈팅](#10-트러블슈팅)

---

## 1. 사전 준비

### 필요한 것들

| 항목 | 설명 |
|------|------|
| **Python 3.10+** | RAG 파이프라인 작성용 |
| **Claude Code** | MCP 도구를 연결할 클라이언트 (구독에 포함) |
| **안드로이드 프로젝트** | 인덱싱할 대상 코드베이스 |
| **맥미니 / 맥북 (M4 Pro)** | MPS 가속으로 빠른 임베딩 생성 |

> **API Key가 필요 없는 이유**
>
> - **임베딩**: `jina-code-embeddings-1.5b` 모델을 내 맥에서 로컬로 실행합니다.
>   1536차원, 코드 특화 모델로 25개 코드 검색 벤치마크에서 SOTA 성능입니다.
>   처음 한 번 ~3GB 모델이 다운로드되고, 이후로는 오프라인에서도 동작합니다.
> - **답변 생성**: MCP 서버는 관련 코드를 검색해서 돌려주기만 합니다.
>   그 코드를 보고 답변을 만드는 건 Claude Code가 알아서 합니다.
>   Claude Code는 구독(Team/Pro)에 포함되어 있으므로 추가 과금이 없습니다.

---

## 2. 프로젝트 구조

```
android-butler/
├── chunker.py          # Step 1: 코드를 의미 단위로 쪼개기
├── indexer.py          # Step 2: 임베딩 생성 + 벡터DB 저장
├── search.py           # Step 3: 벡터DB에서 관련 코드 검색
├── server.py           # Step 4: MCP 서버 (FastMCP)
├── requirements.txt    # 의존성 목록
└── chroma_db/          # (자동 생성) 벡터DB 저장소
```

### 패키지 설치

```bash
# 프로젝트 디렉토리 생성
mkdir android-butler
cd android-butler

# requirements.txt 생성
cat > requirements.txt << 'EOF'
chromadb>=0.5.0
tree-sitter>=0.24.0
tree-sitter-kotlin>=0.1.0
tree-sitter-java>=0.23.0
fastmcp>=2.0.0
sentence-transformers>=5.0.0
torch>=2.7.0
EOF

# 패키지 설치
pip install -r requirements.txt
```

> **설치 시 참고**
> - `torch`는 Apple Silicon에서 자동으로 MPS(Metal Performance Shaders) 백엔드를 포함합니다.
> - 전체 설치에 5-10분 정도 걸릴 수 있습니다.
> - `sentence-transformers>=5.0.0`은 jina-code-embeddings 사용에 필요합니다.

---

## 3. Step 1: 코드 청킹

코드를 검색하기 좋은 단위로 쪼개는 단계입니다.
안드로이드 프로젝트는 Kotlin과 Java 파일이 대부분이므로,
`tree-sitter`를 사용해 함수/클래스 단위로 정확하게 분리합니다.

### 청킹 전략

코드 청킹에는 세 가지 방식이 있습니다:

| 방식 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **고정 크기** | N글자씩 기계적으로 자름 | 구현이 간단함 | 함수가 중간에 잘릴 수 있음 |
| **문단 기준** | 빈 줄 기준으로 자름 | 구현이 간단함 | 코드 구조를 무시함 |
| **AST 기반** | 함수/클래스 단위로 자름 | 의미 단위가 보존됨 | 구현이 복잡함 |

이 가이드에서는 **AST 기반 청킹**을 사용합니다.
코드의 문법 구조를 파싱해서 함수·클래스·프로퍼티 단위로 정확하게 분리하므로,
함수 시그니처와 본문이 항상 한 덩어리로 유지됩니다.

또한 코드뿐만 아니라 **프로젝트를 이해하는 데 필요한 모든 파일**을 포함합니다:

| 파일 종류 | 청킹 방식 | 예시 |
|-----------|-----------|------|
| **Kotlin/Java 코드** | AST 기반 (함수·클래스 단위) | `UserRepository.kt` → 함수별 청크 |
| **마크다운 문서** | 헤딩(`#`) 기준 섹션별 분리 | `PROMPT.md` → 섹션별 청크 |
| **설정 파일** | 파일 통째로 | `build.gradle.kts`, `AndroidManifest.xml` |
| **JSON/YAML/TOML** | 파일 통째로 | `google-services.json`, `.github/ci.yml` |
| **values XML** | 리소스 항목별 분리 | `strings.xml` → 각 `<string>` 청크 |
| **layout/navigation XML** | 파일 통째로 | `activity_main.xml` 전체 |
| **일반 텍스트** | 빈 줄 기준 문단별 분리 | `README.txt` → 문단별 청크 |
| **건너뛰는 것들** | 무시 | `build/`, `.gradle/`, 이미지, 캐시 등 |

이 구조 덕분에 안드로이드 프로젝트뿐 아니라 어떤 프로젝트든
데이터만 바꿔 넣으면 집사를 만들 수 있습니다.
서버 코드, 기획 문서, 회사 정책 등 무엇이든 인덱싱할 수 있습니다.

큰 클래스는 **자동으로 분해**하는 로직도 포함합니다:

- 작은 클래스 (50줄 이하): 클래스 전체를 하나의 청크로 유지
- 큰 클래스 (50줄 초과): 클래스 시그니처 청크 + 내부 함수 개별 청크로 분리

### chunker.py

```python
"""
chunker.py — 안드로이드 프로젝트의 Kotlin/Java 파일을 의미 단위로 쪼갠다.

청킹 전략: AST 기반 (tree-sitter)
- 함수, 프로퍼티, enum 등: 개별 청크
- 작은 클래스 (50줄 이하): 통째로 하나의 청크
- 큰 클래스 (50줄 초과): 시그니처 청크 + 내부 멤버 개별 청크로 분해

사용법:
    from chunker import chunk_project
    chunks = chunk_project("/path/to/android-project")
"""

import os
from dataclasses import dataclass
import tree_sitter_kotlin as ts_kotlin
import tree_sitter_java as ts_java
from tree_sitter import Language, Parser

# ─────────────────────────────────────────────
# 1) tree-sitter 언어 설정
# ─────────────────────────────────────────────

KOTLIN_LANGUAGE = Language(ts_kotlin.language())
JAVA_LANGUAGE = Language(ts_java.language())

kotlin_parser = Parser(KOTLIN_LANGUAGE)
java_parser = Parser(JAVA_LANGUAGE)


# ─────────────────────────────────────────────
# 2) 청크 데이터 구조
# ─────────────────────────────────────────────

@dataclass
class CodeChunk:
    """쪼개진 코드 조각 하나를 나타냄"""
    file_path: str      # 파일 경로 (예: app/src/main/.../UserRepository.kt)
    chunk_type: str      # 타입 (function, class, class_signature, property 등)
    name: str            # 이름 (예: getUser, UserRepository)
    content: str         # 실제 코드 텍스트
    start_line: int      # 시작 줄 번호
    end_line: int        # 끝 줄 번호
    parent_class: str    # 소속 클래스 이름 (최상위이면 빈 문자열)

    def to_text_for_embedding(self) -> str:
        """
        임베딩에 넣을 텍스트를 생성한다.
        파일 경로, 소속 클래스, 코드를 합쳐서 컨텍스트를 풍부하게 만든다.
        """
        header = f"// File: {self.file_path}\n"
        if self.parent_class:
            header += f"// Class: {self.parent_class}\n"
        header += f"// Type: {self.chunk_type} | Name: {self.name}\n"
        return header + self.content


# ─────────────────────────────────────────────
# 3) tree-sitter로 코드 파싱
# ─────────────────────────────────────────────

# 클래스 계열 노드 (내부 멤버를 분해할 대상)
CLASS_NODE_TYPES = {
    "class_declaration",
    "interface_declaration",
    "object_declaration",
    "companion_object",
}

# 멤버 노드 (클래스 내부에서 개별 청크로 추출할 대상)
KOTLIN_MEMBER_TYPES = {
    "function_declaration",
    "property_declaration",
    "companion_object",
    "class_declaration",      # 내부 클래스
    "object_declaration",     # 내부 object
}

JAVA_MEMBER_TYPES = {
    "method_declaration",
    "constructor_declaration",
    "field_declaration",
    "enum_declaration",
    "class_declaration",      # 내부 클래스
    "interface_declaration",  # 내부 인터페이스
}

# 최상위에서 추출할 노드 (클래스 밖에 있는 함수, 프로퍼티 등)
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

# 이 줄 수를 넘는 클래스는 내부 멤버를 개별 청크로 분해한다
CLASS_LINE_THRESHOLD = 50


def _get_node_name(node) -> str:
    """AST 노드에서 이름을 추출한다."""
    for child in node.children:
        if child.type in ("simple_identifier", "identifier"):
            return child.text.decode("utf-8")
    return "(anonymous)"


def _get_node_lines(node) -> int:
    """AST 노드의 줄 수를 계산한다."""
    return node.end_point[0] - node.start_point[0] + 1


def _get_class_signature(node, source_bytes: bytes) -> str:
    """
    클래스의 시그니처(본문 제외)를 추출한다.
    class_body 또는 { 이전까지의 텍스트를 반환한다.

    예: class UserRepository(private val dao: UserDao) : BaseRepository {
    """
    for child in node.children:
        if child.type in ("class_body", "interface_body", "enum_body"):
            # class_body 시작 직전까지가 시그니처
            sig = source_bytes[node.start_byte:child.start_byte].decode(
                "utf-8", errors="replace"
            ).rstrip()
            return sig + " { ... }"

    # class_body를 못 찾으면 전체 반환
    return source_bytes[node.start_byte:node.end_byte].decode(
        "utf-8", errors="replace"
    )


def _get_class_body_node(node):
    """클래스 노드에서 본문(class_body) 노드를 찾는다."""
    for child in node.children:
        if child.type in ("class_body", "interface_body", "enum_body"):
            return child
    return None


def _extract_chunks_from_tree(
    tree, source_bytes: bytes, file_path: str,
    top_level_types: set, member_types: set,
) -> list[CodeChunk]:
    """
    AST 트리에서 청크를 추출한다.

    전략:
    1. 최상위 노드를 순회하면서 대상 타입을 찾는다.
    2. 클래스를 만나면:
       - 작은 클래스 (50줄 이하): 통째로 하나의 청크
       - 큰 클래스 (50줄 초과): 시그니처 청크 + 내부 멤버 개별 청크
    3. 함수/프로퍼티 등은 그대로 개별 청크로 만든다.
    """
    chunks = []

    def make_chunk(node, chunk_type: str, name: str, parent_class: str = ""):
        """노드를 CodeChunk로 변환한다."""
        content = source_bytes[node.start_byte:node.end_byte].decode(
            "utf-8", errors="replace"
        )
        if len(content.strip()) < 30:
            return  # 너무 짧은 코드는 건너뛴다
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
        """
        클래스 노드를 처리한다.
        - 작은 클래스: 통째로 하나의 청크
        - 큰 클래스: 시그니처 + 내부 멤버 개별 청크로 분해
        """
        class_name = _get_node_name(node)
        full_class_name = f"{parent_class}.{class_name}" if parent_class else class_name
        lines = _get_node_lines(node)

        if lines <= CLASS_LINE_THRESHOLD:
            # ── 작은 클래스: 통째로 하나의 청크 ──
            make_chunk(node, node.type, class_name, parent_class)
        else:
            # ── 큰 클래스: 시그니처 + 내부 멤버 분해 ──

            # 1) 클래스 시그니처 청크
            signature = _get_class_signature(node, source_bytes)
            if len(signature.strip()) >= 30:
                chunks.append(CodeChunk(
                    file_path=file_path,
                    chunk_type="class_signature",
                    name=class_name,
                    content=signature,
                    start_line=node.start_point[0] + 1,
                    end_line=node.start_point[0] + 1,
                    parent_class=parent_class,
                ))

            # 2) 내부 멤버 개별 청크
            body = _get_class_body_node(node)
            if body:
                for child in body.children:
                    if child.type in CLASS_NODE_TYPES:
                        # 내부 클래스 → 재귀적으로 처리
                        process_class(child, parent_class=full_class_name)
                    elif child.type in member_types:
                        # 함수, 프로퍼티 등 → 개별 청크
                        make_chunk(
                            child, child.type,
                            _get_node_name(child),
                            parent_class=full_class_name,
                        )

    def visit(node):
        """최상위 노드를 순회한다."""
        if node.type in CLASS_NODE_TYPES:
            process_class(node)
        elif node.type in top_level_types:
            make_chunk(node, node.type, _get_node_name(node))
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return chunks


def chunk_file(file_path: str) -> list[CodeChunk]:
    """파일 하나를 읽어서 청크 목록으로 변환한다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source = f.read()

    source_bytes = source.encode("utf-8")

    if file_path.endswith(".kt") or file_path.endswith(".kts"):
        tree = kotlin_parser.parse(source_bytes)
        return _extract_chunks_from_tree(
            tree, source_bytes, file_path,
            KOTLIN_TOP_LEVEL_TYPES, KOTLIN_MEMBER_TYPES,
        )
    elif file_path.endswith(".java"):
        tree = java_parser.parse(source_bytes)
        return _extract_chunks_from_tree(
            tree, source_bytes, file_path,
            JAVA_TOP_LEVEL_TYPES, JAVA_MEMBER_TYPES,
        )
    else:
        return []


# ─────────────────────────────────────────────
# 4) 설정 파일 & 리소스 XML & 문서 청킹
# ─────────────────────────────────────────────

# 통째로 하나의 청크로 저장할 설정 파일 이름들
CONFIG_FILE_NAMES = {
    "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts",
    "gradle.properties", "local.properties",
    "proguard-rules.pro",
    "AndroidManifest.xml",
    "google-services.json",
}

# 통째로 하나의 청크로 저장할 확장자들
# (설정, CI/CD, 환경 설정 등 — 쪼개면 의미가 깨지는 파일)
WHOLE_FILE_EXTENSIONS = {
    ".json", ".yaml", ".yml",
    ".toml", ".properties", ".pro",
    ".env", ".cfg", ".ini", ".conf",
}

# 리소스 XML 중 항목별로 쪼갤 디렉토리 (values 계열)
VALUES_DIR_PREFIXES = ("values",)

# 리소스 XML 중 파일 단위로 통째로 저장할 디렉토리
WHOLE_FILE_RES_DIRS = {
    "layout", "menu", "navigation", "xml",
    "drawable", "anim", "animator",
}


def chunk_whole_file(file_path: str, relative_path: str, chunk_type: str = "config") -> list[CodeChunk]:
    """파일을 통째로 하나의 청크로 만든다."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    if len(content.strip()) < 10:
        return []
    return [CodeChunk(
        file_path=relative_path,
        chunk_type=chunk_type,
        name=os.path.basename(file_path),
        content=content,
        start_line=1,
        end_line=content.count("\n") + 1,
        parent_class="",
    )]


def chunk_markdown(file_path: str, relative_path: str) -> list[CodeChunk]:
    """
    마크다운 파일을 헤딩(#, ##, ###) 기준으로 섹션별 청크로 분리한다.

    AI 프롬프트, 기획 문서, README 등 .md 파일에 적합하다.
    헤딩이 없거나 섹션이 3개 이하이면 파일 통째로 하나의 청크로 만든다.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    # 헤딩으로 섹션 분리
    lines = content.split("\n")
    sections = []          # [(heading_text, start_line, lines), ...]
    current_heading = os.path.basename(file_path)  # 파일명을 기본 헤딩으로
    current_lines = []
    current_start = 1

    for line_no, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            # 이전 섹션 저장
            if current_lines:
                sections.append((current_heading, current_start, current_lines))
            # 새 섹션 시작
            current_heading = stripped.lstrip("#").strip()
            current_lines = [line]
            current_start = line_no
        else:
            current_lines.append(line)

    # 마지막 섹션 저장
    if current_lines:
        sections.append((current_heading, current_start, current_lines))

    # 섹션이 적으면 파일 통째로
    if len(sections) <= 3:
        return [CodeChunk(
            file_path=relative_path,
            chunk_type="document",
            name=os.path.basename(file_path),
            content=content,
            start_line=1,
            end_line=len(lines),
            parent_class="",
        )]

    # 섹션별 청크 생성
    chunks = []
    for heading, start_line, section_lines in sections:
        section_text = "\n".join(section_lines)
        if len(section_text.strip()) < 20:
            continue
        chunks.append(CodeChunk(
            file_path=relative_path,
            chunk_type="document_section",
            name=heading,
            content=section_text,
            start_line=start_line,
            end_line=start_line + len(section_lines) - 1,
            parent_class="",
        ))

    return chunks


def chunk_plaintext(file_path: str, relative_path: str) -> list[CodeChunk]:
    """
    텍스트 파일을 빈 줄 기준으로 문단별 청크로 분리한다.
    문단이 적으면 파일 통째로 하나의 청크로 만든다.
    """
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    # 빈 줄 기준으로 문단 분리
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

    # 문단이 적으면 파일 통째로
    if len(paragraphs) <= 3:
        return chunk_whole_file(file_path, relative_path, chunk_type="document")

    # 문단별 청크 생성
    chunks = []
    for start_line, para_lines in paragraphs:
        para_text = "\n".join(para_lines)
        if len(para_text.strip()) < 20:
            continue
        # 첫 줄을 이름으로 사용
        first_line = para_lines[0].strip()[:60]
        chunks.append(CodeChunk(
            file_path=relative_path,
            chunk_type="document_paragraph",
            name=first_line if first_line else "(paragraph)",
            content=para_text,
            start_line=start_line,
            end_line=start_line + len(para_lines) - 1,
            parent_class="",
        ))

    return chunks


def chunk_resource_xml_by_item(file_path: str, relative_path: str) -> list[CodeChunk]:
    """
    values 계열 XML (strings.xml, colors.xml, styles.xml 등)을
    각 리소스 항목별로 개별 청크로 분리한다.

    <string name="app_name">MyApp</string> → 1개 청크
    <color name="primary">#FF0000</color>  → 1개 청크

    항목이 적으면(5개 이하) 파일 통째로 하나의 청크로 만든다.
    """
    import re

    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if len(content.strip()) < 10:
        return []

    # 리소스 항목 패턴: <string ...>...</string>, <color ...>...</color> 등
    # 여러 줄에 걸친 항목도 매칭 (예: <style> ... </style>)
    pattern = re.compile(
        r'(<(?:string|color|dimen|bool|integer|string-array|integer-array|style|declare-styleable|attr|plurals)\b[^>]*>.*?</\1*?>|'
        r'<(?:string|color|dimen|bool|integer|item)\b[^/]*/>)',
        re.DOTALL,
    )

    # 간단한 방식: 각 최상위 자식 요소를 추출
    # 정규식 대신 줄 단위로 파싱
    items = []
    current_item_lines = []
    depth = 0

    for line_no, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()

        # 최상위 <resources> 태그 안의 직접 자식 요소를 추출
        if stripped.startswith("<?") or stripped == "<resources>" or stripped == "</resources>" or stripped == "":
            continue

        # 자식 요소 시작 감지
        if depth == 0 and stripped.startswith("<"):
            current_item_lines = [(line_no, line)]
            if "/>" in stripped or ("</" in stripped and ">" in stripped):
                # 한 줄짜리 요소
                items.append(current_item_lines)
                current_item_lines = []
            else:
                depth = 1
        elif depth > 0:
            current_item_lines.append((line_no, line))
            # 열림 태그 감지 (대략적)
            if stripped.startswith("<") and not stripped.startswith("</") and not stripped.startswith("<!--") and "/>" not in stripped:
                depth += 1
            if stripped.startswith("</") or stripped.endswith("/>"):
                depth -= 1
                if depth <= 0:
                    items.append(current_item_lines)
                    current_item_lines = []
                    depth = 0

    # 항목이 적으면 파일 통째로
    if len(items) <= 5:
        return [CodeChunk(
            file_path=relative_path,
            chunk_type="resource_file",
            name=os.path.basename(file_path),
            content=content,
            start_line=1,
            end_line=content.count("\n") + 1,
            parent_class="",
        )]

    # 항목별 청크 생성
    chunks = []
    for item_lines in items:
        item_text = "\n".join(line for _, line in item_lines)
        if len(item_text.strip()) < 10:
            continue

        # name 속성 추출
        import re as _re
        name_match = _re.search(r'name\s*=\s*"([^"]*)"', item_text)
        item_name = name_match.group(1) if name_match else "(unnamed)"

        chunks.append(CodeChunk(
            file_path=relative_path,
            chunk_type="resource_item",
            name=item_name,
            content=f"<!-- File: {relative_path} -->\n{item_text}",
            start_line=item_lines[0][0],
            end_line=item_lines[-1][0],
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
        file_path=relative_path,
        chunk_type="resource_file",
        name=os.path.basename(file_path),
        content=content,
        start_line=1,
        end_line=content.count("\n") + 1,
        parent_class="",
    )]


# ─────────────────────────────────────────────
# 5) 프로젝트 전체 청킹
# ─────────────────────────────────────────────

# 건너뛸 디렉토리들
SKIP_DIRS = {
    # 빌드 & 캐시
    "build", ".gradle", ".idea", ".git",
    "node_modules", "__pycache__",
    ".cxx",              # NDK 빌드 캐시
    ".kotlin",           # Kotlin 컴파일러 캐시
    "intermediates",     # Gradle 빌드 중간 산출물
    "generated",         # 자동 생성 코드
    "transforms",        # Gradle 변환 캐시
    "tmp",               # 임시 파일
    "captures",          # Android Studio 프로파일링

    # 테스트 (필요하면 제거)
    "test",
    "androidTest",

    # 기타
    ".github",
    ".vscode",
    "assets",            # 바이너리 에셋 (이미지, 폰트 등)
    "raw",               # raw 리소스 (바이너리)
    "mipmap",            # 앱 아이콘 (이미지)
}


def _get_res_dir_name(file_path: str) -> str:
    """res/ 하위 디렉토리 이름을 반환한다. (예: layout, values-ko, drawable)"""
    parts = file_path.replace("\\", "/").split("/")
    for i, part in enumerate(parts):
        if part == "res" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _is_values_dir(dir_name: str) -> bool:
    """values 계열 디렉토리인지 확인 (values, values-ko, values-night 등)"""
    return dir_name.startswith("values")


def _is_whole_file_res_dir(dir_name: str) -> bool:
    """파일 통째로 저장할 리소스 디렉토리인지 확인 (layout, layout-land 등)"""
    base = dir_name.split("-")[0]  # "layout-land" → "layout"
    return base in WHOLE_FILE_RES_DIRS


def chunk_project(project_path: str) -> list[CodeChunk]:
    """
    프로젝트 디렉토리를 재귀적으로 순회하면서
    코드, 설정 파일, 리소스 XML, 문서를 모두 청크로 변환한다.

    처리 대상:
    - Kotlin/Java 코드: AST 기반 함수/클래스 단위 청킹
    - 설정 파일 (build.gradle, AndroidManifest.xml 등): 파일 단위 청킹
    - values XML (strings.xml, colors.xml 등): 리소스 항목별 청킹
    - layout/navigation XML: 파일 단위 청킹
    - 마크다운 (.md): 헤딩 기준 섹션별 청킹
    - 기타 텍스트 (.txt): 문단별 청킹
    - JSON/YAML/TOML 등 설정: 파일 단위 청킹

    Args:
        project_path: 안드로이드 프로젝트 루트 경로

    Returns:
        CodeChunk 리스트
    """
    all_chunks = []
    project_path = os.path.abspath(project_path)

    stats = {"code": 0, "config": 0, "resource": 0, "document": 0}

    for root, dirs, files in os.walk(project_path):
        # 건너뛸 디렉토리 제외
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, project_path)
            _, ext = os.path.splitext(filename)

            try:
                # ── 1) Kotlin/Java 코드 파일 ──
                if ext in (".kt", ".kts", ".java"):
                    chunks = chunk_file(full_path)
                    for chunk in chunks:
                        chunk.file_path = relative_path
                    all_chunks.extend(chunks)
                    stats["code"] += len(chunks)

                # ── 2) 이름으로 매칭하는 설정 파일 ──
                elif filename in CONFIG_FILE_NAMES:
                    chunks = chunk_whole_file(full_path, relative_path, "config")
                    all_chunks.extend(chunks)
                    stats["config"] += len(chunks)

                # ── 3) 마크다운 문서 (AI 프롬프트, README, 기획 문서 등) ──
                elif ext == ".md":
                    chunks = chunk_markdown(full_path, relative_path)
                    all_chunks.extend(chunks)
                    stats["document"] += len(chunks)

                # ── 4) 확장자로 매칭하는 설정/환경 파일 ──
                elif ext in WHOLE_FILE_EXTENSIONS:
                    chunks = chunk_whole_file(full_path, relative_path, "config")
                    all_chunks.extend(chunks)
                    stats["config"] += len(chunks)

                # ── 5) 리소스 XML ──
                elif ext == ".xml":
                    res_dir = _get_res_dir_name(relative_path)
                    if _is_values_dir(res_dir):
                        chunks = chunk_resource_xml_by_item(full_path, relative_path)
                        all_chunks.extend(chunks)
                        stats["resource"] += len(chunks)
                    elif _is_whole_file_res_dir(res_dir):
                        chunks = chunk_resource_xml_whole(full_path, relative_path)
                        all_chunks.extend(chunks)
                        stats["resource"] += len(chunks)

                # ── 6) 일반 텍스트 파일 ──
                elif ext == ".txt":
                    chunks = chunk_plaintext(full_path, relative_path)
                    all_chunks.extend(chunks)
                    stats["document"] += len(chunks)

            except Exception as e:
                print(f"  [WARN] {relative_path} 처리 실패: {e}")

    print(
        f"       코드: {stats['code']}개 | 설정: {stats['config']}개 | "
        f"리소스: {stats['resource']}개 | 문서: {stats['document']}개"
    )
    return all_chunks


# ─────────────────────────────────────────────
# 6) 직접 실행 시 테스트
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("사용법: python chunker.py /path/to/android-project")
        sys.exit(1)

    project = sys.argv[1]
    print(f"프로젝트 청킹 시작: {project}")
    chunks = chunk_project(project)
    print(f"총 {len(chunks)}개의 청크 생성됨\n")

    # 처음 5개 미리보기
    for i, chunk in enumerate(chunks[:5]):
        print(f"── 청크 {i+1} ──")
        print(f"  파일: {chunk.file_path}")
        print(f"  타입: {chunk.chunk_type}")
        print(f"  이름: {chunk.name}")
        if chunk.parent_class:
            print(f"  소속: {chunk.parent_class}")
        print(f"  줄:   {chunk.start_line}-{chunk.end_line}")
        print(f"  코드 미리보기: {chunk.content[:100]}...")
        print()
```

### 청킹 테스트

```bash
python chunker.py /path/to/your/android-project
```

정상적으로 동작하면 아래처럼 출력됩니다:

```
프로젝트 청킹 시작: /path/to/your/android-project
       코드: 1,024개 | 설정: 12개 | 리소스: 215개 | 문서: 18개
총 1,269개의 청크 생성됨

── 청크 1 ──
  파일: build.gradle.kts
  타입: config                      ← 설정 파일 → 통째로 하나의 청크
  이름: build.gradle.kts
  줄:   1-45
  코드 미리보기: plugins {
    id("com.android.application") version "8.2.0"...

── 청크 2 ──
  파일: docs/AI_PROMPT.md
  타입: document_section            ← 마크다운 → 헤딩 기준 섹션별 청크
  이름: 코드 스타일 가이드
  줄:   15-42
  코드 미리보기: ## 코드 스타일 가이드
이 프로젝트에서는 Kotlin 공식 코딩 컨벤션을 따릅니다...

── 청크 3 ──
  파일: app/src/main/res/values/strings.xml
  타입: resource_item               ← 리소스 항목 → 개별 청크
  이름: app_name
  줄:   3-3
  코드 미리보기: <!-- File: app/src/main/res/values/strings.xml -->
    <string name="app_name">MyApp...

── 청크 4 ──
  파일: app/src/main/res/layout/activity_main.xml
  타입: resource_file               ← 레이아웃 → 파일 통째로 하나의 청크
  이름: activity_main.xml
  줄:   1-52
  코드 미리보기: <?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://...

── 청크 5 ──
  파일: app/src/main/java/com/example/data/UserRepository.kt
  타입: class_signature             ← 큰 클래스 시그니처 → 별도 청크
  이름: UserRepository
  줄:   8-8
  코드 미리보기: class UserRepository(private val dao: UserDao, private val api: UserApi) { ... }...
```

> **청킹 대상 정리**
>
> | 파일 종류 | 청킹 방식 | 예시 |
> |-----------|-----------|------|
> | Kotlin/Java 코드 | AST 기반 (함수·클래스 단위) | `UserRepository.kt` → `getUser` 함수 청크 |
> | 마크다운 문서 | 헤딩(`#`) 기준 섹션별 | `AI_PROMPT.md` → 섹션별 청크 |
> | 설정 파일 | 파일 통째로 | `build.gradle.kts`, `AndroidManifest.xml` |
> | values XML | 리소스 항목별 분리 | `strings.xml` → 각 `<string>` 청크 |
> | layout/navigation XML | 파일 통째로 | `activity_main.xml` 전체가 하나의 청크 |
> | 건너뛰는 것들 | 무시 | `build/`, `.gradle/`, `mipmap/`, 이미지 등 |

---

## 4. Step 2: 임베딩 & 벡터DB 저장

청크로 쪼갠 코드를 `jina-code-embeddings-1.5b` 모델로 벡터화하고, ChromaDB에 저장합니다.
이 과정을 "인덱싱"이라고 합니다. 한 번 실행하면 됩니다.

### 왜 jina-code-embeddings-1.5b인가?

| 특징 | 값 |
|------|------|
| 차원 | **1536** (OpenAI text-embedding-3-small과 동일) |
| 크기 | ~3GB |
| 컨텍스트 | 8,192 토큰 (긴 함수도 잘리지 않음) |
| 특화 | **코드 검색** — 자연어 질문으로 코드를 찾도록 훈련됨 |
| 지원 언어 | Kotlin, Java 포함 15개 이상 프로그래밍 언어 |
| 벤치마크 | 25개 코드 검색 벤치마크에서 SOTA |
| 비용 | **무료** — 로컬 실행 |

### indexer.py

```python
"""
indexer.py — 청크를 임베딩하고 ChromaDB에 저장한다.

사용법:
    python indexer.py /path/to/android-project

이 스크립트는 한 번만 실행하면 됩니다.
코드가 변경되면 다시 실행하세요.

API Key 불필요 — jina-code-embeddings-1.5b 로컬 모델을 사용합니다.
Apple Silicon MPS 가속을 자동으로 사용합니다.
"""

import sys
import os
import hashlib
import torch
from sentence_transformers import SentenceTransformer
from chunker import chunk_project
import chromadb

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "jinaai/jina-code-embeddings-1.5b"

CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
COLLECTION_NAME = "android_codebase"
BATCH_SIZE = 32  # M4 Pro 메모리에 맞는 배치 크기


# ─────────────────────────────────────────────
# 1) 디바이스 설정 (Apple Silicon MPS 자동 감지)
# ─────────────────────────────────────────────

def get_device() -> str:
    """사용 가능한 최적의 디바이스를 반환한다."""
    if torch.backends.mps.is_available():
        return "mps"  # Apple Silicon GPU 가속
    elif torch.cuda.is_available():
        return "cuda"  # NVIDIA GPU
    else:
        return "cpu"


device = get_device()


# ─────────────────────────────────────────────
# 2) 임베딩 모델 로드
# ─────────────────────────────────────────────

print(f"임베딩 모델 로드 중: {EMBEDDING_MODEL_NAME}")
print(f"  디바이스: {device}")
print(f"  (처음 실행 시 ~3GB 모델 다운로드에 5-10분 걸릴 수 있습니다)")

embed_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    model_kwargs={
        "torch_dtype": torch.float32,  # MPS에서는 float32가 안정적
    },
    tokenizer_kwargs={
        "padding_side": "left",  # jina-code-embeddings 권장 설정
    },
    device=device,
)

print(f"  → 모델 로드 완료! (1536차원, 코드 특화)\n")


# ─────────────────────────────────────────────
# 3) 임베딩 생성
# ─────────────────────────────────────────────

def create_embeddings_for_documents(texts: list[str]) -> list[list[float]]:
    """
    코드 청크(문서)를 임베딩 벡터로 변환한다.
    jina-code-embeddings의 nl2code_document 프롬프트를 사용한다.
    """
    embeddings = embed_model.encode(
        texts,
        prompt_name="nl2code_document",  # "이 텍스트는 코드 문서입니다" 라는 맥락 부여
        show_progress_bar=False,
        batch_size=BATCH_SIZE,
    )
    return embeddings.tolist()


# ─────────────────────────────────────────────
# 4) ChromaDB에 저장
# ─────────────────────────────────────────────

def index_project(project_path: str):
    """
    프로젝트를 청킹하고 임베딩해서 ChromaDB에 저장한다.

    Args:
        project_path: 안드로이드 프로젝트 루트 경로
    """
    # 1. 청킹
    print(f"[1/3] 프로젝트 청킹 중: {project_path}")
    chunks = chunk_project(project_path)
    print(f"       → {len(chunks)}개 청크 생성됨")

    if not chunks:
        print("청크가 없습니다. 프로젝트 경로를 확인하세요.")
        return

    # 2. ChromaDB 준비 (기존 컬렉션이 있으면 삭제 후 재생성)
    print(f"[2/3] ChromaDB 준비 중: {CHROMA_DB_PATH}")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    try:
        chroma_client.delete_collection(COLLECTION_NAME)
        print("       → 기존 컬렉션 삭제됨 (재인덱싱)")
    except ValueError:
        pass

    collection = chroma_client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # 3. 배치 단위로 임베딩 생성 + 저장
    print(f"[3/3] 임베딩 생성 및 저장 중 (배치 크기: {BATCH_SIZE}, 디바이스: {device})")
    total = len(chunks)

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]

        # 임베딩에 사용할 텍스트 생성
        texts = [chunk.to_text_for_embedding() for chunk in batch]

        # 고유 ID 생성 (파일경로 + 줄번호 해시)
        ids = []
        for chunk in batch:
            raw = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
            chunk_id = hashlib.md5(raw.encode()).hexdigest()
            ids.append(chunk_id)

        # 메타데이터 생성
        metadatas = [
            {
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "parent_class": chunk.parent_class,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
            for chunk in batch
        ]

        # 임베딩 생성 (로컬 MPS 가속 — API 호출 없음)
        embeddings = create_embeddings_for_documents(texts)

        # ChromaDB에 저장
        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        progress = min(i + BATCH_SIZE, total)
        print(f"       → {progress}/{total} 완료")

    print(f"\n✅ 인덱싱 완료! {total}개 청크가 ChromaDB에 저장되었습니다.")
    print(f"   저장 위치: {CHROMA_DB_PATH}")
    print(f"   임베딩 차원: 1536")
    print(f"   사용 디바이스: {device}")


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python indexer.py /path/to/android-project")
        sys.exit(1)

    index_project(sys.argv[1])
```

### 인덱싱 실행

```bash
python indexer.py /path/to/your/android-project
```

출력 예시:

```
임베딩 모델 로드 중: jinaai/jina-code-embeddings-1.5b
  디바이스: mps
  (처음 실행 시 ~3GB 모델 다운로드에 5-10분 걸릴 수 있습니다)
  → 모델 로드 완료! (1536차원, 코드 특화)

[1/3] 프로젝트 청킹 중: /path/to/your/android-project
       → 847개 청크 생성됨
[2/3] ChromaDB 준비 중: ./chroma_db
[3/3] 임베딩 생성 및 저장 중 (배치 크기: 32, 디바이스: mps)
       → 32/847 완료
       → 64/847 완료
       ...
       → 847/847 완료

✅ 인덱싱 완료! 847개 청크가 ChromaDB에 저장되었습니다.
   저장 위치: ./chroma_db
   임베딩 차원: 1536
   사용 디바이스: mps
```

> **M4 Pro 기준 예상 소요 시간**
> - 모델 최초 다운로드: 5-10분 (한 번만)
> - 500개 청크 인덱싱: 약 2-3분
> - 1,000개 청크 인덱싱: 약 4-6분

---

## 5. Step 3: 검색 모듈

질문이 들어오면 벡터DB에서 관련 코드를 검색해서 돌려줍니다.
답변 생성은 Claude Code가 알아서 하므로, 이 모듈은 검색만 담당합니다.

### search.py

```python
"""
search.py — 벡터DB에서 질문과 관련된 코드를 검색한다.

사용법:
    from search import search_code
    results = search_code("유저 정보 가져오는 코드 어디있어?")

API Key 불필요 — jina-code-embeddings-1.5b 로컬 모델을 사용합니다.
"""

import os
import torch
from sentence_transformers import SentenceTransformer
import chromadb

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "jinaai/jina-code-embeddings-1.5b"
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")
COLLECTION_NAME = "android_codebase"
TOP_K = 10  # 검색할 코드 청크 개수


# ─────────────────────────────────────────────
# 디바이스 설정
# ─────────────────────────────────────────────

def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    else:
        return "cpu"


device = get_device()

# 모델 로드 (서버 시작 시 한 번만 실행됨)
print(f"검색 모델 로드 중: {EMBEDDING_MODEL_NAME} ({device})")
embed_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME,
    model_kwargs={
        "torch_dtype": torch.float32,
    },
    tokenizer_kwargs={
        "padding_side": "left",
    },
    device=device,
)
print("  → 모델 로드 완료!\n")


# ─────────────────────────────────────────────
# 검색 함수
# ─────────────────────────────────────────────

def search_code(question: str, top_k: int = TOP_K) -> list[dict]:
    """
    질문과 의미적으로 가장 가까운 코드 청크를 검색한다.

    jina-code-embeddings의 nl2code 태스크를 사용한다:
    - 질문: nl2code_query 프롬프트 (자연어 → 코드 검색)
    - 코드: nl2code_document 프롬프트 (인덱싱 시 사용)

    Args:
        question: 사용자의 질문
        top_k: 반환할 결과 수

    Returns:
        [{"code": "...", "file_path": "...", "name": "...", "distance": 0.25}, ...]
    """
    # 질문을 벡터로 변환 (nl2code_query: "자연어로 코드를 찾겠다"는 맥락)
    question_vector = embed_model.encode(
        question,
        prompt_name="nl2code_query",
    ).tolist()

    # ChromaDB에서 검색
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collection = chroma_client.get_collection(COLLECTION_NAME)

    results = collection.query(
        query_embeddings=[question_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    # 결과 정리
    search_results = []
    for i in range(len(results["ids"][0])):
        search_results.append({
            "code": results["documents"][0][i],
            "file_path": results["metadatas"][0][i]["file_path"],
            "name": results["metadatas"][0][i]["name"],
            "chunk_type": results["metadatas"][0][i]["chunk_type"],
            "parent_class": results["metadatas"][0][i]["parent_class"],
            "start_line": results["metadatas"][0][i]["start_line"],
            "end_line": results["metadatas"][0][i]["end_line"],
            "distance": results["distances"][0][i],
        })

    return search_results


def format_results(results: list[dict]) -> str:
    """검색 결과를 읽기 좋은 문자열로 포맷팅한다."""
    if not results:
        return "관련 코드를 찾지 못했습니다."

    output_parts = []
    for i, r in enumerate(results, 1):
        # 소속 클래스가 있으면 "클래스.이름" 형태로 표시
        display_name = r["name"]
        if r["parent_class"]:
            display_name = f"{r['parent_class']}.{r['name']}"

        output_parts.append(
            f"━━━ 검색 결과 {i} ━━━\n"
            f"📁 파일: {r['file_path']}\n"
            f"📌 이름: {display_name} ({r['chunk_type']})\n"
            f"📍 줄:   {r['start_line']}-{r['end_line']}\n"
            f"📊 유사도 거리: {r['distance']:.4f} (낮을수록 유사)\n"
            f"\n{r['code']}\n"
        )

    return "\n".join(output_parts)


# ─────────────────────────────────────────────
# 직접 실행 시 대화형 테스트
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🔍 안드로이드 코드 검색기입니다! 코드에 대해 검색해보세요.")
    print("   종료하려면 'quit'을 입력하세요.\n")

    while True:
        question = input("검색> ").strip()
        if question.lower() in ("quit", "exit", "q"):
            print("👋 안녕히 가세요!")
            break
        if not question:
            continue

        print("\n🔍 검색 중...\n")
        results = search_code(question)
        print(format_results(results))
        print()
```

### 검색 테스트

```bash
python search.py
```

```
검색 모델 로드 중: jinaai/jina-code-embeddings-1.5b (mps)
  → 모델 로드 완료!

🔍 안드로이드 코드 검색기입니다! 코드에 대해 검색해보세요.
   종료하려면 'quit'을 입력하세요.

검색> 유저 프로필 수정하는 API

🔍 검색 중...

━━━ 검색 결과 1 ━━━
📁 파일: app/src/main/java/com/example/api/UserApiService.kt
📌 이름: UserApiService.updateProfile (function_declaration)
📍 줄:   35-42
📊 유사도 거리: 0.1203 (낮을수록 유사)

// File: app/src/main/java/com/example/api/UserApiService.kt
// Class: UserApiService
// Type: function_declaration | Name: updateProfile
suspend fun updateProfile(request: UpdateProfileRequest): Response<UserProfile> {
    return apiClient.put("/api/v1/users/profile", request)
}
```

> **jina-code-embeddings의 강점**:
> "유저 프로필 수정"이라는 자연어 질문으로 `updateProfile`, `EditUserUseCase`,
> `ProfileRepository.save()` 같은 코드를 모두 찾을 수 있습니다.
> 함수 이름에 "유저"나 "프로필"이 없더라도 의미적으로 관련된 코드를 찾아줍니다.

---

## 6. Step 4: MCP 서버로 감싸기

검색 모듈을 MCP 서버로 만들면 Claude Code에서 바로 사용할 수 있습니다.
MCP 서버는 검색만 담당하고, 답변 생성은 Claude Code가 처리합니다.

### server.py

```python
"""
server.py — 안드로이드 집사 MCP 서버

사용법:
    python server.py

API Key 불필요 — jina-code-embeddings-1.5b 로컬 모델을 사용합니다.
답변 생성은 Claude Code가 담당합니다.
"""

from fastmcp import FastMCP
from search import search_code, format_results

# ─────────────────────────────────────────────
# MCP 서버 생성
# ─────────────────────────────────────────────

mcp = FastMCP(
    name="android-butler",
    instructions=(
        "안드로이드 코드베이스에서 관련 코드를 검색하는 도구입니다. "
        "코드 구조, API 사용법, 비즈니스 로직 등에 대해 질문하면 "
        "관련 코드를 찾아서 돌려줍니다. "
        "이 도구의 검색 결과를 바탕으로 답변을 생성해주세요."
    ),
)


@mcp.tool()
def search_android_code(query: str, top_k: int = 10) -> str:
    """
    안드로이드 코드베이스에서 질문과 관련된 코드를 검색합니다.

    1536차원 코드 특화 임베딩(jina-code-embeddings-1.5b)을 사용하는
    의미 기반 검색(semantic search)입니다.
    키워드가 정확히 일치하지 않아도, 의미가 비슷한 코드를 찾을 수 있습니다.

    질문 예시:
    - "유저 프로필 수정하는 API 어디있어?"
    - "결제 로직 흐름이 어떻게 돼?"
    - "네트워크 에러 처리는 어떻게 하고 있어?"
    - "Room DB에 저장하는 엔티티 목록 알려줘"
    - "로그인 화면 ViewModel 코드 보여줘"
    - "Retrofit 인터셉터에서 토큰 갱신 로직"

    Args:
        query: 검색할 질문 또는 키워드
        top_k: 반환할 결과 수 (기본값: 10, 최대: 20)

    Returns:
        검색된 코드 조각들 (파일 경로, 이름, 줄 번호, 코드 포함)
    """
    top_k = min(top_k, 20)
    results = search_code(query, top_k=top_k)
    return format_results(results)


# ─────────────────────────────────────────────
# 서버 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
```

---

## 7. Step 5: Claude Code에 연결하기

MCP 서버를 Claude Code에 등록하면 끝입니다.

### 방법 1: Claude Code CLI로 등록 (추천)

```bash
# android-butler 디렉토리에서 실행
claude mcp add android-butler -- python /absolute/path/to/android-butler/server.py
```

> `/absolute/path/to/` 부분을 실제 경로로 바꾸세요.
> 예: `python /Users/yourname/projects/android-butler/server.py`

### 방법 2: 설정 파일 직접 수정

프로젝트 루트 또는 홈 디렉토리에 `.claude/mcp.json` 파일을 만드세요:

```json
{
  "mcpServers": {
    "android-butler": {
      "command": "python",
      "args": ["/absolute/path/to/android-butler/server.py"]
    }
  }
}
```

> API Key가 필요 없으므로 `env` 항목이 없습니다!

### 사용하기

Claude Code를 실행하면 안드로이드 집사 도구가 자동으로 연결됩니다.

```
사용자> 유저 로그인 로직이 어떻게 되어있어?

Claude Code가 android-butler의 search_android_code 도구를 호출합니다...
(관련 코드 10개가 검색됨)

Claude Code> 로그인 로직은 다음과 같이 구성되어 있습니다:

1. LoginViewModel.kt (25-48줄)
   - login() 함수에서 LoginUseCase를 호출
   - 이메일/비밀번호 유효성 검사 후 API 호출
   ...

2. LoginUseCase.kt (12-30줄)
   - AuthRepository.signIn()을 호출하고 토큰 저장
   ...

3. AuthRepository.kt (45-67줄)
   - Retrofit으로 POST /api/v1/auth/login 요청
   - 응답의 accessToken을 DataStore에 저장
   ...
```

---

## 8. 실행 순서 요약

처음 설정할 때 아래 순서대로 진행하세요:

```bash
# 1. 프로젝트 생성 및 패키지 설치
mkdir android-butler && cd android-butler
pip install chromadb tree-sitter tree-sitter-kotlin tree-sitter-java "fastmcp>=2.0.0" "sentence-transformers>=5.0.0" "torch>=2.7.0"

# 2. 위의 4개 파일 생성
#    chunker.py, indexer.py, search.py, server.py

# 3. 인덱싱 (한 번만 실행 — API Key 불필요, MPS 가속)
python indexer.py /path/to/your/android-project

# 4. 로컬 테스트 (선택사항)
python search.py

# 5. Claude Code에 MCP 서버 등록
claude mcp add android-butler -- python $(pwd)/server.py

# 6. Claude Code에서 사용!
```

코드가 업데이트되면 `python indexer.py`만 다시 실행하면 됩니다.

---

## 9. 개선 아이디어

### 클래스 분해 기준 조정

현재 50줄을 기준으로 큰 클래스를 분해합니다. 프로젝트 특성에 따라 조정할 수 있습니다:

```python
# chunker.py에서
CLASS_LINE_THRESHOLD = 50   # 기본값: 50줄 초과 시 분해
CLASS_LINE_THRESHOLD = 30   # 더 세밀하게 분해 (청크가 많아짐)
CLASS_LINE_THRESHOLD = 100  # 큰 클래스도 통째로 유지 (청크가 줄어듦)
```

### 자동 재인덱싱

git hook을 사용해 코드가 변경될 때마다 자동으로 재인덱싱할 수 있습니다:

```bash
# .git/hooks/post-merge 파일 생성
#!/bin/bash
python /path/to/android-butler/indexer.py /path/to/android-project
```

### 여러 프로젝트 지원

컬렉션 이름을 프로젝트별로 분리하면 됩니다:

```python
# indexer.py와 search.py에서
COLLECTION_NAME = "project_a_codebase"  # 프로젝트마다 다른 이름
```

### 하이브리드 검색 (의미 + 키워드)

ChromaDB의 `where_document` 파라미터로 키워드 필터를 추가할 수 있습니다:

```python
results = collection.query(
    query_embeddings=[question_vector],
    n_results=top_k,
    where_document={"$contains": "Repository"},  # 키워드 필터
)
```

---

## 10. 트러블슈팅

### "ModuleNotFoundError: No module named 'tree_sitter_kotlin'"

```bash
pip install tree-sitter-kotlin tree-sitter-java
```

### "ModuleNotFoundError: No module named 'sentence_transformers'"

```bash
pip install "sentence-transformers>=5.0.0"
```

### MPS에서 에러가 발생할 때

일부 연산이 MPS에서 지원되지 않을 수 있습니다. 이 경우 CPU로 fallback하세요:

```python
# indexer.py와 search.py에서 get_device() 함수를 수정
def get_device() -> str:
    return "cpu"  # MPS 에러 시 CPU로 강제 설정
```

> CPU에서도 M4 Pro라면 충분히 빠릅니다.
> 인덱싱은 약 1.5-2배 느려지지만, 검색(질문 1건)은 체감 차이가 거의 없습니다.

### "chromadb.errors.InvalidCollectionException"

인덱싱을 먼저 실행하세요:

```bash
python indexer.py /path/to/your/android-project
```

### 검색 결과가 부정확할 때

1. `TOP_K` 값을 늘려보세요 (search.py에서 10 → 15)
2. 질문을 더 구체적으로 해보세요 (예: "로그인" → "이메일 로그인 API 요청 코드")
3. 청크가 너무 짧은 건 아닌지 확인하세요 (chunker.py의 최소 길이 30 → 50으로 조정)

### 처음 실행 시 모델 다운로드가 느릴 때

`jina-code-embeddings-1.5b`는 ~3GB입니다.
네트워크 환경에 따라 5-10분 걸릴 수 있습니다.
한 번 다운로드되면 `~/.cache/huggingface/` 에 캐시되어 다음부터는 즉시 로드됩니다.

### 메모리 부족 (Out of Memory)

배치 크기를 줄이세요:

```python
# indexer.py에서
BATCH_SIZE = 16  # 32에서 16으로 줄이기
```

---

## 비용 요약

| 항목 | 비용 |
|------|------|
| 임베딩 모델 (jina-code-embeddings-1.5b) | **무료** — 로컬 실행 |
| 벡터DB (ChromaDB) | **무료** — 로컬 실행 |
| 답변 생성 (Claude Code) | **무료** — 구독에 포함 |
| **합계** | **추가 과금 없음** |
