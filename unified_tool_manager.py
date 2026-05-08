#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一工具管理器 - 集成CAN、Modbus、UART三个工具
使用标签页方式，每个工具占用一个标签页
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
# 移除LanguageManager导入，改为直接调用各工具的set_language方法
import os
import threading
import traceback
import time
import concurrent.futures

# 工具导入策略：默认只导入/加载 Modbus；CAN/UART 在用户勾选时再按需导入
can_tool_available = None   # None=未检测, True=可用, False=不可用
modbus_tool_available = None
uart_tool_available = None

# 添加工具目录到Python路径（不再打印，避免启动日志刷屏）
current_dir = os.path.dirname(os.path.abspath(__file__))
for tool_dir in [
    os.path.join(current_dir, 'can_tool'),
    os.path.join(current_dir, 'mobus_tool'),
    os.path.join(current_dir, 'uart_test')
]:
    if tool_dir not in sys.path:
        sys.path.insert(0, tool_dir)

# 仅预导入 Modbus（因为它固定加载）
try:
    # 调试：检查 serial 模块是否可用
    try:
        import serial
        print(f"DEBUG: serial module found at: {serial.__file__}")
        print(f"DEBUG: serial version: {serial.__version__}")
    except ImportError as serial_err:
        print(f"DEBUG: serial module NOT found: {serial_err}")
        print(f"DEBUG: sys.path = {sys.path[:3]}")  # 只打印前3个路径

    from mobus_tool.main import create_embedded_instance as create_modbus_embedded
    modbus_tool_available = True
except ImportError as e:
    print(f"Modbus工具导入失败: {e}")
    import traceback
    print(f"详细错误信息:\n{traceback.format_exc()}")
    modbus_tool_available = False

# CAN/UART 的 create_* 在运行时按需导入（见 _ensure_tool_imported）
create_can_embedded = None
create_uart_embedded = None

version = "V1.0.25"
date = "2026-05-09"

