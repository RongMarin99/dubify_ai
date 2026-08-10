# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller dubify.spec --noconfirm --clean
# (or just run build_exe.ps1, which also zips the result for a GitHub release)

import os
from PyInstaller.utils.hooks import collect_all

datas = [('translator/app/assets', 'translator/app/assets')]
binaries = []
hiddenimports = []

# torch/transformers/faster_whisper/voxcpm/soundfile ship native binaries and
# non-Python data files that PyInstaller's static import scan can't see —
# collect_all pulls those in via each package's own hook.
for pkg in ('torch', 'transformers', 'faster_whisper', 'voxcpm', 'soundfile'):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# PyInstaller's static dependency scanner misses a handful of MSVC runtime
# DLLs that Qt loads dynamically/delay-loaded rather than importing at link
# time (OpenMP + Concurrency Runtime pieces). Missing them doesn't raise a
# clean ImportError — Qt access-violates trying to call into them at startup.
# Everything Qt-module-shaped (Qt6Core.dll etc.) IS already detected
# correctly by the scanner, so only force these small named extras rather
# than the whole PySide6 folder (which would drag in ~150 unused Qt modules).
_MSVC_RUNTIME_EXTRAS = (
    "vcomp140.dll", "concrt140.dll", "vccorlib140.dll",
    "vcamp140.dll", "msvcp140_codecvt_ids.dll",
)
try:
    import PySide6
    pyside6_dir = os.path.dirname(PySide6.__file__)
    for fname in _MSVC_RUNTIME_EXTRAS:
        fpath = os.path.join(pyside6_dir, fname)
        if os.path.exists(fpath):
            binaries.append((fpath, 'PySide6'))
except Exception:
    pass

a = Analysis(
    ['main.py'],
    pathex=['translator'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DubifyAI',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='translator/app/assets/logo.ico',
)

# onedir build (not onefile) — torch/transformers/voxcpm are large enough that
# a single-file exe would re-unpack itself to a temp dir on every launch. This
# also matches how the auto-updater works: it robocopy's a new build over this
# whole folder instead of swapping a single binary.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='DubifyAI'
)
