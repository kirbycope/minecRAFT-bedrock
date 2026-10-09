"""Films the minecRAFT trailer and the Planet Minecraft screenshots on the local server, one shot at a time.

Drives the Minecraft client on the PC through cobblemon-bedrock's tools/bridge.py (commands on the server) and
tools/client_drive.py (real input), with Bedrock's /camera free camera for eased moves and /hud to hide the HUD.
The screen is recorded with ffmpeg's gdigrab: the 1920x1080 middle of the game window, 30 fps.

    python tools/trailer.py prep            # world state for filming: noon, clear, no island, anchor on the raft
    python tools/trailer.py shot <name>     # films one shot into trailer/takes/<name>.mp4
    python tools/trailer.py still <name>    # one 1920x1080 still into trailer/screenshots/<name>.png

Shots are the SHOTS table below, in trailer order. tools/trailer_cut.py cuts the takes into the trailer.
"""

import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "cobblemon-bedrock", "tools"))
from bridge import Bridge, protect  # noqa: E402
import client_drive as cd  # noqa: E402
import pydirectinput  # noqa: E402

TAKES = os.path.join(ROOT, "trailer", "takes")
STILLS = os.path.join(ROOT, "trailer", "screenshots")
GAME_TOP = 38   # the game window's 16:9 middle starts this far down the 1920x1200 screen
P = "Kirbycope"

b = Bridge()


def run(*commands):
    for c in commands:
        out = b.command(c)
        if "success_count: 0" in out and not c.startswith(("kill", "scriptevent")):
            print(f"  ! {c} -> {out.strip()}")


def cam(x, y, z, fx, fy, fz, ease=0.0, kind="in_out_sine"):
    e = f" ease {ease} {kind}" if ease else ""
    run(f"camera {P} set minecraft:free{e} pos {x} {y} {z} facing {fx} {fy} {fz}")


def record(name, seconds):
    os.makedirs(TAKES, exist_ok=True)
    path = os.path.join(TAKES, f"{name}.mp4")
    return subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "0",
                             "-offset_x", "0", "-offset_y", str(GAME_TOP), "-video_size", "1920x1080", "-t", str(seconds),
                             "-i", "desktop", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "14", "-pix_fmt", "yuv420p", path])


def still(name):
    from PIL import Image
    os.makedirs(STILLS, exist_ok=True)
    shot = cd.shot(f"still_{name}")
    path = os.path.join(STILLS, f"{name}.png")
    Image.open(shot).convert("RGB").crop((0, GAME_TOP, 1920, GAME_TOP + 1080)).save(path, optimize=True)
    print(path)


def resume():
    """Bring the game to the front and close the pause menu it opens whenever it loses focus (a Windows toast,
    for one), which would otherwise be filmed."""
    cd.focus(); time.sleep(0.4)
    # OCR cannot read the green Resume Game button, so the menu is known by its other buttons and Resume is
    # clicked where it sits.
    if cd.find_text(["save & quit", "browse add", "dressing room"]):
        cd.click(563, 400); time.sleep(1.0)
    # Any input clears the game's idle state, or "You've been away for a bit" dims the screen mid-take.
    cd.key("1"); time.sleep(0.5)


def hud(show_hotbar=False):
    resume()
    run(f"hud {P} hide all")
    if show_hotbar: run(f"hud {P} reset hotbar")


def entity_x(query):
    r = b.tool("mc_entity_get", query=query)
    m = re.search(r"x: (-?[\d.]+)", r)
    return float(m.group(1)) if m else None


def island_x():
    """The anchored island's x, found from the hut's chest (island local 3, 12, 6)."""
    for x in range(-80, 20):
        if "success_count: 1" in b.command(f"testforblock {x + 3} 75 8 chest"): return x
    return None


