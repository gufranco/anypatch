from __future__ import annotations

LIMIT = 1 << 30


class ImageSizeError(ValueError):
    pass


def check(size: int, *, source: int) -> None:
    ceiling = max(LIMIT, source)
    if size > ceiling:
        raise ImageSizeError(
            f"the patch claims a {size:,}-byte result, past the {ceiling:,}-byte ceiling"
        )
