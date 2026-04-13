"""
slack_bot.py — code-rag-mcp 슬랙 봇

사용법:
    export SLACK_BOT_TOKEN="xoxb-..."
    export SLACK_APP_TOKEN="xapp-..."
    export CODE_RAG_API_URL="http://localhost:8000"
    python slack_bot.py
"""

import os
import re
import subprocess
import logging
import requests

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
CODE_RAG_API_URL = os.environ.get("CODE_RAG_API_URL", "http://localhost:8000")
CLAUDE_CLI = os.environ.get("CLAUDE_CLI_PATH", "claude")
MAX_BLOCKS = 50

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN)


# ─────────────────────────────────────────────
# 인덱싱된 프로젝트 목록 캐시
# ─────────────────────────────────────────────

_cached_projects: list[str] | None = None


def get_projects() -> list[str]:
    """API 서버에서 인덱싱된 프로젝트 목록을 가져온다 (최초 1회 캐시)."""
    global _cached_projects
    if _cached_projects is not None:
        return _cached_projects
    try:
        resp = requests.get(f"{CODE_RAG_API_URL}/projects", timeout=5)
        resp.raise_for_status()
        _cached_projects = resp.json().get("projects", [])
    except Exception:
        _cached_projects = []
    return _cached_projects


# ─────────────────────────────────────────────
# 질문에서 프로젝트 자동 감지
# ─────────────────────────────────────────────

def _clean_project_from_question(question: str, proj: str) -> str:
    """질문에서 프로젝트 이름을 제거하고 정리한다."""
    cleaned = question.replace(proj, "").strip()
    for suffix in ["에서 ", "에서", "의 ", "의", "에 ", "에"]:
        if cleaned.startswith(suffix):
            cleaned = cleaned[len(suffix):].strip()
            break
    return cleaned or question


def detect_project(question: str) -> tuple[str | list[str], str]:
    """질문에서 프로젝트를 감지한다.
    정확히 매칭되면 str, 여러 프로젝트가 부분 매칭되면 list[str]을 반환한다."""
    projects = get_projects()
    if not projects:
        return "", question

    lower_q = question.lower()

    # 1) 정확한 매칭: 프로젝트 이름이 질문에 포함
    for proj in sorted(projects, key=len, reverse=True):
        if proj.lower() in lower_q:
            cleaned = _clean_project_from_question(question, proj)
            return proj, cleaned

    # 2) 부분 매칭: 질문의 단어가 여러 프로젝트 이름의 공통 접두사인 경우
    words = lower_q.split()
    for word in words:
        matched = [p for p in projects if p.lower().startswith(word)]
        if len(matched) == 1:
            cleaned = _clean_project_from_question(question, word)
            return matched[0], cleaned
        elif len(matched) > 1:
            cleaned = _clean_project_from_question(question, word)
            return matched, cleaned

    return "", question


# ─────────────────────────────────────────────
# 1) 서버에서 코드 검색
# ─────────────────────────────────────────────

