import logging
import re
from bs4 import BeautifulSoup

from .schemas import (
    Heading,
    Image,
    Link,
    PropertyCard,
    WebsiteContent
    
)

logger = logging.getLogger(__name__)


class ContentExtractor:
    """
    Extract structured information from a BeautifulSoup document.
    """

    @staticmethod
    def extract(url: str, soup: BeautifulSoup) -> WebsiteContent:

        title = ContentExtractor._extract_title(soup)
        meta_description = ContentExtractor._extract_meta_description(soup)

        headings = Heading(
            h1=ContentExtractor._extract_h1(soup),
            h2=ContentExtractor._extract_h2(soup),
            h3=ContentExtractor._extract_h3(soup),
            h4=ContentExtractor._extract_h4(soup),
            h5=ContentExtractor._extract_h5(soup),
            h6=ContentExtractor._extract_h6(soup),
        )

        paragraphs = ContentExtractor._extract_paragraphs(soup)

        links = ContentExtractor._extract_links(soup)

        images = ContentExtractor._extract_images(soup)

        plain_text = ContentExtractor._extract_plain_text(soup)

        hero_images = ContentExtractor._extract_hero_images(soup)

        property_cards = ContentExtractor._extract_property_cards(soup)

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
            plain_text=plain_text,
            soup=soup,
        )

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:

        if soup.title and soup.title.string:
            return soup.title.string.strip()

        return ""

    @staticmethod
    def _extract_meta_description(soup: BeautifulSoup) -> str:

        meta = soup.find("meta", attrs={"name": "description"})

        if meta:
            return meta.get("content", "").strip()

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

    _BG_URL_RE = re.compile(
        r"""background-image\s*:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)""",
        re.IGNORECASE,
    )

    # @staticmethod
    # def _extract_hero_images(soup) -> list[Image]:
    #     """Extract hero images from both image sliders and CSS backgrounds.

    #     FIX: The previous version only matched the single hardcoded id
    #     "#img-bg-hero-section". Any other hero markup (different id,
    #     or a class-based hero section) silently produced zero hero
    #     images with no warning. This version:
    #       1. Still checks the Presto slider (unchanged).
    #       2. Matches ANY element whose id or class contains "hero"
    #          (case-insensitive), not just one literal id.
    #       3. Checks that element's inline style AND any <style> block
    #          whose selector (by id or class) references it.
    #       4. Logs a warning if hero-like markup exists but no image
    #          could be extracted, so this doesn't fail silently again.
    #     """

    #     hero_images = []
    #     seen = set()

    #     def _add(src: str, alt: str = "") -> None:
    #         src = (src or "").strip()
    #         if not src or src in seen:
    #             return
    #         seen.add(src)
    #         hero_images.append(Image(src=src, alt=(alt or "").strip()))

    #     # ----------------------------------------------------------
    #     # 1. Presto slider hero images (unchanged).
    #     # ----------------------------------------------------------
    #     slider = soup.select_one(".presto-slider")

    #     if slider:
    #         for img in slider.select(
    #             ".presto-slider-wrap .slider-items .slider-item img"
    #         ):
    #             _add(img.get("src", ""), img.get("alt", ""))

    #     # ----------------------------------------------------------
    #     # 2 & 3. Any hero-like element (id or class contains "hero"),
    #     # covering both inline style="background-image:url(...)" and
    #     # a <style> block that targets that element's id/class.
    #     # ----------------------------------------------------------
    #     hero_elements = soup.select('[id*="hero" i], [class*="hero" i]')

    #     for element in hero_elements:
    #         inline_style = element.get("style", "")
    #         for src in ContentExtractor._BG_URL_RE.findall(inline_style):
    #             _add(src)

    #     if hero_elements:
    #         style_text = " ".join(
    #             tag.get_text(" ", strip=False) for tag in soup.find_all("style")
    #         )

    #         selectors = set()
    #         for element in hero_elements:
    #             el_id = element.get("id", "")
    #             if el_id:
    #                 selectors.add(f"#{el_id}")
    #             for cls in element.get("class", []) or []:
    #                 selectors.add(f".{cls}")

    #         for selector in selectors:
    #             if not selector or selector not in style_text:
    #                 continue

    #             # Only pull background-image URLs out of this selector's
    #             # own rule block, so unrelated rules sharing the same
    #             # <style> tag aren't picked up by accident.
    #             block_pattern = re.compile(
    #                 re.escape(selector) + r"\s*\{([^}]*)\}",
    #                 re.IGNORECASE,
    #             )
    #             for block in block_pattern.findall(style_text):
    #                 for src in ContentExtractor._BG_URL_RE.findall(block):
    #                     _add(src)

    #     if not hero_images and hero_elements:
    #         logger.warning(
    #             "Hero-like elements found but no hero image could be extracted | "
    #             "ids=%s | classes=%s",
    #             [el.get("id", "") for el in hero_elements if el.get("id")],
    #             [el.get("class", "") for el in hero_elements if el.get("class")],
    #         )

    #     return hero_images

    # _PROPERTY_CARD_SELECTORS = (
    #     ".pres__property-tiles.sp-property-card",
    #     ".sp-property-card",
    #     ".pres__property-tiles",
    #     "[data-property_city]",
    # )

    _BG_URL_RE = re.compile(
        r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""",
        re.IGNORECASE,
    )

    @staticmethod
    def _extract_hero_images(
        soup: BeautifulSoup,
    ) -> list[Image]:
        """
        Extract hero images from the final rendered DOM.

        Supports:

        1. Presto image sliders.
        2. Hero elements using inline background-image.
        3. Hero elements whose background-image was injected by
           Playwright from the browser's computed CSS.

        The Playwright renderer should place the computed
        background-image into the element's style attribute.
        BeautifulSoup then extracts that URL normally.
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

        # ----------------------------------------------------------
        # 1. PRESTO SLIDER
        # ----------------------------------------------------------

        slider = soup.select_one(
            ".presto-slider"
        )

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

        # ----------------------------------------------------------
        # 2. HERO ELEMENTS
        # ----------------------------------------------------------

        hero_elements = soup.select(
            '[id*="hero" i], '
            '[class*="hero" i]'
        )

        for element in hero_elements:

            # ------------------------------------------------------
            # 2A. INLINE STYLE
            # ------------------------------------------------------

            style = element.get(
                "style",
                "",
            )

            for src in ContentExtractor._BG_URL_RE.findall(
                style
            ):

                add_image(src)

        # ----------------------------------------------------------
        # 3. FALLBACK: <STYLE> BLOCKS
        # ----------------------------------------------------------

        style_text = " ".join(
            tag.get_text(
                " ",
                strip=False,
            )
            for tag in soup.find_all("style")
        )

        for element in hero_elements:

            element_id = element.get(
                "id",
                "",
            )

            if element_id:

                selector = (
                    f"#{element_id}"
                )

                pattern = re.compile(
                    re.escape(selector)
                    + r"\s*\{([^}]*)\}",
                    re.IGNORECASE,
                )

                for block in pattern.findall(
                    style_text
                ):

                    for src in ContentExtractor._BG_URL_RE.findall(
                        block
                    ):

                        add_image(src)

            for class_name in (
                element.get("class", [])
                or []
            ):

                selector = (
                    f".{class_name}"
                )

                pattern = re.compile(
                    re.escape(selector)
                    + r"\s*\{([^}]*)\}",
                    re.IGNORECASE,
                )

                for block in pattern.findall(
                    style_text
                ):

                    for src in ContentExtractor._BG_URL_RE.findall(
                        block
                    ):

                        add_image(src)

        # ----------------------------------------------------------
        # 4. LOGGING
        # ----------------------------------------------------------

        if hero_images:

            logger.info(
                "Hero images extracted | count=%d | sources=%s",
                len(hero_images),
                [
                    image.src
                    for image in hero_images
                ],
            )

        elif hero_elements:

            logger.warning(
                "Hero elements found but no hero images extracted | "
                "count=%d",
                len(hero_elements),
            )

        else:

            logger.info(
                "Hero image extraction: no hero elements found."
            )

        return hero_images

    _PROPERTY_CARD_SELECTORS = (
        ".pres__property-tiles.sp-property-card",
        ".sp-property-card",
        ".pres__property-tiles",
        "[data-property_city]",
    )
    @staticmethod
    def _extract_property_cards(soup: BeautifulSoup) -> list[PropertyCard]:
        """Extract property cards, tolerant of markup drift.

        FIX: The previous version required BOTH classes
        (".pres__property-tiles.sp-property-card") on the same tag. If
        the real markup only has one, or the classes moved to a parent/
        child element, the selector matched nothing and property-card
        validation was silently skipped (always scoring 100). This
        version tries the exact original selector first, then falls
        back progressively, and logs a warning if it still finds
        nothing despite property-card-like markup being present.
        """

        cards = []
        matched_elements = []
        seen_ids = set()
        used_fallback = False

        # Union results across all selectors (not "stop at first match"),
        # so a page with mixed/inconsistent card markup doesn't silently
        # drop cards that only satisfy a looser selector.
        for selector in ContentExtractor._PROPERTY_CARD_SELECTORS:
            found = soup.select(selector)
            if found and selector != ContentExtractor._PROPERTY_CARD_SELECTORS[0]:
                used_fallback = True
            for element in found:
                if id(element) in seen_ids:
                    continue
                seen_ids.add(id(element))
                matched_elements.append(element)

        if used_fallback:
            logger.warning(
                "Some property cards matched only via fallback selector | total_matched=%d",
                len(matched_elements),
            )

        for card in matched_elements:
            title = card.select_one(".property-title a")
            property_type = card.select_one(".property-type")

            cards.append(
                PropertyCard(
                    title=title.get_text(" ", strip=True) if title else "",
                    city=card.get("data-property_city", ""),
                    country=card.get("data-property_country", ""),
                    country_code=card.get("data-property_country_code", ""),
                    location=card.get("data-search_string", ""),
                    property_type=property_type.get_text(" ", strip=True)
                    if property_type else "",
                )
            )

        if not cards:
            possible = soup.select(
                '[class*="property-card" i], [class*="property-tile" i]'
            )
            if possible:
                logger.warning(
                    "No property cards extracted but property-card-like elements exist | "
                    "count=%d | sample_classes=%s",
                    len(possible),
                    [el.get("class", "") for el in possible[:5]],
                )

        return cards
# import logging
# import re
# from bs4 import BeautifulSoup

# from .schemas import (
#     Heading,
#     Image,
#     Link,
#     PropertyCard,
#     WebsiteContent
    
# )

# logger = logging.getLogger(__name__)


# class ContentExtractor:
#     """
#     Extract structured information from a BeautifulSoup document.
#     """

#     @staticmethod
#     def extract(url: str, soup: BeautifulSoup) -> WebsiteContent:

#         title = ContentExtractor._extract_title(soup)
#         meta_description = ContentExtractor._extract_meta_description(soup)

#         headings = Heading(
#             h1=ContentExtractor._extract_h1(soup),
#             h2=ContentExtractor._extract_h2(soup),
#             h3=ContentExtractor._extract_h3(soup),
#             h4=ContentExtractor._extract_h4(soup),
#             h5=ContentExtractor._extract_h5(soup),
#             h6=ContentExtractor._extract_h6(soup),
#         )

#         paragraphs = ContentExtractor._extract_paragraphs(soup)

#         links = ContentExtractor._extract_links(soup)

#         images = ContentExtractor._extract_images(soup)

#         plain_text = ContentExtractor._extract_plain_text(soup)

#         hero_images = ContentExtractor._extract_hero_images(soup)

#         property_cards = ContentExtractor._extract_property_cards(soup)

#         return WebsiteContent(
#             url=url,
#             title=title,
#             meta_description=meta_description,
#             headings=headings,
#             paragraphs=paragraphs,
#             links=links,
#             images=images,
#             hero_images=hero_images,
#             property_cards=property_cards,
#             plain_text=plain_text,
#             soup=soup,
#         )

#     @staticmethod
#     def _extract_title(soup: BeautifulSoup) -> str:

#         if soup.title and soup.title.string:
#             return soup.title.string.strip()

#         return ""

#     @staticmethod
#     def _extract_meta_description(soup: BeautifulSoup) -> str:

#         meta = soup.find("meta", attrs={"name": "description"})

#         if meta:
#             return meta.get("content", "").strip()

#         return ""

#     @staticmethod
#     def _extract_h1(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h1")
#             if tag.get_text(strip=True)
#         ]

#     @staticmethod
#     def _extract_h2(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h2")
#             if tag.get_text(strip=True)
#         ]
    
#     @staticmethod
#     def _extract_h3(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h3")
#             if tag.get_text(strip=True)
#         ]


#     @staticmethod
#     def _extract_h4(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h4")
#             if tag.get_text(strip=True)
#         ]


#     @staticmethod
#     def _extract_h5(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h5")
#             if tag.get_text(strip=True)
#         ]


#     @staticmethod
#     def _extract_h6(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(strip=True)
#             for tag in soup.find_all("h6")
#             if tag.get_text(strip=True)
#         ]

#     @staticmethod
#     def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:

#         return [
#             tag.get_text(" ", strip=True)
#             for tag in soup.find_all("p")
#             if tag.get_text(strip=True)
#         ]

#     @staticmethod
#     def _extract_links(soup: BeautifulSoup) -> list[Link]:

#         links = []

#         for tag in soup.find_all("a", href=True):

#             links.append(
#                 Link(
#                     text=tag.get_text(strip=True),
#                     href=tag["href"],
#                 )
#             )

#         return links

#     @staticmethod
#     def _extract_images(soup: BeautifulSoup) -> list[Image]:

#         images = []

#         for tag in soup.find_all("img"):

#             images.append(
#                 Image(
#                     src=tag.get("src", ""),
#                     alt=tag.get("alt", ""),
#                 )
#             )

#         return images

#     @staticmethod
#     def _extract_plain_text(soup: BeautifulSoup) -> str:

#         return soup.get_text(" ", strip=True)

#     _BG_URL_RE = re.compile(
#         r"""background-image\s*:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)""",
#         re.IGNORECASE,
#     )

#     @staticmethod
#     def _extract_hero_images(soup) -> list[Image]:
#         """Extract hero images from both image sliders and CSS backgrounds.

#         FIX: The previous version only matched the single hardcoded id
#         "#img-bg-hero-section". Any other hero markup (different id,
#         or a class-based hero section) silently produced zero hero
#         images with no warning. This version:
#           1. Still checks the Presto slider (unchanged).
#           2. Matches ANY element whose id or class contains "hero"
#              (case-insensitive), not just one literal id.
#           3. Checks that element's inline style AND any <style> block
#              whose selector (by id or class) references it.
#           4. Logs a warning if hero-like markup exists but no image
#              could be extracted, so this doesn't fail silently again.
#         """

#         hero_images = []
#         seen = set()

#         def _add(src: str, alt: str = "") -> None:
#             src = (src or "").strip()
#             if not src or src in seen:
#                 return
#             seen.add(src)
#             hero_images.append(Image(src=src, alt=(alt or "").strip()))

#         # ----------------------------------------------------------
#         # 1. Presto slider hero images (unchanged).
#         # ----------------------------------------------------------
#         slider = soup.select_one(".presto-slider")

#         if slider:
#             for img in slider.select(
#                 ".presto-slider-wrap .slider-items .slider-item img"
#             ):
#                 _add(img.get("src", ""), img.get("alt", ""))

#         # ----------------------------------------------------------
#         # 2 & 3. Any hero-like element (id or class contains "hero"),
#         # covering both inline style="background-image:url(...)" and
#         # a <style> block that targets that element's id/class.
#         # ----------------------------------------------------------
#         hero_elements = soup.select('[id*="hero" i], [class*="hero" i]')

#         for element in hero_elements:
#             inline_style = element.get("style", "")
#             for src in ContentExtractor._BG_URL_RE.findall(inline_style):
#                 _add(src)

#         if hero_elements:
#             style_text = " ".join(
#                 tag.get_text(" ", strip=False) for tag in soup.find_all("style")
#             )

#             selectors = set()
#             for element in hero_elements:
#                 el_id = element.get("id", "")
#                 if el_id:
#                     selectors.add(f"#{el_id}")
#                 for cls in element.get("class", []) or []:
#                     selectors.add(f".{cls}")

#             for selector in selectors:
#                 if not selector or selector not in style_text:
#                     continue

#                 # Only pull background-image URLs out of this selector's
#                 # own rule block, so unrelated rules sharing the same
#                 # <style> tag aren't picked up by accident.
#                 block_pattern = re.compile(
#                     re.escape(selector) + r"\s*\{([^}]*)\}",
#                     re.IGNORECASE,
#                 )
#                 for block in block_pattern.findall(style_text):
#                     for src in ContentExtractor._BG_URL_RE.findall(block):
#                         _add(src)

#         if not hero_images and hero_elements:
#             logger.warning(
#                 "Hero-like elements found but no hero image could be extracted | "
#                 "ids=%s | classes=%s",
#                 [el.get("id", "") for el in hero_elements if el.get("id")],
#                 [el.get("class", "") for el in hero_elements if el.get("class")],
#             )

#         return hero_images

#     _PROPERTY_CARD_SELECTORS = (
#         ".pres__property-tiles.sp-property-card",
#         ".sp-property-card",
#         ".pres__property-tiles",
#         "[data-property_city]",
#     )

#     @staticmethod
#     def _extract_property_cards(soup: BeautifulSoup) -> list[PropertyCard]:
#         """Extract property cards, tolerant of markup drift.

#         FIX: The previous version required BOTH classes
#         (".pres__property-tiles.sp-property-card") on the same tag. If
#         the real markup only has one, or the classes moved to a parent/
#         child element, the selector matched nothing and property-card
#         validation was silently skipped (always scoring 100). This
#         version tries the exact original selector first, then falls
#         back progressively, and logs a warning if it still finds
#         nothing despite property-card-like markup being present.
#         """

#         cards = []
#         matched_elements = []
#         seen_ids = set()
#         used_fallback = False

#         # Union results across all selectors (not "stop at first match"),
#         # so a page with mixed/inconsistent card markup doesn't silently
#         # drop cards that only satisfy a looser selector.
#         for selector in ContentExtractor._PROPERTY_CARD_SELECTORS:
#             found = soup.select(selector)
#             if found and selector != ContentExtractor._PROPERTY_CARD_SELECTORS[0]:
#                 used_fallback = True
#             for element in found:
#                 if id(element) in seen_ids:
#                     continue
#                 seen_ids.add(id(element))
#                 matched_elements.append(element)

#         if used_fallback:
#             logger.warning(
#                 "Some property cards matched only via fallback selector | total_matched=%d",
#                 len(matched_elements),
#             )

#         for card in matched_elements:
#             title = card.select_one(".property-title a")
#             property_type = card.select_one(".property-type")

#             cards.append(
#                 PropertyCard(
#                     title=title.get_text(" ", strip=True) if title else "",
#                     city=card.get("data-property_city", ""),
#                     country=card.get("data-property_country", ""),
#                     country_code=card.get("data-property_country_code", ""),
#                     location=card.get("data-search_string", ""),
#                     property_type=property_type.get_text(" ", strip=True)
#                     if property_type else "",
#                 )
#             )

#         if not cards:
#             possible = soup.select(
#                 '[class*="property-card" i], [class*="property-tile" i]'
#             )
#             if possible:
#                 logger.warning(
#                     "No property cards extracted but property-card-like elements exist | "
#                     "count=%d | sample_classes=%s",
#                     len(possible),
#                     [el.get("class", "") for el in possible[:5]],
#                 )

#         return cards


# # import re
# # from bs4 import BeautifulSoup

# # from .schemas import (
# #     Heading,
# #     Image,
# #     Link,
# #     PropertyCard,
# #     WebsiteContent
    
# # )


# # class ContentExtractor:
# #     """
# #     Extract structured information from a BeautifulSoup document.
# #     """

# #     @staticmethod
# #     def extract(url: str, soup: BeautifulSoup) -> WebsiteContent:

# #         title = ContentExtractor._extract_title(soup)
# #         meta_description = ContentExtractor._extract_meta_description(soup)

# #         headings = Heading(
# #             h1=ContentExtractor._extract_h1(soup),
# #             h2=ContentExtractor._extract_h2(soup),
# #             h3=ContentExtractor._extract_h3(soup),
# #             h4=ContentExtractor._extract_h4(soup),
# #             h5=ContentExtractor._extract_h5(soup),
# #             h6=ContentExtractor._extract_h6(soup),
# #         )

# #         paragraphs = ContentExtractor._extract_paragraphs(soup)

# #         links = ContentExtractor._extract_links(soup)

# #         images = ContentExtractor._extract_images(soup)

# #         plain_text = ContentExtractor._extract_plain_text(soup)

# #         hero_images = ContentExtractor._extract_hero_images(soup)

# #         property_cards = ContentExtractor._extract_property_cards(soup)

# #         return WebsiteContent(
# #             url=url,
# #             title=title,
# #             meta_description=meta_description,
# #             headings=headings,
# #             paragraphs=paragraphs,
# #             links=links,
# #             images=images,
# #             hero_images=hero_images,
# #             property_cards=property_cards,
# #             plain_text=plain_text,
# #             soup=soup,
# #         )

# #     @staticmethod
# #     def _extract_title(soup: BeautifulSoup) -> str:

# #         if soup.title and soup.title.string:
# #             return soup.title.string.strip()

# #         return ""

# #     @staticmethod
# #     def _extract_meta_description(soup: BeautifulSoup) -> str:

# #         meta = soup.find("meta", attrs={"name": "description"})

# #         if meta:
# #             return meta.get("content", "").strip()

# #         return ""

# #     @staticmethod
# #     def _extract_h1(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h1")
# #             if tag.get_text(strip=True)
# #         ]

# #     @staticmethod
# #     def _extract_h2(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h2")
# #             if tag.get_text(strip=True)
# #         ]
    
# #     @staticmethod
# #     def _extract_h3(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h3")
# #             if tag.get_text(strip=True)
# #         ]


# #     @staticmethod
# #     def _extract_h4(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h4")
# #             if tag.get_text(strip=True)
# #         ]


# #     @staticmethod
# #     def _extract_h5(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h5")
# #             if tag.get_text(strip=True)
# #         ]


# #     @staticmethod
# #     def _extract_h6(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(strip=True)
# #             for tag in soup.find_all("h6")
# #             if tag.get_text(strip=True)
# #         ]

# #     @staticmethod
# #     def _extract_paragraphs(soup: BeautifulSoup) -> list[str]:

# #         return [
# #             tag.get_text(" ", strip=True)
# #             for tag in soup.find_all("p")
# #             if tag.get_text(strip=True)
# #         ]

# #     @staticmethod
# #     def _extract_links(soup: BeautifulSoup) -> list[Link]:

# #         links = []

# #         for tag in soup.find_all("a", href=True):

# #             links.append(
# #                 Link(
# #                     text=tag.get_text(strip=True),
# #                     href=tag["href"],
# #                 )
# #             )

# #         return links

# #     @staticmethod
# #     def _extract_images(soup: BeautifulSoup) -> list[Image]:

# #         images = []

# #         for tag in soup.find_all("img"):

# #             images.append(
# #                 Image(
# #                     src=tag.get("src", ""),
# #                     alt=tag.get("alt", ""),
# #                 )
# #             )

# #         return images

# #     @staticmethod
# #     def _extract_plain_text(soup: BeautifulSoup) -> str:

# #         return soup.get_text(" ", strip=True)

# #     # def _extract_hero_images(soup: BeautifulSoup) -> list[Image]:
# #     #     """Extract only images belonging to the Presto hero slider."""

# #     #     hero_images = []

# #     #     slider = soup.select_one(".presto-slider")

# #     #     if not slider:
# #     #         return hero_images

# #     #     for img in slider.select(
# #     #         ".presto-slider-wrap .slider-items .slider-item img"
# #     #     ):
# #     #         src = img.get("src", "").strip()

# #     #         if not src:
# #     #             continue

# #     #         hero_images.append(
# #     #             Image(
# #     #                 src=src,
# #     #                 alt=img.get("alt", "").strip(),
# #     #             )
# #     #         )

# #     #     return hero_images

# #     # UPDATE: supports both slider images and CSS background hero images

# #     @staticmethod
# #     def _extract_hero_images(soup) -> list[Image]:
# #         """Extract hero images from both image sliders and CSS backgrounds."""

# #         hero_images = []

# #         # ----------------------------------------------------------
# #         # UPDATE:
# #         # Existing Presto slider hero images.
# #         # ----------------------------------------------------------

# #         slider = soup.select_one(".presto-slider")

# #         if slider:

# #             for img in slider.select(
# #                 ".presto-slider-wrap .slider-items .slider-item img"
# #             ):
# #                 src = img.get("src", "").strip()

# #                 if not src:
# #                     continue

# #                 hero_images.append(
# #                     Image(
# #                         src=src,
# #                         alt=img.get("alt", "").strip(),
# #                     )
# #                 )

# #         # ----------------------------------------------------------
# #         # UPDATE:
# #         # CSS background-image hero section.
# #         #
# #         # Example:
# #         #
# #         # #img-bg-hero-section {
# #         #     background-image: url(...);
# #         # }
# #         # ----------------------------------------------------------

# #         hero_section = soup.select_one(
# #             "#img-bg-hero-section"
# #         )

# #         if hero_section:

# #             style = hero_section.get(
# #                 "style",
# #                 "",
# #             )

# #             background_urls = re.findall(
# #                 r"""background-image\s*:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)""",
# #                 style,
# #                 flags=re.IGNORECASE,
# #             )

# #             for src in background_urls:

# #                 src = src.strip()

# #                 if not src:
# #                     continue

# #                 hero_images.append(
# #                     Image(
# #                         src=src,
# #                         alt="",
# #                     )
# #                 )

# #         # ----------------------------------------------------------
# #         # UPDATE:
# #         # Also inspect <style> blocks because the background-image
# #         # may be defined in CSS rather than inline style.
# #         # ----------------------------------------------------------

# #         if hero_section:

# #             hero_id = hero_section.get(
# #                 "id",
# #                 "",
# #             )

# #             for style_tag in soup.find_all("style"):

# #                 css = style_tag.get_text(
# #                     " ",
# #                     strip=False,
# #                 )

# #                 if (
# #                     hero_id
# #                     and f"#{hero_id}" in css
# #                 ):

# #                     background_urls = re.findall(
# #                         r"""background-image\s*:\s*url\(\s*['"]?([^'")]+)['"]?\s*\)""",
# #                         css,
# #                         flags=re.IGNORECASE,
# #                     )

# #                     for src in background_urls:

# #                         src = src.strip()

# #                         if not src:
# #                             continue

# #                         hero_images.append(
# #                             Image(
# #                                 src=src,
# #                                 alt="",
# #                             )
# #                         )

# #         # ----------------------------------------------------------
# #         # UPDATE:
# #         # Remove duplicate hero image URLs.
# #         # ----------------------------------------------------------

# #         unique_images = []
# #         seen = set()

# #         for image in hero_images:

# #             src = image.src.strip()

# #             if not src:
# #                 continue

# #             if src in seen:
# #                 continue

# #             seen.add(src)

# #             unique_images.append(image)

# #         return unique_images


# #     @staticmethod
# #     def _extract_property_cards(soup: BeautifulSoup) -> list[PropertyCard]:
# #         cards = []

# #         for card in soup.select(".pres__property-tiles.sp-property-card"):
# #             title = card.select_one(".property-title a")
# #             property_type = card.select_one(".property-type")

# #             cards.append(
# #                 PropertyCard(
# #                     title=title.get_text(" ", strip=True) if title else "",
# #                     city=card.get("data-property_city", ""),
# #                     country=card.get("data-property_country", ""),
# #                     country_code=card.get("data-property_country_code", ""),
# #                     location=card.get("data-search_string", ""),
# #                     property_type=property_type.get_text(" ", strip=True)
# #                     if property_type else "",
# #                 )
# #             )

# #         return cards