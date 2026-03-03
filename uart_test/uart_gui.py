#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk
import serial
import time
import json
import tkinter.messagebox as messagebox
import sys
import traceback
import serial.tools.list_ports
import threading
from tkinter import filedialog
from datetime import datetime
import os
import queue
from protocol import (
    PU_FRAME_HEAD, PU_FUN_READ, PU_FUN_WRITE, PU_FUN_UPGRADE, PU_FUN_UPGRADE_CRC,
    PU_FUN_MCU_RESET, PU_FUN_CONNECT, PU_FUN_MCU_WRITE_ALARM, PU_FUN_MCU_WRITE_CONFIG, PU_FUN_MCU_WRITE_DATA,
    PU_ACK_WITH_DATA, PU_ACK_NO_DATA,
    PU_STATUS_OK, PU_STATUS_NO_FUNCODE, PU_STATUS_CRC_ERROR, PU_STATUS_ADDRESS_ERROR, PU_STATUS_NO_PERMISSION,
    PU_STATUS_DATA_ERROR, PU_STATUS_WRITE_FLASHDB_ERROR, PU_STATUS_RW_I2C_ERROR, PU_STATUS_DATA_LENGTH_ERROR,
    PU_STATUS_UPGRADE_PACKAGE_CRC_ERROR,
    calculate_crc16, to_signed, generate_read_command, generate_write_command, parse_response,
    calculate_complete_addr, generate_e0_handshake, generate_upgrade_packets, generate_upgrade_crc_command,
    UPGRADE_PACKET_SIZE, validate_value_for_type
)
from uart_interface import UARTInterface
from log_manager import LogManager
from label_manager import LabelManager
from item_manager import ItemManager
from uart_service import UARTService
import utils


