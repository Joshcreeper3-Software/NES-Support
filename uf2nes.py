#!/usr/bin/env python3
"""
UF2 → NES 1-to-1 Converter

Takes a Raspberry Pi RP2040 UF2 firmware file and produces a valid, bootable
.nes ROM. The raw UF2 binary payload is preserved byte-for-byte inside the
PRG ROM. A tiny 6502 bootstrap initializes the NES and displays the extracted
graphics on screen.

Usage:
    python uf2nes.py firmware.uf2 output.nes
    python uf2nes.py firmware.uf2 output.nes --scan
"""

import struct, sys, os

# ── UF2 Format ────────────────────────────────────────────────────
UF2_MAGIC_START  = 0x0A324655
UF2_MAGIC_START2 = 0x9E5D5157
UF2_MAGIC_END    = 0x0AB16F30
BLOCK_SIZE = 512
DATA_SIZE  = 256

def parse_uf2(path):
    """Extract raw binary payload from UF2 file (concatenated data blocks)."""
    size = os.path.getsize(path)
    if size % BLOCK_SIZE != 0:
        print(f"Warning: file size {size} not multiple of {BLOCK_SIZE}")

    blocks = []
    with open(path, 'rb') as f:
        num = 0
        while True:
            raw = f.read(BLOCK_SIZE)
            if len(raw) < BLOCK_SIZE:
                break
            m1, m2 = struct.unpack_from('<II', raw, 0)
            if m1 != UF2_MAGIC_START or m2 != UF2_MAGIC_START2:
                num += 1; continue
            addr = struct.unpack_from('<I', raw, 12)[0]
            plen = struct.unpack_from('<I', raw, 16)[0]
            data = raw[32:32 + plen]
            me = struct.unpack_from('<I', raw, 32 + DATA_SIZE)[0]
            blocks.append((addr, data))
            num += 1

    if not blocks:
        print("Error: no valid UF2 blocks found"); sys.exit(1)

    blocks.sort(key=lambda x: x[0])
    binary = b''
    last = None
    for addr, data in blocks:
        if last is not None and addr > last:
            binary += b'\x00' * (addr - last)
        binary += data
        last = addr + len(data)

    print(f"UF2: {num} blocks, raw payload {len(binary)} bytes")
    return binary


# ── Asset scan ─────────────────────────────────────────────────────
def scan_assets(data):
    """Scan binary for palette and tile candidates."""
    # Find palette candidates: 16 consecutive bytes 0x00-0x3F
    pals = []
    i = 0
    while i < len(data) - 16:
        chunk = data[i:i+16]
        if all(0x00 <= b <= 0x3F for b in chunk) and len(set(chunk)) > 2:
            pals.append((i, list(chunk)))
            i += 16; continue
        i += 1

    # Find CHR-like tiles: 16-byte windows with balanced bit density
    tiles = []
    for i in range(0, min(len(data), 65536) - 16, 16):
        c = data[i:i+16]
        ld = sum(bin(b).count('1') for b in c[:8]) / 64
        hd = sum(bin(b).count('1') for b in c[8:16]) / 64
        if 0.1 < ld < 0.9 and 0.1 < hd < 0.9:
            tiles.append(list(c))
            if len(tiles) >= 512: break

    return pals, tiles


