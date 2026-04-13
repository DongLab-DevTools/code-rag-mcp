"""
indexer.py — 청크를 임베딩하고 ChromaDB에 저장한다.

사용법:
    python indexer.py --name myapp /path/to/myapp-project
    python indexer.py --name myapp /path/to/myapp-project
    python indexer.py --list                                # 인덱싱된 프로젝트 목록

각 프로젝트는 별도 컬렉션으로 저장되므로 서로 영향을 주지 않는다.
코드가 변경되면 해당 프로젝트만 다시 실행하면 된다.
"""

import sys
import os
sys.stdout.reconfigure(line_buffering=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gc
import json
import time
import hashlib
import argparse
import torch

PROGRESS_FILE = "/tmp/code-rag-indexing-progress.json"
from sentence_transformers import SentenceTransformer
from analysis.chunker import chunk_project
import chromadb

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "jinaai/jina-code-embeddings-1.5b"
CHROMA_DB_PATH = os.path.join(
    os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "chroma_db",
)
COLLECTION_PREFIX = "project_"
MAX_CHARS = 4000
DB_BATCH_SIZE = 64


def get_collection_name(project_name: str) -> str:
    return f"{COLLECTION_PREFIX}{project_name}"


def write_progress(data: dict):
    """진행률을 JSON 파일에 기록한다. Claude Code에서 폴링용."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False)


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


# ─────────────────────────────────────────────
# 프로젝트 목록 조회
# ─────────────────────────────────────────────

def list_projects():
    """인덱싱된 프로젝트 목록을 출력한다."""
    if not os.path.exists(CHROMA_DB_PATH):
        print("인덱싱된 프로젝트가 없습니다.")
        return

    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    collections = chroma_client.list_collections()

    project_collections = [
        c for c in collections if c.name.startswith(COLLECTION_PREFIX)
    ]

    if not project_collections:
        print("인덱싱된 프로젝트가 없습니다.")
        return

    print(f"📦 인덱싱된 프로젝트 ({len(project_collections)}개):\n")
    for col in project_collections:
        name = col.name[len(COLLECTION_PREFIX):]
        count = col.count()
        print(f"  - {name} ({count}개 청크)")


# ─────────────────────────────────────────────
# 임베딩 모델 로드
# ─────────────────────────────────────────────

def load_model():
    print(f"임베딩 모델 로드 중: {EMBEDDING_MODEL_NAME}")
    print(f"  디바이스: {device}")

    model = SentenceTransformer(
        EMBEDDING_MODEL_NAME,
        model_kwargs={"torch_dtype": torch.float32},
        device=device,
    )
    print(f"  → 모델 로드 완료!\n")
    return model


# ─────────────────────────────────────────────
# 인덱싱
# ─────────────────────────────────────────────

def index_project(project_name: str, project_path: str):
    """프로젝트를 청킹하고 임베딩해서 ChromaDB에 저장한다."""

    write_progress({"status": "loading_model", "message": "임베딩 모델 로드 중..."})
    embed_model = load_model()
    collection_name = get_collection_name(project_name)

    def embed_one(text: str) -> list[float]:
        if len(text) > MAX_CHARS:
            text = text[:MAX_CHARS]
        return embed_model.encode(
            text, prompt_name="nl2code_document", show_progress_bar=False,
        ).tolist()

    # 1. 청킹
    write_progress({"status": "chunking", "message": "프로젝트 청킹 중..."})
    print(f"[1/3] 프로젝트 청킹 중: {project_path}")
    print(f"       프로젝트 이름: {project_name}")
    chunks = chunk_project(project_path)
    print(f"       → {len(chunks)}개 청크 생성됨")

    if not chunks:
        print("청크가 없습니다. 프로젝트 경로를 확인하세요.")
        return

    # 2. ChromaDB 준비
    print(f"[2/3] ChromaDB 준비 중: {CHROMA_DB_PATH}")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

    try:
        chroma_client.delete_collection(collection_name)
        print(f"       → 기존 컬렉션 '{collection_name}' 삭제됨 (재인덱싱)")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )

    # 3. 하나씩 임베딩 생성 + 묶어서 DB 저장
    total = len(chunks)
    write_progress({"status": "embedding", "progress": 0, "total": total, "pct": 0, "speed": 0, "eta": ""})
    print(f"[3/3] 임베딩 생성 중 (디바이스: {device}, 청크 1개씩 처리)")

    start_time = time.time()
    buf_ids, buf_docs, buf_embs, buf_metas = [], [], [], []

    for idx, chunk in enumerate(chunks):
        text = chunk.to_text_for_embedding()
        emb = embed_one(text)

        raw = f"{project_name}:{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
        chunk_id = hashlib.md5(raw.encode()).hexdigest()

        buf_ids.append(chunk_id)
        buf_docs.append(text if len(text) <= MAX_CHARS else text[:MAX_CHARS])
        buf_embs.append(emb)
        buf_metas.append({
            "project": project_name,
            "file_path": chunk.file_path,
            "chunk_type": chunk.chunk_type,
            "name": chunk.name,
            "parent_class": chunk.parent_class,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        })

        if len(buf_ids) >= DB_BATCH_SIZE:
            collection.add(
                ids=buf_ids, documents=buf_docs,
                embeddings=buf_embs, metadatas=buf_metas,
            )
            buf_ids, buf_docs, buf_embs, buf_metas = [], [], [], []

        if idx % 100 == 0 and device == "mps":
            torch.mps.empty_cache()

        if (idx + 1) % 200 == 0 or idx == total - 1:
            progress = idx + 1
            pct = progress * 100 // total
            elapsed = time.time() - start_time
            speed = progress / elapsed
            eta = (total - progress) / speed
            eta_min = int(eta // 60)
            eta_sec = int(eta % 60)
            eta_str = f"~{eta_min}분 {eta_sec}초"
            write_progress({
                "status": "embedding", "progress": progress, "total": total,
                "pct": pct, "speed": round(speed, 1), "eta": eta_str,
            })
            print(
                f"       → {progress}/{total} ({pct}%) | "
                f"{speed:.1f} 청크/초 | 남은 시간: {eta_str}"
            )

    if buf_ids:
        collection.add(
            ids=buf_ids, documents=buf_docs,
            embeddings=buf_embs, metadatas=buf_metas,
        )

    elapsed_total = time.time() - start_time
    elapsed_min = int(elapsed_total // 60)
    elapsed_sec = int(elapsed_total % 60)

    write_progress({
        "status": "done", "total": total,
        "elapsed": f"{elapsed_min}분 {elapsed_sec}초",
    })
    print(f"\n✅ 인덱싱 완료! [{project_name}] {total}개 청크 저장됨")
    print(f"   소요 시간: {elapsed_min}분 {elapsed_sec}초")
    print(f"   컬렉션: {collection_name}")


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="프로젝트를 인덱싱한다.")
    parser.add_argument("--name", help="프로젝트 이름 (예: myapp, shopping)")
    parser.add_argument("--list", action="store_true", help="인덱싱된 프로젝트 목록")
    parser.add_argument("path", nargs="?", help="프로젝트 경로")

    args = parser.parse_args()

    if args.list:
        list_projects()
    elif args.name and args.path:
        index_project(args.name, args.path)
    else:
        print("사용법:")
        print("  python indexer.py --name 프로젝트이름 /path/to/project")
        print("  python indexer.py --list")
        sys.exit(1)
