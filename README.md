# VORTEX

**Voice-Oriented Responsive Terminal EXecutive**

VORTEX is a Windows desktop AI assistant that provides voice-controlled interaction with your computer. It features always-listening microphone input, wake word detection ("Vortex"), speaker verification for security, and a fullscreen tech-style UI. VORTEX can launch applications, execute commands, and respond to voice instructions while maintaining a sleek, dark interface with neon accents.

## Features

- Always-listening microphone with wake word detection
- Speaker verification for secure access
- Fullscreen PyQt6 tech-style UI
- Voice command execution
- Application launching and window management
- Text-to-speech responses

---

## Prerequisites

- **Python 3.8 or higher** (Python 3.9+ recommended)
- **Windows 10/11** (required for pywin32 and Windows-specific features)
- **Microphone** connected and working
- **Administrator privileges** (may be required for some operations)

## Installation

### 1. Clone or Download the Project

```bash
cd D:\GitHub\V.O.R.T.E.X
```

### 2. Create a Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** If you encounter issues installing `pyaudio` on Windows, you may need to:
- Install Microsoft Visual C++ Build Tools
- Or download a pre-built wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
  ```bash
  pip install PyAudio‑0.2.14‑cp39‑cp39‑win_amd64.whl
  ```
  (Replace `cp39` with your Python version)

### 4. Verify Installation

```bash
python -c "import PyQt6; import pyaudio; import pyttsx3; import numpy; print('All dependencies installed!')"
```

## Running VORTEX

### Basic Run

```bash
python main.py
```

The application will:
1. Initialize logging (console + `data/logs/vortex.log`)
2. Load configuration from `config.json`
3. Open in fullscreen mode
4. Start listening for the wake word "Vortex"

### First Run

On first run, VORTEX will:
- Create default `config.json` if it doesn't exist
- Create necessary directories (`data/logs/`, `data/voice_profile/`)
- Start in **test mode** (speaker verification accepts all speakers)

### Testing the Application

Since wake-word detection is currently a placeholder, use the test trigger:

1. **Click the red "🔴 Simulate Wake Word" button** in the status bar
2. **OR press the SPACE key** to simulate wake word detection
3. VORTEX will record 5 seconds of audio (or use the simulated command)
4. The STT service will return a random test command
5. Watch the console/logs to see the full processing flow

### Using VORTEX

1. **Wake Word**: Say "Vortex" (currently simulated via button/SPACE)
2. **Command Examples**:
   - "open notepad" - Opens Notepad (embedded in VORTEX)
   - "open calculator" - Opens Calculator
   - "open chrome" - Opens Chrome browser
   - "what time is it" - Returns current time
   - "open valorant" - Opens Valorant (minimizes VORTEX)
   - "vortex come back" - Restores VORTEX window

3. **Keyboard Shortcuts**:
   - `SPACE` - Simulate wake word (test mode)
   - `ESC` or `F11` - Toggle fullscreen

## Voice Enrollment (Training Your Voice Model)

To train VORTEX to recognize your voice:

### Step 1: Run the Enrollment Script

```bash
python enroll_voice.py
```

### Step 2: Follow the Prompts

1. **Choose number of samples** (recommended: 5-10)
   - More samples = better accuracy
   - Minimum: 3 samples

2. **Choose sample duration** (recommended: 3 seconds)
   - Each sample will record for this duration

3. **Record your voice**
   - Speak clearly and naturally
   - You can say anything: your name, a phrase, or just talk
   - Wait for the recording to complete before speaking

### Step 3: Enable Voice Verification

After enrollment, edit `config.json`:

```json
{
  "speaker_verification": {
    "similarity_threshold": 0.7,
    "test_mode": false
  }
}
```

Set `"test_mode": false` to enable real voice verification.

### Step 4: Restart VORTEX

```bash
python main.py
```

Now VORTEX will:
- ✅ Accept commands only from your voice
- 🚨 Show "Intruder alert" if someone else speaks

**Note:** If you need to re-enroll, just run `enroll_voice.py` again. It will overwrite your previous voice profile.

## Configuration

Edit `config.json` to customize:

- **Wake word**: Change `"wake_word"` value
- **App paths**: Update `"apps"` section with your application paths
- **Speaker verification**: Adjust `"speaker_verification.similarity_threshold"` (0.0-1.0)
- **Test mode**: Set `"speaker_verification.test_mode"` to `false` for production

Example:
```json
{
  "wake_word": "vortex",
  "apps": {
    "notepad": "notepad.exe",
    "vscode": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe"
  }
}
```

## Troubleshooting

### Audio Issues

- **"No microphone found"**: Check Windows microphone permissions
- **"PyAudio error"**: Ensure microphone is not being used by another application
- **"Audio stream error"**: Try running as Administrator

### Import Errors

- **"ModuleNotFoundError"**: Run `pip install -r requirements.txt` again
- **"PyQt6 not found"**: Ensure virtual environment is activated

### Window Issues

- **"Window not embedding"**: Some apps (especially games) cannot be embedded due to security restrictions
- **"VORTEX not minimizing"**: Check that callbacks are properly set in `core/vortex.py`

### Logs

Check `data/logs/vortex.log` for detailed error messages and execution flow.

## Windows Startup (Optional)

To run VORTEX automatically on Windows startup:

```python
from core.startup_helper import StartupHelper

helper = StartupHelper()
helper.print_startup_instructions()  # Shows detailed instructions
```

Or manually:
1. Press `Windows + R`, type `shell:startup`
2. Create a shortcut to `python.exe` with arguments: `"D:\GitHub\V.O.R.T.E.X\main.py"`
3. Or create a batch file that activates venv and runs the script

## Project Structure

```
V.O.R.T.E.X/
├── main.py                 # Entry point
├── config.json             # Configuration file
├── requirements.txt        # Python dependencies
├── core/                   # Core backend modules
│   ├── vortex.py          # Main orchestrator
│   ├── config.py          # Configuration manager
│   ├── audio_manager.py   # Audio capture
│   ├── stt_service.py     # Speech-to-text
│   ├── tts_service.py     # Text-to-speech
│   ├── speaker_verification.py
│   ├── command_processor.py
│   └── app_launcher.py
├── ui/                     # PyQt6 GUI
│   ├── main_window.py
│   └── widgets/
└── data/                   # Data storage
    ├── logs/              # Application logs
    └── voice_profile/     # Voice enrollment data
```

## Development Notes

- **Test Mode**: Currently uses stub implementations for wake-word detection and STT
- **Speaker Verification**: In test mode, accepts all speakers (set `test_mode: false` for production)
- **STT**: Returns random test commands (replace `StubSTTProvider` with real implementation)
- **Wake Word**: Currently simulated via button/keyboard (implement real detection later)

## Next Steps for Production

1. Replace `StubSTTProvider` with real STT (Whisper, Vosk, etc.)
2. Implement real wake-word detection (Porcupine, custom model)
3. Replace speaker verification placeholder with real embedding model
4. Enroll owner's voice for speaker verification
5. Test with real microphone input

---

⚠ **This project is proprietary. Do not copy or reuse any part of the code. All rights reserved.**