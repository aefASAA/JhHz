#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JhHz功能测试脚本
用于测试新添加的包大小和安装位置功能
"""

import subprocess
import sys
import json
from pathlib import Path

def test_pip_list():
    """测试pip list命令"""
    print("测试pip list命令...")
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], 
                              capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            print(f"✓ 成功获取 {len(packages)} 个包的信息")
            return True
        else:
            print(f"✗ pip list失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 测试异常: {str(e)}")
        return False

def test_pip_show():
    """测试pip show命令"""
    print("\n测试pip show命令...")
    try:
        # 测试一个常见的包
        result = subprocess.run([sys.executable, "-m", "pip", "show", "pip"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ pip show命令正常")
            print("示例输出:")
            print(result.stdout[:200] + "..." if len(result.stdout) > 200 else result.stdout)
            return True
        else:
            print(f"✗ pip show失败: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ 测试异常: {str(e)}")
        return False

def test_package_size_calculation():
    """测试包大小计算功能"""
    print("\n测试包大小计算...")
    try:
        # 获取pip的安装位置
        result = subprocess.run([sys.executable, "-m", "pip", "show", "pip"], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            location = None
            for line in lines:
                if line.startswith('Location:'):
                    location = line.split(':', 1)[1].strip()
                    break
            
            if location and Path(location).exists():
                # 计算目录大小
                total_size = 0
                file_count = 0
                for file_path in Path(location).rglob('*'):
                    if file_path.is_file():
                        total_size += file_path.stat().st_size
                        file_count += 1
                
                print(f"✓ 成功计算pip包大小: {format_size(total_size)} ({file_count} 个文件)")
                return True
            else:
                print("✗ 无法获取pip安装位置")
                return False
        else:
            print("✗ 无法获取pip信息")
            return False
    except Exception as e:
        print(f"✗ 计算大小异常: {str(e)}")
        return False

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def main():
    """主测试函数"""
    print("=" * 50)
    print("JhHz功能测试")
    print("=" * 50)
    
    tests = [
        ("pip list命令", test_pip_list),
        ("pip show命令", test_pip_show),
        ("包大小计算", test_package_size_calculation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"✗ {test_name} 测试失败")
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！新功能应该可以正常工作。")
    else:
        print("✗ 部分测试失败，请检查环境配置。")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 