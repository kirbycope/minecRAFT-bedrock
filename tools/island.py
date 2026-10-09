"""Builds Raft's Small Island 1 as voxels and writes it to the behavior pack as scripts/island1.js.

Small Island 1, from https://raft.fandom.com/wiki/Small_Tropical_Islands: a rock pillar with an abandoned hut and a
Mountain Loot Box on top, a tiered rock mass with grassy ledges, a long sloping tail that runs down to a sandy tip,
2 mango trees, 4 palm trees, a pineapple plant, 2 watermelon plants, 5 flowers of each of the five colours, and
under the water a sandy shelf with metal ore, copper, sand, clay, stone, seaweed and 2 giant clams.

Local coordinates: x runs with the current (the island's long axis), z across it, and y = 0 is the top layer of
the ocean (world y 63), so y >= 1 is above water. Two lists come out:

- BLOCKS, every voxel of the island including its hidden inside, as [x, y, z, palette index]. These are what the
  island turns into when it anchors beside the raft, so it can be walked on, chopped and mined.
- DISPLAY, the Display add-on entities that draw the island while it drifts: only voxels with an exposed face and
  no deeper than DISPLAY_DEPTH, with runs of rock merged into 2x2x2 cubes (one entity drawn at scale 2) to keep
  the count down. As [x, y, z, type index, variant index, size], the corner of the cube, sorted
  downstream end first so the script can spawn each slice as it comes into range.

    python tools/island.py              # writes development_behavior_packs/minecraft_raft/scripts/island1.js
    python tools/island.py --preview    # also writes build/island1_top.png and build/island1_side.png
"""

import argparse
import json
import math
import os
import random

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "development_behavior_packs", "minecraft_raft", "scripts", "island1.js")
DISPLAY_DEPTH = -2   # voxels deeper than this are only seen once the island is real blocks

# block id, block states, Display entity type, Display variant, whether a 2x2x2 run of it may be one entity
PALETTE = {
    "stone": ("minecraft:stone", {}, "display:block", "stone", True),
    "andesite": ("minecraft:andesite", {}, "display:block", "stone_andesite", True),
    "moss": ("minecraft:moss_block", {}, "display:block", "moss_block", False),
    "sand": ("minecraft:sand", {}, "display:block", "sand", False),
    "clay": ("minecraft:clay", {}, "display:block", "clay", False),
    "iron_ore": ("minecraft:iron_ore", {}, "display:block", "iron_ore", False),
    "copper_ore": ("minecraft:copper_ore", {}, "display:block", "copper_ore", False),
    "palm_log": ("minecraft:jungle_log", {"pillar_axis": "y"}, "display:block", "log_jungle", False),
    "mango_log": ("minecraft:oak_log", {"pillar_axis": "y"}, "display:block", "log_oak", False),
    "palm_leaves": ("minecraft:azalea_leaves", {"persistent_bit": True}, "display:block", "azalea_leaves", False),
    "mango_leaves": ("minecraft:azalea_leaves_flowered", {"persistent_bit": True}, "display:block", "azalea_leaves_flowers", False),
    "melon": ("minecraft:melon_block", {}, "display:block", "melon_side", False),
    "planks": ("minecraft:oak_planks", {}, "display:block", "planks_oak", False),
    "red_wool": ("minecraft:red_wool", {}, "display:block", "wool_colored_red", False),
    "blue_wool": ("minecraft:blue_wool", {}, "display:block", "wool_colored_blue", False),
    "chest": ("minecraft:chest", {"minecraft:cardinal_direction": "south"}, "display:block", "chest_front", False),
    "red_flower": ("minecraft:poppy", {}, "display:block", "flower_rose", False),
    "blue_flower": ("minecraft:cornflower", {}, "display:block", "flower_cornflower", False),
    "yellow_flower": ("minecraft:dandelion", {}, "display:block", "flower_dandelion", False),
    "white_flower": ("minecraft:lily_of_the_valley", {}, "display:block", "flower_lily_of_the_valley", False),
    "black_flower": ("minecraft:wither_rose", {}, "display:block", "flower_wither_rose", False),
    "pineapple": ("minecraft:sweet_berry_bush", {"growth": 3}, "display:item", "sweet_berries", False),
    "ladder": ("minecraft:ladder", {"facing_direction": 5}, "display:block", "ladder", False),
    "seagrass": ("minecraft:seagrass", {}, None, None, False),
    "kelp": ("minecraft:kelp", {"kelp_age": 25}, None, None, False),   # fully grown, so it never grows past the island
    "clam": ("minecraft:sea_pickle", {"cluster_count": 3, "dead_bit": False}, None, None, False),
}
SOLID = {"stone", "andesite", "moss", "sand", "clay", "iron_ore", "copper_ore", "palm_log", "mango_log", "melon",
         "planks", "red_wool", "blue_wool", "chest", "palm_leaves", "mango_leaves"}
