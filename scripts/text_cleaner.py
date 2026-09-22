import re

NUMBER = re.compile(r"^\(?\d{1,3}(,\d{3})*(\.\d+)?\)?$")
FOOTNOTE = re.compile(r"\(\d\)$")
DASHES = {"—", "–", "-"}


def is_value(token):
    return bool(NUMBER.match(token)) or token in DASHES


def to_number(token):
    if token in DASHES:
        return None
    negative = token.startswith("(")
    digits = token.strip("()").replace(",", "")
    number = float(digits)
    return -number if negative else number


def parse_line(line):
    tokens = line.split()
    label_words = []
    i = 0
    while i < len(tokens) and tokens[i] != "$" and not is_value(tokens[i]):
        label_words.append(tokens[i])
        i += 1
    label = FOOTNOTE.sub("", " ".join(label_words)).strip()

    values = []
    dollar = False
    for token in tokens[i:]:
        if token == "$":
            dollar = True
        elif is_value(token):
            raw = "$ " + token if dollar else token
            values.append((raw, to_number(token)))
            dollar = False
        if len(values) == 3:
            break
    return label, values


if __name__ == "__main__":
    tests = [
        "Rare earth concentrate $ 41,992 $ 144,363 $ 252,468 $ (102,371) $ (108,105) (71) % (43) %",
        "Intersegment eliminations(1) (2,789) — — (2,789) — N/M N/M",
        "REO Sales Volume (MTs) 8,922 32,703 36,837 (23,781) (4,134) (73) % (11) %",
        "Price protection agreement income $ 51,016 $ — $ — $ 51,016 $ — N/M N/M",
        "Rare earth concentrate(1)",
        "(in thousands, except percentages) 2025 2024 2023 2024 2023 2024 2023",
    ]
    for line in tests:
        print(parse_line(line))