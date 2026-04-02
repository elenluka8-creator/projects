"""Prompt template loader for the translation stage.

Loads YAML prompt definitions from the prompts/ directory.
Each prompt file must contain: prompt_id, prompt_version, target_stage,
model_family_compatibility, system, user_template.

Template substitution uses Python str.format_map() — placeholders are {name}.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict

import yaml


@dataclass(frozen=True)
class PromptTemplate:
    """Loaded and parsed prompt definition."""

    prompt_id: str
    prompt_version: str
    target_stage: str
    model_family_compatibility: str
    system: str
    user_template: str

    def render_user(self, **kwargs: Any) -> str:
        """Render the user_template with the given substitution variables."""
        return self.user_template.format_map(kwargs)


# Module-level cache so prompts are read from disk only once per process.
_cache: Dict[str, PromptTemplate] = {}


def load_prompt(relative_path: str, prompts_root: str = "prompts") -> PromptTemplate:
    """Load a prompt YAML file relative to prompts_root.

    Args:
        relative_path: Path relative to prompts_root, e.g. "translation/translate_batch.yaml"
        prompts_root:  Root directory for prompt files (defaults to "prompts/").
                       Can be overridden in tests to point to a temp directory.

    Returns:
        PromptTemplate with all fields populated.

    Raises:
        FileNotFoundError: If the prompt file does not exist.
        ValueError: If required fields are missing from the YAML.
    """
    cache_key = f"{prompts_root}::{relative_path}"
    if cache_key in _cache:
        return _cache[cache_key]

    full_path = os.path.join(prompts_root, relative_path)
    if not os.path.exists(full_path):
        raise FileNotFoundError(f"Prompt file not found: {full_path}")

    with open(full_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    required = ("prompt_id", "prompt_version", "target_stage",
                "model_family_compatibility", "system", "user_template")
    missing = [f for f in required if f not in data]
    if missing:
        raise ValueError(
            f"Prompt file {full_path} is missing required fields: {missing}"
        )

    template = PromptTemplate(
        prompt_id=str(data["prompt_id"]),
        prompt_version=str(data["prompt_version"]),
        target_stage=str(data["target_stage"]),
        model_family_compatibility=str(data["model_family_compatibility"]),
        system=str(data["system"]),
        user_template=str(data["user_template"]),
    )
    _cache[cache_key] = template
    return template


def clear_cache() -> None:
    """Clear the module-level prompt cache. Used in tests."""
    _cache.clear()
