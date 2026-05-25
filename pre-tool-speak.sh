#!/usr/bin/env bash
# PreToolUse hook — speak text written before this tool call, then announce what's running

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty' 2>/dev/null)
[ -z "$SESSION_ID" ] && exit 0

TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null)
[ -z "$TRANSCRIPT" ] && exit 0

TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
TOOL_INPUT=$(echo "$INPUT" | jq -c '.tool_input // {}' 2>/dev/null)

python3 /home/matthew/.claude/hooks/tts_speak.py "$TRANSCRIPT" "$SESSION_ID" "$TOOL_NAME" "$TOOL_INPUT"
