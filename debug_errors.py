#!/usr/bin/env python
"""
调试错误页面
"""

import requests
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def test_page_with_error(url_path, page_name):
    """测试页面并捕获错误"""
    print(f"\n测试 {page_name} ({url_path}):")
    
    # 先登录
    login_url = urljoin(BASE_URL, "/login")
    response = SESSION.get(login_url)
    
    # 提取CSRF令牌
    import re
    csrf_token = None
    if response.status_code == 200:
        match = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', response.text)
        if match:
            csrf_token = match.group(1)
    
    if csrf_token:
        # 使用管理员账号登录
        login_data = {
            'username': 'Socrates',
            'password': 'Jiang0531',
            'remember': 'on',
            'csrf_token': csrf_token
        }
        
        response = SESSION.post(login_url, data=login_data, allow_redirects=False)
        if response.status_code != 302:
            print(f"  登录失败: {response.status_code}")
            return
    
    # 测试目标页面
    target_url = urljoin(BASE_URL, url_path)
    response = SESSION.get(target_url)
    
    print(f"  状态码: {response.status_code}")
    
    if response.status_code == 500:
        print("  ⚠️  500内部服务器错误")
        print(f"  响应内容前1000字符:")
        print(response.text[:1000])
        
        # 检查常见错误模式
        content = response.text
        if 'jinja2.exceptions.UndefinedError' in content:
            print("  ❌ Jinja2未定义错误 - 模板引用了不存在的变量")
            # 查找具体是哪个变量
            import re
            match = re.search(r"'([^']+)' is undefined", content)
            if match:
                print(f"    未定义变量: {match.group(1)}")
        elif 'AttributeError' in content:
            print("  ❌ 属性错误 - 对象缺少属性")
        elif 'sqlalchemy' in content.lower():
            print("  ❌ 数据库错误")
    else:
        print(f"  响应内容片段: {response.text[:500]}")

def main():
    """主函数"""
    print("=" * 60)
    print("调试错误页面")
    print("=" * 60)
    
    # 测试有问题的页面
    test_page_with_error('/trade', '二手交易页面')
    test_page_with_error('/profile', '个人资料页面')
    
    print("\n" + "=" * 60)
    print("调试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()