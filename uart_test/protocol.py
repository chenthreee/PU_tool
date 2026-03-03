# protocol.py

import struct
import math

# UART Protocol Constants
PU_FRAME_HEAD = 0x5A

PU_FUN_READ = 0x10
PU_FUN_WRITE = 0x20
PU_FUN_UPGRADE = 0x30
PU_FUN_UPGRADE_CRC = 0x31
PU_FUN_CONFIG_UPDATE_DONE = 0x51
PU_FUN_MCU_RESET = 0xF0
PU_FUN_CONNECT = 0xE0

PU_FUN_MCU_WRITE_ALARM = 0x40
PU_FUN_MCU_WRITE_CONFIG = 0x50
PU_FUN_MCU_WRITE_DATA = 0x60

PU_ACK_WITH_DATA = 0x11
PU_ACK_NO_DATA = 0xF1

PU_STATUS_OK = 0x00
PU_STATUS_NO_FUNCODE = 0xF0
PU_STATUS_CRC_ERROR = 0xF1
PU_STATUS_ADDRESS_ERROR = 0xF2
PU_STATUS_NO_PERMISSION = 0xF3
PU_STATUS_DATA_ERROR = 0xF4
PU_STATUS_WRITE_FLASHDB_ERROR = 0xF5
PU_STATUS_RW_I2C_ERROR = 0xF6
PU_STATUS_DATA_LENGTH_ERROR = 0xF7
PU_STATUS_UPGRADE_PACKAGE_CRC_ERROR = 0xF8

# 最小包大小
MIN_PACKET_SIZE = 6
# 升级包大小
UPGRADE_PACKET_SIZE = 2048

def get_type_info(type_str):
    """Get size, format string, and value range for a given type"""
    type_map = {
        'int8_t': {'size': 1, 'format': 'b', 'min': -128, 'max': 127},
        'uint8_t': {'size': 1, 'format': 'B', 'min': 0, 'max': 255},
        'int16_t': {'size': 2, 'format': '>h', 'min': -32768, 'max': 32767},
        'uint16_t': {'size': 2, 'format': '>H', 'min': 0, 'max': 65535},
        'int32_t': {'size': 4, 'format': '>i', 'min': -2147483648, 'max': 2147483647},
        'uint32_t': {'size': 4, 'format': '>I', 'min': 0, 'max': 4294967295},
        'float': {'size': 4, 'format': '>f', 'min': -3.4e38, 'max': 3.4e38}
    }
    return type_map.get(type_str, type_map['int32_t'])  # Default to int32_t

def validate_value_for_type(value, type_str):
    """Validate and return parsed value if valid, else None"""
    type_info = get_type_info(type_str)
    try:
        if type_str == 'float':
            val = float(value)
        else:
            val = int(value)  # 只接受十进制
        if type_info['min'] <= val <= type_info['max']:
            return val
        return None
    except ValueError:
        return None

def pack_value_by_type(value, type_str):
    """Pack a value according to its type, always return 4 bytes in big-endian format"""
    if type_str == 'float':
        # Float: pack as big-endian float, already 4 bytes
        return struct.pack('>f', float(value))
    else:
        # Integer types: pack to 4 bytes big-endian, with proper alignment
        val = int(value)
        
        if type_str in ['int8_t', 'uint8_t']:
            # 8-bit value: pack as 32-bit big-endian (high 24 bits are 0)
            if type_str == 'int8_t' and val < 0:
                # Sign extend for negative int8_t values
                val = val & 0xFF  # Convert to unsigned byte representation
                return struct.pack('>I', val)
            else:
                return struct.pack('>I', val & 0xFF)
                
        elif type_str in ['int16_t', 'uint16_t']:
            # 16-bit value: pack as 32-bit big-endian (high 16 bits are 0)
            if type_str == 'int16_t' and val < 0:
                # Sign extend for negative int16_t values
                val = val & 0xFFFF  # Convert to unsigned short representation
                return struct.pack('>I', val)
            else:
                return struct.pack('>I', val & 0xFFFF)
                
        else:  # int32_t, uint32_t or default
            if type_str == 'uint32_t':
                return struct.pack('>I', val & 0xFFFFFFFF)
            else:
                return struct.pack('>i', val)

