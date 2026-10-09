"""Cuts the takes filmed by tools/trailer.py into the minecRAFT trailer.

Each segment is a stretch of one take, optionally sped up, with a caption faded in over it; the segments are
joined with short dissolves. Titles use the game's own fonts (Minecraft Ten for the title, Minecraft Seven for
captions), copied into the git-ignored trailer/takes/fonts/ from the game's install.

    python tools/trailer_cut.py                 # writes trailer/minecRAFT-trailer.mp4
    python tools/trailer_cut.py --music x.ogg   # lays a music track under it, faded out at the end

The trailer is 1920x1080, 30 fps, H.264, with an AAC track (silence unless --music is given), which is what
YouTube asks for.
"""

import argparse
import os
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAKES = "trailer/takes"   # relative, so no drive letter's colon has to be escaped inside a filter
OUT = "trailer/minecRAFT-trailer.mp4"
DISSOLVE = 0.6

# take, start, seconds of take used, speed, caption (title segments are handled by name)
SEGMENTS = [
    ("open", 0.8, 9.0, 1, None),
    ("drift", 0.6, 7.5, 1, "Drift on an endless ocean"),
    ("fish", 1.0, 10.5, 1, "Hook whatever floats by"),
    ("horizon", 4.0, 64.0, 6, "Then, on the horizon..."),
    ("alongside", 0.3, 9.0, 1, "Small Island 1, straight out of Raft"),
    ("anchor", 1.0, 7.8, 1, "Throw your anchor"),
    ("explore", 0.3, 15.0, 1, "Climb it, chop it, mine it, loot it"),
    ("hut", 0.3, 6.5, 1, "The abandoned hut and its loot box"),
    ("underwater", 0.3, 7.5, 1, "Ore, clay and kelp below"),
    ("castoff", 1.0, 8.0, 1, "Break the anchor's post..."),
    ("castoff", 9.0, 34.0, 4, "...and drift on"),
    ("end", 0.3, 7.5, 1, None),
]


def esc(text):
    return text.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace(",", "\\,")


def caption(text, length):
    """Lower-left caption in Minecraft Seven, fading in after half a second and out before the dissolve."""
    a = f"if(lt(t\\,0.5)\\,0\\,if(lt(t\\,1.0)\\,(t-0.5)/0.5\\,if(lt(t\\,{length - 1.0:.2f})\\,1\\,max(0\\,({length - 0.5:.2f}-t)/0.5))))"
    return (f"drawtext=fontfile={TAKES}/fonts/seven.ttf:text='{esc(text)}':fontsize=54:fontcolor=white:alpha='{a}'"
            f":shadowcolor=black@0.7:shadowx=4:shadowy=4:x=90:y=h-160")


def wordmark():
    """The minecRAFT wordmark as an image: Minecraft Ten is capitals only, so the pun is carried by colour, MINEC in
    white and RAFT in plank orange. Written to the git-ignored takes folder."""
    from PIL import Image, ImageDraw, ImageFont
    ten = ImageFont.truetype(os.path.join(ROOT, TAKES, "fonts", "ten.otf"), 180)
    parts = [("MINEC", (255, 255, 255)), ("RAFT", (236, 164, 74))]
    img = Image.new("RGBA", (int(sum(ten.getlength(t) for t, _ in parts)) + 40, 240), (0, 0, 0, 0))
    draw, x = ImageDraw.Draw(img), 20
    for text, colour in parts:
        draw.text((x + 9, 29), text, font=ten, fill=(0, 0, 0, 150))
        draw.text((x, 20), text, font=ten, fill=colour + (255,))
        x += ten.getlength(text)
    img.save(os.path.join(ROOT, TAKES, "title.png"))


def title(sub, length, start=1.2):
    """The line under the wordmark; the wordmark itself is overlaid by segment()."""
    a = f"if(lt(t\\,{start})\\,0\\,if(lt(t\\,{start + 0.8})\\,(t-{start})/0.8\\,if(lt(t\\,{length - 1.2:.2f})\\,1\\,max(0\\,({length - 0.6:.2f}-t)/0.6))))"
    return (f"drawtext=fontfile={TAKES}/fonts/seven.ttf:text='{esc(sub)}':fontsize=56:fontcolor=white:alpha='{a}'"
            f":shadowcolor=black@0.6:shadowx=4:shadowy=4:x=(w-tw)/2:y=h*0.30+190")


