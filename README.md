# UF2 to NES ROM Converter

Converts Raspberry Pi RP2040 UF2 firmware files into bootable .nes ROMs.
Extracts graphics data from the UF2 binary and packages it with real 6502
code into a valid iNES format ROM — runs on any NES emulator or flash cart.

## Usage

```bash
python uf2nes.py game.uf2 game.nes
python uf2nes.py game.uf2 game.nes --scan   # show what's detected
```

## How it works

1. **Parses UF2** — extracts 256-byte data blocks, reconstructs the binary
2. **Scans for assets** — finds palette data and sprite/tile patterns
3. **Generates 6502 code** — NES init, PPU setup, palette load, sprite DMA
4. **Wraps in iNES** — standard .nes file with header, PRG, and CHR ROM

The result is a fully bootable NES ROM that displays the extracted graphics.

## Requirements

- Python 3.6+

## Notes

- Best results with UF2 files from **MakeCode Arcade** RP2040 builds
- The ROM boots on any NES emulator (FCEUX, Mesen, Nestopia) or flash cart
- Mapper: NROM (Mapper 0), Mirroring: Horizontal

## License

MIT
