"""Naming conventions shared by pages and step definitions."""
import re
from typing import Dict, Set

ELEMENT_PREFIX: Dict[str, str] = {
    # Text Inputs
    "field": "fld",
    "input": "fld",
    "textbox": "fld",
    # Buttons & Clickables
    "button": "btn",
    "link": "lnk",
    # Selects / Dropdowns
    "drop-down": "drp",
    "dropdown": "drp",
    "select": "drp",
    # Toggles
    "checkbox": "chk",
    "radio": "rdo",
    "radio-button": "rdo",
    # Static text & labels
    "label": "lbl",
    "text": "lbl",
    # UI Containers & Navigation
    "tab": "tab",
    "icon": "icn",
}

VALID_PREFIXES: Set[str] = set(ELEMENT_PREFIX.values())
ETYPE_PATTERN: str = "|".join(re.escape(t) for t in sorted(ELEMENT_PREFIX, key=len, reverse=True))


def normalize(key: str) -> str:
    """Case/underscore/hyphen-insensitive form used for matching."""
    return re.sub(r"[\s_\-]+", "", key).lower()


def key_for(label: str, element_type: str) -> str:
    """('Submit', 'button') -> 'btn_submit'"""
    prefix = ELEMENT_PREFIX.get(element_type.strip().lower())
    if prefix is None:
        raise KeyError(f"Unknown element type '{element_type}'. Known: {sorted(ELEMENT_PREFIX)}")
    words = re.findall(r"[A-Za-z0-9]+", label)
    if not words:
        raise ValueError(f"Invalid label '{label}': must contain alphanumeric characters")
    return f"{prefix}_{'_'.join(w.lower() for w in words)}"


def etype_regex() -> str:
    """Regex that matches only known element types."""
    return ETYPE_PATTERN
