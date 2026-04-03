import time
import requests
from bs4 import BeautifulSoup


class BaseScraper:
    """
    Shared HTTP session with rate limiting and a descriptive User-Agent.
    All scrapers inherit from this class.
    """

    def __init__(self, delay_seconds: float = 2.0):
        self.delay = delay_seconds
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SKZDatabaseBot/1.0 (personal research; non-commercial)"
        })

    def get(self, url: str) -> requests.Response:
        time.sleep(self.delay)
        response = self.session.get(url, timeout=15)
        response.raise_for_status()
        return response

    def get_soup(self, url: str) -> BeautifulSoup:
        response = self.get(url)
        return BeautifulSoup(response.text, "lxml")
