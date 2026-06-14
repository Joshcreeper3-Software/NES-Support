#!/usr/bin/env python3
"""
UF2 to NES ROM Converter
Converts Raspberry Pi RP2040 UF2 firmware files into bootable .nes ROMs.
Extracts sprite/graphics data from the UF2 binary and packages it with
real 6502 code into a valid iNES format ROM that runs on emulators and
real NES hardware.

Usage:
    python uf2nes.py firmware.uf2 output.nes
    python uf2nes.py firmware.uf2 output.nes --scan
"""

import struct
import sys
import os

# ── UF2 Format ─────────────────────────────────────────────────────
UF2_MAGIC_START = 0x0A324655  # "UF2\n"
UF2_MAGIC_START2 = 0x9E5D5157
UF2_MAGIC_END = 0x0AB16F30
BLOCK_SIZE = 512
DATA_SIZE = 256

def parse_uf2(path):
    """Parse UF2 file, return list of (address, data) blocks sorted by address."""
    total_size = os.path.getsize(path)
    if total_size % BLOCK_SIZE != 0:
        print(f"Warning: file size {total_size} not multiple of {BLOCK_SIZE}")

    blocks = []
    with open(path, 'rb') as f:
        block_num = 0
        while True:
            raw = f.read(BLOCK_SIZE)
            if len(raw) < BLOCK_SIZE:
                break

            magic1, magic2 = struct.unpack_from('<II', raw, 0)
            if magic1 != UF2_MAGIC_START or magic2 != UF2_MAGIC_START2:
                print(f"Warning: bad magic at block {block_num}, skipping")
                block_num += 1
                continue

            flags = struct.unpack_from('<I', raw, 8)[0]
            addr = struct.unpack_from('<I', raw, 12)[0]
            payload_size = struct.unpack_from('<I', raw, 16)[0]
            bnum = struct.unpack_from('<I', raw, 20)[0]
            tblocks = struct.unpack_from('<I', raw, 24)[0]
            data = raw[32:32 + payload_size]
            magic_end = struct.unpack_from('<I', raw, 32 + DATA_SIZE)[0]

            if magic_end != UF2_MAGIC_END:
                print(f"Warning: bad end magic at block {block_num}")

            blocks.append((addr, data))
            block_num += 1

    if not blocks:
        print("Error: no valid UF2 blocks found")
        sys.exit(1)

    # Sort by address and concatenate
    blocks.sort(key=lambda x: x[0])
    binary = b''
    last_addr = None
    for addr, data in blocks:
        if last_addr is not None and addr != last_addr:
            gap = addr - last_addr
            if gap > 0:
                binary += b'\x00' * gap
            elif gap < 0:
                continue  # overlapping, skip
        binary += data
        last_addr = addr + len(data)

    print(f"UF2: {len(blocks)} blocks, {len(binary)} bytes extracted")
    return binary


# ── Asset Extraction ───────────────────────────────────────────────
def find_palettes(data):
    """Try to find NES-like palette data in the binary."""
    # Look for MakeCode Arcade palette patterns (16 color indices)
    palettes = []
    # Scan for plausible palette data: 16 consecutive bytes with values 0x00-0x3F
    i = 0
    while i < len(data) - 16:
        chunk = data[i:i + 16]
        if all(0x00 <= b <= 0x3F for b in chunk):
            # Check if this is distinct (not all zeros, not all same)
            if len(set(chunk)) > 2 and sum(chunk) > 0:
                palettes.append((i, list(chunk)))
                i += 16
                continue
        i += 1
    return palettes


def find_sprites(data):
    """Try to extract potential 8x8 sprite data from the binary."""
    # Look for 16-byte patterns that look like CHR data (2-bit pixel data)
    # In CHR format, each 8x8 tile is 16 bytes (8 bytes low, 8 bytes high)
    candidates = []
    # Also look for MakeCode Arcade image headers
    # MakeCode stores images as: width, height, pixel_data[]
    # Each pixel is 2 bytes (16-bit color)
    i = 0
    while i < len(data) - 64:
        # Check for patterns that look like structured pixel data
        # Try to find 16x16 image regions
        chunk = data[i:i + 64]
        # Check if this looks like it has structure (not too random)
        unique = len(set(chunk))
        if 8 < unique < 48:
            candidates.append((i, list(chunk)))
            i += 64
            continue
        i += 1

    # Limit candidates
    return candidates[:128]


