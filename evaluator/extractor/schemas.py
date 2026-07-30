from dataclasses import dataclass, field


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