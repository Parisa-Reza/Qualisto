"""
Render a webpage with Playwright and return its final DOM HTML.

Playwright is responsible only for browser rendering and JavaScript
execution. BeautifulSoup continues to parse the resulting HTML in
the existing extraction layer.
"""

from __future__ import annotations
import logging
from playwright.sync_api import sync_playwright


logger = logging.getLogger(__name__)

class PlaywrightRenderer:
    """Render a single webpage and return its final DOM HTML."""

    def __init__(
        self,
        *,
        timeout: int = 30_000,
    ) -> None:
        self.timeout = timeout

    def render(self, url: str) -> str:
        """
        Render the supplied URL and return the final DOM HTML.
        """

        logger.info(
            "Starting Playwright rendering | url=%s",
            url,
        )

        try:
            with sync_playwright() as playwright:

                browser = playwright.chromium.launch(
                    headless=True,
                )

                try:
                    page = browser.new_page()

                    page.set_default_timeout(
                        self.timeout,
                    )

                    page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=self.timeout,
                    )

                    self._inject_computed_hero_backgrounds(page)
                    html = page.content()

                    logger.info(
                        "Playwright rendering completed | "
                        "url=%s | html_length=%d",
                        url,
                        len(html),
                    )

                    return html

                finally:
                    browser.close()

        except Exception as exc:

            logger.exception(
                "Playwright rendering failed | url=%s",
                url,
            )

            raise RuntimeError(
                f"Failed to render webpage with Playwright: {exc}"
            ) from exc

    def render_property_type_tabs(self, url: str):
        """
        Click every property-type tab and collect only the property
        cards belonging to the currently active tab view.
        """

        tab_results = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=120000,
                )

                page.wait_for_timeout(2000)

                tabs = page.locator(
                    ".tab-component__options"
                )

                for index in range(tabs.count()):

                    tab = tabs.nth(index)

                    tab_name = tab.locator(
                        ".tab-component__button"
                    ).inner_text().strip()

                    if not tab_name:
                        continue

                    logger.info(
                        "Clicking property type tab | tab=%s",
                        tab_name,
                    )

                    tab.click()

                    page.wait_for_timeout(500)

                
                    active_view = page.locator(
                        ".tab-component__views > .tab-component__view.active"
                    )

                    if active_view.count() == 0:
                        logger.warning(
                            "No active property-type view found | tab=%s",
                            tab_name,
                        )

                        tab_results.append(
                            {
                                "tab_name": tab_name,
                                "property_types": [],
                                "card_count": 0,
                            }
                        )

                        continue

                    cards = active_view.locator(
                        ".sp-property-card[data-type]"
                    )

                    property_types = []

                    for card_index in range(cards.count()):

                        property_type = cards.nth(
                            card_index
                        ).get_attribute(
                            "data-type"
                        )

                        if property_type:
                            property_types.append(
                                property_type.strip()
                            )

                    logger.info(
                        "Property type tab collected | "
                        "tab=%s | cards=%d | property_types=%s",
                        tab_name,
                        len(property_types),
                        property_types,
                    )

                    tab_results.append(
                        {
                            "tab_name": tab_name,
                            "property_types": property_types,
                            "card_count": len(property_types),
                        }
                    )

                self._inject_computed_hero_backgrounds(page)

                return page.content(), tab_results

            finally:
                browser.close()

    def _inject_computed_hero_backgrounds(self, page) -> None:
        """
        Copy computed background-image values from hero elements
        into their inline style attributes.

        This allows page.content() to preserve dynamically
        computed hero background images for BeautifulSoup.
        """

        page.evaluate(
            """
            () => {

                const heroElements = document.querySelectorAll(
                    '[id*="hero" i], [class*="hero" i]'
                );

                heroElements.forEach((element) => {

                    const computedStyle =
                        window.getComputedStyle(element);

                    const backgroundImage =
                        computedStyle.backgroundImage;

                    if (
                        backgroundImage &&
                        backgroundImage !== "none"
                    ) {

                        const currentStyle =
                            element.getAttribute("style") || "";

                        if (
                            !currentStyle.includes(
                                "background-image"
                            )
                        ) {

                            element.style.backgroundImage =
                                backgroundImage;
                        }
                    }
                });
            }
            """
        )
