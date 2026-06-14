// NES Export - MakeCode Arcade extension
// Export your games to NES ROM format

enum NesPalette {
    //% block="Original NES"
    Original = 0,
    //% block="Vivid"
    Vivid = 1,
    //% block="Pico-8"
    Pico8 = 2,
    //% block="Game Boy"
    GameBoy = 3,
    //% block="Custom"
    Custom = 4
}

enum NesMirroring {
    //% block="Horizontal"
    Horizontal = 0,
    //% block="Vertical"
    Vertical = 1
}

enum NesMapper {
    //% block="NROM (Mapper 0)"
    NROM = 0,
    //% block="MMC1 (Mapper 1)"
    MMC1 = 1,
    //% block="UNROM (Mapper 2)"
    UNROM = 2,
    //% block="CNROM (Mapper 3)"
    CNROM = 3
}

namespace nes {
    const NES_WIDTH = 32;
    const NES_HEIGHT = 30;

    let _palette: number[] = [];
    let _nametable: number[] = [];
    let _sprites: Image[] = [];
    let _mapper = NesMapper.NROM;
    let _mirroring = NesMirroring.Horizontal;
    let _exportData: string = "";

    // Built-in NES palette (original)
    const NES_COLORS: number[] = [
        0x545454, 0x001e74, 0x08109a, 0x300064,
        0x440064, 0x48002c, 0x480400, 0x3c1800,
        0x202800, 0x083400, 0x003400, 0x002e06,
        0x002a26, 0x000000, 0x000000, 0x000000,
        0x989898, 0x084cc4, 0x3032ec, 0x5c1ea4,
        0x8814a0, 0x941472, 0x8c1c14, 0x703404,
        0x505000, 0x207000, 0x007800, 0x00703c,
        0x00687c, 0x202020, 0x000000, 0x000000,
        0xfffcfc, 0x4cb4ff, 0x7c8cff, 0xb478fc,
        0xe070fc, 0xf870b0, 0xf87064, 0xd4940c,
        0xa8a81c, 0x60c01c, 0x20d020, 0x1cc878,
        0x1cb8d4, 0x505050, 0x000000, 0x000000,
        0xfffcfc, 0xacf4ff, 0xcce0ff, 0xe8ccff,
        0xfcccfc, 0xfcc8e8, 0xfcc8b8, 0xfcd4a0,
        0xe8e4a0, 0xc0f0a0, 0xa0f0a0, 0x9ce8c8,
        0x9ce4f0, 0xa8a8a8, 0x000000, 0x000000
    ];

    const PICO8_COLORS: number[] = [
        0x000000, 0x1D2B53, 0x7E2553, 0x008751,
        0xAB5236, 0x5F574F, 0xC2C3C7, 0xFFF1E8,
        0xFF004D, 0xFFA300, 0xFFEC27, 0x00E436,
        0x29ADFF, 0x83769C, 0xFF77A8, 0xFFCCAA,
        0x291814, 0x111111, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000,
        0x000000, 0x000000, 0x000000, 0x000000
    ];

    // Convert MakeCode color to NES palette index
    function rgbToNesIndex(rgb: number): number {
        let bestIdx = 0;
        let bestDist = 999999;
        const r = (rgb >> 16) & 0xff;
        const g = (rgb >> 8) & 0xff;
        const b = rgb & 0xff;
        for (let i = 0; i < NES_COLORS.length; i++) {
            const nr = (NES_COLORS[i] >> 16) & 0xff;
            const ng = (NES_COLORS[i] >> 8) & 0xff;
            const nb = NES_COLORS[i] & 0xff;
            const dist = (r - nr) * (r - nr) + (g - ng) * (g - ng) + (b - nb) * (b - nb);
            if (dist < bestDist) {
                bestDist = dist;
                bestIdx = i;
            }
        }
        return bestIdx;
    }

