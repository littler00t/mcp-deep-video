"""TranscriptionBackend — audio transcription via Groq or local Whisper."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path


class TranscriptionBackend(ABC):
    """Abstract base for transcription backends."""

    @abstractmethod
    def transcribe(self, audio_path: Path) -> dict:
        """Transcribe an audio file. Returns normalized transcript dict."""
        ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


class GroqBackend(TranscriptionBackend):
    """Transcription via Groq API (whisper-large-v3-turbo)."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @property
    def backend_name(self) -> str:
        return "groq"

    @property
    def model_name(self) -> str:
        return "whisper-large-v3-turbo"

    def transcribe(self, audio_path: Path) -> dict:
        try:
            from groq import Groq
        except ImportError:
            raise RuntimeError(
                "Groq SDK not installed. Install with: pip install groq"
            )

        client = Groq(api_key=self.api_key)
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["word", "segment"],
            )

        # Normalize to common format
        result = response.model_dump() if hasattr(response, "model_dump") else dict(response)

        segments = []
        for seg in result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0),
                    "confidence": w.get("confidence", 0.0),
                })
            segments.append({
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", ""),
                "confidence": seg.get("avg_logprob", 0.0),
                "words": words,
            })

        return {
            "backend": self.backend_name,
            "model": self.model_name,
            "language": result.get("language", "en"),
            "duration_seconds": result.get("duration", 0.0),
            "segments": segments,
        }


class WhisperBackend(TranscriptionBackend):
    """Transcription via local openai-whisper."""

    def __init__(self, model_name: str = "base") -> None:
        self._model_name = model_name
        self._model = None  # Lazy load

    @property
    def backend_name(self) -> str:
        return "whisper-local"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _load_model(self):
        if self._model is None:
            try:
                import whisper
            except ImportError:
                raise RuntimeError(
                    "Local transcription requires 'openai-whisper'. "
                    "Install with: pip install openai-whisper"
                )
            self._model = whisper.load_model(self._model_name)
        return self._model

    def transcribe(self, audio_path: Path) -> dict:
        model = self._load_model()
        result = model.transcribe(str(audio_path), word_timestamps=True)

        segments = []
        for seg in result.get("segments", []):
            words = []
            for w in seg.get("words", []):
                words.append({
                    "word": w.get("word", ""),
                    "start": w.get("start", 0.0),
                    "end": w.get("end", 0.0),
                    "confidence": w.get("probability", 0.0),
                })
            segments.append({
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", ""),
                "confidence": seg.get("avg_logprob", 0.0),
                "words": words,
            })

        return {
            "backend": self.backend_name,
            "model": self.model_name,
            "language": result.get("language", "en"),
            "duration_seconds": result.get("duration", 0.0) if "duration" in result else 0.0,
            "segments": segments,
        }


def extract_audio(video_path: Path) -> Path:
    """Extract audio from video to a temporary WAV file using ffmpeg."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(video_path),
                "-vn", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                "-y", tmp.name,
            ],
            capture_output=True, text=True, timeout=300,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        Path(tmp.name).unlink(missing_ok=True)
        raise RuntimeError(f"Audio extraction failed: {e.stderr}")
    except FileNotFoundError:
        Path(tmp.name).unlink(missing_ok=True)
        raise RuntimeError("ffmpeg not found. Install ffmpeg to use transcription.")
    return Path(tmp.name)


def create_backend() -> TranscriptionBackend:
    """Create the appropriate transcription backend based on environment."""
    groq_key = os.environ.get("GROQ_API_KEY")
    if groq_key:
        return GroqBackend(groq_key)
    whisper_model = os.environ.get("MCP_WHISPER_MODEL", "base")
    return WhisperBackend(whisper_model)
