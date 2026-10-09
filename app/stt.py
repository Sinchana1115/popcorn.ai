"""Voice: speech-to-text with Whisper (multilingual, auto language detection)."""
import os
_model = None


def transcribe(path: str, language: str | None = None):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), compute_type="int8")
    segs, info = _model.transcribe(path, language=language or None, vad_filter=True)
    return " ".join(s.text.strip() for s in segs).strip(), info.language