ROCK = {"stone", "andesite"}


def ellipse(x, z, cx, cz, rx, rz):
    return ((x - cx) / rx) ** 2 + ((z - cz) / rz) ** 2


def build() -> dict:
    rng = random.Random(1)
    v: dict[tuple[int, int, int], str] = {}

    # Above water, a top height for each column.
    top: dict[tuple[int, int], int] = {}
    for x in range(-2, 36):
        for z in range(-2, 18):
            h = None
            if ellipse(x, z, 3, 6, 2.7, 3.0) <= 1: h = 11                               # the pillar
            elif 5 <= x <= 8 and 4 <= z <= 8: h = 6                                     # the saddle between
            elif ellipse(x, z, 14, 7, 6.0, 5.2) <= 1:                                   # the main rock
                h = 12 if z >= 7 else 9 if z >= 4 else 5
                if x >= 18: h = min(h, 8)
            elif 18 <= x <= 32 and 4 <= z <= 9 - max(0, x - 26) // 2:                  # the tail, sloping to the water
                h = max(1, round(7 - (x - 18) * 6 / 13))
            elif 31 <= x <= 33 and 5 <= z <= 7: h = 1                                   # the hump at the tip
            elif 11 <= x <= 18 and 12 <= z <= 13: h = 1                                 # the beach on the far side
            if h is not None:
                top[(x, z)] = h

    # A walkable way up: from the tail onto the right of the main rock, then the ledges, then the top.
    for (x, z), h in {(19, 5): 7, (19, 6): 7, (18, 6): 8, (17, 6): 9, (16, 6): 9, (15, 6): 10, (15, 7): 11, (15, 8): 12,
                      (9, 5): 7, (8, 5): 6}.items():
        top[(x, z)] = h
    # Overhanging cap on the pillar, like the reference's flat-topped stack.
    cap = [(x, z) for x in range(0, 7) for z in range(2, 11) if ellipse(x, z, 3, 6, 3.4, 3.6) <= 1 and (x, z) not in top]

    for (x, z), h in top.items():
        for y in range(-1, h + 1):
            rock = "andesite" if rng.random() < 0.25 else "stone"
            v[(x, y, z)] = rock
        # surface: moss on ledges above the beach line, sand on the low tail and the beach
        if h <= 2: v[(x, h, z)] = "sand"
        elif h <= 3 and x >= 22: v[(x, h, z)] = "sand"
        else: v[(x, h, z)] = "moss" if h in (5, 8, 9, 12) or (x, z) in {(15, 7), (15, 6)} else v[(x, h, z)]
    for (x, z) in cap:
        for y in (10, 11):
            v[(x, y, z)] = "stone"
        v[(x, 11, z)] = "moss"

    # Under water, the shelf: the island's footprint grows with depth, more toward the tail, then tapers to a point.
    foot = set(top) | set(cap)
    for y in range(-2, -13, -1):
        depth = -y
        grow = min((depth - 1) * 0.9, 4.5) if depth <= 7 else max(4.5 - (depth - 7) * 1.0, 0)
        for x in range(-10, 44):
            for z in range(-10, 26):
                if (x, y, z) in v: continue
                d = min((math.hypot(x - fx, (z - fz) * 1.1) for fx, fz in foot if abs(x - fx) <= 8 and abs(z - fz) <= 8), default=99)
                reach = grow + (2.0 if x > 18 and depth >= 3 else 0) + (1.0 if z > 9 and depth >= 3 else 0) + rng.uniform(-0.6, 0.6)
                if d <= reach:
                    v[(x, y, z)] = "stone"
    # The shelf top is the first layer with nothing above it: sand there, clay in patches; boulders on it.
    for (x, y, z), b in list(v.items()):
        if y <= -2 and b in ROCK and (x, y + 1, z) not in v:
            v[(x, y, z)] = "clay" if rng.random() < 0.18 else "sand"
    for _ in range(9):
        bx, bz = rng.randint(-4, 38), rng.randint(-4, 20)
        floor = max((y for (x, y, z) in v if x == bx and z == bz), default=None)
        if floor is None or floor >= 0: continue
        for dx in (0, 1):
            for dz in (0, 1):
                for dy in (1, 2):
                    if (bx + dx, floor + dy, bz + dz) not in v and floor + dy <= -1:
                        v[(bx + dx, floor + dy, bz + dz)] = "andesite"

    def exposed(x, y, z):
        return any(v.get(n) not in SOLID for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)))

    # Ores on the rock walls just under the water: 7 metal ore and 5 copper, in pairs and threes like the game.
    walls = sorted(p for p, b in v.items() if b in ROCK and -6 <= p[1] <= -1 and exposed(*p))
    rng.shuffle(walls)
    for kind, n in (("iron_ore", 7), ("copper_ore", 5)):
        placed = 0
        for p in walls:
            if placed >= n: break
            if v[p] in ROCK:
                v[p] = kind; placed += 1
                q = (p[0], p[1] - 1, p[2])
                if placed < n and v.get(q) in ROCK and exposed(*q):
                    v[q] = kind; placed += 1

    plants: dict[tuple[int, int, int], str] = {}

    def ground(x, z):
        ys = [y for (xx, y, zz), b in v.items() if xx == x and zz == z and b in SOLID]
        return max(ys) if ys else None

    def palm(x, z, lean=(0, 0), height=6):
        g = ground(x, z)
        px, pz = x, z
        for i in range(1, height + 1):
            if i == height // 2 + 1: px, pz = px + lean[0], pz + lean[1]
            v[(px, g + i, pz)] = "palm_log"
        cy = g + height + 1
        v[(px, cy, pz)] = "palm_leaves"
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for r in (1, 2):
                v[(px + dx * r, cy, pz + dz * r)] = "palm_leaves"
            v[(px + dx * 3, cy - 1, pz + dz * 3)] = "palm_leaves"
        for dx, dz in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            v[(px + dx, cy, pz + dz)] = "palm_leaves"
            v[(px + dx * 2, cy - 1, pz + dz * 2)] = "palm_leaves"

    def mango(x, z):
        g = ground(x, z)
        for i in range(1, 4):
            v[(x, g + i, z)] = "mango_log"
        for dx in range(-2, 3):
            for dz in range(-2, 3):
                for dy in (3, 4, 5):
                    if abs(dx) + abs(dz) + abs(dy - 4) * 2 <= 3 and (x + dx, g + dy, z + dz) not in v:
                        v[(x + dx, g + dy, z + dz)] = "mango_leaves"

    # 4 palm trees: one on top, one on the front ledge, one leaning off the right of the main rock, one on the tail.
    palm(13, 9, height=6)
    palm(12, 3, height=5)
    palm(18, 7, lean=(1, 0), height=5)
    palm(23, 6, lean=(1, 0), height=5)
    # 2 mango trees on the middle ledge and the top.
    mango(10, 5)
    mango(16, 10)

    # The hut on the pillar: a 3x3 floor of planks, posts, a red and blue tarp roof, the loot box inside.
    g = 11
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            v[(3 + dx, g, 6 + dz)] = "planks"
    for dx, dz in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        for dy in (1, 2):
            v[(3 + dx, g + dy, 6 + dz)] = "planks"
    for dx in range(-1, 2):
        for dz in range(-1, 2):
            v[(3 + dx, g + 3, 6 + dz)] = "red_wool" if dz < 1 else "blue_wool"
    v[(3, g + 1, 6)] = "chest"
    # A ladder up the pillar's saddle side, from the saddle to the hut.
    for y in range(7, 11):
        plants[(6, y, 6)] = "ladder"

    # Plants on free ground: pineapple, 2 watermelons, 5 of each flower.
    def free_ground(region):
        spots = []
        for (x, z) in region:
            gy = ground(x, z)
            if gy is None or gy < 1 or v.get((x, gy, z)) not in ("moss", "sand"): continue
            if (x, gy + 1, z) in v or (x, gy + 1, z) in plants: continue
            spots.append((x, gy + 1, z))
        rng.shuffle(spots)
        return spots

    grassy = [p for p in free_ground(list(top)) if v.get((p[0], p[1] - 1, p[2])) == "moss"]
    for kind, n in (("pineapple", 1), ("melon", 2), ("red_flower", 5), ("blue_flower", 5), ("yellow_flower", 5), ("white_flower", 5), ("black_flower", 5)):
        for _ in range(n):
            if not grassy: break
            p = grassy.pop()
            if kind == "melon": v[p] = "melon"
            else: plants[p] = kind

    # Under water: seagrass on the sand, kelp along the shelf's edge, 2 giant clams.
    seabed = [(x, y + 1, z) for (x, y, z), b in v.items() if b in ("sand", "clay") and y <= -3 and (x, y + 1, z) not in v]
    rng.shuffle(seabed)
    for p in seabed[:120]:
        plants[p] = "seagrass"
    for p in seabed[120:134]:
        for dy in range(0, rng.randint(3, 6)):
            q = (p[0], p[1] + dy, p[2])
            if q[1] > -1 or q in v: break   # a kelp column stops at the surface or at rock
            plants[q] = "kelp"
    for p in seabed[134:136]:
        plants[p] = "clam"

    return {"voxels": v, "plants": plants}