class UnifiedToolManager:
    """统一工具管理器"""
    
    def __init__(self):
        # 记录 notebook tab id，便于按需移除
        self._tool_tabs = {}
        self.root = tk.Tk()
        self.root.title("BMS Test Bench-"+version+"-"+date)#主窗口标题
        
        # 设置窗口大小和位置
        window_width = 1600
        window_height = 1000
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.minsize(1200, 800)
        
        # 设置窗口图标
        self.set_window_icon()
        
        # 工具实例字典
        self.tools = {}
        
        # 当前活跃标签页跟踪
        self.current_active_tab = None
        self.tab_visibility_state = {}  # 记录每个标签页的可见状态
        
        # 创建主界面
        self.create_main_interface()
        
        # Notebook 占位页（当没有任何工具加载时显示，避免界面错乱）
        self._placeholder_tab = None
        self._ensure_placeholder_tab()

        # 初始化工具（默认仅 Modbus）
        self.initialize_tools()
        
        # 初始化 Tool Status 勾选框状态（modbus 无勾选框，始终加载）
        try:
            self.tool_load_vars['uart'].set('uart' in self.tools)
            self.tool_load_vars['can'].set('can' in self.tools)
        except Exception:
            pass
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 添加窗口大小调整优化
        self.setup_resize_optimization()
        
        # 初始化定时器变量
        self._refresh_timer = None
    
    def setup_resize_optimization(self):
        """设置窗口大小调整优化"""
        try:
            # 窗口大小调整防抖机制
            self._resize_timer = None
            self._is_resizing = False
            
            # 绑定窗口配置事件
            self.root.bind('<Configure>', self.on_window_configure)
            
        except Exception as e:
            print(f"设置窗口调整优化失败: {e}")
    
    def on_window_configure(self, event):
        """窗口配置改变事件处理 - 防抖版本"""
        try:
            # 只处理主窗口的事件
            if event.widget != self.root:
                return
            
            # 防抖机制：取消之前的定时器
            if hasattr(self, '_resize_timer') and self._resize_timer:
                self.root.after_cancel(self._resize_timer)
                self._resize_timer = None
            
            # 设置新的定时器，延迟处理调整
            self._resize_timer = self.root.after(300, self.handle_window_resize)
            
        except Exception as e:
            print(f"窗口配置事件处理错误: {e}")
    
    def handle_window_resize(self):
        """处理窗口大小调整"""
        try:
            if self._is_resizing:
                return
                
            self._is_resizing = True
            
            # 轻量级的窗口调整处理
            current_tab = self.notebook.select()
            if current_tab:
                # 只更新当前可见标签页的关键元素
                tab_widget = self.notebook.nametowidget(current_tab)
                tab_widget.update_idletasks()
            
            # 重置标志
            self._is_resizing = False
            # 清理定时器引用
            if hasattr(self, '_resize_timer'):
                self._resize_timer = None
            
        except Exception as e:
            print(f"处理窗口大小调整错误: {e}")
            self._is_resizing = False
            # 清理定时器引用
            if hasattr(self, '_resize_timer'):
                self._resize_timer = None
    
    def set_window_icon(self):
        """设置窗口图标（兼容开发环境与PyInstaller打包）"""
        try:
            base_paths = []
            # PyInstaller 运行时目录
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_paths.append(sys._MEIPASS)
            # 脚本所在目录
            base_paths.append(os.path.dirname(os.path.abspath(__file__)))
            # 当前工作目录
            base_paths.append(os.getcwd())
            
            candidate_names = [
                'BQC.ico',
                os.path.join('can_tool', 'BQC.ico'),
                os.path.join('mobus_tool', 'BQC.ico'),
                os.path.join('uart_test', 'BQC.ico'),
            ]
            
            for base in base_paths:
                for name in candidate_names:
                    icon_path = os.path.join(base, name)
                    if os.path.exists(icon_path):
                        self.root.iconbitmap(icon_path)
                        return
        except Exception as e:
            print(f"设置窗口图标失败: {e}")
    
    def create_main_interface(self):
        """创建主界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="5")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 使用 grid 三行：标题 + Notebook + 底部区域
        main_frame.grid_rowconfigure(1, weight=1)  # Notebook 行可伸缩
        main_frame.grid_columnconfigure(0, weight=1)

        # 标题
        # title_label = ttk.Label(
        #     main_frame, text="BMS Test Bench", font=("Arial", 16, "bold")
        # )
        # title_label.grid(row=0, column=0, pady=(0, 10), sticky="n")

        # Notebook（可压缩）
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        # 底部框架：语言 + 工具状态
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))

        # 底部框架内部再分两行：语言栏 + 工具状态指示器
        bottom_frame.grid_rowconfigure(0, weight=0)
        bottom_frame.grid_rowconfigure(1, weight=0)
        bottom_frame.grid_columnconfigure(0, weight=1)

        # 统一的语言切换控件
        self.create_unified_language_control(bottom_frame)

        # 工具状态指示器
        self.create_tool_status_indicator(bottom_frame)

        # 状态栏（固定在最底部，独立 pack）
        self.status_var = tk.StringVar(value="Ready - Please select a tool tab")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 绑定标签页切换事件
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # 允许通过点击未加载的 Tab 名称来提示用户在 Tool Status 勾选加载
        # （目前未创建未加载工具的tab，因此无需额外处理）

    def _ensure_placeholder_tab(self):
        """确保 notebook 至少有一个可见页；当没有任何工具加载时显示占位页。"""
        try:
            # 如果有任何工具tab，移除占位页
            if any(k in self._tool_tabs for k in ('modbus', 'uart', 'can')):
                self._remove_placeholder_tab()
                return

            if self._placeholder_tab is None:
                frame = ttk.Frame(self.notebook)
                label = ttk.Label(
                    frame,
                    text="No tool loaded. Please select tools to load in 'Tool Status'.",
                    font=("Arial", 12),
                    foreground="gray"
                )
                label.pack(expand=True)
                self.notebook.add(frame, text="Home")
                self._placeholder_tab = frame

            # 选中占位页
            try:
                self.notebook.select(self._placeholder_tab)
            except Exception:
                pass
        except Exception as e:
            print(f"ensure placeholder tab failed: {e}")

    def _remove_placeholder_tab(self):
        """如果占位页存在则移除"""
        try:
            if self._placeholder_tab is not None:
                try:
                    self.notebook.forget(self._placeholder_tab)
                except Exception:
                    pass
                self._placeholder_tab = None
        except Exception as e:
            print(f"remove placeholder tab failed: {e}")

    def _ensure_tool_imported(self, tool_key: str) -> bool:
        """按需导入 CAN/UART。

        返回：True=可用；False=不可用。
        """
        global can_tool_available, uart_tool_available, create_can_embedded, create_uart_embedded

        if tool_key == 'can':
            if can_tool_available is True and create_can_embedded is not None:
                return True
            if can_tool_available is False:
                return False
            try:
                from can_tool.can_host_computer import create_embedded_instance as _create
                create_can_embedded = _create
                can_tool_available = True
                return True
            except ImportError as e:
                print(f"CAN工具导入失败: {e}")
                can_tool_available = False
                return False

        if tool_key == 'uart':
            if uart_tool_available is True and create_uart_embedded is not None:
                return True
            if uart_tool_available is False:
                return False
            try:
                from uart_test.uart_gui import create_embedded_instance as _create
                create_uart_embedded = _create
                uart_tool_available = True
                return True
            except ImportError as e:
                print(f"UART工具导入失败: {e}")
                uart_tool_available = False
                return False

        return False

    def create_tool_status_indicator(self, parent_frame):
        """创建工具状态指示器（含按需加载勾选框）"""
        status_frame = ttk.LabelFrame(parent_frame, text="Tool Status", padding="5")
        status_frame.pack(fill="x", pady=(0, 10))

        # 勾选框变量：是否加载
        self.tool_load_vars = {
            'can': tk.BooleanVar(value=False),
            # modbus 始终加载，不允许取消
            'uart': tk.BooleanVar(value=False)
        }

        # CAN
        self.can_load_cb = ttk.Checkbutton(
            status_frame,
            text="Load",
            variable=self.tool_load_vars['can'],
            command=lambda: self.on_toggle_tool('can')
        )
        self.can_load_cb.pack(side="left", padx=(10, 2))
        self.can_status_label = ttk.Label(status_frame, text="CAN Tool: Not Initialized", foreground="orange")
        self.can_status_label.pack(side="left", padx=(0, 15))

        # Modbus（默认加载且不可取消）
        self.modbus_status_label = ttk.Label(status_frame, text="Modbus Tool: Not Initialized", foreground="orange")
        self.modbus_status_label.pack(side="left", padx=(10, 15))

        # UART
        self.uart_load_cb = ttk.Checkbutton(
            status_frame,
            text="Load",
            variable=self.tool_load_vars['uart'],
            command=lambda: self.on_toggle_tool('uart')
        )
        self.uart_load_cb.pack(side="left", padx=(10, 2))
        self.uart_status_label = ttk.Label(status_frame, text="UART Tool: Not Initialized", foreground="orange")
        self.uart_status_label.pack(side="left", padx=(0, 15))

        # 启动阶段不预导入 CAN/UART，因此这里不禁用；在用户勾选时再尝试导入
        # （若导入失败，会自动取消勾选并显示 Unavailable）
    
    def create_disabled_tab(self, tab_name, message):
        """创建禁用的标签页"""
        try:
            # 创建标签页
            disabled_frame = ttk.Frame(self.notebook)
            self.notebook.add(disabled_frame, text=tab_name)
            
            # 显示禁用信息
            info_label = ttk.Label(disabled_frame, text=message, 
                                  font=("Arial", 12), foreground="red")
            info_label.pack(expand=True)
            
            # 添加说明
            desc_label = ttk.Label(disabled_frame, 
                                  text="Please check module dependencies and configuration files",
                                  font=("Arial", 10))
            desc_label.pack(pady=(10, 0))
            
        except Exception as e:
            print(f"创建禁用标签页失败: {e}")
    
    def create_unified_language_control(self, parent_frame):
        """创建统一的语言切换控件"""
        lang_frame = ttk.LabelFrame(parent_frame, text="Language Settings", padding="5")
        lang_frame.pack(fill="x", pady=(0, 10))
        
        # 语言选择（只读显示）
        ttk.Label(lang_frame, text="Language:").pack(side=tk.LEFT, padx=(0, 5))
        self.lang_var = tk.StringVar(value="zh")
        self.lang_label = ttk.Label(lang_frame, textvariable=self.lang_var, width=8,relief="solid",background="white")
        self.lang_label.pack(side=tk.LEFT, padx=(0, 5))
        # 语言切换按钮
        self.lang_btn = ttk.Button(lang_frame, text="Switch Language", command=self.toggle_language)
        self.lang_btn.pack(side=tk.LEFT, padx=(10, 0))
    
    def on_tab_changed(self, event=None):
        """标签页切换事件处理 - 优化版本，只更新当前页面"""
        try:
            # 获取当前选中的标签页索引
            current_tab = self.notebook.select()
            if current_tab:
                # 更新状态栏
                tab_text = self.notebook.tab(current_tab, "text")
                self.status_var.set(f"Current Tool: {tab_text}")
                
                # 更新标签页可见状态
                old_active_tab = self.current_active_tab
                self.current_active_tab = tab_text
                
                # 通知旧标签页变为非活跃状态
                if old_active_tab and old_active_tab != tab_text:
                    self.set_tab_visibility(old_active_tab, False)
                
                # 通知新标签页变为活跃状态
                self.set_tab_visibility(tab_text, True)
        except Exception as e:
            print(f"标签页切换处理错误: {e}")
    
    def set_tab_visibility(self, tab_text, is_visible):
        """设置标签页的可见状态"""
        try:
            self.tab_visibility_state[tab_text] = is_visible
            
            # 只设置工具的_ui_active标志位，不调用其他方法
            if "UART" in tab_text and 'uart' in self.tools and self.tools.get('uart') is not None:
                uart_wrapper = self.tools['uart']
                if hasattr(uart_wrapper, 'uart_tool') and uart_wrapper.uart_tool:
                    uart_wrapper.uart_tool._ui_active = is_visible
            elif "CAN" in tab_text and 'can' in self.tools and self.tools.get('can') is not None:
                can_wrapper = self.tools['can']
                if hasattr(can_wrapper, 'can_tool') and can_wrapper.can_tool:
                    can_wrapper.can_tool._ui_active = is_visible
            elif "Modbus" in tab_text and 'modbus' in self.tools and self.tools.get('modbus') is not None:
                modbus_wrapper = self.tools['modbus']
                if hasattr(modbus_wrapper, 'modbus_tool') and modbus_wrapper.modbus_tool:
                    modbus_wrapper.modbus_tool._ui_active = is_visible
                
        except Exception as e:
            print(f"设置标签页可见状态错误: {e}")
    
    def is_tab_active(self, tab_name):
        """检查标签页是否为当前活跃状态"""
        return self.tab_visibility_state.get(tab_name, False)
    
    def toggle_language(self):
        """切换语言 - 优化版本，添加防抖机制"""
        # 防抖机制，避免频繁切换
        if hasattr(self, '_language_switching') and self._language_switching:
            return
            
        try:
            self._language_switching = True
            current_lang = self.lang_var.get()
            new_lang = "en" if current_lang == "zh" else "zh"
            self.lang_var.set(new_lang)
            
            # 延迟执行语言切换，避免UI阻塞
            self.root.after(100, lambda: self.change_all_tools_language_async(new_lang))
            
        except Exception as e:
            print(f"语言切换错误: {e}")
            self._language_switching = False
    
    def change_all_tools_language_async(self, language):
        """异步改变所有工具的语言"""
        try:
            print(f"开始异步切换语言到: {language}")
            
            def change_language_worker():
                try:                   
                    # 使用线程池并行处理所有工具的语言切换
                    tools_to_update = []
                    
                    # 收集需要更新的工具
                    if 'can' in self.tools and self.tools['can'].can_tool:
                        if hasattr(self.tools['can'].can_tool, 'set_language'):
                            tools_to_update.append(('CAN', self.tools['can'].can_tool))
                    
                    if 'modbus' in self.tools and self.tools['modbus'].modbus_tool:
                        if hasattr(self.tools['modbus'].modbus_tool, 'set_language'):
                            tools_to_update.append(('Modbus', self.tools['modbus'].modbus_tool))
                    
                    if 'uart' in self.tools and self.tools['uart'].uart_tool:
                        if hasattr(self.tools['uart'].uart_tool, 'set_language'):
                            tools_to_update.append(('UART', self.tools['uart'].uart_tool))
                    
                    # 并行执行语言切换
                    def update_tool_language(tool_info):
                        tool_name, tool_instance = tool_info
                        try:
                            tool_instance.set_language(language)
                            return f"{tool_name}工具语言切换完成"
                        except Exception as e:
                            return f"{tool_name}工具语言切换失败: {e}"
                    
                    # 使用ThreadPoolExecutor并行处理
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        future_to_tool = {executor.submit(update_tool_language, tool): tool[0] for tool in tools_to_update}
                        
                        for future in concurrent.futures.as_completed(future_to_tool):
                            result = future.result()
                            print(result)
                    
                    # 在主线程中更新状态
                    self.root.after(0, lambda: self.finalize_language_change(language))
                    
                except Exception as e:
                    print(f"语言切换工作线程错误: {e}")
                    self.root.after(0, lambda: self.finalize_language_change(language, error=str(e)))
            
            # 在后台线程中执行语言切换
            threading.Thread(target=change_language_worker, daemon=True).start()
            
        except Exception as e:
            print(f"异步语言切换错误: {e}")
            self.finalize_language_change(language, error=str(e))
    
    def _apply_language_to_tool(self, tool_key: str):
        """给“刚加载”的工具同步当前语言。

        现象：先切换为英文，再勾选加载 UART/CAN 时，它们会用默认中文初始化。
        这里在工具创建后立刻调用对应 set_language()。
        """
        try:
            language = self.lang_var.get()

            if tool_key == 'can' and self.tools.get('can') is not None:
                inst = getattr(self.tools['can'], 'can_tool', None)
                if inst and hasattr(inst, 'set_language'):
                    inst.set_language(language)

            if tool_key == 'uart' and self.tools.get('uart') is not None:
                inst = getattr(self.tools['uart'], 'uart_tool', None)
                if inst and hasattr(inst, 'set_language'):
                    inst.set_language(language)

            if tool_key == 'modbus' and self.tools.get('modbus') is not None:
                inst = getattr(self.tools['modbus'], 'modbus_tool', None)
                if inst and hasattr(inst, 'set_language'):
                    inst.set_language(language)

        except Exception as e:
            print(f"Apply language to {tool_key} failed: {e}")

    def finalize_language_change(self, language, error=None):
        """完成语言切换"""
        try:
            if error:
                self.status_var.set(f"Language switch failed: {error}")
                print(f"语言切换失败: {error}")
            else:
                self.status_var.set(f"Language switched to: {language}")
                print(f"All tools language switched to: {language}")
            
            # 重置切换标志
            self._language_switching = False
            
        except Exception as e:
            print(f"完成语言切换时出错: {e}")
            self._language_switching = False
    
    def initialize_tools(self):
        """初始化工具 - 默认仅加载 Modbus，其它工具按需加载"""
        try:
            tools_initialized = 0

            # 默认仅初始化 Modbus 工具
            if modbus_tool_available:
                try:
                    self.init_modbus_tool()
                    tools_initialized += 1
                    self.modbus_status_label.config(text="Modbus Tool: Loaded", foreground="green")
                except Exception as e:
                    print(f"Modbus工具初始化失败: {e}")
                    self.create_disabled_tab("Modbus Tool", f"Modbus Tool initialization failed:\n{str(e)}")
                    self.modbus_status_label.config(text="Modbus Tool: Failed", foreground="red")
            else:
                self.create_disabled_tab("Modbus Tool", "Modbus Tool module not available")
                self.modbus_status_label.config(text="Modbus Tool: Unavailable", foreground="red")

            # UART/CAN 默认不加载（仅更新状态文本，允许用户勾选后加载）
            if uart_tool_available:
                self.uart_status_label.config(text="UART Tool: Not Loaded", foreground="orange")
            else:
                self.uart_status_label.config(text="UART Tool: Unavailable", foreground="red")

            if can_tool_available:
                self.can_status_label.config(text="CAN Tool: Not Loaded", foreground="orange")
            else:
                self.can_status_label.config(text="CAN Tool: Unavailable", foreground="red")

            if tools_initialized > 0:
                self.status_var.set(f"{tools_initialized} tools initialized successfully")
            else:
                self.status_var.set("No available tools")
                messagebox.showwarning("Warning", "No available tool modules")

        except Exception as e:
            error_msg = f"Tool initialization failed: {str(e)}"
            self.status_var.set(error_msg)
            messagebox.showerror("Initialization Error", error_msg)
            print(traceback.format_exc())
    
    def init_modbus_delayed(self, tools_initialized):
        """延迟初始化Modbus工具（已废弃：改为按需加载）"""
        return
    
    def init_can_delayed(self, tools_initialized):
        """延迟初始化CAN工具（已废弃：改为按需加载）"""
        # 保留空实现，避免旧调用残留导致报错
        return
    
    def init_can_tool(self):
        """初始化CAN工具"""
        try:
            # 已加载则直接返回（需同时存在tab记录，避免"工具实例残留/占位页切换"导致误判）
            if self.tools.get('can') is not None and self._tool_tabs.get('can') is not None:
                return

            # 若之前tab残留被移除，确保不会误用旧frame
            self._remove_placeholder_tab()

            # 创建CAN工具的标签页
            can_frame = ttk.Frame(self.notebook)
            self.notebook.add(can_frame, text="CAN Tool")
            self._tool_tabs['can'] = can_frame
            
            # 获取当前语言设置
            current_language = self.lang_var.get()
            
            # 创建CAN工具实例（使用嵌入模式），传递当前语言
            can_tool = CANToolWrapper(can_frame, current_language)
            self.tools['can'] = can_tool
            
            self.status_var.set("CAN Tool initialization completed")
            
        except Exception as e:
            error_msg = f"CAN Tool initialization failed: {str(e)}"
            self.status_var.set(error_msg)
            print(f"CAN Tool error: {error_msg}")
            print(traceback.format_exc())
    
    def init_modbus_tool(self):
        """初始化Modbus工具"""
        try:
            # 已加载则直接返回（需同时存在tab记录，避免误判导致 parent_frame=None）
            if self.tools.get('modbus') is not None and self._tool_tabs.get('modbus') is not None:
                return

            self._remove_placeholder_tab()

            # 创建Modbus工具的标签页
            modbus_frame = ttk.Frame(self.notebook)
            self.notebook.add(modbus_frame, text="Modbus Tool")
            self._tool_tabs['modbus'] = modbus_frame
            
            # 获取当前语言设置
            current_language = self.lang_var.get()
            
            # 创建Modbus工具实例，传递当前语言
            modbus_tool = ModbusToolWrapper(modbus_frame, self, current_language)
            self.tools['modbus'] = modbus_tool
            
            self.status_var.set("Modbus Tool initialization completed")
            
        except Exception as e:
            error_msg = f"Modbus Tool initialization failed: {str(e)}"
            self.status_var.set(error_msg)
            print(f"Modbus Tool error: {error_msg}")
            print(traceback.format_exc())
            # 添加错误显示到界面
            self.create_disabled_tab("Modbus Tool", f"Modbus Tool initialization failed:\n{str(e)}")
    
    def init_uart_tool(self):
        """初始化UART工具"""
        try:
            # 已加载则直接返回（需同时存在tab记录）
            if self.tools.get('uart') is not None and self._tool_tabs.get('uart') is not None:
                return

            self._remove_placeholder_tab()

            # 创建UART工具的标签页
            uart_frame = ttk.Frame(self.notebook)
            self.notebook.add(uart_frame, text="UART Tool")
            self._tool_tabs['uart'] = uart_frame
            
            # 创建UART工具实例
            uart_tool = UARTToolWrapper(uart_frame, self)
            self.tools['uart'] = uart_tool

            # 新加载的工具需要同步当前语言
            self._apply_language_to_tool('uart')
            
            self.status_var.set("UART Tool initialization completed")
            
        except Exception as e:
            error_msg = f"UART Tool initialization failed: {str(e)}"
            self.status_var.set(error_msg)
            print(f"UART Tool error: {error_msg}")
            print(traceback.format_exc())
    
    def on_toggle_tool(self, tool_key: str):
        """Tool Status 勾选框回调：按需加载/卸载工具"""
        try:
            var = self.tool_load_vars.get(tool_key)
            if var is None:
                # modbus 等无勾选框工具不会走到这里
                return
            want_load = bool(var.get())

            if want_load:
                # 加载
                self._remove_placeholder_tab()

                if tool_key == 'uart':
                    if not self._ensure_tool_imported('uart'):
                        self.uart_status_label.config(text="UART Tool: Unavailable", foreground="red")
                        self.tool_load_vars['uart'].set(False)
                        return
                    self.init_uart_tool()
                    self.uart_status_label.config(text="UART Tool: Loaded", foreground="green")

                elif tool_key == 'can':
                    if not self._ensure_tool_imported('can'):
                        self.can_status_label.config(text="CAN Tool: Unavailable", foreground="red")
                        self.tool_load_vars['can'].set(False)
                        return
                    self.init_can_tool()
                    self.can_status_label.config(text="CAN Tool: Loaded", foreground="green")

            else:
                # 卸载
                self.unload_tool(tool_key)

        except Exception as e:
            print(f"切换工具{tool_key}加载状态失败: {e}")
            print(traceback.format_exc())

    def unload_tool(self, tool_key: str):
        """卸载工具：cleanup + remove tab + remove from dict"""
        try:
            # 先切换到其它 tab，避免当前 tab 被移除导致异常
            try:
                if self.notebook.index('end') > 0:
                    current = self.notebook.select()
                    if current and tool_key in self._tool_tabs and self._tool_tabs[tool_key] == self.notebook.nametowidget(current):
                        # 切到第一个 tab
                        self.notebook.select(0)
            except Exception:
                pass

            tool = self.tools.get(tool_key)
            if tool is not None:
                try:
                    if hasattr(tool, 'cleanup'):
                        tool.cleanup()
                    elif hasattr(tool, 'disconnect'):
                        tool.disconnect()
                except Exception as e:
                    print(f"卸载{tool_key}工具清理失败: {e}")

            # 移除 tab
            tab = self._tool_tabs.get(tool_key)
            if tab is not None:
                try:
                    self.notebook.forget(tab)
                except Exception:
                    pass
                self._tool_tabs.pop(tool_key, None)

            # 移除工具实例引用
            self.tools.pop(tool_key, None)

            # 更新状态文本
            if tool_key == 'modbus':
                self.modbus_status_label.config(text="Modbus Tool: Not Loaded", foreground="orange")
            elif tool_key == 'uart':
                self.uart_status_label.config(text="UART Tool: Not Loaded", foreground="orange")
            elif tool_key == 'can':
                self.can_status_label.config(text="CAN Tool: Not Loaded", foreground="orange")

            # 如果全部工具都卸载了，确保占位页存在
            self._ensure_placeholder_tab()

        except Exception as e:
            print(f"卸载工具{tool_key}失败: {e}")

    def on_closing(self):
        """窗口关闭事件处理"""
        try:
            # 清理所有定时器
            if hasattr(self, '_resize_timer') and self._resize_timer:
                self.root.after_cancel(self._resize_timer)
                self._resize_timer = None
                
            if hasattr(self, '_refresh_timer') and self._refresh_timer:
                self.root.after_cancel(self._refresh_timer)
                self._refresh_timer = None
            
            # 关闭所有工具
            for tool_name, tool in list(self.tools.items()):
                try:
                    if hasattr(tool, 'cleanup'):
                        tool.cleanup()
                    elif hasattr(tool, 'disconnect'):
                        tool.disconnect()
                except Exception as e:
                    print(f"关闭{tool_name}工具时出错: {e}")
            
            # 销毁主窗口
            self.root.destroy()
            
        except Exception as e:
            print(f"关闭程序时出错: {e}")
            self.root.destroy()
    
    def run(self):
        """运行主程序 - 增强版本，增加全局异常捕获"""
        try:
            # 设置全局异常处理器
            import sys
            import traceback
            
            def handle_exception(exc_type, exc_value, exc_traceback):
                """Global exception handler"""
                if issubclass(exc_type, KeyboardInterrupt):
                    # 允许Ctrl+C正常退出
                    sys.__excepthook__(exc_type, exc_value, exc_traceback)
                    return
                
                error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                print(f"Uncaught exception: {error_msg}")
                
                # 记录到文件
                with open('error_crash_log.txt', 'w', encoding='utf-8') as f:
                    f.write(f"Crash time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Exception: {error_msg}\n")
                
                # 显示错误对话框
                try:
                    messagebox.showerror("Unexpected Error", 
                                       f"An unexpected error occurred:\n{exc_value}\n\n" +
                                       "Error details have been saved to error_crash_log.txt")
                except:
                    pass
                
                # 尝试清理资源
                try:
                    self.on_closing()
                except:
                    pass
            
            # 设置全局异常处理器
            sys.excepthook = handle_exception
            
            # 启动主循环
            self.root.mainloop()
            
        except Exception as e:
            print(f"主程序运行错误: {e}")
            print(traceback.format_exc())
            try:
                messagebox.showerror("Startup Error", f"Program failed to start:\n{str(e)}")
            except:
                print("Failed to show error dialog")


class CANToolWrapper:
    """CAN工具包装器"""
    
    def __init__(self, parent_frame, initial_language=None):
        self.parent_frame = parent_frame
        self.initial_language = initial_language
        self.can_tool = None
        self.init_can_tool()
    
    def init_can_tool(self):
        """初始化CAN工具"""
        try:
            # 创建CAN工具实例（使用嵌入模式），传递初始语言
            self.can_tool = create_can_embedded(self.parent_frame, self.initial_language)
            print("CAN工具实例创建成功")
            
            # 检查工具是否成功创建
            if self.can_tool and hasattr(self.can_tool, 'main_frame'):
                print("CAN工具界面创建成功")
                # 工具已经直接使用传入的父框架，无需重新打包
            else:
                print("CAN工具界面创建失败，使用简化界面")
                self.create_simple_can_interface()
                
        except Exception as e:
            # 如果初始化失败，显示错误信息
            error_label = ttk.Label(self.parent_frame, 
                                  text=f"CAN Tool initialization failed:\n{str(e)}",
                                  foreground="red")
            error_label.pack(expand=True)
            print(f"CAN Tool initialization error: {e}")
    
    def create_simple_can_interface(self):
        """创建简化的CAN工具界面"""
        try:
            # 创建标题
            title_label = ttk.Label(self.parent_frame, text="CAN Tool", 
                                   font=("Arial", 14, "bold"))
            title_label.pack(pady=(10, 20))
            
            # 创建说明标签
            info_label = ttk.Label(self.parent_frame, 
                                  text="CAN Tool loaded successfully!\n\nDue to interface embedding limitations, it is recommended to run this tool in standalone mode for full functionality.\n\nClick the button below to launch the standalone CAN tool.",
                                  font=("Arial", 10), justify="center")
            info_label.pack(expand=True, pady=20)
            
            # 创建启动按钮
            launch_btn = ttk.Button(self.parent_frame, text="Launch Standalone CAN Tool", 
                                   command=self.launch_standalone_can)
            launch_btn.pack(pady=20)
            
        except Exception as e:
            print(f"Failed to create simplified CAN interface: {e}")
    
    def launch_standalone_can(self):
        """启动独立的CAN工具"""
        try:
            import subprocess
            import os
            can_path = os.path.join(os.path.dirname(__file__), 'can_tool', 'can_host_computer.py')
            subprocess.Popen([sys.executable, can_path])
        except Exception as e:
            print(f"启动独立CAN工具失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.can_tool and hasattr(self.can_tool, 'disconnect_can'):
                self.can_tool.disconnect_can()
        except Exception as e:
            print(f"CAN工具清理错误: {e}")


class ModbusToolWrapper:
    """Modbus工具包装器"""
    
    def __init__(self, parent_frame, main_window, initial_language=None):
        self.parent_frame = parent_frame
        self.main_window = main_window
        self.initial_language = initial_language
        self.modbus_tool = None
        self.init_modbus_tool()
    
    def init_modbus_tool(self):
        """初始化Modbus工具"""
        try:
            # 创建Modbus工具实例（使用嵌入模式），传递初始语言
            self.modbus_tool = create_modbus_embedded(self.parent_frame, self.main_window.status_var, self.initial_language)
            
            # 检查工具是否成功创建
            if self.modbus_tool and hasattr(self.modbus_tool, 'main_frame'):
                print("Modbus工具界面创建成功")
                # 工具已经直接使用传入的父框架，无需重新打包
            else:
                print("Modbus工具界面创建失败，使用简化界面")
                self.create_simple_modbus_interface()
                
        except Exception as e:
            # 如果初始化失败，显示错误信息
            error_label = ttk.Label(self.parent_frame, 
                                  text=f"Modbus Tool initialization failed:\n{str(e)}",
                                  foreground="red")
            error_label.pack(expand=True)
            print(f"Modbus Tool initialization error: {e}")
    
    def create_simple_modbus_interface(self):
        """创建简化的Modbus工具界面"""
        try:
            # 创建标题
            title_label = ttk.Label(self.parent_frame, text="Modbus Tool", 
                                   font=("Arial", 14, "bold"))
            title_label.pack(pady=(10, 20))
            
            # 创建说明标签
            info_label = ttk.Label(self.parent_frame, 
                                  text="Modbus Tool loaded successfully!\n\nDue to interface embedding limitations, it is recommended to run this tool in standalone mode for full functionality.\n\nClick the button below to launch the standalone Modbus tool.",
                                  font=("Arial", 10), justify="center")
            info_label.pack(expand=True, pady=20)
            
            # 创建启动按钮
            launch_btn = ttk.Button(self.parent_frame, text="Launch Standalone Modbus Tool", 
                                   command=self.launch_standalone_modbus)
            launch_btn.pack(pady=20)
            
        except Exception as e:
            print(f"Failed to create simplified interface: {e}")
    
    def launch_standalone_modbus(self):
        """启动独立的Modbus工具"""
        try:
            import subprocess
            import os
            modbus_path = os.path.join(os.path.dirname(__file__), 'mobus_tool', 'main.py')
            subprocess.Popen([sys.executable, modbus_path])
        except Exception as e:
            print(f"启动独立Modbus工具失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.modbus_tool and hasattr(self.modbus_tool, 'on_closing'):
                self.modbus_tool.on_closing()
        except Exception as e:
            print(f"Modbus工具清理错误: {e}")


class UARTToolWrapper:
    """UART工具包装器"""
    
    def __init__(self, parent_frame, main_window):
        self.parent_frame = parent_frame
        self.main_window = main_window
        self.uart_tool = None
        self.init_uart_tool()
    
    def init_uart_tool(self):
        """初始化UART工具"""
        try:
            # 创建UART工具实例（使用嵌入模式）
            self.uart_tool = create_uart_embedded(self.parent_frame)
            
            # 检查工具是否成功创建
            if self.uart_tool and hasattr(self.uart_tool, 'main_frame'):
                print("UART工具界面创建成功")
                # 工具已经直接使用传入的父框架，无需重新打包
            else:
                print("UART工具界面创建失败，使用简化界面")
                self.create_simple_uart_interface()
                
        except Exception as e:
            # 如果初始化失败，显示错误信息
            error_label = ttk.Label(self.parent_frame, 
                                  text=f"UART Tool initialization failed:\n{str(e)}",
                                  foreground="red")
            error_label.pack(expand=True)
            print(f"UART Tool initialization error: {e}")
    
    def create_simple_uart_interface(self):
        """创建简化的UART工具界面"""
        try:
            # 创建标题
            title_label = ttk.Label(self.parent_frame, text="UART Tool", 
                                   font=("Arial", 14, "bold"))
            title_label.pack(pady=(10, 20))
            
            # 创建说明标签
            info_label = ttk.Label(self.parent_frame, 
                                  text="UART Tool loaded successfully!\n\nDue to interface embedding limitations, it is recommended to run this tool in standalone mode for full functionality.\n\nClick the button below to launch the standalone UART tool.",
                                  font=("Arial", 10), justify="center")
            info_label.pack(expand=True, pady=20)
            
            # 创建启动按钮
            launch_btn = ttk.Button(self.parent_frame, text="Launch Standalone UART Tool", 
                                   command=self.launch_standalone_uart)
            launch_btn.pack(pady=20)
            
        except Exception as e:
            print(f"Failed to create simplified interface: {e}")
    
    def launch_standalone_uart(self):
        """启动独立的UART工具"""
        try:
            import subprocess
            import os
            # 使用专门的启动脚本
            uart_path = os.path.join(os.path.dirname(__file__), 'uart_test', 'run_uart_standalone.py')
            if os.path.exists(uart_path):
                subprocess.Popen([sys.executable, uart_path])
            else:
                # 如果启动脚本不存在，使用原来的main.py
                uart_path = os.path.join(os.path.dirname(__file__), 'uart_test', 'main.py')
                subprocess.Popen([sys.executable, uart_path])
        except Exception as e:
            print(f"启动独立UART工具失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if self.uart_tool and hasattr(self.uart_tool, 'uart'):
                self.uart_tool.uart.close()
        except Exception as e:
            print(f"UART工具清理错误: {e}")


def main():
    """主函数"""
    try:
        app = UnifiedToolManager()
        app.run()
    except Exception as e:
        print(f"Program startup failed: {e}")
        print(traceback.format_exc())
        messagebox.showerror("Startup Error", f"Program startup failed:\n{str(e)}")


if __name__ == "__main__":
    main() 