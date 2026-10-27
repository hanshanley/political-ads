from __future__ import annotations

import hashlib
import json
import re
import subprocess
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path

from political_ads.cli import read_json, write_json
from political_ads.schema import digest


@lru_cache(maxsize=1)
def speech_model(root: Path, offline: bool):
    from faster_whisper import WhisperModel
    from faster_whisper.utils import download_model

    model_path = download_model(
        "base", cache_dir=str(root / "data/models"), local_files_only=offline
    )
    return (
        WhisperModel(model_path, device="cpu", compute_type="int8", cpu_threads=4),
        Path(model_path).name,
    )


def recognize_video(root: Path, body: bytes, offline: bool = False) -> tuple[str, dict, dict]:
    media_hash = hashlib.sha256(body).hexdigest()
    directory = root / "data/media/snap-videos"
    directory.mkdir(parents=True, exist_ok=True)
    video = directory / (media_hash + ".mp4")
    if not video.exists():
        video.write_bytes(body)
    source = Path(__file__).with_name("video_ocr.swift")
    ocr_path = directory / (media_hash + "." + digest(source.read_text())[:12] + ".ocr.json")
    try:
        if not ocr_path.exists():
            executable = directory.parent / ("vision-video-ocr-" + digest(source.read_text())[:16])
            if not executable.exists():
                subprocess.run(
                    ["swiftc", str(source), "-o", str(executable)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                )
            try:
                result = subprocess.run(
                    [str(executable), str(video)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=600,
                )
                ocr = json.loads(result.stdout)
            except subprocess.CalledProcessError:
                decoded = directory / (media_hash + ".vision-h264.mp4")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-nostdin",
                        "-y",
                        "-i",
                        str(video),
                        "-map",
                        "0:v:0",
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "18",
                        "-pix_fmt",
                        "yuv420p",
                        "-fps_mode",
                        "passthrough",
                        str(decoded),
                    ],
                    capture_output=True,
                    check=True,
                    timeout=600,
                )
                result = subprocess.run(
                    [str(executable), str(decoded)],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=600,
                )
                ocr = json.loads(result.stdout)
                ocr["video_decode_fallback"] = {
                    "method": "FFmpeg local H.264 conversion after native frame decode failed",
                    "original_sha256": media_hash,
                    "derived_sha256": hashlib.sha256(decoded.read_bytes()).hexdigest(),
                    "frame_rate": "passthrough; original presentation cadence",
                }
            write_json(ocr_path, ocr)
        ocr = read_json(ocr_path, {})
        asr_path = directory / (
            media_hash + ".whisper-base-v1-" + version("faster-whisper") + ".json"
        )
        if not asr_path.exists():
            import av
            import numpy as np

            with av.open(str(video)) as container:
                has_audio = bool(container.streams.audio)
            speech = dict(
                engine="faster-whisper " + version("faster-whisper"),
                model="Systran/faster-whisper-base",
                model_revision=None,
                language="unknown",
                language_probability=0,
                has_audio=has_audio,
                settings=dict(
                    beam_size=5,
                    temperature=0,
                    condition_on_previous_text=False,
                    vad_filter=True,
                    word_timestamps=True,
                ),
                segments=[],
            )
            if has_audio:
                audio = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-i",
                        str(video),
                        "-f",
                        "s16le",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        "-",
                    ],
                    capture_output=True,
                    check=True,
                    timeout=120,
                ).stdout
                model, revision = speech_model(root, offline)
                segments, info, alignment_error = transcribe_with_alignment_fallback(
                    model,
                    np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768,
                    speech["settings"],
                )
                speech.update(
                    word_alignment_error=alignment_error,
                    model_revision=revision,
                    language=info.language,
                    language_probability=info.language_probability,
                    segments=[
                        dict(
                            text=s.text.strip(),
                            start_seconds=s.start,
                            end_seconds=s.end,
                            avg_logprob=s.avg_logprob,
                            no_speech_probability=s.no_speech_prob,
                            words=[
                                dict(
                                    text=w.word,
                                    start_seconds=w.start,
                                    end_seconds=w.end,
                                    probability=w.probability,
                                )
                                for w in s.words or []
                            ],
                        )
                        for s in segments
                        if s.text.strip()
                    ],
                )
            write_json(asr_path, speech)
        return media_hash, ocr, read_json(asr_path, {})
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, IndexError) as error:
        detail = getattr(error, "stderr", None)
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        raise ValueError(
            f"Local video extraction failed for {media_hash}: {detail or error}"
        ) from error


def transcribe_with_alignment_fallback(model, waveform, settings):
    try:
        segments, info = model.transcribe(waveform, **settings)
        return list(segments), info, None
    except IndexError as error:
        settings["word_timestamps"] = False
        segments, info = model.transcribe(waveform, **settings)
        return list(segments), info, str(error)


def normalized_words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.casefold()))


def video_segments(ocr: dict, speech: dict, media_hash: str) -> list[dict]:
    segments = [
        s
        | dict(
            kind="local_asr",
            voice="unreviewed",
            media_hash=media_hash,
            extraction_engine=speech["engine"],
            model=speech["model"],
            model_revision=speech["model_revision"],
        )
        for s in speech["segments"]
    ]
    spoken = " " + normalized_words(" ".join(s["text"] for s in segments)) + " "
    lines = {}
    rejected = []
    for frame in sorted(ocr["frames"], key=lambda frame: frame["seconds"]):
        for line in frame["lines"]:
            if line["confidence"] < 0.8:
                rejected.append(line | {"seconds": frame["seconds"]})
                continue
            key = normalized_words(line["text"])
            if not key:
                continue
            entry = lines.setdefault(key, {"text": line["text"], "observations": []})
            entry["observations"].append(line | {"seconds": frame["seconds"]})
    duplicates = []
    for key, entry in lines.items():
        if " " + key + " " in spoken:
            duplicates.append(entry)
            continue
        first = entry["observations"][0]
        segments.append(
            dict(
                text=entry["text"],
                kind="video_ocr",
                voice="unreviewed",
                start_seconds=first["seconds"],
                end_seconds=first["seconds"],
                confidence=first["confidence"],
                image_bounds=first["bounds"],
                media_hash=media_hash,
                extraction_engine=ocr["engine"],
                coordinate_system=ocr["coordinate_system"],
                frame_observations=entry["observations"],
            )
        )
    if segments:
        segments[0]["speech_detection"] = {
            key: speech.get(key)
            for key in (
                "language",
                "language_probability",
                "has_audio",
                "settings",
                "word_alignment_error",
            )
        }
        if ocr.get("video_decode_fallback"):
            segments[0]["video_decode_fallback"] = ocr["video_decode_fallback"]
        segments[0]["excluded_low_confidence_ocr_observations"] = rejected
        segments[0]["speech_duplicate_ocr_observations"] = duplicates
        segments[0]["video_sampling"] = {
            key: ocr[key] for key in ("duration_seconds", "sample_interval_seconds")
        }
    return segments
