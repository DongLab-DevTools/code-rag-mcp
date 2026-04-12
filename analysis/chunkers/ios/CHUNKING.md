# iOS 청킹 기준

## 코드 (AST 기반)

| 확장자 | 언어 | 파서 |
|--------|------|------|
| `.swift` | Swift | tree-sitter-swift |

| 대상 | 규칙 |
|------|------|
| func / init / subscript | 개별 청크 |
| var / let (프로퍼티) | 개별 청크 |
| class / struct ≤ 50줄 | 통째로 1 청크 |
| class / struct > 50줄 | 시그니처 1 청크 + 내부 멤버 각각 청크 |
| protocol / extension / enum / actor | 위와 동일 |
| 내부 타입 | 재귀적으로 동일 규칙 적용 |
| 30자 미만 코드 | 스킵 (짧은 상수/getter는 소속 타입이 50줄 이하면 통째로 포함됨) |

## 설정 파일 (파일 단위 1 청크)

`Podfile`, `Podfile.lock`, `Package.swift`, `Info.plist`, `project.pbxproj`, `*.entitlements`

## 기타 파일

바이너리를 제외한 모든 파일을 파일 단위 1 청크로 저장. `.rb`, `.sh`, `Fastfile`, `Cartfile` 등 미분류 파일도 포함.

## 스킵

- 디렉토리: `DerivedData`, `Pods`, `.build`, `xcuserdata`, `xcshareddata`
- 바이너리: `.png`, `.jpg`, `.ttf`, `.dylib`, `.ipa` 등 49종
