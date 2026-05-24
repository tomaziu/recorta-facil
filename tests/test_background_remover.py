import tempfile
import unittest
from pathlib import Path

from PIL import Image

import background_remover as br


class BackgroundRemoverTests(unittest.TestCase):
    def test_parse_color_accepts_hex_values(self):
        self.assertEqual(br.parse_color("#00ff7f"), (0, 255, 127))
        self.assertEqual(br.parse_color("ffffff"), (255, 255, 255))
        self.assertIsNone(br.parse_color(""))
        self.assertIsNone(br.parse_color("transparent"))

    def test_parse_color_rejects_invalid_value(self):
        with self.assertRaises(ValueError):
            br.parse_color("#fff")

    def test_default_output_path(self):
        output = br.default_output_path(Path("fotos") / "produto.jpg")
        self.assertEqual(output, Path("fotos") / "produto-sem-fundo.png")

    def test_make_checkerboard_uses_two_neutral_colors(self):
        image = br.make_checkerboard((32, 32), tile=8)
        colors = {image.getpixel((x, y)) for y in range(32) for x in range(32)}
        self.assertEqual(colors, {(224, 224, 224), (248, 248, 248)})

    def test_remove_local_solid_border_background(self):
        image = Image.new("RGB", (80, 80), "white")
        for y in range(20, 60):
            for x in range(20, 60):
                image.putpixel((x, y), (20, 90, 220))

        result = br.remove_local(
            image,
            br.RemoveOptions(mode="border", tolerance=20, soft_edges=False, enhance=False),
        )

        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((40, 40))[3], 255)

    def test_process_image_checker_background_writes_transparent_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            output = tmp_path / "out.png"

            image = br.make_checkerboard((90, 90), tile=9).convert("RGBA")
            subject = Image.new("RGBA", (40, 40), (230, 20, 50, 255))
            image.alpha_composite(subject, (25, 25))
            image.save(source)

            saved = br.process_image(
                source,
                output,
                br.RemoveOptions(mode="checker", soft_edges=False, enhance=False),
            )

            self.assertEqual(saved, output)
            result = Image.open(output).convert("RGBA")
            self.assertEqual(result.getpixel((0, 0))[3], 0)
            self.assertEqual(result.getpixel((45, 45))[3], 255)

    def test_save_output_image_can_fill_background(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "filled.png"
            image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
            image.putpixel((5, 5), (255, 0, 0, 255))

            br.save_output_image(
                image,
                output,
                br.RemoveOptions(fill=(255, 255, 255), enhance=False),
            )

            result = Image.open(output).convert("RGB")
            self.assertEqual(result.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(result.getpixel((5, 5)), (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
