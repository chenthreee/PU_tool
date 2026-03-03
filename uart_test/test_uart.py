#!/usr/bin/env python3
import serial
import time
import struct
import json
from utils import get_resource_path

# UART Protocol Constants
PU_FRAME_HEAD = 0x5A

PU_FUN_READ = 0x10
PU_FUN_WRITE = 0x20

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

def generate_read_command(addr):
    """
    Generate read command frame with CRC
    Args:
        addr: 32-bit address to read from (e.g. 0x1200)
    Returns:
        bytearray containing the complete command frame
    """
    # Frame format: HEAD + FUNC + LEN_H + LEN_L + ADDR_H + ADDR_L + CRC_H + CRC_L
    data = bytearray([
        PU_FRAME_HEAD,    # Frame head (0x5A)
        PU_FUN_READ,      # Function code (0x10)
        0x00, 0x02,       # Length (2 bytes)
        (addr >> 8) & 0xFF,  # Address high byte
        addr & 0xFF          # Address low byte
    ])
    
    # Calculate CRC for the frame
    crc = calculate_crc16(data, len(data))
    
    # Add CRC to frame
    data.append((crc >> 8) & 0xFF)  # CRC high byte
    data.append(crc & 0xFF)         # CRC low byte
    
    return data

def generate_write_command(addr, value):
    """
    Generate write command frame with CRC
    Args:
        addr: 32-bit address to write to (e.g. 0x1200)
        value: 32-bit integer data to write
    Returns:
        bytearray containing the complete command frame
    """
    # Frame format: HEAD + FUNC + LEN_H + LEN_L + ADDR_H + ADDR_L + DATA(4 bytes) + CRC_H + CRC_L
    data = bytearray([
        PU_FRAME_HEAD,    # Frame head (0x5A)
        PU_FUN_WRITE,     # Function code (0x20)
        0x00, 0x06,       # Length (6 bytes: 2 for address + 4 for data)
        (addr >> 8) & 0xFF,  # Address high byte
        addr & 0xFF,         # Address low byte
        (value >> 24) & 0xFF,  # Data byte 3 (MSB)
        (value >> 16) & 0xFF,  # Data byte 2
        (value >> 8) & 0xFF,   # Data byte 1
        value & 0xFF           # Data byte 0 (LSB)
    ])
    
    # Calculate CRC for the frame
    crc = calculate_crc16(data, len(data))
    
    # Add CRC to frame
    data.append((crc >> 8) & 0xFF)  # CRC high byte
    data.append(crc & 0xFF)         # CRC low byte
    
    return data

def update_json_with_commands():
    """
    Read JSON file, calculate complete addresses and generate read/write commands
    """
    try:
        # Read the JSON file
        with open(get_resource_path('uart_command_set.json'), 'r', encoding='utf-8') as f:
            items = json.load(f)
        
        # Process each item
        for item in items:
            # Calculate complete address
            base_addr = int(item['base addr'], 16)
            base_addr1 = int(item['base addr.1'], 16)
            addr = int(item['addr'], 16)
            complete_addr = base_addr + base_addr1 + addr
            
            # 将complete_addr填入index项，改为16进制字符串
            item['index'] = f"0x{complete_addr:04X}"
            
            # Generate read command
            read_cmd = generate_read_command(complete_addr)
            read_cmd_str = ' '.join([f'{x:02X}' for x in read_cmd])
            item['read command'] = read_cmd_str
            
            # Get write data value from JSON (default to 0 if not present)
            write_data = 0
            if 'write data' in item:
                try:
                    # Handle both hex string and decimal string
                    write_data_str = item['write data']
                    if write_data_str.startswith('0x'):
                        write_data = int(write_data_str, 16)
                    else:
                        write_data = int(write_data_str)
                except ValueError:
                    write_data = 0
            
            # Generate write command with the write data value
            write_cmd = generate_write_command(complete_addr, write_data)
            write_cmd_str = ' '.join([f'{x:02X}' for x in write_cmd])
            item['write command'] = write_cmd_str
        
        # Write back to JSON file
        with open(get_resource_path('uart_command_set.json'), 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
            
        print("Successfully updated read/write commands in JSON file")
            
    except Exception as e:
        print(f"Error updating JSON file: {e}")

# Test function
if __name__ == "__main__":
    # Update JSON file with read/write commands
    update_json_with_commands()
    
    # Test read command generation
    test_addr = 0x1000
    cmd = generate_read_command(test_addr)
    print(f"Read command for address 0x{test_addr:04X}:")
    print("TX:", " ".join([f"{x:02X}" for x in cmd]))
    
    # Test write command generation
    test_value = 0x0F
    cmd = generate_write_command(test_addr, test_value)
    print(f"\nWrite command for address 0x{test_addr:04X}, value 0x{test_value:08X}:")
    print("TX:", " ".join([f"{x:02X}" for x in cmd]))




