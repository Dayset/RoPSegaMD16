# Official Sega Genesis manual — transcript (uploaded by Dayset)

Source: a transcript of the official Rings of Power Sega Genesis manual,
uploaded by Dayset 2026-11-10 (`rings_of_power_sega_guide__1__2_0o3s.txt`,
150 lines). This file summarises it and reproduces only the DATA (rates,
costs, controls) — the full transcript is the source file, kept in
`~/workspace/user/files/`. The manual is the OFFICIAL source for the
travel/consumption model: it confirms the fan Transport guide's rates and
adds the on-foot per-terrain table. All of it is player-facing documentation:
hypotheses for #007/#020 until the ROM routine is located, never evidence
on its own.

## Travel & Terrain — rations consumed per mile by a party of 6 (on foot)

| Terrain | Food | Water |
|---------|------|-------|
| Road    | 1    | 1     |
| Swamp   | 8    | 4     |
| Desert  | 7    | 5     |
| Ice     | 4    | 3     |
| Grass   | 4    | 2     |

Desert is the thirstiest on foot (5 water/mile); swamp is the hungriest
(8 food/mile). This is the "formula" Dayset described: consumption depends
on the cell (terrain) — walking on sand (desert) consumes more water.

## Vehicles

| Vehicle | Where it goes | Food / Water per mile | Notes |
|---------|---------------|----------------------|-------|
| Dino    | Most land except forest/water | Road 1/1, other 3/1 | Abandoning it causes it to run away |
| Boat    | Narrow and deep waters | Shallow 1/1, deep 5/20 | Fresh water used rapidly at sea; summon via Boat Stone |
| Ship    | Deep water only | Deep 1/1 + gold passage | Fast; equipped with cannons; paid via passage rates |
| Dragon  | Flies over everything | All terrain 40/40 | Fastest travel; must land in clearings; summon via Dragon Stone |
| Gateway | Teleport | — | 8-squared pads surrounded by statues; requires a Gate Stone; use a Flip Stone to find the nearest Gateway |

Each vessel gives different speed and properties and a different
food/water cost per cell — the consumption model is vessel × terrain cell.
The dragon (wyvern) is the most expensive by far (40/40 everywhere), which
is why the Genesis Temple article says it is rarely used.

## CAMP

Rest to regain 50% strength and magic. Consumes **100 food and 100 water
rations**. Speeds up time. (Main Menu → CAMP.)

## Controls (Outside / overworld mode)

- D-Pad: move / select.
- A: AUTO MODE / FIRE — travel forward automatically (foot or boat); fire
  cannons (on ship) or breathe fire (on Dino or Dragon).
- B: ZOOM / ENTER — zoom in on the current location, or enter a building
  or vehicle. Zooming is not possible next to a building door whose
  description is on-screen. Press B to ZOOM and hide from threatening
  ships, Dinos, or Dragons on the overworld.
- C: STOP / EXIT — stop Auto Mode, or exit a vehicle.
- START: Main Menu.
- Shortcuts: A+START = Inventory; B+START = Map (must have a map);
  C+START = Search.

Inside mode: A = MORE (scroll text), B = ACT (look/take/open/climb),
C = TALK. B+START = FIGHT in TALK mode.

## Getting around

- Auto Mode: on foot paths, D-Pad in your direction and press A to walk
  automatically until a city or intersection. For boats, press A to follow
  streams automatically until hitting land or pressing C.
- Vehicles: face and press B to board, press C to exit. Dragons/Dinos
  require clear, flat land.

## Main Menu

INVEN (Goods, Items, Papers, Keys, Rings), SPELLS, PARTY (level, XP, HP/MP
bars), SEARCH (full report on a building; with a Sextant, longitude/latitude),
MAP (full-screen map, requires a map item; coordinates with a Sextant),
CAMP, SYSTEM (Help toggles, Quit, Load, Save (1 slot), Combat mode toggle
Manual vs Auto, Direct/Diags D-pad configurations, Music test).

## Combat (manual vs auto)

Combat mode is set via SYSTEM before battle. Manual: spell menu each turn.
Automatic: party members choose their own spells; hold A at the start of a
member's turn to override manually. Damage: shadows indicate alignment
(Blue = Party, Orange = Enemy); bars diminish with damage. If Strength hits
0, the character dies. If Magic hits 0, only Tier 1 spells can be cast.
Fight Menu (START during combat): Flee (takes up an attack round; enemies
attack unopposed), Mood (Berzrk max damage/MP, Advnce, Hold, Wary
conservative/low MP).

## Quick tips (selection)

- Save before healing; reloading can preserve stats.
- If HP drops below 25%, saving and reloading automatically restores it
  to 25%.
- Inns (Sleep/Meals) are cheaper than Temples (Heal/Power) at low levels.
- Travel by day to avoid large roving bands of thieves.
- Pay tax collectors unless your party is extremely strong.
- Harming townspeople drops local opinion; leave town for a few days to
  cool off.
- Keep wealth in trade goods to avoid high cathedral resurrection fees.
- Always have a Boat Stone when using Gate Stones so you don't get
  stranded.
- Lost limbs require a Temple visit; Camp rest will not restore maximum
  health potential.
- Use CAMP inside a building to exit to the overworld quickly.

## The Six Arts (summary)

1. Separation (Knights): rend objects/people. Symbol: Broken Sword. Heavy
   armor and broadswords.
2. Summoning (Conjurers): call perfect forms from other planes.
(The transcript ends mid-list here; the remaining four arts are in the
full transcript.)

## Open / to verify against the ROM

- The food/water consumption routine itself is NOT yet located (#007).
  The manual's rates are the hypothesis to verify: on-foot per-terrain
  (Road 1/1, Swamp 8/4, Desert 7/5, Ice 4/3, Grass 4/2) and per-vessel
  (Dino road 1/1 other 3/1, Boat shallow 1/1 deep 5/20, Ship deep 1/1 +
  gold, Dragon 40/40). The routine should read the terrain cell
  (`$5EDC4` type?) and the vessel state. See the food/water investigation
  (2026-11-10).
- CAMP's 100 food / 100 water cost and the 50% strength/magic regain are
  manual claims to verify in code.
