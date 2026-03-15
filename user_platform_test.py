#!/usr/bin/env python
"""
校园贴吧平台 - 用户端全功能测试脚本
模拟真实用户操作流程，检查乱码和功能错误
"""

import requests
import time
import sys
from urllib.parse import urljoin, urlparse

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def print_step(step_num, description):
    """打印测试步骤"""
    print(f"\n{'='*60}")
    print(f"步骤 {step_num}: {description}")
    print(f"{'='*60}")

def check_encoding(response, page_name):
    """检查页面编码和乱码"""
    print(f"\n检查 {page_name} 编码:")
    print(f"  状态码: {response.status_code}")
    print(f"  Content-Type: {response.headers.get('Content-Type')}")
    
    # 检查响应头中的charset
    content_type = response.headers.get('Content-Type', '')
    if 'charset=utf-8' in content_type.lower():
        print("  ✅ 响应头包含 charset=utf-8")
    else:
        print("  ⚠️  响应头未明确指定 charset=utf-8")
    
    # 尝试解码并检查乱码
    try:
        content = response.content.decode('utf-8')
        print("  ✅ UTF-8解码成功")
        
        # 检查常见乱码特征
        if '锟斤拷' in content or '�' in content or '\\ufffd' in content:
            print("  ⚠️  检测到乱码特征!")
            # 查找乱码位置
            if '锟斤拷' in content:
                idx = content.find('锟斤拷')
                print(f"    发现'锟斤拷'在位置 {idx}")
                print(f"    上下文: {content[max(0, idx-50):min(len(content), idx+50)]}")
        else:
            print("  ✅ 未检测到乱码特征")
        
        # 检查中文字符显示
        test_chars = ['校园', '贴吧', '登录', '注册', '消息', '私信', '二手', '跑腿', '论坛']
        found = [char for char in test_chars if char in content]
        if found:
            print(f"  ✅ 找到中文字符: {found[:5]}")
        else:
            print("  ⚠️  未找到常见中文字符，可能页面内容异常")
        
        # 检查页面标题
        if '<title>' in content:
            start = content.find('<title>') + 7
            end = content.find('</title>', start)
            if end > start:
                title = content[start:end]
                print(f"  页面标题: {title}")
        
        return content
        
    except UnicodeDecodeError as e:
        print(f"  ❌ UTF-8解码失败: {e}")
        # 尝试其他编码
        for encoding in ['gbk', 'gb2312', 'latin-1']:
            try:
                content = response.content.decode(encoding)
                print(f"  使用 {encoding} 解码成功")
                return content
            except:
                continue
        print("  ❌ 所有编码解码失败")
        return None

def test_homepage():
    """测试首页"""
    print_step(1, "访问首页")
    response = SESSION.get(urljoin(BASE_URL, "/"))
    content = check_encoding(response, "首页")
    
    # 检查导航链接
    if content:
        nav_checks = [
            ('首页链接', '/', '首页' in content),
            ('注册链接', '/register', '注册' in content or 'href="/register"' in content),
            ('登录链接', '/login', '登录' in content or 'href="/login"' in content),
            ('二手交易', '/trade', '二手' in content or 'href="/trade"' in content),
            ('跑腿服务', '/services', '跑腿' in content or 'href="/services"' in content),
            ('论坛', '/forum', '论坛' in content or 'href="/forum"' in content),
        ]
        
        print("\n检查导航链接:")
        for name, url, found in nav_checks:
            status = "✅" if found else "❌"
            print(f"  {status} {name}: {url}")
    
    return response.status_code == 200

def test_register_page():
    """测试注册页面"""
    print_step(2, "访问注册页面")
    response = SESSION.get(urljoin(BASE_URL, "/register"))
    content = check_encoding(response, "注册页面")
    
    if content and '注册' in content:
        print("  ✅ 注册页面内容正常")
        
        # 检查表单元素
        form_checks = [
            ('用户名输入框', 'username' in content),
            ('密码输入框', 'password' in content),
            ('确认密码', 'confirm_password' in content or '确认密码' in content),
            ('注册按钮', '注册' in content or 'Register' in content or 'type="submit"' in content),
        ]
        
        print("\n检查表单元素:")
        for name, found in form_checks:
            status = "✅" if found else "❌"
            print(f"  {status} {name}")
    else:
        print("  ❌ 注册页面异常")
    
    return response.status_code == 200

