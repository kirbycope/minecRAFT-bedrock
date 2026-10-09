// Raft's Throwable Anchor; https://raft.fandom.com/wiki/Throwable_Anchor
//
// Use the item on the raft to set it down: a fence post on the raft with the anchor tied to it by a lead.
// Use the post (or the anchor) to throw the anchor into the water, which anchors the raft. Like Raft's, it works
// once: breaking the post destroys it, anchor and all, and the raft drifts again.

import { world, system } from "@minecraft/server";

export const ANCHOR_ITEM = "raft:throwable_anchor";
const POST = "minecraft:oak_fence";
const THROW_OUT = 3;      // how far from the post the anchor lands, in blocks
const SINK_TO = 58;       // world y the anchor settles at, under the raft's water
const FLIGHT_TICKS = 12;  // the throw's arc
const SINK_TICKS = 30;    // then down through the water

let anchor = undefined;   // { x, y, z, dx, dz, thrown } for the post, or null

function load() {
	if (anchor !== undefined) return anchor;
	const saved = world.getDynamicProperty("anchor");
	anchor = typeof saved === "string" ? JSON.parse(saved) : null;
	return anchor;
}

function save() {
	world.setDynamicProperty("anchor", anchor ? JSON.stringify(anchor) : undefined);
}

export function isAnchored() {
	return !!load()?.thrown;
}

// Whether a player can still anchor: one is set down on the raft and not yet thrown, or they carry one.
export function hasAnchor(player) {
	if (load() && !anchor.thrown) return true;
	const inventory = player.getComponent("minecraft:inventory")?.container;
	for (let slot = 0; inventory && slot < inventory.size; slot++) {
		if (inventory.getItem(slot)?.typeId === ANCHOR_ITEM) return true;
	}
	return false;
}

const overworld = () => world.getDimension("overworld");
const anchorEntity = () => overworld().getEntities({ type: "raft:anchor", tags: ["raft_anchor"] })[0];
const isPost = (block) => !!load() && block.x === anchor.x && block.y === anchor.y && block.z === anchor.z;

function tell(player, text) {
	player.onScreenDisplay.setActionBar(text);
}

function setDown(player, block, face) {
	if (load()) return tell(player, "There is already an anchor on the raft.");
	const post = block.above();
	if (!post?.isAir) return tell(player, "There is no room for the anchor there.");
	// The anchor is thrown off the side that was clicked, or off the nearest edge when the top was.
	let [dx, dz] = { North: [0, -1], South: [0, 1], West: [-1, 0], East: [1, 0] }[face] ?? [0, 0];
	if (!dx && !dz) {
		const around = [[0, -1], [-1, 0], [1, 0], [0, 1]].find(([ax, az]) => !overworld().getBlock({ x: block.x + ax, y: block.y, z: block.z + az })?.typeId.endsWith("_planks"));
		[dx, dz] = around ?? [0, -1];
	}
	post.setType(POST);
	const inventory = player.getComponent("minecraft:inventory").container;
	const held = inventory.getItem(player.selectedSlotIndex);
	if (held?.typeId === ANCHOR_ITEM) {
		if (held.amount > 1) {
			held.amount -= 1;
			inventory.setItem(player.selectedSlotIndex, held);
		} else inventory.setItem(player.selectedSlotIndex, undefined);
	}
	anchor = { x: post.x, y: post.y, z: post.z, dx, dz, thrown: false };
	save();
	const entity = overworld().spawnEntity("raft:anchor", { x: post.x + 0.5 + dx * 0.7, y: post.y, z: post.z + 0.5 + dz * 0.7 });
	entity.addTag("raft_anchor");
	entity.setRotation({ x: 0, y: dx ? 90 : 0 });
	tie(entity);
	tell(player, "Use the post to throw the anchor.");
}

// The lead runs from a knot on the post to the anchor. The knot is this pack's own entity: a script cannot spawn
// the vanilla leash knot.
function tie(entity) {
	try {
		const at = { x: anchor.x + 0.5, y: anchor.y + 0.4, z: anchor.z + 0.5 };
		const knot = overworld().getEntities({ type: "raft:knot", location: at, maxDistance: 1 })[0] ?? overworld().spawnEntity("raft:knot", at);
		knot.addTag("raft_anchor");
		entity.getComponent("minecraft:leashable")?.leashTo(knot);
	} catch (error) {
		console.warn(`[minecRAFT] could not tie the anchor's lead: ${error}`);
	}
}

