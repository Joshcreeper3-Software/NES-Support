# NES Export for MakeCode Arcade

Export your MakeCode Arcade games to NES ROM format (.nes) that runs in any NES emulator!

## Usage

### 1. Install the extension
Add `pxt-nes-export` to your MakeCode Arcade project via Extensions.

### 2. Add NES blocks to your game

Use the blocks in the **NES Export** category:

| Block | Description |
|-------|-------------|
| `set NES palette to [type]` | Choose color palette (Original, Vivid, Pico-8, Game Boy) |
| `set palette index [i] to color [c]` | Customize individual palette colors |
| `set NES mapper to [mapper]` | Select mapper (NROM, MMC1, UNROM, CNROM) |
| `set mirroring to [mode]` | Set nametable mirroring |
| `set tile at (x,y) to [index]` | Place tiles in the nametable |
| `convert [img] to CHR data` | Convert a sprite to NES pattern table format |
| `add sprite [img] to CHR ROM as tile [n]` | Add sprite to ROM at specific tile index |
| `export NES ROM data` | Generate the ROM data as JSON |
| `log NES ROM info` | Print ROM details to console |
| `clear NES data` | Reset all NES export data |

### 3. Generate the ROM

In your game, call `export NES ROM data` and copy the JSON output.

### 4. Convert to .nes

```bash
python nes_rom.py export.json mygame.nes
```

## Example

```typescript
// Set up NES export
nes.setPalette(NesPalette.Original)
nes.setMapper(NesMapper.NROM)
nes.setMirroring(NesMirroring.Horizontal)

// Add sprites
let player = sprites.create(img`...`, SpriteKind.Player)
nes.addSprite(player.image, 0)

// Export
let romData = nes.exportData()
nes.logInfo()
```

## Converter Tool

`nes_rom.py` converts the JSON export to a .nes ROM file.

Requires Python 3. No additional dependencies.

## Supported Mappers

- **NROM (Mapper 0)** - 16-32KB PRG, 8KB CHR
- **MMC1 (Mapper 1)** - Up to 256KB PRG, 128KB CHR
- **UNROM (Mapper 2)** - 128-256KB PRG, 8KB CHR
- **CNROM (Mapper 3)** - 16-32KB PRG, 32KB CHR

## License

MIT

for PXT/arcade
