"""Tool: get_audio_transcript."""

from __future__ import annotations

import json

from mcp.server import Server
from mcp.types import TextContent, Tool

from ..extractor import FrameExtractor
from ..transcription import extract_audio
from . import tool_def


async def _get_audio_transcript(server: Server, arguments: dict) -> list[TextContent]:
    filename = arguments.get("filename", "")
    start_seconds = arguments.get("start_seconds")
    end_seconds = arguments.get("end_seconds")
    word_level = arguments.get("word_level", False)
    debug = arguments.get("debug", False)

    resolver = server._resolver  # type: ignore[attr-defined]
    cache = server._cache  # type: ignore[attr-defined]
    transcription = server._transcription  # type: ignore[attr-defined]
    debug_writer = server._debug  # type: ignore[attr-defined]

    try:
        video_path = resolver.resolve(filename)
    except ValueError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    # Check for audio
    ext = FrameExtractor(video_path)
    meta = ext.get_metadata()
    if not meta.get("has_audio"):
        return [TextContent(type="text", text=json.dumps({"error": f"'{filename}' has no audio track"}))]

    if transcription is None:
        return [TextContent(type="text", text=json.dumps({
            "error": "No transcription backend available. Set GROQ_API_KEY or install openai-whisper."
        }))]

    duration = meta["duration_seconds"]

    # Check cache
    cached = cache.read_transcript(filename, video_path)
    if cached is None:
        # Transcribe
        audio_path = None
        try:
            audio_path = extract_audio(video_path)
            transcript_data = transcription.transcribe(audio_path)
            cache.write_transcript(filename, video_path, transcript_data)
            cached = transcript_data
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Transcription failed ({transcription.backend_name}): {e}"
            }))]
        finally:
            if audio_path is not None:
                audio_path.unlink(missing_ok=True)

    # Filter by time window
    if start_seconds is None:
        start_seconds = 0.0
    if end_seconds is None:
        end_seconds = duration

    segments = cached.get("segments", [])
    filtered_segments = []
    for seg in segments:
        if seg["end"] >= start_seconds and seg["start"] <= end_seconds:
            filtered_segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
            })

    result = {
        "filename": filename,
        "cached": True,
        "backend": cached.get("backend", "unknown"),
        "model": cached.get("model", "unknown"),
        "language": cached.get("language", "en"),
        "window": {"start": start_seconds, "end": end_seconds},
        "segments": filtered_segments,
        "words": None,
    }

    if word_level:
        words = []
        for seg in segments:
            for w in seg.get("words", []):
                if w["end"] >= start_seconds and w["start"] <= end_seconds:
                    words.append(w)
        result["words"] = words

    if debug_writer.is_active(debug):
        d = debug_writer.get_debug_dir(filename, "get_audio_transcript")
        debug_writer.save_metadata(d, {"tool": "get_audio_transcript", "filename": filename, "result": result})

    return [TextContent(type="text", text=json.dumps(result, indent=2))]


tool_def(
    Tool(
        name="get_audio_transcript",
        description=(
            "Returns a time-aligned transcript of the video's audio. First call "
            "extracts and transcribes audio (cached for subsequent calls). Uses Groq "
            "API if GROQ_API_KEY is set, otherwise local Whisper."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "start_seconds": {"type": "number", "description": "Start of window (null = beginning)"},
                "end_seconds": {"type": "number", "description": "End of window (null = end)"},
                "word_level": {"type": "boolean", "default": False, "description": "Include word-level timestamps"},
                "debug": {"type": "boolean", "default": False},
            },
            "required": ["filename"],
        },
    ),
    _get_audio_transcript,
)
