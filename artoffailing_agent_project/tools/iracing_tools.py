"""
iRacing Setup Organizer
Target structure: setups\\car\\track\\setup.sto
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import os
import shutil
from pathlib import Path
from collections import defaultdict

from mcp.server.fastmcp import FastMCP

SETUPS_BASE = os.getenv("IRACING_SETUPS_PATH", r"~/Documents/iRacing/setups")  # noqa: W605

# Common abbreviations found in setup filenames → fragment to search for in existing track folder names
TRACK_HINTS: list[tuple[str, str]] = [
    ("WatkinsGlenBoot", "boot"),
    ("WatkinsGlen", "watkins glen"),
    ("Watkins_Glen", "watkins glen"),
    ("WealthwoodSB", "south boston"),
    ("Brainerd", "brainerd"),
    ("Charlotte", "charlotte"),
    ("Mosport", "canadian tire"),
    ("CTMP", "canadian tire"),
    ("Indy", "indianapolis"),
    ("Daytona", "daytona"),
    ("Sebring", "sebring"),
    ("LagunaS", "laguna seca"),
    ("Laguna", "laguna seca"),
    ("Spa", "circuit de spa"),
    ("Monza", "autodromo nazionale monza"),
    ("Imola", "imola"),
    ("Interlagos", "interlagos"),
    ("Road_Atlanta", "road atlanta"),
    ("RoadAtlanta", "road atlanta"),
    ("Rd_Atlanta", "road atlanta"),
    ("Road_America", "road america"),
    ("RoadAmerica", "road america"),
    ("Rd_Am", "road america"),
    ("LongBeach", "long beach"),
    ("Long_Beach", "long beach"),
    ("Knockhill", "knockhill"),
    ("Barber", "barber"),
    ("MidOhio", "mid ohio"),
    ("Mid_Ohio", "mid ohio"),
    ("NOLA", "nola"),
    ("Lime_Rock", "lime rock"),
    ("LimeRock", "lime rock"),
    ("Sonoma", "sonoma"),
    ("Phillip_Island", "phillip island"),
    ("PhillipIsland", "phillip island"),
    ("Suzuka", "suzuka"),
    ("RedBull", "red bull"),
    ("Red_Bull", "red bull"),
    ("Barcelona", "barcelona"),
    ("Catalunya", "barcelona"),
    ("Virginia", "virginia"),
    ("VIR", "virginia"),
    ("Homestead", "homestead"),
    ("Phoenix", "phoenix"),
    ("Pocono", "pocono"),
    ("Talladega", "talladega"),
    ("Daytona", "daytona"),
    ("Atlanta", "atlanta"),
    ("Bristol", "bristol"),
    ("Martinsville", "martinsville"),
    ("Darlington", "darlington"),
    ("COTA", "circuit of the americas"),
    ("Silverstone", "silverstone"),
    ("Nurburgring", "nurburgring"),
    ("Nurburg", "nurburgring"),
    ("Zandvoort", "zandvoort"),
    ("Brands", "brands hatch"),
    ("Donington", "donington"),
    ("Oulton", "oulton"),
    ("Snetterton", "snetterton"),
    ("Okayama", "okayama"),
    ("Bathurst", "mount panorama"),
    ("MtPanora", "mount panorama"),
    ("Motegi", "twin ring motegi"),
    ("Tsukuba", "tsukuba"),
    ("OranPark", "oran park"),
    ("Sandown", "sandown"),
    ("Adelaide", "adelaide"),
    ("Iowa", "iowa"),
    ("Richmond", "richmond"),
    ("Nashville", "nashville"),
    ("Gateway", "gateway"),
    ("NewHampshire", "new hampshire"),
    ("Dover", "dover"),
    ("Kansas", "kansas"),
    ("Michigan", "michigan"),
    ("Texas", "texas"),
    ("Vegas", "las vegas"),
    ("LasVegas", "las vegas"),
    ("Rockingham", "rockingham"),
    ("Watkins", "watkins glen"),
    ("Hocken", "hockenheim"),
    ("Chicago", "chicago"),
    ("Detroit", "detroit"),
    ("Cleveland", "cleveland"),
    ("Portland", "portland"),
    ("Toronto", "toronto"),
    ("Denver", "denver"),
    ("Baltimore", "baltimore"),
    ("Hungaroring", "hungaroring"),
    ("Budapest", "hungaroring"),
    ("Monza", "monza"),
    ("Mugello", "mugello"),
    ("Jerez", "jerez"),
    ("Estoril", "estoril"),
    ("Sochi", "sochi"),
    ("Paul_Ricard", "paul ricard"),
    ("PaulRicard", "paul ricard"),
    ("LesMans", "circuit des 24"),
    ("LeMans", "circuit des 24"),
    ("MountWash", "mt.washington"),
    ("SummitPoint", "summit point"),
    ("Summit", "summit point"),
    ("Lanier", "lanier"),
    ("SoBo", "south boston"),
    ("SouthBoston", "south boston"),
    ("SB", "south boston"),
    ("Oschersleben", "oschersleben"),
    ("Kyalami", "kyalami"),
    ("Fuji", "fuji"),
    ("Portimao", "portimao"),
    ("Istanbul", "istanbul"),
    ("Magny", "magny"),
    ("Zolder", "zolder"),
    ("Winton", "winton"),
    ("Sandown", "sandown"),
    ("Pukekohe", "pukekohe"),
    ("Bathurst", "mount panorama"),
    ("Adelaide", "adelaide"),
    ("Spielberg", "red bull"),
    ("RBRing", "red bull"),
    ("Montreal", "circuit gilles"),
    ("VLNw8", "nordschleife"),
    ("NordsVLN", "nordschleife"),
    ("Nords", "nordschleife"),
    ("MiamiRoadB", "miami"),
    ("WG", "watkins glen"),
    ("Wakins", "watkins glen"),
    ("Hungary", "hungaroring"),
    ("RAmerica", "road america"),
    ("Silv", "silverstone"),
    ("NECw", "nordschleife"),
    ("NEC", "nordschleife"),
]

# Canonical folder names to create when no existing folder matches a hint.
# Maps the hint token → exact folder name to use (will be created if missing).
TRACK_CANONICAL: dict[str, str] = {
    "WatkinsGlenBoot": "Watkins Glen International - Boot",
    "WatkinsGlen": "Watkins Glen International",
    "Watkins_Glen": "Watkins Glen International",
    "Watkins": "Watkins Glen International",
    "Hungaroring": "Hungaroring",
    "Budapest": "Hungaroring",
    "Nurburgring": "Nurburgring Grand Prix Strecke",
    "Nurburg": "Nurburgring Grand Prix Strecke",
    "LongBeach": "Long Beach Street Circuit",
    "Long_Beach": "Long Beach Street Circuit",
    "LeMans": "Circuit des 24 Heures du Mans",
    "LesMans": "Circuit des 24 Heures du Mans",
    "Interlagos": "Aut\u00f3dromo Jose Carlos Pace Interlagos",
    "Spa": "Circuit de Spa Francorchamps",
    "Monza": "Autodromo Nazionale Monza",
    "Imola": "Autodromo Internazionale Enzoe Dino Ferrari\xa0Imola",
    "Barcelona": "Circuit de Barcelona Catalunya",
    "Catalunya": "Circuit de Barcelona Catalunya",
    "COTA": "Circuit of the Americas",
    "Silverstone": "Silverstone Circuit",
    "Zandvoort": "Circuit Park Zandvoort",
    "Brands": "Brands Hatch Circuit",
    "Donington": "Donington Park Racing Circuit",
    "Oulton": "Oulton Park Circuit",
    "Snetterton": "Snetterton Circuit",
    "Okayama": "Okayama International Circuit",
    "Bathurst": "Mount Panorama Circuit",
    "MtPanora": "Mount Panorama Circuit",
    "Motegi": "Twin Ring Motegi",
    "Tsukuba": "Tsukuba Circuit",
    "OranPark": "Oran Park Raceway",
    "Phillip_Island": "Phillip Island Circuit",
    "PhillipIsland": "Phillip Island Circuit",
    "Suzuka": "Suzuka International Racing Course",
    "RedBull": "Red Bull Ring",
    "Red_Bull": "Red Bull Ring",
    "Virginia": "Virginia International Raceway",
    "VIR": "Virginia International Raceway",
    "Homestead": "Homestead Miami Speedway",
    "Phoenix": "Phoenix Raceway",
    "Pocono": "Pocono Raceway",
    "Talladega": "Talladega Super Speedway",
    "Daytona": "Daytona International Speedway",
    "Atlanta": "Atlanta Motor Speedway",
    "Bristol": "Bristol Motor Speedway",
    "Martinsville": "Martinsville Speedway",
    "Darlington": "Darlington Raceway",
    "Sebring": "Sebring International Raceway",
    "LagunaS": "WeatherTech Raceway Laguna Seca",
    "Laguna": "WeatherTech Raceway Laguna Seca",
    "Sonoma": "Sonoma Raceway",
    "Mosport": "Canadian Tire Motorsports Park",
    "CTMP": "Canadian Tire Motorsports Park",
    "Charlotte": "Charlotte Motor Speedway",
    "Barber": "Barber Motorsports Park",
    "MidOhio": "Mid Ohio Sports Car Course",
    "Mid_Ohio": "Mid Ohio Sports Car Course",
    "Knockhill": "Knockhill International Circuit",
    "Road_Atlanta": "Road Atlanta",
    "RoadAtlanta": "Road Atlanta",
    "Rd_Atlanta": "Road Atlanta",
    "MichelinRacewayRoadAtlanta": "MichelinRacewayRoadAtlanta",
    "Road_America": "Road America",
    "RoadAmerica": "Road America",
    "Rd_Am": "Road America",
    "Lime_Rock": "Lime Rock Park",
    "LimeRock": "Lime Rock Park",
    "Iowa": "Iowa Speedway",
    "Richmond": "Richmond Raceway",
    "Nashville": "Nashville Super Speedway",
    "NewHampshire": "New Hampshire Motor Speedway",
    "Dover": "Dover International Speedway",
    "Kansas": "Kansas Speedway",
    "Michigan": "Michigan International Speedway",
    "Texas": "Texas Motor Speedway",
    "Vegas": "Las Vegas Motor Speedway",
    "LasVegas": "Las Vegas Motor Speedway",
    "Rockingham": "Rockingham Speedway",
    "Hocken": "Hockenheim Ring",
    "Chicago": "Chicago Street Course",
    "Detroit": "Detroit Grand Prix at Belle Island",
    "SummitPoint": "Summit Point Motorsports Park",
    "Summit": "Summit Point Motorsports Park",
    "Lanier": "Lanier National Speedway",
    "SoBo": "South Boston Speedway",
    "SouthBoston": "South Boston Speedway",
    "MountWash": "Mt.Washington Auto Road",
    "Indy": "Indianapolis Motor Speedway",
    "Oschersleben": "Motorsport Arena Oschersleben",
    "Paul_Ricard": "Circuit Paul Ricard",
    "PaulRicard": "Circuit Paul Ricard",
    "Kyalami": "Kyalami Grand Prix Circuit",
    "Fuji": "Fuji Speedway",
    "Portimao": "Autodromo Internacional do Algarve",
    "Zolder": "Circuit Zolder",
    "Winton": "Winton Motor Raceway",
    "Spielberg": "Red Bull Ring",
    "RBRing": "Red Bull Ring",
    "Montreal": "Circuit Gilles Villeneuve",
    "VLNw8": "Nurburgring Nordschleife",
    "NordsVLN": "Nurburgring Nordschleife",
    "Nords": "Nurburgring Nordschleife",
    "MiamiRoadB": "Miami International Autodrome",
    "WG": "Watkins Glen International",
    "Wakins": "Watkins Glen International",
    "Hungary": "Hungaroring",
    "RAmerica": "Road America",
    "Silv": "Silverstone Circuit",
    "NECw": "Nurburgring Nordschleife",
    "NEC": "Nurburgring Nordschleife",
}


def _get_all_track_folders() -> dict[str, list[str]]:
    """Return {car: [track_name, ...]} for all existing track folders."""
    result: dict[str, list[str]] = defaultdict(list)
    base = Path(SETUPS_BASE)
    if not base.exists():
        return result
    for car_dir in base.iterdir():
        if car_dir.is_dir():
            for track_dir in car_dir.iterdir():
                if track_dir.is_dir():
                    result[car_dir.name].append(track_dir.name)
    return result


def _guess_track(filename: str, existing_tracks: list[str]) -> str | None:
    """Try to identify a track folder name from a .sto filename.

    Returns an existing folder name if found, or a canonical name to create.
    Returns None only if no hint matched at all.
    """
    name_lower = filename.lower()
    # Try hint table first (longer/more specific hints before shorter ones)
    for hint, fragment in TRACK_HINTS:
        if hint.lower() in name_lower:
            # Look for fragment in existing folder names
            for track in existing_tracks:
                if fragment in track.lower():
                    return track
            # No existing folder — return canonical name to create
            canonical = TRACK_CANONICAL.get(hint)
            if canonical:
                return canonical
            # Last resort: title-case the fragment
            return fragment.title()
    # Fallback: try any existing track name as a substring of the filename
    for track in sorted(existing_tracks, key=len, reverse=True):
        track_norm = track.lower().replace(" ", "").replace("-", "").replace("_", "")
        name_norm = name_lower.replace(" ", "").replace("-", "").replace("_", "")
        if len(track_norm) >= 5 and track_norm in name_norm:
            return track
    return None


def _scan(base: Path) -> dict:
    """Walk the setups directory and classify all .sto files."""
    correct: list[tuple[str, str, str]] = []    # (car, track, filename)
    flattenable: list[tuple[str, str, str]] = []  # (car, track, rel_path) — depth > 2
    loose: list[tuple[str, str]] = []            # (car, filename) — depth 1

    for root, dirs, files in os.walk(base):
        for f in files:
            if not f.lower().endswith(".sto"):
                continue
            full = Path(root) / f
            rel = full.relative_to(base)
            parts = rel.parts  # (car, [sub...]..., track, filename) or (car, filename)
            depth = len(parts) - 1  # number of directory separators

            if depth == 2:
                correct.append((parts[0], parts[1], parts[2]))
            elif depth == 1:
                loose.append((parts[0], parts[1]))
            elif depth >= 3:
                # Always: parts[0] = car, parts[-2] = track (immediate parent dir), parts[-1] = filename
                flattenable.append((parts[0], parts[-2], str(rel)))

    return {"correct": correct, "flattenable": flattenable, "loose": loose}


def register_iracing_tools(mcp: FastMCP):

    @mcp.tool()
    def iracing_scan_setups() -> str:
        """
        Analyze the iRacing setups directory and report on the current
        organization state. Shows which files are correctly placed at
        car\\track\\setup.sto, which need flattening (have extra season/
        intermediate folders), and which are loose in the car folder
        without a track subfolder.
        """
        base = Path(SETUPS_BASE)
        if not base.exists():
            return f"Setups directory not found: {SETUPS_BASE}"

        data = _scan(base)
        correct = data["correct"]
        flattenable = data["flattenable"]
        loose = data["loose"]

        # Group flattenable by car
        flat_by_car: dict[str, list] = defaultdict(list)
        for car, track, rel in flattenable:
            flat_by_car[car].append((track, rel))

        # Group loose by car
        loose_by_car: dict[str, list] = defaultdict(list)
        for car, fname in loose:
            loose_by_car[car].append(fname)

        lines = [
            f"# iRacing Setup Organization Report",
            f"Base: {SETUPS_BASE}",
            "",
            f"## Summary",
            f"- ✅ Correctly organized (car\\\\track\\\\setup.sto): **{len(correct)} files**",
            f"- 🔧 Need flattening (extra season/sub folders): **{len(flattenable)} files** across {len(flat_by_car)} cars",
            f"- ⚠️  Loose in car folder (no track subfolder): **{len(loose)} files** across {len(loose_by_car)} cars",
            f"- **Total .sto files: {len(correct) + len(flattenable) + len(loose)}**",
            "",
        ]

        if flat_by_car:
            lines.append("## Files That Need Flattening (sample, up to 3 per car)")
            for car in sorted(flat_by_car)[:20]:
                items = flat_by_car[car]
                lines.append(f"\n**{car}** ({len(items)} files)")
                for track, rel in items[:3]:
                    lines.append(f"  - `{rel}` → `{car}\\\\{track}\\\\`")
                if len(items) > 3:
                    lines.append(f"  - ...and {len(items) - 3} more")

        if loose_by_car:
            lines.append("\n## Loose Files Without Track Folder (sample, up to 3 per car)")
            all_tracks = _get_all_track_folders()
            for car in sorted(loose_by_car)[:20]:
                fnames = loose_by_car[car]
                known = all_tracks.get(car, [])
                lines.append(f"\n**{car}** ({len(fnames)} files)")
                for fname in fnames[:3]:
                    guess = _guess_track(fname, known)
                    hint = f" → guess: `{guess}`" if guess else " → ⚠️ track unknown"
                    lines.append(f"  - `{fname}`{hint}")
                if len(fnames) > 3:
                    lines.append(f"  - ...and {len(fnames) - 3} more")

        lines += [
            "",
            "---",
            "Run `iracing_organize_setups(dry_run=True)` to preview changes,",
            "or `iracing_organize_setups(dry_run=False)` to apply them.",
        ]
        return "\n".join(lines)

    @mcp.tool()
    def iracing_organize_setups(dry_run: bool = True) -> str:
        """
        Organize iRacing setup files into the correct car\\track\\setup.sto structure.

        Two operations are performed:
        1. Flatten files with extra intermediate season/sub folders:
           car\\season\\track\\file.sto  →  car\\track\\file.sto
        2. Sort loose files (car\\file.sto) into track subfolders by
           parsing the track name from the filename.

        dry_run: if True (default), preview changes without moving anything.
                 Set to False to actually move the files.

        Returns a report of all moves made (or previewed) and any files
        that could not be automatically assigned a track folder.
        """
        base = Path(SETUPS_BASE)
        if not base.exists():
            return f"Setups directory not found: {SETUPS_BASE}"

        data = _scan(base)
        flattenable = data["flattenable"]
        loose = data["loose"]

        all_tracks = _get_all_track_folders()

        moved: list[str] = []
        skipped_conflict: list[str] = []
        skipped_unknown: list[str] = []
        errors: list[str] = []

        # --- Operation 1: Flatten depth 3+ files ---
        for car, track, rel in flattenable:
            src = base / rel
            dest_dir = base / car / track
            dest = dest_dir / src.name

            if dest == src:
                continue

            if not dry_run:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    if dest.exists():
                        skipped_conflict.append(f"CONFLICT: {rel} → {car}\\{track}\\{src.name} already exists")
                        continue
                    shutil.move(str(src), str(dest))
                    moved.append(f"FLATTEN: {rel}  →  {car}\\{track}\\{src.name}")
                except Exception as e:
                    errors.append(f"ERROR moving {rel}: {e}")
            else:
                if dest.exists() and dest != src:
                    skipped_conflict.append(f"CONFLICT: {rel} → {car}\\{track}\\{src.name} already exists")
                else:
                    moved.append(f"FLATTEN: {rel}  →  {car}\\{track}\\{src.name}")

        # --- Operation 2: Sort loose files ---
        for car, fname in loose:
            src = base / car / fname
            known = all_tracks.get(car, [])
            track = _guess_track(fname, known)

            if track is None:
                skipped_unknown.append(f"UNKNOWN TRACK: {car}\\{fname}")
                continue

            dest_dir = base / car / track
            dest = dest_dir / fname

            if dest == src:
                continue

            if not dry_run:
                try:
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    if dest.exists():
                        skipped_conflict.append(f"CONFLICT: {car}\\{fname} → {car}\\{track}\\{fname} already exists")
                        continue
                    shutil.move(str(src), str(dest))
                    moved.append(f"SORT:    {car}\\{fname}  →  {car}\\{track}\\{fname}")
                except Exception as e:
                    errors.append(f"ERROR moving {car}\\{fname}: {e}")
            else:
                if dest.exists():
                    skipped_conflict.append(f"CONFLICT: {car}\\{fname} → {car}\\{track}\\{fname} already exists")
                else:
                    moved.append(f"SORT:    {car}\\{fname}  →  {car}\\{track}\\{fname}")

        # --- After flattening: clean up empty intermediate dirs ---
        cleaned_dirs: list[str] = []
        if not dry_run:
            for root, dirs, files in os.walk(base, topdown=False):
                p = Path(root)
                if p == base:
                    continue
                rel_parts = p.relative_to(base).parts
                # Only clean up dirs that are depth >= 2 (sub-folders of car folders)
                if len(rel_parts) >= 2:
                    try:
                        if not any(p.iterdir()):
                            p.rmdir()
                            cleaned_dirs.append(str(p.relative_to(base)))
                    except Exception:
                        pass

        mode = "DRY RUN — no files moved" if dry_run else "APPLIED — files moved"
        lines = [
            f"# iRacing Setup Organizer — {mode}",
            "",
            f"## Results",
            f"- Files moved/queued: {len(moved)}",
            f"- Conflicts skipped: {len(skipped_conflict)}",
            f"- Track unknown (needs manual sort): {len(skipped_unknown)}",
        ]
        if not dry_run:
            lines.append(f"- Empty dirs removed: {len(cleaned_dirs)}")
        if errors:
            lines.append(f"- Errors: {len(errors)}")

        if moved:
            lines += ["", "## Moves" + (" (preview)" if dry_run else "")]
            lines += [f"  {m}" for m in moved[:50]]
            if len(moved) > 50:
                lines.append(f"  ...and {len(moved) - 50} more")

        if skipped_conflict:
            lines += ["", "## Conflicts (skipped)"]
            lines += [f"  {s}" for s in skipped_conflict[:20]]

        if skipped_unknown:
            lines += ["", "## Unknown Track — Manual Action Required"]
            lines += [f"  {s}" for s in skipped_unknown[:50]]
            if len(skipped_unknown) > 50:
                lines.append(f"  ...and {len(skipped_unknown) - 50} more")

        if errors:
            lines += ["", "## Errors"]
            lines += [f"  {e}" for e in errors]

        if dry_run and (moved or skipped_unknown):
            lines += [
                "",
                "---",
                "To apply, call: `iracing_organize_setups(dry_run=False)`",
            ]
        return "\n".join(lines)

    @mcp.tool()
    def iracing_cleanup_empty_dirs() -> str:
        """
        Remove empty subdirectories left behind after organizing iRacing setups.
        Only removes directories that are at least 2 levels deep (car\\subfolder)
        to avoid removing car-level folders.
        """
        base = Path(SETUPS_BASE)
        if not base.exists():
            return f"Setups directory not found: {SETUPS_BASE}"

        removed: list[str] = []
        errors: list[str] = []

        for root, dirs, files in os.walk(base, topdown=False):
            p = Path(root)
            if p == base:
                continue
            rel_parts = p.relative_to(base).parts
            if len(rel_parts) >= 2:
                try:
                    if not any(p.iterdir()):
                        p.rmdir()
                        removed.append(str(p.relative_to(base)))
                except Exception as e:
                    errors.append(f"{p.relative_to(base)}: {e}")

        lines = [f"Removed {len(removed)} empty directories."]
        if removed:
            lines += [f"  - {d}" for d in removed[:50]]
            if len(removed) > 50:
                lines.append(f"  ...and {len(removed) - 50} more")
        if errors:
            lines += ["Errors:"] + [f"  {e}" for e in errors]
        return "\n".join(lines)
