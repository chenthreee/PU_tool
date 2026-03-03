import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import sys
import traceback
from uart_gui import UARTTestGUI
from utils import get_resource_path

def check_requirements():
    """检查运行环境和必要文件"""
    
    # 检查配置文件
    config_path = get_resource_path('uart_command_set.json')
    if not os.path.exists(config_path):
        messagebox.showerror("Error", "Config file not found: uart_command_set.json")
        return False
    label_path = get_resource_path('label.json')
    if not os.path.exists(label_path):
        messagebox.showerror("Error", "Language file not found: label.json")
        return False
    # 检查配置文件格式
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            json.load(f)
    except json.JSONDecodeError:
        messagebox.showerror("Error", "Config file format error: uart_command_set.json")
        return False
    except Exception as e:
        messagebox.showerror("Error", f"Error reading config file: {str(e)}")
        return False

    return True

def main():
    try:
        # 检查运行环境
        if not check_requirements():
            return

        # 创建主窗口
        root = tk.Tk()
        root.title("UART Test Tool")
        
        # 设置窗口大小和位置
        window_width = 800
        window_height = 600
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # 创建应用实例
        try:
            app = UARTTestGUI(root)
        except Exception as e:
            error_msg = str(e)
            error_details = traceback.format_exc()
            
            # 写入错误日志
            with open('error_log.txt', 'w', encoding='utf-8') as f:
                f.write(f"GUI初始化错误: {error_msg}\n")
                f.write("详细信息:\n")
                f.write(error_details)
            
            messagebox.showerror("Error", 
                               f"Program initialization failed:\n{error_msg}\n\nDetails written to error_log.txt")
            return
        
        # 运行主循环
        root.mainloop()
        
    except Exception as e:
        error_msg = str(e)
        error_details = traceback.format_exc()
        
        # 写入错误日志
        with open('error_log.txt', 'w', encoding='utf-8') as f:
            f.write(f"程序运行错误: {error_msg}\n")
            f.write("详细信息:\n")
            f.write(error_details)
        
        # 显示错误对话框
        messagebox.showerror("Error", 
                           f"Program error occurred:\n{error_msg}\n\nDetails written to error_log.txt")

if __name__ == "__main__":
    main() 