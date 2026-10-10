"""Element descriptors: HOW to find an element + WHICH iframes contain it.

Factories (Css, XPath, Role, Label, Placeholder, Text, AltText, Title, TestId)
map 1:1 onto Playwright's built-in locators.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from playwright.sync_api import FrameLocator, Locator, Page

# kind -> Playwright method on Page / FrameLocator
_GET_BY: Dict[str, str] = {
    "role": "get_by_role",
    "label": "get_by_label",
    "text": "get_by_text",
    "placeholder": "get_by_placeholder",
    "alt_text": "get_by_alt_text",
    "title": "get_by_title",
    "test_id": "get_by_test_id",
}
KINDS = {"css", "xpath", *_GET_BY}


class _SafeDict(dict):
    """Prevents KeyError on unsupplied format tokens (e.g. CSS pseudo-classes or XPath braces)."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


@dataclass(frozen=True)
class Element:
    value: str                                           # selector, role, label text, test id ...
    by: str = "css"                                      # one of KINDS
    options: Dict[str, Any] = field(default_factory=dict)  # e.g. name=, exact=, checked=
    frames: Tuple[str, ...] = ()                         # iframe chain, outermost first
    nth: Optional[int] = None                            # pick one match (0-based, -1 = last)
    has_text: Optional[str] = None                       # .filter(has_text=...)

    def __post_init__(self) -> None:
        if self.by not in KINDS:
            raise ValueError(f"Unknown locator kind '{self.by}'. Use one of {sorted(KINDS)}")
        if not isinstance(self.value, str) or not self.value.strip():
            raise ValueError("Element.value must be a non-empty string")
        frames = (self.frames,) if isinstance(self.frames, str) else tuple(self.frames or ())
        if not all(isinstance(f, str) and f.strip() for f in frames):
            raise ValueError("Element.frames must be non-empty selector strings")
        object.__setattr__(self, "frames", frames)

    def resolve(self, root: Union[Page, FrameLocator], fmt: Optional[Dict[str, Any]] = None) -> Locator:
        """Resolve against Page or FrameLocator using Playwright's locator methods."""
        safe_map = _SafeDict(fmt) if fmt else None

        def f(v: Any) -> Any:
            return v.format_map(safe_map) if safe_map and isinstance(v, str) else v

        value = f(self.value)
        opts = {k: f(v) for k, v in self.options.items() if v is not None}

        if self.by == "css":
            loc = root.locator(value)
        elif self.by == "xpath":
            loc = root.locator(value if value.startswith("xpath=") else f"xpath={value}")
        else:
            loc = getattr(root, _GET_BY[self.by])(value, **opts)

        if self.has_text is not None:
            loc = loc.filter(has_text=f(self.has_text))
        if self.nth is not None:
            loc = loc.nth(self.nth)
        return loc

    @classmethod
    def coerce(cls, spec: Union[str, Dict[str, Any], "Element"]) -> "Element":
        """Accepts Element | 'css or engine=selector string' | dict."""
        if isinstance(spec, Element):
            return spec
        if isinstance(spec, str):
            return cls(spec)
        if isinstance(spec, dict):
            d = dict(spec)
            frames = d.pop("frames", ())
            nth = d.pop("nth", None)
            has_text = d.pop("has_text", None)
            if "selector" in d:
                return cls(d.pop("selector"), "css", d, frames, nth, has_text)
            return cls(d.pop("value"), d.pop("by", "css"), d, frames, nth, has_text)
        raise TypeError(f"Unsupported element spec: {spec!r}")


def FrameSection(
    frames: Union[str, Sequence[str]],
    elements_dict: Dict[str, Union[str, Dict[str, Any], Element]],
) -> Dict[str, Element]:
    """Prefix a group of elements with a common iframe hierarchy.
    
    Example:
        elements = {
            **FrameSection(["#checkout", "iframe[name='3ds']"], {
                "fld_otp": TestId("otp"),
                "btn_confirm": Role("button", name="Confirm"),
            })
        }
    """
    frame_tuple = (frames,) if isinstance(frames, str) else tuple(frames)
    scoped: Dict[str, Element] = {}
    for key, spec in elements_dict.items():
        el = Element.coerce(spec)
        scoped[key] = Element(
            value=el.value,
            by=el.by,
            options=dict(el.options),
            frames=frame_tuple + el.frames,
            nth=el.nth,
            has_text=el.has_text,
        )
    return scoped


# ---------------- Factories with Type Hints ----------------
def _make(
    by: str,
    value: str,
    frames: Union[str, Sequence[str]],
    nth: Optional[int],
    has_text: Optional[str],
    **options: Any,
) -> Element:
    frame_tuple = (frames,) if isinstance(frames, str) else tuple(frames)
    return Element(
        value=value,
        by=by,
        options={k: v for k, v in options.items() if v is not None},
        frames=frame_tuple,
        nth=nth,
        has_text=has_text,
    )


def Css(selector: str, *, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("css", selector, frames, nth, has_text)


def XPath(expr: str, *, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("xpath", expr, frames, nth, has_text)


def Role(
    role: str,
    *,
    name: Optional[str] = None,
    exact: Optional[bool] = None,
    frames: Union[str, Sequence[str]] = (),
    nth: Optional[int] = None,
    has_text: Optional[str] = None,
    **options: Any,
) -> Element:
    return _make("role", role, frames, nth, has_text, name=name, exact=exact, **options)


def Label(text: str, *, exact: Optional[bool] = None, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("label", text, frames, nth, has_text, exact=exact)


def Placeholder(text: str, *, exact: Optional[bool] = None, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("placeholder", text, frames, nth, has_text, exact=exact)


def Text(text: str, *, exact: Optional[bool] = None, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("text", text, frames, nth, has_text, exact=exact)


def AltText(text: str, *, exact: Optional[bool] = None, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("alt_text", text, frames, nth, has_text, exact=exact)


def Title(text: str, *, exact: Optional[bool] = None, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("title", text, frames, nth, has_text, exact=exact)


def TestId(test_id: str, *, frames: Union[str, Sequence[str]] = (), nth: Optional[int] = None, has_text: Optional[str] = None) -> Element:
    return _make("test_id", test_id, frames, nth, has_text)
