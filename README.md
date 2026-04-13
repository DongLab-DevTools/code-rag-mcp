# code-rag-mcp

[![Hits](https://myhits.vercel.app/api/hit/https%3A%2F%2Fgithub.com%2FDongLab-DevTools%2Fcode-rag-mcp%3Ftab%3Dreadme-ov-file?color=blue&label=hits&size=small)](https://myhits.vercel.app)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-D97757?style=flat-square)](https://docs.anthropic.com/en/docs/claude-code)
[![MCP](https://img.shields.io/badge/MCP-Server-10A37F?style=flat-square)](https://modelcontextprotocol.io)
[![Python](https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org)

## 개요

로컬 임베딩 기반 코드 검색 MCP 플러그인입니다.
프로젝트를 한 번 인덱싱해두면 Claude Code에서 **자연어로 코드베이스를 검색**할 수 있고,
슬랙에서 봇을 멘션해 코드 질문을 던질 수도 있습니다.

<br>
<br>

외부 API 없이 **로컬에서 Jina Code Embeddings 1.5B 모델**을 돌려 임베딩을 만들고 ChromaDB에 저장합니다.
질문 유형(자연어/코드/에러)을 자동으로 감지해 검색 전략을 바꾸므로, "로그인 로직 어떻게 돼?" 같은 자연어 질문부터 스택트레이스 기반 질문까지 같은 인터페이스로 처리합니다.

<br>

## 주요 기능

- **자연어 코드 검색**: "로그인 로직이 어떻게 돼?" 같은 질문으로 관련 코드를 찾습니다
- **AST 기반 코드 청킹**: tree-sitter로 함수/클래스 단위로 의미 있게 분할합니다
- **로컬 임베딩**: 외부 API 없이 로컬에서 임베딩을 생성합니다 (Jina Code Embeddings 1.5B)
- **질문 유형 자동 감지**: 자연어(nl2code) / 코드(code2code) / 에러 질문(techqa)에 따라 검색 전략을 선택합니다
- **Claude Code 연동**: MCP 서버로 Claude Code에서 바로 검색할 수 있습니다
- **Slack 봇**: 슬랙에서 멘션으로 코드 질문을 할 수 있습니다
- **멀티 프로젝트**: 여러 프로젝트를 인덱싱하고 프로젝트별 또는 전체 검색이 가능합니다

<br>

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

<br>

## 설치

### Step 1: 마켓플레이스 등록

Claude Code에서 마켓플레이스를 추가합니다:

```
/plugin marketplace add DongLab-DevTools/code-rag-mcp
```

### Step 2: 플러그인 설치

```
/plugin install code-rag-mcp
```

### Step 3: 초기 셋업

Python/패키지 설치 및 임베딩 모델(~3GB) 다운로드가 최초 1회 진행됩니다.

```
/init
```

### Step 4: 프로젝트 인덱싱

```
/project-add
```

프로젝트 이름과 경로를 입력하면 자동으로 인덱싱되고, `/search-{이름}` 슬래시 커맨드가 생성됩니다.

<br>

### 수동 설치

```bash
git clone https://github.com/DongLab-DevTools/code-rag-mcp.git
cd code-rag-mcp
./init.sh    # Python/venv/패키지/모델까지 자동 셋업
```

<br>

### 요구사항

- **Python 3.10 이상** (없으면 `init.sh`가 Homebrew로 자동 설치)
- **macOS + Homebrew** (Linux/Windows는 수동 Python 설치 필요)
- **디스크 여유 공간 4GB+** (Jina 모델 가중치 ~3GB + venv)
- **Claude Code CLI** (슬랙 봇의 답변 생성에 사용, 선택)

<br>

## 사용법

### Claude Code에서 검색

인덱싱 후 생성된 슬래시 커맨드로 검색합니다:

```
/search-myapp 로그인 로직이 어떻게 돼?
/search-myapp 결제 흐름
/search-myapp Retrofit 인터셉터에서 토큰 갱신
```

커맨드 없이 자연어로 질문해도 됩니다:

```
myapp에서 유저 프로필 수정하는 API 찾아줘
전체 프로젝트에서 Repository 패턴 구현 찾아줘
```

<br>

### Slack 봇으로 사용

`.env` 파일을 프로젝트 루트에 만듭니다:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

서버 실행:

```bash
./start.sh        # 백그라운드 실행
./start.sh --log  # 포그라운드 (로그 실시간 출력)
./stop.sh         # 종료
```

슬랙에서 멘션:

```
@code-rag-mcp 로그인 로직이 어떻게 돼?
@code-rag-mcp myapp 유저 정보 조회하는 코드
```

자세한 Slack 앱 설정은 [SETUP.md](./SETUP.md)를 참고하세요.

<br>

### CLI로 직접 사용

```bash
source venv/bin/activate

# 인덱싱
python analysis/indexer.py --name myapp /path/to/project

# 인덱싱된 프로젝트 목록
python analysis/indexer.py --list

# 대화형 검색
python analysis/search.py
```

<br>

## 지원 프로젝트 타입

| 타입 | 언어 | 파서 | 청킹 기준 |
|------|------|------|----------|
| Android | Kotlin, Java | tree-sitter-kotlin, tree-sitter-java | [CHUNKING.md](analysis/chunkers/android/CHUNKING.md) |
| iOS | Swift | tree-sitter-swift | [CHUNKING.md](analysis/chunkers/ios/CHUNKING.md) |
| 공통 | 설정, 문서, XML 등 | — | [CHUNKING.md](analysis/chunkers/common/CHUNKING.md) |

모든 프로젝트 타입에서 바이너리를 제외한 나머지 파일도 텍스트로 읽어서 인덱싱합니다.

<br>

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

<br>

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

<br>

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
├── skills/                  # Claude Code 슬래시 커맨드 (/init, /project-add ...)
├── .claude-plugin/          # Claude Code 플러그인 매니페스트 + 마켓플레이스 정의
├── init.sh                  # 초기 셋업 (Python/venv/패키지/모델)
├── start.sh / stop.sh       # 서버 실행/종료
└── SETUP.md                 # 상세 셋업 가이드
```

<br>

## 기여자

<!-- readme: collaborators,contributors -start -->
<table>
	<tbody>
		<tr>
            <td align="center">
                <a href="https://github.com/dongx0915">
                    <img src="https://avatars.githubusercontent.com/u/63500239?v=4" width="100;" alt="dongx0915"/>
                    <br />
                    <sub><b>Donghyeon Kim</b></sub>
                </a>
            </td>
		</tr>
	<tbody>
</table>
<!-- readme: collaborators,contributors -end -->
