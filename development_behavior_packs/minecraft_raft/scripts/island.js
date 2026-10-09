// The first island encounter: Raft's Small Island 1 (tools/island.py builds it into island1.js).
//
// The island comes into sight upstream as Display add-on entities, a slice at a time as each comes into range,
// drifting toward the raft with the current exactly as the flotsam does, so it glides in smoothly. Left alone it
// drifts past and away. Throw the anchor while it is alongside and the island stops on whole-block coordinates
// and turns into real blocks: rock to climb, palms to chop, ore to mine, a loot box in the hut. When the anchor
// is destroyed the raft drifts again: whatever is left of the island turns back into entities and drifts away.

import { world, system, BlockPermutation, ItemStack } from "@minecraft/server";
import { PALETTE, BLOCKS, DISPLAY } from "./island1.js";
import { isAnchored, hasAnchor } from "./anchor.js";

const WATER_TOP = 63;          // world y of the ocean's top layer; island y = 0 is this layer
const ALONGSIDE_X = -16;       // island x at which the raft (x 0..1) lies beside the middle of the main rock
const ISLAND_Z = 2;            // island z, putting its rock three blocks off the raft's side
const IN_RANGE = 56;           // an island entity is spawned once it is this close upstream of the raft...
const LEAVE_PAST = 56;         // ...and removed this far downstream of it
const START_X = -IN_RANGE - 44;   // the island starts just out of range (it is 44 blocks long)
const FIRST_ISLAND_AFTER = 20 * 60 * 2;   // ticks after a new world's first player before the island shows up
const SPAWN_PER_TICK = 120;    // entities spawned per tick at most
const PLACE_PER_TICK = 600;    // blocks placed per tick while it anchors

const overworld = () => world.getDimension("overworld");
let resolved = undefined;
function permutation(index) {
	// Resolved on first use: BlockPermutation cannot be built while the script is first loading.
	resolved ??= PALETTE.map((p) => {
		try {
			return BlockPermutation.resolve(p.id, p.states);
		} catch {
			console.warn(`[minecRAFT] ${p.id} has no states ${JSON.stringify(p.states)} in this version; placing the plain block`);
			return BlockPermutation.resolve(p.id);
		}
	});
	return resolved[index];
}
const CHEST = PALETTE.findIndex((p) => p.id === "minecraft:chest");

// Raft's Mountain Loot Box table; https://raft.fandom.com/wiki/Loot_Box#Mountain_Loot_Box.
// Scrap, nails, bolts and hinges have no Minecraft equivalents of their own, so all four are iron nuggets.
const MOUNTAIN_LOOT = [
	["minecraft:jungle_planks", 48.4], ["minecraft:string", 12.9], ["minecraft:iron_nugget", 32.4],
	["minecraft:raw_iron", 3.2], ["minecraft:slime_ball", 1.6], ["minecraft:glass", 1.6],
];

let state = undefined;   // { phase: "drifting" | "anchoring" | "anchored" | "casting_off", x, next, chestFilled }
let job = undefined;

function load() {
	if (state !== undefined) return state;
	const saved = world.getDynamicProperty("island");
	state = typeof saved === "string" ? JSON.parse(saved) : null;
	return state;
}

function save() {
	world.setDynamicProperty("island", state ? JSON.stringify(state) : undefined);
}

export function islandActive() {
	return !!load();
}

// Flotsam keeps to the far side of the raft while an island is around, so none of it floats through the rock.
export function islandSideBlocked(z) {
	return islandActive() && z >= ISLAND_Z - 3;
}

function spawnDisplay(x, y, z, paletteIndex, size) {
	const p = PALETTE[paletteIndex];
	if (!p.type) return;
	const entity = overworld().spawnEntity(p.type, { x: state.x + x + size / 2, y: WATER_TOP + y, z: ISLAND_Z + z + size / 2 });
	entity.triggerEvent(p.variant);
	if (size !== 1) entity.triggerEvent(`scale_${size}.0`);
	entity.setRotation({ x: 0, y: 0 });
	entity.addTag("island");
}

export function startIsland(x = START_X) {
	if (load()) return false;
	state = { phase: "drifting", x, next: 0, chestFilled: false };
	save();
	world.setDynamicProperty("island1_seen", true);
	for (const entity of overworld().getEntities({ tags: ["flotsam"] })) {
		if (islandSideBlocked(entity.location.z)) entity.remove();
	}
	return true;
}

