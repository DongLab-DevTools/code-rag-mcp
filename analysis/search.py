"""
search.py — 벡터DB에서 질문과 관련된 코드를 검색한다.

여러 프로젝트가 인덱싱되어 있으면 전체 또는 특정 프로젝트만 검색할 수 있다.

사용법:
    from search import search_code
    results = search_code("유저 정보 가져오는 코드")              # 전체 검색
    results = search_code("유저 정보", project="myapp")          # 특정 프로젝트만
"""

import os
import sys

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "jinaai/jina-code-embeddings-1.5b"
CHROMA_DB_PATH = os.path.join(
    os.environ.get("CODE_RAG_DATA") or os.path.expanduser("~/.code-rag-mcp"),
    "chroma_db",
)
COLLECTION_PREFIX = "project_"
TOP_K = 10


# ─────────────────────────────────────────────
# 디바이스 & 모델 (lazy-load)
# ─────────────────────────────────────────────

_embed_model = None


def _get_embed_model():
    """첫 호출 시 모델을 로드한다 (lazy-load)."""
    global _embed_model
    if _embed_model is None:
        import torch
        from sentence_transformers import SentenceTransformer

        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"

        print(f"검색 모델 로드 중: {EMBEDDING_MODEL_NAME} ({device})", file=sys.stderr)
        _embed_model = SentenceTransformer(
            EMBEDDING_MODEL_NAME,
            model_kwargs={"torch_dtype": torch.float32},
            device=device,
        )
        print("  → 모델 로드 완료!\n", file=sys.stderr)
    return _embed_model


# ─────────────────────────────────────────────
# 프로젝트 목록
# ─────────────────────────────────────────────

def list_projects() -> list[str]:
    """인덱싱된 프로젝트 이름 목록을 반환한다."""
    if not os.path.exists(CHROMA_DB_PATH):
        return []
    import chromadb
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collections = chroma_client.list_collections()
    return [
        c.name[len(COLLECTION_PREFIX):]
        for c in collections
        if c.name.startswith(COLLECTION_PREFIX)
    ]


# ─────────────────────────────────────────────
# 검색
# ─────────────────────────────────────────────

def search_code(question: str, top_k: int = TOP_K, project: str = "") -> list[dict]:
    """
    질문과 관련된 코드를 검색한다.

    Args:
        question: 사용자의 질문
        top_k: 반환할 결과 수
        project: 프로젝트 이름 (빈 문자열이면 전체 검색)
    """
    question_vector = _get_embed_model().encode(
        question, prompt_name="nl2code_query",
    ).tolist()

    import chromadb
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    # 검색할 컬렉션 결정
    if project:
        collection_names = [f"{COLLECTION_PREFIX}{project}"]
    else:
        collections = chroma_client.list_collections()
        collection_names = [
            c.name for c in collections if c.name.startswith(COLLECTION_PREFIX)
        ]

    if not collection_names:
        return []

    # 모든 대상 컬렉션에서 검색 후 합치기
    all_results = []

    for col_name in collection_names:
        try:
            collection = chroma_client.get_collection(col_name)
        except Exception:
            continue

        results = collection.query(
            query_embeddings=[question_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            all_results.append({
                "code": results["documents"][0][i],
                "project": meta.get("project", col_name[len(COLLECTION_PREFIX):]),
                "file_path": meta["file_path"],
                "name": meta["name"],
                "chunk_type": meta["chunk_type"],
                "parent_class": meta["parent_class"],
                "start_line": meta["start_line"],
                "end_line": meta["end_line"],
                "distance": results["distances"][0][i],
            })

    # 유사도 거리 기준으로 정렬 후 상위 top_k개
    all_results.sort(key=lambda r: r["distance"])
    return all_results[:top_k]


def format_results(results: list[dict]) -> str:
    """검색 결과를 읽기 좋은 문자열로 포맷팅한다."""
    if not results:
        return "관련 코드를 찾지 못했습니다."

    output_parts = []
    for i, r in enumerate(results, 1):
        display_name = r["name"]
        if r["parent_class"]:
            display_name = f"{r['parent_class']}.{r['name']}"

        confidence = max(0, (1 - r['distance']) * 100)

        output_parts.append(
            f"━━━ 검색 결과 {i} ━━━\n"
            f"📦 프로젝트: {r['project']}\n"
            f"📁 파일: {r['file_path']}\n"
            f"📌 이름: {display_name} ({r['chunk_type']})\n"
            f"📍 줄:   {r['start_line']}-{r['end_line']}\n"
            f"🎯 확신도: {confidence:.1f}%\n"
            f"\n{r['code']}\n"
        )

    return "\n".join(output_parts)


# ─────────────────────────────────────────────
# 대화형 테스트
# ─────────────────────────────────────────────

if __name__ == "__main__":
    projects = list_projects()
    print("🔍 코드 검색기입니다!")
    if projects:
        print(f"   인덱싱된 프로젝트: {', '.join(projects)}")
    print("   종료: quit | 특정 프로젝트 검색: @프로젝트이름 질문\n")

    while True:
        raw = input("검색> ").strip()
        if raw.lower() in ("quit", "exit", "q"):
            print("👋 안녕히 가세요!")
            break
        if not raw:
            continue

        # @프로젝트이름 질문 형태 파싱
        project_filter = ""
        question = raw
        if raw.startswith("@"):
            parts = raw.split(" ", 1)
            project_filter = parts[0][1:]  # @ 제거
            question = parts[1] if len(parts) > 1 else ""

        if not question:
            continue

        scope = f"[{project_filter}]" if project_filter else "[전체]"
        print(f"\n🔍 {scope} 검색 중...\n")
        results = search_code(question, project=project_filter)
        print(format_results(results))
        print()
