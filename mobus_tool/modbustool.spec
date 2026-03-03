# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('model_1.json', '.'),
        ('model_802.json', '.'),
        ('model_805.json', '.'),
        ('model_64900.json', '.'),
        ('model_64950.json', '.'),
        ('model_64951.json', '.'),
        ('model_64952.json', '.'),
        ('uart_command_set.json','.'),
        ('BQC.ico', '.'),  # 添加图标文件到数据文件
    ],
    hiddenimports=[
        'serial',
        'serial.tools.list_ports',
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.scrolledtext',
        'tkinter.filedialog',
        'threading',
        'time',
        'json',
        'os',
        'functools',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='SunSpec上位机',
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
    icon='BQC.ico',  # 设置exe文件的图标
) 