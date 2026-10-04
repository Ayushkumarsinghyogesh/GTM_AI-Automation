"""config/gtm.yaml loader. Ek hi source of truth: rubric, tiers, brand, rules."""
import os
from functools import lru_cache
from pathlib import Path

import yaml

_DEFAULT = Path(__file__).resolve().parents[2] / "config" / "gtm.yaml"


@lru_cache
def cfg() -> dict:
    path = Path(os.environ.get("GTM_CONFIG_PATH", _DEFAULT))
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def signal_defs() -> dict:
    return cfg()["signals"]


def classifiable_keys() -> list[str]:
    return [k for k, v in signal_defs().items() if v.get("classifiable")]