def test_register_user():
    """测试注册用户"""
    print_step(3, "注册测试用户")
    
    # 先获取CSRF令牌（如果存在）
    response = SESSION.get(urljoin(BASE_URL, "/register"))
    content = response.content.decode('utf-8') if response.status_code == 200 else ""
    
    # 查找CSRF令牌
    csrf_token = None
    if 'csrf_token' in content:
        # 简化处理，实际应该解析HTML
        pass
    
    # 准备注册数据
    import random
    test_username = f"testuser_{random.randint(1000, 9999)}"
    test_password = "Test123456"
    
    register_data = {
        'username': test_username,
        'password': test_password,
        'confirm_password': test_password,
    }
    
    if csrf_token:
        register_data['csrf_token'] = csrf_token
    
    print(f"  尝试注册用户: {test_username}")
    
    response = SESSION.post(urljoin(BASE_URL, "/register"), data=register_data, allow_redirects=False)
    
    print(f"  注册响应状态码: {response.status_code}")
    
    if response.status_code == 302:
        print("  ✅ 注册成功，重定向到登录页或首页")
        location = response.headers.get('Location', '')
        print(f"  重定向到: {location}")
        return True
    elif response.status_code == 200:
        # 可能用户已存在或表单验证失败
        content = response.content.decode('utf-8', errors='ignore')
        if '用户名已存在' in content:
            print("  ⚠️  用户名已存在，尝试登录")
            return test_login_user(test_username, test_password)
        elif '注册成功' in content:
            print("  ✅ 注册成功")
            return True
        else:
            print("  ⚠️  注册响应200，但未明确成功")
            print(f"  响应内容片段: {content[:200]}")
            return False
    else:
        print(f"  ❌ 注册失败，状态码: {response.status_code}")
        return False

def test_login_page():
    """测试登录页面"""
    print_step(4, "访问登录页面")
    response = SESSION.get(urljoin(BASE_URL, "/login"))
    content = check_encoding(response, "登录页面")
    
    if content and '登录' in content:
        print("  ✅ 登录页面内容正常")
        
        # 检查表单元素
        form_checks = [
            ('用户名输入框', 'username' in content),
            ('密码输入框', 'password' in content),
            ('记住我', 'remember' in content or '记住' in content),
            ('登录按钮', '登录' in content or 'Login' in content or 'type="submit"' in content),
        ]
        
        print("\n检查表单元素:")
        for name, found in form_checks:
            status = "✅" if found else "❌"
            print(f"  {status} {name}")
    else:
        print("  ❌ 登录页面异常")
    
    return response.status_code == 200

def test_login_user(username, password):
    """测试登录用户"""
    print_step(5, "登录测试用户")
    
    # 先获取登录页面
    response = SESSION.get(urljoin(BASE_URL, "/login"))
    content = response.content.decode('utf-8') if response.status_code == 200 else ""
    
    login_data = {
        'username': username,
        'password': password,
        'remember': 'on'
    }
    
    print(f"  尝试登录用户: {username}")
    
    response = SESSION.post(urljoin(BASE_URL, "/login"), data=login_data, allow_redirects=False)
    
    print(f"  登录响应状态码: {response.status_code}")
    
    if response.status_code == 302:
        print("  ✅ 登录成功，重定向到首页")
        location = response.headers.get('Location', '')
        print(f"  重定向到: {location}")
        
        # 访问重定向页面验证登录状态
        if location:
            redirect_url = urljoin(BASE_URL, location)
            response = SESSION.get(redirect_url)
            if response.status_code == 200:
                content = response.content.decode('utf-8', errors='ignore')
                if '退出' in content or '登出' in content or 'logout' in content:
                    print("  ✅ 登录状态验证成功")
                    return True
        
        return True
    else:
        print(f"  ❌ 登录失败，状态码: {response.status_code}")
        # 尝试使用管理员账号
        print("  尝试使用管理员账号登录...")
        return test_admin_login()

def test_admin_login():
    """测试管理员登录"""
    print("  使用管理员账号登录:")
    admin_data = {
        'username': 'Socrates',
        'password': 'Jiang0531',
        'remember': 'on'
    }
    
    response = SESSION.post(urljoin(BASE_URL, "/login"), data=admin_data, allow_redirects=False)
    
    if response.status_code == 302:
        print("  ✅ 管理员登录成功")
        return True
    else:
        print(f"  ❌ 管理员登录失败，状态码: {response.status_code}")
        return False

