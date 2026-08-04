# -*- mode: python ; coding: utf-8 -*-
# Сборка: pyinstaller build.spec

block_cipher = None

a = Analysis(
    ['main_pyside.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('help.html', '.'),
        ('EULA.md', '.'),
        ('LICENSE', '.'),
        ('PRIVACY.md', '.'),
        ('THIRD_PARTY_LICENSES.txt', '.'),
        ('resources/eula.html', 'resources'),
        ('images', 'images'),
    ],
    hiddenimports=['src', 'src.dialogs', 'src.services', 'src.ui', 'src.utils'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt5', 'cryptography'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FinanceFugue',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='images/FinanceFugue.ico',
)
