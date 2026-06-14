# conv-archive

Claude Code 대화를 아카이빙하고 전문검색하는 도구입니다.

Claude Code는 모든 세션을 `~/.claude/projects/` 아래에 `.jsonl` 파일로 저장합니다.  
이 도구는 해당 파일을 SQLite FTS5 인덱스로 가져와 수천 개의 과거 대화를 빠르게 검색할 수 있게 합니다.

## 기능

- **FTS5 전문검색** — BM25 랭킹, 한국어 + 영어 (`unicode61` 토크나이저)
- **날짜 필터** — `오늘 / 어제 / 그제 / 이번주 / 지난주` (또는 `today / yesterday / thisweek / lastweek`)
- **증분 임포트** — 중복 UUID 자동 스킵
- **세션 내보내기** — 특정 세션을 파일로 추출
- **의존성 없음** — Python 3.8+ 표준 라이브러리만 사용

## 설치

```bash
git clone https://github.com/<you>/conv-archive
cd conv-archive
python conv_archive.py --scan   # 첫 실행: 모든 세션 임포트
```

pip 설치 불필요.

## 사용법

```bash
# 임포트
python conv_archive.py --scan                        # ~/.claude/projects/**/*.jsonl 전체 스캔
python conv_archive.py --file path/to/session.jsonl  # 파일 하나만 임포트

# 검색
python conv_archive.py --search "docker"
python conv_archive.py --search "루프 오늘"          # 키워드 + 날짜 필터
python conv_archive.py --search "어제" --limit 50    # 날짜 필터만, 최대 50개

# 세션 조회
python conv_archive.py --session <session-id>        # 전체 세션 출력 (300자 截 truncation)
python conv_archive.py --export  <session-id>        # 전문 출력 (파이프 가능)
python conv_archive.py --export  <session-id> --date 2026-06-14  # 특정 날짜만

# 유지보수
python conv_archive.py --rebuild-fts                 # FTS 인덱스 재빌드
```

## 경로 설정

| 방법 | DB 경로 | 프로젝트 루트 |
|------|---------|--------------|
| 기본값 | `~/.conv_archive/conv_archive.db` | `~/.claude/projects` |
| 환경변수 | `CONV_ARCHIVE_DB=<path>` | `CONV_ARCHIVE_ROOT=<path>` |
| CLI 플래그 | `--db <path>` | `--root <path>` |

CLI 플래그가 환경변수보다 우선합니다.

## 날짜 필터 키워드

| 키워드 | 범위 |
|--------|------|
| `오늘` / `today` | 오늘 |
| `어제` / `yesterday` | 어제 |
| `그제` | 2일 전 |
| `이번주` / `thisweek` | 최근 7일 |
| `지난주` / `lastweek` | 7~14일 전 |

날짜 + 검색어 조합 가능: `python conv_archive.py --search "react hooks 어제"`

## 예시 워크플로우

```bash
# 아카이브를 최신 상태로 유지 (스케줄러 권장)
python conv_archive.py --scan

# 과거 해결책 검색
python conv_archive.py --search "sqlite fts5"

# 세션 내보내기
python conv_archive.py --export abc12345-... --date 2026-06-14 > session.txt
```

## 스케줄러 설정 (권장)

`--scan`은 자동으로 실행되지 않습니다. 스케줄러를 설정하면 아카이브가 항상 최신 상태를 유지합니다.

`.jsonl` 파일은 삭제되지 않고 누적되므로 **하루 1회로 충분합니다.**  
오늘 진행 중인 세션을 바로 검색하고 싶을 때만 수동으로 한 번 더 실행하면 됩니다.

**Mac / Linux (crontab):**
```bash
crontab -e
# 아래 줄 추가 — 매일 새벽 2시 실행:
0 2 * * * python /path/to/conv_archive.py --scan
```

**Windows (작업 스케줄러):**
```
1. 작업 스케줄러 열기 → 기본 작업 만들기
2. 트리거: 매일 오전 2:00
3. 동작: 프로그램 시작
   프로그램: python
   인수: C:\path\to\conv_archive.py --scan
4. 저장
```

수동으로 실행하려면:
```bash
python conv_archive.py --scan
```

## /m-search 스킬 (Claude Code)

`skill/SKILL.md`를 Claude Code 스킬로 등록하면 `/m-search <키워드>` 명령어로 검색할 수 있습니다.

```bash
# 스킬 설치
mkdir -p ~/.claude/skills/m-search
cp skill/SKILL.md ~/.claude/skills/m-search/SKILL.md
```

이후 Claude Code에서 `/m-search docker 어제` 형식으로 바로 검색 가능합니다.

## 라이선스

MIT
