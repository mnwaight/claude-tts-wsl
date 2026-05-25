#!/usr/bin/env bash
# Stop hook — speak any assistant text not yet spoken this turn

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
[ -z "$SESSION_ID" ] && exit 0

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -z "$TRANSCRIPT" ] && exit 0

sleep 0.5

python3 /home/matthew/.claude/hooks/tts_speak.py "$TRANSCRIPT" "$SESSION_ID"
