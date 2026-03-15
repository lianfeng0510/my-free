#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试跑腿服务功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
from bs4 import BeautifulSoup

BASE_URL = "http://127.0.0.1:5000"

def test_page_access(url_path, expected_status=200):
    """测试页面访问"""
    try:
        response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
        if response.status_code == expected_status:
            print(f"✅ {url_path} - 状态码 {response.status_code}")
            # 检查是否有乱码
            if 'charset=utf-8' in response.headers.get('Content-Type', '').lower():
                print(f"   ✅ 编码正确 (UTF-8)")
            else:
                print(f"   ⚠️  编码可能有问题")
            return True
        else:
            print(f"❌ {url_path} - 状态码 {response.status_code} (期望 {expected_status})")
            return False
    except Exception as e:
        print(f"❌ {url_path} - 请求失败: {e}")
        return False

def test_runner_pages():
    """测试跑腿服务相关页面"""
    print("🔍 测试跑腿服务页面访问...")
    
    # 需要测试的页面
    pages_to_test = [
        # 跑腿订单列表（不同状态）
        ('/runner_orders/my_orders', 200, '我的发布'),
        ('/runner_orders/pending', 200, '待接单'),
        ('/runner_orders/available', 200, '可接订单'),
        ('/runner_orders/accepted', 200, '已接单'),
        ('/runner_orders/completed', 200, '已完成'),
        
        # 跑腿功能页面
        ('/create_runner_order', 200, '发布订单'),
        ('/runner_dashboard', 200, '跑腿员仪表盘'),
    ]
    
    success_count = 0
    total_count = len(pages_to_test)
    
    for url_path, expected_status, description in pages_to_test:
        if test_page_access(url_path, expected_status):
            success_count += 1
        print(f"   📋 {description}")
    
    print(f"\n📊 跑腿服务页面测试结果: {success_count}/{total_count}")
    return success_count == total_count

def test_order_detail_pages():
    """测试订单详情页面（使用示例订单ID）"""
    print("\n🔍 测试订单详情页面...")
    
    # 测试几个示例订单ID
    order_ids = [1, 2, 3]
    success_count = 0
    
    for order_id in order_ids:
        url_path = f"/runner_order_detail/{order_id}"
        if test_page_access(url_path, 200):
            success_count += 1
    
    print(f"\n📊 订单详情页面测试结果: {success_count}/{len(order_ids)}")
    return success_count > 0  # 至少有一个成功

def check_csrf_tokens():
    """检查页面中的CSRF令牌"""
    print("\n🔍 检查CSRF令牌...")
    
    pages_to_check = [
        '/create_runner_order',
        '/runner_order_detail/1',
    ]
    
    for url_path in pages_to_check:
        try:
            response = requests.get(f"{BASE_URL}{url_path}", timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                csrf_inputs = soup.find_all('input', {'name': 'csrf_token'})
                
                if csrf_inputs:
                    print(f"✅ {url_path} - 包含CSRF令牌 ({len(csrf_inputs)}个)")
                else:
                    print(f"⚠️  {url_path} - 未找到CSRF令牌")
            else:
                print(f"❌ {url_path} - 无法访问")
        except Exception as e:
            print(f"❌ {url_path} - 检查失败: {e}")
    
    return True

def main():
    print("🚀 开始跑腿服务功能测试")
    print("=" * 50)
    
    all_tests_passed = True
    
    # 测试页面访问
    if not test_runner_pages():
        all_tests_passed = False
    
    # 测试订单详情
    if not test_order_detail_pages():
        all_tests_passed = False
    
    # 检查CSRF令牌
    check_csrf_tokens()
    
    print("\n" + "=" * 50)
    if all_tests_passed:
        print("🎉 所有跑腿服务功能测试通过！")
    else:
        print("⚠️  部分测试未通过，请检查")
    
    # 提供用户使用建议
    print("\n📋 使用建议:")
    print("1. 访问 http://127.0.0.1:5000/create_runner_order 发布跑腿订单")
    print("2. 访问 http://127.0.0.1:5000/runner_orders/available 查看可接订单")
    print("3. 访问 http://127.0.0.1:5000/runner_dashboard 查看跑腿员统计")
    print("4. 点击订单查看详情，进行接单、配送、完成等操作")

if __name__ == "__main__":
    main()