---
name: help
description: code-rag-mcp 사용법을 안내합니다
---

아래 내용을 그대로 사용자에게 보여주세요.

---

## code-rag-mcp 사용법

로컬 임베딩 기반 코드 검색 MCP 플러그인입니다.
인덱싱된 프로젝트의 코드를 자연어로 검색할 수 있습니다.

### 슬래시 커맨드

| 커맨드 | 설명 | 예시 |
|--------|------|------|
| `/init` | 초기 셋업 (Python/venv/패키지/모델 다운로드) | `/init` |
| `/project-add` | 새 프로젝트 인덱싱 + 검색 커맨드 자동 생성 | `/project-add` |
| `/projects` | 인덱싱된 프로젝트 목록 확인 | `/projects` |
| `/search-{프로젝트}` | 특정 프로젝트에서 코드 검색 | `/search-myapp 로그인 API` |
| `/help` | 이 도움말 표시 | `/help` |

### 검색 예시

```
/search-myapp 유저 프로필 수정하는 API
/search-myapp 결제 로직 흐름
/search-myapp 네트워크 에러 처리
```

커맨드 없이 질문해도 됩니다:
```
"myapp에서 로그인 로직 어떻게 돼?"
"전체 프로젝트에서 Repository 패턴 찾아줘"
```

### 새 프로젝트 추가하기

`/project-add` 실행 후 안내에 따라 프로젝트 이름과 경로를 입력하면:
1. 코드 청킹 (AST 기반)
2. 임베딩 생성 (jina-code-embeddings-1.5b, 로컬)
3. 벡터DB 저장 (ChromaDB)
4. `/search-{이름}` 커맨드 자동 생성

### 재인덱싱 (코드 변경 시)

코드가 변경되면 해당 프로젝트만 다시 인덱싱하면 됩니다:
```
/project-add
```
같은 이름으로 다시 실행하면 기존 데이터를 덮어씁니다.

### 터미널에서 직접 실행

```bash
cd <플러그인 루트>
source venv/bin/activate

# 인덱싱
PYTHONPATH=. python analysis/indexer.py --name 프로젝트이름 /path/to/project

# 프로젝트 목록
PYTHONPATH=. python analysis/indexer.py --list

# 대화형 검색 테스트
PYTHONPATH=. python analysis/search.py
```

### 구조

```
code-rag-mcp/
├── analysis/            # 코드 분석
│   ├── chunker.py       # 코드를 의미 단위로 쪼갬 (AST 기반)
│   ├── indexer.py       # 임베딩 생성 + 벡터DB 저장
│   └── search.py        # 벡터DB 검색
├── server/              # 서버
│   ├── mcp_server.py    # MCP 서버
│   ├── api_server.py    # REST API 서버
│   └── slack_bot.py     # 슬랙 봇
├── chroma_db/           # 벡터DB 저장소 (자동 생성)
└── venv/                # Python 가상환경
```
