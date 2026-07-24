"""GUI-neutral width estimation and stable responsive row planning."""


def estimated_button_width(text: str, minimum: int = 118) -> int:
    longest = max((len(line) for line in str(text).splitlines()), default=0)
    return max(minimum, longest * 8 + 34)


def wrap_widths(available: int, widths, gap: int = 6):
    limit = max(1, int(available))
    rows = []
    current = []
    used = 0
    for index, width in enumerate(widths):
        requested = min(limit, max(1, int(width)))
        addition = requested if not current else gap + requested
        if current and used + addition > limit:
            rows.append(tuple(current))
            current = []
            used = 0
            addition = requested
        current.append(index)
        used += addition
    if current:
        rows.append(tuple(current))
    return tuple(rows)
