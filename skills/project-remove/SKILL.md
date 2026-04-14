---
name: project-remove
description: 인덱싱된 프로젝트를 삭제합니다
---

인덱싱된 프로젝트를 삭제합니다. 아래 순서대로 진행하세요.

## 0단계: 플러그인 루트 확인

이 skill 파일의 위치를 기준으로 플러그인 루트를 파악하세요.
이 파일은 `{플러그인루트}/skills/project-remove/SKILL.md` 에 있으므로,
플러그인 루트는 이 파일에서 2단계 상위 디렉토리입니다.

## 1단계: 프로젝트 목록 표시 및 선택

인자(<args>)가 있으면 거기서 프로젝트 이름을 파싱하고 2단계로 넘어가세요.

인자가 없으면 아래 명령어를 실행해서 등록된 프로젝트 목록을 가져오세요:

```
{플러그인루트}/venv/bin/python -c "
import chromadb, os
db_path = os.path.join(os.environ.get('CLAUDE_PLUGIN_DATA') or '{플러그인루트}', 'chroma_db')
if not os.path.exists(db_path):
    print('EMPTY')
else:
    client = chromadb.PersistentClient(path=db_path)
    cols = [c for c in client.list_collections() if c.name.startswith('project_')]
    if not cols:
        print('EMPTY')
    else:
        for c in cols:
            name = c.name[len('project_'):]
            count = client.get_collection(c.name).count()
            print(f'{name}|{count}')
"
```

- 프로젝트가 없으면 "인덱싱된 프로젝트가 없습니다."라고 안내하고 종료하세요.
- 프로젝트가 있으면 번호 목록으로 보여주세요:

```
삭제할 프로젝트를 선택하세요:

  1. tving-android (18,455개 청크)
  2. tving-ios (13,362개 청크)

번호 또는 프로젝트 이름을 입력하세요:
```

사용자가 번호 또는 이름으로 선택하면 해당 프로젝트 이름으로 2단계를 진행하세요.

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
