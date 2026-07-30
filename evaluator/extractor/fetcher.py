import requests


class HTMLFetcher:
    """
    Responsible for downloading the raw HTML of a webpage.
    """

    DEFAULT_TIMEOUT = 15

    @staticmethod
    def fetch(url: str) -> str:
        """
        Download webpage HTML.

        Args:
            url: Website URL

        Returns:
            Raw HTML as string

        Raises:
            requests.HTTPError
            requests.Timeout
            requests.RequestException
        """

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/138.0 Safari/537.36"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=HTMLFetcher.DEFAULT_TIMEOUT,
        )

        response.raise_for_status()

        return response.text