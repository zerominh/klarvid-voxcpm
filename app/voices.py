from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_ID_RE = re.compile(r"^[a-f0-9]{12}$")


class VoiceNotFound(Exception):
    pass


class InvalidVoiceId(Exception):
    pass


@dataclass
class Voice:
    id: str
    name: str | None
    prompt_text: str
    audio_path: str
    created_at: str

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "prompt_text": self.prompt_text,
            "created_at": self.created_at,
        }


class VoiceStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _dir(self, voice_id: str) -> Path:
        if not _ID_RE.fullmatch(voice_id):
            raise InvalidVoiceId(voice_id)
        return self.root / voice_id

    def create(
        self,
        *,
        prompt_text: str,
        audio: bytes,
        suffix: str,
        name: str | None,
    ) -> Voice:
        voice_id = uuid.uuid4().hex[:12]
        folder = self.root / voice_id
        folder.mkdir(parents=True, exist_ok=False)
        ext = suffix if suffix.startswith(".") else f".{suffix}"
        if ext.lower() not in {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".wave"}:
            ext = ".wav"
        audio_path = folder / f"reference{ext}"
        audio_path.write_bytes(audio)
        created_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "id": voice_id,
            "name": name,
            "prompt_text": prompt_text,
            "audio_file": audio_path.name,
            "created_at": created_at,
        }
        (folder / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return Voice(
            id=voice_id,
            name=name,
            prompt_text=prompt_text,
            audio_path=str(audio_path),
            created_at=created_at,
        )

    def get(self, voice_id: str) -> Voice:
        folder = self._dir(voice_id)
        meta_path = folder / "meta.json"
        if not meta_path.is_file():
            raise VoiceNotFound(voice_id)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        audio_path = folder / meta["audio_file"]
        if not audio_path.is_file():
            raise VoiceNotFound(voice_id)
        return Voice(
            id=meta["id"],
            name=meta.get("name"),
            prompt_text=meta["prompt_text"],
            audio_path=str(audio_path),
            created_at=meta["created_at"],
        )

    def list(self) -> list[Voice]:
        voices: list[Voice] = []
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or not (folder / "meta.json").is_file():
                continue
            try:
                voices.append(self.get(folder.name))
            except (VoiceNotFound, InvalidVoiceId):
                continue
        return voices

    def delete(self, voice_id: str) -> None:
        folder = self._dir(voice_id)
        if not (folder / "meta.json").is_file():
            raise VoiceNotFound(voice_id)
        shutil.rmtree(folder)
