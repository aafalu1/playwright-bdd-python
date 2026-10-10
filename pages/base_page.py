import difflib
from typing import Any, Dict, Optional, Tuple, Union
from playwright.sync_api import FrameLocator, Locator, Page

from pages.element import Element, _SafeDict
from pages.naming import VALID_PREFIXES, key_for, normalize
from utils.exceptions import ElementNotFoundError, ElementRegistrationError, FrameResolutionError


class BasePage:
    """Responsibility: resolve registered elements into frame-aware Locators and handle navigation."""

    url_path: str = ""
    elements: Dict[str, Union[str, Dict[str, Any], Element]] = {}
    _compiled_index: Dict[str, Tuple[str, Element]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Pre-indexes and validates elements up the MRO at class declaration time."""
        super().__init_subclass__(**kwargs)
        cls._compiled_index = {}

        # Merge elements up the class hierarchy (MRO) to inherit base elements
        merged_elements: Dict[str, Union[str, Dict[str, Any], Element]] = {}
        for base in reversed(cls.__mro__):
            if hasattr(base, "elements") and isinstance(base.elements, dict):
                merged_elements.update(base.elements)

        for key, spec in merged_elements.items():
            prefix = key.split("_", 1)[0].lower()
            if "_" not in key or prefix not in VALID_PREFIXES:
                raise ElementRegistrationError(
                    f"{cls.__name__}: key '{key}' must start with one of "
                    f"{sorted(p + '_' for p in VALID_PREFIXES)}"
                )
            norm = normalize(key)
            if norm in cls._compiled_index:
                raise ElementRegistrationError(f"{cls.__name__}: duplicate key '{key}'")
            cls._compiled_index[norm] = (key, Element.coerce(spec))

    def __init__(self, page: Page, base_url: str = "") -> None:
        self.page: Page = page
        self.base_url: str = base_url

    def navigate(self, path: Optional[str] = None) -> None:
        """Navigate to page URL using base_url and url_path."""
        target_path = path if path is not None else self.url_path
        if target_path and (
            target_path.startswith("http://")
            or target_path.startswith("https://")
            or target_path.startswith("file://")
        ):
            url = target_path
        elif self.base_url and target_path:
            url = f"{self.base_url.rstrip('/')}/{target_path.lstrip('/')}"
        else:
            url = target_path or self.base_url
        if url:
            self.page.goto(url)

    def locator(self, key: str, **fmt: Any) -> Locator:
        """Resolve a registered key to a Locator, chaining frame_locator() as needed."""
        norm_key = normalize(key)
        entry = self._compiled_index.get(norm_key)
        if entry is None:
            available = [k for k, _ in self._compiled_index.values()]
            matches = difflib.get_close_matches(key, available, n=1, cutoff=0.4)
            suggestion = matches[0] if matches else None
            raise ElementNotFoundError(
                requested_key=key,
                page_name=type(self).__name__,
                available_keys=available,
                suggestion=suggestion,
            )
        _, el = entry

        # Resolve nested frame hierarchy
        root: Union[Page, FrameLocator] = self.page
        safe_map = _SafeDict(fmt) if fmt else None

        try:
            for frame_selector in el.frames:
                formatted_frame = (
                    frame_selector.format_map(safe_map)
                    if safe_map and isinstance(frame_selector, str)
                    else frame_selector
                )
                root = root.frame_locator(formatted_frame)
            return el.resolve(root, fmt)
        except Exception as e:
            if el.frames:
                raise FrameResolutionError(
                    element_key=key,
                    page_name=type(self).__name__,
                    frame_chain=el.frames,
                    details=str(e),
                ) from e
            raise

    def element(self, label: str, element_type: str, **fmt: Any) -> Locator:
        """('Submit', 'button') -> locator for btn_submit"""
        return self.locator(key_for(label, element_type), **fmt)
