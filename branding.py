"""App version and a generic Windows list icon; no logo assets."""

VERSION = "1.4.0"


def application_icon(size=64):
    """Plain list glyph for Windows/tray identification; no brand artwork."""
    from PIL import Image, ImageDraw
    icon = Image.new("RGBA", (256, 256), "#202020")
    draw = ImageDraw.Draw(icon)
    for y in (72, 120, 168):
        draw.rounded_rectangle((48, y, 208, y+16), radius=8, fill="#F5CD47")
    return icon.resize((size, size), Image.Resampling.LANCZOS)
