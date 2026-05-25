#!/usr/bin/env bash
# UserPromptSubmit hook — kill any running TTS audio when user starts speaking
pkill -x ffplay 2>/dev/null || true
exit 0
