import numpy
from PIL import Image

MIN_MATCH_LEN = 3
MAX_MATCH_LEN = 18
MAX_DISPLACEMENT = 4096
TRANSPARENCY_ALPHA_THRESHOLD = 128  # pixels with alpha below this are treated as transparent
TRANSPARENT_INDEX = 0  # GBA hardware treats palette index 0 as transparent for sprites


def png_to_lz77(png_data: numpy.ndarray) -> tuple[bytearray, bytearray]:
    image = Image.fromarray(png_data).convert("RGBA")

    # Pokemon sprites are 64x64 pixels
    image = image.resize((64, 64), Image.Resampling.LANCZOS)

    # convert back to numpy for easier processing
    rgba = numpy.array(image)

    # extract transparent pixels
    transparent_mask = rgba[:, :, 3] < TRANSPARENCY_ALPHA_THRESHOLD

    # Place the transparent pixels back into the array as black.
    # Copy isn't strictly necessary, but is safer
    rgb_data = rgba[:, :, :3].copy()
    rgb_data[transparent_mask] = (0, 0, 0)
    rgb_image = Image.fromarray(rgb_data, mode="RGB")

    # reduce to 15 colours. The 16th colour is the transparency.
    quantized = rgb_image.quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    indices = numpy.array(quantized, dtype=numpy.uint8) + 1
    indices[transparent_mask] = TRANSPARENT_INDEX

    # GBA images use 8x8 pixel tiles to store sprites.
    # Those 8x8 pixel tiles are themselves flattened.
    back_tiled = _tile_image(indices)
    front_tiled = back_tiled + back_tiled
    palette = _extract_palette(quantized)
    return _compress(front_tiled), _compress(back_tiled), _compress(palette)


def _extract_palette(quantized: Image.Image) -> bytearray:
    sorted_palette = [(colour, index) for colour, index in quantized.palette.colors.items()]
    sorted_palette.sort(key=lambda c: c[1])
    formatted_palette = bytearray(32) # 2 bytes per colour, 16 colours
    for ((r, g, b), index) in sorted_palette:
        # colour channels are 5 bit resolution
        red5 = r >> 3
        green5 = g >> 3
        blue5 = b >> 3
        full_colour = (red5 | (green5 << 5) | (blue5 << 10))
        # quantizer index 0..14 -> GBA palette slot 1..15; slot 0 stays transparent.
        # Each slot is a 16-bit halfword, so slot n occupies bytes n*2 and n*2 + 1.
        slot = index + 1
        formatted_palette[slot * 2] = full_colour & 0xFF
        formatted_palette[slot * 2 + 1] = full_colour >> 8
    return formatted_palette


def _tile_image(indices: numpy.ndarray) -> bytearray:
    # 64x64 sprite -> 8x8 grid of 8x8 tiles, 4bpp (2 px/byte), duplicated for two frames.
    height, width = indices.shape
    tiles_per_row = width // 8
    frame_bytes = width * height // 2
    tile_pixels = bytearray(frame_bytes)

    for i in range(width * height):  # i = pixel index in tile order
        tile_index = i // 64
        within = i % 64
        tile_x = tile_index % tiles_per_row
        tile_y = tile_index // tiles_per_row
        px, py = within % 8, within // 8
        value = int(indices[tile_y * 8 + py, tile_x * 8 + px]) & 0xF

        byte_offset = i // 2
        if i % 2 == 0:
            tile_pixels[byte_offset] |= value  # first pixel -> low nibble
        else:
            tile_pixels[byte_offset] |= value << 4  # second pixel -> high nibble

    return tile_pixels

def _compress(data: bytes) -> bytearray:
    """GBA BIOS-compatible LZ77 compression (header type 0x10)."""
    out = bytearray()
    out.append(0x10)
    out += len(data).to_bytes(3, "little")

    pos = 0
    while pos < len(data):
        flags = 0
        flag_pos = len(out)
        out.append(0)  # placeholder, patched below
        block = bytearray()

        for bit in range(8):
            if pos >= len(data):
                break

            best_len, best_disp = 0, 0
            window_start = max(0, pos - MAX_DISPLACEMENT)
            for start in range(window_start, pos):
                length = 0
                while (length < MAX_MATCH_LEN
                       and pos + length < len(data)
                       and data[start + length] == data[pos + length]):
                    length += 1
                if length > best_len:
                    best_len, best_disp = length, pos - start

            if best_len >= MIN_MATCH_LEN:
                flags |= 1 << (7 - bit)
                disp = best_disp - 1
                block.append(((best_len - 3) << 4) | (disp >> 8))
                block.append(disp & 0xFF)
                pos += best_len
            else:
                block.append(data[pos])
                pos += 1

        out[flag_pos] = flags
        out += block

    return out
