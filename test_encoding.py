#!/usr/bin/env python
"""
测试页面编码问题
"""

import requests
import chardet
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"

def test_page_encoding(url_path, page_name):
    """测试页面编码"""
    print(f"\n测试 {page_name} 页面编码 ({url_path}):")
    
    try:
        response = requests.get(urljoin(BASE_URL, url_path))
        print(f"  状态码: {response.status_code}")
        print(f"  响应头 Content-Type: {response.headers.get('Content-Type')}")
        
        # 检测实际编码
        encoding = chardet.detect(response.content)
        print(f"  检测到的编码: {encoding['encoding']} (置信度: {encoding['confidence']:.2f})")
        
        # 尝试用UTF-8解码
        try:
            content_utf8 = response.content.decode('utf-8')
            print(f"  UTF-8解码成功: 是")
            
            # 检查常见中文字符
            test_chars = ['校园', '贴吧', '登录', '注册', '消息', '私信']
            found_chars = []
            for char in test_chars:
                if char in content_utf8:
                    found_chars.append(char)
            
            print(f"  找到的中文字符: {found_chars if found_chars else '无'}")
            
            # 显示页面标题
            if '<title>' in content_utf8:
                start = content_utf8.find('<title>') + 7
                end = content_utf8.find('</title>', start)
                if end > start:
                    title = content_utf8[start:end]
                    print(f"  页面标题: {title}")
            
        except UnicodeDecodeError as e:
            print(f"  UTF-8解码失败: {e}")
            
            # 尝试用检测到的编码解码
            if encoding['encoding'] and encoding['confidence'] > 0.5:
                try:
                    content = response.content.decode(encoding['encoding'])
                    print(f"  使用 {encoding['encoding']} 解码成功")
                except Exception as e2:
                    print(f"  使用 {encoding['encoding']} 解码也失败: {e2}")
        
        # 检查是否有乱码特征（如锟斤拷）
        if response.content:
            content_str = str(response.content[:500])
            if '\\xef\\xbf\\xbd' in content_str or '锟斤拷' in content_str:
                print(f"  ⚠️ 检测到乱码特征!")
                # 显示乱码部分
                print(f"  前200字节: {response.content[:200]}")
        
    except Exception as e:
        print(f"  请求失败: {e}")

def main():
    """主测试函数"""
    print("=" * 60)
    print("页面编码测试")
    print("=" * 60)
    
    # 测试各个页面
    pages = [
        ("/", "首页"),
        ("/login", "登录页面"),
        ("/register", "注册页面"),
        ("/messages", "消息页面（未登录）"),
        ("/services", "服务页面"),
    ]
    
    for url_path, page_name in pages:
        test_page_encoding(url_path, page_name)
    
    print("\n" + "=" * 60)
    print("编码问题诊断:")
    print("=" * 60)
    print("1. 如果检测到乱码特征（锟斤拷），可能是双重编码问题")
    print("2. 如果UTF-8解码失败但其他编码成功，需要检查服务器配置")
    print("3. 如果Content-Type缺少charset，浏览器可能使用错误编码")
    print("4. 常见乱码原因:")
    print("   - GBK编码的内容被当作UTF-8解析")
    print("   - UTF-8编码的内容被当作GBK解析")
    print("   - 模板文件保存编码与声明编码不一致")
    print("\n建议解决方案:")
    print("1. 确保所有模板文件保存为UTF-8编码（无BOM）")
    print("2. 在Flask应用中设置默认编码")
    print("3. 在响应头中明确指定charset=utf-8")

if __name__ == "__main__":
    main()