def cast_and_catch(kind="barrel_side", tag="barrel", scale="scale_0.6", upstream=3.0):
    """Cast, drop a piece of flotsam just upstream of where the bobber lands, wait for it to be caught."""
    cd.focus(); time.sleep(0.3); cd.key("1"); time.sleep(0.3)
    cd.interact(); time.sleep(2.2)
    hx = entity_x({"type": "minecraft:fishing_hook"})
    r = b.tool("mc_entity_get", query={"type": "minecraft:fishing_hook"})
    hz = float(re.search(r"z: (-?[\d.]+)", r).group(1)) if hx is not None else 1.5
    if hx is None: return False
    run(f"summon display:block {hx - upstream} 63.55 {hz} 0 0 {kind}")
    time.sleep(0.3)
    run(f"event entity @e[type=display:block,tag=!flotsam,tag=!island] {scale}",
        f"tag @e[type=display:block,tag=!flotsam,tag=!island] add flotsam:{tag}",
        f"tag @e[tag=flotsam:{tag},tag=!flotsam] add flotsam")
    return True


def prep():
    protect(b)
    run("gamerule sendcommandfeedback false", "gamerule commandblockoutput false", "gamerule dodaylightcycle false",
        "gamerule doweathercycle false", "gamerule keepinventory true", "time set 4000", "weather clear",
        "scriptevent raft:island clear", "scriptevent raft:anchor clear", "kill @e[type=item]", f"clear {P}",
        f"give {P} fishing_rod", f"replaceitem entity {P} slot.hotbar 8 raft:throwable_anchor 1",
        f"camera {P} clear", f"hud {P} reset", f"tp {P} 1.5 64 1.5 90 60")
    time.sleep(1); cd.focus(); time.sleep(0.3); cd.key("9"); time.sleep(0.5)
    cd.interact(); time.sleep(1.5)   # sets the anchor down on the raft
    print("post:", b.command("testforblock 0 64 1 oak_fence").strip(), "anchor:", b.command("testfor @e[type=raft:anchor]").strip())
    cd.key("1")
    run(f"tp {P} 1.5 64 1.5 90 0")


# --- the shots, in trailer order --------------------------------------------------------------------------------

def shot_open():
    hud(); run(f"tp {P} 1.2 64 1.5 90 0")
    cam(20, 73, -26, 1, 64, 1)
    time.sleep(1.5)
    rec = record("open", 10); time.sleep(0.8)
    cam(5, 65.6, -4.5, 1, 64.6, 1.2, ease=9)
    rec.wait()


FLOTSAM_KINDS = {"barrel": ("barrel_side", "scale_0.6"), "plank": ("planks_jungle", "scale_0.4"), "palm_leaf": ("azalea_leaves", "scale_0.4")}


def piece(x, z, kind):
    """One piece of flotsam put in the current where the camera will see it."""
    variant, scale = FLOTSAM_KINDS[kind]
    run(f"summon display:block {x} 63.55 {z} 0 0 {variant}")
    time.sleep(0.2)
    run(f"event entity @e[type=display:block,tag=!flotsam,tag=!island] {scale}",
        f"tag @e[type=display:block,tag=!flotsam,tag=!island] add flotsam:{kind}",
        f"tag @e[tag=flotsam:{kind},tag=!flotsam] add flotsam")


def shot_drift():
    hud(); run(f"tp {P} 1.2 64 1.5 90 0")
    for x, z, kind in ((-9, -3, "barrel"), (-13, -5.5, "plank"), (-17, -2.5, "palm_leaf"), (-21, -6, "plank"), (-25, -3.5, "barrel"), (-29, -5, "palm_leaf")):
        piece(x, z, kind)
    cam(-5, 64.5, -4, -22, 64.2, 0)
    time.sleep(1.5)
    rec = record("drift", 9); time.sleep(0.5)
    cam(-1.5, 65.2, -3.5, -14, 64.2, 1, ease=8.5, kind="linear")
    rec.wait()


