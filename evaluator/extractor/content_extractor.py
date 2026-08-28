import logging
import re

from bs4 import BeautifulSoup

from .schemas import (
    Heading,
    Image,
    Link,
    PropertyCard,
    PropertyTypeTab,
    WebsiteContent,
)


logger = logging.getLogger(__name__)


class ContentExtractor:
    """
    Extract structured information from a BeautifulSoup document.
    """

    _PROPERTY_CARD_SELECTORS = (
        ".pres__property-tiles.sp-property-card",
        ".sp-property-card",
        ".pres__property-tiles",
        "[data-property_city]",
    )

    _BG_URL_RE = re.compile(
        r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""",
        re.IGNORECASE,
    )

    @staticmethod
    def extract(
        url: str,
        soup: BeautifulSoup,
    ) -> WebsiteContent:
        title = ContentExtractor._extract_title(soup)

        meta_description = (
            ContentExtractor._extract_meta_description(soup)
        )

        headings = Heading(
            h1=ContentExtractor._extract_h1(soup),
            h2=ContentExtractor._extract_h2(soup),
            h3=ContentExtractor._extract_h3(soup),
            h4=ContentExtractor._extract_h4(soup),
            h5=ContentExtractor._extract_h5(soup),
            h6=ContentExtractor._extract_h6(soup),
        )

        paragraphs = ContentExtractor._extract_paragraphs(
            soup
        )

        links = ContentExtractor._extract_links(
            soup
        )

        images = ContentExtractor._extract_images(
            soup
        )

        plain_text = ContentExtractor._extract_plain_text(
            soup
        )

        hero_images = ContentExtractor._extract_hero_images(
            soup
        )

        property_cards = (
            ContentExtractor._extract_property_cards(
                soup
            )
        )

        property_type_tabs = (
            ContentExtractor._extract_active_property_type_tab(
                soup
            )
        )

        return WebsiteContent(
            url=url,
            title=title,
            meta_description=meta_description,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            images=images,
            hero_images=hero_images,
            property_cards=property_cards,
            property_type_tabs=property_type_tabs,
            plain_text=plain_text,
            soup=soup,
        )

    @staticmethod
    def _extract_title(
        soup: BeautifulSoup,
    ) -> str:

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        return ""

    @staticmethod
    def _extract_meta_description(
        soup: BeautifulSoup,
    ) -> str:

        meta = soup.find(
            "meta",
            attrs={"name": "description"},
        )

        if meta:
            return meta.get(
                "content",
                "",
            ).strip()

        return ""

    @staticmethod
    def _extract_h1(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h1")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_h2(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h2")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_h3(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h3")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_h4(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h4")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_h5(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h5")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_h6(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(strip=True)
            for tag in soup.find_all("h6")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:
        return [
            tag.get_text(" ", strip=True)
            for tag in soup.find_all("p")
            if tag.get_text(strip=True)
        ]

    @staticmethod
    def _extract_links(soup: BeautifulSoup) -> list[Link]:
        links = []
        for tag in soup.find_all("a", href=True):
            links.append(
                Link(
                    text=tag.get_text(strip=True),
                    href=tag["href"],
                )
            )
        return links

    @staticmethod
    def _extract_images(soup: BeautifulSoup) -> list[Image]:
        images = []
        for tag in soup.find_all("img"):
            images.append(
                Image(
                    src=tag.get("src", ""),
                    alt=tag.get("alt", ""),
                )
            )
        return images

    @staticmethod
    def _extract_plain_text(soup: BeautifulSoup) -> str:
        return soup.get_text(" ", strip=True)

  
    # HERO IMAGE EXTRACTION

    @staticmethod
    def _extract_hero_images(
        soup: BeautifulSoup,
    ) -> list[Image]:
        """
        Extract hero images from the rendered DOM.

        Supports:
        1. Presto image sliders.
        2. Hero elements with inline background-image (primary path,
           since Playwright injects the computed background-image
           into the inline style attribute before this ever runs).
        3. Hero elements whose background-image exists in a <style>
           block, tolerating pseudo-elements (::before/::after),
           compound selectors, and combinators between the
           id/class token and the opening '{'.
        """

        hero_images = []
        seen = set()

        def add_image(
            src: str,
            alt: str = "",
        ) -> None:

            src = (src or "").strip()

            if not src or src in seen:
                return

            seen.add(src)

            hero_images.append(
                Image(
                    src=src,
                    alt=(alt or "").strip(),
                )
            )

        # PRESTO SLIDER

        slider = soup.select_one(".presto-slider")

        if slider:

            for img in slider.select(
                ".presto-slider-wrap "
                ".slider-items "
                ".slider-item img"
            ):

                add_image(
                    img.get("src", ""),
                    img.get("alt", ""),
                )


        # HERO ELEMENTS


        hero_elements = soup.select(
            '[id*="hero" i], '
            '[class*="hero" i]'
        )


        # INLINE BACKGROUND IMAGE


        for element in hero_elements:

            style = element.get("style", "")

            for src in ContentExtractor._BG_URL_RE.findall(style):
                add_image(src)


        # <STYLE> BLOCK BACKGROUND IMAGE


        style_text = " ".join(
            tag.get_text(" ", strip=False)
            for tag in soup.find_all("style")
        )

        for element in hero_elements:

            element_id = element.get("id", "")

            if element_id:

                selector = f"#{element_id}"

                pattern = re.compile(
                    re.escape(selector) + r"[^{}]*\{([^}]*)\}",
                    re.IGNORECASE,
                )

                for block in pattern.findall(style_text):

                    for src in ContentExtractor._BG_URL_RE.findall(
                        block
                    ):
                        add_image(src)

            for class_name in (
                element.get("class", []) or []
            ):

                selector = f".{class_name}"

                pattern = re.compile(
                    re.escape(selector) + r"[^{}]*\{([^}]*)\}",
                    re.IGNORECASE,
                )

                for block in pattern.findall(style_text):

                    for src in ContentExtractor._BG_URL_RE.findall(
                        block
                    ):
                        add_image(src)

        if hero_images:

            logger.info(
                "Hero images extracted | count=%d | sources=%s",
                len(hero_images),
                [image.src for image in hero_images],
            )

        elif hero_elements:

            logger.warning(
                "Hero elements found but no hero images extracted | count=%d",
                len(hero_elements),
            )

        else:

            logger.info(
                "Hero image extraction: no hero elements found."
            )

        return hero_images


    # ACTIVE TAB SCOPING (used ONLY for property-type validation)


    @staticmethod
    def _find_active_tab_view(soup: BeautifulSoup):
        """
        Locate the currently active property-type tab view.

        Real markup looks like:
            <div id="itendar"
                 class="tab-component__views tab-component__view-0 active">

        i.e. a numbered class like 'tab-component__view-0', not the
        literal 'tab-component__view'. We match on a class *token*
        containing 'tab-component__view' together with the exact
        'active' token.
        """

        active_view = soup.select_one(
            '[class*="tab-component__view"][class~="active"]'
        )

        if active_view:
            return active_view

        return soup.select_one(
            ".tab-component__tabviews .tab-component__view.active"
        )

    @staticmethod
    def _extract_active_property_type_tab(
        soup: BeautifulSoup,
    ) -> list[PropertyTypeTab]:
        """
        Property-TYPE validation stays scoped to the active tab
        only. E.g. if the 'Villas' tab is active with 6 tiles, this
        returns exactly those 6 tiles' data-type values, so
        mismatched types (e.g. a 'Hotel' showing up under 'Villas')
        can be flagged.
        """

        active_view = ContentExtractor._find_active_tab_view(soup)

        if not active_view:

            logger.info(
                "Active property-type tab not found."
            )

            return []

        tab_button = soup.select_one(
            ".tab-component__dropdown-button"
        )

        tab_name = ""

        if tab_button:

            tab_name = tab_button.get_text(" ", strip=True)

        if not tab_name:

            active_option = soup.select_one(
                ".tab-component__options.active "
                ".tab-component__button"
            )

            if active_option:

                tab_name = active_option.get_text(" ", strip=True)

        if not tab_name:

            logger.warning(
                "Active property-type view found but active tab name "
                "could not be determined."
            )

            return []

        property_tiles_block = active_view.select_one(
            '[data-block="property-tiles"]'
        )

        if not property_tiles_block:

            logger.warning(
                "Active property-type tab found but "
                '[data-block="property-tiles"] was not found | '
                "tab=%s",
                tab_name,
            )

            return [
                PropertyTypeTab(
                    tab_name=tab_name,
                    property_types=[],
                )
            ]

        property_cards = property_tiles_block.select(
            ".sp-property-card[data-type]"
        )

        property_types = []

        for card in property_cards:

            property_type = card.get("data-type", "").strip()

            if property_type:
                property_types.append(property_type)

        logger.info(
            "Active property-type tab extracted | "
            "tab=%s | cards=%d | property_types=%s",
            tab_name,
            len(property_types),
            property_types,
        )

        return [
            PropertyTypeTab(
                tab_name=tab_name,
                property_types=property_types,
                card_count=len(property_types),
            )
        ]

    @staticmethod
    def _extract_property_cards(
        soup: BeautifulSoup,
    ) -> list[PropertyCard]:
        """
        Extract property cards for LOCATION/destination validation.

        IMPORTANT: This always scans the WHOLE page, across every
        tab — not just the active one. Location validation must
        cover every property tile on the page regardless of which
        tab is currently active, unlike property-TYPE validation
        (which is intentionally scoped to the active tab in
        _extract_active_property_type_tab above).
        """

        cards = []
        matched_elements = []
        seen_ids = set()
        used_fallback = False

        for selector in ContentExtractor._PROPERTY_CARD_SELECTORS:

            found = soup.select(selector)

            if (
                found
                and selector
                != ContentExtractor._PROPERTY_CARD_SELECTORS[0]
            ):
                used_fallback = True

            for element in found:

                element_id = id(element)

                if element_id in seen_ids:
                    continue

                seen_ids.add(element_id)

                matched_elements.append(element)

        if used_fallback:

            logger.warning(
                "Some property cards matched only via fallback selector | "
                "total_matched=%d",
                len(matched_elements),
            )

        for card in matched_elements:

            title = card.select_one(".property-title a")

            property_type = card.get("data-type", "")

            cards.append(
                PropertyCard(
                    title=(
                        title.get_text(" ", strip=True)
                        if title
                        else ""
                    ),
                    city=card.get("data-property_city", ""),
                    country=card.get("data-property_country", ""),
                    country_code=card.get(
                        "data-property_country_code", ""
                    ),
                    location=card.get("data-search_string", ""),
                    property_type=property_type,
                )
            )

        if not cards:

            possible = soup.select(
                '[class*="property-card" i], '
                '[class*="property-tile" i]'
            )

            if possible:

                logger.warning(
                    "No property cards extracted but property-card-like "
                    "elements exist | count=%d",
                    len(possible),
                )

        logger.info(
            "Property cards extracted (whole-page, all tabs) | count=%d",
            len(cards),
        )

        return cards