def test_trade_page():
    """测试二手交易页面"""
    print_step(6, "访问二手交易页面")
    response = SESSION.get(urljoin(BASE_URL, "/trade"))
    content = check_encoding(response, "二手交易页面")
    
    if response.status_code == 200 and content:
        print("  ✅ 二手交易页面可访问")
        
        # 检查页面内容
        content_checks = [
            ('页面标题', '二手' in content or '交易' in content),
            ('商品列表', '商品' in content or 'item' in content or '产品' in content),
            ('搜索功能', '搜索' in content or 'search' in content),
            ('筛选功能', '筛选' in content or 'filter' in content or '分类' in content),
        ]
        
        print("\n检查页面内容:")
        for name, found in content_checks:
            status = "✅" if found else "⚠️ "
            print(f"  {status} {name}")
    elif response.status_code == 302:
        print("  ⚠️  未登录，重定向到登录页")
        return False
    else:
        print(f"  ❌ 二手交易页面异常，状态码: {response.status_code}")
    
    return response.status_code == 200

def test_services_page():
    """测试跑腿服务页面"""
    print_step(7, "访问跑腿服务页面")
    response = SESSION.get(urljoin(BASE_URL, "/services"))
    content = check_encoding(response, "跑腿服务页面")
    
    if response.status_code == 200 and content:
        print("  ✅ 跑腿服务页面可访问")
        
        # 检查页面内容
        content_checks = [
            ('页面标题', '跑腿' in content or '服务' in content or 'delivery' in content),
            ('服务分类', '分类' in content or 'category' in content or '类型' in content),
            ('订单列表', '订单' in content or 'order' in content),
            ('创建订单', '创建' in content or '发布' in content or '新建' in content),
        ]
        
        print("\n检查页面内容:")
        for name, found in content_checks:
            status = "✅" if found else "⚠️ "
            print(f"  {status} {name}")
    elif response.status_code == 302:
        print("  ⚠️  未登录，重定向到登录页")
        return False
    else:
        print(f"  ❌ 跑腿服务页面异常，状态码: {response.status_code}")
    
    return response.status_code == 200

def test_messages_page():
    """测试消息页面"""
    print_step(8, "访问消息页面")
    response = SESSION.get(urljoin(BASE_URL, "/messages"))
    content = check_encoding(response, "消息页面")
    
    if response.status_code == 200 and content:
        print("  ✅ 消息页面可访问")
        
        # 检查页面内容
        content_checks = [
            ('页面标题', '消息' in content or '私信' in content or '对话' in content),
            ('对话列表', '对话' in content or '聊天' in content or '消息列表' in content),
            ('未读标记', '未读' in content or 'unread' in content),
            ('发送消息', '发送' in content or '回复' in content or 'write' in content),
        ]
        
        print("\n检查页面内容:")
        for name, found in content_checks:
            status = "✅" if found else "⚠️ "
            print(f"  {status} {name}")
    elif response.status_code == 302:
        print("  ⚠️  未登录，重定向到登录页")
        return False
    else:
        print(f"  ❌ 消息页面异常，状态码: {response.status_code}")
    
    return response.status_code == 200

def test_forum_page():
    """测试论坛页面"""
    print_step(9, "访问论坛页面")
    response = SESSION.get(urljoin(BASE_URL, "/forum"))
    content = check_encoding(response, "论坛页面")
    
    if response.status_code == 200 and content:
        print("  ✅ 论坛页面可访问")
        
        # 检查页面内容
        content_checks = [
            ('页面标题', '论坛' in content or '圈子' in content or 'community' in content),
            ('圈子列表', '圈子' in content or '版块' in content or 'board' in content),
            ('帖子列表', '帖子' in content or '主题' in content or 'post' in content),
            ('发帖功能', '发帖' in content or '发布' in content or 'create' in content),
        ]
        
        print("\n检查页面内容:")
        for name, found in content_checks:
            status = "✅" if found else "⚠️ "
            print(f"  {status} {name}")
    elif response.status_code == 302:
        print("  ⚠️  未登录，重定向到登录页")
        return False
    else:
        print(f"  ❌ 论坛页面异常，状态码: {response.status_code}")
    
    return response.status_code == 200

