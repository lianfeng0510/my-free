#!/usr/bin/env python3
# 简化的测试服务器，只包含通知相关功能

from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, current_user
from datetime import datetime
import os

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test_notifications.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 初始化数据库
db = SQLAlchemy(app)

# 初始化登录管理器
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(10), default='user')

# 通知模型
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    notification_type = db.Column(db.String(20), nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    related_type = db.Column(db.String(20), nullable=True)

# 加载用户
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            login_user(user)
            return render_template('simple_notifications.html')
    return '''
        <form method="post">
            <input type="text" name="username" placeholder="用户名" required><br>
            <input type="password" name="password" placeholder="密码" required><br>
            <input type="submit" value="登录">
        </form>
    '''

# 通知页面
@app.route('/notifications')
@login_required
def notifications():
    # 获取所有通知
    user_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.date_created.desc()).all()
    
    # 按类型分组通知
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
    
    for notification in user_notifications:
        if notification.notification_type in notifications_by_type:
            notifications_by_type[notification.notification_type].append(notification)
    
    return render_template('simple_notifications.html', notifications_by_type=notifications_by_type)

# 一键已读
@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

# 创建简化的通知模板
@app.route('/create_template')
def create_template():
    template_content = '''
<!DOCTYPE html>
<html>
<head>
    <title>通知中心</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .group { margin-bottom: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .group-header { padding: 10px; cursor: pointer; background-color: #f5f5f5; }
        .group-content { padding: 10px; }
        .notification { padding: 10px; margin: 5px 0; border-left: 3px solid #ccc; }
        .unread { background-color: #fff3cd; border-left-color: #ffc107; }
        .button { padding: 5px 10px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>通知中心</h1>
            <button class="button" id="mark-all-read">一键已读</button>
        </div>
        
        <!-- 评论和回复 -->
        <div class="group">
            <div class="group-header" onclick="toggleGroup(this)">
                <h3>评论和回复</h3>
            </div>
            <div class="group-content">
                {% set notifications = notifications_by_type.comment + notifications_by_type.reply %}
                {% for notification in notifications %}
                <div class="notification {% if not notification.is_read %}unread{% endif %}">
                    {{ notification.content }}
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- 点赞和收藏 -->
        <div class="group">
            <div class="group-header" onclick="toggleGroup(this)">
                <h3>点赞和收藏</h3>
            </div>
            <div class="group-content">
                {% set notifications = notifications_by_type.like + notifications_by_type.collect %}
                {% for notification in notifications %}
                <div class="notification {% if not notification.is_read %}unread{% endif %}">
                    {{ notification.content }}
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- 系统通知 -->
        <div class="group">
            <div class="group-header" onclick="toggleGroup(this)">
                <h3>系统通知</h3>
            </div>
            <div class="group-content">
                {% for notification in notifications_by_type.system %}
                <div class="notification {% if not notification.is_read %}unread{% endif %}">
                    {{ notification.content }}
                </div>
                {% endfor %}
            </div>
        </div>
    </div>
    
    <script>
        function toggleGroup(header) {
            const content = header.nextElementSibling;
            if (content.style.display === 'none') {
                content.style.display = 'block';
            } else {
                content.style.display = 'none';
            }
        }
        
        document.getElementById('mark-all-read').addEventListener('click', function() {
            fetch('/notifications/mark-all-read', {
                method: 'POST'
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.querySelectorAll('.unread').forEach(item => {
                        item.classList.remove('unread');
                    });
                    alert('所有通知已标记为已读');
                }
            });
        });
    </script>
</body>
</html>
    '''
    with open('templates/simple_notifications.html', 'w', encoding='utf-8') as f:
        f.write(template_content)
    return '模板创建成功'

# 初始化数据库
with app.app_context():
    db.create_all()
    # 创建测试用户
    if not User.query.filter_by(username='test').first():
        user = User(username='test', password='test123')
        db.session.add(user)
        db.session.commit()
        # 创建测试通知
        notification = Notification(
            content='测试通知：欢迎使用通知系统',
            user_id=user.id,
            notification_type='system'
        )
        db.session.add(notification)
        db.session.commit()

if __name__ == '__main__':
    # 创建templates目录
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(debug=False, port=5001)
