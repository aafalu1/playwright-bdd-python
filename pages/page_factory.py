import importlib
import importlib.util
import re
from typing import Callable, Dict, List, Type
from playwright.sync_api import Page
from pages.base_page import BasePage
from utils.exceptions import PageNotFoundError

_PAGE_REGISTRY: Dict[str, Type[BasePage]] = {}


def register_page(*names: str) -> Callable[[Type[BasePage]], Type[BasePage]]:
    """Decorator to register a Page class under one or more custom names/aliases.
    
    Example:
        @register_page("Checkout", "Add to Cart", "Shopping Cart")
        class AddToCartPage(BasePage):
            ...
    """
    def decorator(cls: Type[BasePage]) -> Type[BasePage]:
        for name in names:
            clean = re.sub(r"\s+page$", "", name.strip(), flags=re.IGNORECASE).lower()
            _PAGE_REGISTRY[clean] = cls
        return cls
    return decorator


def _words(name: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+", name)


def _strip_page_suffix(name: str) -> str:
    return re.sub(r"\s+page$", "", name.strip(), flags=re.IGNORECASE)


class PageFactory:
    """Dynamically resolves and caches page objects per scenario."""

    def __init__(self, playwright_page: Page, base_url: str = "") -> None:
        self._page: Page = playwright_page
        self._base_url: str = base_url
        self._cache: Dict[str, BasePage] = {}

    def get(self, page_name: str) -> BasePage:
        stripped = _strip_page_suffix(page_name).strip()
        lookup_key = stripped.lower()

        if lookup_key in self._cache:
            return self._cache[lookup_key]

        # 1. Check explicit registry first
        if lookup_key in _PAGE_REGISTRY:
            cls = _PAGE_REGISTRY[lookup_key]
            instance = cls(self._page, base_url=self._base_url)
            self._cache[lookup_key] = instance
            return instance

        # 2. Convention fallback: "Add to Cart" -> pages.add_to_cart_page.AddToCartPage
        words = _words(stripped)
        if not words:
            raise ValueError(f"Invalid page name: '{page_name}'")
        snake = "_".join(w.lower() for w in words)
        module_name = f"pages.{snake}_page"
        class_name = "".join(w[:1].upper() + w[1:] for w in words) + "Page"

        spec = importlib.util.find_spec(module_name)
        if spec is None:
            raise PageNotFoundError(
                requested_name=page_name,
                expected_module=f"{module_name}.{class_name}",
                available_pages=list(_PAGE_REGISTRY.keys()),
            )

        module = importlib.import_module(module_name)
        try:
            cls = getattr(module, class_name)
        except AttributeError:
            raise PageNotFoundError(
                requested_name=page_name,
                expected_module=f"{module_name}.{class_name}",
                available_pages=list(_PAGE_REGISTRY.keys()),
            ) from None

        instance = cls(self._page, base_url=self._base_url)
        self._cache[lookup_key] = instance
        return instance
