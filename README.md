# Dubify Studio

**Offline AI Video Subtitle Translation & Dubbing Desktop Application**

Built with Python 3.12, PySide6 (Qt6), Faster-Whisper, Multi-Provider AI (Gemini, OpenAI, Ollama, DeepSeek, Google Translate), Edge-TTS, and FFmpeg.

---

## 🌟 Key Features

1. **Video Import & Player**:
   - Supports `.mp4`, `.mkv`, `.avi`, `.mov`.
   - Built-in `QMediaPlayer` preview with Play, Pause, Seek, Volume, Loop, and Ratio options.

2. **Speech Recognition (STT)**:
   - Integrates `Faster-Whisper` (Tiny, Base, Medium, Large-v3).
   - Multi-language support (Chinese, English, Japanese, Korean, Auto).

3. **Subtitle Table Editor**:
   - Live double-click editing of Start/End timecodes, Source text, Khmer text, and Voice assignments.
   - Character Scanner (`Scan Characters`) for auto-detecting male, female, child, and elder roles.
   - Quick operations: `Add Text`, `Edit`, `Delete`, `Find & Replace`.
   - Keyboard Shortcuts (`Delete`, `Ctrl+N`).

4. **Context-Aware AI Translation**:
   - Translates lines with Context Windowing (Previous + Current + Next lines) for smooth, natural Khmer drama dubbing.
   - Multi-Provider routing: Gemini 2.5 Flash / Pro, OpenAI / DeepSeek API, Ollama (Local LLM), and Google Translate.
   - Translation Memory & Exact-Match SQLite Caching to prevent redundant API calls.

5. **Multitrack Timeline Editor**:
   - Premiere / Aegisub style timeline visualizer with `TEXT`, `AUDIO`, and `BGM` tracks.
   - Time ruler with playhead marker, zoom controls (`0.5x` to `4.0x`), and `Fit` view.

6. **TTS Voice Dubbing**:
   - Generates natural Khmer audio using `Edge-TTS` (`km-KH-PisethNeural`, `km-KH-SreymomNeural`).
   - Customizable per-character voice profiles.

7. **Export Options**:
   - Subtitles: `.srt`, `.ass`.
   - Dubbed Video: `.mp4` rendered with subtitle burning and dub audio track using FFmpeg.

---

## 📁 Directory Structure

```
translator/
    app/
        ui/
            main_window.py       # Main Application Window
            timeline.py          # Multitrack Timeline Widget
            editor.py            # Subtitle Data Table Editor
            setting.py           # Settings & AI Preferences Modal
        core/
            ffmpeg.py            # FFmpeg audio extraction & video rendering
            whisper.py           # Faster-Whisper STT QThread worker
            translator.py        # Context-aware translation manager
            subtitle.py          # SRT & ASS parser/exporter
            tts.py               # Edge-TTS voice generation worker
            cache.py             # SQLite translation cache
            exporter.py          # Video & subtitle export manager
        ai/
            base.py              # Base AI provider interface
            gemini.py            # Gemini 2.5 Flash / Pro provider
            openai.py            # OpenAI & DeepSeek provider
            ollama.py            # Local Ollama LLM provider
            deepl.py             # Google Translate provider
        database/
            sqlite.py            # SQLite database schema & operations
        model/
            models.py            # Data classes (SubtitleItem, VoiceProfile, etc.)
        assets/
            style.qss            # Modern Dark Theme stylesheet
        output/
        temp/
    main.py                      # Application Entry point
main.py                          # Root launcher
```

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch Application
```bash
python main.py
```
