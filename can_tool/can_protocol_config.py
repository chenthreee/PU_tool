 # CAN协议配置文件

# 波特率设置
BAUDRATE_250K = 250000
BAUDRATE_500K = 500000

# CAN报文ID定义
CAN_IDS = {
    'INVERTER_TO_BMS': 0x305,    # 逆变器到BMS
    'INVERTER_CONTROL': 0x307,   # 逆变器控制
    'BMS_CHARGE_DISCHARGE': 0x351,  # BMS充放电信息（用作心跳标志）
    'BMS_STATUS': 0x355,         # BMS状态
    'BATTERY_INFO': 0x356,       # 电池信息
    'ERROR_MESSAGE': 0x35A,      # 错误信息
    

}



# 报文数据结构定义
MESSAGE_STRUCTURES = {
    0x305: {
        'name': '逆变器到BMS',
        'length': 8,
        'fields': [
            {'name': 'status', 'offset': 0, 'length': 1, 'description': '状态字节'},
            {'name': 'control', 'offset': 1, 'length': 1, 'description': '控制字节'},
            {'name': 'reserved', 'offset': 2, 'length': 6, 'description': '保留字节'},
        ]
    },
    0x307: {
        'name': '逆变器控制',
        'length': 8,
        'fields': [
            {'name': 'status', 'offset': 0, 'length': 1, 'description': '状态字节'},
            {'name': 'control', 'offset': 1, 'length': 1, 'description': '控制字节'},
            {'name': 'reserved', 'offset': 2, 'length': 6, 'description': '保留字节'},
        ]
    },
    0x351: {
        'name': 'BMS充放电信息（心跳标志）',
        'length': 8,
        'fields': [
            {'name': 'charge_voltage_limit', 'offset': 0, 'length': 2, 'data_type': 'un16', 'scaling': 0.1, 'unit': 'V', 'description': '充电电压限制'},
            {'name': 'max_charge_current', 'offset': 2, 'length': 2, 'data_type': 'un16', 'scaling': 0.1, 'unit': 'A', 'description': '最大充电电流'},
            {'name': 'max_discharge_current', 'offset': 4, 'length': 2, 'data_type': 'un16', 'scaling': 0.1, 'unit': 'A', 'description': '最大放电电流'},
            {'name': 'discharge_voltage', 'offset': 6, 'length': 2, 'data_type': 'un16', 'scaling': 0.1, 'unit': 'V', 'description': '放电电压'},
        ]
    },
    0x355: {
        'name': 'BMS状态',
        'length': 8,
        'fields': [
            {'name': 'soc_value', 'offset': 0, 'length': 2, 'data_type': 'un16', 'scaling': 1, 'unit': '%', 'description': 'SOC值'},
            {'name': 'soh_value', 'offset': 2, 'length': 2, 'data_type': 'un16', 'scaling': 1, 'unit': '%', 'description': 'SOH值'},
            {'name': 'high_res_soc', 'offset': 4, 'length': 2, 'data_type': 'un16', 'scaling': 0.01, 'unit': '%', 'description': '高精度SOC'},
        ]
    },
    0x356: {
        'name': '电池信息',
        'length': 8,
        'fields': [
            {'name': 'battery_voltage', 'offset': 0, 'length': 2, 'data_type': 'sn16', 'scaling': 0.01, 'unit': 'V', 'description': '电池电压'},
            {'name': 'battery_current', 'offset': 2, 'length': 2, 'data_type': 'sn16', 'scaling': 0.1, 'unit': 'A', 'description': '电池电流'},
            {'name': 'battery_temperature', 'offset': 4, 'length': 2, 'data_type': 'sn16', 'scaling': 0.1, 'unit': '°C', 'description': '电池温度'},
        ]
    },
    0x35A: {
        'name': 'BMS警告信息',
        'length': 8,
        'fields': [
            {'name': 'warnings', 'offset': 4, 'length': 4, 'data_type': 'bit_flags', 'description': '警告位'},
        ]
    },
    0x600: {
        'name': 'BMS模式',
        'length': 8,
        'fields': [
            {'name': 'operation_mode', 'offset': 0, 'length': 1, 'data_type': 'bit_flags', 'description': 'operation_mode'},
            {'name': 'state_of_charge', 'offset': 1, 'length': 1, 'data_type': 'uint8', 'scaling': 0.5, 'unit': '%','description': 'state_of_charge'},
            {'name': 'status', 'offset': 2, 'length': 2, 'data_type': 'bit_flags', 'description': 'status'},
        ]
    },
    0x610: {
        'name': '电池参数',
        'length': 8,
        'fields': [
            {'name': 'battery_current', 'offset': 0, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': 'A','description': 'battery_current'},
            {'name': 'battery_voltage', 'offset': 2, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'battery_voltage'},
            {'name': 'rail_voltage', 'offset': 4, 'length': 2, 'data_type': 'uint16','scaling': 0.001, 'unit': 'V', 'description': 'rail_voltage'},
            {'name': 'fet_temperature', 'offset': 6, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C', 'description': 'fet_temperature'},
        ]
    },
    0x620: {
        'name': '电芯电压',
        'length': 8,
        'fields': [
            {'name': 'cell_voltage_1', 'offset': 0, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 1 in mV'},
            {'name': 'cell_voltage_2', 'offset': 2, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 2 in mV'},
            {'name': 'cell_voltage_3', 'offset': 4, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 3 in mV'},
            {'name': 'cell_voltage_4', 'offset': 6, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 4 in mV'},
        ]
    },
    0x630: {
        'name': '电芯电压',
        'length': 8,
        'fields': [
            {'name': 'cell_voltage_5', 'offset': 0, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 5 in mV'},
            {'name': 'cell_voltage_6', 'offset': 2, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 6 in mV'},
            {'name': 'cell_voltage_7', 'offset': 4, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 7 in mV'},
            {'name': 'cell_voltage_8', 'offset': 6, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 8 in mV'},
        ]
    },
    0x640: {
        'name': '电芯电压',
        'length': 8,
        'fields': [
            {'name': 'cell_voltage_9', 'offset': 0, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 9 in mV'},
            {'name': 'cell_voltage_10', 'offset': 2, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 10 in mV'},
            {'name': 'cell_voltage_11', 'offset': 4, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 11 in mV'},
            {'name': 'cell_voltage_12', 'offset': 6, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 12 in mV'},
        ]
    },
    0x650: {
        'name': '电芯电压',
        'length': 8,
        'fields': [
            {'name': 'cell_voltage_13', 'offset': 0, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 13 in mV'},
            {'name': 'cell_voltage_14', 'offset': 2, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 14 in mV'},
            {'name': 'cell_voltage_15', 'offset': 4, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 15 in mV'},
            {'name': 'cell_voltage_16', 'offset': 6, 'length': 2, 'data_type': 'uint16', 'scaling': 0.001, 'unit': 'V','description': 'Cell voltage 16 in mV'},
        ]
    },
    0x660: {
        'name': '电芯温度',
        'length': 8,
        'fields': [
            {'name': 'cell_temperature_1', 'offset': 0, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Cell temperature 1 in °C'},
            {'name': 'cell_temperature_2', 'offset': 2, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Cell temperature 2 in °C'},
            {'name': 'cell_temperature_3', 'offset': 4, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Cell temperature 3 in °C'},
            {'name': 'cell_temperature_4', 'offset': 6, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Cell temperature 4 in °C'},
        ]
    },
    0x670: {
        'name': '配置信息',
        'length': 8,
        'fields': [
            {'name': 'Arm_Antitheft_mode', 'offset': 0, 'length': 1, 'data_type': 'uint8', 'scaling': 1, 'description': 'ARM防盗模式'},
            {'name': 'external_output', 'offset': 1, 'length': 1, 'data_type': 'uint8', 'scaling': 1, 'description': '外部输出'},
        ]
    },
    0x400: {
        'name': '系统参数',
        'length': 8,
        'fields': [
            {'name': 'dcdc_temperature_deci_celsius', 'offset': 0, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'DCDC temperature 1 in deci-Celcius'},
            {'name': 'pos_terminal_temp_deci_celsius', 'offset': 2, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Positive terminal temperature 2 in deci-Celcius'},
            {'name': 'neg_terminal_temp_deci_celsius', 'offset': 4, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Negative terminal temperature 2 in deci-Celcius'},
        ]
    },
    0x410: {
        'name': '系统参数',
        'length': 8,
        'fields': [
            {'name': 'neg_bat_temp_1_deci_celsius', 'offset': 0, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Negative internal cable joint 1 in deci-Celcius'},
            {'name': 'neg_bat_temp_2_deci_celsius', 'offset': 2, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Negative internal cable joint 2 in deci-Celcius'},
            {'name': 'pos_bat_temp_cb_deci_celsius', 'offset': 4, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'Positive internal cable joint in deci-Celcius'},
        ]
    },
    0x420: {
        'name': '系统参数',
        'length': 8,
        'fields': [
            {'name': 'state_of_health', 'offset': 0, 'length': 1, 'data_type': 'uint8', 'scaling': 0.5, 'unit': '%','description': 'SOH in 0.5% resolution'},
            {'name': 'cycle_count', 'offset': 1, 'length': 2, 'data_type': 'uint16', 'scaling': 1,'description': 'Lifetime number of cycle'},
            {'name': 'lifetime_hour', 'offset': 3, 'length': 3, 'data_type': 'uint24', 'scaling': 1, 'unit': 'h','description': 'Lifetime in hours'},
            {'name': 'cell_balance_state', 'offset': 6, 'length': 2, 'data_type': 'uint16', 'scaling': 1, 'description': 'Cell balaning state'},
        ]
    },
    0x430: {
        'name': '系统参数',
        'length': 8,
        'fields': [
            {'name': 'mcu_uptime_seconds', 'offset': 0, 'length': 4, 'data_type': 'uint32', 'scaling': 1, 'unit': 's','description': 'MCU uptime in seconds'},
            {'name': 'mcu_temperature_deci_celsius', 'offset': 4, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'MCU temperature in deci-Celcius'},
            {'name': 'afe_temperature_deci_celsius', 'offset': 6, 'length': 2, 'data_type': 'int16', 'scaling': 0.1, 'unit': '°C','description': 'AFE temperature in deci-Celcius'},
        ]
    },
    0x440: {
        'name': '系统参数',
        'length': 8,
        'fields': [
            {'name': 'esp32_uptime_seconds', 'offset': 0, 'length': 4, 'data_type': 'uint32', 'scaling': 1, 'unit': 's','description': 'ESP32 uptime in seconds'},
            {'name': ' esp32_free_heap_size_byte', 'offset': 4, 'length': 3, 'data_type': 'Uint24', 'scaling': 1, 'unit': 'B','description': 'Available memory in ESP32'},
            {'name': 'esp32_temperature_celsius', 'offset': 7, 'length': 1, 'data_type': 'int8', 'scaling': 1, 'unit': '°C','description': 'ESP32 temperature in Celcius'},
        ]
    },
    0x450: {
        'name': '控制器版本',
        'length': 8,
        'fields': [
            {'name': 'controller_version', 'offset': 0, 'length': 8, 'data_type': 'char', 'description': 'controller_version first 8 chars'},
        ]
    },
    0x460: {
        'name': '控制器版本',
        'length': 8,
        'fields': [
            {'name': 'controller_version', 'offset': 0, 'length': 8, 'data_type': 'char', 'description': 'controller_version last 8 chars'},
        ]
    },
    0x470: {
        'name': 'bms版本',
        'length': 8,
        'fields': [
            {'name': 'bms_version', 'offset': 0, 'length': 8, 'data_type': 'char', 'description': 'bms_version first 8 chars'},
        ]
    },
    0x480: {
        'name': 'bms版本',
        'length': 8,
        'fields': [
            {'name': 'bms_version', 'offset': 0, 'length': 8, 'data_type': 'char', 'description': 'bms_version last 8 chars'},
        ]
    },
    0x490: {
        'name': '加速度计',
        'length': 8,
        'fields': [
            {'name': 'accelerometer_x', 'offset': 0, 'length': 2, 'data_type': 'int16', 'scaling': 1, 'unit': 'milli-g','description': 'Accelerometer x in g'},
            {'name': 'accelerometer_y', 'offset': 2, 'length': 2, 'data_type': 'int16', 'scaling': 1, 'unit': 'milli-g','description': 'Accelerometer y in g'},
            {'name': 'accelerometer_z', 'offset': 4, 'length': 2, 'data_type': 'int16', 'scaling': 1, 'unit': 'milli-g','description': 'Accelerometer z in g'},
        ]
    },
    0x4A0: {
        'name': 'MAC地址',
        'length': 8,
        'fields': [
            {'name': ' esp32_mac_address', 'offset': 0, 'length': 6, 'data_type': 'int16','description': 'The MAC address of the ESP32'},
            {'name': 'module_id', 'offset': 6, 'length': 2, 'data_type': 'uint8', 'description': 'Physical position of the battery in bank/stack counting from top.'},
        ]
    }
}

# 心跳超时设置（秒）
HEARTBEAT_TIMEOUT = 3

# 发送间隔设置（秒）
SEND_INTERVAL = 1

# 创芯科技设备设置
CANALYST_DEVICE_TYPE = 4  # VCI_USBCAN2
CANALYST_DEVICE_INDEX = 0
CANALYST_CAN_INDEX = 0

# 定时参数映射
TIMING_PARAMS = {
    250000: (0x03, 0x1C),  # 250kbps
    500000: (0x00, 0x1C),  # 500kbps
}

def signed_16bit(high_byte, low_byte):
    """将两个字节转换为有符号16位整数"""
    value = (high_byte << 8) | low_byte
    if value > 32767:  # 负数
        value -= 65536
    return value

def parse_351_message(data):
    """解析0x351报文 - 充放电信息（用作心跳标志）"""
    if len(data) >= 8:
        # 解析充放电信息
        # charge_voltage_limit = round((data[1] << 8 | data[0]) * 0.1, 1)  # 充电电压限制 (V)
        # max_charge_current = round((data[3] << 8 | data[2]) * 0.1, 1)    # 最大充电电流 (A)
        # max_discharge_current = round((data[5] << 8 | data[4]) * 0.1, 1)  # 最大放电电流 (A)
        # discharge_voltage = round((data[7] << 8 | data[6]) * 0.1, 1)      # 放电电压 (V)
        
        return {
            'charge_voltage_limit': f"{(data[1] << 8 | data[0]) * 0.1:.1f}",
            'max_charge_current': f"{(data[3] << 8 | data[2]) * 0.1:.1f}",
            'max_discharge_current': f"{(data[5] << 8 | data[4]) * 0.1:.1f}",
            'discharge_voltage': f"{(data[7] << 8 | data[6]) * 0.1:.1f}"
        }
    else:
        return None

def parse_355_message(data):
    """解析0x355报文 - BMS状态信息"""
    if len(data) >= 6:
        # 解析SOC和SOH信息
        soc_value = (data[1] << 8 | data[0])  # SOC值 (%)
        soh_value = (data[3] << 8 | data[2])  # SOH值 (%)
        #high_res_soc = round((data[5] << 8 | data[4]) * 0.01, 2)  # 高精度SOC (%)
        
        return {
            'soc_value': soc_value,
            'soh_value': soh_value,
            'high_res_soc': f"{(data[5] << 8 | data[4]) * 0.01:.2f}"
        }
    else:
        return None

def parse_356_message(data):
    """解析0x356报文 - 电池信息"""
    if len(data) >= 6:
        # 解析电池信息（注意：sn16是有符号16位整数）
        battery_voltage = round(signed_16bit(data[1], data[0]) * 0.01, 2)  # 电池电压 (V)
        battery_current = round(signed_16bit(data[3], data[2]) * 0.1, 1)    # 电池电流 (A)
        battery_temperature = round(signed_16bit(data[5], data[4]) * 0.1, 1) # 电池温度 (°C)
        
        return {
            'battery_voltage': f"{battery_voltage:.2f}",
            'battery_current': f"{battery_current:.1f}",
            'battery_temperature': f"{battery_temperature:.1f}"
        }
    else:
        return None

def parse_35A_message(data):
    """解析0x35A报文 - BMS警告和报警信息"""
    if len(data) >= 8:
        # 解析报警位（字节0-3）
        alarms = {}
        
        # Byte 0: 报警信息
        byte0 = data[0]
        alarms['general_alarm'] = bool(byte0 & 0x03)        # bits 0+1
        alarms['battery_high_voltage_alarm'] = bool(byte0 & 0x0C)    # bits 2+3
        alarms['battery_low_voltage_alarm'] = bool(byte0 & 0x30)     # bits 4+5
        alarms['battery_high_temp_alarm'] = bool(byte0 & 0xC0)       # bits 6+7
        
        # Byte 1: 更多报警信息
        byte1 = data[1]
        alarms['battery_low_temp_alarm'] = bool(byte1 & 0x03)        # bits 0+1
        alarms['battery_high_temp_charge_alarm'] = bool(byte1 & 0x0C) # bits 2+3
        alarms['battery_low_temp_charge_alarm'] = bool(byte1 & 0x30)  # bits 4+5
        alarms['battery_high_current_alarm'] = bool(byte1 & 0xC0)     # bits 6+7
        
        # Byte 2: 更多报警信息
        byte2 = data[2]
        alarms['battery_high_charge_current_alarm'] = bool(byte2 & 0x03) # bits 0+1
        alarms['contactor_alarm'] = bool(byte2 & 0x0C)                   # bits 2+3
        alarms['short_circuit_alarm'] = bool(byte2 & 0x30)               # bits 4+5
        alarms['bms_internal_alarm'] = bool(byte2 & 0xC0)                # bits 6+7
        
        # Byte 3: 更多报警信息
        byte3 = data[3]
        alarms['cell_imbalance_alarm'] = bool(byte3 & 0x03)          # bits 0+1
        # bits 2-7: Reserved (保留位)
        
        # 解析警告位（字节4-7）
        warnings = {}
        
        # Byte 4: 警告信息
        byte4 = data[4]
        warnings['general_warning'] = bool(byte4 & 0x03)        # bits 0+1
        warnings['battery_high_voltage'] = bool(byte4 & 0x0C)    # bits 2+3
        warnings['battery_low_voltage'] = bool(byte4 & 0x30)     # bits 4+5
        warnings['battery_high_temp'] = bool(byte4 & 0xC0)       # bits 6+7
        
        # Byte 5: 更多警告信息
        byte5 = data[5]
        warnings['battery_low_temp'] = bool(byte5 & 0x03)        # bits 0+1
        warnings['battery_high_temp_charge'] = bool(byte5 & 0x0C) # bits 2+3
        warnings['battery_low_temp_charge'] = bool(byte5 & 0x30)  # bits 4+5
        warnings['battery_high_current'] = bool(byte5 & 0xC0)     # bits 6+7
        
        # Byte 6: 更多警告信息
        byte6 = data[6]
        warnings['battery_high_charge_current'] = bool(byte6 & 0x03) # bits 0+1
        warnings['contactor_warning'] = bool(byte6 & 0x0C)           # bits 2+3
        warnings['short_circuit_warning'] = bool(byte6 & 0x30)       # bits 4+5
        warnings['bms_internal'] = bool(byte6 & 0xC0)                # bits 6+7
        
        # Byte 7: 系统状态和更多警告
        byte7 = data[7]
        warnings['cell_imbalance'] = bool(byte7 & 0x03)          # bits 0+1
        warnings['system_online'] = bool(byte7 & 0x0C)           # bits 2+3 (System status)
        # bits 4-7: Reserved (保留位)
        
        return {
            'alarms': alarms,
            'warnings': warnings
        }
    else:
        return None

def parse_35E_message(data):
    """解析0x35E报文 - 厂商名称"""
    if len(data) >= 8:
        Manufacturer_name = ''.join([chr(b) for b in data if b != 0])
        return {
            'Manufacturer_name': Manufacturer_name,
        }
    return None

def parse_35F_message(data):
    """解析0x35F报文 - 电池模型、固件版本、在线容量"""
    if len(data) >= 8:
        Battery_Model = unsigned_16bit(data[1], data[0])
        Firmware_version = unsigned_16bit(data[3], data[2])
        Online_capacity_in_Ah = unsigned_16bit(data[5], data[4])
        return {
            'Battery_Model': Battery_Model,
            'Firmware_version': Firmware_version,
            'Online_capacity_in_Ah': Online_capacity_in_Ah,
        }
    return None
# 通用解析函数
def unsigned_16bit(high_byte, low_byte):
    """将两个字节转换为无符号16位整数"""
    return (high_byte << 8) | low_byte

def unsigned_24bit(byte2, byte1, byte0):
    """将三个字节转换为无符号24位整数"""
    return (byte2 << 16) | (byte1 << 8) | byte0

def unsigned_32bit(byte3, byte2, byte1, byte0):
    """将四个字节转换为无符号32位整数"""
    return (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0

# def parse_60n_message(data, battery_address=1):
#     """解析0x60n报文 - 电池模式和状态"""
#     if len(data) >= 8:
#         operation_mode = data[0] & 0x07  # bits 0-2
#         state_of_charge = data[1] * 0.5  # SOC in 0.5% resolution     
#         # Status bits (16-bit bitfield from bytes 2-3)
#         status_bits = unsigned_16bit(data[3], data[2])
#         status = {
#             'Heater': bool(status_bits & 0x01),
#             'MCB status': bool(status_bits & 0x02),
#             'Top Up': bool(status_bits & 0x04),
#             'Soft Start': bool(status_bits & 0x08),
#             'OCC Recovery': bool(status_bits & 0x10),
#         }      
#         # Alarms (32-bit bitfield from bytes 4-7)
#         alarms_bits = unsigned_32bit(data[7], data[6], data[5], data[4])
#         alarms = {
#             'COTC': bool(alarms_bits & 0x01),
#             'COTD': bool(alarms_bits & 0x02),
#             'CUTC': bool(alarms_bits & 0x04),
#             'CUTD': bool(alarms_bits & 0x08),
#             'System Lock': bool(alarms_bits & 0x10),
#             'SCD': bool(alarms_bits & 0x60),
#             'MOT': bool(alarms_bits & 0x40),
#             'DCDC_OT': bool(alarms_bits & 0x80),
#             'CMC': bool(alarms_bits & 0x100),
#             'BVP': bool(alarms_bits & 0x600),
#             'CTD': bool(alarms_bits & 0x400),
#             'MCB_TRIP': bool(alarms_bits & 0x800),
#             'UCM': bool(alarms_bits & 0x1000),
#             'WDT': bool(alarms_bits & 0x6000),
#             'U_SOC': bool(alarms_bits & 0x4000),
#             'CUVC': bool(alarms_bits & 0x8000),
#             'CUV': bool(alarms_bits & 0x10000),
#             'COV': bool(alarms_bits & 0x60000),
#             'OCC': bool(alarms_bits & 0x40000),
#             'OCD': bool(alarms_bits & 0x80000),
#         }       
#         return {
#             'operation_mode': operation_mode,
#             'state_of_charge': state_of_charge,
#             'status': status,
#             'alarms': alarms,
#             'battery_address': battery_address
#         }
#     return None
def parse_60n_message(data, battery_address=1):
    """解析0x60n报文 - 电池模式和状态"""
    if len(data) >= 8:
        operation_mode = data[0] & 0x07  # bits 0-2
        state_of_charge = data[1] * 0.5  # SOC in 0.5% resolution
        
        # Status bits (16-bit bitfield from bytes 2-3)
        status_bits = unsigned_16bit(data[3], data[2])
        Heater= bool(status_bits & 0x01)
        MCB_status= bool(status_bits & 0x02)
        Top_Up= bool(status_bits & 0x04)
        Soft_Start= bool(status_bits & 0x08)
        OCC_Recovery= bool(status_bits & 0x10)       
        # Alarms (32-bit bitfield from bytes 4-7)
        alarms_bits = unsigned_32bit(data[7], data[6], data[5], data[4])
        COTC= bool(alarms_bits & 0x01)
        COTD= bool(alarms_bits & 0x02)
        CUTC= bool(alarms_bits & 0x04)
        CUTD= bool(alarms_bits & 0x08)
        System_Lock= bool(alarms_bits & 0x10)
        SCD= bool(alarms_bits & 0x60)
        MOT= bool(alarms_bits & 0x40)
        DCDC_OT= bool(alarms_bits & 0x80)
        CMC= bool(alarms_bits & 0x100)
        BVP= bool(alarms_bits & 0x600)
        CTD= bool(alarms_bits & 0x400)
        MCB_TRIP= bool(alarms_bits & 0x800)
        UCM= bool(alarms_bits & 0x1000)
        WDT= bool(alarms_bits & 0x6000)
        U_SOC= bool(alarms_bits & 0x4000)
        CUVC= bool(alarms_bits & 0x8000)
        CUV= bool(alarms_bits & 0x10000)
        COV= bool(alarms_bits & 0x60000)
        OCC= bool(alarms_bits & 0x40000)
        OCD= bool(alarms_bits & 0x80000)
        DCDC_CC= bool(alarms_bits & 0x100000)
        
        return {
            'operation_mode': operation_mode,
            'state_of_charge': state_of_charge,
            #status
            'Heater': Heater,
            'MCB_status': MCB_status,
            'Top_Up': Top_Up,
            'Soft_Start': Soft_Start,
            'OCC_Recovery': OCC_Recovery,
            #alarms
            'COTC': COTC,
            'COTD': COTD,
            'CUTC': CUTC,
            'CUTD': CUTD,
            'System_Lock': System_Lock,
            'SCD': SCD,
            'MOT': MOT,
            'DCDC_OT': DCDC_OT,
            'CMC': CMC,
            'BVP': BVP,
            'CTD': CTD,
            'MCB_TRIP': MCB_TRIP,
            'UCM': UCM,
            'WDT': WDT,
            'U_SOC': U_SOC,
            'CUVC': CUVC,
            'CUV': CUV,
            'COV': COV,
            'OCC': OCC,
            'OCD': OCD,
            'DCDC_CC': DCDC_CC,
            #battery_address
            'battery_address': battery_address
        }
    return None

def parse_61n_message(data, battery_address=1):
    """解析0x61n报文 - 电池电流、电压和温度"""
    if len(data) >= 8:
        battery_current = round(signed_16bit(data[1], data[0]) * 0.1, 1)  # A
        battery_voltage = round(unsigned_16bit(data[3], data[2]) * 0.001, 3)  # V
        rail_voltage = round(unsigned_16bit(data[5], data[4]) * 0.001, 3)  # V
        fet_temperature = round(signed_16bit(data[7], data[6]) * 0.1, 1)  # °C
        
        return {
            'battery_current': f"{battery_current:.1f}",
            'battery_voltage': f"{battery_voltage:.3f}",
            'rail_voltage': f"{rail_voltage:.3f}",
            'fet_temperature': f"{fet_temperature:.1f}",
            'battery_address': battery_address
        }
    return None

def parse_62n_message(data, battery_address=1):
    """解析0x62n报文 - 电芯电压1-4"""
    if len(data) >= 8:
        return {
            'cell_voltage_1': f"{(data[1] << 8 | data[0]) * 0.001:.3f}",
            'cell_voltage_2': f"{(data[3] << 8 | data[2]) * 0.001:.3f}",
            'cell_voltage_3': f"{(data[5] << 8 | data[4]) * 0.001:.3f}",
            'cell_voltage_4': f"{(data[7] << 8 | data[6]) * 0.001:.3f}",
            'battery_address': battery_address
        }
    return None

def parse_63n_message(data, battery_address=1):
    """解析0x63n报文 - 电芯电压5-8"""
    if len(data) >= 8:
        return {
            'cell_voltage_5': f"{(data[1] << 8 | data[0]) * 0.001:.3f}",
            'cell_voltage_6': f"{(data[3] << 8 | data[2]) * 0.001:.3f}",
            'cell_voltage_7': f"{(data[5] << 8 | data[4]) * 0.001:.3f}",
            'cell_voltage_8': f"{(data[7] << 8 | data[6]) * 0.001:.3f}",
            'battery_address': battery_address
        }
    return None

def parse_64n_message(data, battery_address=1):
    """解析0x64n报文 - 电芯电压9-12"""
    if len(data) >= 8:
        return {
            'cell_voltage_9': f"{(data[1] << 8 | data[0]) * 0.001:.3f}",
            'cell_voltage_10': f"{(data[3] << 8 | data[2]) * 0.001:.3f}",
            'cell_voltage_11': f"{(data[5] << 8 | data[4]) * 0.001:.3f}",
            'cell_voltage_12': f"{(data[7] << 8 | data[6]) * 0.001:.3f}",
            'battery_address': battery_address
        }
    return None 

def parse_65n_message(data, battery_address=1):
    """解析0x65n报文 - 电芯电压13-16"""
    if len(data) >= 8:
        return {
            'cell_voltage_13': f"{(data[1] << 8 | data[0]) * 0.001:.3f}",
            'cell_voltage_14': f"{(data[3] << 8 | data[2]) * 0.001:.3f}",
            'cell_voltage_15': f"{(data[5] << 8 | data[4]) * 0.001:.3f}",
            'cell_voltage_16': f"{(data[7] << 8 | data[6]) * 0.001:.3f}",
            'battery_address': battery_address
        }
    return None

def parse_66n_message(data, battery_address=1):
    """解析0x66n报文 - 电芯温度1-4"""
    if len(data) >= 8:
        cell_temperature_1 = round(signed_16bit(data[1], data[0]) * 0.1, 1)
        cell_temperature_2 = round(signed_16bit(data[3], data[2]) * 0.1, 1)
        cell_temperature_3 = round(signed_16bit(data[5], data[4]) * 0.1, 1)
        cell_temperature_4 = round(signed_16bit(data[7], data[6]) * 0.1, 1)
        return {
            'cell_temperature_1': f"{cell_temperature_1:.1f}",
            'cell_temperature_2': f"{cell_temperature_2:.1f}",
            'cell_temperature_3': f"{cell_temperature_3:.1f}",
            'cell_temperature_4': f"{cell_temperature_4:.1f}",
            'battery_address': battery_address
        }
    return None
def parse_67n_message(data, battery_address=1):
    """解析0x60n报文 - On configuration from site controller"""
    if len(data) >= 8:
        Arm_Antitheft_mode = data[0] & 0x01
        external_output = data[1]
        
        return {
            'Arm_Antitheft_mode': Arm_Antitheft_mode,
            'external_output': external_output,
            'battery_address': battery_address
        }
    return None

def parse_40n_message(data, battery_address=1):
    """解析0x40n报文 - 系统温度"""
    if len(data) >= 8:
        dcdc_temperature_deci_celsius = round(signed_16bit(data[1], data[0]) * 0.1, 1)
        pos_terminal_temp_deci_celsius = round(signed_16bit(data[3], data[2]) * 0.1, 1)
        neg_terminal_temp_deci_celsius = round(signed_16bit(data[5], data[4]) * 0.1, 1)
        return {
            'dcdc_temperature_deci_celsius': f"{dcdc_temperature_deci_celsius:.1f}",
            'pos_terminal_temp_deci_celsius': f"{pos_terminal_temp_deci_celsius:.1f}",
            'neg_terminal_temp_deci_celsius': f"{neg_terminal_temp_deci_celsius:.1f}",
            'battery_address': battery_address
        }
    return None

def parse_41n_message(data, battery_address=1):
    """解析0x41n报文 - 内部温度"""
    if len(data) >= 8:
        neg_bat_temp_1_deci_celsius = round(signed_16bit(data[1], data[0]) * 0.1, 1)
        neg_bat_temp_2_deci_celsius = round(signed_16bit(data[3], data[2]) * 0.1, 1)
        pos_bat_temp_cb_deci_celsius = round(signed_16bit(data[5], data[4]) * 0.1, 1)
        return {
            'neg_bat_temp_1_deci_celsius': f"{neg_bat_temp_1_deci_celsius:.1f}",
            'neg_bat_temp_2_deci_celsius': f"{neg_bat_temp_2_deci_celsius:.1f}",
            'pos_bat_temp_cb_deci_celsius': f"{pos_bat_temp_cb_deci_celsius:.1f}",
            'battery_address': battery_address
        }
    return None

def parse_42n_message(data, battery_address=1):
    """解析0x42n报文 - 健康状态和循环次数"""
    if len(data) >= 8:
        return {
            'state_of_health': f"{data[0] * 0.5:.1f}",
            'cycle_count': unsigned_16bit(data[2], data[1]),
            'lifetime_hour': unsigned_24bit(data[5], data[4], data[3]),
            'cell_balance_state': unsigned_16bit(data[7], data[6]),
            'battery_address': battery_address
        }
    return None

def parse_43n_message(data, battery_address=1):
    """解析0x43n报文 - MCU状态"""
    if len(data) >= 8:
        mcu_uptime_seconds = unsigned_32bit(data[3], data[2], data[1], data[0])
        mcu_temperature_deci_celsius = round(signed_16bit(data[5], data[4]) * 0.1, 1)
        afe_temperature_deci_celsius = round(signed_16bit(data[7], data[6]) * 0.1, 1)
        return {
            'mcu_uptime_seconds': f"{mcu_uptime_seconds:.1f}",
            'mcu_temperature_deci_celsius': f"{mcu_temperature_deci_celsius:.1f}",
            'afe_temperature_deci_celsius': f"{afe_temperature_deci_celsius:.1f}",
            'battery_address': battery_address
        }
    return None

def parse_44n_message(data, battery_address=1):
    """解析0x44n报文 - ESP32状态"""
    if len(data) >= 8:

        return {
            'esp32_uptime_seconds': unsigned_32bit(data[3], data[2], data[1], data[0]),
            'esp32_free_heap_size_byte': unsigned_24bit(data[6], data[5], data[4]),
            'esp32_temperature_celsius': data[7] if data[7] < 128 else data[7] - 256,  # signed int8
            'battery_address': battery_address
        }
    return None

def parse_45n_message(data, battery_address=1):
    """解析0x45n报文 - 控制器版本前8字符"""
    if len(data) >= 8:
        #controller_version = ''.join(['%02x' % b for b in data if b != 0])
        controller_version = ''.join([chr(b) for b in data if b != 0])
        return {
            'controller_version_part1': controller_version,
            'battery_address': battery_address
        }
    return None

def parse_46n_message(data, battery_address=1):
    """解析0x46n报文 - 控制器版本后8字符"""
    if len(data) >= 8:
        #controller_version = ''.join(['%02x' % b for b in data if b != 0])
        controller_version = ''.join([chr(b) for b in data if b != 0])
        return {
            'controller_version_part2': controller_version,
            'battery_address': battery_address
        }
    return None

def parse_47n_message(data, battery_address=1):
    """解析0x47n报文 - BMS版本前8字符"""
    if len(data) >= 8:
        #bms_version = ''.join(['%02x' % b for b in data if b != 0])
        bms_version = ''.join([chr(b) for b in data if b != 0])
        return {
            'bms_version_part1': bms_version,
            'battery_address': battery_address
        }
    return None

def parse_48n_message(data, battery_address=1):
    """解析0x48n报文 - BMS版本后8字符"""
    if len(data) >= 8:
        #bms_version = ''.join(['%02x' % b for b in data if b != 0])
        bms_version = ''.join([chr(b) for b in data if b != 0])
        return {
            'bms_version_part2': bms_version,
            'battery_address': battery_address
        }
    return None

def parse_49n_message(data, battery_address=1):
    """解析0x49n报文 - 加速度计"""
    if len(data) >= 8:
        return {
            'accelerometer_x': signed_16bit(data[1], data[0]),
            'accelerometer_y': signed_16bit(data[3], data[2]),
            'accelerometer_z': signed_16bit(data[5], data[4]),
            'battery_address': battery_address
        }
    return None

def parse_4An_message(data, battery_address=1):
    """解析0x4An报文 - MAC地址和模块ID"""
    if len(data) >= 8:
        mac_address = ':'.join(['%02x' % b for b in data[:6]])
        return {
            'esp32_mac_address': mac_address,
            'module_id': data[6],
            'max_charge_current': data[7],
            'battery_address': battery_address
        }
    return None
def parse_4Bn_message(data, battery_address=1):
    """解析0x4Bn报文 - BMS序列号前8字符"""
    if len(data) >= 8:
        battery_serial = ''.join([chr(b) for b in data if b != 0])
        return {
            'battery_serial_part1': battery_serial,
            'battery_address': battery_address
        }
    return None

def parse_4Cn_message(data, battery_address=1):
    """解析0x4Cn报文 - BMS序列号8~16字符"""
    if len(data) >= 8:
        battery_serial = ''.join([chr(b) for b in data if b != 0])
        return {
            'battery_serial_part2': battery_serial,
            'battery_address': battery_address
        }
    return None
def parse_4Dn_message(data, battery_address=1):
    """解析0x4Dn报文 - BMS序列号last 4 chars"""
    if len(data) >= 8:
        #battery_serial = ''.join([chr(b) for b in data if b != 0])
        battery_serial = ''.join(chr(b) for b in data[:4] if b != 0)
        return {
            'battery_serial_part3': battery_serial,
            'battery_address': battery_address
        }
    return None
def get_battery_address_from_can_id(can_id):
    """从CAN ID中提取电池地址"""
    # 对于0x60n格式的ID，n就是电池地址
    if 0x600 <= can_id <= 0x6FF:
        return can_id & 0x0F
    elif 0x400 <= can_id <= 0x4FF:
        return can_id & 0x0F
    return 1  # 默认地址

def parse_can_message(can_id, data):
    """通用CAN报文解析函数"""
    if can_id == 0x351:
        return parse_351_message(data)
    elif can_id == 0x355:
        return parse_355_message(data)
    elif can_id == 0x356:
        return parse_356_message(data)
    elif can_id == 0x35A:
        return parse_35A_message(data)
    # elif can_id == 0x35E:
    #     return parse_35E_message(data)
    # elif can_id == 0x35F:
    #     return parse_35F_message(data)
    # 新增的报文解析
    battery_address = get_battery_address_from_can_id(can_id)
    
    # 0x60n系列
    if (can_id & 0xFF0) == 0x600:
        return parse_60n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x610:
        return parse_61n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x620:
        return parse_62n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x630:
        return parse_63n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x640:
        return parse_64n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x650:
        return parse_65n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x660:
        return parse_66n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x670:
        return parse_67n_message(data, battery_address)
    
    # 0x40n系列
    elif (can_id & 0xFF0) == 0x400:
        return parse_40n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x410:
        return parse_41n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x420:
        return parse_42n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x430:
        return parse_43n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x440:
        return parse_44n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x450:
        return parse_45n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x460:
        return parse_46n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x470:
        return parse_47n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x480:
        return parse_48n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x490:
        return parse_49n_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x4A0:
        return parse_4An_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x4B0:
        return parse_4Bn_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x4C0:
        return parse_4Cn_message(data, battery_address)
    elif (can_id & 0xFF0) == 0x4D0:
        return parse_4Dn_message(data, battery_address)
    else:
        return None