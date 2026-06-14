# /m-search — Claude Code 대화 검색 스킬

## 개요

과거 Claude Code 대화에서 키워드로 검색하는 스킬입니다.  
`conv_archive.py`가 생성한 SQLite DB에서 FTS5 전문검색을 실행합니다.

## 설치

1. `conv_archive.py`를 원하는 위치에 저장  
2. 이 `SKILL.md`를 `~/.claude/skills/m-search/SKILL.md` 경로에 복사  
3. (선택) 환경변수 설정:

```bash
# DB 위치가 기본값(~/.conv_archive/conv_archive.db)과 다른 경우
export CONV_ARCHIVE_DB=/path/to/conv_archive.db
export CONV_ARCHIVE_ROOT=/path/to/.claude/projects
```

## 트리거

사용자가 `/m-search <키워드>`를 입력하면 이 스킬이 실행됩니다.

## 실행 절차

1. `/m-search` 뒤의 텍스트를 키워드로 추출
2. 다음 명령 실행:
   ```
   python /path/to/conv_archive.py --search "<키워드>"
   ```
   - `CONV_ARCHIVE_DB` 환경변수가 설정된 경우 자동 적용
   - 또는 `--db` 플래그로 명시: `python conv_archive.py --db /path/to/db --search "<키워드>"`
3. 결과를 사용자에게 전달 (텔레그램 연동 시 텔레그램으로 전송)
4. 키워드가 없으면 사용법 안내

## 날짜 필터

키워드에 날짜 표현을 포함하면 날짜 필터가 적용됩니다:

| 키워드 | 범위 |
|--------|------|
| `오늘` / `today` | 오늘 |
| `어제` / `yesterday` | 어제 |
| `그제` | 2일 전 |
| `이번주` / `thisweek` | 최근 7일 |
| `지난주` / `lastweek` | 7~14일 전 |

예: `/m-search docker 어제` → 어제 대화에서 "docker" 검색

## 사용 예시

```
/m-search sqlite fts5
/m-search 루프 오늘
/m-search 어제
```
