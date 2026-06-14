// NES Export - Test Example
// A simple MakeCode Arcade game that exports to NES

namespace player {
    let x = 80;
    let y = 60;
    let vx = 1;
    let vy = 1;
}

// Initialize NES export
nes.setPalette(NesPalette.Original);
nes.setMapper(NesMapper.NROM);
nes.setMirroring(NesMirroring.Horizontal);

// Create player sprite (8x8)
const playerImg = img`
. . . . . . . .
. . 1 1 1 1 . .
. 1 1 1 1 1 1 .
. 1 2 2 2 2 1 .
. 1 2 2 2 2 1 .
. 1 1 1 1 1 1 .
. . 1 1 1 1 . .
. . . . . . . .
`;

// Create block sprite (8x8)
const blockImg = img`
2 2 2 2 2 2 2 2
2 1 1 1 1 1 1 2
2 1 2 2 2 2 1 2
2 1 2 2 2 2 1 2
2 1 2 2 2 2 1 2
2 1 2 2 2 2 1 2
2 1 1 1 1 1 1 2
2 2 2 2 2 2 2 2
`;

// Add sprites to NES CHR ROM
nes.addSprite(playerImg, 0);
nes.addSprite(blockImg, 1);

// Build a simple nametable
for (let y = 0; y < 30; y++) {
    for (let x = 0; x < 32; x++) {
        if (y === 0 || y === 29 || x === 0 || x === 31) {
            nes.setTile(x, y, 1); // walls
        } else {
            nes.setTile(x, y, 0); // empty
        }
    }
}

game.onUpdateInterval(500, function () {
    // Bounce the player
    player.x += player.vx * 2;
    player.y += player.vy * 2;
    if (player.x >= 152 || player.x <= 8) player.vx *= -1;
    if (player.y >= 112 || player.y <= 8) player.vy *= -1;
});

controller.A.onEvent(ControllerButtonEvent.Pressed, function () {
    // Export NES data when A is pressed
    const data = nes.exportData();
    game.showLongText("NES data exported! Use the converter to make a .nes file", DialogLayout.Center);
    nes.logInfo();
});

controller.B.onEvent(ControllerButtonEvent.Pressed, function () {
    // Toggle palette
    const pals = [NesPalette.Original, NesPalette.Vivid, NesPalette.Pico8, NesPalette.GameBoy];
    const idx = Math.floor(Math.random() * pals.length);
    nes.setPalette(pals[idx]);
    game.showLongText("Switched palette!", DialogLayout.Center);
});
