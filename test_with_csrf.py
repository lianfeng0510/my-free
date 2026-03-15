#!/usr/bin/env python
"""
测试脚本 - 处理CSRF令牌
"""

import requests
import re
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def extract_csrf_token(html_content):
    """从HTML中提取CSRF令牌"""
    # 查找 <input type="hidden" name="csrf_token" value="...">
    pattern = r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"'
    match = re.search(pattern, html_content)
    if match:
        return match.group(1)
    
    # 查找 {{ csrf_token() }} 可能已经被渲染
    # 如果找不到，返回None
    return None

def test_login_with_csrf():
    """测试带CSRF令牌的登录"""
    print("测试带CSRF令牌的登录...")
    
    # 1. 获取登录页面
    login_url = urljoin(BASE_URL, "/login")
    response = SESSION.get(login_url)
    
    if response.status_code != 200:
        print(f"  获取登录页面失败: {response.status_code}")
        return False
    
    # 2. 提取CSRF令牌
    html = response.text
    csrf_token = extract_csrf_token(html)
    
    if not csrf_token:
        print("  无法提取CSRF令牌")
        # 尝试查找其他形式的CSRF令牌
        print(f"  页面片段: {html[:500]}")
        return False
    
    print(f"  提取到CSRF令牌: {csrf_token[:20]}...")
    
    # 3. 准备登录数据
    login_data = {
        'username': 'Socrates',
        'password': 'Jiang0531',
        'remember': 'on',
        'csrf_token': csrf_token
    }
    
    # 4. 提交登录表单
    response = SESSION.post(login_url, data=login_data, allow_redirects=False)
    
    print(f"  登录响应状态码: {response.status_code}")
    
    if response.status_code == 302:
        location = response.headers.get('Location', '')
        print(f"  登录成功，重定向到: {location}")
        
        # 访问重定向页面验证登录状态
        if location:
            redirect_url = urljoin(BASE_URL, location)
            response = SESSION.get(redirect_url)
            if response.status_code == 200:
                print("  登录状态验证成功")
                return True
        return True
    else:
        print(f"  登录失败")
        print(f"  响应内容: {response.text[:500]}")
        return False

def test_access_protected_pages():
    """测试访问需要登录的页面"""
    print("\n测试访问需要登录的页面...")
    
    protected_pages = [
        ('/trade', '二手交易页面'),
        ('/services', '跑腿服务页面'),
        ('/messages', '消息页面'),
        ('/forum', '论坛页面'),
        ('/profile', '个人资料页面'),
    ]
    
    results = {}
    
    for url_path, page_name in protected_pages:
        url = urljoin(BASE_URL, url_path)
        response = SESSION.get(url)
        
        print(f"\n{page_name} ({url_path}):")
        print(f"  状态码: {response.status_code}")
        
        if response.status_code == 200:
            print("  ✅ 页面可访问")
            
            # 检查编码和乱码
            content = response.text
            if '锟斤拷' in content or '�' in content:
                print("  ⚠️  检测到乱码!")
            
            # 检查中文字符
            test_chars = ['校园', '贴吧', '二手', '跑腿', '消息', '论坛', '个人资料']
            found = [char for char in test_chars if char in content]
            if found:
                print(f"  ✅ 找到中文字符: {found[:3]}")
            else:
                print("  ⚠️  未找到中文字符")
            
            # 检查页面标题
            if '<title>' in content:
                start = content.find('<title>') + 7
                end = content.find('</title>', start)
                if end > start:
                    title = content[start:end]
                    print(f"  页面标题: {title}")
            
            results[page_name] = True
            
        elif response.status_code == 302:
            print("  ⚠️  未登录或会话过期，重定向到登录页")
            results[page_name] = False
        else:
            print(f"  ❌ 页面访问异常")
            results[page_name] = False
    
    return results

def main():
    """主测试函数"""
    print("=" * 60)
    print("CSRF令牌处理测试")
    print("=" * 60)
    
    # 测试登录
    login_success = test_login_with_csrf()
    
    if not login_success:
        print("\n❌ 登录失败，无法继续测试需要登录的页面")
        return
    
    # 测试需要登录的页面
    print("\n" + "=" * 60)
    print("测试需要登录的页面")
    print("=" * 60)
    
    results = test_access_protected_pages()
    
    # 生成报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results.values() if r)
    
    print(f"总测试页面: {total}")
    print(f"可访问页面: {passed}")
    print(f"不可访问页面: {total - passed}")
    
    print("\n详细结果:")
    for page_name, success in results.items():
        status = "✅ 可访问" if success else "❌ 不可访问"
        print(f"  {status} {page_name}")
    
    # 提供手动验证链接
    print("\n" + "=" * 60)
    print("手动验证链接（已登录状态）")
    print("=" * 60)
    print(f"二手交易: {BASE_URL}/trade")
    print(f"跑腿服务: {BASE_URL}/services")
    print(f"消息: {BASE_URL}/messages")
    print(f"论坛: {BASE_URL}/forum")
    print(f"个人资料: {BASE_URL}/profile")
    
    if passed == total:
        print("\n✅ 所有需要登录的页面均可正常访问")
    else:
        print("\n⚠️  部分页面访问异常，建议检查路由和权限设置")

if __name__ == "__main__":
    main()