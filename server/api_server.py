"""
api_server.py — 검색 API 서버

로컬 테스트: python api_server.py
서버 배포:   python api_server.py --host 0.0.0.0 --port 8000
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from fastapi import FastAPI, Query
from pydantic import BaseModel
from analysis.search import search_code, format_results, list_projects

app = FastAPI(title="code-rag-mcp API")


class SearchResponse(BaseModel):
    query: str
    project: str
    total: int
    formatted: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/projects")
def projects():
    return {"projects": list_projects()}


@app.get("/search", response_model=SearchResponse)
def search_get(
    q: str = Query(...),
    top_k: int = Query(10, ge=1, le=20),
    project: str = Query("", description="프로젝트 이름 (빈 문자열이면 전체 검색)"),
):
    results = search_code(q, top_k=top_k, project=project)
    return SearchResponse(
        query=q,
        project=project or "all",
        total=len(results),
        formatted=format_results(results),
    )


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"API 서버: http://{args.host}:{args.port}")
    print(f"   API 문서: http://localhost:{args.port}/docs\n")
    uvicorn.run(app, host=args.host, port=args.port)
