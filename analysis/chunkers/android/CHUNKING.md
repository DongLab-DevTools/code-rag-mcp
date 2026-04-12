# Android 청킹 기준

## 코드 (AST 기반)

| 확장자 | 언어 | 파서 |
|--------|------|------|
| `.kt` `.kts` | Kotlin | tree-sitter-kotlin |
| `.java` | Java | tree-sitter-java |

| 대상 | 규칙 |
|------|------|
| 함수 / 메서드 | 개별 청크 |
| 프로퍼티 / 필드 | 개별 청크 |
| 클래스 ≤ 50줄 | 통째로 1 청크 |
| 클래스 > 50줄 | 시그니처 1 청크 + 내부 멤버 각각 청크 |
| 내부 클래스 | 재귀적으로 동일 규칙 적용 |
| 30자 미만 코드 | 스킵 (짧은 상수/getter는 소속 클래스가 50줄 이하면 통째로 포함됨) |

## 설정 파일 (파일 단위 1 청크)

`build.gradle`, `build.gradle.kts`, `settings.gradle`, `settings.gradle.kts`, `gradle.properties`, `proguard-rules.pro`, `AndroidManifest.xml`, `google-services.json`

## 리소스 XML

| 대상 | 규칙 |
|------|------|
| values 계열 (strings.xml, colors.xml 등) | 항목별 개별 청크 (≤ 5개면 파일 통째로) |
| layout / navigation / menu | 파일 단위 1 청크 |

## 기타 파일

바이너리를 제외한 모든 파일을 파일 단위 1 청크로 저장. `.sh`, `.py`, `.proto`, `Dockerfile`, `Makefile` 등 미분류 파일도 포함.

## 스킵

- 디렉토리: `build`, `.gradle`, `.idea`, `intermediates`, `generated`, `test`, `androidTest`, `assets`, `mipmap`
- 바이너리: `.png`, `.jpg`, `.ttf`, `.so`, `.jar`, `.apk` 등 49종
