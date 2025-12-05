# VORTEX

**Voice-Oriented Responsive Terminal EXecutive**

VORTEX is a Windows desktop AI assistant with a PyQt6 console UI, Porcupine wake-word detection, camera-aware security, memory, workflows, and a lightweight rule-based command engine. It can listen for "Vortex", record a short phrase, transcribe it, and execute actions such as opening/closing apps, storing notes, and running predefined workflows.

## Features

- Porcupine wake word ("Vortex" or fallback "Jarvis") with custom `.ppn` support
- Camera security: detects a blocked/covered webcam and temporarily disables commands
- Voice capture → Whisper-like STT pipeline (tiny.en on CPU) + TTS responses
- Memory: persistent JSON store with optional semantic search
- Workflows: JSON-defined steps (say, sleep, open/close app, note) in `data/workflows/`
- Timeline + Memory panels in the UI; animated console messages
- Rule-based command parsing for open/close apps, notes, smalltalk fallback
- Friend mode: occasional personality prompts during idle time

---

## Prerequisites

- **Python 3.10+** (uses modern typing syntax)
- **Windows 10/11**
- **Microphone** (for voice capture) and **webcam** (for security monitor)
- **Porcupine access key** (for wake word). If omitted, wake word is disabled but you can still click the mic button or type commands.
- Recommended: Visual C++ Build Tools for compiling packages like `pyaudio` if needed.

## Installation

```bash
cd D:\GitHub\V.O.R.T.E.X
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

If `pyaudio` fails, install a prebuilt wheel from https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio (match your Python version).

## Wake Word Setup

1. Put your Porcupine access key in `vortex/controller.py` (see `PORCUPINE_ACCESS_KEY`).
2. A custom wakeword file is expected at `data/wakewords/vortex_en_windows_v3_0_0.ppn`. If missing, the controller falls back to the built-in keyword "Jarvis".
3. If you leave the access key empty, wake word is disabled; you can still trigger the mic button manually or type commands.

## Running

```bash
python main.py
```

On first run VORTEX will:
- Start the camera monitor (security)
- Create `data/workflows/focus_mode.json` if none exist
- Create `data/memory.json` on first note
- Begin friend-mode idle prompts and log to `logs/vortex.log`

The UI opens maximized with a console on the left and tabs (Commands/Timeline/Memory) on the right. Use the text box or mic button at the bottom to issue commands.

## Using VORTEX

- **Wake word**: Say "Vortex" (or "Jarvis" fallback) if a Porcupine key is configured.
- **Manual mic**: Click the mic button to record a short phrase.
- **Typed commands**: Enter text in the command box and press Enter/Send.
- **Security**: If the webcam is dark/blocked, VORTEX switches to SECURITY theme, ignores commands, and announces it. Removing the obstruction restores normal mode.

### Built-in commands (examples)

- Focus workflow: `focus mode`, `start focus mode`, or `run workflow focus mode`
- List workflows: `list workflows` / `show workflows`
- Run a workflow: `run workflow <name>`
- Open apps: `open notepad | chrome | edge | code | whatsapp`
- Close apps: `close <app>`, or `close that/it` to close the last opened app
- Notes: `remember that ...`, `make a note that ...`
- Recall notes: `what did I tell you to remember`, `what do you remember`
- Security reset: `normal mode` / `return to normal mode`

### Workflows

Workflows live in `data/workflows/*.json`. Supported step types: `say`, `sleep`, `open_app`, `close_app`, `note`.

Example (`data/workflows/focus_mode.json` created automatically):
```json
{
  "name": "focus_mode",
  "description": "Close distractions and open coding tools for deep work.",
  "steps": [
    {"type": "say", "text": "Entering focus mode. Closing distractions and opening your tools."},
    {"type": "close_app", "app": "chrome"},
    {"type": "close_app", "app": "edge"},
    {"type": "sleep", "seconds": 1},
    {"type": "open_app", "app": "code"},
    {"type": "note", "text": "Focus session started by VORTEX.", "category": "workflow"},
    {"type": "say", "text": "You're all set. Let's get some serious work done."}
  ]
}
```
Create new workflows by copying this pattern and placing the JSON file in `data/workflows/`.

## Data & Logs

- Logs: `logs/vortex.log`
- Memory store: `data/memory.json`
- Wake word files: `data/wakewords/`
- Workflows: `data/workflows/`

## Project Structure (current)

```
V.O.R.T.E.X/
├── main.py
├── README.md
├── logs/
│   └── vortex.log
├── data/
│   ├── memory.json
│   ├── wakewords/
│   │   └── vortex_en_windows_v3_0_0.ppn
│   └── workflows/
│       └── focus_mode.json   # auto-created sample
└── vortex/
    ├── ui.py                 # PyQt6 window, console/tabs/input
    ├── controller.py         # Orchestrator (wake word, STT, TTS, workflows, security)
    └── core/
        ├── audio_manager.py
        ├── camera_monitor.py
        ├── command_engine.py
        ├── identity.py
        ├── logger.py
        ├── memory.py
        ├── personality.py
        ├── stt_service.py
        ├── timeline.py
        ├── tts_service.py
        ├── wake_word.py
        └── workflow_engine.py
```

## Troubleshooting

- **Wake word not working**: Add a valid Porcupine access key in `vortex/controller.py`; ensure the `.ppn` file exists in `data/wakewords/`.
- **Camera blocked notice keeps appearing**: Ensure the webcam is uncovered and available to OpenCV; the monitor now tolerates temporary failures but will stay in SECURITY while frames are dark/unreadable.
- **PyAudio errors**: Close other apps using the mic; install a compatible wheel; run inside the virtual environment.
- **Missing packages**: `pip install -r requirements.txt` (from the activated venv).
- **Slow or empty STT**: Check microphone input levels and that the device is not muted.

---

⚠ **This project is proprietary. Do not copy or reuse any part of the code. All rights reserved.**