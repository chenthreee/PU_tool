#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试27n报文解析功能
"""

from can_protocol_config import parse_27n_message, parse_can_message

def test_27n_parsing():
    """测试27n报文解析"""
    print("测试27n报文解析功能...")
    
    # 测试数据：Arm_Antitheft_mode=1, external_output=2
    test_data = [1, 2, 0, 0, 0, 0, 0, 0]
    
    # 测试parse_27n_message函数
    result = parse_27n_message(test_data, battery_address=1)
    print(f"parse_27n_message结果: {result}")
    
    # 测试parse_can_message函数
    can_id = 0x271  # 电池地址1
    result2 = parse_can_message(can_id, test_data)
    print(f"parse_can_message结果: {result2}")
    
    # 验证结果
    if result and result2:
        print("✓ 27n报文解析成功!")
        print(f"  - ARM防盗模式: {result['Arm_Antitheft_mode']} ({'Armed' if result['Arm_Antitheft_mode'] else 'Disarmed'})")
        print(f"  - 外部输出: {result['external_output']} ({'Unused' if result['external_output'] == 0 else 'Heater' if result['external_output'] == 1 else 'Solenoid'})")
        print(f"  - 电池地址: {result['battery_address']}")
    else:
        print("✗ 27n报文解析失败!")

if __name__ == "__main__":
    test_27n_parsing()
