![minecRAFT](/minecRAFT-bedrock.png)

# minecRAFT-bedrock
Raft but in Minecraft, for Bedrock Edition. A proof of concept ported from the Java map,
[minecRAFT](https://github.com/kirbycope/minecRAFT).

You start on a 2x2 raft of jungle planks in an ocean that never ends, holding a fishing rod and a Throwable
Anchor. Debris drifts past on the current: barrels, planks, palm leaves and plastic. Cast your line so the bobber
lands in its path, and whatever floats into it is caught and rides on the line. Reel in to collect it. Bruce the
dolphin swims nearby.

| Flotsam | Looks like | Reeling it in gives |
| --- | --- | --- |
| Barrel | a small barrel | 4 to 6 rolls on Raft's barrel table: planks, sugar cane (plastic), jungle leaves (palm leaves), iron nuggets (scrap), string (rope), cobblestone (stone), beetroot, potato |
| Plank | a jungle plank | 1 jungle planks |
| Palm leaf | a clump of leaves | 1 jungle leaves |
| Plastic | sugar cane | 1 sugar cane |

Normal fishing still works alongside it, and the rod still hooks and pulls in mobs as it always has on Bedrock.

### The first island
A couple of minutes into a new world, Raft's
[Small Island 1](https://raft.fandom.com/wiki/Small_Tropical_Islands) comes over the horizon and drifts toward the
raft: a rock pillar with an abandoned hut on top, a tiered rock mass with grassy ledges, a sloping sandy tail, four
palm trees, two mango trees, a pineapple bush, two watermelons, five flowers of each colour, and under the water a
sandy shelf with iron and copper ore, clay, seagrass, kelp and two sea pickles (the giant clams). It passes
alongside the raft and, left alone, drifts away again.

Throw your anchor while it is alongside and the raft stops, so the island does too: it becomes solid ground to climb,
chop, mine and explore. The hut's chest holds a roll on Raft's Mountain Loot Box table. When you are done, break the
anchor's post: the raft drifts on and the island floats away behind you.

### The Throwable Anchor
Raft's [Throwable Anchor](https://raft.fandom.com/wiki/Throwable_Anchor): one item, used once.

1. Use it on the raft. A fence post goes up with the anchor tied to it by a lead.
2. Use the post (or the anchor) to throw it. It splashes down off the edge and the raft is anchored.
3. Break the post to pick it up. That destroys it, as in Raft, and the raft drifts again.

You start with one. More are crafted at a crafting table from 2 jungle planks, 3 string and 4 cobblestone (Raft's
recipe is 2 planks, 4 rope and 4 stone, one more than a crafting grid holds).

## How it works
- **The ocean** is the [void world](https://github.com/kirbycope/void-world-bedrock)'s flat world settings with
  its empty layer list swapped for one barrier layer and 127 layers of water in a Deep Ocean biome, so the game
  generates the ocean itself, endlessly, as you look around.
- **The raft never moves.** Moving placed blocks can only be done a block at a time, which is what made the
  Java maps' moving builds jerky. The ocean looks the same everywhere, so the current is shown by moving the
  debris past the raft instead.
- **The debris** is display entities from the [Display add-on](https://github.com/kirbycope/display-bedrock),
  teleported a short way downstream every tick by `scripts/main.js`. The game smooths an entity's movement
  between updates, so the debris glides rather than steps.
- **Catching** is the same script: every tick it finds each fishing hook, takes any debris within 1.6 blocks of
  it onto the line, and moves it with the hook. When the hook disappears because you reeled in, the loot goes
  to whoever cast it.
- **The island** is built by `tools/island.py` as voxels and written to `scripts/island1.js` twice over: every
  block it is made of (7,973, inside included), and the 767 Display entities that draw it while it drifts (only
  blocks with an exposed face, no deeper than two below the surface, with runs of rock merged into 2x2x2 cubes
  drawn at scale 2). The entities are spawned a slice at a time as each comes within 56 blocks, so it rises over
  the horizon, and move with the current like the debris. When the raft is anchored the island settles onto the
  next whole block and the script places the real blocks (only into water or air, so nothing built is
  overwritten), then removes the entities. Casting off reverses it: every block still as it was placed becomes an
  entity again, the blocks go back to ocean, plants first so none pop off as items, and anything left in the hut's
  chest is dropped. Both steps wait until the island's chunks are loaded.

The tuning lives at the top of each script: `main.js` (drift speed, the stream, the hook's reach, Bruce's leash),
`island.js` (where the island passes, how far out it appears, when the first one comes) and `anchor.js` (how far
the anchor is thrown and how deep it sinks). To change the island itself, edit `tools/island.py` and run it.

## Installation
1. Download `minecRAFT-bedrock.mctemplate` from the [latest release](https://github.com/kirbycope/minecRAFT-bedrock/releases/latest)
1. Double-click the `.mctemplate` file
1. Create a New World using the template
    - "Play" > "Create New" > Scroll down to "Imported Templates" (Select "See More" if necessary)

## Repository layout
| Path | What it is |
| --- | --- |
| `world/` | The world template's own files: `manifest.json`, `level.dat` (the void world with ocean layers), `levelname.txt`, `world_icon.jpeg` |
| `development_behavior_packs/minecraft_raft/` | The behavior pack: `scripts/main.js` (raft, current, hook, Bruce), `scripts/island.js` (the island encounter), `scripts/anchor.js` (the Throwable Anchor), `scripts/island1.js` (generated), the anchor item, its recipe, and the anchor and knot entities |
| `development_resource_packs/minecraft_raft/` | The resource pack: the anchor's icon, model and texture, and the lead knot's |
| `tools/island.py` | Builds Small Island 1 into `scripts/island1.js`; `--preview` also draws top and side views into `build/` |
| `tools/build_addon.py` | Builds the `.mctemplate` |

The Display add-on is not copied into this repository. The build takes its packs from a checkout of
[display-bedrock](https://github.com/kirbycope/display-bedrock), by default the one beside this repository.

## Developing on the local server
The world runs on the Bedrock Dedicated Server in `C:\GitHub\bedrock-server` as `worlds/minecRAFT`, with
junctions to this repository's two packs and to display-bedrock's two packs, so an edit here is live on the
next server restart. That world's `level.dat` differs from `world/level.dat` in one way: it has the Beta APIs
experiment on, which the `bedrock-bridge` pack needs.

### Testing commands
| Command | Does |
| --- | --- |
| `/scriptevent raft:island start` | Brings the island now, from over the horizon |
| `/scriptevent raft:island start -24` | Brings it from just upstream of alongside, a few seconds away |
| `/scriptevent raft:island clear` | Removes the island, entities or blocks |
| `/scriptevent raft:island clear <x>` | Also removes island blocks left standing with the island at that x |
| `/scriptevent raft:anchor clear` | Removes the anchor, post and lead without breaking them |
| `/give @s raft:throwable_anchor` | Another anchor |

A resource pack change needs its manifest version bumped (and the world's `world_resource_packs.json` to match), or
the client keeps its cached copy. On the first join after a bump the client asks whether to download the server's
resource packs; take the download, or the anchor shows as an invisible item with a raw name.

## Releasing
Pushing a tag that starts with `v` (for example `git tag v0.1.0 && git push origin v0.1.0`) runs the Release
workflow in `.github/workflows/release.yml`, which checks out display-bedrock beside this repository, builds the
world template and attaches `minecRAFT-bedrock.mctemplate` to a GitHub Release.

To build it locally, run `python tools/build_addon.py`. It writes `build/minecRAFT-bedrock.mctemplate`, which
git ignores.
