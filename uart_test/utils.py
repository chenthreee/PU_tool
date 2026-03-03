import tkinter as tk
from tkinter import ttk
import sys
import os

def get_resource_path(filename):
    """
    获取资源文件路径，兼容开发环境和PyInstaller打包后的环境
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe
        base_path = sys._MEIPASS
    else:
        # 源码运行
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

def format_bytes(data):
    if isinstance(data, (bytes, bytearray)):
        return ' '.join([f"{b:02X}" for b in data])
    return ' '.join([f"{b:02X}" for b in data])

def create_tooltip(widget, text):
    def show_tooltip(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        label = ttk.Label(tooltip, text=text, justify='left', relief='solid', borderwidth=1)
        label.pack()
        def hide_tooltip():
            tooltip.destroy()
        widget.tooltip = tooltip
        widget.bind('<Leave>', lambda e: hide_tooltip())
        tooltip.bind('<Leave>', lambda e: hide_tooltip())
    widget.bind('<Enter>', show_tooltip) 