def search_from_server(question: str, project: str = "", top_k: int = 10) -> dict:
    try:
        resp = requests.get(
            f"{CODE_RAG_API_URL}/search",
            params={"q": question, "top_k": top_k, "project": project},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.ConnectionError:
        return {"error": f"검색 서버({CODE_RAG_API_URL})에 연결할 수 없습니다."}
    except requests.Timeout:
        return {"error": "검색 서버 응답 시간 초과"}
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────
# 2) Claude Code CLI로 답변 생성
# ─────────────────────────────────────────────

def generate_answer(question: str, search_results_formatted: str) -> str:
    prompt = f"""아래는 안드로이드 코드베이스에서 검색된 관련 코드입니다.
이 코드를 분석해서 질문에 정확하고 간결하게 답변하세요.

## 답변 규칙
- 슬랙 메시지이므로 핵심만 전달하세요.
- 한국어로 답변하세요.
- 각 검색 결과의 🎯 확신도를 반드시 함께 표기하세요. 예: `LoginViewModel (🎯 72.3%)`
- 확신도가 높은 결과를 우선 참고하되, 낮은 결과는 참고 수준으로만 언급하세요.

## 슬랙 포맷 규칙 (반드시 지켜주세요)
- 테이블(| --- |)은 간단한 비교/목록에만 사용하세요. 복잡한 내용은 불릿 리스트가 낫습니다.
- # 헤딩 금지. 대신 *볼드*로 섹션을 구분하세요.
- 볼드는 ** 두 개가 아니라 * 한 개로 감싸세요. (슬랙 문법)
- 인라인 백틱(`) 사용 금지. 함수명, 클래스명, 변수명 등 모두 백틱 없이 그냥 텍스트로 쓰세요. 코드 블록(```)만 허용합니다.
- 넘버링은 1. 2. 3. 으로 쓰세요.
- 문단과 문단 사이에 빈 줄을 반드시 넣어서 여백을 확보하세요.
- 섹션 제목(*볼드*) 앞뒤에도 빈 줄을 넣으세요.
- 불릿 리스트 depth 규칙:
  1단계: • 항목
  2단계:   ◦ 하위 항목
  3단계:     ▸ 더 하위 항목
  반드시 이 기호를 사용하세요. 모든 depth에 • 를 쓰지 마세요.

## 검색된 코드

{search_results_formatted}

## 질문

{question}"""

    try:
        import time
        logger.info("Claude CLI 호출 시작...")
        start_time = time.time()

        result = subprocess.run(
            [CLAUDE_CLI, "-p", "--max-turns", "0", "--dangerously-skip-permissions", prompt],
            capture_output=True, text=True, timeout=120,
        )

        elapsed = time.time() - start_time
        logger.info(f"Claude CLI 응답 완료 ({elapsed:.1f}초, {len(result.stdout)}자)")

        if result.returncode != 0:
            logger.error(f"Claude CLI 에러: {result.stderr[:200]}")
            return f"Claude Code 에러:\n```{result.stderr[:500]}```"
        return result.stdout.strip() or "답변을 생성하지 못했습니다."

    except subprocess.TimeoutExpired:
        logger.error("Claude CLI 타임아웃 (120초)")
        return "답변 생성에 시간이 너무 오래 걸렸습니다."
    except FileNotFoundError:
        logger.error("Claude CLI 실행 파일 없음")
        return "claude CLI를 찾을 수 없습니다. CLAUDE_CLI_PATH를 확인하세요."
    except Exception as e:
        logger.error(f"Claude CLI 예외: {e}")
        return f"예외 발생: {str(e)[:200]}"


# ─────────────────────────────────────────────
# 3) Markdown → Slack Block Kit 변환
# ─────────────────────────────────────────────

def _md_to_mrkdwn(text: str) -> str:
    """인라인 마크다운을 슬랙 mrkdwn으로 변환한다 (코드블록 외부용)."""
    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # __bold__ → *bold*
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    # ~~strike~~ → ~strike~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)
    # ![alt](url) → <url|alt>
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"<\2|\1>", text)
    # [text](url) → <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    # ## 헤딩 → *볼드*
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # 글머리 기호: - item → • item
    text = re.sub(r"^(\s*)[-]\s+", r"\1• ", text, flags=re.MULTILINE)
    return text


