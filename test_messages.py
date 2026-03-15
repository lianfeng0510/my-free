#!/usr/bin/env python
"""
测试消息页面功能
"""

import requests
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def test_homepage():
    """测试首页"""
    print("测试首页...")
    response = SESSION.get(urljoin(BASE_URL, "/"))
    print(f"  状态码: {response.status_code}")
    print(f"  标题包含 '校园贴吧': {'校园贴吧' in response.text}")
    return response.status_code == 200

def test_register():
    """测试注册功能"""
    print("测试注册...")
    # 先检查是否已登录
    response = SESSION.get(urljoin(BASE_URL, "/register"))
    if response.status_code == 200 and "注册" in response.text:
        print("  注册页面可访问")
    
    # 尝试注册测试用户
    register_data = {
        'username': 'testuser_messages',
        'email': 'test_messages@example.com',
        'password': 'Test123456',
        'confirm_password': 'Test123456'
    }
    
    response = SESSION.post(urljoin(BASE_URL, "/register"), data=register_data, allow_redirects=False)
    print(f"  注册响应状态码: {response.status_code}")
    
    if response.status_code == 302:  # 重定向表示成功
        print("  注册成功，重定向到登录页或首页")
        return True
    elif response.status_code == 200:
        # 可能用户已存在，尝试登录
        print("  用户可能已存在，尝试登录")
        return test_login()
    return False

def test_login():
    """测试登录功能"""
    print("测试登录...")
    login_data = {
        'username': 'testuser_messages',
        'password': 'Test123456'
    }
    
    response = SESSION.post(urljoin(BASE_URL, "/login"), data=login_data, allow_redirects=False)
    print(f"  登录响应状态码: {response.status_code}")
    
    if response.status_code == 302:
        print("  登录成功")
        return True
    return False

def test_messages_page():
    """测试消息页面"""
    print("测试消息页面...")
    response = SESSION.get(urljoin(BASE_URL, "/messages"))
    print(f"  状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("  消息页面加载成功")
        print(f"  页面包含 '私信': {'私信' in response.text}")
        print(f"  页面包含 '暂无私信': {'暂无私信' in response.text}")
        return True
    elif response.status_code == 302:
        print("  未登录，重定向到登录页")
        location = response.headers.get('Location', '')
        print(f"  重定向到: {location}")
        return False
    else:
        print(f"  错误状态码: {response.status_code}")
        print(f"  响应内容前500字符: {response.text[:500]}")
        return False

def test_conversation_page():
    """测试对话页面"""
    print("测试对话页面...")
    # 测试用户ID为1的对话页面
    response = SESSION.get(urljoin(BASE_URL, "/conversation/1"))
    print(f"  对话页面状态码: {response.status_code}")
    
    if response.status_code == 200:
        print("  对话页面加载成功")
        return True
    elif response.status_code == 302:
        print("  未登录，重定向到登录页")
        return False
    return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("消息页面功能测试")
    print("=" * 60)
    
    # 测试首页
    if not test_homepage():
        print("首页测试失败，可能服务器未启动")
        return
    
    # 测试消息页面（未登录状态）
    print("\n1. 未登录状态测试消息页面:")
    test_messages_page()
    
    # 尝试注册和登录
    print("\n2. 注册/登录测试:")
    if test_register() or test_login():
        print("登录成功，继续测试...")
        
        # 测试消息页面（已登录状态）
        print("\n3. 已登录状态测试消息页面:")
        if test_messages_page():
            print("✓ 消息页面可正常访问")
        else:
            print("✗ 消息页面访问失败")
        
        # 测试对话页面
        print("\n4. 测试对话页面:")
        test_conversation_page()
    else:
        print("✗ 注册/登录失败")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    
    # 提供手动测试建议
    print("\n手动测试建议:")
    print("1. 访问注册页面: http://127.0.0.1:5000/register")
    print("2. 注册一个新账号")
    print("3. 登录后访问消息页面: http://127.0.0.1:5000/messages")
    print("4. 测试对话页面: http://127.0.0.1:5000/conversation/1")

if __name__ == "__main__":
    main()