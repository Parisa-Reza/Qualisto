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

        Args:
            url: URL of the webpage to render.

        Returns:
            HTML representing the DOM after JavaScript execution.

        Raises:
            RuntimeError: If Playwright cannot render the page.
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