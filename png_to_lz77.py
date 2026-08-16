import numpy
import math
from PIL import Image

MIN_MATCH_LEN = 3
MAX_MATCH_LEN = 18
MAX_DISPLACEMENT = 4096
TRANSPARENCY_ALPHA_THRESHOLD = 128  # pixels with alpha below this are treated as transparent
TRANSPARENT_INDEX = 0  # GBA hardware treats palette index 0 as transparent for sprites


def png_to_lz77(png_data: numpy.ndarray) -> bytearray:
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
    tiled = _tile_image(indices)
    return _compress(tiled)

def _tile_image(indices: numpy.ndarray) -> bytearray:
    # 8 x 8 tiles, each 8 x 8 pixels
    tile_pixels = bytearray(4096)
    for i in range(len(tile_pixels)):
        tile_row = math.floor(i / 512)
        tile_column = math.floor((i - tile_row * 512) / 64)
        tile_start_pixel = tile_row * 512 + tile_column * 64
        pixel_row = math.floor((i - tile_start_pixel) / 8)
        pixel_column = tile_start_pixel % 8
        pixel_within_tile = pixel_row * 8 + pixel_column
        tile_pixels[i] = indices[tile_start_pixel + pixel_within_tile]
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


# def _pack_4bpp(indices: numpy.ndarray) -> bytearray:
#     """Pack one-byte-per-pixel palette indices (0-15) into 2 pixels per byte, row-major."""
#     flat = indices.flatten()
#     packed = bytearray(len(flat) // 2)
#     for i in range(0, len(flat), 2):
#         packed[i // 2] = (flat[i] & 0x0F) | ((flat[i + 1] & 0x0F) << 4)
#     return packed
#
#
# def _lz77_compress(data: bytes) -> bytearray:
#     """GBA BIOS-compatible LZ77 compression (header type 0x10)."""
#     out = bytearray()
#     out.append(0x10)
#     out += len(data).to_bytes(3, "little")
#
#     pos = 0
#     while pos < len(data):
#         flags = 0
#         flag_pos = len(out)
#         out.append(0)  # placeholder, patched below
#         block = bytearray()
#
#         for bit in range(8):
#             if pos >= len(data):
#                 break
#
#             best_len, best_disp = 0, 0
#             window_start = max(0, pos - MAX_DISPLACEMENT)
#             for start in range(window_start, pos):
#                 length = 0
#                 while (length < MAX_MATCH_LEN
#                        and pos + length < len(data)
#                        and data[start + length] == data[pos + length]):
#                     length += 1
#                 if length > best_len:
#                     best_len, best_disp = length, pos - start
#
#             if best_len >= MIN_MATCH_LEN:
#                 flags |= 1 << (7 - bit)
#                 disp = best_disp - 1
#                 block.append(((best_len - 3) << 4) | (disp >> 8))
#                 block.append(disp & 0xFF)
#                 pos += best_len
#             else:
#                 block.append(data[pos])
#                 pos += 1
#
#         out[flag_pos] = flags
#         out += block
#
#     return out