def shot_fish():
    hud(show_hotbar=True); run(f"camera {P} clear", f"tp {P} 1.5 64 0.5 120 14")
    time.sleep(1.5)
    rec = record("fish", 13); time.sleep(1.5)
    if cast_and_catch():
        t0 = time.time()
        while time.time() - t0 < 8 and "success_count: 1" not in b.command("testfor @e[tag=hooked]"): time.sleep(0.3)
        time.sleep(2.0)
        cd.interact()
    rec.wait()


def shot_horizon():
    """Real time; the cut speeds it up. The island appears slice by slice and comes on toward the raft."""
    hud(); run(f"tp {P} 1.2 64 1.5 90 0", "scriptevent raft:island clear", "scriptevent raft:island start")
    cam(3, 66.5, -3, -40, 68, 10)
    time.sleep(0.5)
    rec = record("horizon", 70); time.sleep(10)
    cam(2, 66, -3.5, -30, 67, 9, ease=55, kind="linear")
    rec.wait()


def shot_alongside():
    hud()
    cam(-6, 70, -22, -16, 70, 8)
    time.sleep(1)
    rec = record("alongside", 10); time.sleep(0.3)
    cam(4, 69, -20, -10, 69, 8, ease=9.5, kind="linear")
    rec.wait()


def shot_anchor():
    hud(); run(f"tp {P} 1.5 64 0.5 45 38")
    cam(4.5, 65.8, -2.5, -0.5, 63.8, 1.5)
    time.sleep(1)
    rec = record("anchor", 9); time.sleep(1.5)
    cd.focus(); time.sleep(0.2); cd.key("9"); time.sleep(0.3)
    cd.interact()
    time.sleep(1.5)
    cam(5.5, 66.5, -4, -3, 61, 1.5, ease=5)
    rec.wait()
    print("island entities:", b.command("testfor @e[tag=island]").strip(), "island x:", island_x())


def shot_explore():
    ox = island_x() or -16
    hud(); run(f"tp {P} 1.5 64 1.5 90 0")
    cam(ox + 40, 70, -6, ox + 16, 70, 8)
    time.sleep(1)
    rec = record("explore", 16); time.sleep(0.3)
    cam(ox + 30, 80, -10, ox + 12, 72, 8, ease=7.5)
    time.sleep(7.6)
    cam(ox + 4, 84, -8, ox + 5, 74, 8, ease=7.5)
    rec.wait()


def shot_hut():
    ox = island_x() or -16
    hud(); run(f"tp {P} {ox + 4.5} 76 {9.5} 0 0")
    cam(ox + 9, 79, 2, ox + 3.5, 76, 8)
    time.sleep(1)
    rec = record("hut", 8); time.sleep(0.3)
    cam(ox + 1, 79.5, 1.5, ox + 3.5, 76, 8, ease=7.5)
    rec.wait()


def shot_underwater():
    ox = island_x() or -16
    hud()
    cam(ox + 30, 60, -4, ox + 24, 56, 6)
    time.sleep(1)
    rec = record("underwater", 9); time.sleep(0.3)
    cam(ox + 20, 59.5, -5, ox + 14, 55, 6, ease=8.5, kind="linear")
    rec.wait()


def shot_castoff():
    """The player breaks the post; the island lets go and drifts away. Real time; the cut speeds up the drift."""
    hud(); run(f"tp {P} 1.5 64 0.5 45 38")
    cam(5, 66, -3.5, -1, 64, 1.5)
    time.sleep(1)
    rec = record("castoff", 45); time.sleep(1)
    cd.focus(); time.sleep(0.2); cd.key("9"); time.sleep(0.3)
    pydirectinput.mouseDown(); time.sleep(4.5); pydirectinput.mouseUp()
    time.sleep(2)
    cam(12, 76, -24, 10, 66, 8, ease=6)
    time.sleep(7)
    cam(26, 74, -22, 30, 66, 8, ease=28, kind="linear")
    rec.wait()


