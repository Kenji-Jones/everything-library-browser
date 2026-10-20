"""Make numbered contact sheets of a canvas category's thumbnails, for naming the models by eye.

    python3 naming_sheets.py <export_out_dir> <Category> <sheet_dir> [per_sheet]
"""
import sys, json, os
from PIL import Image, ImageDraw, ImageFont

out, cat, sheet_dir = sys.argv[1:4]
per = int(sys.argv[4]) if len(sys.argv) > 4 else 40
items = json.load(open(os.path.join(out, "data", "parts", cat.lower() + ".json")))
tiles = sorted(((int(i["sourceFiles"][0][:-4]), i["variants"][0]["thumb"]) for i in items))
font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
cols, sz = 8, 220
os.makedirs(sheet_dir, exist_ok=True)
for s in range(0, len(tiles), per):
    chunk = tiles[s:s + per]
    rows = (len(chunk) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * sz, rows * sz), (236, 234, 228))
    d = ImageDraw.Draw(sheet)
    for k, (idx, thumb) in enumerate(chunk):
        x, y = (k % cols) * sz, (k // cols) * sz
        im = Image.open(os.path.join(out, thumb)).convert("RGBA").resize((sz - 10, sz - 10))
        sheet.paste(im, (x + 5, y + 5), im)
        d.rectangle((x + 4, y + 4, x + 60, y + 32), fill=(28, 27, 25))
        d.text((x + 9, y + 6), str(idx), fill=(255, 255, 255), font=font)
        d.rectangle((x, y, x + sz - 1, y + sz - 1), outline=(205, 200, 190))
    path = os.path.join(sheet_dir, f"{cat}_{s:03d}-{s + len(chunk) - 1:03d}.png")
    sheet.save(path, optimize=True)
    print(path)
