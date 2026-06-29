"""StudyConfig — pydantic schema for the study runner."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StudyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    description: str = ""
    languages: list[str] = Field(min_length=1)
    tokenizers: list[str] = Field(min_length=1)
    corpora: list[str] = Field(default_factory=lambda: ["flores"], min_length=1)
    baseline_language: str = "eng"
    n_sentences: int | None = Field(default=None, gt=0)
    split: Literal["dev", "devtest"] = "dev"
    n_bootstrap: int = Field(default=1000, ge=100, le=10000)
    rng_seed: int = 42
    windows: list[int] = Field(default_factory=lambda: [4096, 8192, 32768, 131072])
    prices_snapshot: str = "_defaults/prices_2026-06.yaml"
    fx_snapshot: str = "_defaults/fx_2026-06.yaml"
    output_dir: str = "runs/{name}"

    @model_validator(mode="after")
    def _validate_baseline(self) -> StudyConfig:
        if self.baseline_language not in self.languages:
            raise ValueError(
                f"baseline_language '{self.baseline_language}' must appear in languages {self.languages}"
            )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> StudyConfig:
        text = Path(path).read_text("utf-8")
        raw = yaml.safe_load(text)
        return cls.model_validate(raw)

    def resolve_output_dir(self) -> Path:
        return Path(self.output_dir.format(name=self.name))