def display_list(v: dict, plants: dict, names: list) -> list:
    """The entities that draw the island: exposed voxels down to DISPLAY_DEPTH, rock merged into 2x2x2 cubes."""
    def solid(p):
        return v.get(p) in SOLID

    def exposed(p):
        x, y, z = p
        return any(not solid(n) for n in ((x + 1, y, z), (x - 1, y, z), (x, y + 1, z), (x, y - 1, z), (x, y, z + 1), (x, y, z - 1)))

    shown = {p for p in v if p[1] >= DISPLAY_DEPTH and exposed(p)}
    claimed: set = set()
    out = []
    for p in sorted(shown):
        if p in claimed: continue
        b = v[p]
        if PALETTE[b][4]:
            merged = False
            for ox, oy, oz in ((0, 0, 0), (-1, 0, 0), (0, 0, -1), (-1, 0, -1), (0, -1, 0), (-1, -1, 0), (0, -1, -1), (-1, -1, -1)):
                corner = (p[0] + ox, p[1] + oy, p[2] + oz)
                cube = [(corner[0] + dx, corner[1] + dy, corner[2] + dz) for dx in (0, 1) for dy in (0, 1) for dz in (0, 1)]
                if all(v.get(c) in ROCK and c not in claimed for c in cube):
                    claimed.update(cube)
                    out.append([corner[0], corner[1], corner[2], b, 2])
                    merged = True
                    break
            if merged: continue
        claimed.add(p)
        out.append([p[0], p[1], p[2], b, 1])
    for p, b in sorted(plants.items()):
        if PALETTE[b][2] and p[1] >= DISPLAY_DEPTH:
            out.append([p[0], p[1], p[2], b, 1])
    return out