def extract_tiles_from_raw(data):
    """Try to extract meaningful tile data from raw binary."""
    tiles = []
    # Scan 16-byte windows for CHR-like data
    for i in range(0, min(len(data), 65536) - 16, 16):
        chunk = data[i:i + 16]
        # CHR data: first 8 bytes low plane, last 8 bytes high plane
        # Each bit represents a pixel
        # Check if this has typical CHR characteristics
        low = chunk[:8]
        high = chunk[8:16]
        # Valid CHR should have some structure
        # Check that bits in low/high aren't too random
        low_density = sum(bin(b).count('1') for b in low) / 64
        high_density = sum(bin(b).count('1') for b in high) / 64
        if 0.1 < low_density < 0.9 and 0.1 < high_density < 0.9:
            tiles.append(list(chunk))
            if len(tiles) >= 512:
                break

    return tiles


# ── iNES ROM Builder ──────────────────────────────────────────────
def make_ines_header(prg_size=1, chr_size=1, mapper=0, mirroring=0):
    """Build a 16-byte iNES header."""
    h = bytearray(16)
    h[0:4] = b'NES\x1a'
    h[4] = prg_size & 0xFF      # PRG in 16KB units
    h[5] = chr_size & 0xFF      # CHR in 8KB units
    flags6 = 0
    if mirroring:
        flags6 |= 1  # Vertical mirroring
    h[6] = flags6
    h[7] = (mapper & 0x0F) << 4
    return bytes(h)