def shot_end():
    hud(); run(f"tp {P} 1.2 64 1.5 270 0")
    cam(6, 66, -5, 1, 64.6, 1.2)
    time.sleep(1)
    rec = record("end", 8); time.sleep(0.3)
    cam(18, 76, -22, 1, 64.6, 1.2, ease=7.5)
    rec.wait()


def shot_portfolio():
    """timothycope.com's card preview: 10 s of one steady take, the island drifting past the raft in real time,
    with nothing in the bottom corners (the site draws its icon there)."""
    run("scriptevent raft:island clear", "scriptevent raft:anchor clear", "kill @e[type=wandering_trader]", "kill @e[type=trader_llama]",
        "kill @e[type=item]", f"tp {P} 1.5 64 1.5 270 10", "scriptevent raft:island start -60")
    hud()
    cam(-12, 82, -40, -22, 64, 8)
    time.sleep(2)
    rec = record("portfolio", 11)
    rec.wait()


def stills():
    """The Planet Minecraft screenshots, in one pass through the encounter. Run prep first."""
    hud(); run(f"tp {P} 1.2 64 1.5 270 0")
    for x, z, kind in ((-6, -2.5, "barrel"), (-9, 4, "plank"), (-12, -1, "palm_leaf"), (-15, 5, "plank"), (-4, 6, "barrel")):
        piece(x, z, kind)
    cam(7.5, 66.2, -4.5, 0.5, 64.4, 1.5); time.sleep(1.5); still("01_raft")
    cam(1.6, 64.4, 4.2, 0.6, 64.6, 1.2); time.sleep(1.5); still("02_anchor")

    run(f"camera {P} clear", f"tp {P} 1.5 64 0.5 120 14"); hud(show_hotbar=True)
    time.sleep(1)
    if cast_and_catch():
        t0 = time.time()
        while time.time() - t0 < 8 and "success_count: 1" not in b.command("testfor @e[tag=hooked]"): time.sleep(0.3)
        time.sleep(0.8); still("03_fishing")
        cd.interact()

    hud(); run(f"tp {P} 1.2 64 1.5 90 0", "scriptevent raft:island clear", "scriptevent raft:island start -70")
    cam(3, 66.5, -3, -40, 68, 10)
    time.sleep(24); still("04_island_ahead")
    while (entity_x({"tags": ["island"], "closest": 1, "location": {"x": -16, "y": 70, "z": 9}}) or -99) < -40: time.sleep(1)
    time.sleep(14)
    run(f"tp {P} 1.5 64 0.5 45 38")
    cd.focus(); time.sleep(0.2); cd.key("9"); time.sleep(0.3); cd.interact()
    for _ in range(40):
        if island_x() is not None: break
        time.sleep(1)
    ox = island_x()
    print("anchored at", ox)
    if ox is None: return
    time.sleep(3)
    run(f"tp {P} {ox + 4.5} 76 9.5 0 0")
    cam(ox + 44, 72, -16, ox + 16, 70, 8); time.sleep(2); still("05_island")
    cam(ox + 30, 84, -12, ox + 12, 70, 8); time.sleep(2); still("06_island_above")
    cam(ox + 8.5, 78.5, 2.5, ox + 3.5, 76, 8); time.sleep(2); still("07_hut")
    cam(ox + 26, 59.5, -4, ox + 18, 55.5, 6); time.sleep(2); still("08_underwater")
    run(f"tp {P} 1.5 64 1.5 90 0")
    cam(6, 66, -3.5, -4, 66, 6); time.sleep(2); still("09_alongside")


SHOTS = {name[5:]: fn for name, fn in globals().items() if name.startswith("shot_")}

if __name__ == "__main__":
    what, *args = sys.argv[1:]
    if what == "prep": prep()
    elif what == "shot":
        SHOTS[args[0]]()
        print(os.path.join(TAKES, f"{args[0]}.mp4"))
    elif what == "still": still(args[0])
    elif what == "stills": stills()
    elif what == "cam": cam(*map(float, args[:6]))
    elif what == "reset": run(f"camera {P} clear", f"hud {P} reset")
