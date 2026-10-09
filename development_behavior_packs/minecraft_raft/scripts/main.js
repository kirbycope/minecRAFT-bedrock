// minecRAFT: Raft but in Minecraft.
//
// The raft never moves. The ocean is the flat world's water layers, endless and the same everywhere, so the
// current is shown by moving everything floating in it past the raft instead: flotsam is display entities from
// the Display add-on, teleported a little downstream every tick, which the client draws as smooth motion.
// A fishing hook that lands next to a piece of flotsam carries it, and reeling in gives its loot.

import { world, system, ItemStack } from "@minecraft/server";
import { islandTick, startIsland, clearIsland, islandSideBlocked } from "./island.js";
import { ANCHOR_ITEM } from "./anchor.js";

const RAFT = { x: 0, y: 63, z: 0 };      // north-west corner of the 2x2 starting raft, in the top water layer
const SURFACE = 63.55;                    // flotsam rides half in, half out of the top water layer
const DRIFT = 0.04;                       // blocks per tick the current carries flotsam east (0.8 blocks a second)
const UPSTREAM = 40;                      // flotsam appears this far west of the raft...
const DOWNSTREAM = 40;                    // ...and is gone this far east of it
const SPREAD = 12;                        // north-south half width of the stream
const MAX_FLOTSAM = 30;
const SPAWN_EVERY = 20;                   // ticks between new pieces while under the cap
const HOOK_REACH = 1.6;                   // how close a hook must land to a piece to catch it
const BRUCE_LEASH = 12;                   // how far Bruce may swim from the raft before he is steered back

const FLOTSAM = [
	{ name: "barrel", type: "display:block", variant: "barrel_side", scale: "scale_0.6", weight: 1, loot: barrelLoot },
	{ name: "plank", type: "display:block", variant: "planks_jungle", scale: "scale_0.4", weight: 4, loot: () => [["minecraft:jungle_planks", 1]] },
	{ name: "palm_leaf", type: "display:block", variant: "azalea_leaves", scale: "scale_0.4", weight: 3, loot: () => [["minecraft:jungle_leaves", 1]] },
	{ name: "plastic", type: "display:item", variant: "reeds", scale: "scale_0.5", weight: 3, loot: () => [["minecraft:sugar_cane", 1]] },
];

// Raft's barrel: 4 to 6 rolls on its loot table; https://raft.fandom.com/wiki/Barrel
const BARREL_LOOT = [
	["minecraft:jungle_planks", 37.73], ["minecraft:sugar_cane", 14.15], ["minecraft:jungle_leaves", 18.87],
	["minecraft:iron_nugget", 9.43], ["minecraft:string", 7.08], ["minecraft:cobblestone", 6.13],
	["minecraft:beetroot", 3.3], ["minecraft:potato", 3.3],
];

function barrelLoot() {
	const total = BARREL_LOOT.reduce((sum, [, weight]) => sum + weight, 0);
	const loot = [];
	for (let i = 4 + Math.floor(Math.random() * 3); i > 0; i--) {
		let roll = Math.random() * total;
		const [id] = BARREL_LOOT.find(([, weight]) => (roll -= weight) < 0) ?? BARREL_LOOT[0];
		loot.push([id, 1]);
	}
	return loot;
}

const overworld = () => world.getDimension("overworld");
const kindOf = (entity) => FLOTSAM.find((kind) => entity.hasTag(`flotsam:${kind.name}`));
const hooks = new Map();   // hook entity id -> { owner, flotsam: [entity] }

function pickKind() {
	let roll = Math.random() * FLOTSAM.reduce((sum, kind) => sum + kind.weight, 0);
	return FLOTSAM.find((kind) => (roll -= kind.weight) < 0) ?? FLOTSAM[0];
}

function spawnFlotsam(x) {
	const kind = pickKind();
	let z = RAFT.z + 1 + (Math.random() * 2 - 1) * SPREAD;
	if (islandSideBlocked(z)) z = RAFT.z - 1 - Math.random() * SPREAD;
	let entity;
	try {
		entity = overworld().spawnEntity(kind.type, { x, y: SURFACE, z });
	} catch {
		return;   // the stream's chunk is not loaded, so nobody is near enough to see it
	}
	entity.triggerEvent(kind.variant);
	entity.triggerEvent(kind.scale);
	entity.setRotation({ x: 0, y: Math.random() * 360 });
	entity.addTag("flotsam");
	entity.addTag(`flotsam:${kind.name}`);
}

function placeRaft() {
	if (world.getDynamicProperty("raft_placed")) return true;
	try {
		for (const [dx, dz] of [[0, 0], [1, 0], [0, 1], [1, 1]]) {
			overworld().setBlockType({ x: RAFT.x + dx, y: RAFT.y, z: RAFT.z + dz }, "minecraft:jungle_planks");
		}
	} catch {
		return false;   // spawn not loaded yet; try again next second
	}
	world.setDynamicProperty("raft_placed", true);
	// The whole stream at once, so a new world starts with flotsam already in reach.
	for (let x = RAFT.x - UPSTREAM; x < RAFT.x + DOWNSTREAM; x += (UPSTREAM + DOWNSTREAM) / 12) spawnFlotsam(x);
	return true;
}