def preview(v: dict, plants: dict, out_dir: str) -> None:
    from PIL import Image
    colours = {"stone": (150, 150, 150), "andesite": (130, 130, 130), "moss": (90, 140, 50), "sand": (220, 205, 150), "clay": (160, 165, 180),
               "iron_ore": (200, 160, 130), "copper_ore": (200, 110, 70), "palm_log": (110, 85, 50), "mango_log": (120, 95, 60),
               "palm_leaves": (70, 170, 60), "mango_leaves": (110, 160, 90), "melon": (120, 170, 40), "planks": (170, 130, 80),
               "red_wool": (180, 40, 40), "blue_wool": (50, 70, 180), "chest": (150, 100, 40)}
    xs = [p[0] for p in v]; ys = [p[1] for p in v]; zs = [p[2] for p in v]
    s = 12
    # top view: highest voxel per column
    w, h = (max(xs) - min(xs) + 1), (max(zs) - min(zs) + 1)
    img = Image.new("RGB", (w * s, h * s), (20, 40, 90))
    best = {}
    for (x, y, z), b in v.items():
        if (x, z) not in best or y > best[(x, z)][0]: best[(x, z)] = (y, b)
    for (x, z), (y, b) in best.items():
        c = colours.get(b, (255, 0, 255))
        if y < 0: c = tuple(int(ch * 0.45 + d) for ch, d in zip(c, (10, 25, 60)))
        img.paste(c, ((x - min(xs)) * s, (z - min(zs)) * s, (x - min(xs) + 1) * s, (z - min(zs) + 1) * s))
    img.save(os.path.join(out_dir, "island1_top.png"))
    # side view from -z (the raft's side): nearest voxel per (x, y)
    w, h = (max(xs) - min(xs) + 1), (max(ys) - min(ys) + 1)
    img = Image.new("RGB", (w * s, h * s), (120, 190, 230))
    near = {}
    for (x, y, z), b in v.items():
        if (x, y) not in near or z < near[(x, y)][0]: near[(x, y)] = (z, b)
    for (x, y), (z, b) in near.items():
        c = colours.get(b, (255, 0, 255))
        if y < 0: c = tuple(int(ch * 0.45 + d) for ch, d in zip(c, (10, 25, 60)))
        img.paste(c, ((x - min(xs)) * s, (max(ys) - y) * s, (x - min(xs) + 1) * s, (max(ys) - y + 1) * s))
    img.save(os.path.join(out_dir, "island1_side.png"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()

    island = build()
    v, plants = island["voxels"], island["plants"]
    names = list(PALETTE)
    blocks = [[x, y, z, names.index(b)] for (x, y, z), b in sorted(v.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]
    # plants after every solid, so each has its ground (or its water) when it is placed
    blocks += [[x, y, z, names.index(b)] for (x, y, z), b in sorted(plants.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2]))]
    display = [[x, y, z, names.index(b), size] for x, y, z, b, size in display_list(v, plants, names)]
    # Front first: the island comes into range a slice at a time, its downstream (high x) end first.
    display.sort(key=lambda d: (-(d[0] + d[4]), d[1], d[2]))
    palette = [{"id": PALETTE[n][0], "states": PALETTE[n][1], "type": PALETTE[n][2], "variant": PALETTE[n][3]} for n in names]
    xs = [b[0] for b in blocks]; zs = [b[2] for b in blocks]
    with open(OUT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("// Generated by tools/island.py: Raft's Small Island 1. Do not edit by hand.\n")
        handle.write(f"export const PALETTE = {json.dumps(palette)};\n")
        handle.write(f"export const BOUNDS = {json.dumps({'minX': min(xs), 'maxX': max(xs), 'minZ': min(zs), 'maxZ': max(zs)})};\n")
        handle.write(f"export const BLOCKS = {json.dumps(blocks, separators=(',', ':'))};\n")
        handle.write(f"export const DISPLAY = {json.dumps(display, separators=(',', ':'))};\n")
    counts = {}
    for _, _, _, b in [(0, 0, 0, names[d[3]]) for d in display]: counts[b] = counts.get(b, 0) + 1
    print(f"wrote {os.path.relpath(OUT, ROOT)}: {len(blocks)} blocks, {len(display)} display entities "
          f"({sum(1 for d in display if d[4] == 2)} of them 2x2x2 rock), x {min(xs)}..{max(xs)}, z {min(zs)}..{max(zs)}")
    if args.preview:
        os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
        preview(v, plants, os.path.join(ROOT, "build"))
        print("previews in build/")


if __name__ == "__main__":
    main()
