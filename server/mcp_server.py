"""
mcp_server.py — code-rag-mcp MCP 서버

여러 프로젝트를 인덱싱해두면 전체 또는 특정 프로젝트만 검색할 수 있다.

사용법:
    python mcp_server.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from analysis.search import search_code, format_results, list_projects

# ─────────────────────────────────────────────
# MCP 서버 생성
# ─────────────────────────────────────────────

mcp = FastMCP(
    name="code-rag-mcp",
    instructions=(
        "코드베이스에서 관련 코드를 검색하는 도구입니다. "
        "코드 구조, API 사용법, 비즈니스 로직 등에 대해 질문하면 "
        "관련 코드를 찾아서 돌려줍니다. "
        "여러 프로젝트가 인덱싱되어 있으면 project 파라미터로 특정 프로젝트만 검색할 수 있습니다. "
        "이 도구의 검색 결과를 바탕으로 답변을 생성해주세요."
    ),
)


@mcp.tool()
def search_code(query: str, top_k: int = 10, project: str = "") -> str:
    """
    코드베이스에서 질문과 관련된 코드를 검색합니다.

    1536차원 코드 특화 임베딩(jina-code-embeddings-1.5b)을 사용하는
    의미 기반 검색(semantic search)입니다.
    키워드가 정확히 일치하지 않아도, 의미가 비슷한 코드를 찾을 수 있습니다.

    질문 예시:
    - "유저 프로필 수정하는 API 어디있어?"
    - "결제 로직 흐름이 어떻게 돼?"
    - "네트워크 에러 처리는 어떻게 하고 있어?"

    Args:
        query: 검색할 질문 또는 키워드
        top_k: 반환할 결과 수 (기본값: 10, 최대: 20)
        project: 프로젝트 이름 (빈 문자열이면 전체 프로젝트 검색)

    Returns:
        검색된 코드 조각들 (프로젝트명, 파일 경로, 이름, 줄 번호, 코드 포함)
    """
    top_k = min(top_k, 20)
    results = search_code(query, top_k=top_k, project=project)
    return format_results(results)


@mcp.tool()
def list_indexed_projects() -> str:
    """
    인덱싱된 프로젝트 목록을 반환합니다.
    어떤 프로젝트들이 검색 가능한지 확인할 때 사용하세요.
    """
    projects = list_projects()
    if not projects:
        return "인덱싱된 프로젝트가 없습니다."
    return "인덱싱된 프로젝트: " + ", ".join(projects)


# ─────────────────────────────────────────────
# 서버 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
