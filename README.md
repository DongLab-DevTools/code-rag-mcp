# code-rag-mcp

로컬 임베딩 기반 코드 검색 MCP 서버.
프로젝트를 인덱싱하면 자연어로 코드를 검색할 수 있습니다.

## 기능

- **자연어 코드 검색** — "로그인 로직이 어떻게 돼?" 같은 질문으로 관련 코드를 찾습니다
- **AST 기반 코드 청킹** — 함수/클래스 단위로 의미 있게 분할합니다
- **로컬 임베딩** — 외부 API 없이 로컬에서 임베딩을 생성합니다 (Jina Code Embeddings 1.5B)
- **질문 유형 자동 감지** — 자연어, 코드, 에러 질문에 따라 최적의 검색 전략을 선택합니다
- **Claude Code 연동** — MCP 서버로 Claude Code에서 직접 검색할 수 있습니다
- **Slack 봇** — 슬랙에서 멘션으로 코드 질문을 할 수 있습니다
- **멀티 프로젝트** — 여러 프로젝트를 인덱싱하고 프로젝트별 또는 전체 검색이 가능합니다

## 동작 방식

```
1. 인덱싱 (사전 준비, 1회성)

   프로젝트 소스코드
     → chunker (AST 파싱으로 함수/클래스 단위 분할)
     → indexer (Jina Code Embeddings로 벡터 생성)
     → ChromaDB (벡터 저장)

2. 검색

   자연어 질문
     → 질문 유형 감지 (nl2code / code2code / techqa)
     → 질문을 벡터로 변환
     → ChromaDB에서 cosine 유사도 검색
     → 관련 코드 + 확신도 반환
```

## 지원 프로젝트 타입

| 타입 | 언어 | 파서 | 청킹 기준 |
|------|------|------|----------|
| Android | Kotlin, Java | tree-sitter-kotlin, tree-sitter-java | [CHUNKING.md](analysis/chunkers/android/CHUNKING.md) |
| iOS | Swift | tree-sitter-swift | [CHUNKING.md](analysis/chunkers/ios/CHUNKING.md) |
| 공통 | 설정, 문서, XML 등 | - | [CHUNKING.md](analysis/chunkers/common/CHUNKING.md) |

모든 프로젝트 타입에서 바이너리를 제외한 나머지 파일도 텍스트로 읽어서 인덱싱합니다.

## 새 프로젝트 타입 추가하기

예시: TypeScript 지원 추가

**1. chunker 파일 생성** — `analysis/chunkers/web/typescript.py`

```python
import tree_sitter_typescript as ts_typescript
from tree_sitter import Language, Parser
from analysis.chunkers.base import CodeChunk, extract_chunks_from_tree

TYPESCRIPT_LANGUAGE = Language(ts_typescript.language())
typescript_parser = Parser(TYPESCRIPT_LANGUAGE)

CLASS_NODE_TYPES = {"class_declaration", "interface_declaration", ...}
MEMBER_TYPES = {"method_definition", "public_field_definition", ...}
TOP_LEVEL_TYPES = {"function_declaration", "lexical_declaration"} | CLASS_NODE_TYPES
BODY_TYPES = {"class_body", "interface_body"}

def chunk_typescript(file_path: str) -> list[CodeChunk]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        source_bytes = f.read().encode("utf-8")
    tree = typescript_parser.parse(source_bytes)
    return extract_chunks_from_tree(
        tree, source_bytes, file_path,
        CLASS_NODE_TYPES, TOP_LEVEL_TYPES, MEMBER_TYPES, BODY_TYPES,
    )
```

**2. `__init__.py`에 export 추가** — `analysis/chunkers/web/__init__.py`

```python
from analysis.chunkers.web.typescript import chunk_typescript
```

**3. `chunker.py`에 확장자 분기 추가**

```python
elif ext in (".ts", ".tsx"):
    chunks = chunk_typescript(full_path)
```

**4. 패키지 설치**

```bash
pip install tree-sitter-typescript
```

**5. CHUNKING.md 작성** — `analysis/chunkers/web/CHUNKING.md`

## 설치

### Claude Code 플러그인으로 설치 (권장)

```
/plugin install code-rag-mcp
/init            # Python/패키지 설치 + 임베딩 모델 다운로드(~3GB, 최초 1회만)
/project-add     # 프로젝트 인덱싱
```

### 수동 설치

```bash
git clone https://github.com/your-username/code-rag-mcp.git
cd code-rag-mcp
./init.sh        # Python/venv/패키지/모델까지 자동 셋업
```

## 사용법

### 프로젝트 인덱싱

```bash
source venv/bin/activate
python analysis/indexer.py --name myapp /path/to/project

# 인덱싱된 프로젝트 확인
python analysis/indexer.py --list
```

### Claude Code에서 사용

MCP 서버 등록:
```bash
claude mcp add code-rag-mcp -- $(pwd)/venv/bin/python $(pwd)/server/mcp_server.py
```

검색:
```
/search-myapp 로그인 로직이 어떻게 돼?
```

### Slack 봇으로 사용

`.env` 파일 생성:
```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

실행:
```bash
./start.sh        # 백그라운드
./start.sh --log  # 로그 실시간 출력
./stop.sh         # 종료
```

슬랙에서:
```
@code-rag-mcp 로그인 로직이 어떻게 돼?
@code-rag-mcp myapp 유저 정보 조회하는 코드
```

## 기술 스택

| 구성 | 사용 |
|------|------|
| 임베딩 | Jina Code Embeddings 1.5B (로컬) |
| 벡터DB | ChromaDB |
| 코드 파싱 | tree-sitter |
| MCP 서버 | FastMCP |
| API 서버 | FastAPI |
| Slack 봇 | slack-bolt (Socket Mode) |
| 답변 생성 | Claude CLI |

## 프로젝트 구조

```
code-rag-mcp/
├── analysis/                # 코드 분석 엔진
│   ├── chunker.py           # 진입점 (chunk_project)
│   ├── chunkers/            # 프로젝트 타입별 청킹
│   │   ├── android/         # Kotlin, Java
│   │   ├── ios/             # Swift
│   │   └── common/          # 설정, 문서, 리소스
│   ├── indexer.py           # 임베딩 생성 + 벡터DB 저장
│   └── search.py            # 벡터DB 검색
├── server/                  # 서버
│   ├── mcp_server.py        # MCP 서버 (Claude Code 연동)
│   ├── api_server.py        # REST API
│   └── slack_bot.py         # Slack 봇
├── skills/                  # Claude Code 슬래시 커맨드
├── .claude-plugin/          # Claude Code 플러그인 매니페스트
├── start.sh / stop.sh       # 서버 실행/종료
└── SETUP.md                 # 상세 셋업 가이드
```