def unpack_value_by_type(data, type_str):
    """Unpack 4-byte big-endian data according to its type"""
    if len(data) < 4:
        raise ValueError(f"Need 4 bytes of data, got {len(data)}")
    
    # Always work with 4 bytes
    data_4bytes = data[:4]
    
    if type_str == 'float':
        # Float: unpack as big-endian float
        return struct.unpack('>f', data_4bytes)[0]
    else:
        # First unpack as 32-bit unsigned big-endian
        full_val = struct.unpack('>I', data_4bytes)[0]
        
        if type_str in ['int8_t', 'uint8_t']:
            # Extract the lowest 8 bits
            val_8 = full_val & 0xFF
            if type_str == 'int8_t':
                # Convert to signed 8-bit
                return val_8 if val_8 < 128 else val_8 - 256
            else:
                return val_8
                
        elif type_str in ['int16_t', 'uint16_t']:
            # Extract the lowest 16 bits
            val_16 = full_val & 0xFFFF
            if type_str == 'int16_t':
                # Convert to signed 16-bit
                return val_16 if val_16 < 32768 else val_16 - 65536
            else:
                return val_16
                
        else:  # int32_t, uint32_t or default
            if type_str == 'uint32_t':
                return full_val
            else:
                # Convert to signed 32-bit
                return struct.unpack('>i', data_4bytes)[0]

def calculate_crc16(data, length):
    """
    Calculate CRC-16-CCITT (XMODEM) checksum
    Args:
        data: bytes or bytearray to calculate CRC for
        length: length of the data
    Returns:
        16-bit CRC value
    """
    POLYNOMIAL = 0x11021
    crc = 0xFFFF
    for i in range(length):
        crc ^= (data[i] << 8) & 0xFFFF
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ POLYNOMIAL) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF

def to_signed(val, bits=32):
    if val & (1 << (bits - 1)):
        return val - (1 << bits)
    return val

def generate_read_command(addr):
    """
    Generate read command frame with CRC
    Args:
        addr: 32-bit address to read from (e.g. 0x1200)
    Returns:
        bytearray containing the complete command frame
    """
    data = bytearray([
        PU_FRAME_HEAD,
        PU_FUN_READ,
        0x00, 0x02,
        (addr >> 8) & 0xFF,
        addr & 0xFF
    ])
    crc = calculate_crc16(data, len(data))
    data.append((crc >> 8) & 0xFF)
    data.append(crc & 0xFF)
    return data

def generate_write_command(addr, value, data_type='int32_t'):
    """
    Generate write command frame with CRC
    Args:
        addr: 16-bit address to write to (e.g. 0x1200)
        value: value to write
        data_type: type string from JSON (e.g. 'int16_t', 'float')
    Returns:
        bytearray containing the complete command frame
    """
    # Pack value according to its type (always returns 4 bytes in big-endian)
    try:
        packed_data = pack_value_by_type(value, data_type)
    except Exception as e:
        # Fallback to original method if packing fails
        packed_data = struct.pack('>i', int(value))
    
    data = bytearray([
        PU_FRAME_HEAD,
        PU_FUN_WRITE,
        0x00, 0x06,
        (addr >> 8) & 0xFF,
        addr & 0xFF,
    ])
    
    data.extend(packed_data)
    
    crc = calculate_crc16(data, len(data))
    data.append((crc >> 8) & 0xFF)
    data.append(crc & 0xFF)
    return data