// The display list runs downstream end first, so each tick spawns whatever has come within range.
function spawnInRange(raft) {
	let n = 0;
	while (state.next < DISPLAY.length && n < SPAWN_PER_TICK) {
		const [x, y, z, paletteIndex, size] = DISPLAY[state.next];
		if (state.x + x + size < raft.x - IN_RANGE) break;
		try {
			spawnDisplay(x, y, z, paletteIndex, size);
		} catch {
			break;   // its chunk is not loaded yet; next tick
		}
		state.next++;
		n++;
	}
}

function moveIsland(dx) {
	for (const entity of overworld().getEntities({ tags: ["island"] })) {
		const { x, y, z } = entity.location;
		entity.teleport({ x: x + dx, y, z });
	}
}

function fillChest(block) {
	const container = block.getComponent("minecraft:inventory")?.container;
	if (!container) return;
	const total = MOUNTAIN_LOOT.reduce((sum, [, weight]) => sum + weight, 0);
	for (let i = 4 + Math.floor(Math.random() * 3); i > 0; i--) {
		let roll = Math.random() * total;
		const [id] = MOUNTAIN_LOOT.find(([, weight]) => (roll -= weight) < 0) ?? MOUNTAIN_LOOT[0];
		container.addItem(new ItemStack(id, 1));
	}
}

// The island stops alongside the raft and becomes real blocks, placed only where there is still water or air,
// so nothing the player built is overwritten. The entities go once every block is down.
function anchor() {
	state.phase = "anchoring";
	save();
	job = system.runJob(
		(function* () {
			const dimension = overworld();
			let n = 0;
			for (const [x, y, z, paletteIndex] of BLOCKS) {
				try {
					const block = dimension.getBlock({ x: state.x + x, y: WATER_TOP + y, z: ISLAND_Z + z });
					if (block && (block.isAir || block.typeId === "minecraft:water" || block.typeId === "minecraft:flowing_water")) {
						block.setPermutation(permutation(paletteIndex));
						if (paletteIndex === CHEST && !state.chestFilled) {
							fillChest(block);
							state.chestFilled = true;
						}
					}
				} catch {}
				if (++n % PLACE_PER_TICK === 0) yield;
			}
			for (const entity of dimension.getEntities({ tags: ["island"] })) entity.remove();
			state.phase = "anchored";
			save();
			job = undefined;
		})()
	);
}

// Casting off: what is left of the island (every block that still matches what was placed there) goes back to
// being entities, the blocks go back to ocean, and the island drifts on downstream.
function castOff() {
	state.phase = "casting_off";
	save();
	job = system.runJob(
		(function* () {
			const dimension = overworld();
			const left = new Map();
			let n = 0;
			for (const [x, y, z, paletteIndex] of BLOCKS) {
				try {
					const block = dimension.getBlock({ x: state.x + x, y: WATER_TOP + y, z: ISLAND_Z + z });
					if (block?.typeId === PALETTE[paletteIndex].id) left.set(`${x},${y},${z}`, [x, y, z, paletteIndex, block]);
				} catch {}
				if (++n % PLACE_PER_TICK === 0) yield;
			}
			// Redraw it as it was drawn arriving, cube for cube, wherever a cube is still whole; anything a player
			// broke into is drawn block by block from what is left.
			const covered = new Set();
			n = 0;
			for (const [x, y, z, paletteIndex, size] of DISPLAY) {
				const cells = [];
				for (let dx = 0; dx < size; dx++) for (let dy = 0; dy < size; dy++) for (let dz = 0; dz < size; dz++) cells.push(`${x + dx},${y + dy},${z + dz}`);
				if (!cells.every((key) => left.has(key))) continue;
				cells.forEach((key) => covered.add(key));
				try {
					spawnDisplay(x, y, z, paletteIndex, size);
				} catch {}
				if (++n % SPAWN_PER_TICK === 0) yield;
			}
			const solid = (x, y, z) => {
				const entry = left.get(`${x},${y},${z}`);
				return entry && PALETTE[entry[3]].type === "display:block" && !PALETTE[entry[3]].id.includes("flower") && !PALETTE[entry[3]].id.includes("ladder");
			};
			for (const [key, [x, y, z, paletteIndex]] of left) {
				if (covered.has(key) || y < -2) continue;
				if (!solid(x + 1, y, z) || !solid(x - 1, y, z) || !solid(x, y + 1, z) || !solid(x, y - 1, z) || !solid(x, y, z + 1) || !solid(x, y, z - 1)) {
					try {
						spawnDisplay(x, y, z, paletteIndex, 1);
					} catch {}
					if (++n % SPAWN_PER_TICK === 0) yield;
				}
			}
			// Plants come off before what they stand on, top down, or each would pop off as a dropped item.
			n = 0;
			for (const [x, y, z, paletteIndex, block] of [...left.values()].reverse()) {
				try {
					if (paletteIndex === CHEST) {
						const container = block.getComponent("minecraft:inventory")?.container;
						for (let slot = 0; container && slot < container.size; slot++) {
							const item = container.getItem(slot);
							if (item) dimension.spawnItem(item, { x: state.x + x + 0.5, y: WATER_TOP + y + 1, z: ISLAND_Z + z + 0.5 });
						}
						container?.clearAll();
					}
					block.setType(y <= 0 ? "minecraft:water" : "minecraft:air");
				} catch {}
				if (++n % PLACE_PER_TICK === 0) yield;
			}
			state.phase = "drifting";
			state.next = DISPLAY.length;
			save();
			job = undefined;
		})()
	);
}