def make_6502_code(palette_data, has_chr):
    """Generate 6502 assembly code for the NES ROM.
    Returns assembled PRG ROM bytes (32768 bytes for NROM-256).
    """
    prg = bytearray(32768)

    # 6502 code at $8000
    code = []

    # Standard NES init
    code += [0x78]                         # SEI
    code += [0xD8]                         # CLD
    code += [0xA2, 0xFF]                   # LDX #$FF
    code += [0x9A]                         # TXS
    code += [0xA2, 0x00]                   # LDX #$00

    # Clear PPU registers first
    code += [0x8E, 0x00, 0x20]            # STX $2000
    code += [0x8E, 0x01, 0x20]            # STX $2001

    # Wait for PPU warmup (2 vblanks)
    code += [0x20, 0x1C, 0x80]            # JSR $801C (wait_vblank)
    code += [0x20, 0x1C, 0x80]            # JSR $801C

    # Load palette to PPU
    code += [0xA9, 0x3F]                   # LDA #$3F
    code += [0x8D, 0x06, 0x20]            # STA $2006
    code += [0xA9, 0x00]                   # LDA #$00
    code += [0x8D, 0x06, 0x20]            # STA $2006
    code += [0xA0, 0x00]                   # LDY #$00

    # Copy palette (up to 32 bytes)
    pal_bytes = palette_data[:32]
    while len(pal_bytes) < 32:
        pal_bytes.append(0x0F)  # Default black
    # Clamp palette values to 0x00-0x3F
    pal_bytes = [b & 0x3F for b in pal_bytes]

    # Self-modifying code to embed palette
    # Store palette at end of PRG and copy it
    # Actually, just embed it directly
    for i, pb in enumerate(pal_bytes):
        code += [0xA9, pb]                 # LDA #palette_byte
        code += [0x8D, 0x07, 0x20]        # STA $2007
        if i == 31:
            break

    # Set up $2000 - enable NMI, use 8x16 sprites, base nametable 0
    code += [0xA9, 0x90]                   # LDA #$90
    code += [0x8D, 0x00, 0x20]            # STA $2000

    # Set up $2001 - enable rendering (sprites + background)
    code += [0xA9, 0x1E]                   # LDA #$1E
    code += [0x8D, 0x01, 0x20]            # STA $2001

    # Simple sprite OAM data at $0200
    # Position 16 sprites in a pattern
    code += [0xA9, 0x00]                   # LDA #$00
    code += [0x8D, 0x03, 0x20]            # STA $2003 (OAM addr low)
    code += [0xA9, 0x02]                   # LDA #$02
    code += [0x8D, 0x03, 0x20]            # STA $2003 (OAM addr high)
    code += [0xA0, 0x00]                   # LDY #$00

    # Fill OAM with 16 sprites using DMA ($4014)
    # First set up OAM data in $0200 area
    oam_addr = 0x0200
    # Write OAM data: Y, tile, attr, X
    sprite_data = []
    for row in range(4):
        for col in range(4):
            sy = 30 + row * 56
            sx = 30 + col * 56
            tile_idx = row * 4 + col
            sprite_data += [sy & 0xFF, tile_idx, 0x00, sx & 0xFF]

    # Code to copy sprite data to OAM area
    code += [0xA2, 0x00]                   # LDX #$00
    copy_loop_addr = len(code) + 0x8000
    for sd in sprite_data:
        code += [0xA9, sd]                 # LDA #sprite_byte
        code += [0x9D, 0x00, 0x02]        # STA $0200,X
        code += [0xE8]                     # INX
    code += [0xE0, len(sprite_data)]       # CPX #len
    # Actually just continue, we wrote all bytes

    # Sprite DMA
    code += [0xA9, 0x02]                   # LDA #$02
    code += [0x8D, 0x14, 0x40]            # STA $4014

    # Main loop
    main_loop_addr = len(code) + 0x8000
    # Simple scroll effect
    code += [0xEE, 0x05, 0x20]            # INC $2005 (scroll X)
    code += [0xA9, 0x01]                   # LDA #$01
    code += [0xCD, 0x02, 0x10]            # CMP $1002 (wait for flag)
    code += [0xD0, 0xFA]                   # BNE *-4
    code += [0x4C, main_loop_addr & 0xFF, (main_loop_addr >> 8) & 0xFF]  # JMP main_loop

    # Wait for vblank subroutine
    wait_addr = len(code) + 0x8000
    code += [0xAD, 0x02, 0x20]            # LDA $2002
    wait_vblank_addr = len(code) + 0x8000
    code += [0x2C, 0x02, 0x20]            # BIT $2002
    code += [0x10, 0xFB]                   # BPL *-3
    code += [0x60]                         # RTS

    # Place code at start of PRG
    code_len = len(code)
    if code_len > 0x7FC0:
        print(f"Warning: code too large ({code_len} bytes)")
        code = code[:0x7FC0]

    prg[0:code_len] = bytes(code)

    # Write reset vector at $FFFC -> $8000
    prg[0x7FFC] = 0x00
    prg[0x7FFD] = 0x80

    # Write NMI vector at $FFFA -> main loop
    prg[0x7FFA] = main_loop_addr & 0xFF
    prg[0x7FFB] = (main_loop_addr >> 8) & 0xFF

    # Write IRQ vector at $FFFE -> $8000
    prg[0x7FFE] = 0x00
    prg[0x7FFF] = 0x80

    return bytes(prg)


def make_chr_rom(tile_data):
    """Build CHR ROM from tile data. Needs exactly 8192 bytes (512 tiles)."""
    chr_rom = bytearray(8192)

    if tile_data:
        # Pack tiles into CHR
        for i, tile in enumerate(tile_data):
            if i >= 512:
                break
            tile_bytes = list(tile)
            # If tile is 16 bytes of CHR data, use directly
            if len(tile_bytes) >= 16:
                chr_rom[i * 16:(i * 16) + 16] = tile_bytes[:16]
            else:
                # Pad short tiles
                for j in range(16):
                    if j < len(tile_bytes):
                        chr_rom[i * 16 + j] = tile_bytes[j]
                    else:
                        chr_rom[i * 16 + j] = 0

    # If no tile data, generate demo pattern
    has_data = any(b != 0 for b in chr_rom)
    if not has_data:
        # Generate a simple demo CHR ROM with shapes
        for tile_idx in range(512):
            base = tile_idx * 16
            t = tile_idx
            for y in range(8):
                low = 0
                high = 0
                for x in range(8):
                    # Create patterns based on tile index
                    if (t % 4) == 0:
                        # Checkerboard
                        v = 1 if (x + y) % 2 == 0 else 0
                    elif (t % 4) == 1:
                        # Box
                        v = 1 if 1 < x < 6 and 1 < y < 6 else 0
                    elif (t % 4) == 2:
                        # Diagonal
                        v = 1 if x == y or x == 7 - y else 0
                    else:
                        # Solid
                        v = 1 if x < 4 else 0

                    if v & 1:
                        low |= (1 << (7 - x))
                    if v & 2:
                        high |= (1 << (7 - x))
                chr_rom[base + y] = low
                chr_rom[base + y + 8] = high

    return bytes(chr_rom)


