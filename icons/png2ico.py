from PIL import Image
import argparse

parser = argparse.ArgumentParser(description="Convert PNG to ICO")
parser.add_argument("input", help="Input PNG file")
parser.add_argument("output", help="Output ICO file")
args = parser.parse_args()
# Open the source PNG image
img = Image.open(args.input)

# Save it directly as an ICO file
img.save(args.output, format="ICO")