def md_to_blocks(text: str) -> list[dict]:
    """Markdown 텍스트를 Slack Block Kit 블록 리스트로 변환한다."""
    blocks = []
    lines = text.split("\n")
    buffer = []
    in_code_block = False
    code_lines = []

    def _detect_indent_level(line: str) -> int:
        """줄의 들여쓰기 레벨을 반환한다 (불릿/리스트 항목 기준)."""
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        # 불릿(•◦▸) 또는 마크다운 리스트(- *)로 시작하는 경우만 레벨 판정
        if re.match(r"^[•◦▸\-\*]\s", stripped):
            if indent >= 4:
                return 2
            elif indent >= 2:
                return 1
        return 0

    def _parse_list_items(lines_subset: list[str]) -> list[dict]:
        """연속된 불릿 라인들을 파싱한다."""
        items = []
        for line in lines_subset:
            stripped = line.lstrip()
            level = _detect_indent_level(line)
            text = re.sub(r"^[•◦▸\-\*]\s+", "", stripped).strip()
            if text:  # 빈 텍스트 제거
                items.append({"text": text, "level": level})
        return items

    def _parse_rich_text_elements(text: str) -> list[dict]:
        """텍스트에서 *bold*, `code` 등을 파싱해서 rich_text elements로 변환한다."""
        elements = []
        # *bold*와 `code`를 파싱
        pattern = r"(\*[^*]+\*|`[^`]+`)"
        parts = re.split(pattern, text)

        for part in parts:
            if not part:
                continue
            if part.startswith("*") and part.endswith("*") and len(part) > 2:
                elements.append({
                    "type": "text",
                    "text": part[1:-1],
                    "style": {"bold": True},
                })
            elif part.startswith("`") and part.endswith("`") and len(part) > 2:
                elements.append({
                    "type": "text",
                    "text": part[1:-1],
                    "style": {"code": True},
                })
            else:
                elements.append({"type": "text", "text": part})

        return elements if elements else [{"type": "text", "text": text}]

    def _build_rich_text_list(items: list[dict]) -> dict:
        """항목 리스트를 rich_text 블록으로 변환한다.
        같은 indent 레벨끼리 그룹핑해서 sibling rich_text_list로 배치."""
        rt_elements = []
        current_level = -1
        current_sections = []

        def flush_group():
            if not current_sections:
                return
            rt_elements.append({
                "type": "rich_text_list",
                "style": "bullet",
                "indent": current_level,
                "elements": current_sections.copy(),
            })
            current_sections.clear()

        for item in items:
            section = {
                "type": "rich_text_section",
                "elements": _parse_rich_text_elements(item["text"]),
            }

            if item["level"] != current_level:
                flush_group()
                current_level = item["level"]

            current_sections.append(section)

        flush_group()

        return {"type": "rich_text", "elements": rt_elements} if rt_elements else None

    def flush_buffer():
        """텍스트 버퍼를 블록으로 변환. 불릿 리스트는 rich_text_list로, 나머지는 section으로."""
        if not buffer:
            return

        current_text = []
        current_list = []
        current_table = []
        in_table = False

        def emit_table():
            """테이블 버퍼를 markdown 블록으로 변환."""
            if not current_table:
                return
            table_md = "\n".join(current_table).strip()
            if table_md:
                blocks.append({"type": "markdown", "text": table_md})
            current_table.clear()

        def emit_text():
            if not current_text:
                return
            content = "\n".join(current_text).strip()
            if not content:
                current_text.clear()
                return
            content = _md_to_mrkdwn(content)
            while content:
                chunk = content[:3000]
                content = content[3000:]
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": chunk}
                })
            current_text.clear()

        def emit_list():
            if not current_list:
                return
            items = _parse_list_items(current_list)
            if items:
                block = _build_rich_text_list(items)
                if block:
                    blocks.append(block)
            current_list.clear()

        for idx, line in enumerate(buffer):
            stripped = line.lstrip()
            is_bullet = bool(re.match(r"^[•◦▸\-\*]\s", stripped))

            # 테이블 감지: | col | col | 다음 줄이 |---|---|
            is_table_start = (
                not in_table
                and "|" in line
                and idx + 1 < len(buffer)
                and re.match(r"^\s*\|[\s\-:]+\|", buffer[idx + 1])
            )
            is_table_line = in_table and "|" in line

            if is_table_start:
                emit_text()
                emit_list()
                in_table = True
                current_table.append(line)
            elif is_table_line:
                current_table.append(line)
            else:
                if in_table:
                    emit_table()
                    in_table = False

                if is_bullet:
                    emit_text()
                    current_list.append(line)
                else:
                    if current_list and line.strip() == "":
                        current_list.append(line)
                    elif current_list and not is_bullet:
                        emit_list()
                        current_text.append(line)
                    else:
                        current_text.append(line)

        emit_table()
        emit_list()
        emit_text()
        buffer.clear()

    def flush_code(lang: str = ""):
        """코드 버퍼를 rich_text 블록으로 변환."""
        if not code_lines:
            return
        code_text = "\n".join(code_lines)

        # rich_text_preformatted로 코드블록 렌더링
        elements = [{"type": "text", "text": code_text}]
        blocks.append({
            "type": "rich_text",
            "elements": [{
                "type": "rich_text_preformatted",
                "elements": elements,
            }]
        })
        code_lines.clear()

    for line in lines:
        stripped = line.strip()

        # 코드 블록 시작/끝
        if stripped.startswith("```"):
            if in_code_block:
                # 코드 블록 끝
                flush_code()
                in_code_block = False
            else:
                # 코드 블록 시작
                flush_buffer()
                in_code_block = True
                # ```kotlin 같은 언어 표기 무시
            continue

        if in_code_block:
            code_lines.append(line)
        else:
            # 구분선 --- 또는 ***
            if re.match(r"^[\-\*]{3,}\s*$", stripped):
                flush_buffer()
                blocks.append({"type": "divider"})
            else:
                buffer.append(line)

    # 남은 버퍼 처리
    if in_code_block:
        flush_code()
    flush_buffer()

    # 블록 50개 제한
    if len(blocks) > MAX_BLOCKS:
        blocks = blocks[:MAX_BLOCKS - 1]
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_(답변이 길어서 일부가 생략되었습니다)_"}
        })

    return blocks


