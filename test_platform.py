#!/usr/bin/env python
"""
测试平台基本功能是否正常
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
import json

def test_home_page():
    """测试首页是否能正常访问"""
    print("=== 测试首页访问 ===")
    
    with app.test_client() as client:
        # 测试GET请求
        response = client.get('/')
        print(f"状态码: {response.status_code}")
        print(f"内容类型: {response.content_type}")
        print(f"数据长度: {len(response.data)} 字节")
        
        if response.status_code == 200:
            print("✅ 首页访问正常")
            
            # 检查响应内容是否包含关键元素
            content = response.data.decode('utf-8', errors='ignore')
            
            # 检查是否有乱码
            if '�' in content:
                print("❌ 检测到乱码字符")
                return False
            else:
                print("✅ 无乱码字符")
            
            # 检查是否包含关键文本
            check_keywords = ['校园贴吧', '帖子', '校园']
            for keyword in check_keywords:
                if keyword in content:
                    print(f"✅ 包含关键词: {keyword}")
                else:
                    print(f"⚠️  未找到关键词: {keyword}")
            
            return True
        else:
            print(f"❌ 首页访问失败: {response.status_code}")
            return False

def test_encoding():
    """测试编码设置"""
    print("\n=== 测试编码设置 ===")
    
    with app.test_client() as client:
        response = client.get('/')
        headers = dict(response.headers)
        
        content_type = headers.get('Content-Type', '')
        print(f"Content-Type: {content_type}")
        
        if 'charset=utf-8' in content_type.lower():
            print("✅ UTF-8编码设置正确")
        else:
            print("⚠️  缺少UTF-8编码设置")
        
        return 'charset=utf-8' in content_type.lower()

def test_database_connection():
    """测试数据库连接"""
    print("\n=== 测试数据库连接 ===")
    
    from app import db, User, Post
    
    with app.app_context():
        try:
            # 尝试查询用户数量
            user_count = User.query.count()
            print(f"✅ 数据库连接正常，用户数量: {user_count}")
            
            # 尝试查询帖子数量
            post_count = Post.query.count()
            print(f"✅ 帖子数量: {post_count}")
            
            return True
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False

def test_templates():
    """测试模板渲染"""
    print("\n=== 测试模板渲染 ===")
    
    with app.test_client() as client:
        # 测试多个页面
        pages_to_test = [
            ('/', '首页'),
            ('/forum', '论坛页面'),
            ('/register', '注册页面'),
            ('/login', '登录页面')
        ]
        
        all_passed = True
        for url, name in pages_to_test:
            try:
                response = client.get(url)
                if response.status_code in [200, 302]:  # 302是重定向，也正常
                    print(f"✅ {name} 渲染正常: {response.status_code}")
                else:
                    print(f"❌ {name} 渲染失败: {response.status_code}")
                    all_passed = False
                    
                # 检查内容编码
                if response.status_code == 200:
                    content = response.data.decode('utf-8', errors='ignore')
                    if '�' in content:
                        print(f"⚠️  {name} 可能存在乱码")
            except Exception as e:
                print(f"❌ {name} 测试异常: {e}")
                all_passed = False
        
        return all_passed

def main():
    """主测试函数"""
    print("开始测试平台基本功能...")
    print("=" * 60)
    
    results = []
    
    # 运行各项测试
    results.append(('首页访问', test_home_page()))
    results.append(('编码设置', test_encoding()))
    results.append(('数据库连接', test_database_connection()))
    results.append(('模板渲染', test_templates()))
    
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
    
    print(f"\n通过率: {passed_count}/{total_count} ({passed_count/total_count*100:.1f}%)")
    
    if passed_count == total_count:
        print("🎉 所有测试通过！平台基本功能正常。")
        return True
    else:
        print("⚠️  部分测试未通过，请检查相关问题。")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)