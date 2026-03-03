#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SunSpec协议解析模块 - 支持model_xxx.json格式
"""

import json
import os

class SunSpecProtocol:
    """SunSpec协议解析类"""

    def __init__(self, model_dir='.'):
        self.model_dir = model_dir
        self.models = {}
        self.base_address = 0  # 默认0，可被扫描覆盖
        self.model_base_addrs = {}  # 新增：保存扫描到的模型地址
        self.load_models()

    def load_models(self, available_models=None):
        """
        加载模型定义。
        available_models: 可用模型ID列表（如[ 1，802]），为None时加载全部支持的。
        """
        # 支持的模型及其文件名
        default_model_files = {
            1: 'model_1.json',
            802: 'model_802.json',
            805: 'model_805.json',
            64900: 'model_64900.json',
            64950: 'model_64950.json',
            64951: 'model_64951.json',
            64952: 'model_64952.json',
        }
        
        # 如果传入了扫描到的模型，动态构建文件映射
        if available_models is not None:
            model_files = {}
            for model_id in available_models:
                if model_id in default_model_files:
                    model_files[model_id] = default_model_files[model_id]
                else:
                    # 动态生成文件名
                    model_files[model_id] = f'model_{model_id}.json'
        else:
            model_files = default_model_files

        for table_id, filename in model_files.items():
            try:
                filepath = self.get_resource_path(filename)
                if not os.path.exists(filepath):
                    print(f"模型文件 {filename} 不存在，跳过。")
                    continue
                with open(filepath, 'r', encoding='utf-8') as f:
                    model_data = json.load(f)
                    self.models[table_id] = model_data
            except Exception as e:
                print(f"加载模型文件 {filename} 失败: {e}")

    def get_resource_path(self, filename):
        """获取资源文件路径，支持打包后的路径"""
        import sys
        import os
        
        if getattr(sys, 'frozen', False):
            # 如果是打包后的exe
            base_path = sys._MEIPASS
            return os.path.join(base_path, filename)
        else:
            # 如果是开发环境：使用模块目录
            module_dir = os.path.dirname(__file__)
            return os.path.join(module_dir, filename)

    def parse_table_data(self, table_id, data):
        """解析表格数据，支持model_xxx.json格式"""
        if table_id not in self.models:
            return None
            
        model_data = self.models[table_id]
        points = model_data['group']['points']
        groups = model_data['group'].get('groups', [])
        parsed_data = {}

        # 解析固定points部分
        current_offset = 0
        for point in points:
            name = point['name']
            field_type = point['type'].lower()
            size = point.get('size', 1)
            offset = point.get('offset', current_offset)
            raw_value = None
            value = None

            # 取出对应寄存器
            if offset + size <= len(data):
                regs = data[offset:offset+size]
                # 调试输出
                # if field_type == 'string' and size <= 8:
                #     print(f"DEBUG {name}: offset={offset}, size={size}, data_len={len(data)}")
                #     print(f"DEBUG {name}: regs={[hex(r) for r in regs]}")
                
                # 使用统一的数据类型解析器
                symbols = point.get('symbols', []) if field_type == 'enum16' else None
                value, raw_value = self._parse_data_by_type(regs, field_type, size, symbols)
            else:
                # print(f"DEBUG {name}: 数据长度不足 - offset={offset}, size={size}, data_len={len(data)}")
                value = None
                raw_value = None

            # 移除缩放因子处理，统一显示原始值
            parsed_data[name] = {
                'value': value,
                'raw': raw_value,
                'unit': point.get('units', ''),
                'type': field_type,
                'label': point.get('label', name),
                'description': point.get('desc', ''),
                'access': 'rw' if 'access' in point and point['access'] == 'RW' else 'r',
                'symbols': point.get('symbols', []) if field_type == 'bitfield32' else []
            }
            
            current_offset = offset + size

        # 解析子groups部分（动态重复）
        if groups:
            # 计算固定points部分的长度
            # 找到最大的offset+size作为固定部分的结束位置
            fixed_points_length = 0
            for point in points:
                if 'offset' in point:
                    point_end = point['offset'] + point.get('size', 1)
                    fixed_points_length = max(fixed_points_length, point_end)
                else:
                    # 如果没有offset，按顺序累加（这种情况在805模型中不会出现，因为都有offset）
                    fixed_points_length += point.get('size', 1)
            
            # 使用预计算的重复组信息
            for group in groups:
                group_name = group['name']
                group_points = group['points']
                
                # 使用预计算的值
                single_group_length = group.get('single_group_length', 0)
                repeat_count = group.get('repeat_count', 0)
                
                if repeat_count > 0:
                    
                    # 解析重复的groups
                    for i in range(repeat_count):
                        group_data = {}
                        group_offset = fixed_points_length + (i * single_group_length)
                        
                        # 解析group中的每个point
                        current_group_offset = 0
                        for gp in group_points:
                            gp_name = gp['name']
                            gp_type = gp['type'].lower()
                            gp_size = gp.get('size', 1)
                            
                            # 计算在data中的实际偏移
                            data_offset = group_offset + current_group_offset
                            
                            if data_offset + gp_size <= len(data):
                                regs = data[data_offset:data_offset + gp_size]
                                
                                # 使用统一的数据类型解析器
                                symbols = gp.get('symbols', []) if gp_type == 'enum16' else None
                                value, raw_value = self._parse_data_by_type(regs, gp_type, gp_size, symbols)
                            else:
                                value = None
                                raw_value = None
                            
                            # 添加到group数据中，使用索引区分重复的groups
                            field_name = f"{group_name}_{i+1}_{gp_name}"
                            group_data[field_name] = {
                                'value': value,
                                'raw': raw_value,
                                'unit': gp.get('units', ''),
                                'type': gp_type,
                                'label': f"{gp.get('label', gp_name)} (Group {i+1})",
                                'description': gp.get('desc', ''),
                                'access': 'rw' if 'access' in gp and gp['access'] == 'RW' else 'r',
                                'group_index': i + 1,
                                'group_name': group_name,
                                'symbols': gp.get('symbols', []) if gp_type == 'bitfield32' else []
                            }
                            
                            current_group_offset += gp_size
                        
                        # 将group数据合并到主数据中
                        parsed_data.update(group_data)

        return parsed_data

    def parse_single_field(self, table_id, field_name, data):
        """解析单个字段，根据type和size解析"""
        #print(f"DEBUG: parse_single_field called with table_id={table_id}, field_name={field_name}, data={data}")
        
        if table_id not in self.models:
            #print(f"DEBUG: table_id {table_id} not found in models")
            return None
            
        model_data = self.models[table_id]
        points = model_data['group']['points']
        
        # 首先检查是否是动态group字段
        if '_' in field_name and field_name.count('_') >= 2:
            #print(f"DEBUG: Checking dynamic group field: {field_name}")
            # 动态group字段格式：GroupName_index_fieldName
            parts = field_name.split('_')
            if len(parts) >= 3:
                group_name = parts[0]
                try:
                    group_index = int(parts[1])
                    original_field_name = '_'.join(parts[2:])  # 处理field_name中包含下划线的情况
                    #print(f"DEBUG: Parsed group: {group_name}, index: {group_index}, field: {original_field_name}")
                    
                    # 在groups中查找对应的group定义
                    groups = model_data['group'].get('groups', [])
                    #print(f"DEBUG: Available groups: {[g.get('name', 'unnamed') for g in groups]}")
                    
                    for group in groups:
                        if group['name'] == group_name:
                            #print(f"DEBUG: Found matching group: {group_name}")
                            group_points = group['points']
                            for gp in group_points:
                                if gp['name'] == original_field_name:
                                    #print(f"DEBUG: Found matching field: {original_field_name}")
                                    field_type = gp['type'].lower()
                                    size = gp.get('size', 1)
                                    
                                    # 检查数据长度是否足够
                                    if len(data) < size:
                                        #print(f"DEBUG: Data length {len(data)} insufficient for size {size}")
                                        return None
                                    
                                    # 解析数据（复用下面的解析逻辑）
                                    result = self._parse_field_data(data, field_type, size, gp, original_field_name)
                                    #print(f"DEBUG: Parse result: {result}")
                                    return result
                            #print(f"DEBUG: Field {original_field_name} not found in group {group_name}")
                    #print(f"DEBUG: Group {group_name} not found")
                except ValueError:
                    #print(f"DEBUG: ValueError parsing group index from {parts[1]}")
                    pass  # 如果无法解析索引，继续尝试普通字段解析
        
        # 普通字段解析
        #print(f"DEBUG: Trying normal field parsing for {field_name}")
        for point in points:
            if point['name'] == field_name:
                #print(f"DEBUG: Found normal field: {field_name}")
                field_type = point['type'].lower()
                size = point.get('size', 1)
                
                # 检查数据长度是否足够
                if len(data) < size:
                    ##print(f"DEBUG: Data length {len(data)} insufficient for size {size}")
                    return None
                
                # 解析数据
                result = self._parse_field_data(data, field_type, size, point, field_name)
                ##print(f"DEBUG: Parse result: {result}")
                return result
        
        ##print(f"DEBUG: Field {field_name} not found anywhere")
        return None

    def _parse_field_data(self, data, field_type, size, point, field_name):
        """解析字段数据的通用方法"""
        # 使用统一的数据类型解析器
        symbols = point.get('symbols', []) if field_type == 'enum16' else None
        value, raw_value = self._parse_data_by_type(data, field_type, size, symbols)
        
        if value is None:
            return None
        
        # 移除缩放因子处理，统一显示原始值
        return {
            'value': value,
            'raw': raw_value,
            'unit': point.get('units', ''),
            'type': field_type,
            'label': point.get('label', field_name),
            'description': point.get('desc', ''),
            'access': 'rw' if 'access' in point and point['access'] == 'RW' else 'r',
            'symbols': point.get('symbols', []) if field_type == 'bitfield32' else []
        }

    def _parse_data_by_type(self, data, field_type, size, symbols=None):
        """
        统一的数据类型解析方法
        返回 (value, raw_value) 元组，解析失败时返回 (None, None)
        symbols: 用于enum16类型的symbols定义
        """
        if not data or len(data) == 0:
            return None, None
            
        field_type = field_type.lower()
        
        if field_type in ['uint16', 'sunssf']:
            raw_value = data[0]
            if field_type == 'sunssf':
                # sunssf是有符号的
                if raw_value > 32767:
                    raw_value = raw_value - 65536
            return raw_value, raw_value
            
        elif field_type == 'int16':
            raw_value = data[0]
            if raw_value > 32767:
                raw_value = raw_value - 65536
            # 如果有symbols定义，尝试找到对应的名称
            if symbols:
                for symbol in symbols:
                    if symbol.get('value') == raw_value:
                        return symbol.get('name', str(raw_value)), raw_value
            
            # 如果没有找到对应的symbol，返回原始值
            return raw_value, raw_value    
            
        elif field_type == 'uint32':
            if size >= 2 and len(data) >= 2:
                raw_value = (data[0] << 16) | data[1]
                return raw_value, raw_value
            else:
                return None, None
                
        elif field_type == 'int32':
            if size >= 2 and len(data) >= 2:
                raw_value = (data[0] << 16) | data[1]
                if raw_value > 0x7FFFFFFF:
                    raw_value = raw_value - 0x100000000
                return raw_value, raw_value
            else:
                return None, None
                
        elif field_type == 'enum16':
            # enum16 使用1个寄存器，按uint16解析
            raw_value = data[0]
            
            # 如果有symbols定义，尝试找到对应的名称
            if symbols:
                for symbol in symbols:
                    if symbol.get('value') == raw_value:
                        return symbol.get('name', str(raw_value)), raw_value
            
            # 如果没有找到对应的symbol，返回原始值
            return raw_value, raw_value
            
        elif field_type == 'bitfield32':
            # bitfield32 使用2个寄存器，按uint32解析，显示为十六进制
            if size >= 2 and len(data) >= 2:
                raw_value = (data[0] << 16) | data[1]
                value = f"{raw_value:08X}"  # 32位十六进制格式
                return value, raw_value
            else:
                return None, None
                
        elif field_type == 'string':
            # 字符串解析：每个寄存器存储一个字符
            chars = []
            for reg in data:
                high_byte = (reg >> 8) & 0xFF
                low_byte = reg & 0xFF
                chars.append(chr(high_byte))  # 高字节在前
                chars.append(chr(low_byte))   # 低字节在后
            value = ''.join(chars).rstrip('\x00').strip()
            return value, value
            
        elif field_type == "hex":
            # hex类型：直接显示16进制数据
            hex_values = []
            for reg in data:
                hex_values.append(f"{reg:04X}")
            value = ' '.join(hex_values)  # 用空格分隔多个寄存器
            return value, value
            
        elif field_type == "int16 array":
            # int16 array类型：解析为int16数组
            # size表示数组中uint16的个数
            if len(data) < size:
                return None, None
            
            # 提取前size个int16值
            array_values = []
            for i in range(size):
                if i < len(data):
                    array_values.append(data[i] if data[i] < 32767 else data[i] - 65536)
            
            # 返回数组值，格式为列表
            return array_values, array_values
        elif field_type == "uint32 array":
            # uint32 array类型：解析为uint32数组，size是寄存器个数
            # 每个uint32由2个寄存器组成
            if size >= 2 and len(data) >= size:
                array_values = []
                # size是寄存器总数，每2个寄存器组成1个uint32
                num_uint32 = size // 2
                for i in range(num_uint32):
                    high = data[i * 2]
                    low = data[i * 2 + 1]
                    uint32_value = (high << 16) | low
                    array_values.append(uint32_value)
                return array_values, array_values
            else:
                return None, None
        else:
            # 其他类型直接显示原始
            raw_value = data[0]
            return raw_value, raw_value
    def set_model_base_address(self, model_id, address):
        """设置特定模型的基地址"""
        self.model_base_addrs[model_id] = address

    def get_table_info(self, table_id, scanned_length=None):
        """
        获取表格信息，转换为兼容格式。
        如果提供了scanned_length，则预先计算重复组信息。
        """
        if table_id not in self.models:
            return None

        model_data = self.models[table_id]
        points = model_data['group']['points']
        groups = model_data['group'].get('groups', [])
        fields = {}
        current_offset = 0
        fixed_points_length = 0

        # 计算固定points部分的长度
        for point in points:
            if 'offset' in point:
                offset = point['offset']
                point_end = offset + point.get('size', 1)
                fixed_points_length = max(fixed_points_length, point_end)
            else:
                offset = current_offset
                current_offset += point.get('size', 1)
                fixed_points_length = max(fixed_points_length, current_offset)

            fields[point['name']] = {
                'offset': offset,
                'size': point.get('size', 1),
                'type': point['type'],
                'scale': point.get('sf', 1),
                'unit': point.get('units', ''),
                'access': 'rw' if 'access' in point and point['access'] == 'RW' else 'r',
                'label': point.get('label', point['name']),
                'description': point.get('desc', ''),
                'symbols': point.get('symbols', []) if point['type'].lower() in ['bitfield32', 'enum16'] else []
            }

        # 如果提供了scanned_length，则计算并存储重复组信息
        if scanned_length is not None and groups:
            # scanned_length 是L，不包含ID和L本身，所以要+2
            remaining_length = (scanned_length + 2) - fixed_points_length
            for group in groups:
                group_points = group['points']
                single_group_length = sum(gp.get('size', 1) for gp in group_points)
                group['single_group_length'] = single_group_length

                if single_group_length > 0 and remaining_length > 0:
                    repeat_count = remaining_length // single_group_length
                    group['repeat_count'] = repeat_count
                else:
                    group['repeat_count'] = 0

        base_addr = self.model_base_addrs.get(table_id, self.base_address)

        return {
            'name': model_data['group'].get('label', f'Model {table_id}'),
            'description': model_data['group'].get('label', f'Model {table_id}'),
            'base_address': base_addr,
            'length': fixed_points_length,
            'fields': fields,
            'has_groups': len(groups) > 0,
            'groups_info': groups
        }

    def get_available_tables(self):
        """获取可用的表格列表"""
        return list(self.models.keys())
    
    def parse_bitfield32_bits(self, raw_value, symbols):
        """
        解析bitfield32的每一位状态
        返回每一位的名称和状态字典
        """
        if raw_value is None:
            return {}
        
        bit_status = {}
        
        # 首先处理已定义的symbols
        if symbols:
            for symbol in symbols:
                bit_position = symbol.get('value', 0)
                bit_name = symbol.get('name', f'Bit_{bit_position}')
                
                # 检查该位是否被设置（为1）
                bit_value = (raw_value >> bit_position) & 1
                bit_status[bit_name] = {
                    'position': bit_position,
                    'value': bit_value,
                    'status': '1' if bit_value else '0'
                }
        
        # 然后检查所有32位，为未定义的位也添加显示
        for bit_pos in range(32):
            bit_value = (raw_value >> bit_pos) & 1
            if bit_value:  # 只显示设置为1的位
                # 检查是否已经定义了这个位
                already_defined = False
                if symbols:
                    for symbol in symbols:
                        if symbol.get('value', 0) == bit_pos:
                            already_defined = True
                            break
                
                if not already_defined:
                    bit_name = f'Bit_{bit_pos}'
                    bit_status[bit_name] = {
                        'position': bit_pos,
                        'value': bit_value,
                        'status': '1'
                    }
        
        return bit_status 