# ── NES ROM Builder ────────────────────────────────────────────────
def build_rom(uf2_data, pals, tiles):
    """Build a complete .nes file: header + PRG + CHR.
    The raw UF2 payload is embedded 1:1 in PRG ROM after the bootstrap.
    """
    # ── Bootstrap 6502 code (placed at $8000) ──
    # We use a stack of bytearrays to avoid forward-reference fixups.
    # Build the wait-vblank subroutine first, compute its CPU address,
    # then emit the JSRs with the correct address from the start.

    # wait-vblank subroutine (BIT $2002 ; BPL -3 ; RTS)
    sub_wait = [0x2C, 0x02, 0x20, 0x10, 0xFB, 0x60]

    bootstrap = []
    def emit(*args):
        for a in args:
            if isinstance(a, int):
                bootstrap.append(a)
            else:
                bootstrap.extend(a)

    emit(
        0x78,                         # SEI
        0xD8,                         # CLD
        0xA2, 0xFF, 0x9A,             # LDX #$FF ; TXS
        0xA2, 0x00,                   # LDX #$00
        0x8E, 0x00, 0x20,             # STX $2000
        0x8E, 0x01, 0x20,             # STX $2001
    )

    # Wait 2 vblanks — we know sub_wait will be placed right after enable-code
    # For now emit placeholder addresses, will patch later
    jsr_wait_idx1 = len(bootstrap)
    emit(0x20, 0x00, 0x00)  # placeholder JSR
    jsr_wait_idx2 = len(bootstrap)
    emit(0x20, 0x00, 0x00)  # placeholder JSR

    # Load palette
    emit(0xA9, 0x3F, 0x8D, 0x06, 0x20)  # STA $2006 ; high
    emit(0xA9, 0x00, 0x8D, 0x06, 0x20)  # STA $2006 ; low

    pal_data = []
    if pals:
        pal_data = max(pals, key=lambda p: sum(p[1]))[1]
    while len(pal_data) < 32:
        pal_data.append(0x0F)
    pal_data = [b & 0x3F for b in pal_data[:32]]
    for pb in pal_data:
        emit(0xA9, pb, 0x8D, 0x07, 0x20)

    # Enable rendering
    emit(
        0xA9, 0x90, 0x8D, 0x00, 0x20,  # LDA #$90 ; STA $2000
        0xA9, 0x1E, 0x8D, 0x01, 0x20,  # LDA #$1E ; STA $2001
        0xA9, 0x00, 0x8D, 0x03, 0x20,  # STA $2003
        0xA9, 0x02, 0x8D, 0x03, 0x20,  # STA $2003
    )

    # Now sub_wait goes here — compute its CPU address
    sub_wait_addr = 0x8000 + len(bootstrap)
    # Patch the two JSRs
    bootstrap[jsr_wait_idx1 + 1] = sub_wait_addr & 0xFF
    bootstrap[jsr_wait_idx1 + 2] = (sub_wait_addr >> 8) & 0xFF
    bootstrap[jsr_wait_idx2 + 1] = sub_wait_addr & 0xFF
    bootstrap[jsr_wait_idx2 + 2] = (sub_wait_addr >> 8) & 0xFF
    emit(sub_wait)

    # Build OAM data: 16 sprites in a grid
    oam = []
    for row in range(4):
        for col in range(4):
            sy = 30 + row * 56
            sx = 30 + col * 56
            ti = row * 4 + col
            oam += [sy & 0xFF, ti, 0x00, sx & 0xFF]

    # Copy OAM to $0200 via inline LDA/STA (no loop)
    for b in oam:
        emit(0xA9, b, 0x9D, 0x00, 0x02, 0xE8)  # LDA #b; STA $0200,X; INX

    # Fire OAM DMA
    emit(0xA9, 0x02, 0x8D, 0x14, 0x40)  # LDA #2; STA $4014

    # Main loop (infinite)
    main_loop_ofs = len(bootstrap)
    emit(0x4C, main_loop_ofs & 0xFF, (main_loop_ofs >> 8) & 0xFF)

    bs_len = len(bootstrap)

    # ── Determine PRG size & mapper ──
    min_banks = (bs_len + len(uf2_data) + 16383) // 16384

    if min_banks <= 2:
        mapper = 0
        mapper_name = "NROM"
        valid_banks = [1, 2]
    else:
        mapper = 1
        mapper_name = "MMC1"
        valid_banks = [8, 16, 32]  # MMC1 valid PRG bank counts

    # Round up to next valid bank count
    prg_banks = None
    for v in valid_banks:
        if v >= min_banks:
            prg_banks = v
            break
    if prg_banks is None:
        print(f"Error: UF2 data too large ({len(uf2_data)} bytes, needs {min_banks} banks)")
        sys.exit(1)

    prg_size = prg_banks * 16384

    print(f"  Bootstrap: {bs_len} bytes")
    print(f"  UF2 payload: {len(uf2_data)} bytes (1:1 preserved)")
    print(f"  PRG banks: {prg_banks} x 16KB = {prg_size} bytes")

    prg = bytearray(prg_size)
    prg[0:bs_len] = bytes(bootstrap)
    prg[bs_len:bs_len + len(uf2_data)] = uf2_data

    # Vectors at end of last 16KB page ($FFFA-$FFFF in CPU space)
    prg[-6] = main_loop_ofs & 0xFF                                     # NMI low
    prg[-5] = (0x8000 + main_loop_ofs) >> 8 & 0xFF                     # NMI high
    prg[-4] = 0x00                                                      # Reset low
    prg[-3] = 0x80                                                      # Reset high ($8000)
    prg[-2] = 0x00                                                      # IRQ low
    prg[-1] = 0x80                                                      # IRQ high

    # ── CHR ROM ──
    chr_rom = bytearray(8192)
    if tiles:
        for i, tile in enumerate(tiles[:512]):
            for j in range(16):
                if j < len(tile):
                    chr_rom[i * 16 + j] = tile[j]
    else:
        # Generate demo pattern: 512 tiles with checkerboard/box/diagonal/solid
        for ti in range(512):
            base = ti * 16
            pattern = ti % 4
            for y in range(8):
                lo, hi = 0, 0
                for x in range(8):
                    v = 0
                    if pattern == 0:      v = 1 if (x + y) % 2 == 0 else 0
                    elif pattern == 1:    v = 1 if 1 < x < 6 and 1 < y < 6 else 0
                    elif pattern == 2:    v = 1 if x == y or x == 7 - y else 0
                    else:                 v = 1 if x < 4 else 0
                    if v & 1: lo |= (1 << (7 - x))
                    if v & 2: hi |= (1 << (7 - x))
                chr_rom[base + y] = lo
                chr_rom[base + y + 8] = hi

    # ── Metadata marker (for --extract) ──
    marker_ofs = -(6 + 3 + 2 + 4)
    prg[marker_ofs:marker_ofs+3] = b'UF2'
    prg[marker_ofs+3] = bs_len & 0xFF
    prg[marker_ofs+4] = (bs_len >> 8) & 0xFF
    struct.pack_into('<I', prg, marker_ofs+5, len(uf2_data))

    # ── iNES Header ──
    h = bytearray(16)
    h[0:4] = b'NES\x1a'
    h[4] = prg_banks & 0xFF
    h[5] = 1  # CHR: 1 x 8KB
    h[6] = 1 | ((mapper & 0x0F) << 4)   # bit 0: vertical mirror, bits 4-7: mapper lower nibble
    h[7] = (mapper >> 4) & 0x0F          # bits 0-3: mapper upper nibble

    return bytes(h), bytes(prg), bytes(chr_rom), mapper_name


