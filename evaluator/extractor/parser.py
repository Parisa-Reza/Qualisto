from bs4 import BeautifulSoup


class HTMLParser:
    """
    Responsible for converting raw HTML into a BeautifulSoup object.
    """

    @staticmethod
    def parse(html: str) -> BeautifulSoup:
        """
        Parse raw HTML.

        Args:
            html: Raw HTML string

        Returns:
            BeautifulSoup object
        """

        if not html:
            raise ValueError("HTML content cannot be empty.")

        return BeautifulSoup(html, "html.parser")