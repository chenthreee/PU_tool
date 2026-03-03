import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
from datetime import datetime
import json
import struct
import ctypes
from ctypes import *
from can_protocol_config import *  # 导入配置文件
from lang_config import LANGUAGES
import sys
import os
import queue
from collections import deque

# 创芯科技CAN API常量
VCI_USBCAN2 = 4
STATUS_OK = 1

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

class VCI_INIT_CONFIG(Structure):  
    _fields_ = [("AccCode", c_uint),
                ("AccMask", c_uint),
                ("Reserved", c_uint),
                ("Filter", c_ubyte),
                ("Timing0", c_ubyte),
                ("Timing1", c_ubyte),
                ("Mode", c_ubyte)
                ]  

class VCI_CAN_OBJ(Structure):  
    _fields_ = [("ID", c_uint),
                ("TimeStamp", c_uint),
                ("TimeFlag", c_ubyte),
                ("SendType", c_ubyte),
                ("RemoteFlag", c_ubyte),
                ("ExternFlag", c_ubyte),
                ("DataLen", c_ubyte),
                ("Data", c_ubyte*8),
                ("Reserved", c_ubyte*3)
                ] 

class VCI_CAN_OBJ_ARRAY(Structure):
    _fields_ = [('SIZE', ctypes.c_uint16), ('STRUCT_ARRAY', ctypes.POINTER(VCI_CAN_OBJ))]

    def __init__(self, num_of_structs):
        self.STRUCT_ARRAY = ctypes.cast((VCI_CAN_OBJ * num_of_structs)(), ctypes.POINTER(VCI_CAN_OBJ))
        self.SIZE = num_of_structs
        self.ADDR = self.STRUCT_ARRAY[0]

class CANalystCANBus:
    """创芯科技CAN总线类"""
    def __init__(self, device_type=VCI_USBCAN2, device_index=0, can_index=0):
        self.device_type = device_type
        self.device_index = device_index
        self.can_index = can_index
        self.can_dll = None
        self.is_connected = False
    
    def get_dll_path(self):
        """获取ControlCAN.dll的正确路径"""
        # 尝试多个可能的路径
        possible_paths = [
            # 当前目录
            './ControlCAN.dll',
            # can_tool目录
            './can_tool/ControlCAN.dll',
            # 脚本所在目录
            os.path.join(os.path.dirname(__file__), 'ControlCAN.dll'),
            # 使用get_resource_path函数
            get_resource_path('ControlCAN.dll'),
            get_resource_path('can_tool/ControlCAN.dll'),
        ]
        
        # 如果在PyInstaller环境中，添加更多路径
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
            possible_paths.extend([
                os.path.join(base_path, 'ControlCAN.dll'),
                os.path.join(base_path, 'can_tool', 'ControlCAN.dll'),
            ])
        
        # 测试每个路径
        for path in possible_paths:
            if os.path.exists(path):
                print(f"找到DLL文件: {path}")
                return path
        
        # 如果都找不到，抛出详细错误
        error_msg = f"无法找到ControlCAN.dll文件。已尝试以下路径:\n"
        for path in possible_paths:
            error_msg += f"  - {path} (存在: {os.path.exists(path)})\n"
        error_msg += f"当前工作目录: {os.getcwd()}\n"
        error_msg += f"脚本目录: {os.path.dirname(__file__)}"
        raise FileNotFoundError(error_msg)
        
    def connect(self, baudrate=500000):
        """连接CAN设备"""
        try:
            print(f"开始连接CAN设备...")
            print(f"设备类型: {self.device_type}, 设备索引: {self.device_index}, CAN索引: {self.can_index}")
            print(f"波特率: {baudrate}")
            
            # 加载DLL - 使用正确的路径解析
            print("正在加载ControlCAN.dll...")
            dll_path = self.get_dll_path()
            self.can_dll = windll.LoadLibrary(dll_path)
            print(f"DLL加载成功: {dll_path}")
            
            # 打开设备
            print("正在打开CAN设备...")
            ret = self.can_dll.VCI_OpenDevice(self.device_type, self.device_index, 0)
            print(f"VCI_OpenDevice返回值: {ret}")
            if ret != STATUS_OK:
                print(f"默认设备打开失败，正在自动检测可用设备...")
                # 尝试自动检测可用设备
                available, dev_type, dev_index = self.check_device_availability()
                if available:
                    print(f"自动切换到可用设备: 类型={dev_type}, 索引={dev_index}")
                    self.device_type = dev_type
                    self.device_index = dev_index
                    # 重新尝试打开设备
                    ret = self.can_dll.VCI_OpenDevice(self.device_type, self.device_index, 0)
                    if ret != STATUS_OK:
                        error_info = self.get_device_error_info()
                        raise Exception(f"open device failed even after switching devices (return value: {ret}). {error_info}")
                else:
                    error_info = self.get_device_error_info()
                    raise Exception(f"no available CAN device. {error_info}")
                
            # 设置波特率
            timing0, timing1 = self.get_timing(baudrate)
            print(f"波特率参数: timing0=0x{timing0:02X}, timing1=0x{timing1:02X}")
            
            # 初始化CAN
            print("正在初始化CAN...")
            vci_initconfig = VCI_INIT_CONFIG(0x80000008, 0xFFFFFFFF, 0,
                                           0, timing0, timing1, 0)
            ret = self.can_dll.VCI_InitCAN(self.device_type, self.device_index, 
                                          self.can_index, byref(vci_initconfig))
            print(f"VCI_InitCAN返回值: {ret}")
            if ret != STATUS_OK:
                raise Exception(f"initialize CAN failed (return value: {ret})")
                
            # 启动CAN
            print("正在启动CAN...")
            ret = self.can_dll.VCI_StartCAN(self.device_type, self.device_index, self.can_index)
            print(f"VCI_StartCAN返回值: {ret}")
            if ret != STATUS_OK:
                raise Exception(f"start CAN failed (return value: {ret})")
                
            self.is_connected = True
            print("CAN设备连接成功!")
            return True
            
        except Exception as e:
            print(f"CAN连接错误: {str(e)}")
            raise Exception(f"connect CAN device failed: {str(e)}")
    
    def get_device_error_info(self):
        """获取设备错误信息"""
        try:
            if self.can_dll:
                # 尝试获取设备信息
                return "please check: 1) CAN device is connected 2) driver is correctly installed 3) device is occupied by other programs"
            else:
                return "DLL not loaded"
        except:
            return "cannot get error details"
    
    def check_device_availability(self):
        """检查设备可用性"""
        try:
            if not self.can_dll:
                dll_path = self.get_dll_path()
                self.can_dll = windll.LoadLibrary(dll_path)
            
            # 尝试读取设备信息
            print("正在检查CAN设备可用性...")
            
            # 检查不同的设备类型和索引
            device_types = [4, 3, 1]  # USBCAN2, USBCAN1, PCI5121
            device_names = ["USBCAN2", "USBCAN1", "PCI5121"]
            
            for i, dev_type in enumerate(device_types):
                for dev_index in range(2):  # 检查索引0和1
                    try:
                        ret = self.can_dll.VCI_OpenDevice(dev_type, dev_index, 0)
                        if ret == STATUS_OK:
                            print(f"找到可用设备: {device_names[i]} (类型:{dev_type}, 索引:{dev_index})")
                            # 关闭设备以供后续使用
                            self.can_dll.VCI_CloseDevice(dev_type, dev_index)
                            return True, dev_type, dev_index
                        else:
                            print(f"设备不可用: {device_names[i]} (类型:{dev_type}, 索引:{dev_index}) - 返回值:{ret}")
                    except Exception as e:
                        print(f"error checking device: {device_names[i]} (type:{dev_type}, index:{dev_index}) - {str(e)}")
            
            return False, None, None
            
        except Exception as e:
            print(f"设备检查失败: {str(e)}")
            return False, None, None
            
    def get_timing(self, baudrate):
        """根据波特率获取定时参数"""
        timing_map = {
            250000: (0x03, 0x1C),  # 250kbps
            500000: (0x00, 0x1C),  # 500kbps
        }
        return timing_map.get(baudrate, (0x00, 0x1C))
        
    def send(self, can_id, data):
        """发送CAN报文"""
        if not self.is_connected:
            raise Exception("CAN device not connected")
            
        # 创建数据数组
        ubyte_array = c_ubyte * 8
        can_data = ubyte_array(*data[:8])
        
        # 创建CAN对象
        ubyte_3array = c_ubyte * 3
        reserved = ubyte_3array(0, 0, 0)
        vci_can_obj = VCI_CAN_OBJ(can_id, 0, 0, 1, 0, 0, len(data), can_data, reserved)
        
        # 发送数据
        ret = self.can_dll.VCI_Transmit(self.device_type, self.device_index, 
                                       self.can_index, byref(vci_can_obj), 1)
        if ret != STATUS_OK:
            raise Exception("send CAN message failed")
            
    def receive(self, timeout=100):
        """接收CAN报文"""
        if not self.is_connected:
            return None
            
        try:
            # 创建接收缓冲区
            rx_vci_can_obj = VCI_CAN_OBJ_ARRAY(2500)
            
            # 接收数据
            ret = self.can_dll.VCI_Receive(self.device_type, self.device_index, 
                                          self.can_index, byref(rx_vci_can_obj.ADDR), 2500, timeout)
            
            if ret > 0:
                messages = []
                for i in range(ret):
                    msg = rx_vci_can_obj.STRUCT_ARRAY[i]
                    data = list(msg.Data[:msg.DataLen])
                    messages.append({
                        'id': msg.ID,
                        'data': data,
                        'length': msg.DataLen,
                        'timestamp': msg.TimeStamp
                    })
                return messages
            elif ret == 0:
                # 超时，没有接收到数据
                return None
            else:
                # 接收错误
                print(f"VCI_Receive返回错误: {ret}")
                return None
                
        except Exception as e:
            print(f"接收CAN报文错误: {str(e)}")
            return None
        
    def disconnect(self):
        """断开连接"""
        if self.can_dll and self.is_connected:
            self.can_dll.VCI_CloseDevice(self.device_type, self.device_index)
            self.is_connected = False