def get_resource_path(filename):
    """
    获取资源文件路径,兼容开发环境和PyInstaller打包后的环境
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller打包后的exe
        base_path = sys._MEIPASS
    else:
        # 源码运行：使用模块所在目录
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, filename)

RECYCLE_TIME = 0.5
class UARTTestGUI:
    def __init__(self, parent_frame=None):
        """
        初始化UART工具
        Args:
            parent_frame: 父框架，如果为None则创建独立窗口
        """
        try:
            self.parent_frame = parent_frame
            self.is_embedded = parent_frame is not None
            
            if not self.is_embedded:
                # 独立模式：创建自己的root窗口
                self.root = tk.Tk()
                self.root.title("UART Test Tool")
                
                # 设置窗口大小和位置
                window_width = 800
                window_height = 600
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
                
                # 设置窗口图标
                try:
                    icon_path = get_resource_path('BQC.ico')
                    if os.path.exists(icon_path):
                        self.root.iconbitmap(icon_path)
                except Exception as e:
                    # 如果图标设置失败，不影响程序运行
                    pass
                
                # 创建主框架
                self.main_frame = ttk.Frame(self.root)
                self.main_frame.pack(fill=tk.BOTH, expand=True)
            else:
                # 嵌入模式：使用传入的父框架
                self.root = None
                self.main_frame = parent_frame
            
            # Configure styles 一些风格用于后面子模块的显示
            self.style = ttk.Style()
            self.style.configure("Module.TFrame", borderwidth=2, relief="raised")
            self.style.configure("Submodule.TFrame", borderwidth=1, relief="solid")
            self.style.configure("ModuleHeader.TFrame", background="#e1e1e1")
            self.style.configure("SubmoduleHeader.TFrame", background="#f0f0f0")
            
            # Serial port configuration 串口接口初始化
            self.uart = UARTInterface()
            
            # Dictionary to store variables and frames 初始化变量存储结构
            self.result_vars = {}
            self.input_vars = {}
            self.write_status_vars = {}
            self.module_frames = {}
            self.submodule_frames = {}
            self.module_states = {}
            self.submodule_states = {}

            # UI active state control for tabbed interface
            self._ui_active = True  # Default to active
            
            # Store references for language updates 
            self.module_labels = {}                 #模块标签
            self.submodule_labels = {}              #子模块标签
            self.module_read_buttons = {}           #模块读取按钮
            self.module_write_buttons = {}          #模块写入按钮
            self.submodule_read_buttons = {}
            self.submodule_write_buttons = {}
            self.item_read_buttons = {}
            self.item_write_buttons = {}
            
            # 管理类实例化 - 使用统一的资源路径
            self.log_manager = LogManager()
            self.label_manager = LabelManager()
            
            # 获取 JSON 文件路径
            json_file_path = get_resource_path('uart_command_set.json')
            
            self.item_manager = ItemManager(
                json_file=json_file_path,
                language=self.label_manager.current_language
            )
            
            # 日志回调绑定
            self.log_manager.set_log_callback(self._log_callback)
            
            # Load labels
            self.current_language = self.label_manager.current_language
            self.load_labels()
            
            # 设置默认串口
            self.default_port = 'COM1' if sys.platform == 'win32' else '/dev/ttyS0'
            
            # 创建主界面
            self.create_widgets()
            
            # 加载配置文件
            try:
                self.create_items()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load config file:\n{str(e)}")
                raise
            
            # 在 __init__ 或 create_items 后
            self.addr_map = {}
            for item in self.items:
                addr = int(item['index'], 16)
                self.addr_map[addr] = item
            # 初始化串口服务
            self.uart_service = UARTService(
                self.uart,
                log_func=self.add_to_log,
                gui_update_callback=self.update_item_display,
                addr_map=self.addr_map,
                f0_response_getter=lambda: self.f0_response_var.get(),  # 新增
                response_40_50_getter=lambda: self.response_40_50_var.get()  # 新增
            )
            self.loop_running = False  # <--- 在这里加上
                
        except Exception as e:
            error_msg = str(e)
            error_details = traceback.format_exc()
            with open('error_log.txt', 'w', encoding='utf-8') as f:
                f.write(f"GUI initialization error: {error_msg}\n")
                f.write("详细信息:\n")
                f.write(error_details)
            raise

    # 移除原来的 get_resource_path 方法，使用 utils 中的统一函数

    # 标签相关
    def load_labels(self):
        self.label_manager.load_labels()
        self.labels = self.label_manager.labels
        self.current_language = self.label_manager.current_language

    def get_label(self, key):
        return self.label_manager.get_label(key)

    def toggle_language(self):
        self.current_language = "CN" if self.current_language == "EN" else "EN"
        self.label_manager.set_language(self.current_language)
        self.item_manager.set_language(self.current_language)
        self.update_interface_language()
    
    def set_language(self, language):
        """外部设置语言的方法，用于统一管理器调用 - 优化版本"""
        print(f"UART tool external language setting: {language}")
        
        # 转换语言代码
        if language == 'zh':
            uart_language = "CN"
        elif language == 'en':
            uart_language = "EN"
        else:
            uart_language = language
            
        print(f"UART tool converted language code: {uart_language}")
        
        # 设置语言
        self.current_language = uart_language
        self.label_manager.set_language(uart_language)
        self.item_manager.set_language(uart_language)
        
        # 延迟更新界面，避免阻塞
        self._schedule_language_update()
        
        print(f"UART tool language setting completed: {language}")
    
    def _schedule_language_update(self):
        """延迟调度界面语言更新"""
        def update_ui():
            try:
                self.update_interface_language()
            except Exception as e:
                print(f"UART界面语言更新错误: {e}")
        
        # 延迟30ms执行界面更新
        if hasattr(self, 'root') and self.root:
            self.root.after(30, update_ui)
        elif hasattr(self, 'main_frame') and self.main_frame:
            self.main_frame.after(30, update_ui)

    def update_interface_language(self):
        """Update all interface elements with new language"""
        # Update language button (only if it exists)
        if hasattr(self, 'language_btn') and self.language_btn:
            self.language_btn.configure(text=self.get_label("language"))
        
        # Update serial configuration frame
        self.serial_frame.configure(text=self.get_label("serial_config"))
        self.port_label.configure(text=self.get_label("port"))
        self.baudrate_label.configure(text=self.get_label("baudrate"))
        self.data_bits_label.configure(text=self.get_label("data_bits"))
        self.stop_bits_label.configure(text=self.get_label("stop_bits"))
        self.parity_label.configure(text=self.get_label("parity"))
        
        # Update connection button text based on connection status
        if self.uart.is_open():
            self.connect_btn.configure(text=self.get_label("disconnect"))
            self.status_label.configure(text=self.get_label("connected"))
        else:
            self.connect_btn.configure(text=self.get_label("connect"))
            self.status_label.configure(text=self.get_label("disconnected"))
            
        self.refresh_btn.configure(text=self.get_label("refresh"))
        self.read_all_btn.configure(text=self.get_label("read_all"))
        self.write_all_btn.configure(text=self.get_label("write_all"))
        self.upgrade_btn.configure(text=self.get_label("upgrade_mcu")) # Update upgrade button text
        self.loop_button.configure(text=self.get_label("cycle_send"))
        self.f0_response_checkbox.configure(text=self.get_label("F0_response"))
        self.response_40_50_checkbox.configure(text=self.get_label("40/50_report"))
        # Update communication log frame
        self.log_frame.configure(text=self.get_label("communication_log"))
        self.clear_log_btn.configure(text=self.get_label("clear_log"))
        self.save_log_checkbox.configure(text=self.get_label("save_log"))
        # Clear and recreate all items to update their language
        self.recreate_items()

    def recreate_items(self):
        """Recreate all items with current language"""
        # Save the current scroll position
        current_scroll = self.canvas.yview()
        
        # Clear existing items
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        #save item tracking dictionaries  
        old_result_values ={k:v.get() for k,v in self.result_vars.items()}
        old_input_values ={k:v.get() for k,v in self.input_vars.items()if v is not None}
        old_write_status_values ={k:v.get() for k,v in self.write_status_vars.items()if v is not None}
        # Clear item tracking dictionaries
        self.organized_items = {}
        self.module_states = {}
        self.submodule_states = {}
        self.item_read_buttons = {}
        self.item_write_buttons = {}
        self.result_vars = {}
        self.input_vars = {}
        self.write_status_vars = {}
        
        # Recreate items
        self.create_items(old_result_values, old_input_values, old_write_status_values)
        
        # Restore scroll position
        self.canvas.yview_moveto(current_scroll[0])

    # 参数项相关
    def create_items(self, old_result_values=None, old_input_values=None, old_write_status_values=None):
        self.item_manager.load_items()
        self.items = self.item_manager.items
        self.organized_items = self.item_manager.get_organized_items()

        # Clear existing frames
        self.module_frames.clear()
        self.submodule_frames.clear()

        # Initialize module and submodule states for new modules/submodules
        for module in self.organized_items:
            if module not in self.module_states:
                self.module_states[module] = True
            
            for submodule in self.organized_items[module]:
                state_key = f"{module}_{submodule}"
                if state_key not in self.submodule_states:
                    self.submodule_states[state_key] = True

        # Create frames for each module
        current_row = 0
        for module in self.organized_items:
            # Create module header
            module_frame = ttk.Frame(self.scrollable_frame)
            module_frame.grid(row=current_row, column=0, sticky='ew', pady=2)
            module_frame.columnconfigure(0, weight=1)
            current_row += 1
            
            # Create module header with expand/collapse button
            self.create_module_header(module, module_frame)
            
            # Create content frame for this module
            content_frame = ttk.Frame(self.scrollable_frame)
            content_frame.grid(row=current_row, column=0, sticky='ew')
            content_frame.columnconfigure(0, weight=1)
            current_row += 1
            self.module_frames[module] = content_frame
            
            # Create submodules
            submodule_row = 0
            for submodule in self.organized_items[module]:
                # Create submodule header
                submodule_frame = ttk.Frame(content_frame)
                submodule_frame.grid(row=submodule_row, column=0, sticky='ew', pady=2)
                submodule_frame.columnconfigure(0, weight=1)
                submodule_row += 1
                
                # Create submodule header with expand/collapse button
                self.create_submodule_header(module, submodule, submodule_frame)
                
                # Create items for this submodule
                items_frame = ttk.Frame(content_frame)
                items_frame.grid(row=submodule_row, column=0, sticky='ew')
                items_frame.columnconfigure(0, weight=1)
                submodule_row += 1
                self.submodule_frames[(module, submodule)] = items_frame
                
                # Create individual item frames
                item_row = 0
                for item in self.organized_items[module][submodule]:
                    item_frame = self.create_item_frame(items_frame, item, old_result_values, old_input_values, old_write_status_values)
                    if item_frame:
                        item_frame.grid(row=item_row, column=0, sticky='ew', pady=2)
                        item_row += 1

            # Apply current expansion state
            if not self.module_states.get(module, True):
                content_frame.grid_remove()

            # Apply submodule expansion states
            for submodule in self.organized_items[module]:
                state_key = f"{module}_{submodule}"
                if not self.submodule_states.get(state_key, True):
                    if (module, submodule) in self.submodule_frames:
                        self.submodule_frames[(module, submodule)].grid_remove()

    def create_item_frame(self, parent, item, old_result_values=None, old_input_values=None, old_write_status_values=None):
        """Create a frame for displaying and controlling a single item"""
        try:
            # Create a frame for this item
            item_frame = ttk.Frame(parent)
            item_frame.grid(row=0, column=0, sticky='ew', pady=2)           

            # Configure column weights for better layout
            item_frame.columnconfigure(0, weight=0)  # Label column - fixed
            item_frame.columnconfigure(1, weight=0)  # Read button - fixed
            item_frame.columnconfigure(2, weight=1)  # Result entry - expandable
            item_frame.columnconfigure(3, weight=0)  # Write button - fixed
            item_frame.columnconfigure(4, weight=1)  # Write entry - expandable
            item_frame.columnconfigure(5, weight=1)  # Status entry - expandable

            # Create item label with tooltip
            display_text = item.get('item' if self.current_language == 'EN' else '项目', '')
            item_label = ttk.Label(item_frame, text=display_text, width=47, anchor='w')
            item_label.grid(row=0, column=0, padx=(40, 5), sticky='w')
            item['label_widget'] = item_label
            
            # Create tooltip for the label添加提示框
            data_type = item.get('type', 'int32_t')
            try:
                from protocol import get_type_info
                type_info = get_type_info(data_type)
                if data_type == 'float':
                    range_info = f"Range: ±{type_info['max']:.1e}"
                else:
                    range_info = f"Range: {type_info['min']} to {type_info['max']}"
            except:
                range_info = "Range: See documentation"
            
            self.create_tooltip(item_label, 
                              f"Address: {item['index']}\n"
                              f"Type: {data_type}\n"
                              f"{range_info}\n"
                              f"Permission: {item.get('permission', 'R')}")

            # Create read button and result display
            read_btn = ttk.Button(item_frame, text=self.get_label("read"), width=6,
                                command=lambda item=item: self.read_item(item))
            read_btn.grid(row=0, column=1, padx=2)
            #key = item.get('item' if self.current_language == 'EN' else '项目', '')
            key = item.get('index', '')
            self.item_read_buttons[key] = read_btn

            result_var = tk.StringVar(value=old_result_values.get(key, '')if old_result_values else '')
            result_entry = ttk.Entry(item_frame, textvariable=result_var,
                                   state='readonly', width=15)
            result_entry.grid(row=0, column=2, padx=2, sticky='ew')
            self.result_vars[key] = result_var

            # Create write button and input field if item is writable
            permission = item.get("permission", "R")

            # 只读项不显示写按钮和输入框
            if "W" in permission:
                write_btn = ttk.Button(item_frame, text=self.get_label("write"), width=6,
                                      command=lambda item=item: self.write_item(item))
                write_btn.grid(row=0, column=3, padx=2)
                self.item_write_buttons[key] = write_btn

                #only use write data when there is no old value 
                if old_input_values and key in old_input_values:
                    write_var = tk.StringVar(value=old_input_values[key])
                elif 'write data' in item:
                    write_var = tk.StringVar(value=str(item['write data']))
                else:
                    write_var = tk.StringVar(value='')
                write_entry = ttk.Entry(item_frame, textvariable=write_var, width=15)
                write_entry.grid(row=0, column=4, padx=2, sticky='ew')
                self.input_vars[key] = write_var

                # Create write status display
                write_status_var = tk.StringVar(value=old_write_status_values.get(key, '')if old_write_status_values else '')
                write_status_entry = ttk.Entry(item_frame, textvariable=write_status_var,
                                              state='readonly', width=15)
                write_status_entry.grid(row=0, column=5, padx=2, sticky='ew')
                self.write_status_vars[key] = write_status_var
            else:
                # 没有写权限时，写相关控件不显示
                self.item_write_buttons[key] = None
                self.input_vars[key] = None
                self.write_status_vars[key] = None

            return item_frame
            
        except Exception as e:
            error_msg = str(e)
            error_details = traceback.format_exc()
            with open('error_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"创建项目框架错误: {error_msg}\n")
                f.write("详细信息:\n")
                f.write(error_details)
            raise

    # 工具函数替换
    def create_tooltip(self, widget, text):
        utils.create_tooltip(widget, text)

    def format_bytes(self, data):
        return utils.format_bytes(data)

    def read_item(self, item):
        """Read value for a single item"""
        if not self.check_connection(show_dialog=True):
            return
        if not self.uart_service.is_mcu_connected():
            messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
            return
        addr_hex = item['index']
        def on_response(result, error=None):
            if error:
                if error == 'timeout':
                    self.result_vars[item['index']].set("timeout")
                    self.add_to_log(f"read {addr_hex} timeout")
                else:
                    self.result_vars[item['index']].set("err")
                    self.add_to_log(f"read {addr_hex} error: {error}")
            else:
                if result['status'] == 'success':
                    self.result_vars[item['index']].set(str(result['data']))
                elif result['status'] == 'error':
                    self.result_vars[item['index']].set(f"{result['status_code']:02X}")
                    self.add_to_log(f"read {addr_hex} status_code: {result['status_code']:02X}")
                else:
                    self.result_vars[item['index']].set("err")
                    self.add_to_log(f"read {addr_hex} unknown result: {result}")
        # 现在read_item是真正异步的，直接调用即可
        self.uart_service.read_item(item, on_response)

    def write_item(self, item):
        """Write value for a single item with type validation"""
        if not self.check_connection(show_dialog=True):
            return
        if not self.uart_service.is_mcu_connected():
            messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
            return
        
        addr_hex = item['index']
        if item['index'] not in self.input_vars:
            self.write_status_vars[item['index']].set("err")
            return
        
        value_str = self.input_vars[item['index']].get().strip()
        if not value_str:
            self.write_status_vars[item['index']].set("err")
            return
        
        # Get the data type for this item
        data_type = item.get('type', 'int32_t')
        
        # Validate the input value for this type
        check_value = validate_value_for_type(value_str, data_type)
        if check_value is None:
            self.write_status_vars[item['index']].set("Invalid type")
            self.add_to_log(f"[Write] {addr_hex} invalid '{value_str}' for {data_type} (decimal only for ints)")
            return       
        value = check_value;
        def on_response(result, error=None):
            if error:
                if error == 'timeout':
                    self.write_status_vars[item['index']].set("timeout")
                    self.add_to_log(f"write {addr_hex} timeout")
                else:
                    self.write_status_vars[item['index']].set("err")
                    self.add_to_log(f"write {addr_hex} error: {error}")
            else:
                if result['status'] == 'success':
                    self.write_status_vars[item['index']].set("Write OK")
                elif result['status'] == 'error':
                    self.write_status_vars[item['index']].set(f"{result['status_code']:02X}")
                    self.add_to_log(f"write {addr_hex} status_code: {result['status_code']:02X}")
                else:
                    self.write_status_vars[item['index']].set("err")
                    self.add_to_log(f"write {addr_hex} unknown result: {result}")
        
        # 现在write_item是真正异步的，直接调用即可
        self.uart_service.write_item(item, value, on_response)

    def create_widgets(self):
        try:
            # Create main frame with padding
            if self.is_embedded:
                # 嵌入模式：使用传入的父框架
                main_frame = self.main_frame
            else:
                # 独立模式：创建新的主框架
                main_frame = ttk.Frame(self.root, padding="5")
                main_frame.pack(fill=tk.BOTH, expand=True)
            self.main_frame.columnconfigure(0, weight=1) #列
            # 合理分配三行高度
            self.main_frame.rowconfigure(0, weight=0)  # 语言切换
            self.main_frame.rowconfigure(1, weight=0)  # 串口配置
            self.main_frame.rowconfigure(2, weight=0)  # 全局读写按钮
            self.main_frame.rowconfigure(3, weight=1)  # 模块/参数区
            self.main_frame.rowconfigure(4, weight=1)  # 日志区

            # 语言切换按钮（只在独立模式下显示）
            if not self.is_embedded:
                self.language_btn = ttk.Button(self.main_frame, text=self.get_label("language"),
                                             command=self.toggle_language, width=8)
                self.language_btn.grid(row=0, column=0, sticky='ne', pady=(0, 5))

            # 串口配置框
            self.serial_frame = ttk.LabelFrame(self.main_frame, text=self.get_label("serial_config"), padding="5")
            self.serial_frame.grid(row=1, column=0, sticky='ew', pady=(0, 5))
            for i in range(7):
                self.serial_frame.columnconfigure(i, weight=1)
            # ... 省略串口配置内容 ...
            # Row 1: Port and Baudrate
            self.port_label = ttk.Label(self.serial_frame, text=self.get_label("port"))
            self.port_label.grid(row=0, column=0, padx=5, pady=2)
            
            self.port_var = tk.StringVar(value=self.default_port)
            self.port_combo = ttk.Combobox(self.serial_frame, textvariable=self.port_var)
            self.port_combo.grid(row=0, column=1, padx=5, pady=2, sticky='ew')
            
            self.baudrate_label = ttk.Label(self.serial_frame, text=self.get_label("baudrate"))
            self.baudrate_label.grid(row=0, column=2, padx=5, pady=2)
            
            self.baud_var = tk.StringVar(value='115200')
            self.baud_combo = ttk.Combobox(self.serial_frame, textvariable=self.baud_var)
            self.baud_combo['values'] = ('9600', '19200', '38400', '57600', '115200')
            self.baud_combo.grid(row=0, column=3, padx=5, pady=2, sticky='ew')
            
            # Row 2: Data bits, Stop bits, Parity
            self.data_bits_label = ttk.Label(self.serial_frame, text=self.get_label("data_bits"))
            self.data_bits_label.grid(row=1, column=0, padx=5, pady=2)
            
            self.data_bits_var = tk.StringVar(value='8')
            self.data_bits_combo = ttk.Combobox(self.serial_frame, textvariable=self.data_bits_var)
            self.data_bits_combo['values'] = ('5', '6', '7', '8')
            self.data_bits_combo.grid(row=1, column=1, padx=5, pady=2, sticky='ew')
            
            self.stop_bits_label = ttk.Label(self.serial_frame, text=self.get_label("stop_bits"))
            self.stop_bits_label.grid(row=1, column=2, padx=5, pady=2)
            
            self.stop_bits_var = tk.StringVar(value='1')
            self.stop_bits_combo = ttk.Combobox(self.serial_frame, textvariable=self.stop_bits_var)
            self.stop_bits_combo['values'] = ('1', '1.5', '2')
            self.stop_bits_combo.grid(row=1, column=3, padx=5, pady=2, sticky='ew')
            
            self.parity_label = ttk.Label(self.serial_frame, text=self.get_label("parity"))
            self.parity_label.grid(row=1, column=4, padx=5, pady=2)
            
            self.parity_var = tk.StringVar(value='N')
            self.parity_combo = ttk.Combobox(self.serial_frame, textvariable=self.parity_var)
            self.parity_combo['values'] = ('N', 'E', 'O')
            self.parity_combo.grid(row=1, column=5, padx=5, pady=2, sticky='ew')
            
            # Connect button and status
            self.connect_btn = ttk.Button(self.serial_frame, text=self.get_label("connect"),
                                        command=self.toggle_connection)
            self.connect_btn.grid(row=0, column=4, rowspan=1, padx=5, pady=2, sticky='ew')

            self.status_label = ttk.Label(self.serial_frame, text=self.get_label("disconnected"),
                                        foreground="red")
            self.status_label.grid(row=0, column=5, rowspan=1, padx=5, pady=2)
            
            # Refresh port list button
            self.refresh_btn = ttk.Button(self.serial_frame, text=self.get_label("refresh"),
                                        command=self.refresh_ports)
            self.refresh_btn.grid(row=0, column=6, padx=5, pady=2, sticky='ew')

            # Create global Read All and Write All buttons frame
            global_btn_frame = ttk.Frame(self.main_frame)
            global_btn_frame.grid(row=2, column=0, sticky='e', pady=(0, 5))

            self.read_all_btn = ttk.Button(global_btn_frame, text=self.get_label("read_all"),
                                         command=self.read_all, width=12)
            self.read_all_btn.pack(side=tk.LEFT, padx=2)

            self.write_all_btn = ttk.Button(global_btn_frame, text=self.get_label("write_all"),
                                          command=self.write_all, width=12)
            self.write_all_btn.pack(side=tk.LEFT, padx=2)

            # 新增"upgrade mcu"按钮
            self.upgrade_btn = ttk.Button(global_btn_frame, text=self.get_label("upgrade_mcu"), command=self.upgrade_mcu, width=14)
            self.upgrade_btn.pack(side=tk.LEFT, padx=2)

            # 在升级按钮旁边加循环发送按钮
            self.loop_button = ttk.Button(global_btn_frame, text=self.get_label("cycle_send"), command=self.toggle_loop_send)
            self.loop_button.pack(side=tk.LEFT, padx=2)

            #f0 回复勾选框
            self.f0_response_var = tk.BooleanVar(value=True)
            self.f0_response_checkbox = ttk.Checkbutton(
                global_btn_frame, text=self.get_label("F0_response"), variable=self.f0_response_var
            )
            self.f0_response_checkbox.pack(side=tk.LEFT, padx=2)

            #40/50回复勾选框
            self.response_40_50_var = tk.BooleanVar(value=True)
            self.response_40_50_checkbox = ttk.Checkbutton(
                global_btn_frame, text=self.get_label("40/50_report"), variable=self.response_40_50_var
            )
            self.response_40_50_checkbox.pack(side=tk.LEFT, padx=2)


            # Create canvas and scrollbar for items
            canvas_frame = ttk.Frame(self.main_frame)
            canvas_frame.grid(row=3, column=0, columnspan=2, sticky='nsew')
            canvas_frame.grid_columnconfigure(0, weight=1)
            canvas_frame.grid_rowconfigure(0, weight=1)

            self.canvas = tk.Canvas(canvas_frame)
            scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
            self.scrollable_frame = ttk.Frame(self.canvas)

            self.scrollable_frame.bind(
                "<Configure>",
                lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            )

            # 创建画布窗口
            self.canvas_window = self.canvas.create_window(
                (0, 0),
                window=self.scrollable_frame,
                anchor="nw",
                width=self.canvas.winfo_width()  # 设置初始宽度
            )

            # 绑定画布大小变化事件 scrollable_frame
            self.canvas.bind('<Configure>', self.on_canvas_configure)
            
            # 配置画布和滚动条
            self.canvas.configure(yscrollcommand=scrollbar.set)
            self.canvas.grid(row=0, column=0, sticky='nsew')
            scrollbar.grid(row=0, column=1, sticky='ns')

            # 配置画布框架
            self.scrollable_frame.columnconfigure(0, weight=1)

            # 添加鼠标滚轮支持
            def _on_canvas_mousewheel(event):
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
            def _bind_canvas_mousewheel(event):
                self.canvas.bind_all("<MouseWheel>", _on_canvas_mousewheel)
            
            def _unbind_canvas_mousewheel(event):
                self.canvas.unbind_all("<MouseWheel>")
            
            self.canvas.bind('<Enter>', _bind_canvas_mousewheel)
            self.canvas.bind('<Leave>', _unbind_canvas_mousewheel)


            # Update communication log frame
            self.log_frame = ttk.LabelFrame(self.main_frame, text=self.get_label("communication_log"),
                                          padding="5")
            self.log_frame.grid(row=4, column=0, sticky='nsew', pady=(5, 0))
            self.log_frame.columnconfigure(0, weight=1)
            self.log_frame.rowconfigure(0, weight=1)

            # Create text widget for logging with scrollbar
            self.log_text = tk.Text(self.log_frame, height=6, wrap=tk.WORD)
            log_scrollbar = ttk.Scrollbar(self.log_frame, orient="vertical",
                                        command=self.log_text.yview)
            self.log_text.configure(yscrollcommand=log_scrollbar.set)
            
            self.log_text.grid(row=0, column=0, sticky='nsew')
            log_scrollbar.grid(row=0, column=1, sticky='ns')

            # Configure log text widget禁止输入
            self.log_text.configure(state='disabled')
            
            # 为日志文本框添加鼠标滚轮支持
            def _on_log_mousewheel(event):
                self.log_text.yview_scroll(int(-1*(event.delta/120)), "units")
            
            def _bind_log_mousewheel(event):
                self.log_text.bind_all("<MouseWheel>", _on_log_mousewheel)
            
            def _unbind_log_mousewheel(event):
                self.log_text.unbind_all("<MouseWheel>")
            
            self.log_text.bind('<Enter>', _bind_log_mousewheel)
            self.log_text.bind('<Leave>', _unbind_log_mousewheel)

            # Add clear log button
            self.clear_log_btn = ttk.Button(self.log_frame, text=self.get_label("clear_log"),
                                          command=self.clear_log)
            self.clear_log_btn.grid(row=1, column=0, columnspan=2, pady=(5,0))
            
            # Save Log checkbox
            self.save_log_var = tk.BooleanVar(value=False)
            self.save_log_checkbox = ttk.Checkbutton(
                self.log_frame, text=self.get_label("save_log"), variable=self.save_log_var, command=self.on_save_log_toggle
            )
            self.save_log_checkbox.grid(row=2, column=0, sticky='w', padx=5, pady=(0, 5))

            self.log_file_path = None  # 保存日志文件路径
            
            # Initialize port list
            self.refresh_ports()
            
        except Exception as e:
            error_msg = str(e)
            error_details = traceback.format_exc()
            with open('error_log.txt', 'w', encoding='utf-8') as f:
                f.write(f"创建界面错误: {error_msg}\n")
                f.write("详细信息:\n")
                f.write(error_details)
            raise


    def on_canvas_configure(self, event):
        """处理画布大小变化事件"""
        try:
            # 更新滚动区域
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
            
            # 更新画布窗口宽度以匹配画布
            if hasattr(self, 'canvas_window'):
                self.canvas.itemconfig(self.canvas_window, width=event.width)
                
        except Exception as e:
            # 记录错误但不抛出以防止崩溃
            with open('error_log.txt', 'a', encoding='utf-8') as f:
                f.write(f"\n窗口调整错误: {str(e)}\n")
                f.write(traceback.format_exc())
    
    def force_refresh_display(self):
        """强制刷新显示，解决标签页切换后控件不显示的问题"""
        try:
            # 强制更新画布
            if hasattr(self, 'canvas'):
                self.canvas.update_idletasks()
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                
            # 强制更新滚动框架
            if hasattr(self, 'scrollable_frame'):
                self.scrollable_frame.update_idletasks()
                
            # 强制更新主框架
            if hasattr(self, 'main_frame'):
                self.main_frame.update_idletasks()
                
            # 递归更新所有子控件
            self.recursive_update_widgets(self.main_frame)
            
        except Exception as e:
            print(f"Force refresh display error: {e}")
    
    def recursive_update_widgets(self, widget):
        """递归更新所有子控件"""
        try:
            # 更新当前控件
            widget.update_idletasks()
            
            # 递归更新所有子控件
            for child in widget.winfo_children():
                self.recursive_update_widgets(child)
                
        except Exception as e:
            # 忽略更新错误，避免影响其他控件
            pass

    def refresh_ports(self):
        """Refresh the available serial ports list"""
        ports = UARTInterface.list_ports()
        self.port_combo['values'] = ports
        if ports and not self.port_var.get() in ports:
            self.port_var.set(ports[0])
    
    def set_connection_controls_state(self, enabled):
        """设置连接配置控件的启用/禁用状态"""
        state = 'normal' if enabled else 'disabled'
        self.port_combo.config(state=state)
        self.baud_combo.config(state=state)
        self.data_bits_combo.config(state=state)
        self.stop_bits_combo.config(state=state)
        self.parity_combo.config(state=state)
        self.refresh_btn.config(state=state)

    def toggle_connection(self):
        """Toggle serial port connection with enhanced error handling"""
        if not self.uart.is_open():
            try:
                # Check if port is selected
                port = self.port_var.get()
                if not port:
                    messagebox.showwarning("Warning", "Please select a serial port")
                    return
                
                # 直接打开串口，不设置连接超时（因为需要与MCU握手通信）
                self.uart.open(
                    port=port,
                    baudrate=int(self.baud_var.get()),
                    bytesize=int(self.data_bits_var.get()),
                    stopbits=float(self.stop_bits_var.get()),
                    parity=self.parity_var.get(),
                    timeout=1
                )
                
                # 串口打开成功，更新UI
                self.status_label.config(text="Connected", foreground="green")
                self.connect_btn.config(text="Disconnect")
                self.set_connection_controls_state(False)
                
                self.baud_var.set(self.baud_var.get())
                # Start listener and handshake via uart_service
                # 这里启动监听和握手，握手有自己的超时机制
                self.uart_service.start_listener()
                self.uart_service.start_e0_handshake()

                # 启动一个 watcher，在握手结束后更新 UI 状态
                self.watch_handshake_status()
                        
            except serial.SerialException as e:
                error_msg = str(e)
                if "PermissionError" in error_msg or "访问被拒绝" in error_msg:
                    messagebox.showerror("Error", f"Cannot open port, it may be in use by another application\n{port}")
                elif "FileNotFoundError" in error_msg or "找不到" in error_msg:
                    messagebox.showerror("Error", f"Port not found\n{port}\n\nPlease check connection and refresh port list.")
                elif "句柄无效" in error_msg or "ClearCommError" in error_msg:
                    messagebox.showerror("Error", f"Serial port handle invalid\n{port}\n\nDevice may have been disconnected.")
                else:
                    messagebox.showerror("Error", f"Failed to connect:\n{error_msg}")
            except Exception as e:
                messagebox.showerror("Error", f"Connection error:\n{str(e)}")
        else:
            # 异步断开，避免阻塞UI
            self._async_disconnect()

    def watch_handshake_status(self, timeout_s=10.0, interval_ms=200):
        """在连接后监测握手是否成功，用于刷新 status_label。

        之前 UI 只要串口 open 就显示 Connected，但 MCU 握手失败时也会显示 Connected，
        造成误导。
        """
        start_t = time.time()

        def _poll():
            # 串口断开了就停止
            if not self.uart.is_open():
                return

            if self.uart_service.is_mcu_connected():
                # 握手成功
                try:
                    self.status_label.config(text="Connected", foreground="green")
                except Exception:
                    pass
                return

            # 超时仍未握手成功
            if time.time() - start_t >= timeout_s:
                try:
                    self.status_label.config(text="Handshake Failed", foreground="red")
                except Exception:
                    pass
                return

            # 继续轮询
            try:
                if self.is_embedded and self.parent_frame:
                    self.parent_frame.winfo_toplevel().after(interval_ms, _poll)
                elif self.root:
                    self.root.after(interval_ms, _poll)
            except Exception:
                pass

        _poll()

    def _async_disconnect(self):
        """异步断开串口连接，避免UI卡顿"""
        # 立即更新UI状态，给用户反馈
        self.status_label.config(text="Disconnecting...", foreground="orange")
        self.connect_btn.config(text="Disconnecting...", state='disabled')
        
        def disconnect_worker():
            disconnect_success = False
            try:
                # 设置强制超时机制
                import threading
                import time
                
                stop_event = threading.Event()
                error_msg = None
                
                def forced_disconnect():
                    nonlocal error_msg, disconnect_success
                    try:
                        # 首先尝试优雅关闭
                        if hasattr(self, 'uart_service') and self.uart_service:
                            self.uart_service.stop_listener()
                        
                        # 强制关闭串口
                        if hasattr(self, 'uart') and self.uart:
                            if self.uart.is_open():
                                try:
                                    # 清空缓冲区
                                    self.uart.reset_input_buffer()
                                    self.uart.reset_output_buffer()
                                except:
                                    pass
                                # 关闭串口
                                self.uart.close()
                        disconnect_success = True
                    except Exception as e:
                        error_msg = str(e)
                    finally:
                        stop_event.set()
                
                # 在独立线程中执行断开操作
                disconnect_thread = threading.Thread(target=forced_disconnect, daemon=True)
                disconnect_thread.start()
                
                # 等待操作完成，最多3秒
                if not stop_event.wait(timeout=3.0):
                    error_msg = "Disconnect operation timed out (3s)"
                
                # 断开完成后更新UI（必须在主线程中执行）
                def update_ui():
                    if disconnect_success and not error_msg:
                        self.status_label.config(text="Disconnected", foreground="red")
                        self.connect_btn.config(text="Connect", state='normal')
                        self.set_connection_controls_state(True)
                        self.add_to_log("Serial port disconnected successfully")
                    else:
                        self.status_label.config(text="Disconnect Error", foreground="red")
                        self.connect_btn.config(text="Connect", state='normal')
                        self.set_connection_controls_state(True)
                        self.add_to_log(f"Disconnect error: {error_msg or 'Unknown error'}")
                
                # 使用after方法在主线程中更新UI - 添加异常处理
                if self.is_embedded and self.parent_frame:
                    try:
                        self.parent_frame.winfo_toplevel().after(0, update_ui)
                    except Exception as e:
                        print(f"Failed to schedule UI update: {e}")
                        update_ui()  # 直接执行
                elif self.root:
                    try:
                        self.root.after(0, update_ui)
                    except Exception as e:
                        print(f"Failed to schedule UI update: {e}")
                        update_ui()  # 直接执行
                else:
                    update_ui()
                    
            except Exception as e:
                # 错误处理也要在主线程中执行
                def show_error():
                    self.status_label.config(text="Disconnect Error", foreground="red")
                    self.connect_btn.config(text="Connect", state='normal')
                    self.set_connection_controls_state(True)
                    messagebox.showerror("Error", f"Error disconnecting:\n{str(e)}")
                
                if self.is_embedded and self.parent_frame:
                    try:
                        self.parent_frame.winfo_toplevel().after(0, show_error)
                    except Exception as e:
                        print(f"Failed to schedule error display: {e}")
                        show_error()  # 直接执行
                elif self.root:
                    try:
                        self.root.after(0, show_error)
                    except Exception as e:
                        print(f"Failed to schedule error display: {e}")
                        show_error()  # 直接执行
                else:
                    show_error()
        
        # 在后台线程中执行断开操作
        threading.Thread(target=disconnect_worker, daemon=True).start()

    def create_module_header(self, module, content_frame):
        # Create header frame
        header_frame = ttk.Frame(content_frame, style="ModuleHeader.TFrame")
        header_frame.grid(row=0, column=0, sticky='ew')
        header_frame.columnconfigure(1, weight=1)
        
        # Create expand/collapse button
        button_text = "[-]" if self.module_states.get(module, True) else "[+]"
        button = ttk.Button(header_frame, text=button_text, width=3)
        button.configure(command=lambda m=module, b=button: self.toggle_module(m, b))
        button.grid(row=0, column=0, padx=5, pady=2)
        
        # Create module label (without "Module:" prefix)
        module_label = ttk.Label(header_frame, text=module)
        module_label.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        self.module_labels[module] = module_label
        
        # Create module-level Read All and Write All buttons
        read_btn = ttk.Button(header_frame, text=self.get_label("read_all"),
                            command=lambda m=module: self.read_module(m), width=12)
        read_btn.grid(row=0, column=2, padx=2, pady=2)
        self.module_read_buttons[module] = read_btn
        
        write_btn = ttk.Button(header_frame, text=self.get_label("write_all"),
                             command=lambda m=module: self.write_module(m), width=12)
        write_btn.grid(row=0, column=3, padx=2, pady=2)
        self.module_write_buttons[module] = write_btn
        
        return header_frame

    def create_submodule_header(self, module, submodule, content_frame):
        # Create header frame
        header_frame = ttk.Frame(content_frame, style="SubmoduleHeader.TFrame")
        header_frame.grid(row=0, column=0, sticky='ew')
        header_frame.columnconfigure(1, weight=1)
        
        # Create expand/collapse button
        button_text = "[-]" if self.submodule_states.get(f"{module}_{submodule}", True) else "[+]"
        button = ttk.Button(header_frame, text=button_text, width=3)
        button.configure(command=lambda m=module, s=submodule, b=button: self.toggle_submodule(m, s, b))
        button.grid(row=0, column=0, padx=(20, 5), pady=2)
        
        # Create submodule label (without "Submodule:" prefix)
        submodule_label = ttk.Label(header_frame, text=submodule)
        submodule_label.grid(row=0, column=1, sticky='w', padx=5, pady=2)
        self.submodule_labels[f"{module}_{submodule}"] = submodule_label
        
        # Create submodule-level Read All and Write All buttons
        read_btn = ttk.Button(header_frame, text=self.get_label("read_all"),
                            command=lambda m=module, s=submodule: self.read_submodule(m, s), width=12)
        read_btn.grid(row=0, column=2, padx=2, pady=2)
        self.submodule_read_buttons[f"{module}_{submodule}"] = read_btn
        
        write_btn = ttk.Button(header_frame, text=self.get_label("write_all"),
                             command=lambda m=module, s=submodule: self.write_submodule(m, s), width=12)
        write_btn.grid(row=0, column=3, padx=2, pady=2)
        self.submodule_write_buttons[f"{module}_{submodule}"] = write_btn
        
        return header_frame

    def check_connection(self, *, show_dialog=True):
        """Check if serial port is connected.

        Tk 的 messagebox 在某些场景（比如窗口关闭中/焦点异常/重复触发）可能表现为
        "弹窗关不掉"。因此这里允许调用方选择不弹窗，只返回 False。
        """
        if not self.uart.is_open():
            if show_dialog:
                try:
                    # 让弹窗属于当前窗口，避免焦点/模态异常导致看起来“关不掉”
                    parent = self.root if (hasattr(self, 'root') and self.root) else self.main_frame.winfo_toplevel()
                    messagebox.showwarning(
                        "Warning",
                        "Serial port not connected. Please connect first!",
                        parent=parent
                    )
                except Exception:
                    # 如果 parent 获取失败，回退到默认弹窗
                    messagebox.showwarning("Warning", "Serial port not connected. Please connect first!")
            return False
        return True

    def read_all(self):
        """Read all items (bulk).

        注意：read_item() 内部也会做握手检查并弹窗。
        批量读取时如果未握手成功，逐个 item 弹窗会导致“弹窗关不掉/一直弹”。
        因此这里在开始前做一次统一检查，失败则只提示一次并直接返回。
        """
        if not self.check_connection(show_dialog=True):
            return

        if not self.uart_service.is_mcu_connected():
            try:
                parent = self.root if (hasattr(self, 'root') and self.root) else self.main_frame.winfo_toplevel()
                messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.", parent=parent)
            except Exception:
                messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
            return

        print("=== Reading All Items ===")
        for module in self.organized_items.values():
            for submodule in module.values():
                for item in submodule:
                    # 这里直接调 uart_service，避免 read_item() 再次弹窗
                    def _cb(_result, _error=None):
                        pass
                    self.uart_service.read_item(item, _cb)
    
    def write_all(self):
        """Write all writable items (bulk).

        与 read_all 同理：如果未握手成功，逐个 item 调用 write_item() 会导致连环弹窗。
        这里改为开始前统一检查，失败只弹一次并返回。
        """
        if not self.check_connection(show_dialog=True):
            return

        if not self.uart_service.is_mcu_connected():
            try:
                parent = self.root if (hasattr(self, 'root') and self.root) else self.main_frame.winfo_toplevel()
                messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.", parent=parent)
            except Exception:
                messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
            return

        print("=== Writing All Writable Items ===")
        for module in self.organized_items.values():
            for submodule in module.values():
                for item in submodule:
                    if "W" in item.get("permission", ""):
                        # 直接调 uart_service，避免 write_item() 再次弹窗
                        key = item.get('index', '')
                        value = None
                        try:
                            if key in self.input_vars and self.input_vars[key] is not None:
                                value_str = self.input_vars[key].get().strip()
                                if value_str != '':
                                    # 复用原有类型校验
                                    data_type = item.get('type', 'int32_t')
                                    value = validate_value_for_type(value_str, data_type)
                        except Exception:
                            value = None

                        if value is None:
                            # 没有可写值/类型非法就跳过，避免批量写卡住
                            continue

                        def _cb(_result, _error=None):
                            pass
                        self.uart_service.write_item(item, value, _cb)
    
    def _warn_not_connected_once(self, msg: str):
        """统一的 warning 弹窗（带 parent），用于批量操作的单次提示。"""
        try:
            parent = self.root if (hasattr(self, 'root') and self.root) else self.main_frame.winfo_toplevel()
            messagebox.showwarning("Warning", msg, parent=parent)
        except Exception:
            messagebox.showwarning("Warning", msg)

    def _bulk_read_items(self, items, title: str = ""):
        if not self.check_connection(show_dialog=True):
            return
        if not self.uart_service.is_mcu_connected():
            self._warn_not_connected_once("MCU not connected. Please wait for handshake.")
            return
        if title:
            print(title)
        for item in items:
            def _cb(_result, _error=None):
                pass
            self.uart_service.read_item(item, _cb)

    def _bulk_write_items(self, items, title: str = ""):
        if not self.check_connection(show_dialog=True):
            return
        if not self.uart_service.is_mcu_connected():
            self._warn_not_connected_once("MCU not connected. Please wait for handshake.")
            return
        if title:
            print(title)
        for item in items:
            if "W" not in item.get("permission", ""):
                continue
            key = item.get('index', '')
            value = None
            try:
                if key in self.input_vars and self.input_vars[key] is not None:
                    value_str = self.input_vars[key].get().strip()
                    if value_str != '':
                        data_type = item.get('type', 'int32_t')
                        value = validate_value_for_type(value_str, data_type)
            except Exception:
                value = None
            if value is None:
                continue
            def _cb(_result, _error=None):
                pass
            self.uart_service.write_item(item, value, _cb)

    def read_module(self, module):
        """Read all items in a module (bulk, no repeated dialogs)."""
        items = []
        for submodule in self.organized_items.get(module, {}).values():
            items.extend(list(submodule))
        self._bulk_read_items(items, title=f"=== Reading All Items in Module: {module} ===")

    def write_module(self, module):
        """Write all writable items in a module (bulk, no repeated dialogs)."""
        items = []
        for submodule in self.organized_items.get(module, {}).values():
            items.extend(list(submodule))
        self._bulk_write_items(items, title=f"=== Writing All Items in Module: {module} ===")

    def read_submodule(self, module, submodule):
        """Read all items in a submodule (bulk, no repeated dialogs)."""
        items = list(self.organized_items.get(module, {}).get(submodule, []))
        self._bulk_read_items(items, title=f"=== Reading All Items in Submodule: {submodule} ===")

    def write_submodule(self, module, submodule):
        """Write all writable items in a submodule (bulk, no repeated dialogs)."""
        items = list(self.organized_items.get(module, {}).get(submodule, []))
        self._bulk_write_items(items, title=f"=== Writing All Items in Submodule: {submodule} ===")

    def toggle_module(self, module, button):
        """Toggle module expansion state"""
        try:
            if self.module_states[module]:  # Currently expanded
                button.configure(text="[+]")
                self.module_states[module] = False
                if module in self.module_frames:
                    self.module_frames[module].grid_remove()
            else:  # Currently collapsed
                button.configure(text="[-]")
                self.module_states[module] = True
                if module in self.module_frames:
                    self.module_frames[module].grid()
        except Exception as e:
            print(f"Error in toggle_module: {e}")

    def toggle_submodule(self, module, submodule, button):
        """Toggle submodule expansion state"""
        try:
            state_key = f"{module}_{submodule}"
            if self.submodule_states.get(state_key, True):  # Currently expanded
                button.configure(text="[+]")
                self.submodule_states[state_key] = False
                if (module, submodule) in self.submodule_frames:
                    self.submodule_frames[(module, submodule)].grid_remove()
            else:  # Currently collapsed
                button.configure(text="[-]")
                self.submodule_states[state_key] = True
                if (module, submodule) in self.submodule_frames:
                    self.submodule_frames[(module, submodule)].grid()
        except Exception as e:
            print(f"Error in toggle_submodule: {e}")
    def toggle_loop_send(self):
        if not self.loop_running:
            # 检查串口连接
            if not self.check_connection():
                messagebox.showwarning("Warning", "Please connect serial port first!")
                return
            if not self.uart_service.is_mcu_connected():
                messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
                return
            self.loop_running = True
            self.loop_button.config(text="stop send")
            threading.Thread(target=self.loop_send_items, daemon=True).start()
        else:
            self.loop_running = False
            self.loop_button.config(text="cycle send")

    def loop_send_items(self):
        """循环发送 - 真正的异步，不阻塞"""
        def process_next_item(item_index=0):
            if not self.loop_running or item_index >= len(self.items):
                # 一轮完成，等待后开始下一轮
                if self.loop_running:
                    # 延时后开始下一轮
                    def start_next_round():
                        if self.loop_running:
                            process_next_item(0)
                    
                    if self.is_embedded and self.parent_frame:
                        try:
                            delay_ms = int(RECYCLE_TIME * 1000)
                            if delay_ms > 0:  # 确保延迟时间有效
                                self.parent_frame.winfo_toplevel().after(delay_ms, start_next_round)
                            else:
                                start_next_round()  # 立即执行
                        except (ValueError, TypeError):
                            start_next_round()  # 出错时立即执行
                    elif self.root:
                        try:
                            delay_ms = int(RECYCLE_TIME * 1000)
                            if delay_ms > 0:  # 确保延迟时间有效
                                self.root.after(delay_ms, start_next_round)
                            else:
                                start_next_round()  # 立即执行
                        except (ValueError, TypeError):
                            start_next_round()  # 出错时立即执行
                return
            
            if not self.check_connection():
                self.add_to_log("串口未连接，循环发送已停止。")
                self.loop_running = False
                self.loop_button.config(text="cycle send")
                return
                
            if not self.uart_service.is_mcu_connected():
                self.add_to_log("MCU not connected. Please wait for handshake.")
                self.loop_running = False
                self.loop_button.config(text="cycle send")
                return
            
            item = self.items[item_index]
            permission = item.get('permission', '')
            
            # 先读取
            def on_read_complete(result, error=None):
                if error:
                    self.result_vars[item['index']].set("timeout")
                    self.add_to_log(f"Read {item.get('name', item.get('index'))} timeout")
                
                # 如果有写权限，则写入
                if permission == 'W' and self.loop_running:
                    value = 0
                    addr_hex = f"0x{int(str(item['index']), 16):04X}"
                    if addr_hex in self.input_vars:
                        try:
                            value = int(self.input_vars[addr_hex].get())
                        except Exception:
                            value = 0
                    
                    def on_write_complete(result, error=None):
                        if error:
                            self.write_status_vars[item['index']].set("timeout")
                            self.add_to_log(f"Write {item.get('name', item.get('index'))} timeout")
                        
                        # 处理下一个项目
                        process_next_item(item_index + 1)
                    
                    self.uart_service.write_item(item, value, on_write_complete)
                else:
                    # 没有写权限，直接处理下一个项目
                    process_next_item(item_index + 1)
            
            self.uart_service.read_item(item, on_read_complete)
        
        # 开始第一轮
        process_next_item(0)
    def __del__(self):
        try:
            if hasattr(self, 'uart_service') and self.uart_service:
                self.uart_service.stop_listener()
            if hasattr(self, 'uart') and self.uart and self.uart.is_open():
                self.uart.close()
        except Exception:
            pass

    def clear_log(self):
        """Clear the communication log"""
        self.log_manager.clear_log()

    def add_to_log(self, message):
        self.log_manager.add_log(message)

    def format_bytes(self, data):
        return utils.format_bytes(data)

    def on_save_log_toggle(self):
        if self.save_log_var.get():
            # 勾选时弹出文件保存对话框
            file_path = filedialog.asksaveasfilename(
                title="Select Log File",
                defaultextension=".txt",
                filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                initialfile=f"UART_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if file_path:
                self.log_manager.set_log_file_path(file_path)
                # 立即保存当前log内容到文件
                self.save_current_log_to_file()
            else:
                # 用户取消选择，取消勾选
                self.save_log_var.set(False)
                self.log_manager.set_log_file_path(None)
        else:
            # 取消勾选时，清除路径
            self.log_manager.set_log_file_path(None)

    def save_current_log_to_file(self):
        log_content = self.log_text.get("1.0", tk.END)
        self.log_manager.save_current_log_to_file(log_content)

    def upgrade_mcu(self):
        if not self.check_connection(show_dialog=True):
            return
        if not self.uart_service.is_mcu_connected():
            messagebox.showwarning("Warning", "MCU not connected. Please wait for handshake.")
            return
        file_path = filedialog.askopenfilename(
            title="Select MCU Upgrade .bin File",
            filetypes=[("BIN Files", "*.bin"), ("All Files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'rb') as f:
                bin_data = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read bin file:\n{e}")
            return
        def on_progress(current, total):
            self.add_to_log(f"Upgrade progress: {current}/{total}")
        def do_upgrade():
            success, msg = self.uart_service.upgrade_mcu(bin_data, progress_callback=on_progress)
            if success:
                messagebox.showinfo("Upgrade", msg)
            else:
                messagebox.showerror("Upgrade Error", msg)
        threading.Thread(target=do_upgrade, daemon=True).start()

    def _log_callback(self, message):
        """日志回调函数 - 线程安全版本，支持批量处理和标签页感知"""
        # 初始化日志队列（如果不存在）
        if not hasattr(self, '_log_queue'):
            self._log_queue = queue.Queue()
            self._log_timer = None     
        # 将日志添加到队列
        try:
            self._log_queue.put(message, block=False)
        except queue.Full:
            pass  # 如果队列满了，丢弃日志避免阻塞
        
        # 启动批量处理定时器
        self._schedule_log_batch_update()
    
    def _schedule_log_batch_update(self):
        """调度批量日志更新"""
        if hasattr(self, '_log_timer') and self._log_timer is not None:
            return  # 已经有定时器在运行
        
        # 使用after方法确保在主线程中执行
        try:
            if self.is_embedded and self.parent_frame:
                self._log_timer = self.parent_frame.winfo_toplevel().after(200, self._process_log_batch)
            elif self.root:
                self._log_timer = self.root.after(200, self._process_log_batch)
        except Exception:
            # 如果调度失败，直接处理
            self._process_log_batch()
    
    def _process_log_batch(self):
        """批量处理日志更新 - 在主线程中执行"""
        try:
            # 重置定时器
            if hasattr(self, '_log_timer'):
                self._log_timer = None
            
            # 收集所有待处理的日志
            log_entries = []
            clear_requested = False
            
            while True:
                try:
                    message = self._log_queue.get_nowait()
                    if message == "__CLEAR__":
                        clear_requested = True
                        log_entries.clear()  # 清空之前的日志
                    else:
                        log_entries.append(message)
                    
                    if len(log_entries) >= 50:  # 限制批量大小
                        break
                except queue.Empty:
                    break
            
            # 批量更新UI（只在主线程中执行）
            try:
                self.log_text.configure(state='normal')
                
                if clear_requested:
                    self.log_text.delete(1.0, tk.END)
                
                if log_entries:
                    combined_text = '\n'.join(log_entries) + '\n'
                    self.log_text.insert(tk.END, combined_text)
                    self.log_text.see(tk.END)
                
                self.log_text.configure(state='disabled')
                
            except Exception as e:
                print(f"Log batch UI update error: {e}")
            
            # 如果还有更多日志，继续调度
            if not self._log_queue.empty():
                self._schedule_log_batch_update()
                
        except Exception as e:
            print(f"Log batch processing error: {e}")
            # 重置状态
            if hasattr(self, '_log_timer'):
                self._log_timer = None
            # 如果都没有，直接处理剩余日志
            self._process_log_batch()

    def update_item_display(self, addr, value):     
        # addr 是 int 类型，转成 0xXXXX 格式字符串
        addr_hex = f"0x{addr:04X}"
        if addr_hex in self.result_vars:
            self.result_vars[addr_hex].set(str(value))
        else:
            pass

if __name__ == "__main__":
    # 独立运行模式
    app = UARTTestGUI()
    app.root.mainloop()

def create_embedded_instance(parent_frame):
    """创建嵌入模式的实例，用于统一工具管理器"""
    return UARTTestGUI(parent_frame) 
