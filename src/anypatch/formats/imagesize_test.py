import pytest

from n64_save_patches import imagesize


class TestTheCeiling:
    def test_a_result_at_the_ceiling_is_accepted(self):
        # Arrange
        size = 1 << 30

        # Act
        imagesize.check(size, source=0)

        # Assert
        assert size == imagesize.LIMIT

    def test_a_result_past_the_ceiling_is_refused_naming_both_sizes(self):
        # Arrange
        size = (1 << 30) + 1

        # Act
        with pytest.raises(imagesize.ImageSizeError) as raised:
            imagesize.check(size, source=0)

        # Assert
        assert str(raised.value) == (
            "the patch claims a 1,073,741,825-byte result, past the 1,073,741,824-byte ceiling"
        )

    def test_a_source_larger_than_the_ceiling_raises_it_to_the_source_size(self):
        # Arrange
        source = (1 << 30) + 100

        # Act
        imagesize.check(source, source=source)

        # Assert
        assert source > imagesize.LIMIT
