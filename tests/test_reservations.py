from treaty_checker.reservations import articles_mentioned as am, split_reservations

assert am("obligation under article 16 to prevent") == {16}
assert am("implementing articles 10-14 and 16, the United States") == {10, 11, 12, 13, 14, 16}
assert am("provisions of articles 1 through 16 of the Convention are not self-executing") == set(range(1, 17))
assert am("it does not consider itself bound by Article 30 (1), but reserves") == {30}
assert am("pursuant to article 30 (2) the United States declares") == {30}
assert am("articles 10, 11, 12 and 13 shall apply") == {10, 11, 12, 13}
assert am("Article 14(3)(d) and article 19") == {14, 19}
assert am("paragraphs 1, 2 and 3 of article 20 of the Convention") == {20}
assert am("article 5, paragraph 1, of the fact") == {5}  # a paragraph number is not an article
assert am("The Fifth, Eighth and Fourteenth Amendments") == set()
assert am("articles 14 to 16") == {14, 15, 16}
rel, oth = split_reservations(
    ["about article 16", "about article 30", "not self-executing under articles 1 through 16"], 16)
assert rel == ["about article 16", "not self-executing under articles 1 through 16"]
assert oth == ["about article 30"]
print("reservations: ok")