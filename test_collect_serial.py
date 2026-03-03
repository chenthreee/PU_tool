#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试 PyInstaller 的 collect_all 是否能找到 serial 模块"""

try:
    from PyInstaller.utils.hooks import collect_all

    print("正在尝试收集 serial 模块...")
    serial_datas, serial_binaries, serial_hiddenimports = collect_all('serial')

    print(f"\n收集结果:")
    print(f"  数据文件数量: {len(serial_datas)}")
    print(f"  二进制文件数量: {len(serial_binaries)}")
    print(f"  隐藏导入数量: {len(serial_hiddenimports)}")

    if serial_hiddenimports:
        print(f"\n隐藏导入列表:")
        for imp in sorted(serial_hiddenimports):
            print(f"    - {imp}")
    else:
        print("\n警告: 没有收集到任何 serial 隐藏导入！")
        print("这可能是问题所在。")

        # 尝试使用 collect_submodules
        print("\n尝试使用 collect_submodules...")
        from PyInstaller.utils.hooks import collect_submodules
        serial_modules = collect_submodules('serial')
        print(f"  collect_submodules 找到 {len(serial_modules)} 个模块")
        if serial_modules:
            for mod in sorted(serial_modules):
                print(f"    - {mod}")

except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
