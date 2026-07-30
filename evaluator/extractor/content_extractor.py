from bs4 import BeautifulSoup

from .schemas import (
    Heading,
    Image,
    Link,
    WebsiteContent,
)


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
        )

        paragraphs = ContentExtractor._extract_paragraphs(soup)

        links = ContentExtractor._extract_links(soup)

        images = ContentExtractor._extract_images(soup)

        plain_text = ContentExtractor._extract_plain_text(soup)

        return WebsiteContent(
            url=url,
            title=title,
            meta_description=meta_description,
            headings=headings,
            paragraphs=paragraphs,
            links=links,
            images=images,
            plain_text=plain_text,
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