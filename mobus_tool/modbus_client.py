#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Modbus客户端模块
"""
import threading
import serial
import time

class ModbusClient:
    def __init__(self):
        self.ser = None
        self.connected = False
        self.slave_id = 1
        self.timeout = 1  # 秒
        self.log_callback = None
        self.log_filter = None

    def set_log_filter(self, filter=False):
        self.log_filter = filter
    def set_log_callback(self, callback):
        self.log_callback = callback

    def connect_rtu(self, port, baudrate=9600, timeout=1):
        try:
            # 将串口打开 + 初次访问包装在独立线程中，设定上限时间         
            self.ser = None
            self.connected = False
            connection_error = None
            connection_done = False
            
            def open_and_test_serial():
                """在独立线程中执行串口打开和初次访问测试"""
                nonlocal connection_error, connection_done
                try:              
                    # 步骤1：打开串口
                    self.ser = serial.Serial(port=port, baudrate=baudrate, bytesize=8, parity='N', stopbits=1, timeout=timeout)
                    self.connected = self.ser.is_open
                    
                    if not self.connected:
                        return                          
                    # 步骤2：初次访问测试（这是关键！）
                    # 尝试读取串口状态
                    try:
                        in_waiting = self.ser.in_waiting
                    except Exception as e:
                        # 状态读取失败，可能是虚假串口
                        self.connected = False
                        return        
                    # 尝试发送一个测试字节
                    try:
                        test_byte = b'\x00'
                        bytes_written = self.ser.write(test_byte)
                        
                        if bytes_written == 0:
                            self.connected = False
                            return             
                    except Exception as e:
                        self.connected = False
                        return
                    
                    # 尝试读取响应（非阻塞）
                    try:
                        self.ser.timeout = 0.1  # 设置很短的超时
                        response = self.ser.read(1)
                        self.ser.timeout = timeout  # 恢复原始超时
                    except Exception as e:
                        # 读取失败不算错误，可能是没有响应
                        pass
                    
                except Exception as e:
                    connection_error = e
                    self.connected = False
                finally:
                    connection_done = True
            
            # 在独立线程中执行串口打开和初次访问
            thread = threading.Thread(target=open_and_test_serial)
            thread.daemon = True
            thread.start()
            
            # 等待完成，最多3秒（减少5秒到3秒，提高响应速度）
            thread.join(timeout=3.0)
            
            if not connection_done:
                # 超时，认为是虚假串口，强制停止连接尝试
                try:
                    if self.ser and self.ser.is_open:
                        self.ser.close()
                except:
                    pass
                self.connected = False
                return False
            
            if connection_error:
                self.connected = False
                return False
            
            if not self.connected:
                return False
            
            self.timeout = timeout
            return self.connected
            
        except Exception as e:
            self.connected = False
            return False

    def disconnect(self):
        """断开连接，立即停止所有通信操作"""
        if self.ser and self.ser.is_open:
            try:
                # 清理输入输出缓冲区
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                # 立即关闭串口
                self.ser.close()
            except Exception as e:
                if self.log_callback:
                    self.log_callback(f"Disconnect error: {e}")
        self.connected = False

    def is_connected(self):
        return self.connected and self.ser and self.ser.is_open

    def calculate_crc16(self, data: bytes):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc & 0xFFFF

    def send_and_recv(self, request: bytes, resp_len: int):
        if not self.is_connected():
            return None
        
        try:
            self.ser.reset_input_buffer()
            self.ser.write(request)
            if self.log_callback:
                if not self.log_filter:
                    self.log_callback("Send: " + " ".join(f"{b:02X}" for b in request))
            
            time.sleep(0.05)  # 给设备一点响应时间
            
            # 检查连接状态，如果已断开则立即返回
            if not self.is_connected():
                return None
            
            # 读取响应，如果超时会返回部分数据或空数据
            response = self.ser.read(resp_len)
            
            if self.log_callback:
                if len(response) == 0:
                    self.log_callback("Receive: No response (timeout)")
                elif len(response) < resp_len:
                    self.log_callback(f"Receive: Partial response ({len(response)}/{resp_len} bytes): " + 
                                    " ".join(f"{b:02X}" for b in response))
                else:
                    if not self.log_filter:
                        self.log_callback("Receive: " + " ".join(f"{b:02X}" for b in response))
            
            # 如果没有收到任何数据或数据不完整，返回None表示通信失败
            if len(response) == 0:
                if self.log_callback:
                    self.log_callback(f"Communication timeout (expected {resp_len} bytes, got 0)")
                return None
            elif len(response) < resp_len:
                if self.log_callback:
                    self.log_callback(f"Incomplete response (expected {resp_len} bytes, got {len(response)})")
                return None
                
            return response
            
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"Communication error: {e}")
            return None

    def parse_modbus_data(self, data_bytes, data_types=None):
        """
        根据数据类型解析Modbus数据
        data_bytes: 原始字节数据
        data_types: 数据类型列表，如 ['uint16', 'int16', 'uint32', 'string[4]']
        """
        if not data_types:
            # 默认按uint16处理
            return [data_bytes[i] << 8 | data_bytes[i+1] for i in range(0, len(data_bytes), 2)]
        
        result = []
        byte_index = 0
        
        for data_type in data_types:
            if byte_index >= len(data_bytes):
                break
                
            if data_type == 'uint16':
                if byte_index + 1 < len(data_bytes):
                    value = data_bytes[byte_index] << 8 | data_bytes[byte_index + 1]
                    result.append(value)
                    byte_index += 2
            elif data_type == 'int16':
                if byte_index + 1 < len(data_bytes):
                    value = data_bytes[byte_index] << 8 | data_bytes[byte_index + 1]
                    if value > 32767:
                        value = value - 65536
                    result.append(value)
                    byte_index += 2
            elif data_type == 'uint32':
                if byte_index + 3 < len(data_bytes):
                    value = (data_bytes[byte_index] << 24 | 
                            data_bytes[byte_index + 1] << 16 | 
                            data_bytes[byte_index + 2] << 8 | 
                            data_bytes[byte_index + 3])
                    result.append(value)
                    byte_index += 4
            elif data_type == 'int32':
                if byte_index + 3 < len(data_bytes):
                    value = (data_bytes[byte_index] << 24 | 
                            data_bytes[byte_index + 1] << 16 | 
                            data_bytes[byte_index + 2] << 8 | 
                            data_bytes[byte_index + 3])
                    if value > 0x7FFFFFFF:
                        value = value - 0x100000000
                    result.append(value)
                    byte_index += 4
            elif data_type.startswith('string['):
                # 修正字符串解析
                try:
                    str_len = int(data_type[7:-1])
                    if byte_index + str_len - 1 < len(data_bytes):
                        # 字符串解析：每个寄存器包含2个字符
                        chars = []
                        for i in range(0, str_len, 2):
                            if byte_index + i + 1 < len(data_bytes):
                                # 每个寄存器16位，包含2个8位字符
                                reg_val = data_bytes[byte_index + i] << 8 | data_bytes[byte_index + i + 1]
                                # 高字节在前，低字节在后
                                char1 = chr((reg_val >> 8) & 0xFF)
                                char2 = chr(reg_val & 0xFF)
                                chars.append(char1)
                                chars.append(char2)
                        
                        # 移除null字符和空格
                        result_str = ''.join(chars).rstrip('\x00').strip()
                        result.append(result_str)
                        byte_index += str_len
                    else:
                        result.append("")
                        byte_index += str_len
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"String parsing error: {e}")
                    result.append("")
                    byte_index += 2
            elif data_type == 'enum16':
                # enum16 按 uint16 处理
                if byte_index + 1 < len(data_bytes):
                    value = data_bytes[byte_index] << 8 | data_bytes[byte_index + 1]
                    result.append(value)
                    byte_index += 2
            elif data_type == 'bitfield32':
                # bitfield32 按 uint32 处理
                if byte_index + 3 < len(data_bytes):
                    value = (data_bytes[byte_index] << 24 | 
                            data_bytes[byte_index + 1] << 16 | 
                            data_bytes[byte_index + 2] << 8 | 
                            data_bytes[byte_index + 3])
                    result.append(value)
                    byte_index += 4
            else:
                # 未知类型，按uint16处理
                if byte_index + 1 < len(data_bytes):
                    value = data_bytes[byte_index] << 8 | data_bytes[byte_index + 1]
                    result.append(value)
                    byte_index += 2
        
        return result

    def read_holding_registers(self, address, count, data_types=None):
        # 组帧: [slave][0x03][addr_hi][addr_lo][cnt_hi][cnt_lo][crc_lo][crc_hi]
        slave = self.slave_id
        req = bytes([
            slave,
            0x03,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF
        ])
        crc = self.calculate_crc16(req)
        req += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
        # 响应长度: 1+1+1+count*2+2
        resp_len = 5 + count * 2
        resp = self.send_and_recv(req, resp_len)
        if not resp or len(resp) < resp_len:
            return None
        # 校验CRC
        crc_calc = self.calculate_crc16(resp[:-2])
        crc_recv = resp[-2] | (resp[-1] << 8)
        if crc_calc != crc_recv:
            if self.log_callback:
                self.log_callback("CRC check failed")   
            return None
        # 解析数据：# 检查是否为Modbus异常响应 (功能码 + 0x80)
        if resp[1] != 0x03:
            if resp[1] == 0x83:  # 读保持寄存器异常响应
                exception_code = resp[2]
                if self.log_callback:
                    exception_msg = {
                        1: "error function code",
                        2: "error data address", 
                        3: "error data value",
                        4: "error slave device fault"
                    }.get(exception_code, f"unknown exception code: {exception_code}")
                    self.log_callback(f"Modbus exception response: {exception_msg} (0x{exception_code:02X})")
                return "modbus_exception"  # 返回特殊标识表示收到异常响应
            return None
        reg_bytes = resp[3:-2]
        
        # 使用新的解析方法
        if data_types:
            return self.parse_modbus_data(reg_bytes, data_types)
        else:
            # 默认按uint16处理
            return [reg_bytes[i] << 8 | reg_bytes[i+1] for i in range(0, len(reg_bytes), 2)]

    def write_holding_register(self, address, value):
        slave = self.slave_id
        req = bytes([
            slave,
            0x06,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (value >> 8) & 0xFF,
            value & 0xFF
        ])
        crc = self.calculate_crc16(req)
        req += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
        resp_len = 8  # 固定长度
        resp = self.send_and_recv(req, resp_len)
        if not resp or len(resp) < resp_len:
            return False
        crc_calc = self.calculate_crc16(resp[:-2])
        crc_recv = resp[-2] | (resp[-1] << 8)
        if crc_calc != crc_recv:
            if self.log_callback:
                self.log_callback("CRC check failed")
            return False
        return resp[1] == 0x06

    def write_holding_registers(self, address, values):
        # 批量写入功能码0x10
        slave = self.slave_id
        count = len(values)
        byte_count = count * 2
        req = bytes([
            slave,
            0x10,
            (address >> 8) & 0xFF,
            address & 0xFF,
            (count >> 8) & 0xFF,
            count & 0xFF,
            byte_count
        ])
        for v in values:
            req += bytes([(v >> 8) & 0xFF, v & 0xFF])
        crc = self.calculate_crc16(req)
        req += bytes([crc & 0xFF, (crc >> 8) & 0xFF])
        resp_len = 8
        resp = self.send_and_recv(req, resp_len)
        if not resp or len(resp) < resp_len:
            return False
        crc_calc = self.calculate_crc16(resp[:-2])
        crc_recv = resp[-2] | (resp[-1] << 8)
        if crc_calc != crc_recv:
            if self.log_callback:
                self.log_callback("CRC check failed")
            return False
        return resp[1] == 0x10