// Bruce, the shark of the original, is a dolphin here as he was in the Java map. Left alone a dolphin swims out
// of loaded range and is never seen again, so he is nudged back toward the raft when he strays, and a new Bruce
// is spawned if none is left near it.
function keepBruce() {
	const dimension = overworld();
	const centre = { x: RAFT.x + 1, y: RAFT.y, z: RAFT.z + 1 };
	if (!dimension.getPlayers({ location: centre, maxDistance: 48 }).length) return;
	const bruce = dimension.getEntities({ type: "minecraft:dolphin", name: "Bruce", location: centre, maxDistance: 64 })[0];
	if (!bruce) {
		try {
			dimension.spawnEntity("minecraft:dolphin", { x: centre.x + 8, y: RAFT.y - 1, z: centre.z + 8 }).nameTag = "Bruce";
		} catch {}
		return;
	}
	const dx = centre.x - bruce.location.x, dz = centre.z - bruce.location.z, distance = Math.hypot(dx, dz);
	if (distance > BRUCE_LEASH) bruce.applyImpulse({ x: (dx / distance) * 0.3, y: 0, z: (dz / distance) * 0.3 });
}

function initPlayer(player) {
	if (player.hasTag("raft_init")) return;
	player.addTag("raft_init");
	const inventory = player.getComponent("minecraft:inventory").container;
	inventory.addItem(new ItemStack("minecraft:fishing_rod", 1));
	// Raft has you craft your first anchor; here you start with one so the first island can be visited.
	inventory.addItem(new ItemStack(ANCHOR_ITEM, 1));
}

function give(player, loot, at) {
	const container = player.getComponent("minecraft:inventory")?.container;
	for (const [id, amount] of loot) {
		const leftover = container?.addItem(new ItemStack(id, amount));
		if (leftover) player.dimension.spawnItem(leftover, player.location);
	}
	player.dimension.playSound("random.pop", at, { volume: 0.6, pitch: 1.2 });
}

// A hook that has just come out of the water with flotsam on it delivers the loot to whoever cast it.
function reelIn(hook) {
	const { owner, flotsam } = hook;
	for (const entity of flotsam) {
		if (!entity.isValid) continue;
		if (owner?.isValid) give(owner, kindOf(entity)?.loot() ?? [], entity.location);
		entity.remove();
	}
}

function ownerOf(hook) {
	try {
		const owner = hook.getComponent("minecraft:projectile")?.owner;
		if (owner?.typeId === "minecraft:player") return owner;
	} catch {}
	// Fall back to the nearest player, which is who cast it in any but the most crowded raft.
	return hook.dimension.getPlayers({ location: hook.location, closest: 1, maxDistance: 40 })[0];
}

function tick() {
	const dimension = overworld();

	// Hooks: catch what a hook lands beside, carry it while the line is out, deliver it when the line comes in.
	const live = new Set();
	for (const hook of dimension.getEntities({ type: "minecraft:fishing_hook" })) {
		live.add(hook.id);
		let caught = hooks.get(hook.id);
		if (!caught) hooks.set(hook.id, (caught = { owner: ownerOf(hook), flotsam: [] }));
		for (const entity of dimension.getEntities({ tags: ["flotsam"], excludeTags: ["hooked"], location: hook.location, maxDistance: HOOK_REACH })) {
			entity.addTag("hooked");
			caught.flotsam.push(entity);
		}
		caught.flotsam.forEach((entity, i) => {
			if (entity.isValid) entity.teleport({ x: hook.location.x, y: SURFACE + i * 0.3, z: hook.location.z });
		});
	}
	for (const [id, hook] of hooks) {
		if (!live.has(id)) {
			reelIn(hook);
			hooks.delete(id);
		}
	}

	// The current: everything not on a hook drifts east, bobbing, and is gone once it has passed the raft.
	const t = system.currentTick;
	let count = 0;
	for (const entity of dimension.getEntities({ tags: ["flotsam"], excludeTags: ["hooked"] })) {
		const { x, z } = entity.location;
		if (x > RAFT.x + DOWNSTREAM) {
			entity.remove();
			continue;
		}
		count++;
		const bob = Math.sin(t / 15 + x + z) * 0.04;
		entity.teleport({ x: x + DRIFT, y: SURFACE + bob, z }, { keepVelocity: false });
	}
	if (count < MAX_FLOTSAM && t % SPAWN_EVERY === 0) spawnFlotsam(RAFT.x - UPSTREAM);

	islandTick(DRIFT, RAFT);
}

world.afterEvents.worldLoad.subscribe(() => {
	world.gameRules.spawnRadius = 0;
	world.setDefaultSpawnLocation({ x: RAFT.x + 1, y: RAFT.y + 1, z: RAFT.z + 1 });
	const placing = system.runInterval(() => {
		if (placeRaft()) system.clearRun(placing);
	}, 20);
	system.runInterval(tick, 1);
	system.runInterval(keepBruce, 20);
});

// /scriptevent raft:island start [x]   brings the island now (from x, for testing: -24 is just upstream of alongside)
// /scriptevent raft:island clear [x]   removes it (and with an x, any island blocks left standing at that x)
system.afterEvents.scriptEventReceive.subscribe(({ id, message }) => {
	if (id !== "raft:island") return;
	const [verb, at] = message.trim().split(/\s+/);
	if (verb === "clear") clearIsland(Number(at));
	else startIsland(Number.isFinite(Number(at)) && at !== undefined ? Number(at) : undefined);
});

world.afterEvents.playerSpawn.subscribe(({ player, initialSpawn }) => {
	if (initialSpawn) initPlayer(player);
});
