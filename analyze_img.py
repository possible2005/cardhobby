from PIL import Image
import collections

img = Image.open('/Users/donglin/Desktop/projects/card_env/22572362-27ee-482c-a7b1-c7d039a659d7.png')
print(f'Image size: {img.size}')
print(f'Image mode: {img.mode}')

w, h = img.size
regions = {
    'top-left': (0, 0),
    'top-center': (w//2, 0),
    'top-right': (w-1, 0),
    'center': (w//2, h//2),
    'bottom-left': (0, h-1),
    'bottom-center': (w//2, h-1),
    'bottom-right': (w-1, h-1),
    'mid-left': (0, h//2),
    'mid-right': (w-1, h//2),
}

for name, (x, y) in regions.items():
    pixel = img.getpixel((x, y))
    if len(pixel) == 4:
        r, g, b, a = pixel
    else:
        r, g, b = pixel
    print(f'{name}: rgb({r}, {g}, {b}) #{r:02x}{g:02x}{b:02x}')

pixels = []
for x in range(0, w, max(1, w//50)):
    for y in range(0, h, max(1, h//50)):
        p = img.getpixel((x, y))
        if len(p) == 4:
            r, g, b, a = p
        else:
            r, g, b = p
        pixels.append((r//32*32, g//32*32, b//32*32))

counter = collections.Counter(pixels)
print('\nTop 10 dominant colors:')
for color, count in counter.most_common(10):
    r, g, b = color
    print(f'  rgb({r}, {g}, {b}) #{r:02x}{g:02x}{b:02x} - {count} samples')

# Sample horizontal gradient at top
print('\nTop edge gradient (left to right):')
for x in range(0, w, max(1, w//10)):
    p = img.getpixel((x, 5))
    if len(p) == 4:
        r, g, b, a = p
    else:
        r, g, b = p
    print(f'  x={x}: rgb({r}, {g}, {b}) #{r:02x}{g:02x}{b:02x}')

# Sample vertical gradient at left
print('\nLeft edge gradient (top to bottom):')
for y in range(0, h, max(1, h//10)):
    p = img.getpixel((5, y))
    if len(p) == 4:
        r, g, b, a = p
    else:
        r, g, b = p
    print(f'  y={y}: rgb({r}, {g}, {b}) #{r:02x}{g:02x}{b:02x}')
