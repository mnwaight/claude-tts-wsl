# claude-tts-wsl

Claude Code TTS and voice hook setup for WSL2 — hooks, scripts, and config for speech input and spoken responses.

Tested on WSL2 + WSLg on Windows 11 with Claude Code CLI. Windows 10 is not supported.

## What It Does

**Voice input** uses Claude Code's built-in hold mode. Hold Space to speak, release to submit — no Enter key needed. Releasing the spacebar automatically fires the prompt, so the full interaction is hands-free. This is driven by `"autoSubmit": true` in the voice config block in `settings.json`.

**TTS output** is driven by three lifecycle hooks that fire around each response turn:

- `UserPromptSubmit` — stops any playing audio the instant you start speaking so Claude never talks over you.
- `PreToolUse` — fires before each tool call. Speaks any text Claude wrote since the last hook. If Claude goes straight to a tool with no preamble, it announces what's running ("Running a command", "Checking Telescope", etc.) so you have audio context without looking at the screen.
- `Stop` — fires when the full response is complete. Speaks any remaining text not yet spoken.

A shared state file (`/tmp/tts_state.json`) tracks the last transcript index spoken so nothing is repeated or skipped across hook fires.

## Audio Architecture

**TTS output does NOT go through PulseAudio.** Audio is played via Windows MCI (winmm.dll) using `powershell.exe`. This bypasses the WSLg PulseAudio pipeline entirely, which is unreliable for playback (see [Known Issues](#known-issues)).

The flow for each response:
1. `edge-tts` synthesizes speech to `/tmp/claude-cli-speech.mp3`
2. The file is copied to `C:\Windows\Temp\claude-tts-speech.mp3`
3. `powershell.exe` plays it via `mciSendString` (winmm.dll), waiting for completion
4. The PowerShell process is launched detached (`start_new_session=True`) so it outlives the hook timeout

**Voice input still uses PulseAudio** via SoX. If voice input stops working, restart WSLg with `wsl --shutdown` from Windows PowerShell, then reopen your terminal.

## Dependencies

```bash
# TTS engine
pip install edge-tts

# For voice input — SoX with PulseAudio backend
sudo apt install sox libsox-fmt-pulse jq
```

No ffmpeg or ffplay needed for audio playback — Windows handles playback directly.

WSLg must be active for voice input. The PulseAudio socket at `unix:/mnt/wslg/runtime-dir/pulse/native` is required for SoX recording. This is automatic on Windows 11 with a current WSL2 release.

## Installation

1. Copy the hooks into place:

```bash
mkdir -p ~/.claude/hooks
cp hooks/* ~/.claude/hooks/
chmod +x ~/.claude/hooks/*.sh
```

2. Copy the PowerShell scripts to Windows temp (required for audio playback):

```bash
cp windows/claude_tts_play.ps1 /mnt/c/Windows/Temp/
cp windows/claude_tts_stop.ps1 /mnt/c/Windows/Temp/
```

3. Merge the relevant blocks from `settings.json` into your `~/.claude/settings.json`:

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

4. Restart Claude Code. Run `/voice` in the chat to confirm voice mode is active.

## File Reference

```
hooks/
├── tts_speak.py          # Shared TTS logic used by all hooks
├── stop-audio.sh         # UserPromptSubmit: stops audio on new user input
├── pre-tool-speak.sh     # PreToolUse: speaks text + announces tool before each call
└── speak-response.sh     # Stop: speaks final response text after the turn ends
windows/
├── claude_tts_play.ps1   # PowerShell: plays C:\Windows\Temp\claude-tts-speech.mp3 via MCI
└── claude_tts_stop.ps1   # PowerShell: stops and closes the MCI device
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

# Clear stale state (forces next hook to start fresh)
rm /tmp/tts_state.json

# Kill stuck audio
pkill -f claude_tts_play

# Test TTS manually (full pipeline)
edge-tts --voice en-US-JennyNeural --text "Hello" --write-media /tmp/test.mp3 \
  && cp /tmp/test.mp3 /mnt/c/Windows/Temp/claude-tts-speech.mp3 \
  && powershell.exe -NonInteractive -WindowStyle Hidden \
     -File 'C:\Windows\Temp\claude_tts_play.ps1' \
     -FilePath 'C:\Windows\Temp\claude-tts-speech.mp3'
```

## Known Issues

**WSLg PulseAudio is unreliable for audio playback.** On some machines the `module-rdp-sink` module loses its connection to FreeRDP and the PA event loop deadlocks. Symptoms: `pactl` hangs or returns "Connection refused", `ffplay`/`paplay` return exit code 0 but produce no sound. This is why audio output was moved to Windows MCI.

Do not run `pactl unload-module` or `pactl load-module` for `module-rdp-sink` — this can lock up PulseAudio until the next WSL restart.

**If voice input stops working:** PulseAudio has likely deadlocked. Fix: run `wsl --shutdown` from Windows PowerShell, then reopen your WSL terminal. Audio output will continue working since it doesn't depend on PulseAudio.

**WSL restart wipes `/tmp/tts_state.json`.** The hook handles this gracefully — on first run with no state file it defaults to the end of the transcript rather than replaying the full conversation history.

## Why This Stack

**edge-tts over local TTS engines (piper, espeak, etc.):** Local engines had unacceptable latency — even a short response took several seconds before audio started. edge-tts calls Microsoft's cloud API and returns audio in under 2 seconds consistently.

**Windows MCI over ffplay/PulseAudio for playback:** WSLg PulseAudio is fragile for audio output — the `module-rdp-sink` can drop its FreeRDP socket silently, after which all playback fails with exit code 0 (no error, no audio). Windows MCI (winmm.dll via `powershell.exe`) plays directly to the Windows default audio device, bypasses the entire WSLg pipeline, and is reliable. The tradeoff is a ~200ms PowerShell startup overhead per response.

**`Popen` + `start_new_session=True` over `subprocess.run`:** Claude Code hook timeouts are 30 seconds. A blocking `subprocess.run` for audio playback means long responses get cut off mid-speech when the hook process is killed. Detaching the PowerShell process into its own session lets audio finish independently of the hook.

**WSLg is still required for voice input.** SoX with `libsox-fmt-pulse` records from `PulseAudioRDPSource` via WSLg. If `unix:/mnt/wslg/runtime-dir/pulse/native` doesn't exist, voice input won't work. Windows 11 with a current WSL2 release is required.

## macOS (Untested)

This setup has not been tested on macOS. The Windows MCI playback path is WSL-specific. On macOS you would need to replace `claude_tts_play.ps1` with an `afplay` call, and remove the `PULSE_SERVER`/`DISPLAY` env vars from `settings.json`. Voice input should work natively without SoX. No guarantees — if you get it working, please open a PR.
