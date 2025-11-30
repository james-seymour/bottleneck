def parse_postcode(postcodes: str) -> list[int]:
    if postcodes == "-":
        return []

    return [int(p) for p in postcodes.split(" / ") if p.isdigit()]


def parse_suburbs(suburbs: str | None) -> list[str]:
    if suburbs is None or suburbs == "-":
        return []

    return [s.strip() for s in suburbs.split(" / ")]
