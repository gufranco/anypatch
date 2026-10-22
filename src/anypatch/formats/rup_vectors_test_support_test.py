from anypatch.formats import rup
from anypatch.formats import rup_vectors_test_support as vectors


class TestAPatchNinjaWrote:
    def test_the_typed_nes_patch_applies_to_the_ines_image_and_keeps_its_header(self):
        # Arrange
        source = vectors.INES_HEADER + vectors.source()

        # Act
        result = rup.apply(source, vectors.NINJA_NES)

        # Assert
        assert result == vectors.INES_HEADER + vectors.target()

    def test_it_records_the_nes_rom_type(self):
        # Arrange
        entry = vectors.NINJA_NES[rup.HEADER :]

        # Act
        kind = entry[3 + len(b"game.nes")]

        # Assert
        assert kind == 1
