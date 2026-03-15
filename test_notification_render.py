#!/usr/bin/env python3
# 测试通知页面渲染

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Notification
from flask import Flask
from flask_login import login_user

# 测试通知页面渲染
def test_notification_render():
    print("开始测试通知页面渲染...")
    
    # 使用测试请求上下文
    with app.app_context():
        # 获取测试用户
        user = User.query.filter_by(username='Socrates').first()
        if not user:
            print("错误：未找到测试用户 Socrates")
            return False
        
        print(f"找到测试用户: {user.username}")
        
        # 测试通知查询
        try:
            notifications = Notification.query.filter_by(user_id=user.id).all()
            print(f"找到 {len(notifications)} 条通知")
            for notification in notifications:
                print(f"通知类型: {notification.notification_type}, 内容: {notification.content[:50]}...")
        except Exception as e:
            print(f"错误：查询通知时出错: {e}")
            return False
        
        # 测试按类型分组
        try:
            notifications_by_type = {
                'comment': [],
                'reply': [],
                'like': [],
                'collect': [],
                'message': [],
                'system': [],
                'trade': [],
                'runner': []
            }
            
            for notification in notifications:
                if notification.notification_type in notifications_by_type:
                    notifications_by_type[notification.notification_type].append(notification)
            
            print("按类型分组通知:")
            for type_name, type_notifications in notifications_by_type.items():
                if type_notifications:
                    print(f"{type_name}: {len(type_notifications)} 条")
        except Exception as e:
            print(f"错误：分组通知时出错: {e}")
            return False
        
        # 测试模板渲染
        try:
            from flask import render_template_string
            
            # 简单的模板测试
            test_template = '''
            {% set comment_notifications = (notifications_by_type.comment|default([])) + (notifications_by_type.reply|default([])) %}
            {% set unread_count = (comment_notifications|selectattr('is_read', 'equalto', false)|list)|length %}
            评论和回复未读: {{ unread_count }}
            '''
            
            # 渲染模板
            result = render_template_string(test_template, notifications_by_type=notifications_by_type)
            print(f"模板渲染结果: {result}")
            print("模板渲染成功！")
        except Exception as e:
            print(f"错误：模板渲染时出错: {e}")
            return False
    
    print("通知页面渲染测试通过！")
    return True

if __name__ == '__main__':
    test_notification_render()
