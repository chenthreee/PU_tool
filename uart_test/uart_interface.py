import serial
import serial.tools.list_ports

class UARTInterface:
    def __init__(self):
        self.ser = None

    def open(self, port, baudrate=115200, bytesize=8, stopbits=1, parity='N', timeout=1):
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            stopbits=stopbits,
            parity=parity,
            timeout=timeout
        )

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

    def write(self, data):
        if self.ser and self.ser.is_open:
            return self.ser.write(data)
        else:
            raise serial.SerialException("Serial port not open")

    def read(self, size=1):
        if self.ser and self.ser.is_open:
            return self.ser.read(size)
        else:
            raise serial.SerialException("Serial port not open")

    def is_open(self):
        return self.ser is not None and self.ser.is_open

    def in_waiting(self):
        if self.ser and self.ser.is_open:
            return self.ser.in_waiting
        return 0

    @staticmethod
    def list_ports():
        return [port.device for port in serial.tools.list_ports.comports()] 