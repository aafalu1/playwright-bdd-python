"""Custom framework exceptions with detailed, actionable error messages."""
from typing import List, Optional


class FrameworkError(Exception):
    """Base exception for all framework errors."""
    pass


class ElementRegistrationError(FrameworkError):
    """Raised when an element definition violates conventions (prefix, duplicate key, etc.)."""
    pass


class ElementNotFoundError(FrameworkError):
    """Raised when an element key is not found in the current Page Object."""

    def __init__(
        self,
        requested_key: str,
        page_name: str,
        available_keys: List[str],
        suggestion: Optional[str] = None,
    ) -> None:
        self.requested_key = requested_key
        self.page_name = page_name
        self.available_keys = available_keys
        self.suggestion = suggestion

        msg = (
            f"\n"
            f"❌ [Element Not Found] Key '{requested_key}' is not registered in page '{page_name}'.\n"
            f"   📋 Available registered elements:\n"
            f"      {', '.join(sorted(available_keys)) if available_keys else '(none)'}\n"
        )
        if suggestion:
            msg += f"   💡 Did you mean: '{suggestion}'?\n"
        msg += f"   🔍 Check {page_name}.elements dictionary for spelling or prefix mismatch."
        super().__init__(msg)


class FrameResolutionError(FrameworkError):
    """Raised when an iframe or nested frame cannot be resolved."""

    def __init__(
        self,
        element_key: str,
        page_name: str,
        frame_chain: tuple,
        details: str,
    ) -> None:
        msg = (
            f"\n"
            f"❌ [Frame Resolution Error] Failed to resolve iframe hierarchy for '{element_key}' in '{page_name}'.\n"
            f"   🖼️  Frame chain (outermost -> innermost): {list(frame_chain)}\n"
            f"   ⚠️  Details: {details}\n"
            f"   💡 Verify that all parent and child iframes are loaded and visible in the DOM."
        )
        super().__init__(msg)


class PageNotFoundError(FrameworkError):
    """Raised when PageFactory cannot locate a requested Page Object."""

    def __init__(self, requested_name: str, expected_module: str, available_pages: List[str]) -> None:
        msg = (
            f"\n"
            f"❌ [Page Not Found] Could not find Page Object for '{requested_name}'.\n"
            f"   📁 Expected module: '{expected_module}'\n"
            f"   📋 Registered pages: {', '.join(sorted(available_pages)) if available_pages else '(none)'}\n"
            f"   💡 Ensure the page file exists or register it explicitly via @register_page('{requested_name}')."
        )
        super().__init__(msg)
