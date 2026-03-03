# test.py (Big-Endian version, with 0x45n/46n/47n/48n version frames)
import threading
import time
import random
from datetime import datetime
import tkinter as tk

from can_host_computer import CANHostComputer
from can_protocol_config import parse_can_message  # 仅确保依赖就绪

class FakeCANBus:
    """
    伪 CAN 总线（大端序）：
    - open/close
    - send(id,data)
    - receive(timeout) -> 一批报文
    """
    def __init__(self):
        self._connected = False
        self._last_emit = 0.0
        self._battery_addr = 1
        self._hb_period = 0.1
        self._rng = random.Random(2025)

        # 基础运行状态
        self._soc = 80
        self._soh = 95
        self._voltage = 51.25
        self._current = -1.2
        self._temp = 25.0
        self._warn_toggle = False

        # 版本字符串（≥16字节更直观）
        self._controller_version = "CTRL_FW_1.23_2025"
        self._bms_version        = "BMS_FW_0.90_2025"

        # 电芯：示例 28 节（避开 0x450/0x460/0x470/0x480）
        num_cells = 28
        base_mv = 3600
        self._cells_mv = [base_mv + self._rng.randint(-5, 5) for _ in range(num_cells)]

    # ---- 连接接口 ----
    def open(self, *a, **kw):
        self._connected = True
        return True

    def close(self):
        self._connected = False
        return True

    @property
    def is_connected(self):
        return self._connected

    def send(self, msg_id, data):
        print(f"[FakeCANBus] TX id=0x{msg_id:03X} data={bytes(data).hex(' ')}")
        return True

    # ---- 大端编码工具 ----
    @staticmethod
    def _u16_be(val):
        v = int(val) & 0xFFFF
        return bytes([(v >> 8) & 0xFF, v & 0xFF])

    @staticmethod
    def _s16_be(val):
        x = int(val)
        if x < 0:
            x = (x + 0x10000) & 0xFFFF
        return bytes([(x >> 8) & 0xFF, x & 0xFF])

    @staticmethod
    def _u24_be(val):
        v = int(val) & 0xFFFFFF
        return bytes([(v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF])

    @staticmethod
    def _u32_be(val):
        v = int(val) & 0xFFFFFFFF
        return bytes([(v >> 24) & 0xFF, (v >> 16) & 0xFF, (v >> 8) & 0xFF, v & 0xFF])

    @staticmethod
    def _u8_be(val):
        v = int(val) & 0xFF
        return bytes([v])

    def _mk_msg(self, can_id, payload8):
        return {'id': can_id, 'data': bytes(payload8), 'length': len(payload8), 'timestamp': time.time()}

    # ---- 基本帧 ----
    def _frame_351(self):
        charge_v_lim = int(56.0 * 10)
        max_chg_cur  = int(12.3 * 10)
        max_dch_cur  = int(18.7 * 10)
        dsg_v        = int(44.0 * 10)
        data = (
            self._u16_be(charge_v_lim) +
            self._u16_be(max_chg_cur)  +
            self._u16_be(max_dch_cur)  +
            self._u16_be(dsg_v)
        )
        return self._mk_msg(0x351, data)

    def _frame_355(self):
        self._soc = max(0, min(100, self._soc + self._rng.randint(-1, 1)))
        soh = self._soh
        hisoc = int(self._soc * 100)  # 0.01%
        data = self._u16_be(self._soc) + self._u16_be(soh) + self._u16_be(hisoc)
        return self._mk_msg(0x355, data)

    def _frame_356(self):
        self._voltage += self._rng.uniform(-0.03, 0.03)
        self._current += self._rng.uniform(-0.2, 0.2)
        self._temp    += self._rng.uniform(-0.05, 0.05)
        u  = int(self._voltage * 100)    # 0.01V
        i  = int(self._current * 10)     # 0.1A
        t  = int(self._temp * 10)        # 0.1°C
        data = self._s16_be(u) + self._s16_be(i) + self._s16_be(t) + b'\x00\x00'
        return self._mk_msg(0x356, data)

    def _frame_35A(self):
        self._warn_toggle = not self._warn_toggle
        alarms = 0x00000
        if self._warn_toggle:
            alarms |= (0x20000 | 0x40000)  # COV | OCC 示例
        data = b'\x00\x00\x00\x00' + self._u32_be(alarms)
        return self._mk_msg(0x35A, data)

    # ---- 0x20n/0x21n ----
    def _frame_20n(self):
        op_mode = 0x02 if self._rng.random() < 0.5 else 0x03
        soc05   = int(self._soc * 2)  # 0.5%
        status  = 0x0001
        alarms  = 0
        data = bytes([op_mode, soc05]) + self._u16_be(status) + self._u32_be(alarms)
        can_id = 0x200 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_21n(self):
        i = int(self._current * 10)         # 0.1A
        v = int(self._voltage * 1000)       # mV
        rail = int(51.0 * 1000)             # mV
        fet = int((self._temp + 5.0) * 10)  # 0.1°C
        data = self._s16_be(i) + self._u16_be(v) + self._u16_be(rail) + self._s16_be(fet)
        can_id = 0x210 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    # ---- 0x22n ~ 0x26n 示例 ----
    def _frame_22n(self):
        for i in range(len(self._cells_mv)):
            self._cells_mv[i] += self._rng.randint(-1, 1)
        avg = int(sum(self._cells_mv) / len(self._cells_mv))
        delta = max(self._cells_mv) - min(self._cells_mv)
        cnt = len(self._cells_mv)
        data = self._u16_be(avg) + self._u16_be(cnt) + self._u16_be(delta) + b'\x00\x00'
        can_id = 0x220 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_23n(self):
        mn = min(self._cells_mv); mn_i = self._cells_mv.index(mn)
        mx = max(self._cells_mv); mx_i = self._cells_mv.index(mx)
        data = self._u16_be(mn) + self._u16_be(mn_i) + self._u16_be(mx) + self._u16_be(mx_i)
        can_id = 0x230 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_24n(self):
        cycles = 200 + self._rng.randint(-1, 1)
        soh = self._soh
        data = self._u16_be(soh) + self._u16_be(cycles) + b'\x00\x00' + b'\x00\x00'
        can_id = 0x240 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_25n(self):
        temps = [int((self._temp + self._rng.uniform(-2, 2)) * 10) for _ in range(6)]
        mn = min(temps); mn_i = temps.index(mn)
        mx = max(temps); mx_i = temps.index(mx)
        data = self._s16_be(mn) + self._u16_be(mn_i) + self._s16_be(mx) + self._u16_be(mx_i)
        can_id = 0x250 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_26n(self):
        balance_bits = self._rng.getrandbits(16)
        active_cnt = self._rng.randint(0, 10)
        data = self._u32_be(balance_bits) + self._u16_be(active_cnt) + b'\x00\x00'
        can_id = 0x260 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    def _frame_27n(self):
        Arm_Antitheft_mode = self._rng.randint(0, 1)
        external_output = self._rng.randint(0, 2)
        data = bytes([Arm_Antitheft_mode, external_output]) + b'\x00\x00\x00\x00\x00\x00'
        can_id = 0x270 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)
    # ---- 版本帧：0x45n/0x46n/0x47n/0x48n ----
    @staticmethod
    def _split16_ascii(s: str):
        b = s.encode('ascii', errors='ignore')[:16].ljust(16, b'\x00')
        return b[:8], b[8:]

    def _frame_45n(self):
        """controller_version 前8字节"""
        first8, _ = self._split16_ascii(self._controller_version)
        can_id = 0x450 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, first8)

    def _frame_46n(self):
        """controller_version 后8字节"""
        _, last8 = self._split16_ascii(self._controller_version)
        can_id = 0x460 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, last8)

    def _frame_47n(self):
        """bms_version 前8字节"""
        first8, _ = self._split16_ascii(self._bms_version)
        can_id = 0x470 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, first8)

    def _frame_48n(self):
        """bms_version 后8字节"""
        _, last8 = self._split16_ascii(self._bms_version)
        can_id = 0x480 | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, last8)

    # ---- 电芯电压分组（跳过 0x450/0x460/0x470/0x480）----
    def _cells_base_ids(self):
        # 仅用 0x400/0x410/0x420/0x430/0x440/0x490/0x4A0 -> 7组*4=28节
        return [0x400, 0x410, 0x420, 0x430, 0x440, 0x490, 0x4A0]

    def _frame_cells_group(self, group_index):
        base_id = self._cells_base_ids()[group_index]
        start = group_index * 4
        parts = []
        for k in range(4):
            idx = start + k
            mv = self._cells_mv[idx] if idx < len(self._cells_mv) else 0
            parts.append(self._u16_be(mv))
        data = b''.join(parts)
        can_id = base_id | (self._battery_addr & 0x0F)
        return self._mk_msg(can_id, data)

    # ---- 接收 ----
    def receive(self, timeout=50):
        if not self._connected:
            return []

        now = time.time()
        msgs = []

        if (now - self._last_emit) >= self._hb_period:
            self._last_emit = now

            # 轮换电池地址 1..4
            self._battery_addr += 1
            if self._battery_addr > 4:
                self._battery_addr = 1

            # 常规帧
            msgs += [
                self._frame_351(),
                self._frame_355(),
                self._frame_356(),
                self._frame_35A(),
                self._frame_20n(),
                self._frame_21n(),
                self._frame_22n(),
                self._frame_23n(),
                self._frame_24n(),
                self._frame_25n(),
                self._frame_26n(),
                self._frame_27n(),
            ]

            # 版本帧（45n/46n/47n/48n）
            msgs += [
                self._frame_45n(),
                self._frame_46n(),
                self._frame_47n(),
                self._frame_48n(),
            ]

            # 电芯分组帧（排除 0x450~0x480）
            base_ids = self._cells_base_ids()
            for gi in range(len(base_ids)):
                msgs.append(self._frame_cells_group(gi))

        # 偶尔空读
        if not msgs and random.random() < 0.7:
            return []

        return msgs


def main():
    root = tk.Tk()
    app = CANHostComputer(root)

    fake = FakeCANBus()
    fake.open()
    app.can_bus = fake
    app.is_connected = True
    app.log_message("[Test] FakeCANBus(大端) 已启用；含 0x45n/46n/47n/48n 版本帧，电芯分组避开冲突")

    app.is_receiving = True
    th = threading.Thread(target=app.monitor_heartbeat, daemon=True)
    th.start()

    root.mainloop()

    app.is_receiving = False
    fake.close()


if __name__ == "__main__":
    main()
