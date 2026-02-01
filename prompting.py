from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "portable_guide requires PyYAML to load prompts. Install with: pip install pyyaml"
    ) from e


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user_template: str


class PromptLoader:
    """
    Minimal prompt loader (YAML) with language fallback.

    Prompt file structure:
      prompts/{lang}/{agent_name}.yaml
        system: |-
          ...
        user_template: |-
          ...
    """

    LANGUAGE_FALLBACKS: dict[str, list[str]] = {
        "en": ["en"],
        "zh": ["zh", "en"],
        "cn": ["zh", "en"],
    }

    def __init__(self, prompts_dir: Path):
        self.prompts_dir = Path(prompts_dir)
        self._cache: dict[tuple[str, str], PromptBundle] = {}

    def load(self, agent_name: str, language: str = "en") -> PromptBundle:
        lang = (language or "en").lower()
        cache_key = (agent_name, lang)
        if cache_key in self._cache:
            return self._cache[cache_key]

        candidates = self.LANGUAGE_FALLBACKS.get(lang, [lang, "en"])
        last_error: Exception | None = None

        for candidate_lang in candidates:
            path = self.prompts_dir / candidate_lang / f"{agent_name}.yaml"
            if not path.exists():
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                bundle = self._coerce_bundle(data)
                self._cache[cache_key] = bundle
                return bundle
            except Exception as e:  # pragma: no cover
                last_error = e
                continue

        msg = (
            f"Prompt file not found for agent={agent_name}, language={language} "
            f"(dir={self.prompts_dir})"
        )
        if last_error:
            msg += f" (last_error={last_error})"
        raise FileNotFoundError(msg)

    def _coerce_bundle(self, data: dict[str, Any]) -> PromptBundle:
        system = data.get("system", "")
        user_template = data.get("user_template", "")
        if not isinstance(system, str) or not isinstance(user_template, str):
            raise ValueError("Prompt YAML must contain string fields: system, user_template")
        return PromptBundle(system=system, user_template=user_template)

