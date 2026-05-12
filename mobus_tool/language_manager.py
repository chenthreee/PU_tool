#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语言管理器 - 支持中英文切换
"""

class LanguageManager:
    """语言管理器"""
    
    def __init__(self):
        self.current_language = 'zh'  # 默认中文
        self.languages = self.get_default_languages()
    
    def get_default_languages(self):
        """获取默认语言配置"""
        return {
            "zh": {
                "window_title": "SunSpec Modbus协议上位机",
                "connection_settings": "连接设置",
                "rtu_connection": "RTU连接:",
                "refresh": "刷新",
                "baud_rate": "波特率:",
                "slave_id": "电池ID:",
                "timeout_seconds": "超时(秒):",
                "connect_rtu": "连接RTU",
                "disconnect": "断开",
                "scan_base_address": "扫描SunSpec基地址",
                "current_base_address": "当前基地址:",
                "not_scanned": "未扫描",
                "scan_model_address": "扫描模型地址",
                "read_all_tables": "读取全部表格",
                "auto_read_all_tables": "自动读取全部表格",
                "interval_seconds": "间隔(秒):",
                "refresh_interval_seconds": "刷新间隔(秒):",
                "table": "表格",
                "addr":"地址",
                "read_all": "读全部",
                "field_name": "字段名",
                "value": "值",
                "update_time": "更新时间",
                "unit": "单位",
                "type": "类型",
                "description": "描述",
                "access_rights": "访问权限",
                "read": "读",
                "write_value": "写值",
                "write": "写",
                "write_status": "写状态",
                "log": "日志",
                "clear_log": "清空日志",
                "auto_save_log": "自动保存日志",
                "log_filter": "日志过滤",
                "log_file": "日志文件:",
                "select_file": "选择文件",
                "ready": "就绪",
                "warning": "警告",
                "please_connect_first": "请先连接Modbus设备",
                "please_scan_base_addr_first":"清先扫描基地址",
                "please_scan_model_addr_first":"请先扫描模型地址",
                "connection_success": "连接成功",
                "connection_failed": "连接失败",
                "disconnected": "已断开连接",
                "start_reading_all": "开始读取所有表格",
                "all_tables_read_complete": "所有表格读取完成",
                "start_scanning_base": "开始扫描SunSpec基地址",
                "found_sunspec_base": "发现SunSpec基地址",
                "not_found_sunspec_base": "未找到SunSpec基地址",
                "scan_success": "扫描成功",
                "scan_failed": "扫描失败",
                "start_scanning_models": "开始扫描模型",
                "scan_complete": "扫描完成",
                "success": "成功",
                "failed": "失败",
                "format_error": "格式错误",
                "no_file_selected": "未选择文件",
                "select_log_file": "选择日志文件",
                "model_id": "模型ID"
                
            },
            "en": {
                "window_title": "SunSpec Modbus Protocol Upper Computer",
                "connection_settings": "Connection Settings",
                "rtu_connection": "RTU Connection:",
                "refresh": "Refresh",
                "baud_rate": "Baud Rate:",
                "slave_id": "Battery ID:",
                "timeout_seconds": "Timeout(s):",
                "connect_rtu": "Connect RTU",
                "disconnect": "Disconnect",
                "scan_base_address": "Scan SunSpec Base Address",
                "current_base_address": "Current Base Address:",
                "not_scanned": "Not Scanned",
                "scan_model_address": "Scan Model Address",
                "read_all_tables": "Read All Tables",
                "auto_read_all_tables": "Auto Read All Tables",
                "interval_seconds": "Interval (s):",
                "refresh_interval_seconds": "Refresh Interval (s):",
                "table": "Table",
                "addr":"Address",
                "read_all": "Read All",
                "field_name": "Field Name",
                "value": "Value",
                "update_time": "Update Time",
                "unit": "Unit",
                "type": "Type",
                "description": "Description",
                "access_rights": "Access",
                "read": "Read",
                "write_value": "Write Value",
                "write": "Write",
                "write_status": "Write Status",
                "log": "Log",
                "clear_log": "Clear Log",
                "auto_save_log": "Auto Save Log",
                "log_filter": "Log Filter",
                "log_file": "Log File:",
                "select_file": "Select File",
                "ready": "Ready",
                "warning": "Warning",
                "please_connect_first": "Please connect to Modbus device first",
                "please_scan_base_addr_first":"Please scan base addr first",
                "please_scan_model_addr_first":"Please scan model addr first",
                "connection_success": "Connection Success",
                "connection_failed": "Connection Failed",
                "disconnected": "Disconnected",
                "start_reading_all": "Start reading all tables",
                "all_tables_read_complete": "All tables read complete",
                "start_scanning_base": "Start scanning SunSpec base address",
                "found_sunspec_base": "Found SunSpec base address",
                "not_found_sunspec_base": "Not found SunSpec base address",
                "scan_success": "Scan Success",
                "scan_failed": "Scan Failed",
                "start_scanning_models": "Start scanning models",
                "scan_complete": "Scan complete",
                "success": "Success",
                "failed": "Failed",
                "format_error": "Format Error",
                "no_file_selected": "No file selected",
                "select_log_file": "Select Log File",
                "model_id": "Model ID"
            }
        }
    
    def get_text(self, key, default=None):
        """获取文本"""
        if self.current_language in self.languages:
            return self.languages[self.current_language].get(key, default or key)
        return default or key
    
    def set_language(self, language):
        """设置语言"""
        if language in self.languages:
            self.current_language = language
            return True
        return False
    
    def get_current_language(self):
        """获取当前语言"""
        return self.current_language
    
    def get_available_languages(self):
        """获取可用语言列表"""
        return list(self.languages.keys()) 