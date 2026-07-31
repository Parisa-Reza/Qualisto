from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class Heading:
    h1: list[str] = field(default_factory=list)
    h2: list[str] = field(default_factory=list)
    h3: list[str] = field(default_factory=list)
    h4: list[str] = field(default_factory=list)
    h5: list[str] = field(default_factory=list)
    h6: list[str] = field(default_factory=list)


@dataclass
class Link:
    text: str
    href: str


@dataclass
class Image:
    src: str
    alt: str

@dataclass(slots=True)
class PropertyCard:
    title: str
    city: str
    country: str
    country_code: str
    location: str
    property_type: str

@dataclass
class WebsiteContent:
    url: str
    title: str
    meta_description: str

    headings: Heading

    paragraphs: list[str]

    links: list[Link]

    images: list[Image]

    plain_text: str

    soup: BeautifulSoup
    
    property_cards: list[PropertyCard] = field(default_factory=list)