def text_to_blocks(text: str) -> list[dict]:
    """단순 mrkdwn 텍스트를 Block Kit으로 감싼다."""
    return [{
        "type": "section",
        "text": {"type": "mrkdwn", "text": text[:3000]}
    }]


# ─────────────────────────────────────────────
# 4) 자기소개 & 도움말
# ─────────────────────────────────────────────

INTRO_KEYWORDS = {"자기소개", "소개해", "너 누구", "뭐하는 봇", "넌 뭐야", "정체가"}
HELP_KEYWORDS = {"도움말", "사용법", "사용방법", "어떻게 사용", "help", "명령어"}


def _build_intro_blocks() -> list[dict]:
    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🤖 code-rag-mcp"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "팀의 코드베이스를 로컬 AI로 분석해서, 자연어 질문에 관련 코드를 찾아드리는 봇이에요."}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": (
                "• 코드 구조, API 사용법, 비즈니스 로직 등 코드에 대한 질문이면 뭐든 물어보세요\n"
                "• 질문에 프로젝트 이름을 포함하면 해당 프로젝트만 검색하고, 생략하면 전체를 검색합니다\n"
                "• 벡터 임베딩 기반 시맨틱 검색으로, 정확한 키워드를 몰라도 의미로 찾아줍니다"
            )}
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "`도움말` 이라고 말하면 사용법을 알려드릴게요!"}]
        }
    ]


def _build_help_blocks() -> list[dict]:
    projects = get_projects()
    project_list = "\n".join(f"• `{p}`" for p in projects) if projects else "• _(인덱싱된 프로젝트가 없습니다)_"

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📖 code-rag-mcp 사용법"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*1️⃣ 코드 검색 (기본 기능)*\n코드에 대한 질문을 자연어로 하면 관련 코드를 찾아서 분석해드립니다."}
        },
        {
            "type": "rich_text",
            "elements": [{"type": "rich_text_preformatted", "elements": [
                {"type": "text", "text": "@code-rag-mcp 로그인 로직이 어떻게 돼?\n@code-rag-mcp Retrofit 인터셉터에서 토큰 갱신하는 부분"}
            ]}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*2️⃣ 특정 프로젝트 검색*\n질문에 프로젝트 이름을 포함하면 해당 프로젝트만 검색합니다."}
        },
        {
            "type": "rich_text",
            "elements": [{"type": "rich_text_preformatted", "elements": [
                {"type": "text", "text": "@code-rag-mcp myapp 유저 정보 조회\n@code-rag-mcp myapp 릴레이리스트 화면"}
            ]}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*3️⃣ 현재 인덱싱된 프로젝트*\n{project_list}"}
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*4️⃣ 코드 분석 데이터 업데이트*\n코드가 변경되었을 때 최신 상태로 업데이트하려면:"}
        },
        {
            "type": "rich_text",
            "elements": [{"type": "rich_text_preformatted", "elements": [
                {"type": "text", "text": "cd ~/Documents/ai-projects/code-rag-mcp\nsource venv/bin/activate\npython analysis/indexer.py --name 프로젝트이름 /프로젝트/경로"}
            ]}]
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "같은 이름으로 다시 실행하면 기존 데이터를 덮어씁니다. 또는 Claude Code에서 `/project-add` 커맨드를 사용하세요."}]
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "*5️⃣ 팁*\n• 구체적으로 질문할수록 정확한 결과를 얻을 수 있어요\n• 예: \"로그인\" 보다는 \"소셜 로그인 시 토큰 저장하는 로직\""}
        },
    ]


