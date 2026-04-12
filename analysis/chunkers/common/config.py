"""설정 파일 청킹 — 파일을 통째로 하나의 청크로 저장."""

import os

from analysis.chunkers.base import CodeChunk

# 이름으로 매칭하는 설정 파일
CONFIG_FILE_NAMES = {
    # Android / Gradle
    "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts",
    "gradle.properties", "local.properties",
    "proguard-rules.pro",
    "AndroidManifest.xml",
    "google-services.json",
    # iOS / Xcode
    "Podfile", "Podfile.lock",
    "Package.swift",
    "Info.plist",
    "project.pbxproj",
}

# 확장자로 매칭하는 설정 파일
WHOLE_FILE_EXTENSIONS = {
    ".json", ".yaml", ".yml",
    ".toml", ".properties", ".pro",
    ".env", ".cfg", ".ini", ".conf",
    ".plist", ".entitlements",
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
