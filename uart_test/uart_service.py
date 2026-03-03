import time
import threading
import queue
from protocol import unpack_value_by_type,generate_read_command, generate_write_command, parse_response, generate_upgrade_packets, generate_upgrade_crc_command, calculate_crc16, generate_status_response, validate_value_for_type, to_signed
from protocol import (
    PU_FRAME_HEAD,MIN_PACKET_SIZE,UPGRADE_PACKET_SIZE,
    PU_FUN_READ, PU_FUN_WRITE, PU_FUN_UPGRADE, PU_FUN_UPGRADE_CRC,PU_FUN_CONFIG_UPDATE_DONE,
    PU_FUN_MCU_RESET, PU_FUN_CONNECT,
    PU_FUN_MCU_WRITE_ALARM, PU_FUN_MCU_WRITE_CONFIG, PU_FUN_MCU_WRITE_DATA,
    PU_ACK_WITH_DATA, PU_ACK_NO_DATA
    
)
from protocol import (
    PU_STATUS_OK,
    PU_STATUS_NO_FUNCODE,
    PU_STATUS_CRC_ERROR,
    PU_STATUS_ADDRESS_ERROR,
    PU_STATUS_NO_PERMISSION,
    PU_STATUS_DATA_ERROR,
    PU_STATUS_WRITE_FLASHDB_ERROR,
    PU_STATUS_RW_I2C_ERROR,
    PU_STATUS_DATA_LENGTH_ERROR,
    PU_STATUS_UPGRADE_PACKAGE_CRC_ERROR
)

ALLOWED_FUN_CODES = {
    PU_FUN_READ, PU_FUN_WRITE, PU_FUN_UPGRADE, PU_FUN_UPGRADE_CRC,
    PU_FUN_MCU_RESET, PU_FUN_CONNECT, PU_FUN_CONFIG_UPDATE_DONE,
    PU_FUN_MCU_WRITE_ALARM, PU_FUN_MCU_WRITE_CONFIG, PU_FUN_MCU_WRITE_DATA,
    PU_ACK_WITH_DATA, PU_ACK_NO_DATA

} 

import serial

