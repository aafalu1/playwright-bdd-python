from typing import Any, Dict, Union
from pages.base_page import BasePage
from pages.element import Css, Element, Role
from pages.page_factory import register_page


@register_page("Navigation", "Nav")
class NavigationPage(BasePage):
    elements: Dict[str, Union[str, Dict[str, Any], Element]] = {
        # Parent section/title link
        "lnk_menu_title": Role("link", name="{title}"),

        # Dynamic child submenu item
        "lnk_submenu_item": Role("link", name="{item}"),

        # Generic table or menu action link
        "lnk_action_item": Css("a[role='menuitem']:has-text('{item}')"),
    }
