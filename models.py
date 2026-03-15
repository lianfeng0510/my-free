from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import json

db = SQLAlchemy()

circle_members = db.Table('circle_members',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('circle_id', db.Integer, db.ForeignKey('circle.id'), primary_key=True),
    db.Column('joined_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

circle_admins = db.Table('circle_admins',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('circle_id', db.Integer, db.ForeignKey('circle.id'), primary_key=True),
    db.Column('assigned_by', db.Integer, db.ForeignKey('user.id'), nullable=True),
    db.Column('assigned_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

# 贴吧分类模型
class Board(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    posts = db.relationship('Post', backref='board', lazy=True)

# 圈子模型
class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)
    circle_type = db.Column(db.String(20), nullable=False, index=True)  # basic, interest, temporary
    is_public = db.Column(db.Boolean, default=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    posts = db.relationship('Post', backref='circle', lazy=True)
    members = db.relationship('User', secondary='circle_members', backref=db.backref('joined_circles', lazy='dynamic'), lazy='dynamic')
    admins = db.relationship('User', secondary='circle_admins', primaryjoin='Circle.id==circle_admins.c.circle_id', secondaryjoin='User.id==circle_admins.c.user_id', lazy='dynamic')

class CircleMeta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, unique=True, index=True)
    icon = db.Column(db.String(10), nullable=False, default='🌟')
    level = db.Column(db.Integer, nullable=False, default=1, index=True)
    exp = db.Column(db.Integer, nullable=False, default=0)
    checkin_score = db.Column(db.Integer, nullable=False, default=0)
    post_score = db.Column(db.Integer, nullable=False, default=0)
    interaction_score = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('meta', uselist=False))

class CircleMemberStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    exp = db.Column(db.Integer, nullable=False, default=0)
    level = db.Column(db.Integer, nullable=False, default=1, index=True)
    checkin_days = db.Column(db.Integer, nullable=False, default=0)
    last_checkin_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('member_stats', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('circle_stats', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('circle_id', 'user_id', name='_circle_member_stats_uc'),)

class CircleAdminPermission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    can_manage_posts = db.Column(db.Boolean, nullable=False, default=True)
    can_manage_comments = db.Column(db.Boolean, nullable=False, default=True)
    can_feature_posts = db.Column(db.Boolean, nullable=False, default=False)
    can_pin_posts = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('admin_permissions', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('circle_admin_permissions', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('circle_id', 'user_id', name='_circle_admin_permission_uc'),)

class CircleCheckin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    checkin_date = db.Column(db.Date, nullable=False, index=True)
    exp_gained = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('checkins', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('circle_checkins', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('circle_id', 'user_id', 'checkin_date', name='_circle_checkin_once_per_day_uc'),)

class CircleCheckinRepair(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    repaired_date = db.Column(db.Date, nullable=False, index=True)
    exp_cost = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('repair_checkins', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('circle_repair_checkins', lazy='dynamic'))
    __table_args__ = (db.UniqueConstraint('circle_id', 'user_id', 'repaired_date', name='_circle_checkin_repair_once_uc'),)

class CircleCheckinCardRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    change_amount = db.Column(db.Integer, nullable=False, default=0)
    reason = db.Column(db.String(100), nullable=False, default='system')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('checkin_card_records', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('checkin_card_records', lazy='dynamic'))

class CircleActionLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    action_type = db.Column(db.String(50), nullable=False, index=True)
    action_detail = db.Column(db.String(300), nullable=True)
    target_type = db.Column(db.String(30), nullable=True, index=True)
    target_id = db.Column(db.Integer, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    circle = db.relationship('Circle', backref=db.backref('action_logs', lazy='dynamic'))
    actor = db.relationship('User', backref=db.backref('circle_action_logs', lazy='dynamic'))

# 徽章模型
class Badge(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.String(200), nullable=True)
    icon = db.Column(db.String(100), nullable=True)
    users = db.relationship('User', secondary='user_badges', back_populates='badges')

# 用户徽章关联表
user_badges = db.Table('user_badges',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('badge_id', db.Integer, db.ForeignKey('badge.id'), primary_key=True),
    db.Column('awarded_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

# 积分模型
class Point(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)  # 积分数量，正数为增加，负数为减少
    reason = db.Column(db.String(200), nullable=False)  # 积分变动原因
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user = db.relationship('User', back_populates='point_records')

# 关注关系模型
follows = db.Table('follows',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('created_at', db.DateTime, nullable=False, default=datetime.utcnow)
)

# 用户模型
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(200), nullable=True, default='default_avatar.png')
    bio = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(10), default='user', index=True)  # user, admin
    level = db.Column(db.Integer, default=1)  # 用户等级
    points = db.Column(db.Integer, default=0)  # 用户积分
    post_count = db.Column(db.Integer, default=0)  # 发帖数
    comment_count = db.Column(db.Integer, default=0)  # 评论数
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    privacy_settings = db.Column(db.Text, nullable=True, default='{}')  # JSON格式存储隐私设置
    posts = db.relationship('Post', backref='author', lazy=True, cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    collections = db.relationship('Collection', backref='user', lazy=True, cascade='all, delete-orphan')
    likes = db.relationship('Like', backref='user', lazy=True, cascade='all, delete-orphan')

    # 徽章关系
    badges = db.relationship('Badge', secondary='user_badges', back_populates='users')
    # 积分记录关系
    point_records = db.relationship('Point', back_populates='user', lazy=True, cascade='all, delete-orphan')
    # 关注关系
    followed = db.relationship('User', 
                               secondary='follows',
                               primaryjoin=(follows.c.follower_id == id),
                               secondaryjoin=(follows.c.followed_id == id),
                               backref=db.backref('followers', lazy='dynamic'),
                               lazy='dynamic')
    
    def follow(self, user):
        """关注一个用户"""
        if not self.is_following(user):
            self.followed.append(user)
            return True
        return False
    
    def unfollow(self, user):
        """取消关注一个用户"""
        if self.is_following(user):
            self.followed.remove(user)
            return True
        return False
    
    def is_following(self, user):
        """检查是否已关注该用户"""
        return self.followed.filter(follows.c.followed_id == user.id).count() > 0
    
    def is_followed_by(self, user):
        """检查是否被该用户关注"""
        return self.followers.filter(follows.c.follower_id == user.id).count() > 0
    
    def get_followers_count(self):
        """获取粉丝数"""
        return self.followers.count()
    
    def get_following_count(self):
        """获取关注数"""
        return self.followed.count()
    
    def get_privacy_setting(self, setting_key, default=True):
        """获取用户的隐私设置"""
        try:
            if not self.privacy_settings:
                return default
            settings = json.loads(self.privacy_settings)
            return settings.get(setting_key, default)
        except (json.JSONDecodeError, KeyError):
            return default
    
    def is_profile_public(self):
        """检查个人资料是否公开"""
        return self.get_privacy_setting('public_profile', True)
    
    def shows_online_status(self):
        """检查是否显示在线状态"""
        return self.get_privacy_setting('show_online_status', True)
    
    def allows_stranger_messages(self):
        """检查是否允许陌生人私信"""
        return self.get_privacy_setting('allow_stranger_messages', True)
    
    def wants_content_recommendation(self):
        """检查是否想要内容推荐"""
        return self.get_privacy_setting('recommend_content', True)
    
    def wants_notifications(self):
        """检查是否想要接收通知"""
        return self.get_privacy_setting('receive_notifications', True)
    
    @property
    def avatar_url(self):
        """获取头像URL，如果文件不存在则返回默认头像"""
        if not self.avatar or self.avatar == 'default_avatar.png':
            # 生成基于用户名的默认头像SVG
            import hashlib
            # 生成确定性颜色
            hash_val = hashlib.md5(self.username.encode()).hexdigest()
            hue = int(hash_val[:2], 16) % 360
            color = f'hsl({hue}, 70%, 60%)'
            # 获取用户首字母
            initials = self.username[0].upper() if self.username else 'U'
            # 创建SVG data URI
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
                <rect width="200" height="200" rx="100" fill="{color}"/>
                <text x="100" y="120" text-anchor="middle" font-family="Arial, sans-serif" font-size="80" fill="white" font-weight="bold">{initials}</text>
            </svg>'''
            import base64
            encoded = base64.b64encode(svg.encode()).decode()
            return f"data:image/svg+xml;base64,{encoded}"
        
        avatar_path = str(self.avatar).strip()
        if avatar_path.startswith('http://') or avatar_path.startswith('https://') or avatar_path.startswith('data:'):
            return avatar_path
        if avatar_path.startswith('/'):
            return avatar_path
        return f"/static/{avatar_path}"

# 帖子模型
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    date_updated = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    board_id = db.Column(db.Integer, db.ForeignKey('board.id'), nullable=False, index=True)
    circle_id = db.Column(db.Integer, db.ForeignKey('circle.id'), nullable=True, index=True)  # 关联的圈子
    post_type = db.Column(db.String(20), nullable=False, default='normal', index=True)  # normal, second_hand, food, lost_found, part_time, course, activity, notification
    status = db.Column(db.String(20), nullable=False, default='active', index=True)  # active, sold, resolved, closed
    is_sticky = db.Column(db.Boolean, default=False, index=True)  # 是否置顶
    is_essence = db.Column(db.Boolean, default=False, index=True)  # 是否精华帖
    is_anonymous = db.Column(db.Boolean, default=False, index=True)  # 是否匿名
    views = db.Column(db.Integer, default=0, index=True)  # 浏览量
    like_count = db.Column(db.Integer, default=0, index=True)  # 点赞数
    comment_count = db.Column(db.Integer, default=0, index=True)  # 评论数
    # 服务相关字段
    price = db.Column(db.Float, nullable=True)  # 价格（二手、外卖等）
    location = db.Column(db.String(200), nullable=True)  # 位置
    contact_info = db.Column(db.String(200), nullable=True)  # 联系方式
    metadata_json = db.Column(db.Text, nullable=True)  # 其他元数据（JSON格式）
    # 图片字段
    images = db.Column(db.Text, nullable=True)  # 存储图片路径，多个图片用逗号分隔
    # 关联关系
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    collectors = db.relationship('Collection', backref='post', lazy=True, cascade='all, delete-orphan')
    likers = db.relationship('Like', backref='post', lazy=True, cascade='all, delete-orphan')
    # 服务按钮关联
    service_buttons = db.relationship('ServiceButton', backref='post', lazy=True, cascade='all, delete-orphan')

# 评论模型
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    date_updated = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True, index=True)  # 回复的评论ID
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade='all, delete-orphan')  # 回复关系

class CommentAttachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False, index=True)
    image_path = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    comment = db.relationship('Comment', backref=db.backref('attachments', lazy=True, cascade='all, delete-orphan'))

# 通知模型
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    notification_type = db.Column(db.String(20), nullable=False, index=True)  # comment, reply, like, collect, message, system, trade, runner
    related_id = db.Column(db.Integer, nullable=True)  # 关联的帖子或评论ID
    related_type = db.Column(db.String(20), nullable=True)  # 关联类型: post, comment, order

# 收藏模型
class Collection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    date_collected = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_post_uc'),)  # 确保用户对同一帖子只能收藏一次

# 点赞模型
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    date_liked = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id', name='_user_post_like_uc'),)  # 确保用户对同一帖子只能点赞一次

# 服务按钮模型
class ServiceButton(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    button_type = db.Column(db.String(50), nullable=False)  # buy, sell, order, contact,报名, etc.
    button_text = db.Column(db.String(50), nullable=False)
    action_url = db.Column(db.String(500), nullable=True)
    action_data = db.Column(db.Text, nullable=True)  # 按钮动作相关数据（JSON格式）
    order_index = db.Column(db.Integer, default=0)  # 按钮显示顺序

# 跑腿订单模型
class RunnerOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    service_type = db.Column(db.String(50), nullable=False)  # 代取快递, 代买饭, 代打印, 其他
    pick_up_location = db.Column(db.String(200), nullable=False)
    delivery_location = db.Column(db.String(200), nullable=False)
    tip = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, accepted, in_progress, completed, cancelled
    creator_reviewed = db.Column(db.Boolean, default=False, nullable=False)  # 发布者是否已评价
    runner_reviewed = db.Column(db.Boolean, default=False, nullable=False)   # 跑腿员是否已评价
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    runner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True, index=True)  # 关联的跑腿帖子
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    accepted_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_orders')
    runner = db.relationship('User', foreign_keys=[runner_id], backref='accepted_orders')
    post = db.relationship('Post', foreign_keys=[post_id], backref='runner_orders')

# 支付模型
class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey('trade.id'), nullable=True, index=True)
    runner_order_id = db.Column(db.Integer, db.ForeignKey('runner_order.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    payment_method = db.Column(db.String(50), nullable=False, index=True)  # wechat, alipay, balance, credit_card
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='CNY')
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, processing, completed, failed, refunded
    transaction_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    payment_channel = db.Column(db.String(50), nullable=True)  # wechat_pay, alipay_app, alipay_web
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    paid_at = db.Column(db.DateTime, nullable=True)
    refunded_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    # 约束：至少有一个关联的交易或跑腿订单
    __table_args__ = (db.CheckConstraint('trade_id IS NOT NULL OR runner_order_id IS NOT NULL', name='payment_has_order'),)
    
    # 关系
    trade = db.relationship('Trade', foreign_keys=[trade_id], backref='payments')
    runner_order = db.relationship('RunnerOrder', foreign_keys=[runner_order_id], backref='payments')
    user = db.relationship('User', foreign_keys=[user_id], backref='payments')

# 私信模型
class PrivateMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    sent_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # 关系
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')
    
    def mark_as_read(self):
        """标记为已读"""
        self.is_read = True
        self.read_at = datetime.utcnow()

# 黑名单模型
class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    blocker = db.relationship('User', foreign_keys=[blocker_id], backref='blocked_users')
    blocked = db.relationship('User', foreign_keys=[blocked_id], backref='blocked_by_users')
    
    __table_args__ = (db.UniqueConstraint('blocker_id', 'blocked_id', name='_blocker_blocked_uc'),)

# 举报模型
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    reported_post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True, index=True)
    reported_comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True, index=True)
    report_type = db.Column(db.String(50), nullable=False, index=True)  # user, post, comment
    reason = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, reviewing, resolved, dismissed
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    
    reporter = db.relationship('User', foreign_keys=[reporter_id], backref='reports_made')
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref='reports_received')
    reported_post = db.relationship('Post', foreign_keys=[reported_post_id], backref='reports')
    reported_comment = db.relationship('Comment', foreign_keys=[reported_comment_id], backref='reports')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='reports_resolved')

# 担保交易模型
class Trade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    price = db.Column(db.Float, nullable=False)
    trade_status = db.Column(db.String(20), nullable=False, default='pending', index=True)  # pending, payment_pending, paid, shipped, delivered, completed, cancelled, disputed
    payment_status = db.Column(db.String(20), nullable=False, default='unpaid', index=True)  # unpaid, paid, refunded
    escrow_held = db.Column(db.Boolean, default=False)  # 是否启用平台担保
    escrow_release_condition = db.Column(db.String(100), nullable=True)  # 担保释放条件
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    payment_date = db.Column(db.DateTime, nullable=True)
    shipping_date = db.Column(db.DateTime, nullable=True)
    delivery_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    dispute_reason = db.Column(db.Text, nullable=True)
    
    post = db.relationship('Post', backref='trade')
    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='purchases')
    seller = db.relationship('User', foreign_keys=[seller_id], backref='sales')

# 跑腿服务评价模型
class RunnerReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    runner_order_id = db.Column(db.Integer, db.ForeignKey('runner_order.id'), nullable=False, index=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # 评价人ID
    reviewed_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)  # 被评价人ID
    review_type = db.Column(db.String(20), nullable=False, index=True)  # creator_to_runner（发布者评价跑腿员）, runner_to_creator（跑腿员评价发布者）
    rating = db.Column(db.Integer, nullable=False)  # 评分：1-5星
    content = db.Column(db.Text, nullable=True)  # 评价内容
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)
    
    runner_order = db.relationship('RunnerOrder', backref='reviews')
    reviewer = db.relationship('User', foreign_keys=[reviewer_id], backref='given_reviews')
    reviewed = db.relationship('User', foreign_keys=[reviewed_id], backref='received_reviews')
