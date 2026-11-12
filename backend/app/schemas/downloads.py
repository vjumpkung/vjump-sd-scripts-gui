"""Download API schemas and catalog models."""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class DownloadRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=200)


class DownloadFile(BaseModel):
    url: str
    # Relative POSIX path inside the workspace, e.g. models/vae/ae.safetensors.
    path: str
    size_bytes: int = Field(gt=0)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "huggingface.co"
            or parsed.netloc.lower() != "huggingface.co"
            or "?" in value
            or "#" in value
        ):
            raise ValueError("Download URL must use HTTPS on huggingface.co")
        return value

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if (
            not value
            or any(character in value for character in ("\\", ":", "\0"))
            or any(segment in {"", ".", ".."} for segment in value.split("/"))
        ):
            raise ValueError("Download path must be a relative POSIX path")
        return value


class DownloadModel(BaseModel):
    id: str
    name: str
    family: str
    gated: bool = False
    files: list[DownloadFile] = Field(min_length=1)

    @property
    def size_bytes(self) -> int:
        return sum(file.size_bytes for file in self.files)

    @model_validator(mode="after")
    def validate_unique_paths(self) -> DownloadModel:
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("Download paths must be unique within a model")
        return self