// Removes the island: its entities, and its blocks if it is anchored. With an x, also clears island blocks left
// standing at that x (for a world where a conversion ran while its chunks were unloaded).
export function clearIsland(at) {
	load();
	const dimension = overworld();
	for (const entity of dimension.getEntities({ tags: ["island"] })) entity.remove();
	const xs = [];
	if (state && (state.phase === "anchoring" || state.phase === "anchored" || state.phase === "casting_off")) xs.push(state.x);
	if (Number.isFinite(at)) xs.push(at);
	for (const ox of xs) {
		for (const [x, y, z, paletteIndex] of [...BLOCKS].reverse()) {
			try {
				const block = dimension.getBlock({ x: ox + x, y: WATER_TOP + y, z: ISLAND_Z + z });
				if (block?.typeId === PALETTE[paletteIndex].id) block.setType(y <= 0 ? "minecraft:water" : "minecraft:air");
			} catch {}
		}
	}
	state = null;
	save();
}

// Converting the island reads and writes its blocks, which only works while its chunks are loaded (a player is
// near). Right after a restart nobody is, so a step waits for that rather than silently doing nothing.
function islandLoaded() {
	try {
		return !!overworld().getBlock({ x: state.x + 16, y: WATER_TOP, z: ISLAND_Z + 7 }) && !!overworld().getBlock({ x: state.x, y: WATER_TOP, z: ISLAND_Z }) && !!overworld().getBlock({ x: state.x + 39, y: WATER_TOP, z: ISLAND_Z + 20 });
	} catch {
		return false;
	}
}

export function islandTick(drift, raft) {
	load();
	const t = system.currentTick;

	if (!state) {
		// The first island turns up a couple of minutes into a new world, once.
		if (!world.getDynamicProperty("island1_seen") && world.getPlayers().length) {
			const due = world.getDynamicProperty("island1_due");
			if (typeof due !== "number") world.setDynamicProperty("island1_due", t + FIRST_ISLAND_AFTER);
			else if (t >= due) startIsland();
		}
		return;
	}

	if (state.phase === "drifting") {
		spawnInRange(raft);
		let step = drift;
		if (isAnchored()) {
			// The raft has stopped, so the island has. One that is all here settles onto the next whole block
			// and becomes solid; one still coming over the horizon just waits.
			const settle = Math.ceil(state.x - 1e-6) - state.x;
			step = state.next >= DISPLAY.length ? Math.min(drift, settle) : 0;
		}
		if (step > 0) {
			moveIsland(step);
			state.x += step;
		}
		if (isAnchored() && state.next >= DISPLAY.length && Math.abs(state.x - Math.round(state.x)) < 1e-6 && islandLoaded()) {
			state.x = Math.round(state.x);
			anchor();
		} else {
			for (const entity of overworld().getEntities({ tags: ["island"] })) {
				if (entity.location.x > raft.x + LEAVE_PAST) entity.remove();
			}
			if (state.next >= DISPLAY.length && !overworld().getEntities({ tags: ["island"] }).length) state = null;
		}
		save();
		if (state && !isAnchored() && t % 100 === 0 && Math.abs(state.x - ALONGSIDE_X) < 14) {
			for (const player of world.getPlayers()) {
				if (hasAnchor(player)) player.onScreenDisplay.setActionBar("An island! Throw your anchor to stop here.");
			}
		}
	} else if (state.phase === "anchored" && !isAnchored() && islandLoaded()) {
		castOff();
	}
	// The world was reloaded part way through a step; do it again from the start.
	if (!job && state?.phase === "anchoring" && islandLoaded()) anchor();
	if (!job && state?.phase === "casting_off" && islandLoaded()) castOff();
}