def end_card(length):
    a = f"if(lt(t\\,1.0)\\,0\\,min(1\\,(t-1.0)/0.8))"
    return (f"drawtext=fontfile={TAKES}/fonts/seven.ttf:text='Free for Minecraft\\: Bedrock Edition':fontsize=58:fontcolor=white:alpha='{a}'"
            f":shadowcolor=black@0.6:shadowx=4:shadowy=4:x=(w-tw)/2:y=h*0.26+190,"
            f"drawtext=fontfile={TAKES}/fonts/seven.ttf:text='Planet Minecraft  ·  github.com/kirbycope/minecRAFT-bedrock':fontsize=42:fontcolor=white:alpha='{a}'"
            f":shadowcolor=black@0.6:shadowx=3:shadowy=3:x=(w-tw)/2:y=h*0.26+275")


def segment(i, take, start, used, speed, text):
    length = used / speed
    filters = [f"setpts=(PTS-STARTPTS)/{speed}", "fps=30", "scale=1920:1080"]
    if take == "open": filters.append(title("Raft, in Minecraft: Bedrock Edition", length))
    elif take == "end": filters.append(end_card(length))
    elif text: filters.append(caption(text, length))
    fades = []
    if i == 0: fades.append("fade=t=in:st=0:d=1.0")
    if i == len(SEGMENTS) - 1: fades.append(f"fade=t=out:st={length - 1.2:.2f}:d=1.2")
    inputs = ["-ss", str(start), "-t", str(used), "-i", f"{TAKES}/{take}.mp4"]
    graph = f"[0:v]{','.join(filters + fades)}[v]"
    if take in ("open", "end"):
        # The wordmark fades with the text under it: in at 1.2 s (1.0 s on the end card), out with the open's text.
        fade_in = 1.2 if take == "open" else 1.0
        fade_out = f",fade=t=out:st={length - 1.2:.2f}:d=0.6:alpha=1" if take == "open" else ""
        y = "H*0.30-40" if take == "open" else "H*0.26-40"
        inputs += ["-loop", "1", "-t", f"{length:.3f}", "-i", f"{TAKES}/title.png"]
        graph = (f"[1:v]format=rgba,fade=t=in:st={fade_in}:d=0.8:alpha=1{fade_out}[t];"
                 f"[0:v]{','.join(filters)}[b];[b][t]overlay=(W-w)/2:{y}:shortest=1[o];[o]{','.join(fades) or 'null'}[v]")
    path = f"{TAKES}/seg_{i:02d}.mp4"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs,
                    "-filter_complex", graph, "-map", "[v]", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p", path],
                   check=True, cwd=ROOT)
    return path, length


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--music", help="an audio file to lay under the trailer")
    args = parser.parse_args()

    wordmark()
    parts = [segment(i, *s) for i, s in enumerate(SEGMENTS)]
    inputs, chain, offset, last = [], [], 0.0, "0:v"
    for i, (path, length) in enumerate(parts):
        inputs += ["-i", path]
        if i == 0:
            offset = length - DISSOLVE
            continue
        label = f"v{i}"
        chain.append(f"[{last}][{i}:v]xfade=transition=fade:duration={DISSOLVE}:offset={offset:.3f}[{label}]")
        last, offset = label, offset + length - DISSOLVE
    total = offset + DISSOLVE
    audio_index = len(parts)
    if args.music:
        inputs += ["-i", args.music]
        chain.append(f"[{audio_index}:a]atrim=0:{total:.3f},afade=t=in:d=1.5,afade=t=out:st={total - 3:.3f}:d=3[a]")
    else:
        inputs += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        chain.append(f"[{audio_index}:a]anull[a]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(chain), "-map", f"[{last}]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT], check=True, cwd=ROOT)
    print(f"wrote {OUT} ({total:.1f} s)")


if __name__ == "__main__":
    main()
