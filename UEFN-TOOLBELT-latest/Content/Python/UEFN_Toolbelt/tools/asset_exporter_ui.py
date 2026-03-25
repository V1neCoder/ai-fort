"""
╔══════════════════════════════════════════════════════════════════════╗
║           UEFN ASSET EXPORTER / IMPORTER  v5.3                       ║
║                                                                      ║
║  v5.0 — PROPER UASSET HEADER PARSING                                ║
║    • Parses the actual UAsset Name Table + Import Table              ║
║      instead of regex-matching raw bytes.  This is how UE itself     ║
║      knows what a file depends on.                                   ║
║    • Scans .uasset AND .uexp for additional path strings             ║
║    • Export goes into ONE folder: ExportName/Meshes/, /Materials/…   ║
║    • Full chain: Prefab→Mesh→MI→Master Mat→Textures + Verse         ║
║    • Detailed log with every ref found / matched / missed            ║
║    • CPU yields so UEFN doesn't freeze                               ║
║    • UEFN tick-mode auto-detection (same as v4.x)                    ║
║                                                                      ║
║  v4.x features kept:                                                 ║
║    • Project auto-detection, Import tab, Organize tab                ║
║    • Category filter buttons, folder filter, search                  ║
║    • Double-click protection, manifest export                        ║
╚══════════════════════════════════════════════════════════════════════╝

Requirements:  Python 3.10+
Standalone:    python uefn_asset_exporter_v5.py
Inside UEFN:   py "C:/path/to/uefn_asset_exporter_v5.py"
"""

import os, sys, json, shutil, hashlib, struct, threading, re, time, platform
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from io import StringIO
from tkinter import (Tk, Frame, Label, Button, Entry, Listbox, Scrollbar, Text,
    filedialog, messagebox, StringVar, BooleanVar,
    END, BOTH, LEFT, RIGHT, TOP, BOTTOM, X, Y, W, E, N, S,
    VERTICAL, EXTENDED, DISABLED, NORMAL, WORD)
from tkinter import ttk

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

UEFN_PRIMARY_EXT  = {".uasset", ".umap"}
UEFN_COMPANION_EXT = {".uexp", ".ubulk"}
VERSE_EXT          = {".verse"}
ALL_SCANNABLE      = UEFN_PRIMARY_EXT | VERSE_EXT
EXPORT_MANIFEST    = "export_manifest.json"
CPU_YIELD_EVERY    = 30
CPU_YIELD_SEC      = 0.004

UASSET_MAGIC = 0x9E2A83C1   # UE4 package magic number (little-endian)

CATEGORY_RULES = [
    # (Category, name_patterns, folder_patterns)
    ("Prefab",    ["_prefab","prefab_","PFB_","PF_","PRF_"],
                  ["Prefabs","prefab","PrefabActors"]),
    ("Blueprint", ["BP_","_BP"],
                  ["Blueprints","Blueprint"]),
    ("Verse",     [],
                  ["Verse","VerseScripts","verse"]),
    ("Mesh",      ["SM_","SK_","SKM_","S_M_","StaticMesh","SkeletalMesh","GEO_"],
                  ["Meshes","Mesh","StaticMesh","Geometry","StaticMeshes"]),
    ("Material",  ["M_","MI_","Mat_","MF_","MPC_","MaterialInst","MasterMat"],
                  ["Materials","Material","MaterialInstances"]),
    ("Texture",   ["T_","TX_","Tex_","Icon_"],
                  ["Textures","Texture","Icons"]),
    ("Animation", ["A_","Anim_","ABP_","AM_"],
                  ["Animations","Anim"]),
    ("Sound",     ["SFX_","SND_","Sound_","Cue_","AK_","Audio_"],
                  ["Sounds","Audio","SFX","Music"]),
    ("Particle",  ["P_","PS_","FX_","NS_","Niagara_"],
                  ["Particles","FX","Niagara","Effects","VFX"]),
    ("UI",        ["UI_","UMG_","Widget_","W_","HUD_"],
                  ["UI","Widgets","HUD"]),
    ("Map",       [],
                  ["Maps","Levels"]),
    ("Data",      ["DT_","DA_","DataTable","Curve_"],
                  ["Data","DataTables"]),
]

ORGANIZE_FOLDERS = {
    "Prefab":"Prefabs","Blueprint":"Blueprints","Verse":"Verse",
    "Mesh":"Meshes","Material":"Materials","Texture":"Textures",
    "Animation":"Animations","Sound":"Audio","Particle":"Effects",
    "UI":"UI","Map":"Maps","Data":"Data","Other":"Other",
}

CATEGORY_ICONS = {
    "Prefab":"🏗️","Blueprint":"📐","Verse":"📜","Mesh":"🔷",
    "Material":"🎨","Texture":"🖼️","Animation":"🎬","Sound":"🔊",
    "Particle":"✨","UI":"🖥️","Map":"🗺️","Data":"📊","Other":"📄",
}

# Name-prefix chain for fallback matching
RELATED_PREFIXES = {
    "PFB_": ["SM_","SK_","SKM_","GEO_","M_","MI_","T_","Mat_","MF_","SFX_","SND_","NS_","FX_","P_"],
    "PF_":  ["SM_","SK_","SKM_","GEO_","M_","MI_","T_","Mat_","MF_","SFX_","SND_","NS_","FX_","P_"],
    "PRF_": ["SM_","SK_","SKM_","GEO_","M_","MI_","T_","Mat_","MF_","SFX_","SND_","NS_","FX_","P_"],
    "BP_":  ["SM_","SK_","SKM_","GEO_","M_","MI_","T_","Mat_","MF_","SFX_","SND_","NS_","FX_","P_"],
    "SM_":  ["M_","MI_","T_","Mat_","MF_"],
    "SK_":  ["M_","MI_","T_","Mat_","MF_"],
    "SKM_": ["M_","MI_","T_","Mat_","MF_"],
    "GEO_": ["M_","MI_","T_","MF_"],
    "MI_":  ["M_","MF_","T_","Mat_"],
    "Mat_": ["M_","MF_","T_"],
    "M_":   ["T_","MF_"],
    "MF_":  ["T_"],
}

# Catppuccin Mocha theme (the clean blue one)
BG_DARK="#1e1e2e"; BG_MID="#282840"; BG_LIGHT="#313244"; BG_INPUT="#313244"
ACCENT="#89b4fa"; ACCENT_HOVER="#74c7ec"
TEXT_PRIMARY="#cdd6f4"; TEXT_SECONDARY="#a6adc8"; TEXT_DIM="#6c7086"
SUCCESS="#a6e3a1"; WARNING="#f9e2af"; SELECT="#45475a"


# ─────────────────────────────────────────────
# LOGGER  (in-memory, feeds the Log tab)
# ─────────────────────────────────────────────