class CANHostComputer:
    def __init__(self, parent_frame=None, initial_language=None):
        """
        初始化CAN工具
        Args:
            parent_frame: 父框架，如果为None则创建独立窗口
            initial_language: 初始语言设置（'zh' 或 'en'），如果为None则使用默认中文
        """
        self.parent_frame = parent_frame
        self.is_embedded = parent_frame is not None
        
        if not self.is_embedded:
            # 独立模式：创建自己的root窗口
            self.root = tk.Tk()
            self.root.title("CAN协议上位机 - 创芯科技CANalyst-II")
            
            # 设置窗口初始大小和最小尺寸
            window_width = 1400
            window_height = 800
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            self.root.minsize(1000, 700)
            
            # 设置窗口图标
            self.set_window_icon()
            
            # 创建主框架
            self.main_frame = ttk.Frame(self.root)
            self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        else:
            # 嵌入模式：使用传入的父框架
            self.root = None
            self.main_frame = parent_frame
        
        # CAN相关变量
        self.can_bus = None
        self.is_connected = False
        self.is_running = False
        self.is_receiving = False  # 新增接收状态
        self.last_heartbeat_time = None
        self.heartbeat_monitor_thread = None
        
        # 统计变量
        self.sent_count = 0
        self.received_count = 0
        self.heartbeat_count = 0  # 新增心跳计数器
        
        # 发送统计变量
        self.sent_305_count = 0
        self.sent_307_count = 0
        
        # 四线程架构队列
        self.send_queue = queue.Queue(maxsize=500)      # UI -> 发送线程
        self.receive_queue = queue.Queue(maxsize=1000)   # 接收线程 -> 解析线程 (增大到2000)
        self.parse_to_ui_queue = queue.Queue(maxsize=100)  # 解析线程 -> UI线程
        
        # 线程安全的UI更新队列（保留原有）
        self.ui_update_queue = queue.Queue()
        self.ui_pump_running = False
        
        # 四线程架构线程引用
        self.send_thread = None
        self.receive_thread = None
        self.parse_thread = None
        
        # 线程运行标志
        #self.threads_running = False
        self.send_thread_running = False
        self.receive_thread_running = False
        self.parse_thread_running = False
        
        # 日志批量处理
        self.log_buffer = deque()
        self.log_buffer_lock = threading.Lock()
        self.last_log_flush = time.monotonic()
        self.log_flush_interval = 0.1  # 100ms批量刷新一次
        self._log_timer = None  # 定时器引用
        
        # 语言设置
        self.lang = initial_language if initial_language in LANGUAGES else 'zh'  # 使用传入的语言或默认中文
        self.lang_var = tk.StringVar(value=self.lang)
        
        # 创建界面
        self.create_widgets()
        
        # 启动UI更新泵
        self.start_ui_pump()

        # UI active state control for tabbed interface
        self._ui_active = True  # Default to active
    
    def start_ui_pump(self):
        """启动UI更新泵，在主线程中处理所有UI更新"""
        if self.ui_pump_running:
            return
        
        self.ui_pump_running = True
        self.process_ui_updates()
    
    def stop_ui_pump(self):
        """停止UI更新泵"""
        self.ui_pump_running = False
    
    def process_ui_updates(self):
        """处理UI更新队列中的所有待处理更新"""
        if not self.ui_pump_running:
            return
        
        # 处理从解析线程发来的UI更新
        self.process_parse_to_ui_queue()
        
        # 批量处理队列中的所有更新
        updates_processed = 0
        max_updates_per_cycle = 20  # 每次最多处理20个更新，减少窗口操作时的卡顿
        
        try:
            while updates_processed < max_updates_per_cycle:
                try:
                    update_func, args, kwargs = self.ui_update_queue.get_nowait()
                    update_func(*args, **kwargs)
                    updates_processed += 1
                except queue.Empty:
                    break
                except Exception as e:
                    self.log_message_direct(f"UI update error: {str(e)}")
        except Exception as e:
            self.log_message_direct(f"UI pump error: {str(e)}")
        
        # 处理日志文件批量刷新
        self.flush_log_buffer()
        
        # 调度下一次更新处理 - 降低频率减少卡顿
        update_interval = 50 if updates_processed > 0 else 100  # 有更新时50ms，无更新时100ms
        if self.is_embedded and self.main_frame:
            self.main_frame.after(update_interval, self.process_ui_updates)
        elif not self.is_embedded and self.root:
            self.root.after(update_interval, self.process_ui_updates)
    
    def queue_ui_update(self, func, *args, **kwargs):
        """将UI更新操作加入队列"""
        try:
            self.ui_update_queue.put((func, args, kwargs), block=False)
        except queue.Full:
            # 队列满时丢弃最旧的更新
            try:
                self.ui_update_queue.get_nowait()
                self.ui_update_queue.put((func, args, kwargs), block=False)
            except queue.Empty:
                pass
    
    def set_window_icon(self):
        """设置窗口图标"""
        try:
            # 获取图标文件路径
            icon_path = get_resource_path('BQC.ico')        
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
            else:
                print(f"图标文件不存在: {icon_path}")
        except Exception as e:
            print(f"设置窗口图标失败: {e}")
    
    def create_widgets(self):
        # 获取当前语言配置
        lang = LANGUAGES[self.lang]
        
        # 主框架
        if self.is_embedded:
            # 嵌入模式：使用传入的父框架
            main_frame = self.main_frame
        else:
            # 独立模式：直接使用已创建的主框架
            main_frame = self.main_frame
        
        # 语言选择（只在独立模式下显示）
        if not self.is_embedded:
            lang_frame = ttk.Frame(self.root)
            lang_frame.pack(fill="x", padx=10, pady=2)
            ttk.Label(lang_frame, text=lang['language']).pack(side="left")
            self.lang_var = tk.StringVar(value=self.lang)
            lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, values=['zh', 'en'], width=8, state="readonly")
            lang_combo.pack(side="left")
            lang_combo.bind("<<ComboboxSelected>>", self.on_language_change)
        
        # 连接设置框架
        self.connection_frame = ttk.LabelFrame(main_frame, text=lang['connection_settings'], padding="10")
        connection_frame = self.connection_frame
        connection_frame.pack(fill="x", pady=5)
        
        # 第一行：设备设置
        row1 = ttk.Frame(connection_frame)
        row1.pack(fill="x", pady=2)
        
        ttk.Label(row1, text=lang['device_type']).pack(side="left", padx=5)
        self.device_type_var = tk.StringVar(value="VCI_USBCAN2")
        self.device_type_combo = ttk.Combobox(row1, textvariable=self.device_type_var, 
                                       values=["VCI_USBCAN2"], width=15, state="readonly")
        self.device_type_combo.pack(side="left", padx=5)
        
        ttk.Label(row1, text=lang['device_index']).pack(side="left", padx=5)
        self.device_index_var = tk.StringVar(value="0")
        self.device_index_combo = ttk.Combobox(row1, textvariable=self.device_index_var, 
                                        values=["0", "1"], width=5)
        self.device_index_combo.pack(side="left", padx=5)
        
        ttk.Label(row1, text=lang['can_channel']).pack(side="left", padx=5)
        self.can_index_var = tk.StringVar(value="0")
        self.can_index_combo = ttk.Combobox(row1, textvariable=self.can_index_var, 
                                      values=["0", "1"], width=5)
        self.can_index_combo.pack(side="left", padx=5)
        
        # 第二行：波特率设置
        row2 = ttk.Frame(connection_frame)
        row2.pack(fill="x", pady=2)
        
        ttk.Label(row2, text=lang['baud_rate']).pack(side="left", padx=5)
        self.baudrate_var = tk.StringVar(value="500000")
        self.baudrate_combo = ttk.Combobox(row2, textvariable=self.baudrate_var,
                                     values=["250000", "500000"], width=10)
        self.baudrate_combo.pack(side="left", padx=5)

        # 设备ID选择
        ttk.Label(row2, text="设备ID:").pack(side="left", padx=5)
        self.device_id_var = tk.IntVar(value=1)
        self.device_id_spinbox = ttk.Spinbox(row2, from_=1, to=6, textvariable=self.device_id_var, width=5)
        self.device_id_spinbox.pack(side="left", padx=5)

        # 连接按钮
        self.connect_btn = ttk.Button(row2, text=lang['connect'], command=self.connect_can)
        self.connect_btn.pack(side="left", padx=10)
        
        self.disconnect_btn = ttk.Button(row2, text=lang['disconnect'], command=self.disconnect_can, state="disabled")
        self.disconnect_btn.pack(side="left", padx=5)
        
        # 控制框架
        self.control_frame = ttk.LabelFrame(main_frame, text=lang['control'], padding="10")
        control_frame = self.control_frame
        control_frame.pack(fill="x", pady=5)
        
        # 控制按钮
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill="x")
        
        # 发送控制
        send_frame = ttk.Frame(btn_frame)
        send_frame.pack(side="left", padx=10)
        
        ttk.Label(send_frame, text=lang['send_control']).pack(side="left")
        self.start_btn = ttk.Button(send_frame, text=lang['start_send'], command=self.start_sending, state="disabled")
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(send_frame, text=lang['stop_send'], command=self.stop_sending, state="disabled")
        self.stop_btn.pack(side="left", padx=5)
        
        # 接收控制
        receive_frame = ttk.Frame(btn_frame)
        receive_frame.pack(side="left", padx=10)
        
        ttk.Label(receive_frame, text=lang['receive_control']).pack(side="left")
        self.receive_var = tk.BooleanVar(value=False)
        self.receive_check = ttk.Checkbutton(receive_frame, text=lang['open_receive'], 
                                           variable=self.receive_var, 
                                           command=self.toggle_receive, 
                                           state="disabled")
        self.receive_check.pack(side="left", padx=5)
        
        # 状态显示
        self.status_var = tk.StringVar(value=lang['disconnected'])
        status_label = ttk.Label(btn_frame, textvariable=self.status_var)
        status_label.pack(side="right", padx=5)
        
        # 统计信息框架
        self.stats_frame = ttk.LabelFrame(main_frame, text=lang['stat_info'], padding="10")
        stats_frame = self.stats_frame
        stats_frame.pack(fill="x", pady=5)
        
        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill="x")
        
        # 发送统计
        ttk.Label(stats_inner, text=lang['send'] + ":").grid(row=0, column=0, sticky="w", padx=5)
        self.sent_count_var = tk.StringVar(value="0")
        ttk.Label(stats_inner, textvariable=self.sent_count_var).grid(row=0, column=1, padx=5)
        
        # 接收统计
        ttk.Label(stats_inner, text=lang['receive'] + ":").grid(row=0, column=2, sticky="w", padx=5)
        self.received_count_var = tk.StringVar(value="0")
        ttk.Label(stats_inner, textvariable=self.received_count_var).grid(row=0, column=3, padx=5)
        
        # 心跳状态
        ttk.Label(stats_inner, text=lang['heartbeat_status'] + ":").grid(row=0, column=4, sticky="w", padx=5)
        self.heartbeat_status_var = tk.StringVar(value=lang['normal'])
        self.heartbeat_status_label = ttk.Label(stats_inner, textvariable=self.heartbeat_status_var)
        self.heartbeat_status_label.grid(row=0, column=5, padx=5)
        
        # 创建左右分栏布局
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill="both", expand=True, pady=5)
        
        # 左侧：发送数据和实时数据
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # 发送数据显示框架
        self.send_data_frame = ttk.LabelFrame(left_frame, text=lang['send_data'], padding="10")
        send_data_frame = self.send_data_frame
        send_data_frame.pack(fill="x", pady=5)
        
        # 创建发送数据表格
        self.create_send_data_table(send_data_frame)
        
        # 实时数据表格显示框架
        self.data_frame = ttk.LabelFrame(left_frame, text=lang['realtime_data'], padding="10")
        data_frame = self.data_frame
        data_frame.pack(fill="both", expand=True, pady=5)
        
        # 创建表格
        self.create_data_table(data_frame)
        
        # 右侧：日志框架
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # 日志框架
        self.log_frame = ttk.LabelFrame(right_frame, text=lang['log'], padding="10")
        log_frame = self.log_frame
        log_frame.pack(fill="both", expand=True)
        
        # 日志控制按钮 - 移到日志文本框上方
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.pack(fill="x", pady=(0, 5))
        
        clear_btn = ttk.Button(log_btn_frame, text=lang['clear_log'], command=self.clear_log)
        clear_btn.pack(side="left")
        
        # 将保存日志按钮改为勾选框 - 默认不勾选
        self.auto_save_var = tk.BooleanVar(value=False)  # 默认不勾选
        self.auto_save_check = ttk.Checkbutton(log_btn_frame, text=lang['auto_save_log'], 
                                             variable=self.auto_save_var, 
                                             command=self.toggle_auto_save)
        self.auto_save_check.pack(side="left", padx=5)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15)
        self.log_text.pack(fill="both", expand=True)
        
        # 配置文本标签颜色
        self.log_text.tag_configure("heartbeat_red", foreground="red")
        
        # 初始化日志文件相关变量
        self.log_file = None
        self.log_filename = None
        
        # 程序启动时自动开始保存日志（只在独立模式下）
        if not self.is_embedded and self.root:
            self.root.after(100, self.start_auto_save_on_startup)    
    
    def toggle_auto_save(self):
        """切换自动保存日志功能"""
        if self.auto_save_var.get():
            self.start_auto_save()
        else:
            self.stop_auto_save()  
    
    def start_auto_save(self):
        """开始自动保存日志"""
        try:
            # 弹出文件保存对话框
            filetypes = [("log file", "*.txt"), ("all files", "*.*")]
            filename = filedialog.asksaveasfilename(
                title="select log save path",
                defaultextension=".txt",
                filetypes=filetypes,
                initialfile=f"can_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            if not filename:
                # 用户取消选择，自动保存不生效
                self.auto_save_var.set(False)
                return

            self.log_filename = filename
            self.log_file = open(self.log_filename, 'w', encoding='utf-8')

            # 写入日志文件头部信息
            header = f"CAN host computer log file\n"
            header += f"create time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"device type: CANalyst-II\n"
            header += "=" * 50 + "\n\n"
            self.log_file.write(header)
            self.log_file.flush()

            self.log_message(f"Auto save log enabled, log file: {self.log_filename}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to create log file: {str(e)}")
            self.auto_save_var.set(False)
    
    def stop_auto_save(self):
        """停止自动保存日志"""
        if self.log_file:
            try:
                # 写入日志文件尾部信息
                footer = f"\n" + "=" * 50 + "\n"
                footer += f"log end time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                footer += f"total log lines: {self.get_log_line_count()}\n"
                
                self.log_file.write(footer)
                self.log_file.close()
                
                self.log_message(f"Auto save log stopped, log file: {self.log_filename}")
                
            except Exception as e:
                self.log_message(f"Error closing log file: {str(e)}")
            
            self.log_file = None
            self.log_filename = None
    
    def get_log_line_count(self):
        """获取日志行数"""
        try:
            content = self.log_text.get(1.0, tk.END)
            return len(content.split('\n')) - 1  # 减去最后一行空行
        except:
            return 0
    
    def log_message(self, message, color="black"):
        """添加日志消息 - 自动检测线程并确保线程安全"""      
        # 检查是否在主线程中
        main_thread = threading.main_thread()
        current_thread = threading.current_thread()
        
        if current_thread == main_thread:
            # 在主线程中，直接使用批量处理机制
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {message}\n"
            
            # 添加到批量缓冲区
            with self.log_buffer_lock:
                self.log_buffer.append((log_entry, message, color))
            
            # 启动定时批量更新（如果还没有启动）
            self._schedule_log_batch_update()
        else:
            # 在其他线程中，通过队列安全传递到UI线程
            try:
                self.parse_to_ui_queue.put_nowait({
                    'type': 'system_log',
                    'message': message,
                    'color': color
                })
            except queue.Full:
                # 队列满时静默丢弃，避免阻塞线程
                #清空部分旧消息
                try:
                    for _ in range(20):
                        self.parse_to_ui_queue.get_nowait()
                except queue.Empty:
                    pass
                self.parse_to_ui_queue.put_nowait({
                    'type': 'system_log',
                    'message': message,
                    'color': color
                })
    
    def log_message_direct(self, message, color="black"):
        """直接添加日志消息，用于UI线程内部 - 线程安全版本"""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}\n"
        
        # 确保在主线程中执行UI操作
        def update_log_ui():
            try:
                # 直接插入到界面文本框
                self.log_text.insert(tk.END, log_entry)
                
                # 限制UI显示的日志行数，最多保留1000行
                self.limit_log_display_lines()
                
                # 检查是否包含"心跳状态"并设置颜色
                if "心跳状态" in message:
                    last_line_start = self.log_text.index("end-2l linestart")
                    last_line_end = self.log_text.index("end-1c")
                    self.log_text.tag_add("heartbeat_red", last_line_start, last_line_end)
                
                self.log_text.see(tk.END)
            except Exception as e:
                print(f"Log UI update error: {e}")
        
        # 使用after方法确保在主线程中执行
        try:
            if self.is_embedded and self.main_frame:
                self.main_frame.winfo_toplevel().after_idle(update_log_ui)
            elif not self.is_embedded and self.root:
                self.root.after_idle(update_log_ui)
            else:
                update_log_ui()  # 直接执行（可能在主线程中）
        except Exception:
            update_log_ui()  # 回退到直接执行
        
        # 如果开启了自动保存，写入文件（在后台线程中）
        if self.auto_save_var.get() and self.log_file:
            def write_to_file():
                try:
                    self.log_file.write(log_entry)
                except Exception as e:
                    error_msg = f"[{timestamp}] write log file failed: {str(e)}\n"
                    # 错误消息也需要线程安全处理
                    def show_error():
                        try:
                            self.log_text.insert(tk.END, error_msg)
                            self.log_text.see(tk.END)
                        except Exception:
                            pass
                    
                    try:
                        if self.is_embedded and self.main_frame:
                            self.main_frame.winfo_toplevel().after_idle(show_error)
                        elif not self.is_embedded and self.root:
                            self.root.after_idle(show_error)
                    except Exception:
                        pass
            
            # 在后台线程中写入文件
            import threading
            threading.Thread(target=write_to_file, daemon=True).start()
    
    def _schedule_log_batch_update(self):
        """调度批量日志更新 - 定时机制"""
        if self._log_timer is not None:
            return  # 已经有定时器在运行
        
        # 使用after方法确保在主线程中执行，200ms延迟批量处理
        try:
            if self.is_embedded and self.main_frame:
                self._log_timer = self.main_frame.winfo_toplevel().after(500, self._process_log_batch)
            elif not self.is_embedded and self.root:
                self._log_timer = self.root.after(500, self._process_log_batch)
        except Exception:
            # 如果调度失败，直接处理
            self._process_log_batch()
    
    def _process_log_batch(self):
        """批量处理日志更新 - 定时执行"""
        try:
            # 重置定时器
            self._log_timer = None
            
            # 检查是否有日志需要处理
            with self.log_buffer_lock:
                if not self.log_buffer:
                    return
            
            # 调用现有的批量刷新方法
            self._flush_log_buffer_to_ui()
            
            # 如果还有更多日志，继续调度下一次处理 - 添加延迟避免过于频繁的重新调度
            with self.log_buffer_lock:
                if self.log_buffer:
                    # 延迟重新调度，避免窗口操作时的卡顿
                    if self.is_embedded and self.main_frame:
                        self.main_frame.winfo_toplevel().after(1000, self._schedule_log_batch_update)
                    elif not self.is_embedded and self.root:
                        self.root.after(1000, self._schedule_log_batch_update)
                    
        except Exception as e:
            print(f"Log batch processing error: {e}")
            # 重置状态
            self._log_timer = None
    
    def _flush_log_buffer_to_ui(self):
        """将日志缓冲区内容刷新到UI - 线程安全版本"""
        with self.log_buffer_lock:
            if not self.log_buffer:
                return
            
            # 批量处理所有日志条目
            entries_to_process = list(self.log_buffer)
            self.log_buffer.clear()
        
        # 确保在主线程中执行UI更新
        def update_ui():
            try:
                # 批量插入到UI
                combined_text = ""
                last_message = ""
                for log_entry, message, color in entries_to_process:
                    combined_text += log_entry
                    last_message = message
                
                if combined_text:
                    self.log_text.insert(tk.END, combined_text)
                
                # 限制UI显示的日志行数，最多保留1000行
                if entries_to_process:  # 只有在有新日志时才检查
                    self.limit_log_display_lines()
                    
                    # 检查是否包含"心跳状态"并设置颜色
                    if "心跳状态" in last_message:
                        last_line_start = self.log_text.index("end-2l linestart")
                        last_line_end = self.log_text.index("end-1c")
                        self.log_text.tag_add("heartbeat_red", last_line_start, last_line_end)
                
                self.log_text.see(tk.END)
            except Exception as e:
                print(f"Log buffer flush UI error: {e}")
        
        # 使用after方法确保在主线程中执行
        try:
            if self.is_embedded and self.main_frame:
                self.main_frame.winfo_toplevel().after_idle(update_ui)
            elif not self.is_embedded and self.root:
                self.root.after_idle(update_ui)
            else:
                update_ui()
        except Exception:
            update_ui()
        
        # 批量写入文件（在后台线程中）
        if self.auto_save_var.get() and self.log_file and entries_to_process:
            def write_to_file():
                try:
                    for log_entry, _, _ in entries_to_process:
                        self.log_file.write(log_entry)
                except Exception as e:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    error_msg = f"[{timestamp}] batch write log file failed: {str(e)}\n"
                    # 错误消息也需要线程安全处理
                    def show_error():
                        try:
                            self.log_text.insert(tk.END, error_msg)
                            self.log_text.see(tk.END)
                        except Exception:
                            pass
                    
                    try:
                        if self.is_embedded and self.main_frame:
                            self.main_frame.winfo_toplevel().after_idle(show_error)
                        elif not self.is_embedded and self.root:
                            self.root.after_idle(show_error)
                    except Exception:
                        pass
            
            # 在后台线程中写入文件
            import threading
            threading.Thread(target=write_to_file, daemon=True).start()
    
    def flush_log_buffer(self):
        """定期刷新日志文件（UI更新已改为定时机制）"""
        current_time = time.monotonic()
        
        # 只处理文件刷新，UI更新由定时机制处理
        if (current_time - self.last_log_flush) >= self.log_flush_interval:
            if self.auto_save_var.get() and self.log_file:
                try:
                    self.log_file.flush()
                except Exception as e:
                    self.log_message_direct(f"log file refresh failed: {str(e)}")
            
            self.last_log_flush = current_time
    
    def clear_log(self):
        """清空日志 不清空文件"""
        self.log_text.delete(1.0, tk.END)
    
    def limit_log_display_lines(self, max_lines=1000):
        """限制UI日志显示的行数，超出时删除旧记录"""
        try:
            # 获取当前总行数
            current_lines = int(self.log_text.index('end-1c').split('.')[0]) - 1
            
            if current_lines > max_lines:
                #直接删除前100行
                delete_end_index = "100.0"
                self.log_text.delete("1.0", delete_end_index)
                
        except Exception as e:
            # 如果出错，不影响正常日志功能
            pass
    
    def save_log(self):
        """手动保存日志到文件（保留原有功能作为备用）"""
        try:
            filename = f"can_log_manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Save Success", f"Log saved to: {filename}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Failed to save log: {str(e)}")
    
    def __del__(self):
        """析构函数，确保程序退出时关闭日志文件"""
        if hasattr(self, 'log_file') and self.log_file:
            try:
                self.log_file.close()
            except:
                pass
        
    def start_receive_and_parse_threads(self):
        """启动接收和解析线程"""
        if self.receive_thread_running or self.parse_thread_running:
            return
        
        self.receive_thread_running = True
        self.parse_thread_running = True
        
        # 先启动解析线程
        self.parse_thread = threading.Thread(target=self._parse_worker, daemon=True)
        self.parse_thread.start()

        # 再启动接收线程
        self.receive_thread = threading.Thread(target=self._receive_worker, daemon=True) 
        self.receive_thread.start()

        self.log_message("Receive and parse threads started")
    
    def stop_receive_and_parse_threads(self):
        """停止接收和解析线程"""
        self.receive_thread_running = False
        self.parse_thread_running = False
        
        # 发送停止信号到队列
        try:
            self.receive_queue.put_nowait(None)
        except queue.Full:
            pass
        
        try:
            self.parse_to_ui_queue.put_nowait(None)
        except queue.Full:
            pass
        
        # 等待线程结束
        threads = [
            (self.receive_thread, "Receive"), 
            (self.parse_thread, "Parse")
        ]
        
        for thread, name in threads:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)
                if thread.is_alive():
                    self.log_message(f"Warning: {name} thread did not stop gracefully")
        
        # 清理线程引用
        self.receive_thread = None
        self.parse_thread = None
        
        # 清空相关队列中的残留数据
        self._clear_receive_queues()
        
        self.log_message("Receive and parse threads stopped")
    
    def start_send_thread(self):
        """启动发送线程"""
        if self.send_thread_running:
            return
        
        self.send_thread_running = True
        
        # 启动发送线程
        self.send_thread = threading.Thread(target=self._send_worker, daemon=True)
        self.send_thread.start()
        
        self.log_message("Send thread started")
    
    def stop_send_thread(self):
        """停止发送线程"""
        self.send_thread_running = False
        
        # 发送停止信号到发送队列
        try:
            self.send_queue.put_nowait(None)
        except queue.Full:
            pass
        
        # 等待线程结束
        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1.0)
            if self.send_thread.is_alive():
                self.log_message("Warning: Send thread did not stop gracefully")
        
        # 清理线程引用
        self.send_thread = None
        
        # 清空发送队列中的残留数据
        self._clear_send_queue()
        
        self.log_message("Send thread stopped")
       
    def _clear_receive_queues(self):
        """清空接收相关队列中的残留数据"""
        queues_to_clear = [
            (self.receive_queue, "receive_queue"), 
            (self.parse_to_ui_queue, "parse_to_ui_queue")
        ]
        
        for q, name in queues_to_clear:
            cleared_count = 0
            try:
                while True:
                    q.get_nowait()
                    cleared_count += 1
            except queue.Empty:
                pass
            
            if cleared_count > 0:
                self.log_message(f"Cleared {cleared_count} items from {name}")
    
    def _clear_send_queue(self):
        """清空发送队列中的残留数据"""
        cleared_count = 0
        try:
            while True:
                self.send_queue.get_nowait()
                cleared_count += 1
        except queue.Empty:
            pass
        
        if cleared_count > 0:
            self.log_message(f"Cleared {cleared_count} items from send_queue")
    
    def _send_worker(self):
        """发送线程 - 直接实现定时发送逻辑"""
        # 创建0x305和0x307报文数据，数据格式固定只需要生成一次
        msg_305_data = self.create_305_message()
        msg_307_data = self.create_307_message()
        
        while self.send_thread_running and self.is_running and self.is_connected:
            try:
                # 发送0x305报文
                try:
                    if self.can_bus and self.can_bus.is_connected:
                        self.can_bus.send(0x305, msg_305_data)
                        self.sent_305_count += 1
                        
                        # 更新发送数据表格
                        current_time = datetime.now().strftime("%H:%M:%S")
                        lang = LANGUAGES[self.lang]
                        self.queue_ui_update(self.update_send_data_table, 0x305, lang['start_send_status'], self.sent_305_count, current_time)
                        self.log_message(f"Send[{self.sent_305_count}]: ID=0x305, Data: {msg_305_data.hex()}")
                    else:
                        self.log_message("Cannot send 0x305: CAN bus not connected")
                        break
                except Exception as e:
                    self.log_message(f"Send 0x305 failed: {e}")
                
                # 发送0x307报文
                try:
                    if self.can_bus and self.can_bus.is_connected:
                        self.can_bus.send(0x307, msg_307_data)
                        self.sent_307_count += 1
                        
                        # 更新发送数据表格
                        current_time = datetime.now().strftime("%H:%M:%S")
                        lang = LANGUAGES[self.lang]
                        self.queue_ui_update(self.update_send_data_table, 0x307, lang['start_send_status'], self.sent_307_count, current_time)
                        self.log_message(f"Send[{self.sent_307_count}]: ID=0x307, Data: {msg_307_data.hex()}")
                    else:
                        self.log_message("Cannot send 0x307: CAN bus not connected")
                        break
                except Exception as e:
                    self.log_message(f"Send 0x307 failed: {e}")
                
                # 每秒发送一次
                time.sleep(1)
                    
            except Exception as e:
                self.log_message(f"Send thread error: {e}")
                break
        
        self.log_message(f"Send thread stopped, total sent: 0x305={self.sent_305_count}, 0x307={self.sent_307_count}")
    
    def _receive_worker(self):
        """接收线程 - 专门负责CAN数据接收"""
        receive_count = 0
        while self.receive_thread_running and self.is_connected:
            try:
                # 如果未开启接收，则等待100ms后继续
                if not self.is_receiving:
                    time.sleep(0.1)
                    continue
                
                # 接收CAN数据
                messages = self.can_bus.receive(timeout=10)
                
                if messages:
                    receive_count += len(messages)
                    # 将接收到的数据发送给解析线程
                    for msg in messages:
                        # 通过队列安全地发送recv日志到UI线程
                        msg_id = msg.get('id', 0)
                        data = msg.get('data', [])
                        data_hex = ' '.join(f'{b:02X}' for b in data)
                        self.log_message(f"recv: ID=0x{msg_id:03X} Data=[{data_hex}]")
                        try:
                            self.receive_queue.put_nowait(msg)
                        except queue.Full:
                            # 批量清理旧消息为新消息让路 (清理10%的旧消息)
                            dropped_count = 0
                            try:
                                # 清理约500条旧消息 (队列的50%)
                                for _ in range(500):
                                    self.receive_queue.get_nowait()
                                    dropped_count += 1
                                # 放入新消息
                                self.receive_queue.put_nowait(msg)
                                if dropped_count > 0:
                                    self.log_message(f"Receive queue full, dropped {dropped_count} old messages")
                            except (queue.Empty, queue.Full):
                                self.log_message("Receive queue full, dropping message")
                
                    # 批量更新统计信息 - 降低更新频率
                    if receive_count % 10 == 0:  
                        self.queue_ui_update(self._update_receive_stats, receive_count)
                        
            except Exception as e:
                if self.receive_thread_running:
                    self.log_message(f"Receive thread error: {e}")
                break
        
        self.log_message(f"Receive thread stopped, total received: {receive_count} messages")
    
    def _parse_worker(self):
        """解析线程 - 专门负责数据解析和处理"""
        parsed_count = 0
        last_heartbeat_check = time.monotonic()
        heartbeat_timeout_reported = False
        
        while self.parse_thread_running:
            try:
                # 从接收队列获取消息
                try:
                    msg = self.receive_queue.get(timeout=0.1)
                    
                    # 检查停止信号
                    if msg is None:
                        break                   
                    parsed_count += 1
                    
                    # 解析消息
                    msg_id = msg['id']
                    
                    # 心跳处理（0x351作为心跳标志）
                    if msg_id == 0x351:
                        self._handle_heartbeat_in_parse_thread(msg)
                        heartbeat_timeout_reported = False  # 重置超时报告标志
                    
                    # 处理其他消息
                    self._process_message_in_parse_thread(msg)
                
                except queue.Empty:
                    # 超时是正常的，继续检查心跳超时
                    pass
                
                # 定期检查心跳超时（每0.5秒检查一次）
                current_time = time.monotonic()
                if current_time - last_heartbeat_check >= 0.5:
                    last_heartbeat_check = current_time
                    
                    # 检查心跳超时（3秒未收到0x351）
                    if (self.is_receiving and 
                        self.last_heartbeat_time and 
                        (current_time - self.last_heartbeat_time) > 3):
                        if not heartbeat_timeout_reported:
                            # 发送超时处理到UI线程
                            try:
                                self.parse_to_ui_queue.put_nowait({
                                    'type': 'heartbeat_timeout'
                                })
                                heartbeat_timeout_reported = True
                            except queue.Full:
                                pass
                                
            except Exception as e:
                self.log_message(f"Parse thread error: {e}")
                continue
        
        self.log_message(f"Parse thread stopped, total parsed: {parsed_count} messages")
    
    def _handle_heartbeat_in_parse_thread(self, msg):
        """在解析线程中处理心跳"""
        self.last_heartbeat_time = time.monotonic()
        self.heartbeat_count += 1
        
        # 发送心跳更新到UI线程
        try:
            self.parse_to_ui_queue.put_nowait({
                'type': 'heartbeat',
                'count': self.heartbeat_count,
                'msg': msg
            })
        except queue.Full:
            #清空部分旧消息
            try:
                for _ in range(20):
                    self.parse_to_ui_queue.get_nowait()
            except queue.Empty:
                pass
            self.parse_to_ui_queue.put_nowait({
                'type': 'heartbeat',
                'count': self.heartbeat_count,
                'msg': msg
            })
    
    def _process_message_in_parse_thread(self, msg):
        """在解析线程中处理普通消息"""
        try:
            # 解析消息内容
            parsed_data = self.parse_can_message(msg)
            
            # 发送解析结果到UI线程
            if parsed_data:
                try:
                    self.parse_to_ui_queue.put_nowait({
                        'type': 'parsed_data',
                        'msg_id': msg['id'],
                        'data': parsed_data,
                        'msg': msg
                    })
                except queue.Full:
                    #清空部分旧消息
                    self.log_message("Parse to UI queue full, dropping message")
                    try:
                        for _ in range(20):
                            self.parse_to_ui_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.parse_to_ui_queue.put_nowait({
                        'type': 'parsed_data',
                        'msg_id': msg['id'],
                        'data': parsed_data,
                        'msg': msg
                    })
                    
        except Exception as e:
            self.log_message(f"Message parsing error: {e}")
    
    def _update_send_stats(self, count):
        """更新发送统计"""
        self.sent_count = count
        self.sent_count_var.set(str(count))
    
    def _update_receive_stats(self, count):
        """更新接收统计"""
        self.received_count = count
        self.received_count_var.set(str(count))
    
    def process_parse_to_ui_queue(self):
        """处理从解析线程发来的UI更新"""
        try:
            while True:
                try:
                    item = self.parse_to_ui_queue.get_nowait()
                    if item is None:
                        break
                    
                    if item['type'] == 'heartbeat':
                        self._update_heartbeat_gui(item['count'])
                        self.log_message(f"Received heartbeat: ID=0x351, Data: {bytes(item['msg']['data']).hex()}")
                    elif item['type'] == 'parsed_data':
                        self.update_table_data(item['msg_id'], item['data'])
                        self.log_message(f"Successfully parsed 0x{item['msg_id']:03X}: {item['data']}")
                    elif item['type'] == 'recv_log':
                        self.log_message(f"recv: ID=0x{item['msg_id']:03X} Data=[{item['data_hex']}]")
                    elif item['type'] == 'system_log':
                        self.log_message(item['message'], item.get('color', 'black'))
                    elif item['type'] == 'heartbeat_timeout':
                        self.handle_heartbeat_timeout()
                        
                except queue.Empty:
                    break
        except Exception as e:
            self.log_message(f"Parse to UI queue processing error: {e}")

    def connect_can(self):
        """连接CAN总线"""
        try:
            device_type = VCI_USBCAN2
            device_index = int(self.device_index_var.get())
            can_index = int(self.can_index_var.get())
            baudrate = int(self.baudrate_var.get())
            
            self.log_message(f"Connecting to CAN device...")
            self.log_message(f"Device type: VCI_USBCAN2, Device index: {device_index}, CAN channel: {can_index}, Baud rate: {baudrate}")
            
            # 创建CAN总线对象
            self.can_bus = CANalystCANBus(device_type, device_index, can_index)
            self.can_bus.connect(baudrate)
            
            self.is_connected = True
            
            # 重置关键状态变量
            self.last_heartbeat_time = None
            self.heartbeat_count = 0
            
            # 不在连接时启动四线程架构，改为在勾选接收和点击发送时分别启动
            
            # 禁用连接配置控件
            self.set_connection_controls_state(False)
            
            self.connect_btn.config(state="disabled")
            self.disconnect_btn.config(state="normal")
            self.start_btn.config(state="normal")
            self.receive_check.config(state="normal")  # 确保复选框可用
            
            lang = LANGUAGES[self.lang]
            self.status_var.set(lang['connected'])
            lang = LANGUAGES[self.lang]
            self.heartbeat_status_var.set(lang['waiting'])  # 初始状态为等待
            self.heartbeat_count = 0  # 重置心跳计数
            
            # 重置表格中的心跳状态
            current_time = datetime.now().strftime("%H:%M:%S")
            lang = LANGUAGES[self.lang]
            self.update_table_item('0x351', lang['table_351'][0][0], '0', '', lang['waiting'], current_time)
            
            # 重置发送数据表格状态
            lang = LANGUAGES[self.lang]
            self.update_send_data_table(0x305, lang['stop_send'], 0, current_time)
            self.update_send_data_table(0x307, lang['stop_send'], 0, current_time)
            
            self.log_message("CAN device connected successfully")
            
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect CAN device: {str(e)}")
            self.log_message(f"Connection failed: {str(e)}")
            
    def disconnect_can(self):
        """断开CAN连接"""
        # 停止所有线程
        if self.is_running:
            self.stop_sending()
        if self.is_receiving:
            self.stop_receiving()
        
        if self.can_bus:
            self.can_bus.disconnect()
            self.can_bus = None
            
        self.is_connected = False
        
        # 恢复连接配置控件
        self.set_connection_controls_state(True)
        
        self.connect_btn.config(state="normal")
        self.disconnect_btn.config(state="disabled")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="disabled")
        self.receive_check.config(state="disabled")  # 禁用接收复选框
        self.receive_var.set(False)  # 取消勾选
        
        lang = LANGUAGES[self.lang]
        self.status_var.set(lang['disconnected'])
        self.heartbeat_count = 0  # 重置心跳计数
        
        # 重置表格中的心跳状态
        current_time = datetime.now().strftime("%H:%M:%S")
        lang = LANGUAGES[self.lang]
        self.update_table_item('0x351', lang['table_351'][0][0], '0', '', lang['stop'], current_time)
        
        # 重置发送数据表格状态
        lang = LANGUAGES[self.lang]
        self.update_send_data_table(0x305, lang['stop_send'], 0, current_time)
        self.update_send_data_table(0x307, lang['stop_send'], 0, current_time)
        
        self.log_message("CAN device disconnected")
    
    def set_connection_controls_state(self, enabled):
        """设置连接配置控件的启用/禁用状态"""
        state = 'normal' if enabled else 'disabled'
        self.device_type_combo.config(state=state)
        self.device_index_combo.config(state=state)
        self.can_index_combo.config(state=state)
        self.baudrate_combo.config(state=state)
    
    def start_sending(self):
        """开始发送CAN报文"""
        if not self.is_connected:
            return
            
        self.is_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        # 重置发送计数
        self.sent_305_count = 0
        self.sent_307_count = 0
        
        # 更新发送数据表格初始状态 - 改为"正在发送"
        current_time = datetime.now().strftime("%H:%M:%S")
        lang = LANGUAGES[self.lang]
        self.update_send_data_table(0x305, lang['start_send_status'], 0, current_time)
        self.update_send_data_table(0x307, lang['start_send_status'], 0, current_time)
        
        # 启动发送线程，直接绑定_send_worker
        self.start_send_thread()
        
        self.log_message("Starting to send CAN messages")
    
    def stop_sending(self):
        """停止发送CAN报文"""
        self.is_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        
        # 停止发送线程
        self.stop_send_thread()
        
        # 更新发送数据表格停止状态 - 改为"已停止"
        current_time = datetime.now().strftime("%H:%M:%S")
        lang = LANGUAGES[self.lang]
        self.update_send_data_table(0x305, lang['stopped'], self.sent_305_count, current_time)
        self.update_send_data_table(0x307, lang['stopped'], self.sent_307_count, current_time)
        
        self.log_message("Stopping to send CAN messages")
                      
    def create_305_message(self):
        """创建0x305报文数据 - Keepalive from inverter to BMS"""
        # 根据协议文档：8个字节都是0
        data = bytearray(8)
        # 所有字节都是0，不需要额外设置，bytearray默认就是0
        return data
        
    def create_307_message(self):
        """创建0x307报文数据 - Inverter identification from inverter to BMS"""
        # 根据协议文档：0x12 0x34 0x56 0x78 V I C 0x00
        data = bytearray(8)
        data[0] = 0x12  # Byte 0
        data[1] = 0x34  # Byte 1
        data[2] = 0x56  # Byte 2
        data[3] = 0x78  # Byte 3
        data[4] = ord('V')  # Byte 4: ASCII 'V'
        data[5] = ord('I')  # Byte 5: ASCII 'I'
        data[6] = ord('C')  # Byte 6: ASCII 'C'
        data[7] = 0x00  # Byte 7: reserved for future use
        return data               
    
    def parse_can_message(self, msg):
        """解析CAN报文"""
        msg_id = msg['id']
        data = msg['data']

        try:
            # 使用通用解析函数
            parsed_data = parse_can_message(msg_id, data)

            # 根据设备ID过滤battery_address
            if parsed_data and 'battery_address' in parsed_data:
                selected_device_id = self.device_id_var.get()
                if parsed_data['battery_address'] != selected_device_id:
                    # 丢弃不匹配的数据
                    return None

            return parsed_data
        except Exception as e:
            self.log_message(f"Parsing message 0x{msg_id:03X} error: {str(e)}")
            return None
    
    def start_receiving(self):
        """启动接收CAN报文"""
        if not self.is_connected:
            self.log_message("Please connect CAN bus first.", color="orange")
            self.receive_check.config(state="disabled")
            return
        
        if self.is_receiving:
            self.log_message("Receive is already running.", color="orange")
            return
        
        self.is_receiving = True
        
        # 启动接收和解析线程
        self.start_receive_and_parse_threads()
        
        # 重置心跳状态
        lang = LANGUAGES[self.lang]
        self.heartbeat_status_var.set(lang['waiting'])
        self.heartbeat_count = 0
        self.last_heartbeat_time = None
        
        # 重置表格中的心跳状态
        current_time = datetime.now().strftime("%H:%M:%S")
        self.update_table_item('0x351', lang['table_351'][0][0], '0', '', lang['waiting'], current_time)
        
        self.log_message("Started receiving CAN messages.", color="green")
    
    def stop_receiving(self):
        """停止接收CAN报文"""
        if not self.is_receiving:
            self.log_message("Receive is not running.", color="orange")
            return
        
        self.is_receiving = False
        
        # 停止接收和解析线程
        self.stop_receive_and_parse_threads()
        
        # 重置心跳状态
        lang = LANGUAGES[self.lang]
        self.heartbeat_status_var.set(lang['stop'])
        self.heartbeat_count = 0
        self.last_heartbeat_time = None
        
        # 重置表格中的心跳状态
        current_time = datetime.now().strftime("%H:%M:%S")
        self.update_table_item('0x351', lang['table_351'][0][0], '0', '', lang['stop'], current_time)
        
        self.log_message("Stopped receiving CAN messages.", color="green")
    
    def toggle_receive(self):
        """切换接收状态 - 复选框回调函数"""
        if self.receive_var.get():
            self.start_receiving()
        else:
            self.stop_receiving()
    
    def _update_heartbeat_gui(self, heartbeat_count):
        """异步更新心跳GUI状态"""
        try:
            lang = LANGUAGES[self.lang]
            self.heartbeat_status_var.set(lang['normal'])
            self.heartbeat_status_label.config(foreground="black")
            
            # 更新表格中的心跳状态 - 使用语言无关的tag
            current_time = datetime.now().strftime("%H:%M:%S")
            heartbeat_key = lang['table_351'][0][1]  # Get the key 'heartbeat_status'
            heartbeat_tag = f"0x351_{heartbeat_key}"
            self.update_table_item(heartbeat_tag,'0x351', str(heartbeat_count), '', lang['normal'], current_time)
            self.set_table_item_color('0x351', 'heartbeat_status', 'black')
        except Exception as e:
            self.log_message(f"Update heartbeat GUI error: {str(e)}")
    
    def handle_heartbeat_timeout(self):
        """处理心跳超时"""
        lang = LANGUAGES[self.lang]
        self.heartbeat_status_var.set(lang['stop'])
        # 设置统计信息区域为红色
        self.heartbeat_status_label.config(foreground="red")
        # 更新表格中的心跳状态 - 使用语言无关的tag
        current_time = datetime.now().strftime("%H:%M:%S")
        heartbeat_key = lang['table_351'][0][1]  # Get the key 'heartbeat_status'
        heartbeat_tag = f"0x351_{heartbeat_key}"
        self.update_table_item(heartbeat_tag, '0x351', str(self.heartbeat_count), '', lang['stop'], current_time)
        # 设置表格中"停止"为红色
        self.set_table_item_color('0x351', 'heartbeat_status', 'red')
        # 日志记录
        self.log_message("Warning: BMS heartbeat terminated, 3 seconds no 0x351 message received", color="red")

    def process_received_message(self, msg):
        """处理接收到的CAN报文"""
        msg_id = msg['id']
        
        # 扩展支持的CAN ID列表 0x35E, 0x35F
        supported_ids = [0x351, 0x355, 0x356, 0x35A]
        
        # 添加新的0x6nn系列ID支持
        for i in range(7):  # 支持电池地址0-6
            supported_ids.extend([
                0x600 + i, 0x610 + i, 0x620 + i, 0x630 + i, 0x640 + i, 0x650 + i, 0x660 + i, 0x670 + i,
                0x400 + i, 0x410 + i, 0x420 + i, 0x430 + i, 0x440 + i, 0x450 + i, 0x460 + i,
                0x470 + i, 0x480 + i, 0x490 + i, 0x4A0 + i, 0x4B0 + i, 0x4C0 + i, 0x4D0 + i
            ])
        
        if msg_id in supported_ids:
            self.log_message(f"Parsing message: ID=0x{msg_id:03X}, Data: {bytes(msg['data']).hex()}")
            
            # 根据协议解析具体内容
            self.parse_can_message(msg)

    def create_data_table(self, parent):
        """创建数据表格"""
        # 创建表格框架
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True)
        
        # 创建Treeview表格 - 调整高度
        lang = LANGUAGES[self.lang]
        columns = ('CAN ID', 'parameter', 'value', 'unit', 'status', 'refresh_time')
        column_texts = (lang['can_id'], lang['parameter'], lang['value'], lang['unit'], lang['status_col'], lang['refresh_time'])
        self.data_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=12)  # 增加高度
        
        # 设置列标题
        for i, col in enumerate(columns):
            self.data_tree.heading(col, text=column_texts[i])
            # 调整列宽
            if col == 'CAN ID':
                self.data_tree.column(col, width=80, anchor='center')
            elif col == 'parameter':
                self.data_tree.column(col, width=150, anchor='w')
            elif col == 'value':
                self.data_tree.column(col, width=100, anchor='center')
            elif col == 'unit':
                self.data_tree.column(col, width=60, anchor='center')
            elif col == 'status':
                self.data_tree.column(col, width=80, anchor='center')
            elif col == 'refresh_time':
                self.data_tree.column(col, width=120, anchor='center')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.data_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 初始化表格数据
        self.initialize_table_data()
    
    def initialize_table_data(self):
        """初始化表格数据，并为每一行添加唯一的、语言无关的tag"""
        lang = LANGUAGES[self.lang]
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        def insert_row(can_id, label, key, unit=''):
            tag = f"{can_id}_{key}"
            values = (can_id, label, '--', unit, lang['waiting'], '--')
            self.data_tree.insert('', 'end', values=values, tags=(tag,))

        # 0x351
        label, key = lang['table_351'][0]
        insert_row('0x351', label, key)
        for label, key in lang['table_351'][1:]:
            unit = 'V' if 'voltage' in key else 'A' if 'current' in key else ''
            insert_row('0x351', label, key, unit)
        
        # 0x355
        for label, key in lang.get('table_355', []):
            unit = '%' if 'soc' in key.lower() or 'soh' in key.lower() else ''
            insert_row('0x355', label, key, unit)
        
        # 0x356
        for label, key in lang.get('table_356', []):
            unit = 'V' if 'voltage' in key else 'A' if 'current' in key else '°C' if 'temperature' in key else ''
            insert_row('0x356', label, key, unit)

        self.data_tree.insert('', 'end', values=('', '', '', '', '', ''), tags=('divider15',))
        self.data_tree.tag_configure('divider15', background='#bcd9f3')
        # 0x35A
        for label, key in lang['table_35A_alarm']:
            insert_row('0x35A', label, key)

        self.data_tree.insert('', 'end', values=('', '', '', '', '', ''), tags=('divider14',))
        self.data_tree.tag_configure('divider14', background='#bcd9f3')

        for label, key in lang['table_35A_warning']:
            insert_row('0x35A', label, key)

        self.data_tree.insert('', 'end', values=('', '', '', '', '', ''), tags=('divider',))
        self.data_tree.tag_configure('divider', background='#bcd9f3')

        # 0x600, 0x610, etc.
        tables_to_process = [
            ('table_600_base', '0x600'), ('table_600_status', '0x600'), ('table_600_alarms', '0x600'),
            ('divider1', None), 
            ('table_610', '0x610'),
            ('divider2', None),
            ('table_620', '0x620'), ('table_630', '0x630'), ('table_640', '0x640'), ('table_650', '0x650'),
            ('divider3', None),
            ('table_660', '0x660'),
            ('divider4', None),
            ('table_670', '0x670'),
            ('divider5', None),
            ('table_400', '0x400'), ('table_410', '0x410'),
            ('divider6', None),
            ('table_420', '0x420'),
            ('divider7', None),
            ('table_430', '0x430'),
            ('divider8', None),
            ('table_440', '0x440'),
            ('divider9', None),
            ('table_450', '0x450'), ('table_460', '0x460'),
            ('divider10', None),
            ('table_470', '0x470'), ('table_480', '0x480'),
            ('divider11', None),
            ('table_490', '0x490'),
            ('divider12', None),
            ('table_4A0', '0x4A0'),
            ('divider13', None),
            ('table_4B0', '0x4B0'), ('table_4C0', '0x4C0'), ('table_4D0', '0x4D0')
        ]

        for table_name, can_id in tables_to_process:
            if can_id:
                for label, key in lang.get(table_name, []):
                    insert_row(can_id, label, key)
            else:
                self.data_tree.insert('', 'end', values=('', '', '', '', '', ''), tags=(table_name,))
                self.data_tree.tag_configure(table_name, background='#bcd9f3')
    def update_table_data(self, can_id, parsed_data):
        """更新表格数据 - 使用key进行更新"""
        lang = LANGUAGES[self.lang]
        current_time = datetime.now().strftime("%H:%M:%S")

        def fmt_scalar(key, val):
            # (This function remains unchanged)
            unit = ''
            if key == 'operation_mode':
                op = {1: "Standby Mode", 2: "Run Mode", 3: "Charge Disabled !", 4: "Charge DC/DC !", 5: "Discharge Disabled !", 6: "Emergency !"}
                return op.get(val, f"模式{val}"), unit
            if key == 'external_output':
                eo = {0: "Unused", 1: "Heater", 2:"Solenoid"}
                return eo.get(val, f"输出{val}"), unit
            if key == 'max_charge_current':
                max_charge_current_dict = {0: "Not set", 1: "100", 2: "200"}
                return max_charge_current_dict.get(val, f"{val}"), 'A'
            if key in ('state_of_charge', 'state_of_health'): return f"{val}", '%'
            if 'voltage' in key: return f"{val}", 'V'
            if 'current' in key: return f"{val}", 'A'
            if ('temperature' in key) or ('temp' in key): return f"{val}", '°C'
            if 'uptime' in key: return f"{val}", 's'
            if 'accelerometer' in key: return f"{val}", 'milli-g'
            if key == 'esp32_free_heap_size_byte': return f"{val}", 'B'
            if key in ('cycle_count', 'lifetime_hour', 'cell_balance_state', 'module_id'):
                u = 'h' if key == 'lifetime_hour' else ('次' if key == 'cycle_count' else '')
                return f"{val}", u
            if isinstance(val, bool): return str(int(val)), ''
            return str(val), ''

        # Special handling for 0x35A with nested data
        if can_id == 0x35A:
            alarms = parsed_data.get('alarms', {})
            for key, value in alarms.items():
                tag = f"0x35A_{key}"
                self.update_table_item(tag, '0x35A', str(int(value)), '', lang['normal'], current_time)
            
            warnings = parsed_data.get('warnings', {})
            for key, value in warnings.items():
                tag = f"0x35A_{key}"
                self.update_table_item(tag, '0x35A', str(int(value)), '', lang['normal'], current_time)
            return # Stop further processing for this message

        # Generic handling for other messages
        for key, value in parsed_data.items():
            if key == 'battery_address': continue

            # Determine display CAN ID (always actual ID in hex)
            display_can_id = f'0x{can_id:03X}'
            
            # Determine tag CAN ID for lookup
            if (0x600 <= can_id <= 0x6FF) or (0x400 <= can_id <= 0x4FF):
                # For 6xx messages, use group ID for tag (e.g., 0x600)
                tag_can_id_str = f'0x{(can_id & 0xFF0):03X}'
            else:
                # For other messages, use actual ID for tag
                tag_can_id_str = display_can_id

            tag = f"{tag_can_id_str}_{key}"
            
            val_str, unit = fmt_scalar(key, value)
            
            self.update_table_item(tag, display_can_id, val_str, unit, lang['normal'], current_time)

    def update_table_item(self, tag, can_id, value, unit, status, update_time):
        """使用唯一的、语言无关的tag来更新表格行"""
        # Treeview's `set` method can find items by tag
        items = self.data_tree.tag_has(tag)
        if items:
            item_id = items[0]
            current_values = list(self.data_tree.item(item_id, 'values'))
            # Update the values, keeping the parameter name (current_values[1]) as is
            self.data_tree.item(item_id, values=(
                can_id, 
                current_values[1], 
                value, 
                unit if unit else current_values[3], # Preserve unit if new one is empty
                status, 
                update_time
            ))
        # else: # Row not found, which is unexpected if initialized correctly
        #     print(f"Warning: Could not find table item with tag: {tag}")

    def create_send_data_table(self, parent):
        """创建发送数据表格"""
        # 创建表格框架
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="x")
        
        # 创建Treeview表格 - 调整高度
        lang = LANGUAGES[self.lang]
        columns = ('CAN ID', 'send_status', 'send_count', 'status', 'send_time')
        column_texts = (lang['can_id'], lang['send_status'], lang['send_count'], lang['status_col'], lang['send_time'])
        self.send_data_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=3)  # 减少高度
        
        # 设置列标题
        for i, col in enumerate(columns):
            self.send_data_tree.heading(col, text=column_texts[i])
            # 调整列宽
            if col == 'CAN ID':
                self.send_data_tree.column(col, width=80, anchor='center')
            elif col == 'send_status':
                self.send_data_tree.column(col, width=150, anchor='w')
            elif col == 'send_count':
                self.send_data_tree.column(col, width=100, anchor='center')
            elif col == 'status':
                self.send_data_tree.column(col, width=80, anchor='center')
            elif col == 'send_time':
                self.send_data_tree.column(col, width=120, anchor='center')
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.send_data_tree.yview)
        self.send_data_tree.configure(yscrollcommand=scrollbar.set)
        
        # 布局
        self.send_data_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 初始化发送数据表格
        self.initialize_send_data_table()
    
    def initialize_send_data_table(self):
        """初始化发送数据表格"""
        lang = LANGUAGES[self.lang]
        
        # 清空现有数据
        for item in self.send_data_tree.get_children():
            self.send_data_tree.delete(item)
        
        # 添加0x305数据项 - 初始状态为"停止发送"
        self.send_data_tree.insert('', 'end', values=('0x305', lang['stop_send'], '0', lang['stop'], '--'))
        
        # 添加0x307数据项 - 初始状态为"停止发送"
        self.send_data_tree.insert('', 'end', values=('0x307', lang['stop_send'], '0', lang['stop'], '--'))
    
    def update_send_data_table(self, can_id, status, count, send_time):
        """更新发送数据表格"""
        lang = LANGUAGES[self.lang]
        if can_id == 0x305:
            self.update_send_table_item('0x305', status, str(count), lang['normal'], send_time)
        elif can_id == 0x307:
            self.update_send_table_item('0x307', status, str(count), lang['normal'], send_time)
    
    def update_send_table_item(self, can_id, send_status, count, status, send_time):
        """更新发送表格中的单个项目"""
        for item in self.send_data_tree.get_children():
            values = self.send_data_tree.item(item)['values']
            if values[0] == can_id:
                self.send_data_tree.item(item, values=(can_id, send_status, count, status, send_time))
                break

    def start_auto_save_on_startup(self):
        """程序启动时自动开始保存日志"""
        if self.auto_save_var.get():
            self.start_auto_save()

    def on_language_change(self, event=None):
        self.lang = self.lang_var.get()
        print(f"CAN工具语言切换: {self.lang}")
        self.refresh_ui_language()
    
    def set_language(self, language):
        """外部设置语言的方法，用于统一管理器调用"""
        if language in LANGUAGES:
            self.lang = language
            if hasattr(self, 'lang_var'):
                self.lang_var.set(language)
            print(f"CAN tool external language set: {language}")
            self.refresh_ui_language()
            print(f"CAN工具语言设置完成: {language}")
        else:
            print(f"CAN工具不支持的语言: {language}")

    def refresh_ui_language(self):
        """刷新UI语言显示"""
        lang = LANGUAGES[self.lang]
        
        # 更新窗口标题（只在独立模式下）
        if not self.is_embedded and self.root:
            self.root.title(lang['title'])
        
        # 更新按钮文本
        self.connect_btn.config(text=lang['connect'])
        self.disconnect_btn.config(text=lang['disconnect'])
        self.start_btn.config(text=lang['start_send'])
        self.stop_btn.config(text=lang['stop_send'])
        self.receive_check.config(text=lang['open_receive'])
        
        # 更新LabelFrame标题
        self.connection_frame.config(text=lang['connection_settings'])
        self.control_frame.config(text=lang['control'])
        self.stats_frame.config(text=lang['stat_info'])
        self.send_data_frame.config(text=lang['send_data'])
        self.data_frame.config(text=lang['realtime_data'])
        self.log_frame.config(text=lang['log'])
        
        # 更新连接状态显示
        current_status = self.status_var.get()
        if current_status in ['未连接', 'Disconnected']:
            self.status_var.set(lang['disconnected'])
        elif current_status in ['已连接', 'Connected']:
            self.status_var.set(lang['connected'])
        
        # 更新心跳状态显示
        current_heartbeat_status = self.heartbeat_status_var.get()
        if current_heartbeat_status in ['正常', 'Normal']:
            self.heartbeat_status_var.set(lang['normal'])
            self.heartbeat_status_label.config(foreground="black") # 恢复黑色
            self.set_table_item_color('0x351', 'heartbeat_status', 'black')
        elif current_heartbeat_status in ['等待', 'Waiting']:
            self.heartbeat_status_var.set(lang['waiting'])
            self.heartbeat_status_var.set(lang['waiting'])
            self.heartbeat_status_label.config(foreground="black") # 恢复黑色
            self.set_table_item_color('0x351', 'heartbeat_status', 'black')
        elif current_heartbeat_status in ['停止', 'Stop']:
            self.heartbeat_status_var.set(lang['stop'])
            self.heartbeat_status_var.set(lang['stop'])
            self.heartbeat_status_label.config(foreground="red") # 设置统计信息区域为红色
            self.set_table_item_color('0x351', 'heartbeat_status', 'red')
        
        # 更新标签文本
        self.update_label_texts(lang)
        
        # 只更新表格列标题和文本内容，不重建表格
        self.refresh_table_headers()
        self.update_table_language()
        self.update_send_table_language()
    
    def update_label_texts(self, lang):
        """更新所有标签的文本"""
        # 这个方法会递归遍历所有控件并更新文本
        def update_widget_texts(widget):
            try:
                if isinstance(widget, ttk.Label):
                    text = widget.cget('text')
                    # 更新特定的标签文本
                    if '语言/Language:' in text or 'Language:' in text:
                        widget.config(text=lang['language'])
                    elif '设备类型:' in text or 'Device Type:' in text:
                        widget.config(text=lang.get('device_type', '设备类型:' if self.lang == 'zh' else 'Device Type:'))
                    elif '设备索引:' in text or 'Device Index:' in text:
                        widget.config(text=lang.get('device_index', '设备索引:' if self.lang == 'zh' else 'Device Index:'))
                    elif 'CAN通道:' in text or 'CAN Channel:' in text:
                        widget.config(text=lang.get('can_channel', 'CAN通道:' if self.lang == 'zh' else 'CAN Channel:'))
                    elif '波特率:' in text or 'Baud Rate:' in text:
                        widget.config(text=lang.get('baud_rate', '波特率:' if self.lang == 'zh' else 'Baud Rate:'))
                    elif '发送控制:' in text or 'Send Control:' in text:
                        widget.config(text=lang['send_control'])
                    elif '接收控制:' in text or 'Receive Control:' in text:
                        widget.config(text=lang['receive_control'])
                    elif '发送:' in text or 'Send:' in text:
                        widget.config(text=lang['send'] + ':')
                    elif '接收:' in text or 'Receive:' in text:
                        widget.config(text=lang['receive'] + ':')
                    elif '心跳状态:' in text or 'Heartbeat:' in text:
                        widget.config(text=lang['heartbeat_status'] + ':')
                elif isinstance(widget, ttk.Button):
                    text = widget.cget('text')
                    if '清空日志' in text or 'Clear Log' in text:
                        widget.config(text=lang['clear_log'])
                elif isinstance(widget, ttk.Checkbutton):
                    text = widget.cget('text')
                    if '自动保存日志' in text or 'Auto Save Log' in text:
                        widget.config(text=lang['auto_save_log'])
                
                # 递归更新所有子控件
                for child in widget.winfo_children():
                    update_widget_texts(child)
                    
            except Exception as e:
                print(f"更新控件文本时出错: {e}")
        
        # 从主框架开始递归更新
        if hasattr(self, 'main_frame'):
            update_widget_texts(self.main_frame)
        elif hasattr(self, 'root') and self.root:
            update_widget_texts(self.root)
    
    def refresh_table_headers(self):
        """刷新表格表头语言"""
        lang = LANGUAGES[self.lang]
        
        # 更新实时数据表格表头
        if hasattr(self, 'data_tree'):
            columns = ('CAN ID', 'parameter', 'value', 'unit', 'status', 'refresh_time')
            column_texts = (lang['can_id'], lang['parameter'], lang['value'], 
                           lang['unit'], lang['status_col'], lang['refresh_time'])
            for i, col in enumerate(columns):
                self.data_tree.heading(col, text=column_texts[i])
        
        # 更新发送数据表格表头
        if hasattr(self, 'send_data_tree'):
            columns = ('CAN ID', 'send_status', 'send_count', 'status', 'send_time')
            column_texts = (lang['can_id'], lang['send_status'], lang['send_count'], 
                           lang['status_col'], lang['send_time'])
            for i, col in enumerate(columns):
                self.send_data_tree.heading(col, text=column_texts[i])

    def update_table_language(self):
        """更新表格中的参数名称和状态列文本，不重建表格结构"""
        lang = LANGUAGES[self.lang]
        
        # 状态翻译映射
        status_map = {
            '等待': lang['waiting'], 'Waiting': lang['waiting'],
            '正常': lang['normal'], 'Normal': lang['normal'],
            '停止': lang['stop'], 'Stop': lang['stop']
        }
        
        # 创建完整的参数映射表（按initialize_table_data的顺序）
        parameter_list = []
        
        # 按照initialize_table_data的确切顺序添加参数
        parameter_list.extend([(label, '0x351') for label, key in lang['table_351']])
        parameter_list.extend([(label, '0x355') for label, key in lang.get('table_355', [])])
        parameter_list.extend([(label, '0x356') for label, key in lang.get('table_356', [])])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x35A') for label, key in lang['table_35A_alarm']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x35A') for label, key in lang['table_35A_warning']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x600') for label, key in lang['table_600_base']])
        parameter_list.extend([(label, '0x600') for label, key in lang['table_600_status']])
        parameter_list.extend([(label, '0x600') for label, key in lang['table_600_alarms']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x610') for label, key in lang['table_610']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x620') for label, key in lang['table_620']])
        parameter_list.extend([(label, '0x630') for label, key in lang['table_630']])
        parameter_list.extend([(label, '0x640') for label, key in lang['table_640']])
        parameter_list.extend([(label, '0x650') for label, key in lang['table_650']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x660') for label, key in lang['table_660']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x670') for label, key in lang['table_670']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x400') for label, key in lang['table_400']])
        parameter_list.extend([(label, '0x410') for label, key in lang['table_410']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x420') for label, key in lang['table_420']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x430') for label, key in lang['table_430']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x440') for label, key in lang['table_440']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x450') for label, key in lang['table_450']])
        parameter_list.extend([(label, '0x460') for label, key in lang['table_460']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x470') for label, key in lang['table_470']])
        parameter_list.extend([(label, '0x480') for label, key in lang['table_480']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x490') for label, key in lang['table_490']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x4A0') for label, key in lang['table_4A0']])
        parameter_list.append(('', ''))  # 分割行
        parameter_list.extend([(label, '0x4B0') for label, key in lang['table_4B0']])
        parameter_list.extend([(label, '0x4C0') for label, key in lang['table_4C0']])
        parameter_list.extend([(label, '0x4D0') for label, key in lang['table_4D0']])
        
        # 批量更新表格
        items = self.data_tree.get_children()
        for i, item in enumerate(items):
            if i < len(parameter_list):
                new_label, expected_can_id = parameter_list[i]
                values = list(self.data_tree.item(item)['values'])
                
                # 更新参数名称
                if len(values) > 1:
                    values[1] = new_label
                
                # 更新状态
                if len(values) > 4 and values[4] in status_map:
                    values[4] = status_map[values[4]]
                
                self.data_tree.item(item, values=values)

    def update_send_table_language(self):
        """更新发送数据表格中的状态文本，不重建表格结构"""
        lang = LANGUAGES[self.lang]
        
        # 获取现有的表格行
        items = self.send_data_tree.get_children()
        
        # 更新每一行的状态文本
        for item in items:
            values = list(self.send_data_tree.item(item)['values'])
            
            if len(values) > 1:
                # 更新发送状态列（第2列，索引1）
                current_send_status = values[1]
                if current_send_status in ['停止发送', 'Stop Send']:
                    values[1] = lang['stop_send']
                elif current_send_status in ['正在发送', 'Sending']:
                    values[1] = lang['start_send_status']
                elif current_send_status in ['已停止', 'Stopped']:
                    values[1] = lang['stopped']
            
            if len(values) > 3:
                # 更新状态列（第4列，索引3）
                current_status = values[3]
                if current_status in ['停止', 'Stop']:
                    values[3] = lang['stop']
                elif current_status in ['正常', 'Normal']:
                    values[3] = lang['normal']
            
            # 应用更新
            self.send_data_tree.item(item, values=values)

    def set_table_item_color(self, can_id_str, data_key, color):
        """设置表格中特定行的字体颜色 (通过tag)"""
        tag = f"{can_id_str}_{data_key}"
        items = self.data_tree.tag_has(tag)
        if items:
            item_id = items[0]
            color_tag = f"color_{color}"
            self.data_tree.tag_configure(color_tag, foreground=color)
            
            current_tags = list(self.data_tree.item(item_id, 'tags'))
            current_tags = [t for t in current_tags if not t.startswith('color_')]
            current_tags.append(color_tag)
            self.data_tree.item(item_id, tags=tuple(current_tags))
    
    def force_refresh_display(self):
        """强制刷新显示，解决标签页切换后控件不显示的问题"""
        try:
            # 强制更新主框架
            if hasattr(self, 'main_frame'):
                self.main_frame.update_idletasks()
                
            # 强制更新表格
            if hasattr(self, 'data_tree'):
                self.data_tree.update_idletasks()
                
            if hasattr(self, 'send_data_tree'):
                self.send_data_tree.update_idletasks()
                
            # 强制更新日志文本框
            if hasattr(self, 'log_text'):
                self.log_text.update_idletasks()
                
            # 递归更新所有子控件
            self.recursive_update_widgets(self.main_frame)
            
        except Exception as e:
            print(f"CAN工具强制刷新显示错误: {e}")
    
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

def main():
    # 独立运行模式
    app = CANHostComputer() 
    
    # 设置窗口关闭事件处理
    def on_closing():
        if app.auto_save_var.get():
            app.stop_auto_save()
        app.root.destroy()
    
    app.root.protocol("WM_DELETE_WINDOW", on_closing)
    app.root.mainloop()

def create_embedded_instance(parent_frame, initial_language=None):
    """创建嵌入模式的实例，用于统一工具管理器"""
    return CANHostComputer(parent_frame, initial_language)

if __name__ == "__main__":
    main()