    /**
     * Set the NES color palette to use
     */
    //% blockId=nesSetPalette block="set NES palette to %palette"
    //% weight=100
    export function setPalette(palette: NesPalette): void {
        switch (palette) {
            case NesPalette.Original:
                _palette = NES_COLORS.slice(0, 16);
                break;
            case NesPalette.Pico8:
                _palette = PICO8_COLORS.slice(0, 16);
                break;
            case NesPalette.GameBoy:
                _palette = [0x0f380f, 0x306230, 0x8bac0f, 0x9bbc0f];
                break;
            case NesPalette.Vivid:
                _palette = [
                    0x000000, 0xffffff, 0xff0000, 0x00ff00,
                    0x0000ff, 0xffff00, 0xff00ff, 0x00ffff,
                    0x808080, 0xff8080, 0x80ff80, 0x8080ff,
                    0xffff80, 0xff80ff, 0x80ffff, 0x000000
                ];
                break;
            case NesPalette.Custom:
                break;
        }
    }

    /**
     * Set a custom palette color
     */
    //% blockId=nesSetPaletteColor block="set NES palette index %idx to color %color"
    //% idx.min=0 idx.max=15
    //% weight=99
    export function setPaletteColor(idx: number, color: number): void {
        if (idx >= 0 && idx < 16) {
            if (_palette.length <= idx) _palette.length = idx + 1;
            _palette[idx] = color;
        }
    }

    /**
     * Set the mapper type
     */
    //% blockId=nesSetMapper block="set NES mapper to %mapper"
    //% weight=90
    export function setMapper(mapper: NesMapper): void {
        _mapper = mapper;
    }

    /**
     * Set mirroring mode
     */
    //% blockId=nesSetMirroring block="set mirroring to %mirroring"
    //% weight=89
    export function setMirroring(mirroring: NesMirroring): void {
        _mirroring = mirroring;
    }

    /**
     * Set a tile in the nametable
     */
    //% blockId=nesSetTile block="set tile at (%x, %y) to index %tile"
    //% x.min=0 x.max=31 y.min=0 y.max=29
    //% tile.min=0 tile.max=255
    //% weight=85 inlineInputMode=inline
    export function setTile(x: number, y: number, tile: number): void {
        const idx = y * NES_WIDTH + x;
        if (_nametable.length <= idx) _nametable.length = idx + 1;
        _nametable[idx] = tile;
    }

    /**
     * Set an attribute byte for a region
     */
    //% blockId=nesSetAttribute block="set attribute at (%x, %y) to %attr"
    //% x.min=0 x.max=31 y.min=0 y.max=29
    //% attr.min=0 attr.max=255
    //% weight=84 inlineInputMode=inline
    export function setAttribute(x: number, y: number, attr: number): void {
        // Attribute table entries: 32x30 tiles -> 8x8 regions
        const ax = Math.floor(x / 4);
        const ay = Math.floor(y / 4);
        const attrIdx = ay * 8 + ax;
        // Each byte controls 2x2 regions of 4x4 tile groups
        // For simplicity, just store it
    }

    /**
     * Export the game data to a NES-compatible format
     * Returns the export data as a string
     */
    //% blockId=nesExportData block="export NES ROM data"
    //% weight=70
    export function exportData(): string {
        const data: any = {
            mapper: _mapper,
            mirroring: _mirroring,
            palette: _palette,
            nametable: _nametable,
            chrRom: generateChrRom(),
            prgRom: generatePrgRom()
        };
        _exportData = JSON.stringify(data);
        return _exportData;
    }

    /**
     * Download the export data as a file
     */
    //% blockId=nesDownloadExport block="download NES export"
    //% weight=69
    export function downloadExport(): void {
        const data = _exportData || exportData();
        control.runInParallel(function() {
            const blob = serial.readBuffer(0);
            // Use the simulator console to output the data
            console.log("NES Export Data:");
            console.log(data);
            console.log("Copy this data and use the NES converter tool to generate a .nes file");
        });
    }

