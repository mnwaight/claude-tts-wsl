# claude-tts-wsl

Claude Code TTS and voice hook setup for WSL2 — hooks, scripts, and config for speech input and spoken responses.

Tested on WSL2 with WSLg (Windows 11) and Claude Code CLI.

## What It Does

**Voice input** uses Claude Code's built-in hold mode. Hold Space to speak, release to submit — no Enter key needed. Releasing the spacebar automatically fires the prompt, so the full interaction is hands-free. This is driven by `"autoSubmit": true` in the voice config block in `settings.json`.

**TTS output** is driven by three lifecycle hooks that fire around each response turn:

- `UserPromptSubmit` — kills any playing audio the instant you start speaking so Claude never talks over you.
- `PreToolUse` — fires before each tool call. Speaks any text Claude wrote since the last hook. If Claude goes straight to a tool with no preamble, it announces what's running ("Running a command", "Checking Telescope", etc.) so you have audio context without looking at the screen.
- `Stop` — fires when the full response is complete. Speaks any remaining text not yet spoken.

A shared state file (`/tmp/tts_state.json`) tracks the last transcript index spoken so nothing is repeated or skipped across hook fires.

## Dependencies

Install these before setup:

```bash
# TTS engine and audio playback
pip install edge-tts
sudo apt install ffmpeg jq

# For voice input — SoX with PulseAudio backend (WSLg)
sudo apt install sox libsox-fmt-pulse
```

WSLg must be active and the PulseAudio socket must exist at `unix:/mnt/wslg/runtime-dir/pulse/native`. This is automatic on Windows 11 with a current WSL2 release.

## Installation

1. Copy the hooks into place:

```bash
mkdir -p ~/.claude/hooks
cp hooks/* ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

2. Merge the relevant blocks from `settings.json` into your `~/.claude/settings.json`:

```json
{
  "env": {
    "PULSE_SERVER": "unix:/mnt/wslg/runtime-dir/pulse/native",
    "DISPLAY": ":0"
  },
  "voice": {
    "enabled": true,
    "mode": "hold",
    "autoSubmit": true
  },
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/stop-audio.sh", "timeout": 5 }] }
    ],
    "PreToolUse": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/pre-tool-speak.sh", "timeout": 30 }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command", "command": "~/.claude/hooks/speak-response.sh", "timeout": 30 }] }
    ]
  }
}
```

3. Restart Claude Code. Run `/voice` in the chat to confirm voice mode is active.

## File Reference

```
hooks/
├── tts_speak.py          # Shared TTS logic used by all hooks
├── stop-audio.sh         # UserPromptSubmit: kills ffplay on new user input
├── pre-tool-speak.sh     # PreToolUse: speaks text + announces tool before each call
└── speak-response.sh     # Stop: speaks final response text after the turn ends
settings.json             # Example settings block to merge into ~/.claude/settings.json
```

## Response Style

For natural-sounding speech, instruct Claude in your `CLAUDE.md` to write prose instead of markdown lists and headers. Code blocks are fine — they get stripped before TTS. Example instruction:

```
## Voice Mode
This environment uses voice input and text-to-speech output. Write responses that work well spoken aloud:
- Use flowing prose instead of bullet points or markdown headers
- Keep sentences short and direct
- Code blocks are fine but prose around them should read naturally
```

## Debugging

```bash
# Check TTS state
cat /tmp/tts_state.json

# Kill stuck audio
pkill ffplay

# Test TTS manually
edge-tts --voice en-US-JennyNeural --text "Hello" --write-media /tmp/test.mp3 && ffplay -nodisp -autoexit /tmp/test.mp3
```

## Why This Stack

After significant time debugging on WSL2 without WSLg, WSLg + edge-tts + ffplay is the only approach that worked reliably. Key decisions:

**edge-tts over local TTS engines (piper, espeak, etc.):** Local engines had unacceptable latency — even a short response took several seconds before audio started. edge-tts calls Microsoft's cloud API and returns audio in under 2 seconds consistently.

**ffplay over paplay/RDPSink:** On machines without WSLg, the common workaround is routing audio through Windows via an RDP audio sink using `paplay --device=RDPSink`. This requires manually unsuspending the sink before each playback, introduces sync issues, and still had latency problems. On WSLg, the PulseAudio socket is available natively and ffplay plays back with no additional setup.

**`Popen` + `start_new_session=True` over `subprocess.run`:** Claude Code hook timeouts are 30 seconds. A blocking `subprocess.run` for audio playback means any response longer than ~27 seconds gets cut off mid-speech when the hook process is killed. Detaching ffplay into its own process group with `start_new_session=True` lets audio finish independently of the hook. The hook only needs to cover edge-tts generation (~2-3 seconds) — ffplay plays on after the hook exits.

**WSLg is a hard requirement.** If `unix:/mnt/wslg/runtime-dir/pulse/native` doesn't exist on your machine, this setup will not work. WSLg requires Windows 11 with a current WSL2 release. There is no reliable drop-in alternative for WSL2 on Windows 10.

## Known Limitations

- During long-running Bash or tool calls there is silence — `PreToolUse` fires before the tool starts but there is no mid-tool audio progress.
- If you manually navigate inside Claude's Playwright browser while it is active, the MCP may lose its page reference and the `Stop` hook may not fire.
- If `/tmp/tts_state.json` is missing on first run, the Stop hook may attempt to speak from the beginning of the session. The 8000-character cap limits this.
