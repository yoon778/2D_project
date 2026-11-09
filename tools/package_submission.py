"""Build a submission ZIP from the game modules and their runtime assets."""
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
ASSETS = GAME / "assets"
CREDITS = {
    "sources/courier-imagegen-prompts.json":
        "art/player/style-studies/eight-direction-consistency/generation-prompts.json",
    "sources/zombie-imagegen-prompt.md": "art/zombie/studies/imagegen-prompt.md",
}


def metadata_assets(relative_path):
    path = ASSETS / relative_path
    return path, json.loads(path.read_text(encoding="utf-8"))


def add_sprite(files, directory, source, *, empty=False):
    image = directory / source["image"]
    files.add(image)
    if empty:
        files.add(image.with_stem(image.stem + "-empty"))


def runtime_files():
    files = set(GAME.glob("*.py"))
    files.update((ROOT / "PRD.md", GAME / "requirements.txt", ASSETS / "props/alley-trash-can.png"))
    files.update(ASSETS / "neighborhood" / name
                 for name in ("ground.png", "west-house.png", "east-house.png", "fence.png",
                              "shop.png", "bus-stop.png", "streetlamp.png", "workshop.png", "roads.json"))
    files.update(ASSETS / "audio" / name for name in ("last-delivery.mp3", "zombie_step.wav", "zombie_groan.wav"))

    player_path, player = metadata_assets("player/r1b-courier-atlas-20261104.json")
    files.add(player_path)
    for facing, frames in player["frames"].items():
        for key in {frame["source"] for frame in frames}:
            add_sprite(files, player_path.parent, player["sources"][key], empty=facing not in ("back", "back_right"))

    for facing, filename in player.get("sprint", {}).get("images", {}).items():
        add_sprite(files, player_path.parent, {"image": filename}, empty=facing not in ("back", "back_right"))

    combat_path, combat = metadata_assets("combat/r2a-combat-20261106.json")
    files.add(combat_path)
    for name, source in combat.items():
        if name.startswith("attack"):
            add_sprite(files, combat_path.parent, source, empty=source["facing"] not in ("back", "back_right"))

    for name in ("r2z-zombie-20261106.json", "r2za-zombie-attack-20261106.json"):
        path, source = metadata_assets(f"zombie/{name}")
        files.add(path)
        add_sprite(files, path.parent, source)
    return files


def main():
    files = runtime_files()
    guide = ROOT / "SUBMISSION.md"
    for path in sorted(files | {guide} | {ROOT / source for source in CREDITS.values()}):
        if not path.is_file():
            raise FileNotFoundError(path)

    destination = ROOT / "output/submit/Dead_Route.zip"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    with ZipFile(temporary, "w", ZIP_DEFLATED) as archive:
        archive.write(guide, "Dead_Route/README.md")
        for target, source in CREDITS.items():
            archive.write(ROOT / source, f"Dead_Route/{target}")
        for path in sorted(files):
            archive.write(path, f"Dead_Route/{path.relative_to(ROOT).as_posix()}")
    with ZipFile(temporary) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise ValueError(f"Corrupt ZIP entry: {corrupt}")
    temporary.replace(destination)
    print(f"{destination} ({len(files) + 1 + len(CREDITS)} files)")


if __name__ == "__main__":
    main()
