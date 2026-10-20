import hashlib
import re

import pytest

from anypatch import api
from anypatch import boundaries_test_support as boundaries
from anypatch.formats import ipswrite
from anypatch.patchio import WRITABLE, Format, PatchError

CASES = {case.name: case for case in boundaries.cases()}
STAR_ROD = boundaries.STAR_ROD
PAIRS = [(name, kind) for name in CASES for kind in sorted(WRITABLE, key=lambda one: one.value)]
REFUSED = {pair: found for pair in PAIRS if (found := boundaries.refused(*pair))}
IPS32_CASES = {
    "ips-past-limit-high-change",
    "ips-shrink-to-limit",
    "xdelta-window-0x1000001",
    *STAR_ROD,
}
BUILT = [pair for pair in PAIRS if pair not in REFUSED]
TINY = ipswrite.Variant("TINY", ipswrite.MAGIC, ipswrite.END, 1, 16)


def _fingerprint(image: bytes) -> tuple[int, str]:
    return len(image), hashlib.sha256(image).hexdigest()


def _replayed(name: str, kind: Format) -> tuple[int, str]:
    case = CASES[name]
    files = api.make(case.source, case.target, kind)
    patch = api.load(
        files[f".{kind.value}"], name=f"{name}.{kind.value}", binding=files.get(".hdr")
    )
    return _fingerprint(api.apply(case.source, [patch]).image)


class TestEveryFormatOnEveryBoundary:
    @pytest.mark.parametrize(("name", "kind"), BUILT, ids=[f"{n}-{k.value}" for n, k in BUILT])
    def test_the_patch_it_writes_rebuilds_the_target(self, name, kind):
        # Arrange
        expected = _fingerprint(CASES[name].target)

        # Act
        result = _replayed(name, kind)

        # Assert
        assert result == expected

    @pytest.mark.parametrize(
        ("name", "kind"), sorted(REFUSED), ids=[f"{n}-{k.value}" for n, k in sorted(REFUSED)]
    )
    def test_a_change_the_format_cannot_hold_is_refused_by_name(self, name, kind):
        # Arrange
        case = CASES[name]

        # Act
        with pytest.raises(PatchError) as raised:
            api.make(case.source, case.target, kind)

        # Assert
        assert REFUSED[name, kind] in str(raised.value)


class TestTheIpsVariant:
    @pytest.mark.parametrize("name", sorted(set(CASES) - set(STAR_ROD)))
    def test_ips32_is_written_only_when_ips_cannot_reach(self, name):
        # Arrange
        case = CASES[name]

        # Act
        patch = api.make(case.source, case.target, Format.IPS)[".ips"]

        # Assert
        assert patch.startswith(ipswrite.MAGIC32) is (name in IPS32_CASES)


class TestTheReachOfAnIpsVariant:
    @pytest.mark.parametrize(
        ("before", "after", "expected"),
        [
            (bytes(15), bytes(16), True),
            (bytes(20), bytes(15), True),
            (bytes(20), bytes(16), False),
            (bytes(16), bytes(17), False),
            (bytes(20), bytes(16) + b"\x01" * 4, False),
            (bytes(20), b"\x01" * 16 + bytes(4), True),
        ],
    )
    def test_every_write_and_the_size_field_must_stay_below_the_limit(
        self, before, after, expected
    ):
        # Arrange
        variant = TINY

        # Act
        reached = ipswrite.reaches(variant, before, after)

        # Assert
        assert reached is expected

    def test_a_variant_that_cannot_reach_is_refused_with_its_name(self):
        # Arrange
        before, after = bytes(20), bytes(16)

        # Act
        with pytest.raises(ipswrite.IpsError) as raised:
            ipswrite.build_variant(TINY, before, after)

        # Assert
        assert re.search(r"TINY offsets cannot reach a 16-byte image", str(raised.value))
