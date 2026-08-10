# -*- mode: python ; coding: utf-8 -*-
# Build with: pyinstaller dubify.spec --noconfirm --clean
# (or just run build_exe.ps1, which also zips the result for a GitHub release)

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

a = Analysis(
    ['main.py'],
    pathex=[],
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
    icon=None,
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
