import struct

import pytest

from anypatch.formats import dldi
from anypatch.formats.dldi_vectors_test_support import header, placed, words

DRIVER_BASE = 0xBF800000
APP_BASE = 0x02000000
RELOCATION = APP_BASE - DRIVER_BASE
STUB_AT = 0x100
LOG2 = 8
SPACE = 1 << LOG2


def word(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def driver(flags: int = 0, *, log2: int = LOG2, length: int = 0xC0, data_end: int = 0xC0) -> bytes:
    base = DRIVER_BASE
    sections = words(base, base + data_end, base + 0xA0, base + 0xA8, base + 0xA8, base + 0xB0)
    bss = words(base + 0xB0, base + 0xB8)
    io = b"TEST" + words(0x23, *(base + 0x80 + 4 * at for at in range(6)))
    head = header(log2, flags, log2, b"test") + sections + bss + io
    return head + bytes(length - len(head))


def app(*, allocated: int = LOG2, text_start: int = APP_BASE, stub_at: int = STUB_AT) -> bytes:
    stub = header(allocated, 0, allocated, b"stub") + words(text_start, *([0] * 7))
    io = b"DLDI" + words(0, APP_BASE + 0x80, *([0] * 5))
    return placed(bytes(range(256)) * 4, stub_at, stub + io)


class TestPatching:
    def test_the_driver_replaces_the_stub_and_keeps_the_reserved_size(self):
        # Arrange
        patch = driver()

        # Act
        result = dldi.apply(app(allocated=9), patch)

        # Assert
        assert result[STUB_AT : STUB_AT + 0x40] == patch[:0x0F] + b"\x09" + patch[0x10:0x40]

    def test_every_header_pointer_moves_to_the_app_address(self):
        # Arrange
        patch = driver()

        # Act
        result = dldi.apply(app(), patch)

        # Assert
        moved = [word(result, STUB_AT + at) for at in dldi.POINTERS]
        assert moved == [(word(patch, at) + RELOCATION) & 0xFFFFFFFF for at in dldi.POINTERS]

    def test_a_stub_with_no_text_start_is_placed_at_its_startup_less_the_header(self):
        # Arrange
        patch = driver()

        # Act
        result = dldi.apply(app(text_start=0), patch)

        # Assert
        assert word(result, STUB_AT + 0x40) == APP_BASE

    def test_bytes_past_the_driver_file_keep_the_app_and_nothing_past_the_space_changes(self):
        # Arrange
        before = app()

        # Act
        result = dldi.apply(before, driver())

        # Assert
        assert result[STUB_AT + 0xC0 : STUB_AT + SPACE] == before[STUB_AT + 0xC0 : STUB_AT + SPACE]
        assert result[STUB_AT + SPACE :] == before[STUB_AT + SPACE :]
        assert result[:STUB_AT] == before[:STUB_AT]

    def test_the_first_aligned_section_is_patched_and_an_unaligned_magic_is_skipped(self):
        # Arrange
        decoy = placed(app(stub_at=0x200), 0x81, dldi.MAGIC)

        # Act
        result = dldi.apply(decoy, driver())

        # Assert
        assert result[0x81 : 0x81 + len(dldi.MAGIC)] == dldi.MAGIC
        assert word(result, 0x200 + 0x40) == APP_BASE


class TestRelocation:
    @pytest.mark.parametrize(
        ("value", "moved"),
        [
            (DRIVER_BASE, APP_BASE),
            (DRIVER_BASE + SPACE - 1, APP_BASE + SPACE - 1),
            (DRIVER_BASE - 1, DRIVER_BASE - 1),
            (DRIVER_BASE + SPACE, DRIVER_BASE + SPACE),
        ],
        ids=["start", "last", "before", "end"],
    )
    def test_fix_all_moves_only_words_inside_the_driver_space(self, value, moved):
        # Arrange
        patch = placed(driver(dldi.FIX_ALL), 0x90, words(value))

        # Act
        result = dldi.apply(app(), patch)

        # Assert
        assert word(result, STUB_AT + 0x90) == moved

    def test_fix_all_scans_every_byte_offset_not_only_aligned_words(self):
        # Arrange
        patch = placed(driver(dldi.FIX_ALL), 0x93, words(DRIVER_BASE + 8))

        # Act
        result = dldi.apply(app(), patch)

        # Assert
        assert struct.unpack_from("<I", result, STUB_AT + 0x93)[0] == APP_BASE + 8

    @pytest.mark.parametrize(
        ("flag", "inside", "outside"),
        [(dldi.FIX_GLUE, 0xA0, 0xA8), (dldi.FIX_GOT, 0xA8, 0x98)],
        ids=["glue", "got"],
    )
    def test_glue_and_got_fixes_stay_inside_their_section(self, flag, inside, outside):
        # Arrange
        patch = placed(
            placed(driver(flag), inside, words(DRIVER_BASE)), outside, words(DRIVER_BASE)
        )

        # Act
        result = dldi.apply(app(), patch)

        # Assert
        assert (word(result, STUB_AT + inside), word(result, STUB_AT + outside)) == (
            APP_BASE,
            DRIVER_BASE,
        )

    def test_the_bss_is_cleared(self):
        # Arrange
        patch = placed(driver(dldi.FIX_BSS), 0xB0, b"\xff" * 8)

        # Act
        result = dldi.apply(app(), patch)

        # Assert
        assert result[STUB_AT + 0xB0 : STUB_AT + 0xB8] == bytes(8)


class TestRefusals:
    @pytest.mark.parametrize(
        ("target", "patch", "message"),
        [
            (bytes(64), driver(), "the app has no DLDI section"),
            (app(), driver()[:0x7F], "too short to hold the 128-byte DLDI header"),
            (app(), b"x" + driver()[1:], "not a DLDI driver"),
            (app(), placed(driver(), 0x0C, b"\x02"), "DLDI version 2; only 1 is read"),
            (app(), driver(log2=9), "needs 512 bytes, but the app reserves 256"),
            (app(), driver(length=SPACE + 4), "the driver file is 260 bytes, past the 256"),
            (app(stub_at=0x380), driver(), "runs past the end of the app"),
            (app(), driver(dldi.FIX_ALL, data_end=SPACE + 0x40), "outside the driver space"),
            (app(), placed(driver(dldi.FIX_BSS), 0x5C, words(DRIVER_BASE)), "outside the driver"),
            (
                app(stub_at=0x300),
                driver(dldi.FIX_ALL, length=SPACE, data_end=SPACE),
                "a section to relocate runs past the end of the app",
            ),
        ],
        ids=[
            "no-section",
            "short-driver",
            "magic",
            "version",
            "too-big",
            "file-past-size",
            "past-app-end",
            "fix-range",
            "bss-range",
            "window-past-app-end",
        ],
    )
    def test_a_driver_that_cannot_be_placed_is_refused(self, target, patch, message):
        # Arrange
        source = target

        # Act
        with pytest.raises(dldi.DldiError) as raised:
            dldi.apply(source, patch)

        # Assert
        assert message in str(raised.value)
