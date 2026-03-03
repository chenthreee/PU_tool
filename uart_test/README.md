# UART Test Tool

This tool is designed to test UART communication with the device by reading and writing registers defined in the system table.

## Requirements

- Python 3.6 or higher
- pyserial
- crcmod

## Installation

1. Install the required Python packages:
```bash
pip install -r requirements.txt
```

2. Make the script executable:
```bash
chmod +x test_uart.py
```

## Usage

1. Connect your device to the computer via USB-to-UART converter.

2. Update the serial port in the script if needed (default is "/dev/ttyUSB0"):
```python
tester = UARTTester(port="/dev/ttyUSB0", baudrate=115200)
```

3. Run the test script:
```bash
./test_uart.py
```

## Test Sequence

The script will:
1. Read all test registers (both readable and writable)
2. Write new values to writable registers
3. Read back the written values to verify

## Protocol Details

- Frame Header: 0x5A
- Read Command: 0x01
- Write Command: 0x02
- Response with Data: 0x81
- Response without Data: 0x82

Each command and response includes CRC16 (Modbus) for error checking.

## Example Output

```
Starting UART Test Sequence
==========================

Testing register: NUM_OF_CELLS
TX: 5A 01 00 02 10 00 XX XX
RX: 5A 81 00 06 10 00 00 00 00 10 XX XX

Testing write to register: NUM_OF_CELLS
TX: 5A 02 00 06 10 00 00 00 00 11 XX XX
RX: 5A 82 02 00 XX XX
```

Note: XX XX represents CRC bytes which vary based on the data. 