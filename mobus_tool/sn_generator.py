#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SN生成与验证模块

SN格式：[PU][CC][HW][L][YY][WW][R][NNNN]
  PU   (2) : 产品标识，固定 "PU"
  CC   (2) : HMAC-SHA-256 校验码，取摘要前2字节的大写十六进制
  HW   (2) : 硬件版本，零填充两位，如 "01"
  L    (1) : 产线标识，1-9 或 A-Z，每台机器独立配置
  YY   (2) : 当前年份后两位，如 "25"
  WW   (2) : 当前 ISO 周号，如 "03"
  R    (1) : 随机混淆字符，0-9 或 A-Z
  NNNN (4) : 自增流水号，如 "0001"
总长 = 2+2+2+1+2+2+1+4 = 16
"""

import os
import json
import hmac
import hashlib
import random
import datetime
import threading

# ─── 路径解析 ──────────────────────────────────────────────────────────────────

def _get_resource_dir():
    """返回资源文件所在目录（支持 PyInstaller 打包）"""
    import sys
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _config_path(filename):
    """返回 mobus_tool 目录下的配置文件路径（运行时写入目录，不是 MEIPASS）"""
    import sys
    if getattr(sys, 'frozen', False):
        # 打包后，可写的目录与 exe 同级
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, filename)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


# ─── 常量 ──────────────────────────────────────────────────────────────────────

_OBFUSCATION_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

SN_LENGTH = 16

# ─── 文件读取 ──────────────────────────────────────────────────────────────────

_lock = threading.Lock()


def _load_secret_key():
    """从 secret.key 加载 HMAC 密钥（hex 字符串 → bytes）"""
    key_path = os.path.join(_get_resource_dir(), 'secret.key')
    # 回退到可写目录
    if not os.path.exists(key_path):
        key_path = _config_path('secret.key')
    with open(key_path, 'r', encoding='ascii') as f:
        hex_str = f.read().strip()
    return bytes.fromhex(hex_str)


def _load_sn_config():
    """从 sn_config.json 加载配置"""
    cfg_path = os.path.join(_get_resource_dir(), 'sn_config.json')
    if not os.path.exists(cfg_path):
        cfg_path = _config_path('sn_config.json')
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    return cfg


def _load_counter():
    """读取当前流水号（线程安全）"""
    counter_path = _config_path('sn_counter.json')
    if not os.path.exists(counter_path):
        return 1
    with open(counter_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return int(data.get('counter', 1))


def _save_counter(value):
    """保存流水号（线程安全）"""
    counter_path = _config_path('sn_counter.json')
    with open(counter_path, 'w', encoding='utf-8') as f:
        json.dump({'counter': value}, f)


# ─── 核心算法 ──────────────────────────────────────────────────────────────────

def _compute_cc(body: str, key: bytes) -> str:
    """
    计算校验码 CC。
    body = PU + HW + L + YY + WW + R + NNNN (14字符)
    取 HMAC-SHA-256 摘要的前 1 字节，转大写十六进制 → 2字符
    """
    digest = hmac.new(key, body.encode('ascii'), hashlib.sha256).digest()
    return digest[:1].hex().upper()


def _build_body(pu: str, hw: str, l: str, yy: str, ww: str, r: str, nnnn: str) -> str:
    """拼接 SN 主体（不含 CC）"""
    return f"{pu}{hw}{l}{yy}{ww}{r}{nnnn}"


def _assemble_sn(pu: str, cc: str, hw: str, l: str, yy: str, ww: str, r: str, nnnn: str) -> str:
    """组装最终 SN"""
    return f"{pu}{cc}{hw}{l}{yy}{ww}{r}{nnnn}"


def _parse_sn(sn: str):
    """
    将 SN 字符串拆分为各字段，返回 dict；若长度不对则返回 None。
    """
    if len(sn) != SN_LENGTH:
        return None
    return {
        'PU':   sn[0:2],
        'CC':   sn[2:4],
        'HW':   sn[4:6],
        'L':    sn[6:7],
        'YY':   sn[7:9],
        'WW':   sn[9:11],
        'R':    sn[11:12],
        'NNNN': sn[12:16],
    }


# ─── 公共 API ──────────────────────────────────────────────────────────────────

def validate_sn(sn: str) -> bool:
    """
    验证 SN 是否合法：
      1. 长度必须为 16
      2. 前两字节必须为 "PU"
      3. 重新计算 CC 并与 SN 中的 CC 比对
    返回 True / False
    """
    fields = _parse_sn(sn)
    if not fields:
        return False
    if fields['PU'] != 'PU':
        return False

    try:
        key = _load_secret_key()
    except Exception:
        return False

    body = _build_body(
        fields['PU'], fields['HW'], fields['L'],
        fields['YY'], fields['WW'], fields['R'], fields['NNNN']
    )
    expected_cc = _compute_cc(body, key)
    return fields['CC'] == expected_cc


def generate_sn() -> str:
    """
    生成一个新的合法 SN，并递增流水号计数器。
    线程安全。
    """
    with _lock:
        cfg = _load_sn_config()
        key = _load_secret_key()

        pu = str(cfg.get('PU', 'PU'))[:2].upper()
        hw = str(cfg.get('HW', '01'))[:2].zfill(2).upper()
        l  = str(cfg.get('L',  '1'))[:1].upper()

        now = datetime.datetime.now()
        yy = now.strftime('%y')          # e.g. "25"
        ww = now.strftime('%W')          # ISO-like week 00-53; use %V for ISO
        r  = random.choice(_OBFUSCATION_CHARS)

        counter = _load_counter()
        nnnn = f"{counter:04d}"

        body = _build_body(pu, hw, l, yy, ww, r, nnnn)
        cc   = _compute_cc(body, key)
        sn   = _assemble_sn(pu, cc, hw, l, yy, ww, r, nnnn)

        # 保存递增后的计数
        _save_counter(counter + 1)

    return sn


def check_and_fix_sn(existing_sn: str):
    """
    检查已有 SN 是否合法：
      - 合法：返回 (True, existing_sn)，不做任何操作
      - 不合法/为空：生成新 SN，返回 (False, new_sn)
    """
    stripped = existing_sn.strip('\x00').strip()
    if stripped and validate_sn(stripped):
        return True, stripped
    new_sn = generate_sn()
    return False, new_sn