class UARTService:
    def __init__(self, uart_interface, log_func=None, gui_update_callback=None, addr_map=None, f0_response_getter=None, response_40_50_getter=None):
        self.uart = uart_interface
        self.log_func = log_func or (lambda msg: None)
        self.gui_update_callback = gui_update_callback
        self.pending_requests = {}
        self.pending_lock = threading.Lock()
        
        # 串口监听线程相关
        self.listener_thread = None
        self.running = False
        
        # 四线程架构相关
        # 1. 监听线程：接收数据分包
        self.listener_thread = None
        
        # 2. 解析线程：解析数据，产生回复包
        self.parser_thread = None
        
        # 3. 发送线程：发送回复/握手
        self.sender_thread = None
        
        # 线程间通信队列
        self.packet_queue = queue.Queue(maxsize=100)  # 监听线程 -> 解析线程
        self.send_queue = queue.Queue(maxsize=100)    # 解析线程/其他 -> 发送线程
        
        # 握手相关
        self.e0_handshake_thread = None
        self.e0_handshake_stop = threading.Event()
        self.mcu_connected = False
        
        # 配置相关
        self.addr_map = addr_map or {}
        self.f0_response_getter = f0_response_getter or (lambda: False)
        self.response_40_50_getter = response_40_50_getter or (lambda: False)
    def start_listener(self):
        """启动四线程架构"""
        if self.running:
            return
            
        self.running = True
        
        # 启动发送线程
        self.sender_thread = threading.Thread(target=self._sender_worker, daemon=True)
        self.sender_thread.start()
        
        # 启动数据解析线程
        self.parser_thread = threading.Thread(target=self._parse_packets, daemon=True)
        self.parser_thread.start()
        
        # 启动串口监听线程
        self.listener_thread = threading.Thread(target=self._listen, daemon=True)
        self.listener_thread.start()

    def stop_listener(self):
        """停止四线程架构 - 优化版本，减少等待时间并防止死锁"""
        if not self.running:
            return
            
        self.running = False
        
        # 立即发送停止信号给所有线程
        self._send_stop_signals()
        
        # 停止握手线程
        self.stop_e0_handshake()
        
        # 使用更短的超时时间，防止长时间阻塞
        def wait_for_thread(thread, name, timeout=0.3):
            """等待单个线程结束"""
            if thread and thread.is_alive():
                thread.join(timeout=timeout)
                if thread.is_alive():
                    self.log_func(f"Warning: {name} thread did not stop gracefully within {timeout}s")
                    return False
            return True
        
        # 顺序等待线程，避免并发等待可能的问题
        threads_to_wait = [
            (self.listener_thread, "Listener"),
            (self.parser_thread, "Parser"), 
            (self.sender_thread, "Sender")
        ]
        
        for thread, name in threads_to_wait:
            if thread:
                wait_for_thread(thread, name, 0.3)
        
        # 清理线程引用
        self.listener_thread = None
        self.parser_thread = None
        self.sender_thread = None
        
        # 清空所有队列
        self._clear_queue(self.packet_queue)
        self._clear_queue(self.send_queue)
        
        # 清理挂起的请求
        with self.pending_lock:
            self.pending_requests.clear()
    
    def _send_stop_signals(self):
        """向所有线程发送停止信号"""
        # 向解析线程发送停止信号
        try:
            self.packet_queue.put_nowait(None)
        except queue.Full:
            self._clear_queue(self.packet_queue)
            try:
                self.packet_queue.put_nowait(None)
            except queue.Full:
                pass
        
        # 向发送线程发送停止信号
        try:
            self.send_queue.put_nowait(None)
        except queue.Full:
            self._clear_queue(self.send_queue)
            try:
                self.send_queue.put_nowait(None)
            except queue.Full:
                pass
    
    def _clear_queue(self, q):
        """清空队列"""
        while not q.empty():
            try:
                q.get_nowait()
            except queue.Empty:
                break
    
    def _sender_worker(self):
        """发送线程 - 专门负责所有串口发送操作"""
        send_count = 0
        while self.running:
            try:
                # 从发送队列获取数据，设置超时避免阻塞
                data = self.send_queue.get(timeout=0.1)
                
                # 检查停止信号
                if data is None:
                    break
                
                # 执行发送操作
                try:
                    if self.uart.is_open():
                        self.uart.write(data)
                        send_count += 1
                        self.log_func(f"Send[{send_count}]: {' '.join(f'{b:02X}' for b in data)}")
                    else:
                        self.log_func("Cannot send: UART port is closed")
                except Exception as e:
                    self.log_func(f"Send failed: {e}")
                    
            except queue.Empty:
                continue
            except Exception as e:
                self.log_func(f"Sender thread error: {e}")
                break
        
        self.log_func(f"Sender thread stopped, total sent: {send_count} packets")

    def _parse_packets(self):
        """数据解析线程 - 负责解析数据包和发送回复"""
        while self.running:
            try:
                # 从队列中获取数据包，设置超时避免阻塞
                packet = self.packet_queue.get(timeout=1.0)
                
                # 收到停止信号
                if packet is None:
                    break
                
                # 解析数据包
                fun_code = packet[1]
                
                # 握手包优先处理
                if fun_code in (PU_FUN_CONNECT, PU_FUN_MCU_RESET):
                    if self._handle_handshake_packet(packet):
                        continue
                
                # 其他数据包处理
                self._handle_data_packet(packet)
                
            except queue.Empty:
                # 超时是正常的，继续循环
                continue
            except Exception as e:
                self.log_func(f"Parser error: {e}")
                continue

    def _listen(self):
        """串口监听线程 - 只负责接收数据和分包"""
        recv_buffer = bytearray()
        while self.running and self.uart.is_open():
            try:
                # 检查停止标志，快速响应停止请求
                if not self.running:
                    break
                    
                if self.uart.in_waiting() > 0:
                    recv_buffer += self.uart.read(self.uart.in_waiting())
                
                # 粘包处理循环 - 只负责分包，不做数据解析
                while len(recv_buffer) >= MIN_PACKET_SIZE and self.running:
                    # 1. 找包头
                    idx = recv_buffer.find(PU_FRAME_HEAD)
                    if idx == -1:
                        # 没有包头，全部丢弃
                        if len(recv_buffer) > 0:
                            self.log_func(f"discard packet: NO HEAD {' '.join(f'{b:02X}' for b in recv_buffer)}")
                        recv_buffer.clear()
                        break
                    if idx > 0:
                        # 丢弃包头前的无效数据
                        discarded = recv_buffer[:idx]
                        if len(discarded) > 0:
                            self.log_func(f"discard invalid data: {' '.join(f'{b:02X}' for b in discarded)}")
                        recv_buffer = recv_buffer[idx:]
                    
                    # 2. 检查最小长度
                    if len(recv_buffer) < MIN_PACKET_SIZE:
                        break  # 等待更多数据
                    
                    # 3. 检查FUN_CODE
                    fun_code = recv_buffer[1]
                    if fun_code not in ALLOWED_FUN_CODES:
                        # FUN_CODE非法，丢弃当前包头到下一个包头之间的所有数据
                        next_head = recv_buffer[1:].find(PU_FRAME_HEAD)
                        if next_head == -1:
                            # 后面没有包头，全部丢弃
                            invalid_packet = recv_buffer[:]
                            self.log_func(
                                f"discard packet: INVALID FUN_CODE: 0x{fun_code:02X}, packet: " +
                                ' '.join(f'{b:02X}' for b in invalid_packet)
                            )
                            recv_buffer.clear()
                            break
                        else:
                            # 丢弃到下一个包头
                            invalid_packet = recv_buffer[:next_head+1]
                            self.log_func(
                                f"Invalid FUN_CODE: 0x{fun_code:02X}, discard: " +
                                ' '.join(f'{b:02X}' for b in invalid_packet)
                            )
                            recv_buffer = recv_buffer[next_head + 1:]
                        continue
                    
                    # 4. 读取LEN字段
                    data_len = (recv_buffer[2] << 8) | recv_buffer[3]
                    total_len = 1 + 1 + 2 + data_len + 2  # 包头+FUN_CODE+LEN+DATA+CRC
                    if len(recv_buffer) < total_len:
                        break  # 数据还不够，等待下次
                    
                    # 5. 取出完整包并发送给解析线程
                    packet = recv_buffer[:total_len]
                    self.log_func(f"recv packet: {' '.join(f'{b:02X}' for b in packet)}")
                    
                    # 将完整数据包发送给解析线程
                    try:
                        self.packet_queue.put_nowait(bytes(packet))
                    except queue.Full:
                        self.log_func("Packet queue full, dropping packet")
                        # 清理一些旧包为新包让路
                        try:
                            self.packet_queue.get_nowait()
                            self.packet_queue.put_nowait(bytes(packet))
                        except (queue.Empty, queue.Full):
                            pass
                    
                    recv_buffer = recv_buffer[total_len:]
                
                # 使用更短的睡眠时间，提高响应速度
                time.sleep(0.005)
            except (serial.SerialException, OSError) as e:
                # 串口异常或句柄无效时，优雅退出监听线程
                if "句柄无效" in str(e) or "ClearCommError failed" in str(e) or not self.uart.is_open():
                    self.log_func("Serial port closed or handle invalid, stopping listener")
                    break
                else:
                    self.log_func(f"Listener error: {e}")
                    break
            except Exception as e:
                self.log_func(f"Listener error: {e}")
                break

    def _handle_handshake_packet(self, data):
        """处理握手包 - 在解析线程中调用"""
        # 检查是否为握手帧，如果是则自动回复
        # 握手帧格式: 5A F0 00 00 + CRC(2字节)
        if len(data) == 6 and data[0] == PU_FRAME_HEAD and data[1] == PU_FUN_MCU_RESET and data[2] == 0x00 and data[3] == 0x00:
            received_crc = (data[4] << 8) | data[5]
            calculated_crc = calculate_crc16(data[:4], 4)
            if received_crc == calculated_crc:
                try:
                    self.log_func("MCU RESET")
                    if self.f0_response_getter():
                        self._send_response(data)
                        self.log_func("Recv handshake, sent handshake reply.")
                except Exception as e:
                    self.log_func(f"Handshake reply failed: {e}")
                return True
            else:
                if self.f0_response_getter():
                    self._send_status_response(PU_FUN_MCU_RESET, PU_STATUS_CRC_ERROR)
                return False
        
        # 检查E0握手回复
        if len(data) == 6 and data[0] == PU_FRAME_HEAD and data[1] == PU_FUN_CONNECT and data[2] == 0x00 and data[3] == 0x00:
            received_crc = (data[4] << 8) | data[5]
            calculated_crc = calculate_crc16(data[:4], 4)
            if received_crc == calculated_crc:
                self.mcu_connected = True
                self.log_func("MCU connected")
                self.e0_handshake_stop.set()
                return True
        return False

    def start_e0_handshake(self, timeout=10.0):
        """Start E0 handshake process with a timeout
        
        Args:
            timeout: Maximum time in seconds to wait for handshake to complete
        """
        self.mcu_connected = False
        self.e0_handshake_stop.clear()
        self.handshake_start_time = time.time()
        
        def handshake_loop():
            not_connected_logged = False
            while not self.mcu_connected and self.uart.is_open() and not self.e0_handshake_stop.is_set():
                try:
                    # Check if handshake timeout has been reached
                    if time.time() - self.handshake_start_time > timeout:
                        self.log_func("Handshake timeout, stopping...")
                        self.e0_handshake_stop.set()
                        break
                        
                    # 发送E0握手包
                    from protocol import generate_e0_handshake
                    e0_packet = generate_e0_handshake()
                    self._send_response(e0_packet)
                    
                    if not not_connected_logged:
                        self.log_func("MCU not connected, starting handshake...")
                        not_connected_logged = True
                        
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.log_func(f"Handshake error: {e}")
                    break
                    
        # Stop any existing handshake thread
        self.stop_e0_handshake()
        
        # Start new handshake thread
        self.e0_handshake_thread = threading.Thread(
            target=handshake_loop, 
            daemon=True,
            name="E0_Handshake_Thread"
        )
        self.e0_handshake_thread.start()
        
    def stop_e0_handshake(self):
        """Stop the E0 handshake process if it's running"""
        if hasattr(self, 'e0_handshake_thread') and self.e0_handshake_thread is not None:
            self.e0_handshake_stop.set()
            if self.e0_handshake_thread.is_alive():
                self.e0_handshake_thread.join(timeout=1.0)
                if self.e0_handshake_thread.is_alive():
                    self.log_func("Warning: Handshake thread did not stop gracefully")
            self.e0_handshake_thread = None
        self.mcu_connected = False

    def _send_response(self, data):
        """将响应数据放入发送队列 - 优化版本"""
        try:
            self.send_queue.put_nowait(data)
        except queue.Full:
            self.log_func("Send queue full, trying to make space...")
            # 更安全的队列清理：只清理一个，避免大量数据丢失
            try:
                dropped_data = self.send_queue.get_nowait()
                self.log_func(f"Dropped data due to full queue: {' '.join(f'{b:02X}' for b in dropped_data[:8])}...")
                self.send_queue.put_nowait(data)
            except (queue.Empty, queue.Full):
                self.log_func("Failed to send data: queue management failed")
                # 如果还是失败，说明系统很忙，放弃这个包

    def _send_status_response(self, fun_code, status_code):
        """发送状态响应 - 线程安全"""
        # fun_code 是60 就不需要回复
        if fun_code == PU_FUN_MCU_WRITE_DATA:
            return
        resp = generate_status_response(fun_code, status_code)
        self._send_response(resp)

    def _handle_data_packet(self, data):
        """处理数据包 - 在解析线程中调用"""
        try:
            # 1. CRC校验
            received_crc = (data[-2] << 8) | data[-1]
            calculated_crc = calculate_crc16(data[:-2], len(data)-2)
            fun_code = data[1]
            data_len = (data[2] << 8) | data[3]
            
            # 2. 处理配置更新完成包 (0x51)
            if fun_code == PU_FUN_CONFIG_UPDATE_DONE:
                if received_crc != calculated_crc:
                    self._send_status_response(fun_code, PU_STATUS_CRC_ERROR)
                    self.log_func("CONFIG_UPDATE_DONE: CRC error, discard: " + ' '.join(f'{b:02X}' for b in data))
                    return
                if data_len != 0x00:
                    self._send_status_response(fun_code, PU_STATUS_DATA_LENGTH_ERROR)
                    self.log_func(f"CONFIG_UPDATE_DONE: invalid data_len, expected 0x00, got 0x{data_len:02X}, discard: " + ' '.join(f'{b:02X}' for b in data))
                    return
                
                self.log_func("CONFIG_UPDATE_DONE received, sending OK response")
                self._send_status_response(fun_code, PU_STATUS_OK)
                return

            # 3. 处理MCU主动上报包
            if fun_code in (0x40, 0x50, 0x60):
                if received_crc != calculated_crc:
                    if self.response_40_50_getter():
                        self._send_status_response(fun_code, PU_STATUS_CRC_ERROR)
                        self.log_func("serial_data: CRC error, discard: " + ' '.join(f'{b:02X}' for b in data))
                        return
                if data_len % 6 != 0:
                    if self.response_40_50_getter():
                        self._send_status_response(fun_code, PU_STATUS_DATA_LENGTH_ERROR)
                        self.log_func(f"serial_data: invalid data_len for report, discard: " + ' '.join(f'{b:02X}' for b in data))
                        return
                        
                status_code = PU_STATUS_OK
                for i in range(0, data_len, 6):
                    addr = (data[4+i] << 8) | data[5+i]
                    raw_value = (data[6+i] << 24) | (data[7+i] << 16) | (data[8+i] << 8) | data[9+i]
                    item = self.addr_map.get(addr)
                    if item is None:
                        status_code = PU_STATUS_ADDRESS_ERROR
                        self.log_func(f"MCU report: addr=0x{addr:04X}, value={raw_value}, status=ADDR_ERROR")
                        break
                    else:
                        # Parse value according to item type
                        try:
                            data_type = item.get('type', 'int32_t')
                            raw_data = data[6+i:10+i]  # 4 bytes
                            parsed_value = unpack_value_by_type(raw_data, data_type)
                            # self.log_func(f"MCU report: addr=0x{addr:04X}, value={parsed_value} ({data_type}), status=OK")
                            if self.gui_update_callback:
                                self.gui_update_callback(addr, parsed_value)
                        except Exception as e:
                            # Fallback to original parsing
                            signed_value = to_signed(raw_value, bits=32)
                            # self.log_func(f"MCU report: addr=0x{addr:04X}, value={signed_value} (fallback), status=OK")
                            if self.gui_update_callback:
                                self.gui_update_callback(addr, signed_value)
                                
                if self.response_40_50_getter():
                    self._send_status_response(fun_code, status_code)
                return

            # 4. 其它包按原有逻辑处理
            if len(data) >= 8:
                resp_type = data[1]
                if resp_type in (0x11, 0xF1):  # PU_ACK_WITH_DATA, PU_ACK_NO_DATA
                    addr = (data[4] << 8) | data[5] if resp_type == 0x11 else None
                    with self.pending_lock:
                        for req_id, req in list(self.pending_requests.items()):
                            if req['type'] == 'read' and resp_type == 0x11 and req['addr'] == addr:
                                data_type = req.get('data_type', 'int32_t')
                                result = parse_response(data, is_write=False, expected_addr=addr, data_type=data_type)
                                req['callback'](result)
                                del self.pending_requests[req_id]
                                return
                            elif req['type'] == 'write' and resp_type == 0xF1:
                                result = parse_response(data, is_write=True)
                                req['callback'](result)
                                del self.pending_requests[req_id]
                                return
                            # === 升级包应答处理 ===
                            elif req['type'] == 'upgrade' and resp_type == 0xF1:
                                # 针对升级数据包
                                if 'pack_index' in req and isinstance(req['pack_index'], int) and data[4] == PU_FUN_UPGRADE:
                                    result = parse_response(data, is_write=True)
                                    req['callback'](result)
                                    del self.pending_requests[req_id]
                                    return
                                # 针对升级CRC校验包
                                elif req.get('pack_index') == 'crc' and data[4] == PU_FUN_UPGRADE_CRC:
                                    result = parse_response(data, is_write=True)
                                    req['callback'](result)
                                    del self.pending_requests[req_id]
                                    return
        except Exception as e:
            self.log_func(f"Error parsing data packet: {e}")

    def read_item(self, item, callback, timeout=5.0):
        """异步读取项目 - 真正的异步，不阻塞调用线程"""
        addr = int(item['index'], 16)
        data_type = item.get('type', 'int32_t')
        cmd = generate_read_command(addr)

        request_id = f"read_{addr}_{int(time.time()*1000)}"
        
        # 真正的异步：直接注册回调，不等待
        with self.pending_lock:
            self.pending_requests[request_id] = {
                'item': item,
                'type': 'read',
                'addr': addr,
                'data_type': data_type,
                'time': time.time(),
                'callback': callback,  # 直接使用回调
                'timeout': timeout
            }
        
        # 发送命令
        self._send_response(cmd)
        
        # 启动超时检查线程
        def timeout_checker():
            time.sleep(timeout)
            with self.pending_lock:
                request = self.pending_requests.pop(request_id, None)
                if request:
                    # 请求超时，调用回调
                    callback(None, error='timeout')
                    self.log_func(f"[TIMEOUT][{request_id}] addr=0x{addr:04X} wait={timeout:.1f}s")
        
        threading.Thread(target=timeout_checker, daemon=True).start()

    def write_item(self, item, value, callback, timeout=5.0):
        """异步写入项目 - 真正的异步，不阻塞调用线程"""
        addr = int(item['index'], 16)
        data_type = item.get('type', 'int32_t')
        cmd = generate_write_command(addr, value, data_type)

        # 地址特殊超时在注册前就决定
        eff_timeout = 20.0 if addr in (0x301C, 0x3020) else timeout
        request_id = f"write_{addr}_{int(time.time()*1000)}"

        # 真正的异步：直接注册回调，不等待
        with self.pending_lock:
            self.pending_requests[request_id] = {
                'item': item,
                'type': 'write',
                'addr': addr,
                'data_type': data_type,
                'time': time.time(),
                'callback': callback,  # 直接使用回调
                'timeout': eff_timeout
            }
        
        # 发送命令
        self._send_response(cmd)
        
        # 启动超时检查线程
        def timeout_checker():
            time.sleep(eff_timeout)
            with self.pending_lock:
                request = self.pending_requests.pop(request_id, None)
                if request:
                    # 请求超时，调用回调
                    callback(None, error='timeout')
                    self.log_func(f"[TIMEOUT][{request_id}] addr=0x{addr:04X} wait={eff_timeout:.1f}s")
        
        threading.Thread(target=timeout_checker, daemon=True).start()

    def upgrade_mcu(self, bin_data, progress_callback=None, timeout=2.0, max_retries=3):
        if len(bin_data) % UPGRADE_PACKET_SIZE != 0:
            self.log_func("upgrade failed bin size error")
            return False, "upgrade failed bin size error"
        packets = generate_upgrade_packets(bin_data)
        for upgrade_attempt in range(max_retries):
            self.log_func(f"Upgrade attempt {upgrade_attempt+1}/{max_retries}")
            # 1. 发送所有数据包
            for i, frame in enumerate(packets):
                retry_count = 0
                while retry_count < max_retries:
                    ack_event = threading.Event()
                    ack_result = {'ok': False, 'status_code': None}
                    def ack_callback(result, error=None):
                        if error:
                            ack_result['ok'] = False
                        else:
                            if result['status'] == 'success' or (result.get('status_code', 0) == PU_STATUS_OK):
                                ack_result['ok'] = True
                            else:
                                ack_result['ok'] = False
                            ack_result['status_code'] = result.get('status_code', None)
                        ack_event.set()
                    with self.pending_lock:
                        self.pending_requests[f'upgrade_{i}_{int(time.time()*1000)}'] = {
                            'type': 'upgrade',
                            'pack_index': i,
                            'time': time.time(),
                            'callback': ack_callback
                        }
                    self._send_response(frame)
                    self.log_func(f"Send upgrade pack {i+1}/{len(packets)} (try {retry_count+1}): {' '.join(f'{b:02X}' for b in frame[:16])} ... [{len(frame)} bytes]")
                    if ack_event.wait(timeout=timeout):
                        if ack_result['ok']:
                            break
                        else:
                            self.log_func(f"Upgrade pack {i+1} failed, status: {ack_result['status_code']}")
                            return False, f"Upgrade pack {i+1} failed, status: {ack_result['status_code']}"
                    else:
                        retry_count += 1
                        self.log_func(f"Upgrade pack {i+1} timeout, retry {retry_count}")
                        if retry_count >= max_retries:
                            return False, f"Upgrade pack {i+1} timeout after {max_retries} retries"
                    if progress_callback:
                        progress_callback(i+1, len(packets))
                    time.sleep(0.05)
            # 2. 发送升级CRC校验命令
            crc_cmd = generate_upgrade_crc_command(bin_data, len(packets))
            crc_ack_event = threading.Event()
            crc_ack_result = {'ok': False, 'status_code': None}
            def crc_ack_callback(result, error=None):
                if error:
                    crc_ack_result['ok'] = False
                else:
                    if result['status'] == 'success' or (result.get('status_code', 0) == PU_STATUS_OK):
                        crc_ack_result['ok'] = True
                    else:
                        crc_ack_result['ok'] = False
                    crc_ack_result['status_code'] = result.get('status_code', None)
                crc_ack_event.set()
            with self.pending_lock:
                self.pending_requests[f'upgrade_crc_{int(time.time()*1000)}'] = {
                    'type': 'upgrade',
                    'pack_index': 'crc',
                    'time': time.time(),
                    'callback': crc_ack_callback
                }
            try:
                self._send_response(crc_cmd)
                self.log_func(f"Send upgrade CRC command: {' '.join(f'{b:02X}' for b in crc_cmd)}")
            except Exception as e:
                self.log_func(f"Error sending upgrade CRC command: {e}")
                return False, f"Failed to send upgrade CRC command: {e}"
            # 3. 等待CRC回复
            if crc_ack_event.wait(timeout=10.0):
                if crc_ack_result['ok']:
                    self.log_func("Upgrade success")
                    return True, f"Upgrade file sent, total {len(packets)} packets."
                else:
                    self.log_func(f"Upgrade CRC check failed, status: {crc_ack_result['status_code']}, retrying whole upgrade...")
                    continue  # 整个升级流程重试
            else:
                self.log_func("Upgrade CRC check timeout, retrying whole upgrade...")
                continue  # 整个升级流程重试
        return False, f"Upgrade failed after {max_retries} attempts."

    def is_mcu_connected(self):
        return self.mcu_connected 