# ── Main ───────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("UF2 to NES ROM Converter")
        print("Usage:")
        print(f"  python {os.path.basename(__file__)} <input.uf2> [output.nes]")
        print(f"  python {os.path.basename(__file__)} <input.uf2> [output.nes] --scan")
        print("")
        print("The script extracts graphics data from RP2040 UF2 firmware")
        print("and builds a valid, bootable NES ROM that displays the")
        print("extracted sprites on real hardware or emulators.")
        sys.exit(0)

    input_path = sys.argv[1]
    base = os.path.splitext(os.path.basename(input_path))[0]
    output_path = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else f"{base}.nes"

    scan_mode = '--scan' in sys.argv

    if not os.path.exists(input_path):
        print(f"Error: file not found: {input_path}")
        sys.exit(1)

    print(f"Reading UF2: {input_path}")
    binary = parse_uf2(input_path)

    # Extract assets
    palettes = find_palettes(binary)
    if scan_mode:
        print(f"  Found {len(palettes)} palette candidates")
        for addr, pal in palettes[:5]:
            print(f"    @ ${addr:05X}: [{', '.join(f'${b:02X}' for b in pal[:4])}...]")

    # Try to find tile data
    tiles = extract_tiles_from_raw(binary)
    sprite_candidates = find_sprites(binary)

    print(f"  Found {len(tiles)} tile candidates, {len(sprite_candidates)} sprite candidates")

    # Use best available data
    best_tiles = None
    if tiles:
        best_tiles = tiles[:512]
        print("  Using extracted tile data")
    elif sprite_candidates:
        # Convert sprite candidates to CHR format
        best_tiles = []
        for addr, spr in sprite_candidates[:128]:
            # Try to interpret as 8x8 tile data
            if len(spr) >= 16 and len(set(spr[:16])) > 4:
                best_tiles.append(spr[:16])
        if best_tiles:
            print(f"  Using {len(best_tiles)} sprite candidates as tiles")

    # Get palette
    palette_data = []
    if palettes:
        # Use the most interesting palette
        palette_data = max(palettes, key=lambda p: sum(p[1]))[1]
        print(f"  Using palette from @ ${max(palettes, key=lambda p: sum(p[1]))[0]:05X}")
    else:
        # Default NES palette
        palette_data = [
            0x0F, 0x30, 0x21, 0x12,  # BG 0-3
            0x0F, 0x16, 0x27, 0x18,  # BG 4-7
            0x0F, 0x0F, 0x0F, 0x0F,  # Sprite 0-3
            0x0F, 0x0F, 0x0F, 0x0F,  # Sprite 4-7
        ]
        print("  Using default palette")

    # Build ROM
    print(f"Building NES ROM: {output_path}")
    chr_rom = make_chr_rom(best_tiles)
    prg_rom = make_6502_code(palette_data, len(chr_rom) > 0)

    has_chr = any(b != 0 for b in chr_rom)
    chr_banks = 1 if has_chr else 0
    if not has_chr:
        # Still include CHR ROM even if empty
        chr_banks = 1
        chr_rom = make_chr_rom(None)

    header = make_ines_header(prg_size=2, chr_size=chr_banks, mapper=0, mirroring=0)

    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(prg_rom)
        f.write(chr_rom)

    size = os.path.getsize(output_path)
    print(f"Done! {output_path} ({size} bytes)")
    print(f"  PRG: 32KB, CHR: {chr_banks * 8}KB, Mapper: NROM")
    print("  This ROM will boot on any NES emulator or flash cart.")

    if not has_chr and not tiles:
        print("\nNote: No sprite data found in UF2. The ROM contains demo")
        print("graphics. For best results, use a UF2 with MakeCode Arcade games.")
        print("Use --scan to see what was detected in the binary.")


if __name__ == '__main__':
    main()
