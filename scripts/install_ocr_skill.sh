#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/install_ocr_skill.sh [--codex-only|--claude-only] [--dry-run]

Installs:
  Codex:      $CODEX_HOME/skills/ocr or ~/.codex/skills/ocr
  Claude:     $CLAUDE_HOME/skills/ocr or ~/.claude/skills/ocr
  Claude /ocr command: $CLAUDE_HOME/commands/ocr.md or ~/.claude/commands/ocr.md

The installer copies skill files only. It does not copy, print, or validate secrets.
USAGE
}

install_codex=1
install_claude=1
dry_run=0

for arg in "$@"; do
  case "$arg" in
    --codex-only)
      install_codex=1
      install_claude=0
      ;;
    --claude-only)
      install_codex=0
      install_claude=1
      ;;
    --dry-run)
      dry_run=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
skill_src="$repo_root/skills/ocr"
command_src="$repo_root/claude/commands/ocr.md"

copy_dir() {
  local src="$1"
  local dest="$2"
  if [ "$dry_run" -eq 1 ]; then
    echo "would install $src -> $dest"
    return
  fi
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  cp -R "$src" "$dest"
  chmod +x "$dest/scripts/run_ocr.py"
  echo "installed $dest"
}

copy_file() {
  local src="$1"
  local dest="$2"
  if [ "$dry_run" -eq 1 ]; then
    echo "would install $src -> $dest"
    return
  fi
  mkdir -p "$(dirname "$dest")"
  cp "$src" "$dest"
  echo "installed $dest"
}

if [ "$install_codex" -eq 1 ]; then
  codex_home="${CODEX_HOME:-$HOME/.codex}"
  copy_dir "$skill_src" "$codex_home/skills/ocr"
fi

if [ "$install_claude" -eq 1 ]; then
  claude_home="${CLAUDE_HOME:-$HOME/.claude}"
  copy_dir "$skill_src" "$claude_home/skills/ocr"
  copy_file "$command_src" "$claude_home/commands/ocr.md"
fi

cat <<'NEXT'

Next:
  export OCR_HOST=127.0.0.1:8080
  export OCR_API_KEY=<your key>

Usage:
  Codex:  $ocr /path/to/file.pdf
  Claude: /ocr /path/to/file.pdf
NEXT