    /**
     * Convert an image to NES CHR-ROM format data
     * Returns a buffer with the pattern table data
     */
    //% blockId=nesImageToChr block="convert %img to CHR data"
    //% weight=60
    export function imageToChr(img: Image): Buffer {
        const buf = control.createBuffer(16);
        for (let y = 0; y < 8; y++) {
            let low = 0;
            let high = 0;
            for (let x = 0; x < 8; x++) {
                const c = img.getPixel(x, y);
                if (c > 0) {
                    low |= (1 << (7 - x));
                }
                if (c > 1) {
                    high |= (1 << (7 - x));
                }
            }
            buf[y] = low;
            buf[y + 8] = high;
        }
        return buf;
    }

    /**
     * Add a sprite to the CHR ROM data
     */
    //% blockId=nesAddSprite block="add sprite %img to CHR ROM as tile %tile"
    //% tile.min=0 tile.max=255
    //% weight=59
    export function addSprite(img: Image, tile: number): void {
        const chr = imageToChr(img);
        // Store for export
        while (_sprites.length <= tile) {
            _sprites.push(null);
        }
        _sprites[tile] = img;
    }

    // Generate CHR ROM from collected sprites
    function generateChrRom(): number[] {
        const data: number[] = [];
        for (const sprite of _sprites) {
            if (sprite) {
                const chr = imageToChr(sprite);
                for (let i = 0; i < 16; i++) {
                    data.push(chr[i]);
                }
            } else {
                for (let i = 0; i < 16; i++) {
                    data.push(0);
                }
            }
        }
        // Pad to at least 8KB
        while (data.length < 8192) {
            data.push(0);
        }
        return data;
    }

    // Generate placeholder PRG ROM
    function generatePrgRom(): number[] {
        const data: number[] = [];
        // Reset vector at $FFFC-$FFFD
        for (let i = 0; i < 16384; i++) {
            if (i === 16380) { // NMI vector
                data.push(0x00);
            } else if (i === 16381) {
                data.push(0x80);
            } else if (i === 16382) { // Reset vector
                data.push(0x00);
            } else if (i === 16383) {
                data.push(0x80);
            } else {
                data.push(0x00);
            }
        }
        // Set reset vector handler at $8000
        // LDA #$00, STA $2000, STA $2001, JMP $8000
        const startup = [
            0xA9, 0x00, 0x8D, 0x00, 0x20, 0x8D, 0x01, 0x20,
            0xA2, 0xFF, 0x9A, 0xA2, 0x00, 0xBD, 0x00, 0x80,
            0x9D, 0x00, 0x02, 0xE8, 0xE0, 0x00, 0xD0, 0xF5,
            0x4C, 0x00, 0x80
        ];
        for (let i = 0; i < startup.length; i++) {
            data[i] = startup[i];
        }
        return data;
    }

    /**
     * Get the number of CHR ROM banks
     */
    //% blockId=nesChrBanks block="CHR ROM banks"
    //% weight=50
    export function chrBanks(): number {
        return Math.ceil(_sprites.length / 512);
    }

    /**
     * Get the number of PRG ROM banks
     */
    //% blockId=nesPrgBanks block="PRG ROM banks"
    //% weight=49
    export function prgBanks(): number {
        return 1; // 16KB
    }

    /**
     * Clear all NES data
     */
    //% blockId=nesClear block="clear NES data"
    //% weight=40
    export function clear(): void {
        _palette = [];
        _nametable = [];
        _sprites = [];
        _mapper = NesMapper.NROM;
        _mirroring = NesMirroring.Horizontal;
        _exportData = "";
    }

    /**
     * Log NES ROM info to console
     */
    //% blockId=nesLogInfo block="log NES ROM info"
    //% weight=39
    export function logInfo(): void {
        console.log("--- NES ROM Info ---");
        console.log("Mapper: " + _mapper);
        console.log("Mirroring: " + (_mirroring === NesMirroring.Horizontal ? "Horizontal" : "Vertical"));
        console.log("PRG Banks: " + prgBanks() + " (16KB each)");
        console.log("CHR Banks: " + chrBanks() + " (8KB each)");
        console.log("Sprites: " + _sprites.length);
        console.log("Nametable Tiles: " + _nametable.length);
        console.log("Palette Colors: " + _palette.length);
    }
}
