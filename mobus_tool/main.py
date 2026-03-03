#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SunSpec Modbus协议上位机主程序
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import os
import queue
from mobus_tool.sunspec_protocol import SunSpecProtocol
from mobus_tool.modbus_client import ModbusClient
from mobus_tool.gui_components import ConnectionFrame, DataTableFrame, OverviewFrame
from mobus_tool.language_manager import LanguageManager
#from mobus_tool.excel_recorder import ExcelHistoryRecorder

class SunSpecGUI:
    """SunSpec协议GUI界面"""
    
    def __init__(self, parent_frame=None, status_var=None, initial_language=None):
        """初始化Modbus工具"""
        # 基本属性
        self.parent_frame = parent_frame
        self.is_embedded = parent_frame is not None
        self.status_var = status_var
        self.language_manager = LanguageManager()
        # 如果指定了初始语言，立即设置
        if initial_language:
            self.language_manager.set_language(initial_language)
        
        # 初始化窗口
        self._init_window()
        
        # 核心组件
        self.modbus_client = ModbusClient()
        self.sunspec_protocol = SunSpecProtocol()
        
        # # Excel历史记录器（不指定路径，启用时自动生成）
        # self.excel_recorder = ExcelHistoryRecorder(None)
        
        # 状态管理
        self.is_scan_base_addr = False
        self.is_scan_model_addr = False
        self.user_initiated_disconnect = False
        self._auto_read_all_running = False
        self._auto_read_stop_reason = "user"
        
        # UI活跃状态控制
        self._ui_active = True  # 默认为活跃状态
        
        # 线程管理
        self._init_threads()
        
        # 添加线程同步锁
        self._auto_read_lock = threading.Lock()
        # self._ui_reset_lock = threading.RLock()  # Use RLock to prevent deadlocks on the main thread
        # self._ui_resetting = False  # Flag to prevent UI updates during reset
        
        # Overview数据定时打印功能（独立线程）
        self._overview_log_enabled = True  # 启用Overview数据定时打印功能
        self._overview_log_interval = 2  # 默认2秒一次
        self._last_overview_log_time = 0  # 上次打印时间
        self._overview_log_running = False
        self._overview_log_thread = None
        
        # UI初始化
        self.setup_gui()
        self.bind_events()
        
    def _init_window(self):
        """初始化窗口"""
        if not self.is_embedded:
            try:
                self.root = tk.Tk()
                self.root.title(self.language_manager.get_text("window_title"))
                
                # 设置窗口大小和位置
                window_width, window_height = 1400, 900
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                x = (screen_width - window_width) // 2
                y = (screen_height - window_height) // 2
                self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

                self.set_window_icon()
                self.main_frame = ttk.Frame(self.root)
                self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                print("Window created successfully")
            except Exception as e:
                print(f"Failed to create the menu window: {e}")
                print(f"Error type: {type(e).__name__}")
                print(f"Tkinter available: {tk.TkVersion}")
                raise e
        else:
            self.root = None
            self.main_frame = self.parent_frame
            
    def _init_threads(self):
        """初始化线程管理 - 恢复为合理的三线程架构"""
        # 通信线程：负责串行的读取->接收->发送给解析线程
        self.comm_thread = None
        self.comm_queue = queue.Queue()
        self.comm_thread_running = False
        
        # 解析线程：独立处理数据解析和UI更新
        self.parse_thread = None
        self.parse_queue = queue.Queue()
        self.parse_thread_running = False
        
        # 操作结果队列
        self.result_queue = queue.Queue()
        self.operation_timeout = 10.0
        
        # 启动线程
        self.start_communication_thread()
        self.start_parse_thread()
        self.start_result_processor()
        
    # 统一的UI更新和错误处理辅助方法          
    def notify(self, level, title, message, log=True):
        """统一的日志+弹窗通知"""
        if log:
            self.log_message(f"[{level.upper()}] {title}: {message}")
        
        if getattr(self, 'user_initiated_disconnect', False):
            return
            
        if level == "error":
            parent = None
            try:
                if self.is_embedded and self.parent_frame:
                    parent = self.parent_frame.winfo_toplevel()
                elif not self.is_embedded and self.root:
                    parent = self.root
            except Exception:
                parent = None

            if level == "error":
                messagebox.showerror(title, message, parent=parent)
            elif level == "warning":
                messagebox.showwarning(title, message, parent=parent)
            elif level == "info":
                messagebox.showinfo(title, message, parent=parent)
                    
    def _stop_auto_read(self, reason="user", message=""):
        """统一停止自动读取，同时停止Overview定时打印线程"""
        with self._auto_read_lock:
            self._auto_read_stop_reason = reason
            self._auto_read_all_running = False
        
        # 停止Overview打印线程
        self._stop_overview_log_thread()
        
        # 在主线程中更新UI
        if not self.is_embedded and self.root:
            self.root.after_idle(self._update_auto_read_ui)
        elif self.is_embedded and self.parent_frame:
            self.parent_frame.winfo_toplevel().after_idle(self._update_auto_read_ui)
        else:
            self._update_auto_read_ui()
            
        if reason == "error" and message:
            self.log_message(f"Auto read stopped due to error: {message}")
            
    def _cancel_all_operations(self):
        """立即取消所有正在进行的操作"""
        # 停止自动读取
        self._auto_read_all_running = False
        
        # 如果有正在进行的Modbus通信，通过清理缓冲区来中断
        if hasattr(self, 'modbus_client') and self.modbus_client.is_connected():
            try:
                # 清理串口缓冲区，中断正在进行的通信
                if self.modbus_client.ser and self.modbus_client.ser.is_open:
                    self.modbus_client.ser.reset_input_buffer()
                    self.modbus_client.ser.reset_output_buffer()
            except Exception:
                pass  # 忽略清理过程中的错误
    
    def _update_auto_read_ui(self):
        """更新自动读取UI状态"""
        self.auto_read_all_var.set(False)
        if self._auto_read_stop_reason == "error":
            self.notify("warning", "Auto Read Stopped", "Auto read has been stopped due to communication timeout or connection loss.",log=False)
                             
    def scan_base_address(self):
        """扫描SunSpec协议基地址"""
        if not self.modbus_client.is_connected():
            self.log_message("Please connect to the device first")
            return
        
        self.log_message(self.language_manager.get_text("start_scanning_base"))
        
        def on_scan_result(result, error):
            if error:
                self.base_addr_var.set(self.language_manager.get_text("scan_failed"))
                self.log_message(f"Base address scan error: {error}")
                self.log_message("Base address scan failed")
                return
            
            if result["success"]:
                addr = result["base_address"]
                self.sunspec_protocol.base_address = addr
                self.base_addr_var.set(str(addr))
                self.log_message(f"Found SunSpec base address: {addr}")
                self.is_scan_base_addr = True             
                self.log_message(f"SunSpec base address found: {addr}")
                
                # 自动流程：找到基地址后自动扫描模型
                self.log_message("SunSpec base address found, starting to scan models...")
                self.scan_models()
            else:
                self.base_addr_var.set(self.language_manager.get_text("scan_failed"))
                error_msg = self.language_manager.get_text("not_found_sunspec_base")
                
                if result.get("error") == "timeout":
                    error_msg += f"\n\n{result.get('message', 'Communication timeout')}"
                elif result.get("timeout_count") == 3:
                    error_msg += f"\n\nAll addresses timed out. Please check:\n1. Serial port connection\n2. Device power\n3. Baud rate settings\n4. Slave ID settings"
                    self.log_message("All scan attempts timed out - possible connection issues")
                else:
                    self.log_message(self.language_manager.get_text("not_found_sunspec_base"))
                
                self.log_message("Base address scan completed - not found")
        
        self._execute_operation("scan_base_address", None, on_scan_result, timeout=30.0)

    def scan_models(self):
        """扫描所有SunSpec模型，找到802/805/899的起始地址"""
        if not self.modbus_client.is_connected():
            self.log_message("Please connect to the device first")
            return
        if self.is_scan_base_addr == False:
            self.log_message("Please scan the base address first")
            return
        def on_scan_models_result(result, error):
            if error:
                self.log_message(f"Model scan error: {error}")
                return
            if result["success"]:
                model_map = result["model_map"]
                self.model_lengths = result.get("model_lengths", {})
                self.model_base_addrs = model_map
                self.is_scan_model_addr = True
                self.log_message(f"{self.language_manager.get_text('scan_complete')}, found models: {list(model_map.keys())}")
                
                # 设置协议中的模型地址并预计算重复组信息
                for model_id, addr in model_map.items():
                    self.sunspec_protocol.set_model_base_address(model_id, addr)
                    # 使用扫描到的长度预计算重复组信息
                    model_length = self.model_lengths.get(model_id)
                    if model_length:
                        self.sunspec_protocol.get_table_info(model_id, model_length)
                
                # 重新加载模型，只加载扫描到的模型 init的时候已经加载完所有的模型了
                #self.sunspec_protocol.load_models(available_models=list(model_map.keys()))
                
                # 为新发现的模型创建表格页（只对有JSON文件的模型 805一定要更新 805有重复子组）
                if 805 in model_map.keys():
                    # 805模型有重复子组，需要强制重新创建以显示正确的重复组字段
                    self.force_recreate_table_tab(805)
                for model_id in model_map.keys():
                    if model_id not in self.table_frames:
                        if model_id in self.sunspec_protocol.models:
                            self.create_table_tab(model_id)
                            self.log_message(f"Created new table page: Model {model_id}")
                        else:
                            self.log_message(f"Skipped model {model_id}: JSON file not found")
                
                # 更新标签页标题显示地址
                self.update_table_titles()
                
                # 自动流程完成提示
                self.log_message("Auto scanning process completed! Ready to read data.")
                

            else:
                error_msg = f"Model scan failed: {result.get('error', 'Unknown error')}"
                if result.get("error") == "timeout":
                    error_msg = f"Scan models timeout at address {result.get('address', 'unknown')}. Aborting."
                    # 检测到超时，如果正在自动读取，则停止自动读取
                    if self.auto_read_all_var.get():
                        self.auto_read_all_var.set(False)
                        self.on_auto_read_all_changed()
                        self.notify("warning", "Communication Timeout", 
                                   "Communication timeout detected during model scan. Auto-read has been stopped.")
                
                self.log_message(error_msg)       
        self._execute_operation("scan_models", None, on_scan_models_result, timeout=60.0)
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 获取图标文件路径
            icon_path = self.get_resource_path('BQC.ico')
            
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                print(f"图标文件不存在: {icon_path}")
        except Exception as e:
            print(f"设置窗口图标失败: {e}")

    def get_resource_path(self, filename):
        """获取资源文件路径，支持打包后的路径"""
        import sys
        
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            base_path = sys._MEIPASS
            return os.path.join(base_path, filename)
        else:
            # 如果是开发环境
            return filename

    def setup_gui(self):
        """设置GUI界面"""
        # 使用统一的main_frame，避免重复创建
        main_frame = self.main_frame

        # 语言切换按钮（只在独立模式下显示）
        if not self.is_embedded:
            lang_frame = ttk.Frame(main_frame)
            lang_frame.pack(fill=tk.X, pady=(0, 5))
            ttk.Label(lang_frame, text="Language:").pack(side=tk.LEFT)
            lang_var = tk.StringVar(value=self.language_manager.get_current_language())
            lang_combo = ttk.Combobox(lang_frame, textvariable=lang_var, 
                                     values=self.language_manager.get_available_languages(),
                                     state="readonly", width=10)
            lang_combo.pack(side=tk.LEFT, padx=(5, 0))
            lang_combo.bind('<<ComboboxSelected>>', lambda e: self.change_language(lang_var.get()))

        # 连接设置
        self.connection_frame = ConnectionFrame(main_frame, self.language_manager)
        self.connection_frame.pack(fill=tk.X, pady=(0, 10))

        # 扫描基地址和模型地址按钮及显示
        scan_frame = ttk.Frame(main_frame)
        scan_frame.pack(fill=tk.X, pady=(0, 5))
        

        
        self.current_base_addr_label = ttk.Label(scan_frame, text=self.language_manager.get_text("current_base_address"))
        self.current_base_addr_label.pack(side=tk.LEFT, padx=(10, 2))
        
        self.base_addr_var = tk.StringVar(value=self.language_manager.get_text("not_scanned"))
        base_addr_entry = ttk.Entry(scan_frame, textvariable=self.base_addr_var, width=10, state="readonly")
        base_addr_entry.pack(side=tk.LEFT, padx=(0, 10))     

        # 总控按钮（只保留读取全部）
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        self.read_all_tables_btn = ttk.Button(btn_frame, text=self.language_manager.get_text("read_all_tables"), 
                                 command=self.read_all_tables)
        self.read_all_tables_btn.pack(side=tk.LEFT)

        # 新增：自动读取全部表格勾选框
        self.auto_read_all_var = tk.BooleanVar(value=False)
        self.auto_read_all_check = ttk.Checkbutton(
            btn_frame, text=self.language_manager.get_text("auto_read_all_tables"), variable=self.auto_read_all_var, command=self.on_auto_read_all_changed
        )
        self.auto_read_all_check.pack(side=tk.LEFT, padx=(10, 0))
        
        # 自动读取间隔设置
        self.interval_label = ttk.Label(btn_frame, text=self.language_manager.get_text("interval_seconds"))
        self.interval_label.pack(side=tk.LEFT, padx=(10, 2))
        self.auto_read_interval_var = tk.StringVar(value="5")
        interval_entry = ttk.Entry(btn_frame, textvariable=self.auto_read_interval_var, width=5)
        interval_entry.pack(side=tk.LEFT)

        # # Excel历史记录
        # self.excel_record_var = tk.BooleanVar(value=False)
        # self.excel_record_check = ttk.Checkbutton(
        #     btn_frame,
        #     text="记录历史到Excel",
        #     variable=self.excel_record_var,
        #     command=self.on_excel_record_changed,
        # )
        # self.excel_record_check.pack(side=tk.LEFT, padx=(15, 0))

        # self.excel_path_var = tk.StringVar(value="")
        # self.excel_path_entry = ttk.Entry(btn_frame, textvariable=self.excel_path_var, width=35)
        # self.excel_path_entry.pack(side=tk.LEFT, padx=(5, 0))

        # self.excel_browse_btn = ttk.Button(btn_frame, text="选择", command=self.select_excel_file)
        # self.excel_browse_btn.pack(side=tk.LEFT, padx=(5, 0))

        # 垂直可分割区域：上-数据页签，下-日志区域（支持拖动调整高度）
        self.split = tk.PanedWindow(main_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        self.split.pack(fill=tk.BOTH, expand=True, padx=(10, 10), pady=(0, 10))

        top_pane = ttk.Frame(self.split)
        bottom_pane = ttk.Frame(self.split)
        # 添加面板并设置最小高度，保证底部按钮可见
        self.split.add(top_pane, minsize=150)
        self.split.add(bottom_pane, minsize=80)

        # 创建标签页容器（放在上半部分）
        self.notebook = ttk.Notebook(top_pane)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 数据显示区 - 使用标签页
        self.data_tables = {}
        self.table_frames = {}
        self.read_all_btns = {}  # 保存每个表格的读全部按钮

        # 创建Overview标签页
        self.create_overview_tab()

        # 创建UART Command Set标签页
        self.create_uart_command_tab()

        # 初始创建默认表格页 (1,802,805,64900,64950,64951,64952)
        for table_id in [1,802,64900,64950,64951,64952,805]:
            self.create_table_tab(table_id)

        # 下半部分：日志区域（带标题与按钮，始终可见）
        log_header_frame = ttk.Frame(bottom_pane)
        log_header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        self.log_title_label = ttk.Label(log_header_frame, text=self.language_manager.get_text("log"),
                                         font=('TkDefaultFont', 10, 'bold'))
        self.log_title_label.pack(side=tk.LEFT)

        log_btn_frame = ttk.Frame(log_header_frame)
        log_btn_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        self.clear_log_btn = ttk.Button(log_btn_frame, text=self.language_manager.get_text("clear_log"),
                                   command=self.clear_log)
        self.clear_log_btn.pack(side=tk.LEFT)

        # 自动保存日志勾选框 - 默认不勾选
        self.auto_save_log_var = tk.BooleanVar(value=False)
        self.auto_save_check = ttk.Checkbutton(log_btn_frame, text=self.language_manager.get_text("auto_save_log"),
                                          variable=self.auto_save_log_var, command=self.on_auto_save_changed)
        self.auto_save_check.pack(side=tk.LEFT, padx=(10, 0))

        # 可选：日志过滤开关（若有文本）
        self.log_filter_var = tk.BooleanVar(value=True)
        try:
            self.log_filter_check = ttk.Checkbutton(log_btn_frame, text=self.language_manager.get_text("log_filter"),
                                                    variable=self.log_filter_var, command=self.set_log_filter)
            self.log_filter_check.pack(side=tk.LEFT, padx=(10, 0))
        except Exception:
            pass

        # 日志文本框
        self.log_frame = ttk.Frame(bottom_pane)
        self.log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 5))

        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=6, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 初始化分割条位置（默认让日志占窗口高度约25%）
        try:
            if not self.is_embedded and self.root:
                self.root.after(200, self._init_paned_sash)
            elif self.is_embedded and self.parent_frame:
                self.parent_frame.winfo_toplevel().after(200, self._init_paned_sash)
        except Exception:
            pass

        # 隐藏文件路径相关变量
        self.log_file_path = None
        self.log_file_var = tk.StringVar(value="not selected")

    def _init_paned_sash(self):
        """初始化分割条默认位置（让日志区域占窗口约25%高度）"""
        # 只在第一次布局完成时设置一次
        def on_configure(event):
            # 解绑，避免每次窗口大小变化都重新设
            self.split.unbind("<Configure>")

            height = event.height
            if height <= 1:
                return

            # 上面 72%，下面 28%
            sash_y = int(height * 0.72)
            # x 用 0 就行，垂直 PanedWindow 只看 y
            self.split.sash_place(0, 0, sash_y)

        # 绑定在 PanedWindow 本身上更合理
        self.split.bind("<Configure>", on_configure)

    def change_language(self, language):
        """切换语言"""
        if self.language_manager.set_language(language):
            # 只更新界面文本，不重建窗口
            self.update_interface_text()
    
    def set_language(self, language):
        """外部设置语言的方法，用于统一管理器调用"""
        print(f"Modbus工具外部语言设置: {language}")
        # 转换语言代码
        modbus_language = language
            
        print(f"Modbus工具转换后的语言代码: {modbus_language}")
        
        if self.language_manager.set_language(modbus_language):
            self.update_interface_text()                
            print(f"Modbus工具语言设置完成: {language}")
        else:
            print(f"Modbus工具语言设置失败: {language}")

    def update_interface_text(self):
        """更新界面文本"""
        # 更新窗口标题（只在独立模式下）
        if not self.is_embedded and self.root:
            self.root.title(self.language_manager.get_text("window_title"))
        
        # 更新状态栏
        # 初始化状态栏（如果有统一状态栏的话）
        if self.status_var:
            self.status_var.set("Ready")
        
        # 更新连接设置框架
        self.update_connection_frame_text()
        
        # 更新扫描按钮文本
        self.update_scan_buttons_text()
        
        # 更新表格标题
        self.update_table_titles()
        
        # 更新日志区域文本
        self.update_log_area_text()
        
        # 更新间隔标签文本
        self.update_interval_labels_text()
        
        # 更新数据表格文本
        self.update_data_tables_text()

    def update_connection_frame_text(self):
        """更新连接设置框架的文本"""
        # 更新连接框架的语言
        self.connection_frame.update_language(self.language_manager)
        
        # 更新按钮文本
        self.connection_frame.connect_rtu_btn.configure(text=self.language_manager.get_text("connect_rtu"))
        self.connection_frame.disconnect_btn.configure(text=self.language_manager.get_text("disconnect"))

    def update_scan_buttons_text(self):
        """更新扫描按钮的文本"""

        # if hasattr(self, 'scan_model_btn'):
        #     self.scan_model_btn.configure(text=self.language_manager.get_text("scan_model_address"))
        if hasattr(self, 'current_base_addr_label'):
            self.current_base_addr_label.configure(text=self.language_manager.get_text("current_base_address"))
        if hasattr(self, 'read_all_tables_btn'):
            self.read_all_tables_btn.configure(text=self.language_manager.get_text("read_all_tables"))
    
        # 更新基地址变量的默认值
        if hasattr(self, 'base_addr_var'):
            if self.base_addr_var.get() == "未扫描" or self.base_addr_var.get() == "Not Scanned":
                self.base_addr_var.set(self.language_manager.get_text("not_scanned"))

    def update_table_titles(self):
        """更新表格标题"""
        # 遍历所有已存在的表格页
        for i in range(self.notebook.index("end")):
            tab_text = self.notebook.tab(i, "text")
            # 从标签文本中提取表格ID
            import re
            match = re.search(r'(\d+)', tab_text)
            if match:
                table_id = int(match.group(1))
                # 获取当前地址显示
                if hasattr(self, 'model_base_addrs') and table_id in self.model_base_addrs:
                    addr_text = str(self.model_base_addrs[table_id])
                else:
                    addr_text = "-"
                self.notebook.tab(i, text=f"{self.language_manager.get_text('table')}{table_id}({self.language_manager.get_text('addr')}: {addr_text})")

    def update_log_area_text(self):
        """更新日志区域的文本"""
        # 更新标题
        if hasattr(self, 'log_title_label'):
            self.log_title_label.configure(text=self.language_manager.get_text("log"))
        # 更新按钮文本
        if hasattr(self, 'clear_log_btn'):
            self.clear_log_btn.configure(text=self.language_manager.get_text("clear_log"))
        if hasattr(self, 'auto_save_check'):
            self.auto_save_check.configure(text=self.language_manager.get_text("auto_save_log"))
        if hasattr(self, 'auto_read_all_check'):
            self.auto_read_all_check.configure(text=self.language_manager.get_text("auto_read_all_tables"))
        if hasattr(self, 'log_filter_check'):
            self.log_filter_check.configure(text=self.language_manager.get_text("log_filter"))

    def update_interval_labels_text(self):
        """更新间隔标签的文本"""
        if hasattr(self, 'interval_label'):
            self.interval_label.configure(text=self.language_manager.get_text("interval_seconds"))

    def update_data_tables_text(self):
        """更新数据表格的文本"""
        # 更新每个表格的读全部按钮
        for table_id, read_all_btn in self.read_all_btns.items():
            read_all_btn.configure(text=self.language_manager.get_text("read_all"))
        
        # 更新数据表格的语言
        for table_id, data_table in self.data_tables.items():
            data_table.update_language(self.language_manager)
        
        # 更新OverviewFrame的语言
        if hasattr(self, 'overview_frame'):
            self.overview_frame.update_language(self.language_manager)

    def bind_events(self):
        """绑定事件"""
        # 绑定连接框架的按钮事件
        self.connection_frame.connect_rtu_btn.config(command=self.connect_rtu)
        self.connection_frame.disconnect_btn.config(command=self.disconnect)
        
        # 初始化按钮状态
        self.update_connection_buttons_state()

    def update_connection_buttons_state(self):
        """更新连接按钮状态"""
        is_connected = self.modbus_client.is_connected()
        
        # 更新连接框架的按钮状态
        self.connection_frame.update_buttons_state(is_connected)

    def force_recreate_table_tab(self, table_id):
        """强制重新创建表格标签页（用于805模型等需要重复组更新的情况）"""
        if table_id in self.table_frames:
            # 移除现有的表格标签页
            self.remove_table_tab(table_id)
        # 重新创建表格标签页
        self.create_table_tab(table_id)
        self.log_message(f"Force recreated table page for Model {table_id} with repeated groups")

    def remove_table_tab(self, table_id):
        """移除表格标签页"""
        if table_id not in self.table_frames:
            return
        
        # 找到对应的标签页索引
        for i in range(self.notebook.index("end")):
            tab_text = self.notebook.tab(i, "text")
            # 从标签文本中提取表格ID
            import re
            match = re.search(r'(\d+)', tab_text)
            if match and int(match.group(1)) == table_id:
                # 移除标签页
                self.notebook.forget(i)
                break
        
        # 清理相关数据
        if table_id in self.table_frames:
            del self.table_frames[table_id]
        if table_id in self.data_tables:
            del self.data_tables[table_id]
        if table_id in self.read_all_btns:
            del self.read_all_btns[table_id]

    def create_table_tab(self, table_id):
        """创建单个表格标签页"""
        if table_id in self.table_frames:
            return  # 已存在，不重复创建
        
        # 检查模型是否已加载
        if table_id not in self.sunspec_protocol.models:
            print(f"警告：尝试创建未加载的模型{table_id}的标签页")
            return
        
        # 检查模型是否有有效的字段信息
        table_info = self.sunspec_protocol.get_table_info(table_id)
        if not table_info or not table_info.get("fields"):
            print(f"警告：模型{table_id}没有有效的字段信息")
            return

        # 获取扫描到的模型长度（优先使用扫描缓存）
        scanned_model_length = None
        if hasattr(self, 'model_lengths') and table_id in getattr(self, 'model_lengths', {}):
            scanned_model_length = self.model_lengths[table_id]
            self.log_message(f"Model {table_id} cached length: {scanned_model_length}")
        elif hasattr(self, 'model_base_addrs') and table_id in self.model_base_addrs:
            # 回退：从设备读取一次长度
            base_addr = self.model_base_addrs[table_id]
            try:
                length_regs = self.modbus_client.read_holding_registers(base_addr + 1, 1)
                if length_regs and len(length_regs) > 0:
                    scanned_model_length = length_regs[0]
                    self.log_message(f"Model {table_id} scanned length: {scanned_model_length}")
            except Exception as e:
                self.log_message(f"Failed to read model {table_id} length: {e}")

        # 创建标签页
        tab_frame = ttk.Frame(self.notebook)
        self.notebook.add(tab_frame, text=f"{self.language_manager.get_text('table')}{table_id}({self.language_manager.get_text('addr')}: -)")
        self.table_frames[table_id] = tab_frame

        # 按钮区（只保留读全部）
        btn_frame = ttk.Frame(tab_frame)
        btn_frame.pack(fill=tk.X, anchor="w", pady=(5, 0))
        read_all_btn = ttk.Button(btn_frame, text=self.language_manager.get_text("read_all"), 
                         command=lambda tid=table_id: self.read_table(tid))
        read_all_btn.pack(side=tk.LEFT)
        self.read_all_btns[table_id] = read_all_btn  # 保存按钮引用

        # 内容区+滚动条
        content_frame = ttk.Frame(tab_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        canvas = tk.Canvas(content_frame)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        scrollable_frame.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        
        def on_canvas_configure(event, canvas=canvas, window_id=canvas_window_id, sf=scrollable_frame):
            canvas.itemconfig(window_id, width=event.width)
            sf.configure(width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        canvas.bind('<Configure>', on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_mousewheel(_):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def _unbind_mousewheel(_):
            canvas.unbind_all("<MouseWheel>")
        # 鼠标进入/离开可滚动区域时绑定/解绑（仅 Windows）
        scrollable_frame.bind("<Enter>", _bind_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)


        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        dt = DataTableFrame(scrollable_frame, table_id, self.sunspec_protocol, 
                          self.modbus_client, main_window=self, language_manager=self.language_manager,
                          scanned_model_length=scanned_model_length)
        dt.pack(fill=tk.BOTH, expand=True)
        self.data_tables[table_id] = dt

    def create_overview_tab(self):
        """创建Overview标签页"""
        # 创建标签页
        overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(overview_frame, text="Overview")
        
        # 内容区+滚动条
        content_frame = ttk.Frame(overview_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        canvas = tk.Canvas(content_frame)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        scrollable_frame.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        
        def on_canvas_configure(event, canvas=canvas, window_id=canvas_window_id, sf=scrollable_frame):
            canvas.itemconfig(window_id, width=event.width)
            sf.configure(width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        canvas.bind('<Configure>', on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_mousewheel(_):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def _unbind_mousewheel(_):
            canvas.unbind_all("<MouseWheel>")
            
        scrollable_frame.bind("<Enter>", _bind_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 创建Overview组件
        self.overview_frame = OverviewFrame(scrollable_frame, self.sunspec_protocol, 
                                          self.modbus_client, main_window=self, 
                                          language_manager=self.language_manager)
        self.overview_frame.pack(fill=tk.BOTH, expand=True)

    def create_uart_command_tab(self):
        """创建UART Command Set标签页"""
        # 创建标签页
        uart_frame = ttk.Frame(self.notebook)
        self.notebook.add(uart_frame, text="UART Command Set")
        
        # 移除按钮区，不需要读取UART参数功能
        
        # 内容区+滚动条
        content_frame = ttk.Frame(uart_frame)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        canvas = tk.Canvas(content_frame)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        canvas_window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        scrollable_frame.bind(
            "<Configure>",
            lambda e, c=canvas: c.configure(scrollregion=c.bbox("all"))
        )
        
        def on_canvas_configure(event, canvas=canvas, window_id=canvas_window_id, sf=scrollable_frame):
            canvas.itemconfig(window_id, width=event.width)
            sf.configure(width=event.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        canvas.bind('<Configure>', on_canvas_configure)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 绑定鼠标滚轮事件
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_mousewheel(_):
            canvas.bind_all("<MouseWheel>", on_mousewheel)

        def _unbind_mousewheel(_):
            canvas.unbind_all("<MouseWheel>")
            
        scrollable_frame.bind("<Enter>", _bind_mousewheel)
        scrollable_frame.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 创建UART命令表格组件
        from gui_components import UartCommandFrame
        self.uart_command_frame = UartCommandFrame(scrollable_frame, self.modbus_client, 
                                                 main_window=self, language_manager=self.language_manager)
        self.uart_command_frame.pack(fill=tk.BOTH, expand=True)

    def on_auto_save_changed(self):
        """自动保存日志勾选框状态改变时的处理"""
        if self.auto_save_log_var.get():
            # 勾选时，直接弹出文件选择对话框
            self.select_log_file()
        else:
            # 取消勾选时，清除文件路径
            self.log_file_path = None
            self.log_file_var.set("未选择文件" if self.language_manager.get_current_language() == "zh" else "No file selected")
    def set_log_filter(self):
        """设置日志过滤"""
        self.modbus_client.set_log_filter(self.log_filter_var.get())

    def select_log_file(self):
        """选择日志文件"""
        from tkinter import filedialog
        import time
        import os
        
        # 生成默认文件名
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_filename = f"SunSpec_Log_{timestamp}.txt"
        
        # 获取用户文档目录作为默认保存位置
        try:
            import os.path
            default_dir = os.path.expanduser("~/Documents")
            if not os.path.exists(default_dir):
                default_dir = os.getcwd()  # 如果文档目录不存在，使用当前目录
        except:
            default_dir = os.getcwd()
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="选择日志文件" if self.language_manager.get_current_language() == "zh" else "Select Log File",
            initialdir=default_dir,
            initialfile=default_filename
        )
        if filename:
            self.log_file_path = filename
            self.log_file_var.set(filename)
            # 立即创建文件
            try:
                with open(self.log_file_path, 'w', encoding='utf-8') as f:
                    f.write(f"# SunSpec Modbus Log File\n")
                    f.write(f"# Created: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Language: {self.language_manager.get_current_language()}\n")
                    f.write(f"# File: {os.path.basename(filename)}\n\n")
                    f.write(self.log_text.get(1.0, tk.END))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create log file: {str(e)}")
                # 如果创建失败，取消勾选
                self.auto_save_log_var.set(False)
        else:
            # 如果用户取消选择，取消勾选
            self.auto_save_log_var.set(False)

    def log_message(self, message):
        """添加日志消息 - 线程安全版本，支持标签页感知"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        # 初始化日志队列（如果不存在）
        if not hasattr(self, '_log_queue'):
            import queue
            self._log_queue = queue.Queue()
            self._log_batch = []
            self._log_timer = None
        
        # 将日志添加到队列而不是直接更新UI
        try:
            self._log_queue.put(log_entry, block=False)
        except queue.Full:
            pass  # 如果队列满了，丢弃日志避免阻塞
        
        # 启动批量处理定时器
        self._schedule_log_batch_update()
    
    def _schedule_log_batch_update(self):
        """调度批量日志更新"""
        if self._log_timer is not None:
            return  # 已经有定时器在运行
        
        # 使用after方法确保在主线程中执行
        try:
            if not self.is_embedded and self.root:
                self._log_timer = self.root.after(200, self._process_log_batch)
            elif self.is_embedded and self.parent_frame:
                top_level = self.parent_frame.winfo_toplevel()
                self._log_timer = top_level.after(200, self._process_log_batch)
        except Exception:
            # 如果调度失败，直接处理
            self._process_log_batch()
    
    def _process_log_batch(self):
        """批量处理日志更新 - 在主线程中执行"""
        try:
            # 重置定时器
            self._log_timer = None
            
            # 收集所有待处理的日志
            log_entries = []
            while True:
                try:
                    entry = self._log_queue.get_nowait()
                    log_entries.append(entry)
                    if len(log_entries) >= 50:  # 限制批量大小
                        break
                except queue.Empty:
                    break
            
            if not log_entries:
                return
            
            # 批量更新UI（只在主线程中执行）
            combined_text = ''.join(log_entries)
            self.log_text.insert(tk.END, combined_text)
            self.log_text.see(tk.END)
            # 同步到文件
            if self.auto_save_log_var.get() and self.log_file_path:
                try:
                    with open(self.log_file_path, 'a', encoding='utf-8') as f:
                        f.write(combined_text)
                except Exception as e:
                    # 如果写入失败，取消勾选并提示用户
                    self.auto_save_log_var.set(False)
                    self.log_file_path = None
                    self.log_message(f"Failed to write to log file, auto-save disabled: {e}")
            # 限制日志行数，避免内存占用过多
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > 1000:  # 保持最多1000行日志
                self.log_text.delete('1.0', '100.0')  # 删除前100行
            
            # 如果还有更多日志，继续调度
            if not self._log_queue.empty():
                self._schedule_log_batch_update()
                
        except Exception as e:
            print(f"Log batch processing error: {e}")
            # 重置状态
            self._log_timer = None

    def clear_log(self):
        """清空日志显示区域（不清空文件）"""
        self.log_text.delete(1.0, tk.END)
        #         self.log_text.insert(tk.END, error_msg)

    def connect_rtu(self):
        """连接RTU Modbus"""
        port = self.connection_frame.rtu_port_var.get()
        baudrate = int(self.connection_frame.baudrate_var.get())
        slave_id = int(self.connection_frame.slave_id_var.get())
        timeout = int(self.connection_frame.timeout_var.get())
        
        def on_result(result, error):
            if error:
                self.log_message("RTU Connection Failed")
                self.notify("error", "Connection Failed", f"Failed to connect to {port}: {error}")
                return
                
            if result:
                self.modbus_client.set_log_filter(self.log_filter_var.get())
                self.modbus_client.set_log_callback(self.log_message)
                self.log_message(f"RTU Connected: {port}, Slave ID: {slave_id}")
                self.log_message(f"RTU Connected: {port}, Slave ID: {slave_id}")
                
                # 更新UI状态
                self.connection_frame.set_connection_controls_state(False)
                self.update_connection_buttons_state()
                
                # 自动开始扫描
                self.log_message("start scanning base address...")
                self.scan_base_address()
            else:
                self.log_message("RTU Connection Failed")
                self.notify("error", "Connection Failed", f"Failed to connect to {port}")
        
        self._execute_operation("connect_rtu", (port, baudrate, timeout, slave_id), on_result)

    def disconnect(self):
        """断开连接"""
        def on_result(result, error):
            self.log_message(self.language_manager.get_text("disconnected"))
            
            # 恢复串口配置控件
            self.connection_frame.set_connection_controls_state(True)
            self.update_connection_buttons_state()
            
            # 在断开连接完成后再重置扫描状态和表格
            self.reset_scan_and_tables()
        
            # 重置用户主动断开标志
            self.user_initiated_disconnect = False
        
        # 设置用户主动断开标志
        self.user_initiated_disconnect = True
        
        # 立即设置停止自动读取所有标志
        self._stop_auto_read("user", "User disconnected")
        
        # 立即停止所有正在进行的操作
        self._cancel_all_operations()
        
        # 执行断开连接（通信线程中关闭串口）
        self._execute_operation("disconnect", None, on_result)
        
    def reset_scan_and_tables(self, reset_state=True):
        """重置扫描状态 + 表格页"""          
        if reset_state:
            self.is_scan_base_addr = False
            self.is_scan_model_addr = False
            self.base_addr_var.set(self.language_manager.get_text("not_scanned"))
        
        if hasattr(self.sunspec_protocol, 'base_address'):
            self.sunspec_protocol.base_address = None
        if hasattr(self, 'model_base_addrs'):
            self.model_base_addrs.clear()         
        
        #更新表头地址
        self.update_table_titles()
                   
        self.log_message("Reset scan state and tables")

    def read_all_tables(self):
        """读取全部表格 - 使用优化的通信线程"""
        if not self._check_read_preconditions():
            return False
        
        def on_read_complete(result, error=None):
            if error:
                self.log_message(f"Read all tables failed: {error}")
            elif result:
                #self.log_message("Read all tables completed successfully")
                pass
            else:
                self.log_message("Read all tables completed with errors")
        
        self._execute_operation("read_data", list(self.data_tables.keys()), on_read_complete)
        return True
    
    def read_table(self, table_id):
        """读取单个表格 - 使用优化的通信线程 读全部"""
        if not self._check_read_preconditions():
            return False
        
        def on_read_complete(result, error=None):
            if error:
                self.log_message(f"Read table {table_id} failed: {error}")
            elif result:
                #self.log_message(f"Read table {table_id} completed successfully")
                pass
            else:
                self.log_message(f"Read table {table_id} failed")
        
        self._execute_operation("read_data", [table_id], on_read_complete)
        return True
        
    def _check_read_preconditions(self):
        """检查读取前置条件"""
        if not self.modbus_client.is_connected():
            if not self.user_initiated_disconnect:
                self.notify("warning", self.language_manager.get_text("warning"), 
                                     self.language_manager.get_text("please_connect_first"))
            return False
        
        if not self.is_scan_model_addr:
            if not self.user_initiated_disconnect:
                self.notify("warning", self.language_manager.get_text("warning"), 
                                    self.language_manager.get_text("please_scan_model_addr_first"))
            return False
            
        return True
              
    def _handle_read_error(self, error_msg, table_id=None):
        """处理读取错误"""
        # 记录日志
        if table_id:
                self.log_message(f"Table {table_id} read failed: {error_msg}")
        else:
            self.log_message(f"Read error: {error_msg}")
            
        # 检查是否为连接错误
        connection_keywords = ["timeout", "connection", "device", "serial", "port", 
                              "communication", "no response", "failed to read"]
        is_connection_error = any(keyword in error_msg.lower() for keyword in connection_keywords)
        
        # 如果是连接错误且正在自动读取，停止自动读取
        if is_connection_error and self.auto_read_all_var.get():
            self._stop_auto_read("error", f"Communication error: {error_msg}")
            
        # 如果不是用户主动断开，显示错误弹窗
        if not self.user_initiated_disconnect and is_connection_error:
            self.notify("error", "Communication Error", error_msg)
            
    def _read_registers_in_chunks(self, base_addr, total_length, chunk_size=125, verbose=False):
        """分段读取寄存器数据"""
        if chunk_size > 125:
            chunk_size = 125
            
        all_data = []
        current_addr = base_addr
        remaining = total_length
        
        if verbose:
            self.schedule_on_ui(self.log_message, f"Starting segmented read, total length: {total_length}, max per segment: {chunk_size} registers")
        
        chunk_num = 1
        while remaining > 0:
            current_chunk_size = min(chunk_size, remaining)
            
            if verbose:
                self.schedule_on_ui(self.log_message, f"Reading segment {chunk_num}: address {current_addr}, length {current_chunk_size}")
            
            chunk_data = self.modbus_client.read_holding_registers(current_addr, current_chunk_size)
            if chunk_data is None:
                if verbose:
                    self.schedule_on_ui(self.log_message, f"Segment {chunk_num} read failed")
                return None
            
            all_data.extend(chunk_data)
            current_addr += current_chunk_size
            remaining -= current_chunk_size
            chunk_num += 1
            time.sleep(0.01)  # 短暂延迟
        
        if verbose:
            self.schedule_on_ui(self.log_message, f"Segmented read completed, total {len(all_data)} registers read")
        
        return all_data
        
    def _execute_operation(self, operation_type, params=None, callback=None, timeout=None):
        """执行操作（恢复为通信线程方式）"""
        if timeout is None:
            timeout = self.operation_timeout
            
        try:
            self.comm_queue.put((operation_type, params, callback, timeout), timeout=1.0)
        except queue.Full:
            if callback:
                callback(None, "Communication queue full")
    
    def _execute_operation_sync(self, operation, params, timeout=10.0):
        """同步执行通信操作，用于自动读取线程"""
        result_event = threading.Event()
        result_data = {"result": None, "error": None}
        
        def callback(result, error=None):
            result_data["result"] = result
            result_data["error"] = error
            result_event.set()
        
        # 提交操作
        self._execute_operation(operation, params, callback)
        
        # 等待结果
        if result_event.wait(timeout):
            return result_data["result"], result_data["error"]
        else:
            return None, "Operation timeout"

    # def on_excel_record_changed(self):
    #     """Excel历史记录勾选框状态改变"""
    #     if self.excel_record_var.get():
    #         # 设置用户指定的路径（如果有）
    #         path = (self.excel_path_var.get() or "").strip()
    #         if path:
    #             self.excel_recorder.set_excel_path(path)
            
    #         # 启用记录（会自动生成路径如果还没有）
    #         self.excel_recorder.enable()
    #         self.excel_path_var.set(self.excel_recorder.excel_path or "")
    #         self.log_message(f"Excel history recording enabled: {self.excel_recorder.excel_path}")
    #     else:
    #         self.excel_recorder.disable()
    #         self.log_message("Excel history recording disabled")

    # def select_excel_file(self):
    #     """选择Excel文件保存路径"""
    #     from tkinter import filedialog
    #     timestamp = time.strftime("%Y%m%d_%H%M%S")
    #     default_filename = f"SunSpec3_Log_{timestamp}.xlsx"
        
    #     try:
    #         default_dir = os.path.expanduser("~/Documents")
    #         if not os.path.exists(default_dir):
    #             default_dir = os.getcwd()
    #     except Exception:
    #         default_dir = os.getcwd()
        
    #     filename = filedialog.asksaveasfilename(
    #         defaultextension=".xlsx",
    #         filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
    #         title="Select Excel File",
    #         initialdir=default_dir,
    #         initialfile=default_filename,
    #     )
    #     if filename:
    #         self.excel_path_var.set(filename)
    #         self.excel_recorder.set_excel_path(filename)

    def on_auto_read_all_changed(self):
        """自动读取全部表格勾选框状态改变时的处理"""
        if self.auto_read_all_var.get():
            # 检查前置条件
            if not self.modbus_client.is_connected():
                self.auto_read_all_var.set(False)
                self.notify("warning", self.language_manager.get_text("warning"), 
                self.language_manager.get_text("please_connect_first"))
                return
            if not self.is_scan_model_addr:
                self.auto_read_all_var.set(False)
                self.notify("warning", self.language_manager.get_text("warning"), 
                self.language_manager.get_text("please_scan_model_addr_first"))
                return 
            
            # 启动自动读取
            with self._auto_read_lock:
                self._auto_read_all_running = True
            self.auto_read_thread = threading.Thread(target=self.auto_read_worker, daemon=True)
            self.auto_read_thread.start()
            # 同时启动Overview定时打印线程
            self._start_overview_log_thread()
            self.log_message("Auto read enabled")
        else:
            # 停止自动读取 - 非阻塞方式
            with self._auto_read_lock:
                self._auto_read_all_running = False
            # 同时停止Overview定时打印线程
            self._stop_overview_log_thread()
            # 不阻塞等待线程结束，让它自然结束
            self.log_message("Auto read disabled")

    def auto_read_worker(self):
        """后台线程工作函数，执行自动读取"""
        self.schedule_on_ui(self.log_message, "Auto read started")
        
        while True:
            # 使用锁检查运行状态
            with self._auto_read_lock:
                should_continue = self._auto_read_all_running
            
            if not should_continue:
                break              
            try:
                # 获取用户设置的间隔时间
                try:
                    interval = float(self.auto_read_interval_var.get())
                    interval = max(1, min(60, interval))  # 限制在1-60秒之间
                except:
                    interval = 5  # 默认5秒
                
                if not self._check_read_preconditions():
                    self._stop_auto_read("error", "Read preconditions not met")
                    break
                # 使用优化的通信线程进行读取
                #self.schedule_on_ui(self.log_message, f"Auto reading {len(self.data_tables)} tables...")
                
                result, error = self._execute_operation_sync("read_data", list(self.data_tables.keys()), timeout=15.0)
                
                if error:
                    self.schedule_on_ui(self.log_message, f"Auto read cycle failed: {error}")
                    # 对于通信错误，停止自动读取
                    communication_keywords = ["timeout", "connection", "communication", "failed_to_read", "exception_attempt"]
                    if any(keyword in str(error).lower() for keyword in communication_keywords):
                        self._stop_auto_read("error", error)
                        break
                elif result:
                    #self.schedule_on_ui(self.log_message, f"Auto read cycle completed successfully")
                    pass
                else:
                    self.schedule_on_ui(self.log_message, "Auto read cycle completed with some errors")
                
                # 等待指定时间后继续下一次读取
                self._sleep_with_interrupt_check(interval)
                        
            except Exception as e:
                self.schedule_on_ui(self.log_message, f"Auto read error: {e}")
                self._stop_auto_read("error", f"Auto read error: {e}")
                break
                
        self.schedule_on_ui(self.log_message, "Auto read worker stopped")
                
    def _sleep_with_interrupt_check(self, interval):
        """可中断的睡眠"""
        sleep_steps = int(interval * 10)  # 分成0.1秒的小段，便于快速响应停止信号
        for _ in range(sleep_steps):
            with self._auto_read_lock:
                should_continue = self._auto_read_all_running
            if not should_continue:
                break
            time.sleep(0.1)
                        
    def _start_overview_log_thread(self):
        """启动Overview定时打印线程"""
        if not self._overview_log_enabled:
            return
        if self._overview_log_running:
            return
        self._overview_log_running = True
        self._last_overview_log_time = 0
        self._overview_log_thread = threading.Thread(target=self._overview_log_worker, daemon=True)
        self._overview_log_thread.start()

    def _stop_overview_log_thread(self):
        """停止Overview定时打印线程"""
        self._overview_log_running = False
        # 不阻塞等待线程结束，让它自然退出

    def _overview_log_worker(self):
        """Overview数据定时打印后台线程"""
        self.schedule_on_ui(self.log_message, "Overview logger started")
        while self._overview_log_running:
            try:
                self.schedule_on_ui(self._log_overview_data)
            except Exception as e:
                self.schedule_on_ui(self.log_message, f"Overview logger error: {e}")
            # 间隔睡眠，可快速响应停止
            try:
                #interval = float(self._overview_log_interval)
                interval = float(self.auto_read_interval_var.get())#自动读取 日志打印时间 5s（间隔写几秒就是几秒）
            except Exception:
                interval = 5
            interval = max(1, min(60, interval))
            steps = int(interval * 10)
            for _ in range(steps):
                if not self._overview_log_running:
                    break
                time.sleep(0.1)
        self.schedule_on_ui(self.log_message, "Overview logger stopped")

    def schedule_on_ui(self, func, *args, **kwargs):
        """确保在主线程调度函数"""
        try:
            if not self.is_embedded and self.root:
                            self.root.after_idle(lambda: func(*args, **kwargs))
            elif self.is_embedded and self.parent_frame:
                            self.parent_frame.winfo_toplevel().after_idle(lambda: func(*args, **kwargs))
            else:
                func(*args, **kwargs)
        except Exception:
            func(*args, **kwargs)

    def run(self):
        # 只在独立模式下设置关闭事件和主循环
        if not self.is_embedded and self.root:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()

    def start_communication_thread(self):
        """启动通信线程"""
        if self.comm_thread and self.comm_thread.is_alive():
            return
        
        self.comm_thread_running = True
        self.comm_thread = threading.Thread(target=self._communication_worker, daemon=True)
        self.comm_thread.start()
        
    def stop_communication_thread(self):
        """停止通信线程"""
        self.comm_thread_running = False
        if self.comm_thread and self.comm_thread.is_alive():
            try:
                self.comm_queue.put(("STOP", None, None, None), timeout=1.0)
            except queue.Full:
                pass
            self.comm_thread.join(timeout=2.0)
    
    def start_parse_thread(self):
        """启动后台解析线程"""
        if self.parse_thread and self.parse_thread.is_alive():
            return
        
        self.parse_thread_running = True
        self.parse_thread = threading.Thread(target=self._parse_worker, daemon=True)
        self.parse_thread.start()
        
    def stop_parse_thread(self):
        """停止后台解析线程"""
        self.parse_thread_running = False
        if self.parse_thread and self.parse_thread.is_alive():
            # 发送停止信号
            try:
                self.parse_queue.put(("STOP", None, None, None), timeout=1.0)
            except queue.Full:
                pass
            self.parse_thread.join(timeout=2.0)
    
    def start_result_processor(self):
        """启动结果处理器，定期检查结果队列"""
        self._process_results()
    
    def _process_results(self):
        """处理结果队列中的结果"""
        try:
            while True:
                try:
                    result_type, result_data, callback, error = self.result_queue.get_nowait()
                    if callback:
                        try:
                            callback(result_data, error)
                        except Exception as callback_error:
                            import traceback
                            self.log_message(f"Callback error for {result_type}: {callback_error}")
                            self.log_message(f"Callback traceback: {traceback.format_exc()}")
                            self.log_message(f"Result data keys: {list(result_data.keys()) if isinstance(result_data, dict) else type(result_data)}")
                except queue.Empty:
                    break
        except Exception as e:
            self.log_message(f"Result processing error: {e}")
        
        # 继续调度下一次处理
        try:
            if not self.is_embedded and self.root:
                self.root.after(100, self._process_results)
            elif self.is_embedded and self.parent_frame:
                # 获取顶级窗口进行调度
                top_level = self.parent_frame.winfo_toplevel()
                if top_level:
                    top_level.after(100, self._process_results)
            elif self.is_embedded:
                # 如果parent_frame不可用，尝试使用主框架
                if hasattr(self, 'main_frame') and self.main_frame:
                    top_level = self.main_frame.winfo_toplevel()
                    if top_level:
                        top_level.after(100, self._process_results)
        except Exception as e:
            self.log_message(f"Error scheduling result processor: {e}")
            # 如果调度失败，尝试直接调用（可能会导致阻塞，但至少能处理结果）
            import threading
            threading.Timer(0.1, self._process_results).start()
    
    def _communication_worker(self):
        """通信线程工作函数 - 优化的串行处理"""
        while self.comm_thread_running:
            try:
                # 等待通信任务
                try:
                    operation, params, callback, timeout = self.comm_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if operation == "STOP":
                    break
                
                result = None
                error = None
                
                try:
                    # 执行具体的Modbus操作
                    if operation == "connect_rtu":
                        port, baudrate, timeout_val, slave_id = params
                        result = self.modbus_client.connect_rtu(port, baudrate, timeout=timeout_val)
                        if result:
                            self.modbus_client.slave_id = slave_id
                    elif operation == "disconnect":
                        self.modbus_client.disconnect()
                        result = True
                    elif operation == "scan_base_address":
                        result = self._do_scan_base_address()
                    elif operation == "scan_models":
                        result = self._do_scan_models()
                    elif operation == "read_data":
                        table_ids = params
                        result = self._do_read_data_optimized(table_ids)
                    elif operation == "read_single_field":
                        table_id, field_name = params
                        result = self._do_read_single_field(table_id, field_name)
                    elif operation == "write_field":
                        table_id, field_name, value = params
                        result = self._do_write_field(table_id, field_name, value)
                    else:
                        error = f"Unknown operation: {operation}"
                        
                except Exception as e:
                    error = str(e)
                    self.schedule_on_ui(self.log_message, f"Communication error in {operation}: {e}")
                
                # 将结果放入结果队列
                self.result_queue.put((operation, result, callback, error))
                
            except Exception as e:
                self.schedule_on_ui(self.log_message, f"Communication thread error: {e}")
                break
    
    def _do_read_data_optimized(self, table_ids):
        """优化的数据读取：读取->立即丢给解析线程->继续下一次"""
        if not hasattr(self, 'model_base_addrs'):
            return False
        
        # 确保table_ids是列表
        if isinstance(table_ids, int):
            table_ids = [table_ids]
        elif table_ids is None:
            table_ids = list(self.data_tables.keys())
        
        success_count = 0
        total_tables = len(table_ids)
        
        for table_id in table_ids:
            # 检查自动读取状态
            with self._auto_read_lock:
                auto_read_enabled = self.auto_read_all_var.get()
                auto_read_running = self._auto_read_all_running
            
            if auto_read_enabled and not auto_read_running:
                self.schedule_on_ui(self.log_message, "Read operation cancelled")
                break
                
            # 读取单个表格的原始数据
            raw_data_result = self._read_single_table_raw_data(table_id)
            
            if raw_data_result.get("success"):
                # 立即将原始数据发送给解析线程，不等待解析完成
                self._send_to_parse_thread(table_id, raw_data_result["raw_data"], 
                                         raw_data_result.get("receive_timestamp"))
                success_count += 1
                # 注意：这里不等待解析完成，立即继续下一个表格的读取
                
            else:
                error_msg = raw_data_result.get("error", "Unknown error")
                self.schedule_on_ui(self.log_message, f"Table {table_id} read failed: {error_msg}")
                
                # 检查是否为通信相关错误
                communication_errors = [
                    "failed_to_read_data", "timeout", "communication_error", "connection_lost",
                    "failed_to_read_length", "failed_to_read_data_attempt", "exception_attempt"
                ]
                is_communication_error = any(err in error_msg for err in communication_errors)
                
                if is_communication_error:
                    self.schedule_on_ui(self.log_message, f"Communication error detected, stopping read cycle")
                    # 立即停止自动读取
                    if self.auto_read_all_var.get():
                        self.schedule_on_ui(self._stop_auto_read, "error", f"Communication error: {error_msg}")
                    break
        
        # 添加总结日志
        if total_tables > 1:
            if success_count == total_tables:
                #self.schedule_on_ui(self.log_message, f"Read cycle: {success_count}/{total_tables} tables successful")
                pass
            elif success_count > 0:
                #self.schedule_on_ui(self.log_message, f"Read cycle: {success_count}/{total_tables} tables successful")
                pass
            else:
                self.schedule_on_ui(self.log_message, f"Read cycle: all tables failed")
        
        return success_count > 0
    
    def _do_scan_base_address(self):
        """在通信线程中执行基地址扫描 """
        candidate_addrs = [0, 40000, 50000]
        timeout_count = 0
        
        for i, addr in enumerate(candidate_addrs):
            # 更新扫描进度（通过日志）
            self.schedule_on_ui(self.log_message, f"Scanning address {addr} ({i+1}/{len(candidate_addrs)})...")
            
            # 直接使用ModbusClient的同步方法
            data = self.modbus_client.read_holding_registers(addr, 2)
            
            if data is None:
                timeout_count += 1
                self.schedule_on_ui(self.log_message, f"Address {addr}: No response (timeout or communication error)")
                if timeout_count == 1:
                    # 第一个地址就超时，可能是连接问题
                    return {"success": False, "error": "timeout", "message": "First address timeout - check connection"}
                continue
            elif data == "modbus_exception":
                self.schedule_on_ui(self.log_message, f"Address {addr}: Modbus exception response (device connected, wrong address)")
                continue
                
            if data and len(data) == 2:
                bytes_data = ((data[0]>>8) & 0xFF).to_bytes(1, 'big') + (data[0]  & 0xFF).to_bytes(1, 'big') + \
                           ((data[1]>>8)& 0xFF).to_bytes(1, 'big') + (data[1]  & 0xFF).to_bytes(1, 'big')
                try:
                    ascii_str = bytes_data.decode('ascii')
                    hex_str = ' '.join([f"{b:02X}" for b in bytes_data])
                    self.schedule_on_ui(self.log_message, f"Address {addr} content: {ascii_str} (hex: {hex_str})")
                    if ascii_str == "SunS":
                        return {"success": True, "base_address": addr}
                except Exception as e:
                    self.schedule_on_ui(self.log_message, f"Address {addr} parsing failed: {e}")
            else:
                self.schedule_on_ui(self.log_message, f"Address {addr}: Invalid response length")
        
        return {"success": False, "error": "not_found", "timeout_count": timeout_count}
    
    def _do_scan_models(self):
        """在后台线程中执行模型扫描"""
        if not hasattr(self.sunspec_protocol, 'base_address') or self.sunspec_protocol.base_address is None:
            return {"success": False, "error": "no_base_address"}
        
        base_addr = self.sunspec_protocol.base_address
        addr = base_addr + 2
        model_map = {}
        model_len_map = {}
        
        self.schedule_on_ui(self.log_message, f"Start scanning models, base address: {base_addr}")
        
        while True:
            regs = self.modbus_client.read_holding_registers(addr, 2)
            if regs is None:
                self.schedule_on_ui(self.log_message, f"Scan models timeout at address {addr}. Aborting.")
                return {"success": False, "error": "timeout", "address": addr}
            elif regs == "modbus_exception":
                self.schedule_on_ui(self.log_message, f"Modbus exception at address: {addr}, continuing...")
                addr += 1
                continue
            elif not regs or len(regs) < 2:
                self.schedule_on_ui(self.log_message, f"Failed to read model ID/LEN, address: {addr}")
                break
            
            model_id, model_len = regs[0], regs[1]
            self.schedule_on_ui(self.log_message, f"Model ID: {model_id} LEN: {model_len} @ {addr}")
            
            if model_id == 0xFFFF and model_len == 0:
                self.schedule_on_ui(self.log_message, "Model chain list end")
                break
            
            model_map[model_id] = addr
            model_len_map[model_id] = model_len
            addr = addr + 2 + model_len
        
        return {"success": True, "model_map": model_map, "model_lengths": model_len_map}
     
    def _do_read_single_field(self, table_id, field_name):
        """在后台线程中读取单个字段 单个读"""
        if not hasattr(self, 'model_base_addrs') or table_id not in self.model_base_addrs:
            return {"success": False, "error": "no_model_address"}
        
        # 从GUI组件获取字段信息
        table_component = None
        if hasattr(self, 'data_tables') and table_id in self.data_tables:
            table_component = self.data_tables[table_id]
        
        if not table_component or field_name not in table_component.fields:
            return {"success": False, "error": "field_not_found"}
        
        base_addr = self.model_base_addrs[table_id]
        field_info = table_component.fields[field_name]
        
        # 处理动态group字段的偏移
        if field_info.get('is_dynamic_group', False):
            offset = field_info["offset"]
        else:
            offset = field_info["offset"]
            
        addr = base_addr + offset
        length = field_info["size"]
        
        # 读取数据read_holding_registers返回的是每一个寄存器的数据
        data = self.modbus_client.read_holding_registers(addr, length)
        if data:
            # 将原始数据发送给解析线程处理，而不是在这里直接解析
            try:
                data_with_timestamp = {
                    "raw_data": data,
                    "receive_timestamp": time.time(),
                    "field_name": field_name  # 添加字段名信息
                }
                self.parse_queue.put(("parse_single_field", table_id, data_with_timestamp, None), timeout=0.1)
                return {"success": True, "queued": True}
            except queue.Full:
                return {"success": False, "error": "parse_queue_full"}
        else:
            return {"success": False, "error": "read_failed"}
    
    def _do_write_field(self, table_id, field_name, value):
        """在后台线程中写入单个字段，支持多寄存器字段（如string/uint32等）"""
        if not hasattr(self, 'model_base_addrs') or table_id not in self.model_base_addrs:
            return {"success": False, "error": "no_model_address"}
        
        # 从GUI组件获取字段信息
        table_component = None
        if hasattr(self, 'data_tables') and table_id in self.data_tables:
            table_component = self.data_tables[table_id]
        
        if not table_component or field_name not in table_component.fields:
            return {"success": False, "error": "field_not_found"}
        
        base_addr = self.model_base_addrs[table_id]
        field_info = table_component.fields[field_name]
        offset = field_info["offset"]
        size = field_info.get("size", 1)
        ftype = str(field_info.get("type", "uint16")).lower()
        addr = base_addr + offset
        
        try:
            # 处理字符串类型（每个寄存器存储两个字符）
            if ftype == 'string':
                # 期望value为字符串
                if not isinstance(value, str):
                    value = str(value)
                # 将字符串编码为ASCII
                raw_bytes = value.encode('ascii', errors='ignore')
                # 每个寄存器存储两个字符，所以最多存储 size*2 个字符
                max_chars = size * 2
                if len(raw_bytes) < max_chars:
                    raw_bytes = raw_bytes + b'\x00' * (max_chars - len(raw_bytes))
                else:
                    raw_bytes = raw_bytes[:max_chars]
                
                # 将字符按两个一组打包到寄存器中
                regs = []
                for i in range(0, len(raw_bytes), 2):
                    high_byte = raw_bytes[i] if i < len(raw_bytes) else 0
                    low_byte = raw_bytes[i+1] if i+1 < len(raw_bytes) else 0
                    reg_value = (high_byte << 8) | low_byte
                    regs.append(reg_value)
                
                ok = self.modbus_client.write_holding_registers(addr, regs)
                if ok:
                    try:
                        self._do_read_single_field(table_id, field_name)
                    except Exception:
                        pass
                return {"success": ok, "table_id": table_id, "field_name": field_name, "value": value, "refreshed": ok}
            
            # 处理32位整数或位域（2寄存器，高字在前）
            if size == 2 and ftype in ['uint32', 'int32', 'bitfield32']:
                ival = int(value)
                hi = (ival >> 16) & 0xFFFF
                lo = ival & 0xFFFF
                ok = self.modbus_client.write_holding_registers(addr, [hi, lo])
                if ok:
                    try:
                        self._do_read_single_field(table_id, field_name)
                    except Exception:
                        pass
                return {"success": ok, "table_id": table_id, "field_name": field_name, "value": ival, "refreshed": ok}
            
            # 如果是其他多寄存器类型，且value为列表/元组，直接写入
            if size > 1 and isinstance(value, (list, tuple)):
                vals = [int(v) & 0xFFFF for v in value]
                # 截断或补齐到size长度
                if len(vals) < size:
                    vals = vals + [0] * (size - len(vals))
                elif len(vals) > size:
                    vals = vals[:size]
                ok = self.modbus_client.write_holding_registers(addr, vals)
                if ok:
                    try:
                        self._do_read_single_field(table_id, field_name)
                    except Exception:
                        pass
                return {"success": ok, "table_id": table_id, "field_name": field_name, "value": vals, "refreshed": ok}
            
            # 默认：单寄存器写入
            ival = int(value)
            ok = self.modbus_client.write_holding_register(addr, ival & 0xFFFF)
            if ok:
                try:
                    self._do_read_single_field(table_id, field_name)
                except Exception:
                    pass
            return {"success": ok, "table_id": table_id, "field_name": field_name, "value": ival, "refreshed": ok}
        except ValueError:
            return {"success": False, "error": "invalid_value"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _read_single_table_raw_data(self, table_id):
        """读取单个表格的原始数据（不解析）"""
        import time  # 在函数开始就导入time模块
        
        if not hasattr(self, 'model_base_addrs') or table_id not in self.model_base_addrs:
            return {"success": False, "error": "no_model_address", "table_id": table_id}
        
        base_addr = self.model_base_addrs[table_id]
        
        # 优先使用扫描阶段的模型长度
        scanned_length = None
        if hasattr(self, 'model_lengths') and table_id in getattr(self, 'model_lengths', {}):
            scanned_length = self.model_lengths[table_id]
        
        last_error = None
        max_retries = 3  # 减少重试次数，避免长时间阻塞
        
        for attempt in range(1, max_retries + 1):
            try:
                # 检查连接状态
                if not self.modbus_client.is_connected():
                    return {"success": False, "error": "connection_lost", "table_id": table_id}
                
                # 如无缓存长度，则读取长度寄存器
                if scanned_length is None:
                    length_regs = self.modbus_client.read_holding_registers(base_addr + 1, 1)
                    if not length_regs or len(length_regs) == 0:
                        last_error = f"failed_to_read_length_attempt_{attempt}"
                        if attempt < max_retries:
                            time.sleep(0.1)  # 短暂延迟后重试
                        continue
                    scanned_length = length_regs[0]
                
                if scanned_length <= 0:
                    return {"success": False, "error": "invalid_length", "table_id": table_id, "length": scanned_length}
                
                # 读取完整原始数据
                total_length = scanned_length + 2
                if total_length <= 125:
                    raw_data = self.modbus_client.read_holding_registers(base_addr, total_length)
                else:
                    raw_data = self._read_registers_in_chunks(base_addr, total_length, verbose=False)
                
                if not raw_data:
                    last_error = f"failed_to_read_data_attempt_{attempt}"
                    if attempt < max_retries:
                        time.sleep(0.1)  # 短暂延迟后重试
                    continue
                
                # 成功读取，记录时间戳
                receive_timestamp = time.time()
                
                return {
                    "success": True, 
                    "table_id": table_id, 
                    "raw_data": raw_data,
                    "receive_timestamp": receive_timestamp
                }
                
            except Exception as e:
                last_error = f"exception_attempt_{attempt}: {str(e)}"
                if attempt < max_retries:
                    time.sleep(0.1)  # 短暂延迟后重试
                continue
        
        # 所有尝试均失败
        return {"success": False, "error": last_error or "table_read_failed", "table_id": table_id}
     
    def _send_to_parse_thread(self, table_id, raw_data, receive_timestamp=None):
        """将原始数据和时间戳发送给解析线程"""
        try:
            # 将时间戳包装到数据中
            data_with_timestamp = {
                "raw_data": raw_data,
                "receive_timestamp": receive_timestamp
            }
            self.parse_queue.put(("parse_table", table_id, data_with_timestamp, None), timeout=0.1)
        except queue.Full:
            self.schedule_on_ui(self.log_message, f"Parse queue full, skipping table {table_id}")
    
    def _parse_worker(self):
        """解析线程工作函数"""
        while self.parse_thread_running:
            try:
                # 等待解析任务
                try:
                    operation, table_id, raw_data, callback = self.parse_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                if operation == "STOP":
                    break
                
                if operation == "parse_table":
                    try:
                        # 从包装的数据中提取原始数据和时间戳
                        if isinstance(raw_data, dict) and "raw_data" in raw_data:
                            actual_raw_data = raw_data["raw_data"]
                            receive_timestamp = raw_data.get("receive_timestamp")
                        else:
                            # 兼容旧格式
                            actual_raw_data = raw_data
                            receive_timestamp = None
                        
                        # 解析数据
                        parsed_data = self.sunspec_protocol.parse_table_data(table_id, actual_raw_data)
                        if parsed_data:
                            # # 记录历史到Excel（使用raw值，不做symbols解析，不展开bit）
                            # try:
                            #     if hasattr(self, 'excel_recorder') and getattr(self, 'excel_record_var', None) and self.excel_record_var.get():
                            #         self.excel_recorder.record_model_data(table_id, parsed_data, receive_timestamp)
                            # except Exception as e:
                            #     self.schedule_on_ui(self.log_message, f"Excel record error for table {table_id}: {e}")

                            # 通过主线程更新UI，传递接收时间戳
                            self._schedule_ui_update(table_id, parsed_data, receive_timestamp)
                        else:
                            self.schedule_on_ui(self.log_message, f"Table {table_id} parse failed")
                    except Exception as e:
                        self.schedule_on_ui(self.log_message, f"Table {table_id} parse error: {e}")
                
                elif operation == "parse_single_field":
                    try:
                        # 从包装的数据中提取原始数据、时间戳和字段名
                        if isinstance(raw_data, dict) and "raw_data" in raw_data:
                            actual_raw_data = raw_data["raw_data"]
                            receive_timestamp = raw_data.get("receive_timestamp")
                            field_name = raw_data.get("field_name")
                        else:
                            # 兼容旧格式
                            actual_raw_data = raw_data
                            receive_timestamp = None
                            field_name = None
                        
                        if field_name:
                            # 解析单个字段数据
                            field_data = self.sunspec_protocol.parse_single_field(table_id, field_name, actual_raw_data)
                            if field_data:
                                # 通过主线程更新UI
                                self._schedule_single_field_ui_update(table_id, field_name, field_data, receive_timestamp)
                            else:
                                self.schedule_on_ui(self.log_message, f"Field {field_name} in table {table_id} parse failed")
                        else:
                            self.schedule_on_ui(self.log_message, f"Missing field name for single field parse")
                    except Exception as e:
                        self.schedule_on_ui(self.log_message, f"Single field parse error: {e}")
                        
            except Exception as e:
                self.schedule_on_ui(self.log_message, f"Parse thread error: {e}")
                break
    
    def _schedule_ui_update(self, table_id, parsed_data, receive_timestamp=None):
        """调度UI更新到主线程 - 更新所有model标签页"""
        def update_ui():
            # 检查UI是否正在重置，如果是则跳过更新
            # if not self._ui_reset_lock.acquire(blocking=False):
            #     return  # UI正在重置，跳过此次更新
            
            try:
                # 总是更新所有model标签页的数据，不再限制只更新当前可见页面
                if table_id in self.data_tables:
                    # 使用接收时间戳更新UI，如果没有则使用当前时间
                    if receive_timestamp:
                        self.data_tables[table_id].display_data(parsed_data, timestamp=receive_timestamp)
                    else:
                        self.data_tables[table_id].display_data(parsed_data)
                    
                    # 如果是model 64951，同时更新UART命令标签页
                    if table_id == 64951 and hasattr(self, 'uart_command_frame'):
                        self.uart_command_frame.update_values_from_model_data(parsed_data)

                    # 更新Overview页面数据
                    if hasattr(self, 'overview_frame'):
                        self.overview_frame.update_model_data(table_id, parsed_data, receive_timestamp)
                                    
            except Exception as e:
                self.log_message(f"UI update error for table {table_id}: {e}")
            # finally:
            #     self._ui_reset_lock.release()
        # 确保在主线程中执行UI更新
        try:
            if not self.is_embedded and self.root:
                self.root.after_idle(update_ui)
            elif self.is_embedded and self.parent_frame:
                self.parent_frame.winfo_toplevel().after_idle(update_ui)
            else:
                update_ui()
        except Exception:
            update_ui()
    
    def _schedule_single_field_ui_update(self, table_id, field_name, field_data, receive_timestamp=None):
        """调度单个字段的UI更新到主线程"""
        # 确保在主线程中执行UI更新
        try:
            if not self.is_embedded and self.root:
                self.root.after_idle(lambda: self._update_single_field_ui(table_id, field_name, field_data, receive_timestamp))
            elif self.is_embedded and self.parent_frame:
                self.parent_frame.winfo_toplevel().after_idle(lambda: self._update_single_field_ui(table_id, field_name, field_data, receive_timestamp))
            else:
                self._update_single_field_ui(table_id, field_name, field_data, receive_timestamp)
        except Exception:
            self._update_single_field_ui(table_id, field_name, field_data, receive_timestamp)
    
    def _update_single_field_ui(self, table_id, field_name, field_data, receive_timestamp=None):
        """执行单个字段的UI更新"""
        try:
            if table_id in self.data_tables:
                # 使用display_data方法，将单个字段包装成字典格式
                self.data_tables[table_id].display_data({field_name: field_data}, timestamp=receive_timestamp)
                #self.log_message(f"Field {field_name} in table {table_id} updated successfully")
                
                # 处理特殊字段的额外逻辑
                if field_name == "mcu_read_data":
                    # 获取当前mcu_read_address的值
                    mcu_read_address_value = None
                    if table_id in self.data_tables and "mcu_read_address" in self.data_tables[table_id].entries:
                        addr_str = self.data_tables[table_id].entries["mcu_read_address"][0].get()
                        if addr_str and addr_str != "Err" and addr_str != "--":
                            try:
                                if addr_str.startswith('0x') or addr_str.startswith('0X'):
                                    mcu_read_address_value = int(addr_str, 16)
                                else:
                                    mcu_read_address_value = int(addr_str)
                            except ValueError:
                                pass
                    
                    # 直接使用update_values_from_model_data方法
                    if hasattr(self, 'uart_command_frame') and mcu_read_address_value is not None:
                        mock_model_data = {
                            'mcu_read_address': {
                                'raw_value': mcu_read_address_value,
                                'value': mcu_read_address_value
                            },
                            'mcu_read_data': field_data
                        }
                        self.uart_command_frame.update_values_from_model_data(mock_model_data)
                            
        except Exception as e:
            self.log_message(f"Single field UI update error for {field_name} in table {table_id}: {e}")


    
    def _log_overview_data(self):
        """打印Overview字段数据到日志"""
        try:
            if not self._overview_log_enabled or not hasattr(self, 'overview_frame'):
                return
            
            # 检查是否已连接且扫描了模型
            if not self.modbus_client.is_connected() or not self.is_scan_model_addr:
                return
            
            # 收集Overview字段的当前数据
            overview_data = []
            
            # 遍历Overview框架中定义的字段
            for model_id, fields in self.overview_frame.overview_fields.items():
                for field_info in fields:
                    field_name = field_info["name"]
                    field_label = field_info["label"]
                    
                    # 获取字段的当前值
                    key = f"{model_id}_{field_name}"
                    if key in self.overview_frame.entries:
                        entry = self.overview_frame.entries[key]
                        current_value = entry['value_var'].get()
                        current_time = entry['time_var'].get()
                        
                        # 只记录有效数据（不是默认的"-"或"--"）
                        if current_value not in ['-', '--', 'Err']:
                            # 特殊处理Alarms字段，显示详细的位标志
                            if field_name == "Alarms" and model_id == 64900:
                                detailed_alarms = self._get_alarms_from_bitfield(key, current_value)
                                overview_data.append(f"{field_label}: {detailed_alarms}")
                            else:
                                overview_data.append(f"{field_label}: {current_value}")
            
            # 如果有数据，打印到日志
            if overview_data:
                log_message = "Overview data: " + ", ".join(overview_data)
                self.log_message(log_message)
            else:
                self.log_message("Overview data: No valid data")
            
        except Exception as e:
            self.log_message(f"Overview data print error: {e}")
    


    def _get_alarms_from_bitfield(self, parent_key, alarms_value):
        """从Overview页面已解析的bitfield数据获取Alarms详细信息"""
        try:
            # 直接使用Overview页面已经解析好的bitfield数据
            if hasattr(self, 'overview_frame') and hasattr(self.overview_frame, 'bitfield_entries'):
                if parent_key in self.overview_frame.bitfield_entries:
                    # 收集置1的位标志
                    active_alarms = []
                    for bit_name, bit_var in self.overview_frame.bitfield_entries[parent_key].items():
                        bit_value = bit_var.get()
                        if bit_value == "1":  # 位状态为1
                            active_alarms.append(f"{bit_name}:1")
                    
                    # 构建结果字符串
                    if active_alarms:
                        return f"{alarms_value}, {', '.join(active_alarms)}"
                    else:
                        return alarms_value
            
            # 如果无法从bitfield获取，返回原始值
            return alarms_value
                
        except Exception as e:
            # 如果获取失败，返回原始值
            return str(alarms_value)

    def on_closing(self):
        """程序关闭处理 - 线程安全版本"""
        try:
            # 立即停止所有定时器
            if hasattr(self, '_log_timer') and self._log_timer:
                try:
                    if not self.is_embedded and self.root:
                        self.root.after_cancel(self._log_timer)
                    elif self.is_embedded and self.parent_frame:
                        self.parent_frame.winfo_toplevel().after_cancel(self._log_timer)
                except Exception:
                    pass
                self._log_timer = None
            
            # 关闭Excel记录器
            # if hasattr(self, 'excel_recorder'):
            #     self.excel_recorder.close()
            
            # 使用非阻塞方式停止自动读取
            with self._auto_read_lock:
                self._auto_read_all_running = False
            self._stop_auto_read("user", "Application closing")
            
            # 立即停止所有通信操作
            self._cancel_all_operations()
            
            # 非阻塞方式等待线程结束
            if hasattr(self, 'auto_read_thread') and self.auto_read_thread.is_alive():
                # 给线程一些时间自然结束，但不阻塞UI
                if not self.is_embedded and self.root:
                    self.root.after(100, self._delayed_cleanup)
                else:
                    self._complete_cleanup()
            else:
                self._complete_cleanup()
                
        except Exception as e:
            print(f"关闭处理错误: {e}")
            self._force_cleanup()
    
    def _delayed_cleanup(self):
        """延迟清理，确保线程有时间结束"""
        try:
            self._complete_cleanup()
        except Exception as e:
            print(f"Delayed cleanup error: {e}")
            # 强制清理
            self._force_cleanup()
    
    def _complete_cleanup(self):
        """完成清理过程"""
        self.stop_parse_thread()
        self.stop_communication_thread()
        self.modbus_client.disconnect()
        # 只在独立模式下销毁root
        if not self.is_embedded and self.root:
            self.root.destroy()
    
    def _force_cleanup(self):
        """强制清理，用于异常情况"""
        try:
            if not self.is_embedded and self.root:
                self.root.destroy()
        except Exception:
            pass

def main():
    # 独立运行模式
    app = SunSpecGUI()
    app.run()

def create_embedded_instance(parent_frame, status_var=None, initial_language=None):
    """创建嵌入模式的实例，用于统一工具管理器"""
    return SunSpecGUI(parent_frame, status_var, initial_language)

if __name__ == "__main__":
    main()