---
name: project-remove
description: 인덱싱된 프로젝트를 삭제합니다
---

인덱싱된 프로젝트를 삭제합니다. 아래 순서대로 진행하세요.

## 0단계: 플러그인 루트 확인

이 skill 파일의 위치를 기준으로 플러그인 루트를 파악하세요.
이 파일은 `{플러그인루트}/skills/project-remove/SKILL.md` 에 있으므로,
플러그인 루트는 이 파일에서 2단계 상위 디렉토리입니다.

## 1단계: 프로젝트 이름 확인

인자(<args>)가 있으면 거기서 프로젝트 이름을 파싱하세요.
없으면 사용자에게 삭제할 프로젝트 이름을 물어보세요.

## 2단계: 삭제 실행

**반드시 당신(Claude)이 Bash 도구를 사용해서 아래 명령어를 직접 실행하세요.**
**절대로 사용자에게 명령어를 보여주고 직접 실행하라고 하지 마세요.**

실행할 명령어:
```
{플러그인루트}/venv/bin/python -c "
import chromadb, os, sys
db_path = os.path.join(os.environ.get('CLAUDE_PLUGIN_DATA') or '{플러그인루트}', 'chroma_db')
client = chromadb.PersistentClient(path=db_path)
name = 'project_{프로젝트이름}'
try:
    col = client.get_collection(name)
    count = col.count()
    client.delete_collection(name)
    print(f'삭제 완료: {프로젝트이름} ({count}개 청크)')
except Exception as e:
    print(f'프로젝트를 찾을 수 없습니다: {프로젝트이름}')
    sys.exit(1)
"
```

## 3단계: 검색 커맨드 정리

`{플러그인루트}/skills/search-{프로젝트이름}/` 디렉토리가 있으면 삭제하세요.

## 4단계: 완료 안내

사용자에게 다음을 알려주세요:
- 삭제된 프로젝트 이름과 청크 수
- `/reload-plugins`로 검색 커맨드를 갱신할 수 있다는 것
