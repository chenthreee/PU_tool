#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI组件模块
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import serial.tools.list_ports
import datetime
import json
import os

# 添加语言管理器导入
try:
    from mobus_tool.language_manager import LanguageManager
except ImportError:
    # 如果导入失败，创建一个简单的默认类
    class LanguageManager:
        def get_text(self, key, default=None):
            return default or key

class OverviewFrame(ttk.Frame):
    """Overview page displaying key parameters from multiple models"""
    
    def __init__(self, parent, protocol, modbus_client, main_window=None, language_manager=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.protocol = protocol
        self.modbus_client = modbus_client
        self.main_window = main_window
        self.language_manager = language_manager or LanguageManager()
        
        # Define the key parameters to display from each model
        self.overview_fields = {
            802: [
                {"name": "StateVnd", "label": "Vendor Battery Bank State"},
            ],
            805: [
                {"name": "SoC", "label": "Module SoC"},
            ],
            64950: [
                {"name": "Cell voltage sum", "label": "Cell voltage sum"},
                {"name": "battery voltage", "label": "battery voltage"},
                {"name": "Rail voltage", "label": "Rail voltage"},
                {"name": "Cell1_voltage", "label": "Cell1_voltage"},
                {"name": "Cell2_voltage", "label": "Cell2_voltage"},
                {"name": "Cell3_voltage", "label": "Cell3_voltage"},
                {"name": "Cell4_voltage", "label": "Cell4_voltage"},
                {"name": "Cell5_voltage", "label": "Cell5_voltage"},
                {"name": "Cell6_voltage", "label": "Cell6_voltage"},
                {"name": "Cell7_voltage", "label": "Cell7_voltage"},
                {"name": "Cell8_voltage", "label": "Cell8_voltage"},
                {"name": "Cell9_voltage", "label": "Cell9_voltage"},
                {"name": "Cell10_voltage", "label": "Cell10_voltage"},
                {"name": "Cell11_voltage", "label": "Cell11_voltage"},
                {"name": "Cell12_voltage", "label": "Cell12_voltage"},
                {"name": "Cell13_voltage", "label": "Cell13_voltage"},
                {"name": "Cell14_voltage", "label": "Cell14_voltage"},
                {"name": "Cell15_voltage", "label": "Cell15_voltage"},
                {"name": "Cell16_voltage", "label": "Cell16_voltage"},
                {"name": "Cell temperature1", "label": "Cell temperature1"},
                {"name": "Cell temperature2", "label": "Cell temperature2"},
                {"name": "Cell temperature3", "label": "Cell temperature3"},
                {"name": "Cell temperature4", "label": "Cell temperature4"},
                {"name": "Positive terminal temp", "label": "Positive terminal temp"},
                {"name": "Negative terminal temp", "label": "Negative terminal temp"},
                {"name": "Positive Bat temp", "label": "Positive Bat temp"},
                {"name": "Negative Bat temp1", "label": "Negative Bat temp1"},
                {"name": "Negative Bat temp2", "label": "Negative Bat temp2"},
                {"name": "Discharge MOS temp", "label": "Discharge MOS temp"},
                {"name": "Charge MOS temp", "label": "Charge MOS temp"},
                {"name": "DC/DC temperature", "label": "DC/DC temperature"},
                {"name": "Current1", "label": "Current1"},
                {"name": "Coulomb Charge", "label": "Coulomb Charge"},
            ],
            64900: [
                {"name": "AFEDieTemperature", "label": "AFE die temperature"},
                {"name": "MCUDieTemperature", "label": "MCU die temperature"},
                {"name": "Alarms", "label": "Alarms"},
            ],
            64952:[
                {"name": "current_capacity", "label": "current_capacity"},
                {"name": "current_charge","label": "current_charge"},
                {"name": "product_version","label": "product_version"}
            ]

        }
        
        self.entries = {}  # Store display variables for each field
        self.bitfield_entries = {}  # Store display variables for bitfield sub-items
        self.setup_overview_table()
    
    def setup_overview_table(self):
        """Setup the overview table with key parameters - same format as table pages"""
        # Use same headers as DataTableFrame
        headers = [
            self.language_manager.get_text("model_id"),
            self.language_manager.get_text("field_name"),
            self.language_manager.get_text("value"),
            self.language_manager.get_text("update_time"),
            self.language_manager.get_text("unit"),
            self.language_manager.get_text("type"),
            self.language_manager.get_text("description"),
            self.language_manager.get_text("access_rights")
        ]
        
        col_widths = [60, 120, 80, 80, 60, 70, 200, 60]
        self.headers = []  # 保存表头引用以便更新
        
        for col, h in enumerate(headers):
            header_label = ttk.Label(self, text=h, anchor='center', borderwidth=1, relief='solid')
            header_label.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
            self.headers.append(header_label)  # 保存引用
            self.grid_columnconfigure(col, weight=1, minsize=col_widths[col])
        
        # Create parameter rows
        self.create_parameter_rows()
    
    def create_parameter_rows(self):
        """Create rows for each parameter - same format as DataTableFrame"""
        current_row = 1
        
        for model_id, fields in self.overview_fields.items():
            for field_info in fields:
                field_name = field_info["name"]
                field_label = field_info["label"]
                
                # Get field details from the protocol definition
                field_details = None  # Initialize to None
                unit = ''
                field_type = ''
                description = ''
                table_info = self.protocol.get_table_info(model_id)
                if table_info and 'fields' in table_info:
                    field_details = table_info['fields'].get(field_name)
                    if field_details:
                        unit = field_details.get('unit', '')
                        field_type = field_details.get('type', '')
                        description = field_details.get('description', '')
                
                # Create variables for this row
                value_var = tk.StringVar(value='-')
                update_time_var = tk.StringVar(value='-')
                unit_var = tk.StringVar(value=unit)
                type_var = tk.StringVar(value=field_type)
                desc_var = tk.StringVar(value=description)
                
                # Model ID
                ttk.Label(self, text=model_id).grid(row=current_row, column=0, sticky='nsew')
                
                # Field name 
                ttk.Label(self, text=field_label).grid(row=current_row, column=1, sticky='nsew')
                
                # Value
                value_label = ttk.Label(self, textvariable=value_var, wraplength=200, justify='left')
                value_label.grid(row=current_row, column=2, sticky='nsew')
                
                # Update time
                ttk.Label(self, textvariable=update_time_var).grid(row=current_row, column=3, sticky='nsew')
                
                # Unit
                ttk.Label(self, textvariable=unit_var).grid(row=current_row, column=4, sticky='nsew')
                
                # Type
                ttk.Label(self, textvariable=type_var).grid(row=current_row, column=5, sticky='nsew')
                
                # Description
                desc_label = ttk.Label(self, textvariable=desc_var, wraplength=300, justify='left')
                desc_label.grid(row=current_row, column=6, sticky='nsew')
                
                # Access rights (always 'r' for overview)
                ttk.Label(self, text='r').grid(row=current_row, column=7, sticky='nsew')
                
                # Store references
                key = f"{model_id}_{field_name}"
                self.entries[key] = {
                    'value_var': value_var,
                    'time_var': update_time_var,
                    'unit_var': unit_var,
                    'type_var': type_var,
                    'desc_var': desc_var,
                    'model_id': model_id,
                    'field_name': field_name
                }
                
                current_row += 1

                # If it's a bitfield32 with symbols, add sub-items
                if field_details and field_type == 'bitfield32' and field_details.get('symbols'):
                    current_row = self.create_bitfield_subitems(model_id, field_name, field_details, current_row)
    
    def create_bitfield_subitems(self, model_id, field_name, field_details, current_row):
        """为bitfield32字段创建子项显示每一位的状态"""
        symbols = field_details.get('symbols', [])
        if not symbols:
            return current_row

        parent_key = f"{model_id}_{field_name}"
        
        if parent_key not in self.bitfield_entries:
            self.bitfield_entries[parent_key] = {}
        
        for symbol in symbols:
            bit_name = symbol.get('name', f'Bit_{symbol.get("value", 0)}')
            bit_position = symbol.get('value', 0)
            
            # Model ID (empty for sub-items)
            ttk.Label(self, text='').grid(row=current_row, column=0, sticky='nsew')
            
            # Bit name (indented)
            bit_label = ttk.Label(self, text=f"  └ {bit_name} (Bit {bit_position})")
            bit_label.grid(row=current_row, column=1, sticky='nsew', padx=(20, 0))
            
            # Bit value
            bit_value_var = tk.StringVar(value="-")
            bit_value_label = ttk.Label(self, textvariable=bit_value_var)
            bit_value_label.grid(row=current_row, column=2, sticky='nsew')
            
            # Empty cells for other columns
            for col in range(3, 8):
                ttk.Label(self, text='').grid(row=current_row, column=col, sticky='nsew')
            
            self.bitfield_entries[parent_key][bit_name] = bit_value_var
            
            current_row += 1
        
        return current_row

    def update_bitfield_display(self, model_id, field_name, field_data):
        """更新bitfield32字段的位状态显示"""
        parent_key = f"{model_id}_{field_name}"
        if parent_key not in self.bitfield_entries:
            return
        
        raw_value = field_data.get('raw_value', field_data.get('raw', 0))
        if raw_value is None:
            raw_value = 0
        
        if isinstance(raw_value, str):
            try:
                raw_value = int(raw_value, 16) if raw_value.startswith('0x') else int(raw_value)
            except (ValueError, TypeError):
                raw_value = 0

        table_info = self.protocol.get_table_info(model_id)
        if not table_info or 'fields' not in table_info:
            return
        field_details = table_info['fields'].get(field_name)
        if not field_details or 'symbols' not in field_details:
            return
        
        symbols = field_details.get('symbols', [])
        bit_status = self.protocol.parse_bitfield32_bits(raw_value, symbols)
        
        for bit_name, bit_info in bit_status.items():
            if bit_name in self.bitfield_entries[parent_key]:
                bit_var = self.bitfield_entries[parent_key][bit_name]
                bit_var.set(str(bit_info['status']))

    def update_field_data(self, model_id, field_name, field_data, timestamp=None):
        """Update a specific field's data"""
        key = f"{model_id}_{field_name}"
        if key not in self.entries:
            return
        
        entry = self.entries[key]
        
        if isinstance(field_data, dict):
            display_value = field_data.get('display_value', field_data.get('value', '--'))
        else:
            display_value = str(field_data)

        # 如果是数组类型，格式化为逗号分隔
        table_info = self.protocol.get_table_info(model_id)
        if table_info and 'fields' in table_info:
            field_details = table_info['fields'].get(field_name)
            if field_details:
                ftype = str(field_details.get('type', '')).lower()
                if (isinstance(display_value, list) or isinstance(display_value, tuple)) or ('array' in ftype and isinstance(field_data, dict) and isinstance(field_data.get('value'), (list, tuple))):
                    vals = display_value if isinstance(display_value, (list, tuple)) else field_data.get('value', [])
                    try:
                        display_value = ', '.join(str(int(x)) for x in vals)
                    except Exception:
                        display_value = ', '.join(str(x) for x in vals)

        entry['value_var'].set(str(display_value))
        
        if timestamp:
            time_str = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        else:
            time_str = datetime.datetime.now().strftime("%H:%M:%S")
        entry['time_var'].set(time_str)

        # Get field type from protocol definition
        table_info = self.protocol.get_table_info(model_id)
        if table_info and 'fields' in table_info:
            field_details = table_info['fields'].get(field_name)
            if field_details:
                field_type = field_details.get('type', '').lower()
                # If it's a bitfield32, update its sub-items
                if field_type == 'bitfield32':
                    self.update_bitfield_display(model_id, field_name, field_data)
    
    def update_model_data(self, model_id, model_data, timestamp=None):
        """Update all fields for a specific model"""
        if model_id not in self.overview_fields:
            return
        
        for field_info in self.overview_fields[model_id]:
            field_name = field_info["name"]
            if field_name in model_data:
                self.update_field_data(model_id, field_name, model_data[field_name], timestamp)
    
    def clear_data(self):
        """Clear all displayed data"""
        for entry in self.entries.values():
            entry['value_var'].set("-")
            entry['time_var'].set("-")
            entry['unit_var'].set("")
            entry['type_var'].set("")
            entry['desc_var'].set("")

    def update_language(self, language_manager):
        """更新语言"""
        self.language_manager = language_manager
        
        # 更新表头
        new_headers = [
            self.language_manager.get_text("model_id"),
            self.language_manager.get_text("field_name"),
            self.language_manager.get_text("value"),
            self.language_manager.get_text("update_time"),
            self.language_manager.get_text("unit"),
            self.language_manager.get_text("type"),
            self.language_manager.get_text("description"),
            self.language_manager.get_text("access_rights")
        ]
        
        # 更新每个表头标签的文本
        for i, header_text in enumerate(new_headers):
            if i < len(self.headers):
                self.headers[i].config(text=header_text)


class UartCommandFrame(ttk.Frame):
    def __init__(self, parent, modbus_client, main_window=None, language_manager=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.modbus_client = modbus_client
        self.main_window = main_window
        self.language_manager = language_manager or LanguageManager()
        
        # 加载UART命令集数据
        self.uart_commands = self.load_uart_commands()
        self.command_entries = {}  # 存储显示变量
        
        # 加载model_64951.json以获取mcu_read_address映射
        self.mcu_address_mapping = self.load_mcu_address_mapping()
        
        self.setup_uart_table()
    
    def load_uart_commands(self):
        """加载uart_command_set.json文件"""
        try:
            # 支持PyInstaller打包环境的资源路径查找
            def get_resource_path(filename):
                import sys
                if getattr(sys, 'frozen', False):
                    # PyInstaller打包环境 - 文件在根目录
                    base_path = sys._MEIPASS
                    # 先尝试根目录
                    root_path = os.path.join(base_path, filename)
                    if os.path.exists(root_path):
                        return root_path
                    # 如果根目录没有，尝试原始路径
                    return os.path.join(base_path, 'mobus_tool', filename)
                else:
                    # 开发环境
                    return os.path.join(os.path.dirname(__file__), filename)
            
            uart_file_path = get_resource_path('uart_command_set.json')
            with open(uart_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            if self.main_window:
                self.main_window.log_message(f"load uart_command_set.json failed: {e}")
            return []
    
    def load_mcu_address_mapping(self):
        """加载model_64951.json并创建mcu_read_address到index的映射"""
        try:
            # 支持PyInstaller打包环境的资源路径查找
            def get_resource_path(filename):
                import sys
                if getattr(sys, 'frozen', False):
                    # PyInstaller打包环境 - 文件在根目录
                    base_path = sys._MEIPASS
                    # 先尝试根目录
                    root_path = os.path.join(base_path, filename)
                    if os.path.exists(root_path):
                        return root_path
                    # 如果根目录没有，尝试原始路径
                    return os.path.join(base_path, 'mobus_tool', filename)
                else:
                    # 开发环境
                    return os.path.join(os.path.dirname(__file__), filename)
            
            model_file_path = get_resource_path('model_64951.json')
            with open(model_file_path, 'r', encoding='utf-8') as f:
                model_data = json.load(f)
            
            mapping = {}
            if 'group' in model_data and 'points' in model_data['group']:
                for point in model_data['group']['points']:
                    if 'mcu_read_address' in point:
                        mcu_addr = point['mcu_read_address']
                        # 将十六进制地址转换为index格式进行匹配
                        if isinstance(mcu_addr, str) and mcu_addr.startswith('0x'):
                            addr_int = int(mcu_addr, 16)
                            index_str = f"0x{addr_int:X}"
                            mapping[index_str] = point.get('name', '')
                        elif isinstance(mcu_addr, int):
                            index_str = f"0x{mcu_addr:X}"
                            mapping[index_str] = point.get('name', '')
            
            return mapping
        except Exception as e:
            if self.main_window:
                self.main_window.log_message(f"load model_64951.json failed: {e}")
            return {}
    
    def setup_uart_table(self):
        """设置UART命令表格"""
        # 创建表格头
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 表头
        ttk.Label(header_frame, text="item", width=40, relief="solid", borderwidth=1).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Index", width=15, relief="solid", borderwidth=1).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="value", width=20, relief="solid", borderwidth=1).pack(side=tk.LEFT)
        
        # 创建数据行
        for cmd in self.uart_commands:
            self.create_command_row(cmd)
    
    def create_command_row(self, cmd):
        """创建单个命令行"""
        row_frame = ttk.Frame(self)
        row_frame.pack(fill=tk.X, pady=1)
        
        # 项目
        item_label = ttk.Label(row_frame, text=cmd.get('item', ''), width=40, relief="solid", borderwidth=1)
        item_label.pack(side=tk.LEFT)
        
        # Index
        index_text = cmd.get('index', '')
        index_label = ttk.Label(row_frame, text=index_text, width=15, relief="solid", borderwidth=1)
        index_label.pack(side=tk.LEFT)
        
        # 值显示变量
        value_var = tk.StringVar(value="--")
        value_label = ttk.Label(row_frame, textvariable=value_var, width=20, relief="solid", borderwidth=1)
        value_label.pack(side=tk.LEFT)
        
        # 保存显示变量
        self.command_entries[index_text] = {
            'value_var': value_var,
            'cmd_data': cmd
        }
    
    def update_value_by_index(self, index, value):
        """根据index更新对应的值"""
        if index in self.command_entries:
            self.command_entries[index]['value_var'].set(str(value))
            return True
        return False
    
    def update_values_from_model_data(self, model_data):
        """根据model数据更新UART命令的值"""
        if not model_data:
            return
        
        updated_count = 0
        
        # 检查是否有mcu_read_address和mcu_read_data字段
        mcu_read_address_data = model_data.get('mcu_read_address')
        mcu_read_data_data = model_data.get('mcu_read_data')
        
        if mcu_read_address_data and mcu_read_data_data:
            # 获取mcu_read_address的值
            mcu_address = mcu_read_address_data.get('raw_value', mcu_read_address_data.get('value'))
            mcu_data = mcu_read_data_data.get('display_value', mcu_read_data_data.get('raw_value', mcu_read_data_data.get('value')))
            
            if mcu_address is not None and mcu_data is not None:
                # 将地址转换为十六进制格式的索引
                if isinstance(mcu_address, (int, float)):
                    index_str = f"0x{int(mcu_address):X}"
                elif isinstance(mcu_address, str):
                    try:
                        if mcu_address.startswith('0x') or mcu_address.startswith('0X'):
                            addr_int = int(mcu_address, 16)
                        else:
                            addr_int = int(mcu_address)
                        index_str = f"0x{addr_int:X}"
                    except ValueError:
                        index_str = None
                else:
                    index_str = None
                
                # 根据地址匹配更新UART表格
                if index_str and index_str in self.command_entries:
                    target_item = self.command_entries[index_str]
                    item_info = target_item.get('cmd_data', {})
                    item_type = item_info.get('type', 'uint32').lower()  # 默认为uint32
                    
                    parsed_value = mcu_data  # 默认使用原始值
                    
                    # 根据目标项的类型解析uint32数据
                    if isinstance(mcu_data, int):
                        if item_type == 'uint32_t':
                            parsed_value = mcu_data
                        elif item_type == 'int32_t':
                            val = mcu_data & 0xFFFFFFFF
                            parsed_value = val if val < 0x80000000 else val - 0x100000000
                        elif item_type == 'uint16_t':
                            parsed_value = mcu_data & 0xFFFF
                        elif item_type == 'int16_t':
                            val = mcu_data & 0xFFFF
                            parsed_value = val if val < 32768 else val - 65536
                        elif item_type == 'uint8_t':
                             parsed_value = mcu_data & 0xFF
                        elif item_type == 'int8_t':
                            val = mcu_data & 0xFF
                            parsed_value = val if val < 128 else val - 256

                    # 使用解析后的值更新UI
                    if self.update_value_by_index(index_str, parsed_value):
                        updated_count += 1
                        if self.main_window:
                            self.main_window.log_message(f"Update UART parameters for {index_str}: {parsed_value} (raw: {mcu_data}, type: {item_type})")
        
        # 保留原有的更新逻辑作为备用
        for field_name, field_data in model_data.items():
            # 跳过已经处理的mcu字段
            if field_name in ['mcu_read_address', 'mcu_read_data']:
                continue
                
            # 查找对应的mcu_read_address映射
            for index, mapped_name in self.mcu_address_mapping.items():
                if mapped_name == field_name:
                    # 找到匹配的字段，更新对应的UART命令值
                    if self.update_value_by_index(index, field_data.get('display_value', field_data.get('raw_value', '--'))):
                        updated_count += 1
                        if self.main_window:
                            self.main_window.log_message(f" Update UART parameters {index}: {field_name} = {field_data.get('display_value', field_data.get('raw_value', '--'))}")
        
        if self.main_window and updated_count > 0:
            self.main_window.log_message(f"UART parameters updated, total {updated_count} parameters updated")

class DataTableFrame(ttk.Frame):
    def __init__(self, parent, table_id, protocol, modbus_client, main_window=None, language_manager=None,scanned_model_length=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.table_id = table_id
        self.protocol = protocol
        self.modbus_client = modbus_client
        self.main_window = main_window
        self.language_manager = language_manager or LanguageManager()
        self.scanned_model_length = scanned_model_length  # 新增：扫描到的模型长度
        
        # 获取字段信息，支持动态长度
        if scanned_model_length:
            # 如果有扫描到的长度，动态生成字段信息
            self.fields = self.generate_dynamic_fields(scanned_model_length)
        else:
            # 否则使用固定字段信息
            table_info = protocol.get_table_info(table_id)
            self.fields = table_info["fields"]
        
        self.entries = {}
        self.headers = []  # 保存表头引用
        self.bitfield_expanded = {}  # 记录bitfield32字段的展开状态
        self.bitfield_entries = {}  # 保存bitfield32子项的显示变量
        
        self.setup_table()
    def generate_dynamic_fields(self, scanned_length):
            """根据扫描到的模型长度动态生成字段信息"""
            # 获取基础模型信息，传递scanned_length以触发预计算
            table_info = self.protocol.get_table_info(self.table_id, scanned_length)
            if not table_info:
                return {}
            
            fields = {}
            
            # 添加固定points部分
            for field_name, field_info in table_info["fields"].items():
                fields[field_name] = field_info.copy()
            
            # 检查是否有子groups
            if table_info.get("has_groups") and table_info.get("groups_info"):
                groups_info = table_info["groups_info"]
                fixed_length = table_info["length"]  # 固定points部分的长度
                
                # 使用预计算的重复组信息
                for group in groups_info:
                    group_name = group['name']
                    group_points = group['points']
                    
                    # 使用预计算的值
                    single_group_length = group.get('single_group_length', 0)
                    repeat_count = group.get('repeat_count', 0)
                    
                    if repeat_count > 0:
                        
                        # 为每个重复的group生成字段
                        for i in range(repeat_count):
                            current_offset = fixed_length + (i * single_group_length)
                            
                            for gp in group_points:
                                gp_name = gp['name']
                                gp_size = gp.get('size', 1)
                                
                                # 生成字段名
                                field_name = f"{group_name}_{i+1}_{gp_name}"
                                
                                # 计算在扫描数据中的实际偏移
                                data_offset = current_offset
                                
                                fields[field_name] = {
                                    'offset': data_offset,
                                    'size': gp_size,
                                    'type': gp['type'],
                                    'scale': gp.get('sf', 1),
                                    'unit': gp.get('units', ''),
                                    'access': 'rw' if 'access' in gp and gp['access'] == 'RW' else 'r',
                                    'label': f"{gp.get('label', gp_name)} (Group {i+1})",
                                    'description': gp.get('desc', ''),
                                    'group_index': i + 1,
                                    'group_name': group_name,
                                    'is_dynamic_group': True,  # 标识这是动态生成的group字段
                                    'symbols': gp.get('symbols', []) if gp['type'].lower() in ['bitfield32', 'enum16'] else []
                                }
                                
                                current_offset += gp_size
            
            return fields
    def setup_table(self):
        headers = [
            self.language_manager.get_text("field_name"),
            self.language_manager.get_text("value"),
            self.language_manager.get_text("update_time"),
            self.language_manager.get_text("unit"),
            self.language_manager.get_text("type"),
            self.language_manager.get_text("description"),
            self.language_manager.get_text("access_rights"),
            self.language_manager.get_text("read"),
            self.language_manager.get_text("write_value"),
            self.language_manager.get_text("write"),
            self.language_manager.get_text("write_status")
        ]
        
        col_widths = [120, 80, 80, 60, 70, 200, 60, 40, 80, 40, 80]
        self.headers = []  # 保存表头引用以便更新
        
        for col, h in enumerate(headers):
            header_label = ttk.Label(self, text=h, anchor='center', borderwidth=1, relief='solid')
            header_label.grid(row=0, column=col, sticky='nsew', padx=1, pady=1)
            self.headers.append(header_label)  # 保存引用
            self.grid_columnconfigure(col, weight=1, minsize=col_widths[col])
        
        current_row = 1
        for field_name, field_info in self.fields.items():
            current_row = self.create_field_row(field_name, field_info, current_row)
            
            # 如果是bitfield32字段且有symbols，直接添加子项
            if (field_info.get('type', '').lower() == 'bitfield32' and 
                field_info.get('symbols', [])):
                current_row = self.create_bitfield_subitems(field_name, field_info, current_row)

    def create_field_row(self, field_name, field_info, row):
        """创建字段行"""
        value_var = tk.StringVar(value='-')
        update_time_var = tk.StringVar(value='-')
        write_var = tk.StringVar(value='')
        write_status_var = tk.StringVar(value='')
        
        # 使用 label 作为显示名
        display_name = field_info.get('label', field_name)
        
        # 直接显示字段名，不需要展开按钮
        ttk.Label(self, text=display_name).grid(row=row, column=0, sticky='nsew')
        
        # value列也支持自动换行，防止长值被截断
        value_label = ttk.Label(self, textvariable=value_var, wraplength=200, justify='left')
        value_label.grid(row=row, column=1, sticky='nsew')
        ttk.Label(self, textvariable=update_time_var).grid(row=row, column=2, sticky='nsew')
        ttk.Label(self, text=field_info.get('unit', '')).grid(row=row, column=3, sticky='nsew')
        ttk.Label(self, text=field_info.get('type', '')).grid(row=row, column=4, sticky='nsew')
        # description列支持自动换行，设置合适的换行长度
        description_text = field_info.get('description', '')
        desc_label = ttk.Label(self, text=description_text, wraplength=300, justify='left')
        desc_label.grid(row=row, column=5, sticky='nsew')
        ttk.Label(self, text=field_info.get('access', 'r')).grid(row=row, column=6, sticky='nsew')
        
        btn_read = ttk.Button(self, text=self.language_manager.get_text("read"), width=4, 
                             command=lambda fn=field_name: self.read_field(fn))
        btn_read.grid(row=row, column=7, sticky='nsew')
        
        # 根据访问权限决定是否显示写值输入框
        if field_info.get('access', 'r') == 'rw':
            # 有写入权限，显示输入框
            entry_write = ttk.Entry(self, textvariable=write_var, width=8)
            entry_write.grid(row=row, column=8, sticky='nsew')
            
            # 显示写按钮
            btn_write = ttk.Button(self, text=self.language_manager.get_text("write"), width=4, 
                                 command=lambda fn=field_name: self.write_field(fn))
            btn_write.grid(row=row, column=9, sticky='nsew')
        else:
            # 只读字段，隐藏输入框和写按钮
            ttk.Label(self, text='').grid(row=row, column=8, sticky='nsew')  # 空的写值列
            ttk.Label(self, text='').grid(row=row, column=9, sticky='nsew')  # 空的写按钮列
        
        ttk.Label(self, textvariable=write_status_var).grid(row=row, column=10, sticky='nsew')
        self.entries[field_name] = (value_var, update_time_var, write_var, write_status_var)
        
        return row + 1

    def create_bitfield_subitems(self, field_name, field_info, current_row):
        """为bitfield32字段创建子项显示每一位的状态"""
        symbols = field_info.get('symbols', [])
        if not symbols:
            return current_row
        
        # 初始化bitfield条目存储
        if field_name not in self.bitfield_entries:
            self.bitfield_entries[field_name] = {}
        
        # 为每个symbol创建子行
        for symbol in symbols:
            bit_name = symbol.get('name', f'Bit_{symbol.get("value", 0)}')
            bit_position = symbol.get('value', 0)
            
            # 位名称（缩进显示）
            bit_label = ttk.Label(self, text=f"  └ {bit_name} (Bit {bit_position})")
            bit_label.grid(row=current_row, column=0, sticky='nsew', padx=(20, 0))
            
            # 位状态值
            bit_value_var = tk.StringVar(value="0")
            bit_value_label = ttk.Label(self, textvariable=bit_value_var)
            bit_value_label.grid(row=current_row, column=1, sticky='nsew')
            
            # 其他列
            ttk.Label(self, text='').grid(row=current_row, column=2, sticky='nsew')  # 更新时间
            ttk.Label(self, text='').grid(row=current_row, column=3, sticky='nsew')  # 单位
            ttk.Label(self, text='bit').grid(row=current_row, column=4, sticky='nsew')  # 类型
            ttk.Label(self, text='').grid(row=current_row, column=5, sticky='nsew')  # 描述
            ttk.Label(self, text='r').grid(row=current_row, column=6, sticky='nsew')  # 访问权限
            ttk.Label(self, text='').grid(row=current_row, column=7, sticky='nsew')  # 读按钮
            ttk.Label(self, text='').grid(row=current_row, column=8, sticky='nsew')  # 写值
            ttk.Label(self, text='').grid(row=current_row, column=9, sticky='nsew')  # 写按钮
            ttk.Label(self, text='').grid(row=current_row, column=10, sticky='nsew')  # 写状态
            
            # 保存位状态变量以便更新
            self.bitfield_entries[field_name][bit_name] = bit_value_var
            
            current_row += 1
        
        return current_row

    def get_field_symbols(self, field_name):
        """获取字段的symbols定义"""
        field_info = self.fields.get(field_name, {})
        return field_info.get('symbols', [])

    def get_symbols_from_model(self, field_name):
        """从原始模型定义中获取symbols，用于动态group字段"""
        if '_' not in field_name or field_name.count('_') < 2:
            return []
        
        parts = field_name.split('_')
        if len(parts) < 3:
            return []
        
        group_name = parts[0]
        try:
            group_index = int(parts[1])
            original_field_name = '_'.join(parts[2:])
        except ValueError:
            return []
        
        # 从协议中获取原始模型数据
        if self.table_id not in self.protocol.models:
            return []
        
        model_data = self.protocol.models[self.table_id]
        groups = model_data['group'].get('groups', [])
        
        # 查找对应的group定义
        for group in groups:
            if group['name'] == group_name:
                group_points = group['points']
                for gp in group_points:
                    if gp['name'] == original_field_name and gp.get('type', '').lower() == 'bitfield32':
                        return gp.get('symbols', [])
        
        return []

    def update_bitfield_display(self, field_name, field_data):
        """更新bitfield32字段的位状态显示"""
        if field_name not in self.bitfield_entries:
            return
        
        # 获取原始值
        raw_value = field_data.get('raw', 0)
        if raw_value is None:
            raw_value = 0
        
        # 如果raw_value是字符串（十六进制），需要转换为整数
        if isinstance(raw_value, str):
            try:
                if raw_value.startswith('0x') or raw_value.startswith('0X'):
                    raw_value = int(raw_value, 16)
                else:
                    raw_value = int(raw_value, 16)
            except (ValueError, TypeError):
                raw_value = 0
        
        # 获取symbols定义
        field_info = self.fields.get(field_name, {})
        symbols = field_info.get('symbols', [])
        
        if not symbols:
            return
        
        # 解析每一位的状态
        bit_status = self.protocol.parse_bitfield32_bits(raw_value, symbols)
        
        # 更新每个位的显示
        for bit_name, bit_info in bit_status.items():
            if bit_name in self.bitfield_entries[field_name]:
                bit_var = self.bitfield_entries[field_name][bit_name]
                bit_var.set(str(bit_info['status']))

    def read_field(self, field_name):
        # 检查是否已连接
        if not self.modbus_client.is_connected():
            self.main_window.notify("warning", self.language_manager.get_text("warning"), 
                                    self.language_manager.get_text("please_connect_first"))
            return
        
        # 检查模型是否扫描
        if self.main_window and not getattr(self.main_window, 'is_scan_model_addr', False):
            self.main_window.notify("warning", self.language_manager.get_text("warning"), 
                                    self.language_manager.get_text("please_scan_model_addr_first"))
            return
        
        # 通过通信线程读取单个字段
        def on_read_complete(result, error=None):
            # 简化回调函数，只处理错误情况
            # UI更新现在由解析线程通过schedule_on_ui处理
            if error:
                self.entries[field_name][0].set("Err")
                self.entries[field_name][1].set("-")
                return
            
            # 如果读取失败，显示错误
            if not result or not result.get("success"):
                if not result.get("queued"):  # 只有在非队列情况下才显示错误
                    self.entries[field_name][0].set("Err")
                    self.entries[field_name][1].set("-")
        
        self.main_window._execute_operation("read_single_field", (self.table_id, field_name), on_read_complete)

    def write_field(self, field_name):
        # 检查是否已连接
        if not self.modbus_client.is_connected():
            messagebox.showwarning(self.language_manager.get_text("warning"), 
                                 self.language_manager.get_text("please_connect_first"))
            return
        
        # 检查模型是否扫描
        if self.main_window and not getattr(self.main_window, 'is_scan_model_addr', False):
            messagebox.showwarning(self.language_manager.get_text("warning"), 
                                self.language_manager.get_text("please_scan_model_addr_first"))
            return
        
        value_str = self.entries[field_name][2].get()
        if not value_str.strip():
            self.entries[field_name][3].set(self.language_manager.get_text("format_error"))
            return
        
        # 获取字段信息以确定数据类型
        field_info = self.fields.get(field_name, {})
        field_type = str(field_info.get('type', 'uint16')).lower()
        field_size = field_info.get('size', 1)
        
        try:
            # 根据字段类型处理输入值
            if 'array' in field_type:
                # 数组类型：使用逗号分隔，严格要求元素个数等于size
                parts = [p.strip() for p in value_str.split(',')]
                if len(parts) != field_size:
                    self.entries[field_name][3].set(f"array length error: need {field_size} elements")
                    return
                values = []
                for p in parts:
                    if not p:
                        self.entries[field_name][3].set("format error")
                        return
                    if p.lower().startswith('0x'):
                        v = int(p, 16)
                    else:
                        v = int(p)
                    # 根据数组类型检查范围
                    if 'uint32' in field_type:
                        # uint32 array：每个元素是uint32
                        if v < 0 or v > 0xFFFFFFFF:
                            self.entries[field_name][3].set("out of uint32 range")
                            return
                    elif 'int32' in field_type:
                        # int32 array：每个元素是int32
                        if v < -0x80000000 or v > 0x7FFFFFFF:
                            self.entries[field_name][3].set("out of int32 range")
                            return
                    elif 'uint16' in field_type:
                        # uint16 array：每个元素是uint16
                        if v < 0 or v > 0xFFFF:
                            self.entries[field_name][3].set("out of uint16 range")
                            return
                    elif 'int16' in field_type:
                        # int16 array：每个元素是int16
                        if v < -32768 or v > 32767:
                            self.entries[field_name][3].set("out of int16 range")
                            return
                    values.append(v)
                value = values
            elif field_type == 'string':
                # 字符串类型：直接使用输入的字符串
                value = value_str
                # 检查字符串长度是否超过字段容量
                max_chars = field_size * 2  # 每个寄存器2个字符
                if len(value) > max_chars:
                    self.entries[field_name][3].set(f"string too long(max {max_chars} characters)")
                    return
            elif field_type in ['uint32', 'int32', 'bitfield32']:
                # 32位类型：支持十进制和十六进制输入
                if value_str.lower().startswith('0x'):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
                # 检查32位范围
                if field_type == 'uint32' or field_type == 'bitfield32':
                    if value < 0 or value > 0xFFFFFFFF:
                        self.entries[field_name][3].set("out of uint32 range")
                        return
                elif field_type == 'int32':
                    if value < -0x80000000 or value > 0x7FFFFFFF:
                        self.entries[field_name][3].set("out of int32 range")
                        return
            elif field_type in ['uint16', 'int16', 'enum16']:
                # 16位类型：支持十进制和十六进制输入
                if value_str.lower().startswith('0x'):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
                if field_type == 'uint16' or field_type == 'enum16':
                    if value < 0 or value > 0xFFFF:
                        self.entries[field_name][3].set("out of uint16 range")
                        return
                elif field_type == 'int16':
                    if value < -32768 or value > 32767:
                        self.entries[field_name][3].set("out of int16 range")
                        return
            elif field_type in ['uint8', 'int8']:
                # 8位类型：支持十进制和十六进制输入
                if value_str.lower().startswith('0x'):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
                if field_type == 'uint8':
                    if value < 0 or value > 255:
                        self.entries[field_name][3].set("out of uint8 range")
                        return
                elif field_type == 'int8':
                    if value < -128 or value > 127:
                        self.entries[field_name][3].set("out of int8 range")
                        return
            else:
                # 其他类型，尝试转换为整数
                if value_str.lower().startswith('0x'):
                    value = int(value_str, 16)
                else:
                    value = int(value_str)
        except ValueError as ve:
            self.entries[field_name][3].set("format error")
            return
        except Exception as e:
            self.entries[field_name][3].set(f"input error: {str(e)}")
            return
        
        # 通过通信线程写入字段
        def on_write_complete(result, error=None):
            if error:
                self.entries[field_name][3].set(f"failed: {error}")
                return
            
            if result and result.get("success"):
                self.entries[field_name][3].set("success")
                # 写入成功后，清空输入框
                self.entries[field_name][2].set("")
            else:
                error_msg = result.get("error", "unknown") if result else "unknown"
                self.entries[field_name][3].set(f"failed: {error_msg}")
        
        self.main_window._execute_operation("write_field", (self.table_id, field_name, value), on_write_complete)

    def display_data(self, data, timestamp=None):
        # 如果主窗口UI不活跃，缓存数据而不更新UI
        if (hasattr(self.main_window, '_ui_active') and 
            not getattr(self.main_window, '_ui_active', True)):
            return
            
        # 使用传入的时间戳，如果没有则使用当前时间
        if timestamp:
            import datetime
            now = datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        else:
            now = datetime.datetime.now().strftime("%H:%M:%S")
        
        # 强制在主线程中更新UI
        def update_ui():
            updated_count = 0
            for field_name, v in data.items():
                if field_name in self.entries:
                    try:
                        # 根据字段类型格式化显示值（支持数组）
                        field_info = self.fields.get(field_name, {})
                        ftype = str(field_info.get('type', '')).lower()
                        val = v.get('value')
                        if isinstance(val, list) or ('array' in ftype and isinstance(val, (list, tuple))):
                            # 将数组格式化为逗号分隔字符串
                            try:
                                value_str = ', '.join(str(int(x)) for x in val)
                            except Exception:
                                value_str = ', '.join(str(x) for x in val)
                        else:
                            value_str = str(val)
                        self.entries[field_name][0].set(value_str)
                        self.entries[field_name][1].set(str(now))
                        updated_count += 1
                        
                        # 如果是bitfield32字段且有子项，更新位状态
                        if field_name in self.bitfield_entries:
                            self.update_bitfield_display(field_name, v)
                    except Exception as e:
                        pass
            
            # 强制刷新界面
            if hasattr(self, 'tree') and self.tree:
                self.tree.update_idletasks()
        
        # 确保在主线程中执行UI更新
        try:
            if hasattr(self, 'tree') and self.tree:
                self.tree.after_idle(update_ui)
            else:
                update_ui()
        except:
            update_ui()



    def clear_data(self):
        for field_name, (value_var, update_time_var, _, write_status_var) in self.entries.items():
            value_var.set('-')
            update_time_var.set('-')
            write_status_var.set('')

    def update_language(self, language_manager):
        """更新语言"""
        self.language_manager = language_manager
        
        # 更新表头
        new_headers = [
            self.language_manager.get_text("field_name"),
            self.language_manager.get_text("value"),
            self.language_manager.get_text("update_time"),
            self.language_manager.get_text("unit"),
            self.language_manager.get_text("type"),
            self.language_manager.get_text("description"),
            self.language_manager.get_text("access_rights"),
            self.language_manager.get_text("read"),
            self.language_manager.get_text("write_value"),
            self.language_manager.get_text("write"),
            self.language_manager.get_text("write_status")
        ]
        
        for i, header_label in enumerate(self.headers):
            if i < len(new_headers):
                header_label.configure(text=new_headers[i])
        
        # 更新刷新间隔标签
        if hasattr(self, 'refresh_interval_label'):
            self.refresh_interval_label.configure(text=self.language_manager.get_text("refresh_interval_seconds"))
        
        # 更新按钮文本
        for row in range(1, len(self.fields) + 1):
            # 更新读按钮
            read_btn = self.grid_slaves(row=row, column=7)[0]
            if isinstance(read_btn, ttk.Button):
                read_btn.configure(text=self.language_manager.get_text("read"))
            
            # 更新写按钮
            write_btn = self.grid_slaves(row=row, column=9)[0]
            if isinstance(write_btn, ttk.Button):
                write_btn.configure(text=self.language_manager.get_text("write"))

class ConnectionFrame(ttk.LabelFrame):
    """连接设置框架"""
    def __init__(self, parent, language_manager=None, **kwargs):
        # 获取语言管理器
        if language_manager is None:
            from language_manager import LanguageManager
            language_manager = LanguageManager()
        
        # 使用语言管理器获取文本
        frame_text = language_manager.get_text("connection_settings")
        super().__init__(parent, text=frame_text, padding=10, **kwargs)
        
        self.language_manager = language_manager
        self.setup_connection_controls()

    def setup_connection_controls(self):
        # 只保留RTU连接设置
        rtu_frame = ttk.Frame(self)
        rtu_frame.pack(fill=tk.X)
        
        # 第一行：COM口和波特率
        self.rtu_connection_label = ttk.Label(rtu_frame, text=self.language_manager.get_text("rtu_connection"))
        self.rtu_connection_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        
        # 自动识别COM口
        self.rtu_port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(rtu_frame, textvariable=self.rtu_port_var, width=12)
        self.port_combo.grid(row=0, column=1, padx=(0, 5))
        
        # 刷新COM口按钮
        self.refresh_btn = ttk.Button(rtu_frame, text=self.language_manager.get_text("refresh"), 
                                     command=self.refresh_ports, width=6)
        self.refresh_btn.grid(row=0, column=2, padx=(0, 5))
        
        self.baud_rate_label = ttk.Label(rtu_frame, text=self.language_manager.get_text("baud_rate"))
        self.baud_rate_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 5))
        self.baudrate_var = tk.StringVar(value="115200")
        self.baud_combo = ttk.Combobox(rtu_frame, textvariable=self.baudrate_var, 
                     values=["9600", "19200", "38400", "57600", "115200"], 
                     width=8)
        self.baud_combo.grid(row=0, column=4, padx=(0, 10))
        self.baud_rate_label.grid_remove()
        self.baud_combo.grid_remove()
        
        # 第二行：从站ID和其他设置
        self.slave_id_label = ttk.Label(rtu_frame, text=self.language_manager.get_text("slave_id"))
        self.slave_id_label.grid(row=1, column=0, sticky=tk.W, padx=(0, 5))
        self.slave_id_var = tk.StringVar(value="1")
        self.slave_id_spinbox = ttk.Spinbox(rtu_frame, textvariable=self.slave_id_var, 
                                       from_=1, to=247, width=8)
        self.slave_id_spinbox.grid(row=1, column=1, padx=(0, 5))
        
        self.timeout_label = ttk.Label(rtu_frame, text=self.language_manager.get_text("timeout_seconds"))
        self.timeout_label.grid(row=1, column=2, sticky=tk.W, padx=(0, 5))
        self.timeout_var = tk.StringVar(value="3")
        self.timeout_spinbox = ttk.Spinbox(rtu_frame, textvariable=self.timeout_var, 
                                     from_=1, to=60, width=8)
        self.timeout_spinbox.grid(row=1, column=3, padx=(0, 10))
        self.timeout_label.grid_remove()
        self.timeout_spinbox.grid_remove()
        
        # 连接按钮
        self.connect_rtu_btn = ttk.Button(rtu_frame, text=self.language_manager.get_text("connect_rtu"))
        self.connect_rtu_btn.grid(row=1, column=4, padx=(0, 5))
        
        self.disconnect_btn = ttk.Button(rtu_frame, text=self.language_manager.get_text("disconnect"))
        self.disconnect_btn.grid(row=1, column=5)
        
        # 初始化COM口列表
        self.refresh_ports()

    def update_buttons_state(self, is_connected):
        """更新按钮状态"""
        if is_connected:
            # 已连接：禁用连接按钮，启用断开按钮
            self.connect_rtu_btn.configure(state="disabled")
            self.disconnect_btn.configure(state="normal")
        else:
            # 未连接：启用连接按钮，禁用断开按钮
            self.connect_rtu_btn.configure(state="normal")
            self.disconnect_btn.configure(state="disabled")

    def update_language(self, language_manager):
        """更新语言"""
        self.language_manager = language_manager
        
        # 更新框架标题
        self.configure(text=self.language_manager.get_text("connection_settings"))
        
        # 更新标签文本
        self.rtu_connection_label.configure(text=self.language_manager.get_text("rtu_connection"))
        self.refresh_btn.configure(text=self.language_manager.get_text("refresh"))
        self.baud_rate_label.configure(text=self.language_manager.get_text("baud_rate"))
        self.slave_id_label.configure(text=self.language_manager.get_text("slave_id"))
        self.timeout_label.configure(text=self.language_manager.get_text("timeout_seconds"))
        
        # 更新按钮文本
        self.connect_rtu_btn.configure(text=self.language_manager.get_text("connect_rtu"))
        self.disconnect_btn.configure(text=self.language_manager.get_text("disconnect"))

    def refresh_ports(self):
        """刷新可用COM口列表"""
        try:
            # 获取系统所有可用串口
            ports = [port.device for port in serial.tools.list_ports.comports()]
            
            if ports:
                self.port_combo['values'] = ports
                # 如果有COM口，默认选择第一个
                if not self.rtu_port_var.get() or self.rtu_port_var.get() not in ports:
                    self.rtu_port_var.set(ports[0])
            else:
                self.port_combo['values'] = ['无可用串口']
                self.rtu_port_var.set('')
                
        except Exception as e:
            # 如果无法获取串口列表，提供默认选项
            default_ports = ['COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8']
            self.port_combo['values'] = default_ports
            if not self.rtu_port_var.get():
                self.rtu_port_var.set('COM1')
    
    def set_connection_controls_state(self, enabled):
        """设置连接配置控件的启用/禁用状态"""
        state = 'normal' if enabled else 'disabled'
        self.port_combo.config(state=state)
        self.baud_combo.config(state=state)
        self.slave_id_spinbox.config(state=state)
        self.timeout_spinbox.config(state=state)
        self.refresh_btn.config(state=state)