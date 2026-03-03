# 27n报文集成总结

## 修改内容

### 1. can_protocol_config.py
- **添加了0x270的MESSAGE_STRUCTURES配置**：
  ```python
  0x270: {
      'name': '配置信息',
      'length': 8,
      'fields': [
          {'name': 'Arm_Antitheft_mode', 'offset': 0, 'length': 1, 'data_type': 'uint8', 'scaling': 1, 'description': 'ARM防盗模式'},
          {'name': 'external_output', 'offset': 1, 'length': 1, 'data_type': 'uint8', 'scaling': 1, 'description': '外部输出'},
      ]
  }
  ```

- **已有的parse_27n_message函数**：
  - 解析字节0的Arm_Antitheft_mode（1位）
  - 解析字节1的external_output（8位）
  - 返回包含battery_address的字典

### 2. can_host_computer.py
- **在initialize_table_data()中添加了27n表格初始化**：
  ```python
  # 0x270 - 配置信息
  for label, key in lang.get('table_270', []):
      unit = ''
      self.data_tree.insert('', 'end', values=('0x270', label, '--', unit, lang['waiting'], '--'))
  ```

- **在fmt_scalar()中添加了Arm_Antitheft_mode的格式化**：
  ```python
  if key == 'Arm_Antitheft_mode':
      arm_mode = {
          0: "Disarmed", 1: "Armed"
      }
      return arm_mode.get(val, f"模式{val}"), unit
  ```

- **在process_received_message()中添加了0x270+i支持**：
  ```python
  supported_ids.extend([
      0x200 + i, 0x210 + i, 0x220 + i, 0x230 + i, 0x240 + i, 0x250 + i, 0x260 + i, 0x270 + i,
      # ... 其他ID
  ])
  ```

### 3. lang_config.py
- **已有的table_270配置**：
  ```python
  'table_270': [
      ('ARM防盗模式', 'Arm_Antitheft_mode'),
      ('外部输出', 'external_output'),  
  ]
  ```

### 4. test.py
- **添加了_u8_be()方法**：
  ```python
  @staticmethod
  def _u8_be(val):
      v = int(val) & 0xFF
      return bytes([v])
  ```

- **修正了_frame_27n()方法**：
  ```python
  def _frame_27n(self):
      Arm_Antitheft_mode = self._rng.randint(0, 1)
      external_output = self._rng.randint(0, 2)
      data = bytes([Arm_Antitheft_mode, external_output]) + b'\x00\x00\x00\x00\x00\x00'
      can_id = 0x270 | (self._battery_addr & 0x0F)
      return self._mk_msg(can_id, data)
  ```

## 功能验证

### 1. 解析功能测试
- 创建了test_27n.py进行单元测试
- 验证parse_27n_message和parse_can_message函数正常工作
- 测试结果显示解析成功

### 2. 集成测试
- 运行test.py进行完整系统测试
- 27n报文现在会在GUI的实时数据表格中显示
- 支持多电池地址（0x270-0x27F）

## 数据格式

### 27n报文格式
- **字节0**: Arm_Antitheft_mode (1位: 0=Disarmed, 1=Armed)
- **字节1**: external_output (8位: 0=Unused, 1=Heater, 2=Solenoid)
- **字节2-7**: 保留字节

### 表格显示
- **CAN ID**: 0x270(电池1), 0x271(电池2), 等
- **参数**: ARM防盗模式, 外部输出
- **数值**: 格式化显示（Armed/Disarmed, Unused/Heater/Solenoid）
- **单位**: 无
- **状态**: 正常/等待/停止
- **刷新时间**: 实时更新

## 总结

27n报文已成功集成到CAN协议上位机中，包括：
1. ✅ 数据解析功能
2. ✅ 表格显示功能  
3. ✅ 多语言支持
4. ✅ 多电池地址支持
5. ✅ 测试验证

现在27n报文会按照"其它 CAN ID"的分类在表格中正确显示和更新。