class ToolLogger:
    def __init__(self):
        self._buf = StringIO()

    def info(self, msg):
        self._buf.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

    def warn(self, msg):
        self._buf.write(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠ {msg}\n")

    def debug(self, msg):
        self._buf.write(f"[{datetime.now().strftime('%H:%M:%S')}]   {msg}\n")

    def text(self):
        return self._buf.getvalue()

    def clear(self):
        self._buf = StringIO()

log = ToolLogger()


# ─────────────────────────────────────────────
# UASSET HEADER PARSER
# ─────────────────────────────────────────────
# Reads the Name Table and Import Table from .uasset files.
# The Import Table lists every external package/object this
# asset depends on — this is how UE knows what to load.
# ─────────────────────────────────────────────

def parse_uasset_names_and_imports(filepath: Path) -> tuple[list[str], list[str]]:
    """
    Parse a .uasset file's header to extract:
      - names:   the Name Table (list of FName strings)
      - imports: reconstructed package paths from the Import Table

    Returns (names_list, import_paths_list).
    On any parse failure, returns ([], []).
    """
    names: list[str] = []
    import_paths: list[str] = []

    try:
        with open(filepath, "rb") as f:
            data = f.read()

        if len(data) < 100:
            return names, import_paths

        # ── Read the package summary header ──
        # Offset 0: Magic (4 bytes, LE uint32)
        magic = struct.unpack_from("<I", data, 0)[0]
        if magic != UASSET_MAGIC:
            log.debug(f"    Not a valid UAsset (magic=0x{magic:08X}): {filepath.name}")
            return names, import_paths

        # The header layout varies by UE version, but the core fields are:
        # Offset  0: Tag/Magic           (uint32)
        # Offset  4: LegacyFileVersion   (int32)  — usually negative for UE4+
        # We need to find NameCount, NameOffset, ImportCount, ImportOffset.
        #
        # For UE4/UE5 (LegacyFileVersion < 0):
        #   After skipping version fields, the summary contains:
        #     NameCount    @ offset varies
        #     NameOffset   @ offset varies
        #     ImportCount
        #     ImportOffset
        #     ExportCount
        #     ExportOffset
        #
        # Rather than hardcoding every version's offsets, we use a pragmatic
        # approach: scan for the Name Table by looking for a plausible
        # (count, offset) pair, then validate by reading names at that offset.

        legacy_ver = struct.unpack_from("<i", data, 4)[0]

        # ── Try known offset layouts ──
        # UE4.27 / UE5.0-5.4 / UEFN typically have these at:
        #   NameCount  @ 41 (or nearby), NameOffset @ 45
        #   ImportCount @ 69, ImportOffset @ 73
        #   (but this shifts with version fields)
        #
        # Strategy: search common offset ranges for a (count, offset) pair
        # where offset points into the file and count is reasonable.

        name_count = 0
        name_offset = 0
        import_count = 0
        import_offset = 0

        # Scan for NameCount/NameOffset in the first 200 bytes
        best_name_score = -1
        for probe in range(20, 180, 4):
            if probe + 8 > len(data):
                break
            nc = struct.unpack_from("<i", data, probe)[0]
            no = struct.unpack_from("<i", data, probe + 4)[0]
            # Plausibility: count 1..500000, offset within file, offset > 100
            if 1 <= nc <= 500000 and 100 < no < len(data):
                # Try reading the first name at that offset
                test_name = _try_read_fname(data, no)
                if test_name and len(test_name) > 0 and test_name.isprintable():
                    score = nc  # prefer the probe that gives most names
                    if score > best_name_score:
                        best_name_score = score
                        name_count = nc
                        name_offset = no

        if name_count == 0:
            log.debug(f"    Could not find Name Table in {filepath.name}")
            return names, import_paths

        # ── Read the Name Table ──
        pos = name_offset
        for _ in range(name_count):
            if pos + 4 > len(data):
                break
            # FNameEntrySerialized: int32 length (including null terminator), then chars
            # If length > 0: UTF-8.  If length < 0: abs(length) UTF-16 chars.
            str_len = struct.unpack_from("<i", data, pos)[0]
            pos += 4

            if str_len == 0:
                names.append("")
                continue

            if str_len > 0:
                # UTF-8, includes null terminator
                if pos + str_len > len(data):
                    break
                raw = data[pos:pos + str_len - 1]  # skip null
                names.append(raw.decode("utf-8", errors="replace"))
                pos += str_len
            else:
                # UTF-16
                char_count = -str_len
                byte_count = char_count * 2
                if pos + byte_count > len(data):
                    break
                raw = data[pos:pos + byte_count - 2]  # skip null
                names.append(raw.decode("utf-16-le", errors="replace"))
                pos += byte_count

            # Skip the uint32 hash after each name
            if pos + 4 <= len(data):
                pos += 4

        log.debug(f"    Parsed {len(names)} names from {filepath.name}")

        # ── Find ImportCount/ImportOffset ──
        # It's typically shortly after the NameCount/NameOffset pair.
        # Search after the name table fields but before the file midpoint.
        for probe in range(20, min(250, len(data) - 8), 4):
            if probe + 8 > len(data):
                break
            ic = struct.unpack_from("<i", data, probe)[0]
            io_ = struct.unpack_from("<i", data, probe + 4)[0]
            if (1 <= ic <= 100000 and
                name_offset < io_ < len(data) and
                io_ != name_offset and
                io_ > pos - 100):  # import table should be after (or near) name table
                # Validate: try reading first import entry
                # Each import entry is: ClassPackage(8) + ClassName(8) + OuterIndex(4) + ObjectName(8) = 28 bytes
                if io_ + 28 <= len(data):
                    test_pkg_idx = struct.unpack_from("<i", data, io_)[0]
                    if 0 <= test_pkg_idx < len(names):
                        import_count = ic
                        import_offset = io_
                        break

        if import_count == 0:
            log.debug(f"    Could not find Import Table in {filepath.name}")
            # Still return names — they contain useful path-like strings
            path_names = [n for n in names if "/" in n and len(n) > 4]
            return names, path_names

        # ── Read the Import Table ──
        pos = import_offset
        import_entries = []  # list of (class_package, class_name, outer_index, object_name)

        for _ in range(import_count):
            if pos + 28 > len(data):
                break
            # FObjectImport layout:
            #   ClassPackage:  FName (int32 index + int32 number)
            #   ClassName:     FName (int32 index + int32 number)
            #   OuterIndex:    int32 (package index, 0 = root)
            #   ObjectName:    FName (int32 index + int32 number)
            cpkg_idx = struct.unpack_from("<i", data, pos)[0]
            pos += 8  # skip FName number field
            cname_idx = struct.unpack_from("<i", data, pos)[0]
            pos += 8
            outer_idx = struct.unpack_from("<i", data, pos)[0]
            pos += 4
            obj_idx = struct.unpack_from("<i", data, pos)[0]
            pos += 8

            def _safe_name(idx):
                if 0 <= idx < len(names):
                    return names[idx]
                return f"?{idx}"

            import_entries.append((
                _safe_name(cpkg_idx),
                _safe_name(cname_idx),
                outer_idx,
                _safe_name(obj_idx),
            ))

        # ── Reconstruct package paths from import entries ──
        # Entries with OuterIndex == 0 are top-level packages (like /Game/Meshes/SM_Wall)
        # Entries with OuterIndex != 0 point to their parent import
        for cpkg, cname, outer, obj_name in import_entries:
            # Top-level packages are the actual asset paths
            if outer == 0 and obj_name.startswith("/"):
                import_paths.append(obj_name)
            elif outer == 0:
                # Sometimes the package name is in ClassPackage
                if cpkg.startswith("/"):
                    import_paths.append(cpkg)

        # Also grab any /Game/ or /Verse/ paths from the name table directly
        for n in names:
            if n.startswith(("/Game/", "/Verse/", "/FortniteGame/")) and n not in import_paths:
                import_paths.append(n)

        log.debug(f"    Parsed {len(import_entries)} imports → {len(import_paths)} paths from {filepath.name}")

    except Exception as e:
        log.warn(f"    UAsset parse error on {filepath.name}: {e}")

    return names, import_paths


def _try_read_fname(data: bytes, offset: int) -> str | None:
    """Try to read a single FName string at offset. Returns None on failure."""
    try:
        if offset + 4 > len(data):
            return None
        str_len = struct.unpack_from("<i", data, offset)[0]
        if str_len <= 0 or str_len > 1024:
            return None
        if offset + 4 + str_len > len(data):
            return None
        raw = data[offset + 4 : offset + 4 + str_len - 1]
        return raw.decode("utf-8", errors="strict")
    except Exception:
        return None


# ─────────────────────────────────────────────
# FALLBACK: Regex byte scan for .uexp / .ubulk
# ─────────────────────────────────────────────

MAX_SCAN_BYTES = 8 * 1024 * 1024  # 8 MB cap

def extract_paths_from_bytes(filepath: Path, project_name: str = "") -> list[str]:
    """Scan raw bytes for asset paths.
    
    UEFN stores references as:
      - /Game/Path/Asset.Asset          (standard UE)
      - /<ProjectName>/Path/Asset.Asset (UEFN entity system!)
      - AssetForEditor<...>="/<ProjectName>/Path/Asset.Asset"
      - Object<...>="/Script/Engine.StaticMesh'/<ProjectName>/Path/Asset'"
    
    The /<ProjectName>/ pattern is the KEY one that previous versions missed.
    """
    refs = set()
    try:
        with open(filepath, "rb") as f:
            raw = f.read(MAX_SCAN_BYTES)

        # ── Standard /Game/, /Verse/, /Script/ paths (UTF-8) ──
        for m in re.finditer(rb'/(?:Game|Verse|FortniteGame|Script)/[A-Za-z0-9_/.\-]+', raw):
            p = m.group(0).decode("utf-8", errors="ignore").split(":")[0]
            # Keep the dotted form (e.g. /Game/Meshes/SM_Door.SM_Door)
            if len(p) > 6:
                refs.add(p)

        # ── /<ProjectName>/ paths — THIS IS THE CRITICAL ONE ──
        if project_name:
            # Build regex for this specific project name
            pn_bytes = project_name.encode("utf-8")
            # Match /<ProjectName>/any/path.possible_name (UTF-8)
            pattern = rb'/' + re.escape(pn_bytes) + rb'/[A-Za-z0-9_/.\-]+'
            for m in re.finditer(pattern, raw):
                p = m.group(0).decode("utf-8", errors="ignore")
                if len(p) > len(project_name) + 3:
                    refs.add(p)

            # UTF-16-LE version of project name paths
            try:
                pn_utf16 = project_name.encode("utf-16-le")
                # /\x00P\x00R\x00O\x00J\x00/\x00...
                pattern16 = rb'/\x00' + re.escape(pn_utf16) + rb'/\x00[A-Za-z0-9_/.\-\x00]+'
                for m in re.finditer(pattern16, raw):
                    try:
                        d = m.group(0).decode("utf-16-le", errors="ignore")
                        if len(d) > len(project_name) + 3:
                            refs.add(d)
                    except:
                        pass
            except:
                pass

        # ── Broad /WORD/ path pattern (catches any project name) ──
        # Matches paths like /SomeProject/Meshes/AssetName.AssetName
        for m in re.finditer(rb'/([A-Z][A-Za-z0-9_]{2,30})/[A-Za-z0-9_/.\-]{4,}', raw):
            p = m.group(0).decode("utf-8", errors="ignore")
            # Only keep if it looks like a project path (has at least 2 segments)
            if p.count("/") >= 3 and len(p) > 10:
                first_seg = p.split("/")[1]
                # Skip known engine prefixes
                if first_seg not in ("Script", "Engine", "Verse", "Game", "FortniteGame",
                                      "EntityFramework", "VerseEngine", "VerseDevices",
                                      "VerseEngineAssets", "CreativeCoreDevices",
                                      "CRD_VolumetricRegion", "EntityInteract"):
                    refs.add(p)

        # ── Quoted paths (from serialized properties) ──
        for m in re.finditer(rb'"(/[A-Za-z0-9_/.\-]+)"', raw):
            p = m.group(1).decode("utf-8", errors="ignore")
            if len(p) > 6:
                refs.add(p)

        # ── UE typed object refs: ClassName'/Path/Asset.Asset' ──
        for m in re.finditer(rb"'(/[A-Za-z0-9_/.\-]+)'", raw):
            p = m.group(1).decode("utf-8", errors="ignore").split(":")[0]
            if len(p) > 6:
                refs.add(p)

    except Exception as e:
        log.warn(f"    Byte scan error on {filepath.name}: {e}")

    return list(refs)


# ─────────────────────────────────────────────
# CLASSIFIER
# ─────────────────────────────────────────────

def classify_asset(name: str, rel_path: str, ext: str) -> str:
    if ext in VERSE_EXT:
        return "Verse"
    if ext == ".umap":
        lp = rel_path.lower()
        if "prefab" in lp:
            return "Prefab"
        return "Map"

    un = name.upper()
    pp = [p.upper() for p in Path(rel_path).parts]

    for cat, name_pats, folder_pats in CATEGORY_RULES:
        for pat in name_pats:
            if un.startswith(pat.upper()) or pat.upper() in un:
                return cat
        for pat in folder_pats:
            if pat.upper() in pp:
                return cat
    return "Other"


# ─────────────────────────────────────────────
# PROJECT SCANNER
# ─────────────────────────────────────────────

class ProjectScanner:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.content_dir: Path | None = None
        self.project_name: str = ""       # e.g. "SPUNCHBOBTHUGS"
        self.all_entries: list[dict] = []
        self.folder_tree: dict[str, int] = {}
        self.category_counts: dict[str, int] = {}
        self._cancel = False

        # Lookup tables built after scan
        self._by_stem: dict[str, list[dict]] = defaultdict(list)
        self._by_game_path: dict[str, dict] = {}

    def cancel(self):
        self._cancel = True

    def _detect_project_name(self) -> str:
        """Detect the UEFN project name.
        
        UEFN binary paths use /<PluginName>/Path (e.g. /SPUNCHBOBTHUGS/Meshes/SM_Door).
        This is the PLUGIN name — typically the Content folder's parent.
        NOT the .uproject name (which may have underscores or be different).
        
        Path example: .../SPUNCHBOBTHUGS_/Plugins/SPUNCHBOBTHUGS/Content
        Binary paths use: /SPUNCHBOBTHUGS/Meshes/...
        So we want "SPUNCHBOBTHUGS" = Content's parent folder.
        """
        # Strategy 1 (BEST): Content folder's parent = the UEFN plugin name
        # This is what UEFN actually uses in binary asset paths
        if self.content_dir:
            parent_name = self.content_dir.parent.name
            if parent_name.lower() not in ("content", "plugins", "source", "config", ""):
                log.info(f"Detected project name from Content parent: {parent_name}")
                return parent_name

        # Strategy 2: Auto-detect by scanning first .uasset/.uexp binaries
        if self.content_dir:
            detected = self._detect_name_from_binary()
            if detected:
                log.info(f"Auto-detected project name from binary scan: {detected}")
                return detected

        # Strategy 3: Walk up looking for .uproject file
        search_dirs = [self.project_root]
        if self.content_dir:
            p = self.content_dir.parent
            for _ in range(5):
                if p and p != p.parent:
                    search_dirs.append(p)
                    p = p.parent
        for d in search_dirs:
            try:
                for f in d.iterdir():
                    if f.suffix.lower() == ".uproject":
                        name = f.stem
                        log.info(f"Detected project name from .uproject: {name}")
                        return name
            except:
                pass

        # Strategy 4: Folder name fallback
        name = self.project_root.name
        if name.lower() == "content" and self.project_root.parent:
            name = self.project_root.parent.name
        log.info(f"Fallback project name: {name}")
        return name

    def _detect_name_from_binary(self) -> str:
        """Scan a few .uasset/.uexp files to find the project name in binary paths."""
        from collections import Counter
        candidates = Counter()
        
        sample_files = []
        for ext in (".uasset", ".uexp"):
            for f in self.content_dir.rglob(f"*{ext}"):
                sample_files.append(f)
                if len(sample_files) >= 6:
                    break
            if len(sample_files) >= 6:
                break
        
        for fp in sample_files[:6]:
            try:
                with open(fp, "rb") as f:
                    data = f.read(2 * 1024 * 1024)
                # Look for /WORD/ patterns where WORD starts with uppercase
                for m in re.finditer(rb'/([A-Z][A-Za-z0-9_]{2,40})/[A-Za-z0-9_/]', data):
                    name = m.group(1).decode("utf-8", errors="ignore")
                    # Skip known engine prefixes
                    if name not in ("Game", "Script", "Engine", "Verse", "FortniteGame",
                                     "EntityFramework", "VerseEngine", "VerseDevices",
                                     "VerseEngineAssets", "CreativeCoreDevices",
                                     "CRD_VolumetricRegion", "EntityInteract",
                                     "Content", "Plugins", "Source", "Config",
                                     "CoreUObject", "MetasoundEngine"):
                        candidates[name] += 1
            except:
                pass
        
        if candidates:
            best = candidates.most_common(1)[0]
            if best[1] >= 2:  # seen at least twice
                return best[0]
        return ""

    def scan(self, progress_cb=None):
        self.all_entries.clear()
        self.folder_tree.clear()
        self.category_counts.clear()
        self._by_stem.clear()
        self._by_game_path.clear()
        self._cancel = False

        self.content_dir = self._find_content()
        if not self.content_dir:
            log.warn("No Content directory found!")
            return

        self.project_name = self._detect_project_name()
        log.info(f"Scanning: {self.content_dir}")
        log.info(f"Project name for path matching: {self.project_name}")

        files = [f for f in self.content_dir.rglob("*")
                 if f.is_file() and f.suffix.lower() in ALL_SCANNABLE]
        total = len(files)
        log.info(f"Found {total} primary asset files.")

        for idx, fp in enumerate(files):
            if self._cancel:
                return
            if idx % CPU_YIELD_EVERY == 0:
                time.sleep(CPU_YIELD_SEC)

            ext = fp.suffix.lower()
            rel = fp.relative_to(self.project_root)
            rf = str(rel.parent)
            cat = classify_asset(fp.stem, str(rel), ext)

            entry = {
                "name": fp.name,
                "stem": fp.stem,
                "ext": ext,
                "rel_path": str(rel),
                "rel_folder": rf,
                "abs_path": str(fp),
                "size": fp.stat().st_size,
                "category": cat,
            }
            self.all_entries.append(entry)
            self.folder_tree[rf] = self.folder_tree.get(rf, 0) + 1
            self.category_counts[cat] = self.category_counts.get(cat, 0) + 1

            # Build lookup tables
            self._by_stem[fp.stem.upper()].append(entry)

            try:
                game_rel = fp.relative_to(self.content_dir)
                rel_str = str(game_rel).replace("\\", "/")
                rel_no_ext = rel_str.rsplit(".", 1)[0]

                # Register under /Game/ (standard UE)
                self._by_game_path["/Game/" + rel_no_ext] = entry

                # Register under /<ProjectName>/ (UEFN uses this!)
                if self.project_name:
                    self._by_game_path[f"/{self.project_name}/{rel_no_ext}"] = entry
            except:
                pass

            if progress_cb and idx % 80 == 0:
                progress_cb(idx + 1, total)

        if progress_cb:
            progress_cb(total, total)

        parts = " | ".join(f"{c}: {n}" for c, n in sorted(self.category_counts.items()))
        log.info(f"Scan complete: {len(self.all_entries)} assets — {parts}")
        log.info(f"Path lookup table: {len(self._by_game_path)} entries "
                 f"(both /Game/ and /{self.project_name}/ keys)")

    def lookup_by_game_path(self, game_path: str) -> dict | None:
        """Look up an asset by /Game/... or /<ProjectName>/... path.
        Handles dotted format like /Proj/Meshes/SM_Door.SM_Door"""
        # Strip trailing quotes/colons
        clean = game_path.rstrip("'\"").split(":")[0]
        
        # Try as-is first
        result = self._by_game_path.get(clean)
        if result:
            return result
        
        # Try stripping the .AssetName suffix (UE dotted notation)
        # /PROJ/Meshes/SM_Door.SM_Door → /PROJ/Meshes/SM_Door
        last_seg = clean.rsplit("/", 1)[-1] if "/" in clean else clean
        if "." in last_seg:
            stripped = clean.rsplit(".", 1)[0]
            result = self._by_game_path.get(stripped)
            if result:
                return result
        
        return None

    def lookup_by_stem(self, stem: str) -> list[dict]:
        """Look up assets by filename stem (case-insensitive)."""
        return self._by_stem.get(stem.upper(), [])

    def _find_content(self):
        # If project_root IS a Content folder, use it directly
        if self.project_root.name.lower() == "content":
            return self.project_root
        # Check for Content/ subfolder
        for n in ["Content", "content"]:
            p = self.project_root / n
            if p.is_dir():
                return p
        # Check grandchildren (project/PluginName/Content)
        try:
            for c in self.project_root.iterdir():
                if c.is_dir() and (c / "Content").is_dir():
                    return c / "Content"
        except:
            pass
        # Check Plugins/X/Content
        plugins = self.project_root / "Plugins"
        if plugins.is_dir():
            try:
                for p in plugins.iterdir():
                    if p.is_dir() and (p / "Content").is_dir():
                        return p / "Content"
            except:
                pass
        return self.project_root


# ─────────────────────────────────────────────
# DEPENDENCY RESOLVER  (v5 — header-based)
# ─────────────────────────────────────────────

class DependencyResolver:

    def __init__(self, scanner: ProjectScanner):
        self.scanner = scanner

    def resolve(self, entry: dict, max_depth: int = 8) -> list[dict]:
        """Resolve all dependencies of an asset, recursively."""
        log.info(f"{'═'*50}")
        log.info(f"RESOLVING: [{entry['category']}] {entry['name']}")
        log.info(f"  Path: {entry['rel_path']}")

        all_deps: list[dict] = []
        seen: set[str] = {entry["abs_path"]}
        queue = [entry]

        for depth in range(max_depth):
            if not queue:
                break
            log.info(f"  ── Depth {depth} — processing {len(queue)} assets ──")
            next_queue = []

            for cur in queue:
                time.sleep(CPU_YIELD_SEC)
                deps = self._find_direct_deps(cur, seen)
                for d in deps:
                    seen.add(d["abs_path"])
                    all_deps.append(d)
                    next_queue.append(d)

            queue = next_queue

        log.info(f"  TOTAL DEPS: {len(all_deps)}")
        for d in all_deps:
            log.info(f"    [{d['category']:>10}] {d['name']}")
        log.info(f"{'═'*50}")

        return all_deps

    def _find_direct_deps(self, entry: dict, seen: set[str]) -> list[dict]:
        deps: list[dict] = []
        found_paths: set[str] = set()

        def _add(d):
            if d["abs_path"] not in seen and d["abs_path"] not in found_paths:
                found_paths.add(d["abs_path"])
                deps.append(d)
                log.debug(f"    + [{d['category']}] {d['name']}")

        # ═══ METHOD 1: Parse UAsset Import Table ═══
        filepath = Path(entry["abs_path"])
        if filepath.suffix.lower() in (".uasset", ".umap"):
            names, import_paths = parse_uasset_names_and_imports(filepath)

            log.info(f"  [{entry['name']}] Import Table → {len(import_paths)} paths")

            for ref_path in import_paths:
                # Try direct /Game/ path lookup
                match = self.scanner.lookup_by_game_path(ref_path)
                if match:
                    _add(match)
                    continue

                # Try extracting the last segment as a stem
                segments = ref_path.replace("\\", "/").split("/")
                if segments:
                    stem = segments[-1].split(".")[0]
                    for m in self.scanner.lookup_by_stem(stem):
                        _add(m)

            # Also search the Name Table for asset paths
            pn = self.scanner.project_name
            for n in names:
                if n.startswith(("/Game/", "/Verse/")) or (pn and n.startswith(f"/{pn}/")):
                    match = self.scanner.lookup_by_game_path(n)
                    if match:
                        _add(match)

        # ═══ METHOD 2: Regex scan .uexp (component property data) ═══
        # This is WHERE UEFN stores mesh/material/sound refs as /<ProjectName>/path
        uexp = filepath.with_suffix(".uexp")
        pn = self.scanner.project_name
        if uexp.exists():
            uexp_refs = extract_paths_from_bytes(uexp, project_name=pn)
            log.info(f"  [{entry['name']}] .uexp scan → {len(uexp_refs)} paths")
            for ref in uexp_refs:
                # Try direct lookup (handles both /Game/ and /<ProjectName>/ keys)
                match = self.scanner.lookup_by_game_path(ref)
                if match:
                    _add(match)
                    continue
                # Try stripping the dotted suffix: /Proj/Meshes/SM_Door.SM_Door → /Proj/Meshes/SM_Door
                clean = ref.split(".")[0] if "." in ref.split("/")[-1] else ref
                match = self.scanner.lookup_by_game_path(clean)
                if match:
                    _add(match)
                    continue
                # Stem fallback
                segs = ref.replace("\\", "/").split("/")
                if segs:
                    stem = segs[-1].split(".")[0]
                    for m in self.scanner.lookup_by_stem(stem):
                        _add(m)

        # ═══ METHOD 3: Regex scan .uasset raw bytes ═══
        if filepath.suffix.lower() in (".uasset", ".umap"):
            raw_refs = extract_paths_from_bytes(filepath, project_name=pn)
            log.info(f"  [{entry['name']}] Raw byte scan → {len(raw_refs)} paths")
            for ref in raw_refs:
                match = self.scanner.lookup_by_game_path(ref)
                if match:
                    _add(match)
                    continue
                clean = ref.split(".")[0] if "." in ref.split("/")[-1] else ref
                match = self.scanner.lookup_by_game_path(clean)
                if match:
                    _add(match)

        # ═══ METHOD 4: Name-prefix matching (PFB_Chair → SM_Chair) ═══
        stem = entry["stem"]
        base = None
        src_pfx = None
        for pfx in RELATED_PREFIXES:
            if stem.upper().startswith(pfx.upper()):
                src_pfx = pfx
                base = stem[len(pfx):]
                break

        if base and src_pfx:
            targets = RELATED_PREFIXES[src_pfx]
            bu = base.upper()
            prefix_found = 0
            for o in self.scanner.all_entries:
                if o["abs_path"] in seen or o["abs_path"] in found_paths:
                    continue
                os_upper = o["stem"].upper()
                for tp in targets:
                    tu = tp.upper()
                    if os_upper == tu + bu or os_upper.startswith(tu + bu):
                        _add(o)
                        prefix_found += 1
                        break
            log.info(f"  [{entry['name']}] Name-prefix → {prefix_found} matches")

        # ═══ METHOD 5: Verse association ═══
        if entry["category"] in ("Prefab", "Blueprint", "Map", "Mesh"):
            stem_clean = re.sub(
                r'^(PFB_|PF_|PRF_|BP_|SM_|SK_|SKM_|GEO_)',
                '', entry["stem"], flags=re.IGNORECASE
            ).upper().replace("_", "")
            entry_folder = str(Path(entry["abs_path"]).parent).upper()

            for o in self.scanner.all_entries:
                if o["category"] != "Verse":
                    continue
                if o["abs_path"] in seen or o["abs_path"] in found_paths:
                    continue

                verse_clean = re.sub(
                    r'(_device|_script|device_|script_|verse_|_verse)',
                    '', o["stem"], flags=re.IGNORECASE
                ).upper().replace("_", "")

                if (stem_clean and verse_clean and len(stem_clean) >= 3 and len(verse_clean) >= 3):
                    if stem_clean in verse_clean or verse_clean in stem_clean:
                        _add(o)
                        log.debug(f"    Verse match: {o['name']} <-> {entry['name']}")
                        continue

                # Folder proximity + partial overlap
                o_folder = str(Path(o["abs_path"]).parent).upper()
                if o_folder == entry_folder:
                    try:
                        if Path(o["abs_path"]).stat().st_size < 256_000:
                            with open(o["abs_path"], "r", errors="ignore") as f:
                                if entry["stem"].lower() in f.read().lower():
                                    _add(o)
                                    log.debug(f"    Verse content match: {o['name']}")
                    except:
                        pass

        return deps


# ─────────────────────────────────────────────
# EXPORTER
# ─────────────────────────────────────────────

class AssetExporter:
    def __init__(self, scanner: ProjectScanner, export_root: str):
        self.scanner = scanner
        self.export_root = Path(export_root)
        self.export_log: list[str] = []
        self.copied = 0
        self.errors = 0

    def export(self, selected: list[dict], resolve: bool = True, progress_cb=None) -> dict:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # All organized subfolders go INSIDE one export folder
        export_folder = self.export_root / f"UEFN_Export_{ts}"
        export_folder.mkdir(parents=True, exist_ok=True)

        queue: list[tuple[dict, str]] = []  # (entry, category)
        seen: set[str] = set()

        resolver = DependencyResolver(self.scanner) if resolve else None

        for e in selected:
            if e["abs_path"] in seen:
                continue
            seen.add(e["abs_path"])
            queue.append((e, e["category"]))
            self._add_companions(e, queue, seen)

            if resolve and resolver:
                deps = resolver.resolve(e)
                if deps:
                    self.export_log.append(f"  ── Deps for {e['name']} ({e['category']}): {len(deps)} found")
                else:
                    self.export_log.append(f"  ── Deps for {e['name']} ({e['category']}): NONE FOUND")
                for d in deps:
                    if d["abs_path"] not in seen:
                        seen.add(d["abs_path"])
                        queue.append((d, d["category"]))
                        self._add_companions(d, queue, seen)
                        self.export_log.append(f"     ↳ [{d['category']:>10}] {d['rel_path']}")

        total = len(queue)
        log.info(f"Exporting {total} files to {export_folder}")

        for i, (e, cat) in enumerate(queue):
            # Organize into subfolders INSIDE the export folder
            subfolder = ORGANIZE_FOLDERS.get(cat, "Other")
            target_dir = export_folder / subfolder
            target_dir.mkdir(parents=True, exist_ok=True)

            src = Path(e["abs_path"])
            dst = target_dir / src.name
            if dst.exists():
                dst = target_dir / f"{src.stem}_{hashlib.md5(str(src).encode()).hexdigest()[:6]}{src.suffix}"

            try:
                shutil.copy2(str(src), str(dst))
                self.copied += 1
                self.export_log.append(f"  ✓  {e.get('rel_path', e['name'])} → {subfolder}/")
            except Exception as ex:
                self.errors += 1
                self.export_log.append(f"  ✗  {e['name']} → {ex}")

            if progress_cb and i % 20 == 0:
                progress_cb(i + 1, total)
            if i % CPU_YIELD_EVERY == 0:
                time.sleep(CPU_YIELD_SEC)

        if progress_cb:
            progress_cb(total, total)

        # Write manifest
        manifest = {
            "tool_version": "5.1",
            "exported_at": ts,
            "source_project": str(self.scanner.project_root),
            "total_files": self.copied,
            "errors": self.errors,
            "categories": {},
            "files": [],
        }
        for e, cat in queue:
            manifest["files"].append({
                "name": e["name"], "category": cat,
                "original_path": e.get("rel_path", ""),
            })
            manifest["categories"][cat] = manifest["categories"].get(cat, 0) + 1
        (export_folder / EXPORT_MANIFEST).write_text(json.dumps(manifest, indent=2))

        return {
            "export_folder": str(export_folder),
            "copied": self.copied,
            "errors": self.errors,
            "log": self.export_log,
        }

    def _add_companions(self, e: dict, queue: list, seen: set):
        for ext in [".uexp", ".ubulk"]:
            c = Path(e["abs_path"]).with_suffix(ext)
            if c.exists() and str(c) not in seen:
                seen.add(str(c))
                queue.append(({
                    "name": c.name, "stem": c.stem, "ext": ext,
                    "abs_path": str(c),
                    "rel_path": str(c.relative_to(self.scanner.project_root)),
                    "category": e["category"],
                }, e["category"]))


# ─────────────────────────────────────────────
# IMPORTER
# ─────────────────────────────────────────────

class AssetImporter:
    IMAP = {k: f"Content/ImportedAssets/{v}" for k, v in ORGANIZE_FOLDERS.items()}

    def __init__(self, src, tgt):
        self.src = Path(src); self.tgt = Path(tgt)
        self.log_lines: list[str] = []; self.copied = 0; self.errors = 0

    def run(self, progress_cb=None):
        af = [
            (f, s.name)
            for s in self.src.iterdir()
            if s.is_dir() and s.name != "__pycache__"
            for f in s.rglob("*")
            if f.is_file() and f.name != EXPORT_MANIFEST
        ]
        total = len(af)
        if not total:
            return {"error": "No files in bundle."}
        for i, (src, cat) in enumerate(af):
            td = self.tgt / self.IMAP.get(cat, f"Content/ImportedAssets/{cat}")
            td.mkdir(parents=True, exist_ok=True)
            dst = td / src.name
            if dst.exists():
                dst = td / f"{src.stem}_imported{src.suffix}"
            try:
                shutil.copy2(str(src), str(dst))
                self.copied += 1
                self.log_lines.append(f"  ✓  {src.name} → {cat}/")
            except Exception as ex:
                self.errors += 1
                self.log_lines.append(f"  ✗  {src.name} → {ex}")
            if progress_cb:
                progress_cb(i + 1, total)
        return {"copied": self.copied, "errors": self.errors, "log": self.log_lines}


# ─────────────────────────────────────────────
# ORGANIZER
# ─────────────────────────────────────────────

class ProjectOrganizer:
    def __init__(self, scanner, mode="copy"):
        self.scanner = scanner; self.mode = mode
        self.log_lines: list[str] = []; self.moved = 0; self.errors = 0; self.skipped = 0

    def organize(self, progress_cb=None):
        cd = self.scanner.content_dir
        if not cd:
            return {"error": "No Content directory."}
        total = len(self.scanner.all_entries)
        for idx, entry in enumerate(self.scanner.all_entries):
            cat = entry["category"]
            tn = ORGANIZE_FOLDERS.get(cat, "Other")
            src = Path(entry["abs_path"])
            if src.parent.name == tn:
                self.skipped += 1; continue
            td = cd / tn; td.mkdir(parents=True, exist_ok=True)
            dst = td / src.name
            if dst.exists():
                dst = td / f"{src.stem}_{hashlib.md5(str(src).encode()).hexdigest()[:6]}{src.suffix}"
            try:
                comps = [src.with_suffix(ext) for ext in [".uexp",".ubulk"] if src.with_suffix(ext).exists()]
                if self.mode == "move":
                    shutil.move(str(src), str(dst))
                    for c in comps: shutil.move(str(c), str(td / c.name))
                else:
                    shutil.copy2(str(src), str(dst))
                    for c in comps: shutil.copy2(str(c), str(td / c.name))
                self.moved += 1
                self.log_lines.append(f"  ✓  {entry['rel_path']} → {tn}/")
            except Exception as e:
                self.errors += 1
                self.log_lines.append(f"  ✗  {entry['name']} → {e}")
            if progress_cb and idx % 20 == 0:
                progress_cb(idx + 1, total)
        if progress_cb:
            progress_cb(total, total)
        return {"moved": self.moved, "skipped": self.skipped, "errors": self.errors, "log": self.log_lines}


# ─────────────────────────────────────────────
# PROJECT FINDER
# ─────────────────────────────────────────────

class UEFNProjectFinder:
    KNOWN_ROOTS = []
    @classmethod
    def _build(cls):
        if cls.KNOWN_ROOTS: return
        h = Path.home(); la = os.environ.get("LOCALAPPDATA",""); ad = os.environ.get("APPDATA","")
        if platform.system()=="Windows":
            cls.KNOWN_ROOTS = [
                os.path.join(la,"UnrealEditorFortnite","Saved","Projects"),
                os.path.join(la,"EpicGames","UnrealEditorFortnite","Saved","Projects"),
                os.path.join(la,"FortniteGame","Saved","Projects"),
                os.path.join(ad,"UnrealEditorFortnite","Saved","Projects"),
                str(h/"Documents"/"UEFN Projects"), str(h/"Documents"/"Fortnite Projects"),
                str(h/"Documents"/"Unreal Projects"), str(h/"Desktop"),
                "D:\\UEFN Projects","E:\\UEFN Projects"]
        else:
            cls.KNOWN_ROOTS = [str(h/"Documents"/"UEFN Projects"), str(h/"Documents"/"Unreal Projects")]

    @classmethod
    def find_all_projects(cls):
        cls._build(); projects=[]; seen=set()
        for root in cls.KNOWN_ROOTS:
            rp=Path(root)
            if not rp.is_dir(): continue
            try:
                for up in rp.rglob("*.uproject"):
                    pd=up.parent; k=str(pd).lower()
                    if k not in seen: seen.add(k); projects.append(cls._entry(pd,up.stem))
                for child in rp.iterdir():
                    if child.is_dir() and (child/"Content").is_dir():
                        k=str(child).lower()
                        if k not in seen: seen.add(k); projects.append(cls._entry(child))
            except: pass
        projects.sort(key=lambda p:p["last_modified"],reverse=True)
        return projects

    @classmethod
    def _entry(cls,d,name=None):
        hv=False
        try: hv=any((d/"Content").rglob("*.verse")) if (d/"Content").is_dir() else False
        except: pass
        try: mt=datetime.fromtimestamp(d.stat().st_mtime)
        except: mt=datetime.min
        return {"name":name or d.name,"path":str(d),"last_modified":mt,"has_verse":hv}


# ─────────────────────────────────────────────
# CLIPBOARD / PASTE PARSER
# ─────────────────────────────────────────────
# Parses the UEFN copy-paste text format (Begin Map / Begin Object)
# to extract every asset reference. This is 100% reliable because
# it's the same data UEFN uses internally.
#
# Key patterns it extracts:
#   AssetForEditor<...>="/PROJECT/Meshes/SM_Door.SM_Door"
#   Object<...>="/Script/Engine.StaticMesh'/PROJECT/Meshes/SM_Door.SM_Door'"
#   Class=/PROJECT/_Verse.some_component
#   Class=/PROJECT/Prefabs/PF_Name.PF_Name_C
# ─────────────────────────────────────────────

def parse_clipboard_refs(text: str, project_name: str = "") -> list[str]:
    """Parse UEFN copy-paste text and return unique asset paths (project-relative).
    
    Returns paths like: Meshes/SM_JailDoor, Materials/rust, SFX/Effects/Cue_CellDoor
    These are relative to the Content folder.
    """
    refs: set[str] = set()
    
    if not text.strip():
        return []
    
    # ── Pattern 1: AssetForEditor<...>="/PROJECT/Path/Asset.Asset" ──
    # This is the most reliable — it's the actual asset reference
    for m in re.finditer(r'AssetForEditor[^=]*=\s*"([^"]+)"', text):
        path = m.group(1).strip()
        refs.add(path)
    
    # ── Pattern 2: Object<...>="/Script/Engine.Type'/PROJECT/Path/Asset'" ──
    for m in re.finditer(r"Object[^=]*=\s*\"[^']*'([^']+)'\"", text):
        path = m.group(1).strip()
        refs.add(path)
    
    # ── Pattern 3: Typed refs — /Script/Engine.StaticMesh'/PROJECT/path' ──
    for m in re.finditer(r"(?:StaticMesh|MaterialInterface|MaterialInstanceConstant|SoundWave|"
                          r"SoundCue|MetaSoundSource|NiagaraSystem|Texture2D|SkeletalMesh)"
                          r"'(/[^']+)'", text):
        path = m.group(1).strip()
        refs.add(path)
    
    # ── Pattern 4: Class=/PROJECT/_Verse.component_name (Verse components) ──
    if project_name:
        for m in re.finditer(rf'Class=/{re.escape(project_name)}/_Verse\.(\S+)', text):
            comp = m.group(1).split("'")[0].split('"')[0]
            refs.add(f"/{project_name}/_Verse.{comp}")
    # Generic version
    for m in re.finditer(r'Class=/([A-Z][A-Za-z0-9_]+)/_Verse\.(\S+)', text):
        proj = m.group(1)
        comp = m.group(2).split("'")[0].split('"')[0]
        refs.add(f"/{proj}/_Verse.{comp}")
    
    # ── Convert to Content-relative paths ──
    content_paths: set[str] = set()
    for ref in refs:
        # Strip project prefix: /SPUNCHBOBTHUGS/Meshes/X.X → Meshes/X
        # Also handle /Script/Engine.Type'/PROJECT/path' format
        path = ref
        
        # Remove leading /ProjectName/
        if project_name and path.startswith(f"/{project_name}/"):
            path = path[len(project_name) + 2:]
        elif path.startswith("/"):
            # Try stripping first segment: /ANYPROJECT/rest → rest
            parts = path.split("/", 2)
            if len(parts) >= 3:
                first_seg = parts[1]
                if first_seg not in ("Script", "Engine", "Verse", "Game",
                                      "EntityFramework", "VerseEngine", "VerseDevices",
                                      "VerseEngineAssets", "CreativeCoreDevices",
                                      "CRD_VolumetricRegion", "EntityInteract"):
                    path = parts[2]
        
        # Strip .AssetName suffix: Meshes/SM_Door.SM_Door → Meshes/SM_Door
        last_part = path.rsplit("/", 1)[-1] if "/" in path else path
        if "." in last_part:
            path = path.rsplit(".", 1)[0]
        
        if path and "/" in path:
            content_paths.add(path)
    
    log.info(f"Clipboard parser found {len(refs)} raw refs → {len(content_paths)} content paths:")
    for p in sorted(content_paths):
        log.info(f"  📋 {p}")
    
    return sorted(content_paths)


# ═════════════════════════════════════════════
#  GUI
# ═════════════════════════════════════════════

class App:
    def __init__(self):
        self.root = Tk()
        self.root.title("UEFN Asset Tool v5.3")
        self.root.geometry("1200x900")
        self.root.minsize(1000, 650)
        self.root.configure(bg=BG_DARK)

        self.source_path = StringVar()
        self.export_path = StringVar()
        self.paste_source_path = StringVar()
        self.paste_export_path = StringVar()
        self.import_source = StringVar()
        self.import_target = StringVar()
        self.org_path = StringVar()
        self.search_var = StringVar()
        self.folder_filter = StringVar(value="ALL")
        self.resolve_deps = BooleanVar(value=True)
        self.org_mode = StringVar(value="copy")

        self.scanner: ProjectScanner | None = None
        self.org_scanner: ProjectScanner | None = None
        self.display_list: list[dict] = []
        self.active_cats: set[str] = set()
        self.cat_buttons: dict = {}
        self.projects: list[dict] = []
        self._search_id = None
        self._busy = False
        self._in_uefn = False
        self._pending = None

        self._styles()
        self._build()
        self._detect_projects()
        self.search_var.trace_add("write", self._on_search)

    # ── Styles ──────────────────────────────
    def _styles(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("Dark.TFrame", background=BG_DARK)
        s.configure("Title.TLabel", background=BG_DARK, foreground=ACCENT, font=("Segoe UI",16,"bold"))
        s.configure("Header.TLabel", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI",11,"bold"))
        s.configure("Body.TLabel", background=BG_DARK, foreground=TEXT_SECONDARY, font=("Segoe UI",10))
        s.configure("Dim.TLabel", background=BG_DARK, foreground=TEXT_DIM, font=("Segoe UI",9))
        s.configure("Status.TLabel", background=BG_MID, foreground=SUCCESS, font=("Consolas",9))
        s.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI",10,"bold"), padding=(14,6))
        s.map("Accent.TButton", background=[("active",ACCENT_HOVER)])
        s.configure("Sec.TButton", background=BG_LIGHT, foreground=TEXT_PRIMARY, font=("Segoe UI",10), padding=(10,5))
        s.map("Sec.TButton", background=[("active",BG_MID)])
        s.configure("Sm.TButton", background=BG_LIGHT, foreground=TEXT_PRIMARY, font=("Segoe UI",9), padding=(6,3))
        s.map("Sm.TButton", background=[("active",BG_MID)])
        s.configure("FOn.TButton", background=ACCENT, foreground="white", font=("Segoe UI",9,"bold"), padding=(8,3))
        s.configure("FOff.TButton", background=BG_MID, foreground=TEXT_SECONDARY, font=("Segoe UI",9), padding=(8,3))
        s.map("FOff.TButton", background=[("active",BG_LIGHT)])
        s.configure("Dark.TCheckbutton", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI",10))
        s.configure("Dark.TRadiobutton", background=BG_DARK, foreground=TEXT_PRIMARY, font=("Segoe UI",10))
        s.configure("green.Horizontal.TProgressbar", troughcolor=BG_MID, background=SUCCESS)
        s.configure("warn.Horizontal.TProgressbar", troughcolor=BG_MID, background=WARNING)

    # ── Build ──────────────────────────────
    def _build(self):
        nb = ttk.Notebook(self.root); nb.pack(fill=BOTH, expand=True, padx=8, pady=8)
        t1 = Frame(nb, bg=BG_DARK); nb.add(t1, text="  ⬆  Export  "); self._build_export(t1)
        tp = Frame(nb, bg=BG_DARK); nb.add(tp, text="  📋  Paste Export  "); self._build_paste(tp)
        t2 = Frame(nb, bg=BG_DARK); nb.add(t2, text="  ⬇  Import  "); self._build_import(t2)
        t3 = Frame(nb, bg=BG_DARK); nb.add(t3, text="  🗂️  Organize  "); self._build_organizer(t3)
        t4 = Frame(nb, bg=BG_DARK); nb.add(t4, text="  📋  Log  "); self._build_log(t4)

    def _picker(self, parent, label, svar, browse_cmd, attr):
        ttk.Label(parent, text=label, style="Header.TLabel").pack(anchor=W, pady=(8,0))
        r = Frame(parent, bg=BG_DARK); r.pack(fill=X, pady=2)
        cb = ttk.Combobox(r, state="readonly", width=55, font=("Segoe UI",10))
        cb.pack(side=LEFT, fill=X, expand=True, padx=(0,4))
        cb.set("  ← Pick a project or Browse")
        def sel(e):
            i = cb.current()
            if 0 <= i < len(self.projects):
                svar.set(self.projects[i]["path"])
        cb.bind("<<ComboboxSelected>>", sel)
        setattr(self, attr, cb)
        ttk.Button(r, text="🔄", style="Sm.TButton", command=self._detect_projects).pack(side=LEFT, padx=2)
        ttk.Button(r, text="📁 Browse…", style="Sec.TButton", command=browse_cmd).pack(side=LEFT, padx=2)
        r2 = Frame(parent, bg=BG_DARK); r2.pack(fill=X, pady=(1,0))
        Entry(r2, textvariable=svar, font=("Consolas",9), bg=BG_INPUT, fg=TEXT_DIM,
              insertbackground=TEXT_PRIMARY, relief="flat", bd=5).pack(fill=X)

    def _build_export(self, p):
        top = Frame(p, bg=BG_DARK); top.pack(fill=X, padx=16, pady=(8,0))
        ttk.Label(top, text="UEFN Asset Exporter v5.3", style="Title.TLabel").pack(anchor=W)
        ttk.Label(top, text="Scans /<ProjectName>/ paths from .uexp — full dep chain",
                  style="Dim.TLabel").pack(anchor=W, pady=(0,4))

        self._picker(top, "Source Project:", self.source_path, self._br_src, "_src_cb")

        ttk.Label(top, text="Export To:", style="Header.TLabel").pack(anchor=W, pady=(8,0))
        dr = Frame(top, bg=BG_DARK); dr.pack(fill=X, pady=2)
        Entry(dr, textvariable=self.export_path, font=("Consolas",10), bg=BG_INPUT, fg=TEXT_PRIMARY,
              insertbackground=TEXT_PRIMARY, relief="flat", bd=6).pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        ttk.Button(dr, text="📁 Browse…", style="Sec.TButton", command=self._br_exp).pack(side=RIGHT)

        sr = Frame(p, bg=BG_DARK); sr.pack(fill=X, padx=16, pady=6)
        ttk.Button(sr, text="🔍  Scan Project", style="Accent.TButton", command=self._scan).pack(side=LEFT)
        ttk.Checkbutton(sr, text="Auto-resolve deps", variable=self.resolve_deps,
                        style="Dark.TCheckbutton").pack(side=LEFT, padx=(16,0))

        sf = Frame(p, bg=BG_DARK); sf.pack(fill=X, padx=16, pady=(4,2))
        ttk.Label(sf, text="🔎", style="Header.TLabel").pack(side=LEFT, padx=(0,4))
        self.search_e = Entry(sf, textvariable=self.search_var, font=("Segoe UI",11), bg=BG_INPUT,
                              fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY, relief="flat", bd=6)
        self.search_e.pack(side=LEFT, fill=X, expand=True)
        self._ph(self.search_e, "Search…")

        self.cat_frame = Frame(p, bg=BG_DARK); self.cat_frame.pack(fill=X, padx=16, pady=(2,2))
        ttk.Label(self.cat_frame, text="Filter:", style="Body.TLabel").pack(side=LEFT, padx=(0,6))

        fr = Frame(p, bg=BG_DARK); fr.pack(fill=X, padx=16, pady=(0,3))
        ttk.Label(fr, text="Folder:", style="Body.TLabel").pack(side=LEFT, padx=(0,6))
        self.folder_cb = ttk.Combobox(fr, textvariable=self.folder_filter, state="readonly",
                                       width=65, font=("Consolas",9))
        self.folder_cb.pack(side=LEFT, fill=X, expand=True)
        self.folder_cb.bind("<<ComboboxSelected>>", lambda e: self._filter())

        lf = Frame(p, bg=BG_DARK); lf.pack(fill=BOTH, expand=True, padx=16, pady=(0,3))
        self.count_lbl = ttk.Label(lf, text="0 assets", style="Dim.TLabel")
        self.count_lbl.pack(anchor=W)
        sc = Scrollbar(lf, orient=VERTICAL); sc.pack(side=RIGHT, fill=Y)
        self.asset_lb = Listbox(lf, selectmode=EXTENDED, bg=BG_MID, fg=TEXT_PRIMARY,
                                selectbackground=ACCENT, selectforeground="white",
                                font=("Consolas",10), relief="flat", bd=4,
                                yscrollcommand=sc.set, activestyle="none")
        self.asset_lb.pack(fill=BOTH, expand=True); sc.config(command=self.asset_lb.yview)

        bt = Frame(p, bg=BG_DARK); bt.pack(fill=X, padx=16, pady=(0,3))
        ttk.Button(bt, text="Select All", style="Sec.TButton",
                   command=lambda: self.asset_lb.select_set(0, END)).pack(side=LEFT, padx=2)
        ttk.Button(bt, text="Deselect", style="Sec.TButton",
                   command=lambda: self.asset_lb.select_clear(0, END)).pack(side=LEFT, padx=2)
        self.exp_btn = ttk.Button(bt, text="⬆  EXPORT SELECTED", style="Accent.TButton",
                                   command=self._export)
        self.exp_btn.pack(side=RIGHT, padx=2)

        sb = Frame(p, bg=BG_MID); sb.pack(fill=X, padx=16, pady=(2,8))
        self.exp_prog = ttk.Progressbar(sb, style="green.Horizontal.TProgressbar", length=400)
        self.exp_prog.pack(fill=X, padx=8, pady=4)
        self.exp_stat = ttk.Label(sb, text="Ready.", style="Status.TLabel")
        self.exp_stat.pack(padx=8, pady=(0,4))

    def _build_paste(self, p):
        top = Frame(p, bg=BG_DARK); top.pack(fill=X, padx=16, pady=(8,0))
        ttk.Label(top, text="Paste Prefab Export", style="Title.TLabel").pack(anchor=W)
        ttk.Label(top, text="Copy a prefab in UEFN (Ctrl+C), paste the text here → exports all referenced assets",
                  style="Dim.TLabel").pack(anchor=W, pady=(0,4))

        # Source project (needed to locate files on disk)
        self._picker(top, "Source Project (same as Export tab):", self.paste_source_path,
                     lambda: self._br_generic(self.paste_source_path, "Source Project"), "_paste_src_cb")

        ttk.Label(top, text="Export To:", style="Header.TLabel").pack(anchor=W, pady=(8,0))
        dr = Frame(top, bg=BG_DARK); dr.pack(fill=X, pady=2)
        Entry(dr, textvariable=self.paste_export_path, font=("Consolas",10), bg=BG_INPUT, fg=TEXT_PRIMARY,
              insertbackground=TEXT_PRIMARY, relief="flat", bd=6).pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        ttk.Button(dr, text="📁 Browse…", style="Sec.TButton",
                   command=lambda: self._br_generic(self.paste_export_path, "Export Destination")).pack(side=RIGHT)

        ttk.Label(top, text="Paste prefab data below (Ctrl+C on prefab in UEFN, then Ctrl+V here):",
                  style="Header.TLabel").pack(anchor=W, pady=(10,2))

        # Paste text area
        pf = Frame(p, bg=BG_DARK); pf.pack(fill=BOTH, expand=True, padx=16, pady=4)
        sc = Scrollbar(pf, orient=VERTICAL); sc.pack(side=RIGHT, fill=Y)
        self.paste_text = Text(pf, bg=BG_INPUT, fg=TEXT_PRIMARY, font=("Consolas",9), wrap=WORD,
                               relief="flat", bd=6, insertbackground=TEXT_PRIMARY, yscrollcommand=sc.set)
        self.paste_text.pack(fill=BOTH, expand=True); sc.config(command=self.paste_text.yview)

        # Buttons
        bt = Frame(p, bg=BG_DARK); bt.pack(fill=X, padx=16, pady=(4,2))
        ttk.Button(bt, text="🔍  Parse References", style="Sec.TButton",
                   command=self._parse_paste).pack(side=LEFT, padx=2)
        ttk.Button(bt, text="Clear", style="Sec.TButton",
                   command=lambda: self.paste_text.delete("1.0", END)).pack(side=LEFT, padx=2)
        self.paste_export_btn = ttk.Button(bt, text="⬆  EXPORT ALL REFERENCED ASSETS",
                                            style="Accent.TButton", command=self._export_from_paste)
        self.paste_export_btn.pack(side=RIGHT, padx=2)

        # Results list
        rf = Frame(p, bg=BG_DARK); rf.pack(fill=X, padx=16, pady=(2,2))
        self.paste_refs_lbl = ttk.Label(rf, text="Paste prefab data and click Parse to see referenced assets.",
                                         style="Dim.TLabel")
        self.paste_refs_lbl.pack(anchor=W)

        rlf = Frame(p, bg=BG_DARK); rlf.pack(fill=X, padx=16, pady=(0,2), ipady=40)
        sc2 = Scrollbar(rlf, orient=VERTICAL); sc2.pack(side=RIGHT, fill=Y)
        self.paste_refs_lb = Listbox(rlf, bg=BG_MID, fg=TEXT_PRIMARY, selectbackground=ACCENT,
                                      selectforeground="white", font=("Consolas",10), relief="flat",
                                      bd=4, yscrollcommand=sc2.set, activestyle="none", height=6)
        self.paste_refs_lb.pack(fill=BOTH, expand=True); sc2.config(command=self.paste_refs_lb.yview)

        # Status
        sb = Frame(p, bg=BG_MID); sb.pack(fill=X, padx=16, pady=(2,8))
        self.paste_prog = ttk.Progressbar(sb, style="green.Horizontal.TProgressbar", length=400)
        self.paste_prog.pack(fill=X, padx=8, pady=4)
        self.paste_stat = ttk.Label(sb, text="", style="Status.TLabel")
        self.paste_stat.pack(padx=8, pady=(0,4))

    def _br_generic(self, var, title):
        d = filedialog.askdirectory(title=title)
        if d:
            var.set(d)

    def _parse_paste(self):
        """Parse the pasted prefab text and show found references."""
        text = self.paste_text.get("1.0", END)
        if not text.strip():
            messagebox.showinfo("Empty", "Paste prefab data first (Ctrl+C on prefab in UEFN).")
            return

        # Determine project name
        pn = ""
        src = self.paste_source_path.get().strip()
        if src:
            s = ProjectScanner(src)
            s.content_dir = s._find_content()
            pn = s._detect_project_name()
        if not pn:
            # Try to detect from paste text itself
            m = re.search(r'/([A-Z][A-Za-z0-9_]+)/(?:Meshes|Materials|Prefabs|SFX|Textures|Sounds)/', text)
            if m:
                pn = m.group(1)

        paths = parse_clipboard_refs(text, project_name=pn)

        self.paste_refs_lb.delete(0, END)
        self._paste_parsed_paths = paths
        self._paste_project_name = pn

        if not paths:
            self.paste_refs_lbl.config(text="⚠ No asset references found in pasted text.")
            return

        for p in paths:
            # Classify based on path
            cat = "Other"
            pl = p.lower()
            if "mesh" in pl or pl.startswith("sm_") or "/sm_" in pl:
                cat = "Mesh"
            elif "material" in pl or pl.startswith("m_") or pl.startswith("mi_"):
                cat = "Material"
            elif "sfx" in pl or "sound" in pl or "audio" in pl or "cue_" in pl or "mss_" in pl:
                cat = "Sound"
            elif "texture" in pl or pl.startswith("t_"):
                cat = "Texture"
            elif "prefab" in pl or pl.startswith("pf_"):
                cat = "Prefab"
            elif "_verse" in pl:
                cat = "Verse"
            elif "fx" in pl or "niagara" in pl or "particle" in pl:
                cat = "Particle"

            ic = CATEGORY_ICONS.get(cat, "📄")
            self.paste_refs_lb.insert(END, f"{ic} [{cat:>10}]  {p}")

        self.paste_refs_lbl.config(text=f"Found {len(paths)} asset references (project: {pn})")
        self.paste_stat.config(text=f"Parsed {len(paths)} references. Click Export to copy them.")
        self._refresh_log()

    def _export_from_paste(self):
        """Export all assets found in the pasted prefab data."""
        if not hasattr(self, '_paste_parsed_paths') or not self._paste_parsed_paths:
            self._parse_paste()
            if not hasattr(self, '_paste_parsed_paths') or not self._paste_parsed_paths:
                return

        src = self.paste_source_path.get().strip()
        if not src or not Path(src).is_dir():
            messagebox.showerror("Error", "Pick a source project folder first.")
            return
        dst = self.paste_export_path.get().strip()
        if not dst:
            messagebox.showerror("Error", "Pick an export destination.")
            return

        if self._busy:
            return
        self._busy = True
        self.paste_export_btn.state(["disabled"])
        self.paste_stat.config(text="Scanning project + exporting…")

        paths = self._paste_parsed_paths
        pn = getattr(self, '_paste_project_name', '')

        def do():
            # Scan the source project
            scanner = ProjectScanner(src)
            scanner.scan()

            # Match parsed paths to actual files
            matched: list[dict] = []
            unmatched: list[str] = []
            seen: set[str] = set()

            for content_path in paths:
                found = False
                # Try direct game path lookup
                for prefix in [f"/{scanner.project_name}/", "/Game/"]:
                    entry = scanner.lookup_by_game_path(prefix + content_path)
                    if entry and entry["abs_path"] not in seen:
                        seen.add(entry["abs_path"])
                        matched.append(entry)
                        found = True
                        break
                if found:
                    continue

                # Try stem lookup (last segment of path)
                stem = content_path.rsplit("/", 1)[-1] if "/" in content_path else content_path
                stem = stem.split(".")[0]
                entries = scanner.lookup_by_stem(stem)
                if entries:
                    for e in entries:
                        if e["abs_path"] not in seen:
                            seen.add(e["abs_path"])
                            matched.append(e)
                            found = True
                    continue

                unmatched.append(content_path)

            log.info(f"Paste export: {len(matched)} matched, {len(unmatched)} unmatched")
            for u in unmatched:
                log.warn(f"  UNMATCHED: {u}")

            # Also resolve deps for matched assets (they might ref textures etc.)
            resolver = DependencyResolver(scanner)
            extra_deps: list[dict] = []
            for entry in list(matched):
                deps = resolver.resolve(entry)
                for d in deps:
                    if d["abs_path"] not in seen:
                        seen.add(d["abs_path"])
                        extra_deps.append(d)
            matched.extend(extra_deps)

            # Export
            exporter = AssetExporter(scanner, dst)
            result = exporter.export(matched, resolve=False)  # deps already resolved
            result["matched"] = len(matched)
            result["unmatched"] = unmatched
            return result

        self._run_task(do, self._paste_export_done)

    def _paste_export_done(self, r):
        self._busy = False
        self.paste_export_btn.state(["!disabled"])
        self._log_lines([
            f"\n{'═'*65}",
            f"  PASTE EXPORT — {datetime.now()}",
            f"  Folder: {r['export_folder']}",
            f"  Matched: {r.get('matched', '?')} | Copied: {r['copied']} | Errors: {r['errors']}",
        ])
        if r.get("unmatched"):
            self._log_lines([f"  UNMATCHED (not found in project):"])
            for u in r["unmatched"]:
                self._log_lines([f"    ✗ {u}"])
        self._log_lines([f"{'─'*65}"] + r["log"])
        self.paste_stat.config(text=f"Done — {r['copied']} files exported. "
                               f"{len(r.get('unmatched', []))} unmatched.")
        self.paste_prog["value"] = 100
        self._refresh_log()
        msg = f"Exported {r['copied']} files"
        if r.get("unmatched"):
            msg += f"\n\n{len(r['unmatched'])} assets not found in project:\n"
            msg += "\n".join(f"  • {u}" for u in r["unmatched"][:10])
        messagebox.showinfo("Done", msg + f"\n\n{r['export_folder']}")

    def _build_import(self, p):
        top = Frame(p, bg=BG_DARK); top.pack(fill=X, padx=16, pady=(8,0))
        ttk.Label(top, text="Import from Export Bundle", style="Title.TLabel").pack(anchor=W)
        ttk.Label(top, text="Select an export folder + target project", style="Dim.TLabel").pack(anchor=W)

        ttk.Label(top, text="Export Bundle:", style="Header.TLabel").pack(anchor=W, pady=(10,0))
        dr = Frame(top, bg=BG_DARK); dr.pack(fill=X, pady=2)
        Entry(dr, textvariable=self.import_source, font=("Consolas",10), bg=BG_INPUT, fg=TEXT_PRIMARY,
              insertbackground=TEXT_PRIMARY, relief="flat", bd=6).pack(side=LEFT, fill=X, expand=True, padx=(0,5))
        ttk.Button(dr, text="📁 Browse…", style="Sec.TButton", command=self._br_isrc).pack(side=RIGHT)

        self.mf_lbl = ttk.Label(top, text="", style="Dim.TLabel"); self.mf_lbl.pack(anchor=W, pady=2)
        bf = Frame(top, bg=BG_DARK); bf.pack(fill=BOTH, expand=True, pady=4)
        sc = Scrollbar(bf, orient=VERTICAL); sc.pack(side=RIGHT, fill=Y)
        self.bun_lb = Listbox(bf, bg=BG_MID, fg=TEXT_PRIMARY, font=("Consolas",10), relief="flat",
                              bd=4, yscrollcommand=sc.set, activestyle="none")
        self.bun_lb.pack(fill=BOTH, expand=True); sc.config(command=self.bun_lb.yview)

        self._picker(top, "Target Project:", self.import_target, self._br_itgt, "_tgt_cb")

        ib = Frame(p, bg=BG_DARK); ib.pack(fill=X, padx=16, pady=8)
        ttk.Button(ib, text="⬇  IMPORT", style="Accent.TButton", command=self._import).pack(side=LEFT)
        self.imp_stat = ttk.Label(ib, text="", style="Status.TLabel"); self.imp_stat.pack(side=LEFT, padx=12)
        self.imp_prog = ttk.Progressbar(ib, style="green.Horizontal.TProgressbar", length=300)
        self.imp_prog.pack(side=RIGHT, padx=8)

    def _build_organizer(self, p):
        top = Frame(p, bg=BG_DARK); top.pack(fill=X, padx=16, pady=(8,0))
        ttk.Label(top, text="Project Organizer", style="Title.TLabel").pack(anchor=W)
        ttk.Label(top, text="Sort assets into category folders", style="Dim.TLabel").pack(anchor=W)

        self._picker(top, "Project:", self.org_path, self._br_org, "_org_cb")

        cr = Frame(top, bg=BG_DARK); cr.pack(fill=X, pady=6)
        ttk.Button(cr, text="🔍 Scan", style="Accent.TButton", command=self._org_scan).pack(side=LEFT)
        ttk.Radiobutton(cr, text="Copy", variable=self.org_mode, value="copy",
                        style="Dark.TRadiobutton").pack(side=LEFT, padx=(16,4))
        ttk.Radiobutton(cr, text="Move", variable=self.org_mode, value="move",
                        style="Dark.TRadiobutton").pack(side=LEFT, padx=4)
        self.org_count = ttk.Label(cr, text="", style="Dim.TLabel"); self.org_count.pack(side=LEFT, padx=12)

        of = Frame(top, bg=BG_DARK); of.pack(fill=BOTH, expand=True, pady=4)
        sc = Scrollbar(of, orient=VERTICAL); sc.pack(side=RIGHT, fill=Y)
        self.org_lb = Listbox(of, bg=BG_MID, fg=TEXT_PRIMARY, font=("Consolas",10), relief="flat",
                              bd=4, yscrollcommand=sc.set, activestyle="none")
        self.org_lb.pack(fill=BOTH, expand=True); sc.config(command=self.org_lb.yview)

        ob = Frame(p, bg=BG_DARK); ob.pack(fill=X, padx=16, pady=8)
        ttk.Button(ob, text="🗂️  ORGANIZE", style="Accent.TButton", command=self._org_run).pack(side=LEFT)
        self.org_stat = ttk.Label(ob, text="", style="Status.TLabel"); self.org_stat.pack(side=LEFT, padx=12)
        self.org_prog = ttk.Progressbar(ob, style="green.Horizontal.TProgressbar", length=300)
        self.org_prog.pack(side=RIGHT, padx=8)

    def _build_log(self, p):
        ttk.Label(p, text="Tool Log", style="Title.TLabel").pack(anchor=W, padx=16, pady=(8,4))
        ttk.Label(p, text="Shows dependency resolution details. Save and send for debugging.",
                  style="Dim.TLabel").pack(anchor=W, padx=16)
        lf = Frame(p, bg=BG_DARK); lf.pack(fill=BOTH, expand=True, padx=10, pady=4)
        sc = Scrollbar(lf, orient=VERTICAL); sc.pack(side=RIGHT, fill=Y)
        self.log_t = Text(lf, bg=BG_INPUT, fg=TEXT_SECONDARY, font=("Consolas",9), wrap=WORD,
                          relief="flat", bd=6, state=DISABLED, yscrollcommand=sc.set)
        self.log_t.pack(fill=BOTH, expand=True); sc.config(command=self.log_t.yview)

        bb = Frame(p, bg=BG_DARK); bb.pack(fill=X, padx=16, pady=6)
        ttk.Button(bb, text="Refresh", style="Sec.TButton", command=self._refresh_log).pack(side=LEFT, padx=4)
        ttk.Button(bb, text="Save Log…", style="Sec.TButton", command=self._save_log).pack(side=LEFT, padx=4)
        ttk.Button(bb, text="Clear", style="Sec.TButton", command=self._clear_log).pack(side=LEFT, padx=4)

    # ── Helpers ─────────────────────────────
    def _ph(self, w, txt):
        def fi(e):
            if w.get() == txt: w.delete(0, END); w.config(fg=TEXT_PRIMARY)
        def fo(e):
            if not w.get(): w.insert(0, txt); w.config(fg=TEXT_DIM)
        w.insert(0, txt); w.config(fg=TEXT_DIM)
        w.bind("<FocusIn>", fi); w.bind("<FocusOut>", fo)

    def _run_task(self, work_fn, callback):
        if self._in_uefn:
            self._pending = (work_fn, callback)
        else:
            def wrapper():
                try:
                    result = work_fn()
                    self.root.after(0, lambda: callback(result))
                except Exception as ex:
                    self.root.after(0, lambda: self._task_err(ex))
            threading.Thread(target=wrapper, daemon=True).start()

    def _task_err(self, ex):
        self._busy = False
        try: self.exp_btn.state(["!disabled"])
        except: pass
        self.exp_stat.config(text=f"Error: {ex}")
        log.warn(f"Task error: {ex}")
        self._refresh_log()

    # ── Project detection ───────────────────
    def _detect_projects(self):
        self._run_task(lambda: UEFNProjectFinder.find_all_projects(), self._on_detected)

    def _on_detected(self, pj):
        self.projects = pj
        disp = [f"{p['name']}  —  {p['last_modified'].strftime('%Y-%m-%d %H:%M')}"
                f"{'  [Verse]' if p['has_verse'] else ''}   ({p['path']})" for p in pj]
        if not disp:
            disp = ["  (No projects found — use Browse)"]
        for attr in ["_src_cb", "_tgt_cb", "_org_cb", "_paste_src_cb"]:
            cb = getattr(self, attr, None)
            if cb: cb["values"] = disp
        if pj:
            if not self.source_path.get(): self.source_path.set(pj[0]["path"])
            if not self.paste_source_path.get(): self.paste_source_path.set(pj[0]["path"])
            if not self.import_target.get(): self.import_target.set(pj[0]["path"])
            if not self.org_path.get(): self.org_path.set(pj[0]["path"])
        self.exp_stat.config(text=f"Found {len(pj)} project{'s' if len(pj)!=1 else ''}. Ready.")

    # ── Browse ──────────────────────────────
    def _br_src(self):
        d = filedialog.askdirectory(title="Source Project"); d and self.source_path.set(d)
    def _br_exp(self):
        d = filedialog.askdirectory(title="Export Destination"); d and self.export_path.set(d)
    def _br_isrc(self):
        d = filedialog.askdirectory(title="Export Bundle")
        if d: self.import_source.set(d); self._preview_bundle(d)
    def _br_itgt(self):
        d = filedialog.askdirectory(title="Target Project"); d and self.import_target.set(d)
    def _br_org(self):
        d = filedialog.askdirectory(title="Project to Organize"); d and self.org_path.set(d)

    # ── Scan ────────────────────────────────
    def _scan(self):
        if self._busy: return
        src = self.source_path.get().strip()
        if not src or not Path(src).is_dir():
            messagebox.showerror("Error", "Pick a valid project."); return
        self._busy = True; self.exp_stat.config(text="Scanning…"); self.asset_lb.delete(0, END)
        if self.scanner: self.scanner.cancel()
        def do():
            s = ProjectScanner(src); s.scan(); self.scanner = s; return None
        self._run_task(do, lambda _: self._on_scanned())

    def _on_scanned(self):
        self._busy = False
        if not self.scanner: return
        for w in list(self.cat_frame.winfo_children()):
            if isinstance(w, ttk.Button): w.destroy()
        self.active_cats = set(self.scanner.category_counts.keys())
        self.cat_buttons.clear()
        ab = ttk.Button(self.cat_frame, text="ALL", style="FOn.TButton", command=self._tog_all)
        ab.pack(side=LEFT, padx=2); self.cat_buttons["__ALL__"] = ab
        for c, n in sorted(self.scanner.category_counts.items()):
            ic = CATEGORY_ICONS.get(c, "📄")
            b = ttk.Button(self.cat_frame, text=f"{ic} {c} ({n})", style="FOn.TButton",
                           command=lambda c=c: self._tog_cat(c))
            b.pack(side=LEFT, padx=2); self.cat_buttons[c] = b
        self.folder_cb["values"] = ["ALL"] + sorted(self.scanner.folder_tree.keys())
        self.folder_filter.set("ALL")
        self.search_var.set(""); self._ph(self.search_e, "Search…")
        self._filter()
        total = len(self.scanner.all_entries)
        parts = " | ".join(f"{CATEGORY_ICONS.get(c,'')} {c}: {n}"
                           for c, n in sorted(self.scanner.category_counts.items()))
        self.exp_stat.config(text=f"{total} assets — {parts}")
        self.exp_prog["value"] = 0
        self._refresh_log()

    # ── Filter ──────────────────────────────
    def _on_search(self, *_):
        if self._search_id: self.root.after_cancel(self._search_id)
        self._search_id = self.root.after(200, self._filter)

    def _tog_cat(self, c):
        if c in self.active_cats:
            self.active_cats.discard(c); self.cat_buttons[c].configure(style="FOff.TButton")
        else:
            self.active_cats.add(c); self.cat_buttons[c].configure(style="FOn.TButton")
        self._filter()

    def _tog_all(self):
        if self.scanner:
            ac = set(self.scanner.category_counts.keys())
            if self.active_cats == ac:
                self.active_cats.clear()
                for b in self.cat_buttons.values(): b.configure(style="FOff.TButton")
            else:
                self.active_cats = ac.copy()
                for b in self.cat_buttons.values(): b.configure(style="FOn.TButton")
        self._filter()

    def _filter(self):
        if not self.scanner: return
        s = self.search_var.get().strip().lower()
        if s in ("search…", ""): s = ""
        fld = self.folder_filter.get()
        self.display_list.clear(); self.asset_lb.delete(0, END)
        for e in self.scanner.all_entries:
            if e["category"] not in self.active_cats: continue
            if fld != "ALL" and e["rel_folder"] != fld: continue
            if s:
                hay = f"{e['name']} {e['rel_path']} {e['category']}".lower()
                if not all(t in hay for t in s.split()): continue
            self.display_list.append(e)
        self.display_list.sort(key=lambda e: (e["category"], e["rel_path"]))
        for e in self.display_list:
            ic = CATEGORY_ICONS.get(e["category"], "📄")
            kb = e["size"] / 1024
            ct = f"[{e['category']:>10}]"
            self.asset_lb.insert(END, f"{ic} {ct}  {e['rel_path']}   ({kb:.1f} KB)")
        self.count_lbl.config(text=f"{len(self.display_list)} shown (of {len(self.scanner.all_entries)} total)")

    # ── Export ──────────────────────────────
    def _export(self):
        if self._busy: return
        if not self.scanner: messagebox.showerror("Error", "Scan first."); return
        ep = self.export_path.get().strip()
        if not ep: messagebox.showerror("Error", "Pick export destination."); return
        sel = self.asset_lb.curselection()
        if not sel: messagebox.showwarning("Warning", "Nothing selected."); return
        self._busy = True; self.exp_btn.state(["disabled"])
        items = [self.display_list[i] for i in sel]
        self.exp_stat.config(text=f"Exporting {len(items)} assets…")
        def do():
            return AssetExporter(self.scanner, ep).export(items, resolve=self.resolve_deps.get())
        self._run_task(do, self._exp_done)

    def _exp_done(self, r):
        self._busy = False; self.exp_btn.state(["!disabled"])
        self._log_lines([
            f"\n{'═'*65}",
            f"  EXPORT — {datetime.now()}",
            f"  Folder: {r['export_folder']}",
            f"  Copied: {r['copied']} | Errors: {r['errors']}",
            f"{'─'*65}",
        ] + r["log"])
        self.exp_stat.config(text=f"Done — {r['copied']} files → {Path(r['export_folder']).name}")
        self.exp_prog["value"] = 100
        self._refresh_log()
        messagebox.showinfo("Done",
            f"Exported {r['copied']} files\nErrors: {r['errors']}\n\n{r['export_folder']}")

    # ── Import ──────────────────────────────
    def _preview_bundle(self, folder):
        self.bun_lb.delete(0, END)
        mp = Path(folder) / EXPORT_MANIFEST
        if mp.exists():
            m = json.loads(mp.read_text())
            cs = ", ".join(f"{k}: {v}" for k, v in sorted(m.get("categories", {}).items()))
            self.mf_lbl.config(text=f"Bundle: {m.get('total_files','?')} files | {m.get('exported_at','?')} | {cs}")
            for e in m.get("files", []):
                ic = CATEGORY_ICONS.get(e.get("category", ""), "📄")
                self.bun_lb.insert(END, f"{ic}  [{e.get('category',''):>10}]  {e['name']}")
        else:
            self.mf_lbl.config(text="⚠ No manifest found.")

    def _import(self):
        if self._busy: return
        s = self.import_source.get().strip()
        t = self.import_target.get().strip()
        if not s or not Path(s).is_dir(): messagebox.showerror("Error", "Pick bundle."); return
        if not t or not Path(t).is_dir(): messagebox.showerror("Error", "Pick target project."); return
        self._busy = True; self.imp_stat.config(text="Importing…")
        self._run_task(lambda: AssetImporter(s, t).run(), self._imp_done)

    def _imp_done(self, r):
        self._busy = False
        if "error" in r: messagebox.showerror("Error", r["error"]); return
        self._log_lines([
            f"\n{'═'*65}",
            f"  IMPORT — {datetime.now()}",
            f"  Copied: {r['copied']} | Errors: {r['errors']}",
            f"{'─'*65}",
        ] + r["log"])
        self.imp_stat.config(text=f"Done — {r['copied']} imported.")
        self.imp_prog["value"] = 100
        self._refresh_log()
        messagebox.showinfo("Done", f"Imported {r['copied']} files.\nRestart UEFN to see them.")

    # ── Organizer ───────────────────────────
    def _org_scan(self):
        if self._busy: return
        op = self.org_path.get().strip()
        if not op or not Path(op).is_dir(): messagebox.showerror("Error", "Pick a project."); return
        self._busy = True; self.org_stat.config(text="Scanning…"); self.org_lb.delete(0, END)
        def do():
            s = ProjectScanner(op); s.scan(); self.org_scanner = s; return None
        self._run_task(do, lambda _: self._org_preview())

    def _org_preview(self):
        self._busy = False
        if not self.org_scanner: return
        self.org_lb.delete(0, END); counts = {}
        for e in self.org_scanner.all_entries:
            cat = e["category"]; tn = ORGANIZE_FOLDERS.get(cat, "Other")
            cp = Path(e["abs_path"]).parent.name
            if cp == tn: status = "✅ in place"
            else: status = f"→ {tn}/"; counts[cat] = counts.get(cat, 0) + 1
            ic = CATEGORY_ICONS.get(cat, "📄")
            self.org_lb.insert(END, f"{ic}  [{cat:>10}]  {e['rel_path']}   {status}")
        mv = sum(counts.values()); al = len(self.org_scanner.all_entries) - mv
        self.org_count.config(text=f"{mv} to reorganize, {al} already in place")
        self.org_stat.config(text="Preview ready."); self.org_prog["value"] = 0

    def _org_run(self):
        if self._busy: return
        if not self.org_scanner: messagebox.showerror("Error", "Scan first."); return
        mode = self.org_mode.get()
        if not messagebox.askyesno("Confirm", f"{'MOVE' if mode=='move' else 'COPY'} files?\n\nProceed?"): return
        self._busy = True; self.org_stat.config(text="Organizing…")
        self._run_task(lambda: ProjectOrganizer(self.org_scanner, mode=mode).organize(), self._org_done)

    def _org_done(self, r):
        self._busy = False
        if "error" in r: messagebox.showerror("Error", r["error"]); return
        self._log_lines([
            f"\n{'═'*65}",
            f"  ORGANIZE — {datetime.now()}",
            f"  Moved: {r['moved']} | Skipped: {r['skipped']} | Errors: {r['errors']}",
            f"{'─'*65}",
        ] + r["log"])
        self.org_stat.config(text=f"Done — {r['moved']} organized, {r['skipped']} in place.")
        self.org_prog["value"] = 100
        self._refresh_log()
        messagebox.showinfo("Done", f"Organized {r['moved']}.\nSkipped {r['skipped']}.\n"
                            f"Errors: {r['errors']}\n\nRestart UEFN.")

    # ── Log ─────────────────────────────────
    def _log_lines(self, lines):
        self.log_t.config(state=NORMAL)
        for l in lines:
            self.log_t.insert(END, l + "\n")
        self.log_t.see(END); self.log_t.config(state=DISABLED)

    def _refresh_log(self):
        self.log_t.config(state=NORMAL)
        self.log_t.insert(END, log.text())
        log.clear()
        self.log_t.see(END); self.log_t.config(state=DISABLED)

    def _save_log(self):
        self._refresh_log()
        path = filedialog.asksaveasfilename(
            title="Save Log",
            defaultextension=".txt",
            initialfile=f"uefn_migrator_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            filetypes=[("Text files", "*.txt"), ("All", "*.*")],
        )
        if path:
            self.log_t.config(state=NORMAL)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_t.get("1.0", END))
            self.log_t.config(state=DISABLED)
            self.exp_stat.config(text=f"Log saved: {path}")

    def _clear_log(self):
        self.log_t.config(state=NORMAL); self.log_t.delete("1.0", END); self.log_t.config(state=DISABLED)
        log.clear()

    # ═══════════════════════════════════════
    #  RUN — auto-detects UEFN vs standalone
    # ═══════════════════════════════════════
    def run(self):
        try:
            import unreal as _ue
            self._run_uefn(_ue)
        except ImportError:
            self.root.mainloop()

    def _run_uefn(self, ue):
        self._in_uefn = True; self._ue = ue; self._tick_handle = None
        self.root.attributes('-topmost', True)
        def on_tick(delta_time):
            try:
                if not self.root.winfo_exists(): self._stop_tick(); return
                if self._pending:
                    work_fn, callback = self._pending; self._pending = None
                    try:
                        result = work_fn(); callback(result)
                    except Exception as ex:
                        self._busy = False
                        try: self.exp_btn.state(["!disabled"])
                        except: pass
                        self.exp_stat.config(text=f"Error: {ex}")
                        ue.log_error(f"[UEFN Exporter] {ex}")
                self.root.update()
            except: self._stop_tick()
        self._tick_handle = ue.register_slate_post_tick_callback(on_tick)
        ue.log("[UEFN Exporter v5] Tool opened (tick mode)")
        def on_close(): self._stop_tick(); self.root.destroy()
        self.root.protocol("WM_DELETE_WINDOW", on_close)

    def _stop_tick(self):
        if hasattr(self, '_tick_handle') and self._tick_handle:
            try: self._ue.unregister_slate_post_tick_callback(self._tick_handle); self._ue.log("[UEFN Exporter] Closed")
            except: pass
            self._tick_handle = None


if __name__ == "__main__":
    App().run()
# Note: When imported as a module, do NOT auto-launch.
# Call App().run() explicitly from wrapper tool instead.
