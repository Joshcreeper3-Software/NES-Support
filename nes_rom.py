#!/usr/bin/env python3
"""
NES ROM Builder - Converts MakeCode Arcade NES Export data to .nes files
Usage: python nes_rom.py export.json output.nes
"""

import json
import sys
import struct

def build_ines_header(mapper, mirroring, prg_banks, chr_banks):
    """Build iNES header (16 bytes)"""
    header = bytearray(16)
    header[0:4] = b'NES\x1a'  # Magic
    header[4] = prg_banks & 0xff       # PRG ROM size (16KB units)
    header[5] = chr_banks & 0xff       # CHR ROM size (8KB units)
    # Flags 6: mirroring, battery, trainer, four-screen
    flags6 = 0
    if mirroring == 1:  # Vertical
        flags6 |= 1
    header[6] = flags6
    # Flags 7: mapper low nibble, VS, PlayChoice
    header[7] = (mapper & 0x0f) << 4
    # Flags 8: mapper high nibble
    header[8] = (mapper >> 4) & 0x0f
    return header

def build_prg_rom(data):
    """Build PRG ROM from export data"""
    prg = bytearray(16384)  # Default 16KB
    # Copy startup code
    startup = bytes(data.get('prgRom', []))
    if len(startup) > 0:
        prg[0:len(startup)] = startup[:len(prg)]
    # Set reset vector ($FFFC) to $8000
    prg[0x7ffc] = 0x00
    prg[0x7ffd] = 0x80
    # Set NMI vector ($FFFA) to $8000
    prg[0x7ffa] = 0x00
    prg[0x7ffb] = 0x80
    return prg

def build_chr_rom(data):
    """Build CHR ROM from export data"""
    chr_data = data.get('chrRom', [])
    chr_rom = bytearray(chr_data)
    # Pad to 8KB
    while len(chr_rom) < 8192:
        chr_rom.append(0)
    return chr_rom[:8192]

def convert(export_json, output_path):
    """Convert export JSON to .nes ROM file"""
    with open(export_json, 'r') as f:
        data = json.load(f)

    mapper = data.get('mapper', 0)
    mirroring = data.get('mirroring', 0)

    # Build PRG and CHR
    prg_rom = build_prg_rom(data)
    chr_rom = build_chr_rom(data)

    prg_banks = len(prg_rom) // 16384
    chr_banks = len(chr_rom) // 8192

    # Build header
    header = build_ines_header(mapper, mirroring, prg_banks, chr_banks)

    # Write output
    with open(output_path, 'wb') as f:
        f.write(header)
        f.write(prg_rom)
        f.write(chr_rom)

    print(f"ROM written to {output_path}")
    print(f"  PRG: {prg_banks} x 16KB")
    print(f"  CHR: {chr_banks} x 8KB")
    print(f"  Mapper: {mapper}")
    print(f"  Mirroring: {'Vertical' if mirroring == 1 else 'Horizontal'}")
    print(f"  Total size: {os.path.getsize(output_path)} bytes")

def main():
    if len(sys.argv) < 2:
        print("Usage: python nes_rom.py <export.json> [output.nes]")
        print("")
        print("Steps:")
        print("  1. In MakeCode Arcade, add the NES Export extension")
        print("  2. Use 'export NES ROM data' block to get JSON")
        print("  3. Save the JSON to a file")
        print("  4. Run this converter: python nes_rom.py export.json game.nes")
        sys.exit(1)

    export_json = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else export_json.replace('.json', '.nes')

    import os
    convert(export_json, output_path)

if __name__ == '__main__':
    main()
