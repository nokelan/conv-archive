# conv-archive

Archive and full-text search your [Claude Code](https://claude.ai/code) conversations.

Claude Code stores every session as a `.jsonl` file under `~/.claude/projects/`. This tool imports them into SQLite with an FTS5 index, giving you fast BM25-ranked search across thousands of past conversations.

## Features

- **FTS5 full-text search** — BM25 ranking, Korean + English (`unicode61` tokenizer)
- **Date filters** — `오늘 / 어제 / 그제 / 이번주 / 지난주` (or `today / yesterday / thisweek / lastweek`)
- **Incremental import** — duplicate UUIDs skipped automatically
- **Export** — dump any session to stdout (pipe to a file)
- **Zero dependencies** — stdlib only (Python 3.8+)

## Install

```bash
git clone https://github.com/<you>/conv-archive
cd conv-archive
python conv_archive.py --scan   # first run: import all sessions
```

No pip install needed.

## Usage

```bash
# Import
python conv_archive.py --scan                        # scan ~/.claude/projects/**/*.jsonl
python conv_archive.py --file path/to/session.jsonl  # import one file

# Search
python conv_archive.py --search "docker"
python conv_archive.py --search "루프 오늘"          # keyword + date filter
python conv_archive.py --search "어제" --limit 50    # date only, up to 50 results

# Browse
python conv_archive.py --session <session-id>        # full session (truncated at 300 chars)
python conv_archive.py --export  <session-id>        # full text, pipe-friendly
python conv_archive.py --export  <session-id> --date 2026-06-14  # one day only

# Maintenance
python conv_archive.py --rebuild-fts                 # rebuild FTS index from scratch
```

## Path configuration

| Method | DB path | Projects root |
|--------|---------|---------------|
| Default | `~/.conv_archive/conv_archive.db` | `~/.claude/projects` |
| Env var | `CONV_ARCHIVE_DB=<path>` | `CONV_ARCHIVE_ROOT=<path>` |
| CLI flag | `--db <path>` | `--root <path>` |

CLI flags take precedence over env vars.

## Date filter keywords

| Keyword | Range |
|---------|-------|
| `오늘` / `today` | today |
| `어제` / `yesterday` | yesterday |
| `그제` | 2 days ago |
| `이번주` / `thisweek` | last 7 days |
| `지난주` / `lastweek` | 7–14 days ago |

Combine with search terms: `python conv_archive.py --search "react hooks 어제"`

## Example workflow

```bash
# Run on a schedule to keep the archive fresh
# crontab: */30 * * * * python /path/to/conv_archive.py --scan

# Search for a past solution
python conv_archive.py --search "sqlite fts5"

# Export a session for sharing or review
python conv_archive.py --export abc12345-... --date 2026-06-14 > session.txt
```

## License

MIT