def parse_response(response, is_write=False, expected_addr=None, data_type='int32_t'):
    """
    Parse the response from UART with type awareness
    For read command:
        Success response(12B): 5A 11 00 06 + addr(2B) + data(4B) + crc(2B)
        Error response(8B): 5A F1 00 02 + pu_fun_code(1B) + STATUS_CODE(1B) + CRC(2B)
    For write command:
        Only error response format(8B): 5A F1 00 02 + pu_fun_code(1B) + STATUS_CODE(1B) + CRC(2B)
    """
    if len(response) < 8:
        raise ValueError("Response too short")
    if response[0] != PU_FRAME_HEAD:
        raise ValueError("Invalid response header")
    resp_type = response[1]
    length = (response[2] << 8) | response[3]
    received_crc = (response[-2] << 8) | response[-1]
    calculated_crc = calculate_crc16(response[:-2], len(response)-2)
    if received_crc != calculated_crc:
        raise ValueError("CRC check failed")
    if resp_type == PU_ACK_WITH_DATA:
        if is_write:
            raise ValueError("Unexpected data response for write command")
        if length != 0x06:
            raise ValueError("Invalid length for read response")
        if len(response) != 12:
            raise ValueError("Invalid response length")
        
        addr = (response[4] << 8) | response[5]
        raw_data = response[6:10]  # 4 bytes of data
        
        # Parse according to the specified type
        try:
            parsed_value = unpack_value_by_type(raw_data, data_type)
        except Exception as e:
            # Fallback to original parsing for compatibility
            parsed_value = (response[6] << 24) | (response[7] << 16) | (response[8] << 8) | response[9]
            parsed_value = to_signed(parsed_value)
        
        if expected_addr is not None and addr != expected_addr:
            raise ValueError(f"Address mismatch: expected 0x{expected_addr:04X}, got 0x{addr:04X}")
        
        return {
            'status': 'success',
            'addr': addr,
            'data': parsed_value,
            'raw_data': raw_data.hex(),
            'type': data_type
        }
    elif resp_type == PU_ACK_NO_DATA:
        if length != 0x02:
            raise ValueError("Invalid length for status response")
        if len(response) != 8:
            raise ValueError("Invalid status response length")
        pu_fun_code = response[4]
        status_code = response[5]
        if is_write and status_code == PU_STATUS_OK:
            return {
                'status': 'success',
                'status_code': status_code
            }
        return {
            'status': 'error',
            'function_code': pu_fun_code,
            'status_code': status_code
        }
    else:
        raise ValueError(f"Unknown response type: {resp_type:02X}")

def calculate_complete_addr(item):
    base_addr = int(item['base addr'], 16)
    base_addr1 = int(item['base addr.1'], 16)
    addr = int(item['addr'], 16)
    return base_addr + base_addr1 + addr

def generate_e0_handshake():
    data = bytearray([PU_FRAME_HEAD, PU_FUN_CONNECT, 0x00, 0x00])
    crc = calculate_crc16(data, 4)
    data.append((crc >> 8) & 0xFF)
    data.append(crc & 0xFF)
    return data

def generate_upgrade_packets(bin_data):
    """
    将bin数据分包，生成每个升级包的完整帧
    :param bin_data: bytes
    :return: List[bytearray]
    """
    chunk_size = UPGRADE_PACKET_SIZE
    total_len = len(bin_data)
    num_chunks = (total_len + chunk_size - 1) // chunk_size
    packets = []
    for pack_index in range(num_chunks):
        start = pack_index * chunk_size
        end = min(start + chunk_size, total_len)
        chunk = bin_data[start:end]
        frame = bytearray()
        frame.append(0x5A)
        frame.append(0x30)
        frame.append(0x08)
        frame.append(0x02)
        frame.append((pack_index >> 8) & 0xFF)
        frame.append(pack_index & 0xFF)
        frame.extend(chunk)
        if len(chunk) < chunk_size:
            frame.extend([0x00] * (chunk_size - len(chunk)))
        crc = calculate_crc16(frame, len(frame))
        frame.append((crc >> 8) & 0xFF)
        frame.append(crc & 0xFF)
        packets.append(frame)
    return packets

def generate_upgrade_crc_command(bin_data, pack_sum_num):
    """
    生成升级bin包后需要发送的5A 31 00 04 + binCRC(2) + PACK_SUM_NUM(2) + CRC(2)指令
    :param bin_data: bytes, 升级bin文件内容
    :param pack_sum_num: int, 总包数
    :return: bytearray, 完整指令
    """
    frame = bytearray()
    frame.append(0x5A)
    frame.append(0x31)
    frame.append(0x00)
    frame.append(0x04)
    # binCRC: 整个bin文件的CRC16（XMODEM）
    bin_crc = calculate_crc16(bin_data, len(bin_data))
    frame.append((bin_crc >> 8) & 0xFF)
    frame.append(bin_crc & 0xFF)
    # PACK_SUM_NUM: 总包数，2字节大端
    frame.append((pack_sum_num >> 8) & 0xFF)
    frame.append(pack_sum_num & 0xFF)
    # 整帧CRC
    crc = calculate_crc16(frame, len(frame))
    frame.append((crc >> 8) & 0xFF)
    frame.append(crc & 0xFF)
    return frame

def generate_status_response(fun_code, status_code):
    """
    生成 5A F1 00 02 + FUN_CODE + STATUS_CODE + CRC(2) 回复帧
    """
    resp = bytearray([0x5A, 0xF1, 0x00, 0x02, fun_code, status_code])
    crc = calculate_crc16(resp, len(resp))
    resp.append((crc >> 8) & 0xFF)
    resp.append(crc & 0xFF)
    return resp
