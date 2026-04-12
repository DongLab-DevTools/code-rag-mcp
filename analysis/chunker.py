"""
chunker.py — 프로젝트의 코드/설정/문서를 의미 단위로 쪼갠다.

지원 언어: Kotlin, Java, Swift
지원 파일: 설정(gradle, plist 등), 리소스 XML, 마크다운, 텍스트

사용법:
    from analysis.chunker import chunk_project
    chunks = chunk_project("/path/to/project")
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.chunkers import (
    CodeChunk,
    chunk_kotlin, chunk_java, chunk_swift,
    CONFIG_FILE_NAMES, WHOLE_FILE_EXTENSIONS, chunk_whole_file,
    chunk_markdown, chunk_plaintext,
    get_res_dir_name, is_values_dir, is_whole_file_res_dir,
    chunk_resource_xml_by_item, chunk_resource_xml_whole,
)

# 건너뛸 디렉토리들
# 바이너리 파일 확장자 (읽어도 의미 없는 파일)
BINARY_EXTENSIONS = {
    # 이미지
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico", ".bmp",
    # 폰트
    ".ttf", ".otf", ".woff", ".woff2",
    # 컴파일/아카이브
    ".class", ".jar", ".aar", ".dex", ".so", ".dylib", ".a",
    ".o", ".pyc", ".pyo",
    # 앱 패키지
    ".apk", ".aab", ".ipa", ".app", ".xcarchive",
    # 미디어
    ".mp3", ".mp4", ".wav", ".mov", ".avi",
    # 문서 바이너리
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # 압축
    ".zip", ".tar", ".gz", ".rar", ".7z",
    # 기타
    ".db", ".sqlite", ".realm",
    ".DS_Store", ".lock",
}

SKIP_DIRS = {
    # 빌드 & 캐시
    "build", ".gradle", ".idea", ".git",
    "node_modules", "__pycache__",
    ".cxx", ".kotlin",
    "intermediates", "generated", "transforms",
    "tmp", "captures",
    # 테스트
    "test", "androidTest",
    # iOS 빌드
    "DerivedData", "Pods", ".build",
    "xcuserdata", "xcshareddata",
    # 기타
    ".github", ".vscode",
    "assets", "raw", "mipmap",
}


def chunk_project(project_path: str) -> list[CodeChunk]:
    """프로젝트 디렉토리를 재귀적으로 순회하며 모든 파일을 청크로 변환한다."""
    all_chunks = []
    project_path = os.path.abspath(project_path)
    stats = {"code": 0, "config": 0, "resource": 0, "document": 0}

    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

        for filename in files:
            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, project_path)
            _, ext = os.path.splitext(filename)

            try:
                # ── 코드 파일 ──
                if ext in (".kt", ".kts"):
                    chunks = chunk_kotlin(full_path)
                    for c in chunks:
                        c.file_path = relative_path
                    all_chunks.extend(chunks)
                    stats["code"] += len(chunks)

                elif ext == ".java":
                    chunks = chunk_java(full_path)
                    for c in chunks:
                        c.file_path = relative_path
                    all_chunks.extend(chunks)
                    stats["code"] += len(chunks)

                elif ext == ".swift":
                    chunks = chunk_swift(full_path)
                    for c in chunks:
                        c.file_path = relative_path
                    all_chunks.extend(chunks)
                    stats["code"] += len(chunks)

                # ── 설정 파일 (이름 매칭) ──
                elif filename in CONFIG_FILE_NAMES:
                    chunks = chunk_whole_file(full_path, relative_path, "config")
                    all_chunks.extend(chunks)
                    stats["config"] += len(chunks)

                # ── 마크다운 ──
                elif ext == ".md":
                    chunks = chunk_markdown(full_path, relative_path)
                    all_chunks.extend(chunks)
                    stats["document"] += len(chunks)

                # ── 설정 파일 (확장자 매칭) ──
                elif ext in WHOLE_FILE_EXTENSIONS:
                    chunks = chunk_whole_file(full_path, relative_path, "config")
                    all_chunks.extend(chunks)
                    stats["config"] += len(chunks)

                # ── 리소스 XML ──
                elif ext == ".xml":
                    res_dir = get_res_dir_name(relative_path)
                    if is_values_dir(res_dir):
                        chunks = chunk_resource_xml_by_item(full_path, relative_path)
                        all_chunks.extend(chunks)
                        stats["resource"] += len(chunks)
                    elif is_whole_file_res_dir(res_dir):
                        chunks = chunk_resource_xml_whole(full_path, relative_path)
                        all_chunks.extend(chunks)
                        stats["resource"] += len(chunks)

                # ── 텍스트 ──
                elif ext == ".txt":
                    chunks = chunk_plaintext(full_path, relative_path)
                    all_chunks.extend(chunks)
                    stats["document"] += len(chunks)

                # ── 나머지: 바이너리가 아닌 모든 파일 ──
                elif ext not in BINARY_EXTENSIONS:
                    try:
                        chunks = chunk_whole_file(full_path, relative_path, "misc")
                        all_chunks.extend(chunks)
                        stats["document"] += len(chunks)
                    except UnicodeDecodeError:
                        pass  # 바이너리 파일

            except Exception as e:
                print(f"  [WARN] {relative_path} 처리 실패: {e}")

    print(
        f"       코드: {stats['code']}개 | 설정: {stats['config']}개 | "
        f"리소스: {stats['resource']}개 | 문서: {stats['document']}개"
    )
    return all_chunks


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python chunker.py /path/to/project")
        sys.exit(1)

    project = sys.argv[1]
    print(f"프로젝트 청킹 시작: {project}")
    chunks = chunk_project(project)
    print(f"총 {len(chunks)}개의 청크 생성됨\n")

    for i, chunk in enumerate(chunks[:5]):
        print(f"── 청크 {i+1} ──")
        print(f"  파일: {chunk.file_path}")
        print(f"  타입: {chunk.chunk_type}")
        print(f"  이름: {chunk.name}")
        if chunk.parent_class:
            print(f"  소속: {chunk.parent_class}")
        print(f"  줄:   {chunk.start_line}-{chunk.end_line}")
        print(f"  코드: {chunk.content[:100]}...")
        print()