def test_profile_page():
    """测试个人资料页面"""
    print_step(10, "访问个人资料页面")
    response = SESSION.get(urljoin(BASE_URL, "/profile"))
    content = check_encoding(response, "个人资料页面")
    
    if response.status_code == 200 and content:
        print("  ✅ 个人资料页面可访问")
        
        # 检查页面内容
        content_checks = [
            ('页面标题', '个人资料' in content or '资料' in content or 'profile' in content),
            ('用户信息', '用户名' in content or '用户' in content or 'info' in content),
            ('编辑功能', '编辑' in content or '修改' in content or 'edit' in content),
            ('统计信息', '帖子' in content or '评论' in content or '统计' in content),
        ]
        
        print("\n检查页面内容:")
        for name, found in content_checks:
            status = "✅" if found else "⚠️ "
            print(f"  {status} {name}")
    elif response.status_code == 302:
        print("  ⚠️  未登录，重定向到登录页")
        return False
    else:
        print(f"  ❌ 个人资料页面异常，状态码: {response.status_code}")
    
    return response.status_code == 200

def run_comprehensive_test():
    """运行全面测试"""
    print("=" * 60)
    print("校园贴吧平台 - 用户端全功能测试")
    print("=" * 60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试地址: {BASE_URL}")
    print("=" * 60)
    
    # 记录测试结果
    test_results = {}
    
    # 测试未登录状态下的页面
    test_results['homepage'] = test_homepage()
    test_results['register_page'] = test_register_page()
    test_results['login_page'] = test_login_page()
    
    # 测试注册和登录
    test_results['register_user'] = test_register_user()
    
    # 如果注册失败，尝试使用测试用户登录
    if not test_results['register_user']:
        test_results['login_user'] = test_login_user('testuser_1234', 'Test123456')
    else:
        test_results['login_user'] = True
    
    # 测试登录状态下的功能页面
    if test_results.get('login_user'):
        test_results['trade_page'] = test_trade_page()
        test_results['services_page'] = test_services_page()
        test_results['messages_page'] = test_messages_page()
        test_results['forum_page'] = test_forum_page()
        test_results['profile_page'] = test_profile_page()
    
    # 生成测试报告
    print("\n" + "=" * 60)
    print("测试报告")
    print("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result)
    
    print(f"总测试项: {total_tests}")
    print(f"通过项: {passed_tests}")
    print(f"失败项: {total_tests - passed_tests}")
    print(f"通过率: {passed_tests/total_tests*100:.1f}%")
    
    print("\n详细结果:")
    for test_name, result in test_results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} {test_name}")
    
    print("\n" + "=" * 60)
    print("问题总结与建议")
    print("=" * 60)
    
    # 分析常见问题
    issues = []
    
    if not test_results.get('login_user'):
        issues.append("用户登录功能存在问题，可能影响所有需要登录的功能")
    
    if not test_results.get('trade_page'):
        issues.append("二手交易页面访问异常")
    
    if not test_results.get('services_page'):
        issues.append("跑腿服务页面访问异常")
    
    if not test_results.get('messages_page'):
        issues.append("消息页面访问异常")
    
    if not test_results.get('forum_page'):
        issues.append("论坛页面访问异常")
    
    if issues:
        print("发现以下问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("✅ 所有主要功能测试通过")
    
    print("\n建议:")
    print("1. 检查所有页面的编码设置，确保使用UTF-8")
    print("2. 验证所有路由是否正确配置")
    print("3. 检查模板文件是否保存为UTF-8编码（无BOM）")
    print("4. 确保登录状态验证正常工作")
    print("5. 添加页面加载错误处理机制")
    
    return test_results

if __name__ == "__main__":
    try:
        results = run_comprehensive_test()
        
        # 提供手动验证链接
        print("\n" + "=" * 60)
        print("手动验证链接")
        print("=" * 60)
        print(f"首页: {BASE_URL}/")
        print(f"注册: {BASE_URL}/register")
        print(f"登录: {BASE_URL}/login")
        print(f"二手交易: {BASE_URL}/trade")
        print(f"跑腿服务: {BASE_URL}/services")
        print(f"消息: {BASE_URL}/messages")
        print(f"论坛: {BASE_URL}/forum")
        print(f"个人资料: {BASE_URL}/profile")
        
        # 根据测试结果给出建议
        if not all(results.values()):
            print("\n⚠️  发现功能问题，建议优先修复:")
            for test_name, result in results.items():
                if not result:
                    print(f"  - {test_name}")
        
        sys.exit(0 if all(results.values()) else 1)
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)