#!/usr/bin/env python3
"""Shared TTS logic for Claude Code hooks. Called with: path session_id [tool_name] [tool_input_json]"""
import sys, json, re, subprocess, os, shutil

STATE_FILE = '/tmp/tts_state.json'
WIN_TTS_MP3   = '/mnt/c/Windows/Temp/claude-tts-speech.mp3'
WIN_PLAY_PS1  = 'C:\\Windows\\Temp\\claude_tts_play.ps1'
WIN_STOP_PS1  = 'C:\\Windows\\Temp\\claude_tts_stop.ps1'

TOOL_LABELS = {
    'Bash':                                    'Running a command.',
    'Read':                                    'Reading a file.',
    'Edit':                                    'Editing a file.',
    'Write':                                   'Writing a file.',
    'Agent':                                   'Launching a sub-agent.',
    'WebFetch':                                'Fetching a page.',
    'WebSearch':                               'Searching the web.',
    'mcp__playwright__browser_navigate':       None,
    'mcp__playwright__browser_evaluate':       'Checking the page.',
    'mcp__playwright__browser_snapshot':       'Reading the page.',
    'mcp__playwright__browser_click':          'Clicking on the page.',
    'mcp__playwright__browser_fill_form':      'Filling a form.',
    'mcp__playwright__browser_type':           'Typing on the page.',
    'mcp__playwright__browser_take_screenshot':'Taking a screenshot.',
}

def tool_description(tool_name, tool_input=None):
    if tool_name == 'mcp__playwright__browser_navigate' and tool_input:
        try:
            inp = tool_input if isinstance(tool_input, dict) else json.loads(tool_input)
            url = inp.get('url', '').lower()
            if 'telescope' in url:    return 'Checking Telescope.'
            if 'horizon' in url:      return 'Checking Horizon.'
            if 'cornerstone2' in url: return 'Opening CS2.'
            return 'Navigating the browser.'
        except Exception:
            return 'Navigating the browser.'
    return TOOL_LABELS.get(tool_name, '')

def load_last_idx(session_id):
    try:
        with open(STATE_FILE) as f:
            s = json.load(f)
        if s.get('session_id') == session_id:
            return s.get('last_idx', -1)
    except Exception:
        pass
    return -1

def save_last_idx(session_id, idx):
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump({'session_id': session_id, 'last_idx': idx}, f)
    except Exception:
        pass

def speak(path, session_id, tool_name=None, tool_input=None):
    last_idx = load_last_idx(session_id)

    try:
        with open(path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
    except Exception:
        return

    # On first run (no saved state), skip history — only speak the latest entry
    if last_idx == -1 and len(lines) > 1:
        last_idx = len(lines) - 2

    chunks = []
    for i, entry in enumerate(lines):
        if i <= last_idx:
            continue
        if entry.get('type') != 'assistant':
            continue
        content = entry.get('message', {}).get('content', [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    t = block.get('text', '').strip()
                    if t:
                        chunks.append(t)
        elif isinstance(content, str) and content.strip():
            chunks.append(content.strip())

    save_last_idx(session_id, len(lines) - 1)

    if not chunks:
        desc = tool_description(tool_name, tool_input) if tool_name else ''
        if not desc:
            return
        text = desc
    else:
        text = ' '.join(chunks)

    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'`[^`]*`', ' ', text)
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\*', '', text)
    text = re.sub(r'[#_\[\]()]', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text[:8000]

    if not text:
        return

    tts_tmp = '/tmp/claude-cli-speech.mp3'
    result = subprocess.run(
        ['edge-tts', '--voice', 'en-US-JennyNeural', '--text', text, '--write-media', tts_tmp],
        capture_output=True
    )
    if result.returncode != 0:
        return

    # Kill any previous TTS playback
    subprocess.run(['pkill', '-f', 'claude_tts_play'], capture_output=True)

    # Copy to Windows-accessible path and play via Windows MCI
    try:
        shutil.copy2(tts_tmp, WIN_TTS_MP3)
    except Exception:
        return

    subprocess.Popen(
        ['powershell.exe', '-NonInteractive', '-WindowStyle', 'Hidden',
         '-File', WIN_PLAY_PS1, '-FilePath', 'C:\\Windows\\Temp\\claude-tts-speech.mp3'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        tool_name  = sys.argv[3] if len(sys.argv) > 3 else None
        tool_input = sys.argv[4] if len(sys.argv) > 4 else None
        speak(sys.argv[1], sys.argv[2], tool_name, tool_input)