# ── Extract ──────────────────────────────────────────────────────────
def extract_rom(path):
    """Extract UF2 payload from a .nes file. Writes <name>.bin."""
    with open(path, 'rb') as f:
        d = f.read()
    if d[:4] != b'NES\x1a':
        print("Error: not a valid .nes file"); sys.exit(1)

    prg_banks = d[4]
    prg_size = prg_banks * 16384
    prg = d[16:16+prg_size]

    # Locate marker
    marker = prg[-15:-12]
    if marker != b'UF2':
        print("Error: no UF2 metadata marker found in .nes")
        print("  (This ROM was not created by this converter)")
        sys.exit(1)

    data_ofs = prg[-12] + 256 * prg[-11]
    data_size = struct.unpack_from('<I', prg, -10)[0]

    if data_ofs + data_size > prg_size:
        print("Error: metadata out of range"); sys.exit(1)

    raw = prg[data_ofs:data_ofs+data_size]
    base = os.path.splitext(os.path.basename(path))[0]
    out = f"{base}.bin"
    with open(out, 'wb') as f:
        f.write(raw)
    print(f"Extracted {len(raw)} bytes -> {out}")


# ── Entry ───────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("UF2 → NES 1-to-1 Converter")
        print(f"  python {os.path.basename(__file__)} <input.uf2> [output.nes]")
        print(f"  python {os.path.basename(__file__)} <input.uf2> [output.nes] --scan")
        print(f"  python {os.path.basename(__file__)} --extract <input.nes>")
        sys.exit(0)

    # Check for extract mode
    if len(sys.argv) >= 3 and sys.argv[1] == '--extract':
        extract_rom(sys.argv[2])
        return

    inp = sys.argv[1]
    base = os.path.splitext(os.path.basename(inp))[0]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else f"{base}.nes"
    scan = '--scan' in sys.argv

    if not os.path.exists(inp):
        print(f"Error: file not found: {inp}"); sys.exit(1)

    binary = parse_uf2(inp)

    pals, tiles = scan_assets(binary)
    if scan:
        print(f"  Palette candidates: {len(pals)}")
        for a, p in pals[:3]:
            print(f"    @ ${a:05X}: [{' '.join(f'${b:02X}' for b in p[:8])}]")
        print(f"  Tile candidates: {len(tiles)}")
    else:
        print(f"  Palettes: {len(pals)}, Tiles: {len(tiles)}")

    header, prg, chr_rom, mapper_name = build_rom(binary, pals, tiles)

    with open(out, 'wb') as f:
        f.write(header)
        f.write(prg)
        f.write(chr_rom)

    size = os.path.getsize(out)
    print(f"Written: {out} ({size} bytes)")
    print(f"  Format: iNES ({mapper_name}, {len(prg)//1024}KB PRG + 8KB CHR)")
    print(f"  UF2 payload: {len(binary)} bytes embedded 1:1 in PRG ROM")
    print(f"  Use --extract <file.nes> to recover raw binary")

if __name__ == '__main__':
    main()
