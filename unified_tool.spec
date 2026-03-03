# -*- mode: python ; coding: utf-8 -*-

import re
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

# 从 unified_tool_manager.py 中提取版本号
def get_version_from_source():
    """从源代码中提取版本号"""
    try:
        with open('unified_tool_manager.py', 'r', encoding='utf-8') as f:
            content = f.read()
            match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"Warning: Could not extract version: {e}")
    return "V1.0.0"  # 默认版本
# 获取版本号
version = get_version_from_source()
exe_name = f'PU_BMS_Test_Bench_{version}'

print(f"Building executable with name: {exe_name}")

# 使用 collect_all 强制收集 pyserial 的所有内容
serial_datas, serial_binaries, serial_hiddenimports = collect_all('serial')
print(f"Collected serial hiddenimports: {len(serial_hiddenimports)} modules")

# 自动收集可能被动态加载的子模块，减少"缺少 module"问题
can_hiddenimports = collect_submodules('can_tool')
modbus_hiddenimports = collect_submodules('mobus_tool')
uart_hiddenimports = collect_submodules('uart_test')

block_cipher = None

a = Analysis(
    ['unified_tool_manager.py'],
    pathex=[],
    binaries=[
        ('can_tool/ControlCAN.dll', '.'),  # 改到根目录
    ] + serial_binaries,  # 添加 serial 的二进制文件
    datas=[
        # 共用图标（根目录）
        ('mobus_tool/BQC.ico', '.'),

        # CAN 配置（根目录可省，但放着不影响）
        ('can_tool/can_protocol_config.py', '.'),
        ('can_tool/lang_config.py', '.'),

        # Modbus 模型（改到根目录，代码用 sys._MEIPASS 直接找文件名）
        ('mobus_tool/model_1.json', '.'),
        ('mobus_tool/model_802.json', '.'),
        ('mobus_tool/model_805.json', '.'),
        ('mobus_tool/model_64900.json', '.'),
        ('mobus_tool/model_64950.json', '.'),
        ('mobus_tool/model_64951.json', '.'),
        ('mobus_tool/model_64952.json', '.'),
        ('mobus_tool/uart_command_set.json', '.'),

        # 确保所有JSON文件都在根目录，避免路径问题
        # UART 资源（改到根目录，代码直接找 label.json / uart_command_set.json）
        ('uart_test/pu_app.bin', '.'),
        ('uart_test/uart_command_set.json', '.'),
        ('uart_test/label.json', '.'),
    ] + serial_datas,  # 添加 serial 的数据文件
    hiddenimports=[
        'tkinter', 'tkinter.ttk', 'tkinter.messagebox', 'tkinter.scrolledtext', 'tkinter.filedialog',
        'serial', 'serial.tools.list_ports',
        'threading', 'time', 'json', 'os', 'functools', 'traceback', 'subprocess', 'ctypes',
        'datetime', 'struct',
        'can_tool.can_protocol_config', 'can_tool.lang_config', 'can_tool.can_host_computer',
        'mobus_tool.main', 'mobus_tool.sunspec_protocol', 'mobus_tool.modbus_client',
        'mobus_tool.gui_components', 'mobus_tool.language_manager',
        'uart_test.uart_gui', 'uart_test.protocol', 'uart_test.uart_interface',
        'uart_test.log_manager', 'uart_test.label_manager', 'uart_test.item_manager',
        'uart_test.uart_service', 'uart_test.utils',
    ] + serial_hiddenimports + can_hiddenimports + modbus_hiddenimports + uart_hiddenimports,
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
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name=exe_name,
    debug=False, bootloader_ignore_signals=False, strip=False,
    upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=False,  
    disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon='mobus_tool/BQC.ico',
)