def _match_keywords(text: str, keywords: set[str]) -> bool:
    lower = text.lower().strip()
    return any(kw in lower for kw in keywords)


# ─────────────────────────────────────────────
# 5) 슬랙 이벤트 핸들러
# ─────────────────────────────────────────────

@app.event("app_mention")
def handle_mention(event, say):
    text = event.get("text", "")
    question = text.split(">", 1)[-1].strip() if ">" in text else text.strip()
    thread_ts = event.get("thread_ts") or event.get("ts")

    if not question:
        say(
            blocks=text_to_blocks("질문을 함께 입력해주세요!\n예: `@code-rag-mcp myapp 로그인 로직이 어떻게 돼?`"),
            text="질문을 함께 입력해주세요!",
            thread_ts=thread_ts,
        )
        return

    # 자기소개
    if _match_keywords(question, INTRO_KEYWORDS):
        say(blocks=_build_intro_blocks(), text="code-rag-mcp 소개", thread_ts=thread_ts)
        return

    # 도움말
    if _match_keywords(question, HELP_KEYWORDS):
        say(blocks=_build_help_blocks(), text="code-rag-mcp 사용법", thread_ts=thread_ts)
        return

    # 프로젝트 자동 감지
    project, cleaned_question = detect_project(question)

    # 여러 프로젝트가 매칭된 경우 (예: "tving" → tving-android, tving-ios)
    if isinstance(project, list):
        scope = "[" + ", ".join(project) + "]"
        logger.info(f"질문: {question} → 프로젝트: {scope}, 검색어: {cleaned_question}")
        say(text=f"🔍 {scope} 코드베이스에서 관련 코드를 찾고 있습니다...", thread_ts=thread_ts)

        # 각 프로젝트에서 검색 후 결과 병합
        all_results = []
        total = 0
        for proj in project:
            data = search_from_server(cleaned_question, project=proj)
            if "error" not in data and data.get("total", 0) > 0:
                all_results.append(data["formatted"])
                total += data["total"]

        if total == 0:
            say(text="관련 코드를 찾지 못했습니다. 질문을 다르게 해보세요.", thread_ts=thread_ts)
            return

        merged_formatted = "\n\n".join(all_results)
        answer = generate_answer(question, merged_formatted)
        blocks = md_to_blocks(answer)
        say(blocks=blocks, text=answer[:3000], thread_ts=thread_ts)
        logger.info(f"답변 전송 완료 (블록 {len(blocks)}개)")
        return

    scope = f"[{project}]" if project else "[전체]"
    logger.info(f"질문: {question} → 프로젝트: {scope}, 검색어: {cleaned_question}")

    say(text=f"🔍 {scope} 코드베이스에서 관련 코드를 찾고 있습니다...", thread_ts=thread_ts)

    # 서버에서 검색
    search_data = search_from_server(cleaned_question, project=project)

    if "error" in search_data:
        say(text=f"검색 실패: {search_data['error']}", thread_ts=thread_ts)
        return

    if search_data["total"] == 0:
        say(text="관련 코드를 찾지 못했습니다. 질문을 다르게 해보세요.", thread_ts=thread_ts)
        return

    # Claude Code CLI로 답변 생성
    answer = generate_answer(question, search_data["formatted"])
    blocks = md_to_blocks(answer)

    say(blocks=blocks, text=answer[:3000], thread_ts=thread_ts)
    logger.info(f"답변 전송 완료 (블록 {len(blocks)}개)")


# ─────────────────────────────────────────────
# 실행
# ─────────────────────────────────────────────

if __name__ == "__main__":
    projects = get_projects()
    print("code-rag-mcp 슬랙 봇 시작!")
    print(f"   검색 서버: {CODE_RAG_API_URL}")
    print(f"   인덱싱된 프로젝트: {', '.join(projects) if projects else '(서버 미연결)'}")
    print(f"   Claude CLI: {CLAUDE_CLI}")
    print(f"   종료: Ctrl+C\n")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
