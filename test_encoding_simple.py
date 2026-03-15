#!/usr/bin/env python
"""
测试页面编码问题（简化版）
"""

import requests
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"

def test_page_encoding(url_path, page_name):
    """测试页面编码"""
    print(f"\n测试 {page_name} 页面编码 ({url_path}):")
    
    try:
        response = requests.get(urljoin(BASE_URL, url_path))
        print(f"  状态码: {response.status_code}")
        print(f"  响应头 Content-Type: {response.headers.get('Content-Type')}")
        
        # 尝试用不同编码解码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                content = response.content.decode(encoding)
                print(f"  {encoding}解码成功")
                
                # 检查常见中文字符
                test_chars = ['校园', '贴吧', '登录', '注册', '消息', '私信']
                found_chars = []
                for char in test_chars:
                    if char in content:
                        found_chars.append(char)
                
                if found_chars:
                    print(f"    找到的中文字符: {found_chars}")
                
                # 检查乱码特征
                if '锟斤拷' in content or '�' in content:
                    print(f"    ⚠️ 检测到乱码特征!")
                
                # 显示页面标题
                if '<title>' in content:
                    start = content.find('<title>') + 7
                    end = content.find('</title>', start)
                    if end > start:
                        title = content[start:end]
                        print(f"    页面标题: {title}")
                
                # 显示前200字符中的中文内容
                preview = content[:200].replace('\n', ' ').replace('\r', '')
                chinese_chars = [c for c in preview if '\u4e00' <= c <= '\u9fff']
                if chinese_chars:
                    print(f"    预览中的中文字符: {''.join(chinese_chars[:20])}")
                
                return True
                
            except UnicodeDecodeError:
                continue
            except Exception as e:
                print(f"    {encoding}解码异常: {e}")
                continue
        
        print(f"  所有编码解码失败")
        # 显示原始字节
        print(f"  前100字节: {response.content[:100]}")
        
    except Exception as e:
        print(f"  请求失败: {e}")
    
    return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("页面编码测试（简化版）")
    print("=" * 60)
    
    # 测试各个页面
    pages = [
        ("/", "首页"),
        ("/login", "登录页面"),
        ("/register", "注册页面"),
        ("/messages", "消息页面（未登录）"),
        ("/services", "服务页面"),
    ]
    
    results = {}
    for url_path, page_name in pages:
        success = test_page_encoding(url_path, page_name)
        results[page_name] = success
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    for page_name, success in results.items():
        status = "✅ 正常" if success else "❌ 异常"
        print(f"  {page_name}: {status}")
    
    print("\n诊断建议:")
    if all(results.values()):
        print("所有页面编码正常，乱码可能是浏览器缓存或显示问题。")
        print("建议：清除浏览器缓存或尝试其他浏览器。")
    else:
        print("部分页面存在编码问题，建议：")
        print("1. 检查模板文件是否保存为UTF-8编码（无BOM）")
        print("2. 在Flask应用中添加编码配置")
        print("3. 确保响应头包含charset=utf-8")
    
    print("\n手动验证:")
    print("1. 访问 http://127.0.0.1:5000/register 查看注册页面")
    print("2. 检查页面标题是否显示为'校园贴吧 - 注册'")
    print("3. 查看页面是否有乱码字符")

if __name__ == "__main__":
    main()