function throwAnchor(player) {
	if (!load() || anchor.thrown) return;
	const entity = anchorEntity();
	if (!entity) return;
	anchor.thrown = true;
	save();
	const from = { x: anchor.x + 0.5, y: anchor.y + 0.5, z: anchor.z + 0.5 };
	const to = { x: from.x + anchor.dx * THROW_OUT, z: from.z + anchor.dz * THROW_OUT };
	let tick = 0;
	const flight = system.runInterval(() => {
		if (!entity.isValid) return system.clearRun(flight);
		tick++;
		if (tick <= FLIGHT_TICKS) {
			const t = tick / FLIGHT_TICKS;
			entity.teleport({ x: from.x + (to.x - from.x) * t, y: from.y + Math.sin(t * Math.PI) * 1.5 - t * 1.2, z: from.z + (to.z - from.z) * t });
			if (tick === FLIGHT_TICKS) overworld().playSound("random.splash", { x: to.x, y: 63.5, z: to.z });
		} else if (tick <= FLIGHT_TICKS + SINK_TICKS) {
			const t = (tick - FLIGHT_TICKS) / SINK_TICKS;
			entity.teleport({ x: to.x, y: from.y - 1.2 + (SINK_TO - (from.y - 1.2)) * t, z: to.z });
		} else system.clearRun(flight);
	}, 1);
	tell(player, "Anchor down. The raft has stopped.");
}

// Breaking the post destroys the anchor: it is single use, as in Raft.
function destroy(player) {
	load();
	if (!anchor) return;
	const { x, y, z } = anchor;
	anchor = null;
	save();
	system.run(() => {
		const dimension = overworld();
		const post = dimension.getBlock({ x, y, z });
		if (post?.typeId === POST) post.setType("minecraft:air");
		anchorEntity()?.remove();
		for (const knot of dimension.getEntities({ type: "raft:knot", location: { x: x + 0.5, y: y + 0.5, z: z + 0.5 }, maxDistance: 1.5 })) knot.remove();
		for (const item of dimension.getEntities({ type: "minecraft:item", location: { x: x + 0.5, y: y + 0.5, z: z + 0.5 }, maxDistance: 2 })) {
			if (item.getComponent("minecraft:item")?.itemStack.typeId === "minecraft:lead") item.remove();
		}
		if (player) tell(player, "The anchor is gone, and the raft drifts on.");
	});
}

// The before event, because an item that does nothing of its own when used never raises the after event.
world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
	const { player, block, blockFace, itemStack, isFirstEvent } = event;
	if (!isFirstEvent) return;
	if (isPost(block)) {
		event.cancel = true;
		system.run(() => throwAnchor(player));
	} else if (itemStack?.typeId === ANCHOR_ITEM && block.typeId.endsWith("_planks")) {
		event.cancel = true;
		system.run(() => setDown(player, block, blockFace));
	}
});

// The knot and the anchor are entities, and using either one counts as using the post. Vanilla would untie the
// lead instead, so that is cancelled.
world.beforeEvents.playerInteractWithEntity.subscribe((event) => {
	const { target, player } = event;
	if (!load()) return;
	const ours = target.typeId === "raft:anchor" || target.typeId === "raft:knot";
	if (!ours) return;
	event.cancel = true;
	system.run(() => throwAnchor(player));
});

world.beforeEvents.playerBreakBlock.subscribe((event) => {
	if (!isPost(event.block)) return;
	event.cancel = true;
	destroy(event.player);
});

world.afterEvents.entityHitEntity.subscribe(({ damagingEntity, hitEntity }) => {
	if ((hitEntity.typeId === "raft:anchor" || hitEntity.typeId === "raft:knot") && load()) destroy(damagingEntity.typeId === "minecraft:player" ? damagingEntity : undefined);
});

// /scriptevent raft:anchor clear   removes the anchor without anyone breaking it (for testing)
system.afterEvents.scriptEventReceive.subscribe(({ id, message }) => {
	if (id === "raft:anchor" && message.trim() === "clear") destroy();
});
