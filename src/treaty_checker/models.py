from dataclasses import dataclass, field


@dataclass(frozen=True)
class Clause:
    # Required: every clause must have these
    id: str
    treaty: str
    article: str
    text: str
    source_url: str

    # Optional: position inside the article
    paragraph: str | None = None
    subparagraph: str | None = None

    # Optional: links and provenance
    parent_id: str | None = None
    verified: bool = False

    @property
    def citation(self) -> str:
        cite = f"{self.treaty}, Article {self.article}"
        if self.paragraph:
            cite += f"({self.paragraph})"
            if self.subparagraph:
                cite += f"({self.subparagraph})"
        return cite


@dataclass(frozen=True)
class Ratification:
    country: str
    treaty: str
    status: str                  # ratified / acceded / succeeded / signed
    source_url: str
    retrieved_on: str            # date you looked it up, YYYY-MM-DD
    date: str | None = None      # date of ratification/accession, YYYY-MM-DD
    reservations: list[str] = field(default_factory=list)


if __name__ == "__main__":
    c = Clause(
        id="ICCPR-14-3-b",
        treaty="ICCPR",
        article="14",
        paragraph="3",
        subparagraph="b",
        text="(placeholder)",
        source_url="https://example.org",
        parent_id="ICCPR-14-3",
    )
    print(c)
    print(c.verified)
    print(c.citation)