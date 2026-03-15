from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, g
import json
import time
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import re
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError

# 导入配置
from config import config

# 导入数据库模型
from models import db, User, Board, Circle, Badge, Post, Comment, Notification, Collection, Like, ServiceButton, RunnerOrder, Payment, PrivateMessage, Block, Report, Trade, Point, CircleMeta, CircleMemberStats, CircleCheckin, CircleAdminPermission, CircleCheckinRepair, CircleCheckinCardRecord, CircleActionLog, CommentAttachment, circle_admins, RunnerReview

# 导入路由蓝图
from routes.trade_routes import trade_bp

# 导入工具函数
from utils.validators import allowed_file
from utils.helpers import generate_order_number

# 导入服务
from services.notification_service import NotificationService

# 应用工厂函数
def create_app(config_name='default'):
    """创建Flask应用"""
    app = Flask(__name__)
    
    # 加载配置
    app.config.from_object(config[config_name])
    
    # 初始化数据库
    db.init_app(app)
    
    # 启用 CSRF 保护
    csrf = CSRFProtect(app)
    
    # 初始化登录管理器
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'error'
    
    # 注册蓝图
    app.register_blueprint(trade_bp)
    
    # 创建上传文件夹
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    valid_service_types = {'all', 'second_hand', 'runner', 'food', 'lost_found', 'part_time', 'course', 'activity'}
    valid_post_types = {'normal', 'second_hand', 'runner', 'food', 'lost_found', 'part_time', 'course', 'activity', 'notification'}
    valid_second_hand_categories = {'electronics', 'books', 'daily', 'clothes', 'other'}
    valid_price_sort = {'asc', 'desc'}
    valid_conditions = {'new', 'like_new', 'good', 'fair'}

    def safe_page_value(raw_page):
        try:
            page_value = int(raw_page)
        except (TypeError, ValueError):
            page_value = 1
        return max(1, min(page_value, 100000))

    def is_verified_runner(user):
        return bool(user and user.is_authenticated and user.role in ['runner', 'admin'])

    def build_payment_transaction_id(prefix, user_id):
        return f"{prefix}_{int(time.time() * 1000)}_{user_id}"

    def get_or_create_circle_meta(circle_id):
        meta = CircleMeta.query.filter_by(circle_id=circle_id).first()
        if not meta:
            meta = CircleMeta(circle_id=circle_id, icon='🌟', level=1, exp=0)
            db.session.add(meta)
            db.session.flush()
        return meta

    def get_or_create_circle_member_stats(circle_id, user_id):
        stats = CircleMemberStats.query.filter_by(circle_id=circle_id, user_id=user_id).first()
        if not stats:
            stats = CircleMemberStats(circle_id=circle_id, user_id=user_id, exp=0, level=1, checkin_days=0)
            db.session.add(stats)
            db.session.flush()
        return stats

    def get_or_create_circle_admin_permission(circle_id, user_id):
        permission = CircleAdminPermission.query.filter_by(circle_id=circle_id, user_id=user_id).first()
        if not permission:
            permission = CircleAdminPermission(circle_id=circle_id, user_id=user_id)
            db.session.add(permission)
            db.session.flush()
        return permission

    def record_circle_action(circle_id, actor_id, action_type, action_detail='', target_type='', target_id=None):
        if not circle_id or not actor_id or not action_type:
            return None
        log_item = CircleActionLog(
            circle_id=circle_id,
            actor_id=actor_id,
            action_type=action_type[:50],
            action_detail=(action_detail or '')[:300],
            target_type=(target_type or '')[:30] if target_type else None,
            target_id=target_id
        )
        db.session.add(log_item)
        return log_item

    def circle_checkin_card_balance(circle_id, user_id):
        balance = db.session.query(func.coalesce(func.sum(CircleCheckinCardRecord.change_amount), 0)).filter(
            CircleCheckinCardRecord.circle_id == circle_id,
            CircleCheckinCardRecord.user_id == user_id
        ).scalar() or 0
        return max(0, int(balance))

    def normalize_circle_name(raw_name):
        return re.sub(r'\s+', '', (raw_name or '').strip().lower())

    def parse_metadata(raw_json):
        if not raw_json:
            return {}
        if isinstance(raw_json, dict):
            return raw_json
        try:
            loaded = json.loads(raw_json)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}

    def dump_metadata(meta_dict):
        if not isinstance(meta_dict, dict):
            return None
        return json.dumps(meta_dict, ensure_ascii=False)

    def resolve_avatar_url(user_obj):
        if not user_obj or not getattr(user_obj, 'avatar', None):
            return ''
        raw_avatar = str(user_obj.avatar).strip()
        if not raw_avatar:
            return ''
        if raw_avatar.startswith('http://') or raw_avatar.startswith('https://') or raw_avatar.startswith('data:'):
            return raw_avatar
        if raw_avatar.startswith('/'):
            return raw_avatar
        return f"/static/{raw_avatar}"

    def save_upload_file(file_obj, prefix, user_id):
        if not file_obj or not file_obj.filename:
            return None, '未检测到上传文件。'
        if not allowed_file(file_obj.filename, app.config['ALLOWED_EXTENSIONS']):
            return None, '仅支持 png/jpg/jpeg/gif 图片格式。'
        original_name = secure_filename(file_obj.filename)
        unique_name = f"{prefix}_{int(time.time() * 1000)}_{user_id}_{original_name}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
        try:
            file_obj.save(file_path)
        except Exception:
            return None, '文件保存失败，请稍后重试。'
        return f"uploads/{unique_name}", None

    def second_hand_meta(post_obj):
        base = {
            'category': 'other',
            'condition_label': '成色未知',
            'trade_method': 'face',
            'trade_method_label': '面交',
            'escrow_enabled': True,
            'listing_state': 'on_sale'
        }
        if not post_obj:
            return base
        raw_meta = parse_metadata(post_obj.metadata_json)
        category = (raw_meta.get('category') or 'other').strip()
        condition_label = (raw_meta.get('condition_label') or '成色未知').strip()
        trade_method = (raw_meta.get('trade_method') or 'face').strip()
        escrow_enabled = bool(raw_meta.get('escrow_enabled', True))
        listing_state = (raw_meta.get('listing_state') or 'on_sale').strip()
        trade_method_map = {
            'face': '面交',
            'delivery': '送货',
            'both': '面交/送货'
        }
        base.update({
            'category': category if category else 'other',
            'condition_label': condition_label,
            'trade_method': trade_method,
            'trade_method_label': trade_method_map.get(trade_method, '面交'),
            'escrow_enabled': escrow_enabled,
            'listing_state': listing_state
        })
        return base

    def post_images(post_obj):
        if not post_obj or not post_obj.images:
            return []
        return [item.strip() for item in str(post_obj.images).split(',') if item.strip()]

    def get_or_create_board_for_type(post_type):
        post_type_map = {
            'second_hand': '二手交易',
            'runner': '跑腿服务',
            'lost_found': '失物招领',
            'part_time': '兼职信息',
            'course': '课程交流',
            'activity': '活动组局',
            'notification': '校园通知'
        }
        board_name = post_type_map.get(post_type, '普通交流')
        board = Board.query.filter(func.lower(Board.name) == board_name.lower()).first()
        if not board:
            board = Board(name=board_name, description=f'{board_name}专区')
            db.session.add(board)
            db.session.flush()
        return board

    def circle_member_badge(level):
        level_value = max(1, int(level or 1))
        if level_value >= 30:
            return '神话圈友'
        if level_value >= 20:
            return '大师圈友'
        if level_value >= 12:
            return '进阶圈友'
        if level_value >= 6:
            return '活跃圈友'
        return '新秀圈友'

    def circle_checkin_streak(circle_id, user_id, today=None):
        base_date = today or datetime.utcnow().date()
        checkin_dates = [
            row.checkin_date for row in CircleCheckin.query.with_entities(CircleCheckin.checkin_date).filter(
                CircleCheckin.circle_id == circle_id,
                CircleCheckin.user_id == user_id,
                CircleCheckin.checkin_date <= base_date
            ).order_by(CircleCheckin.checkin_date.desc()).limit(90).all()
        ]
        if not checkin_dates:
            return 0
        streak = 0
        cursor_date = base_date
        date_set = set(checkin_dates)
        while cursor_date in date_set and streak < 90:
            streak += 1
            cursor_date -= timedelta(days=1)
        return streak

    def circle_level_unlocks(level):
        safe_level = max(1, int(level or 1))
        return {
            'max_post_images': 3 if safe_level < 5 else (6 if safe_level < 12 else 9),
            'max_comment_images': 2 if safe_level < 6 else (4 if safe_level < 14 else 6),
            'checkin_repair_days': 0 if safe_level < 3 else (2 if safe_level < 8 else (4 if safe_level < 15 else 7)),
            'pin_post': safe_level >= 6,
            'feature_post': safe_level >= 8
        }

    def next_level_progress(exp):
        current_exp = max(0, int(exp or 0))
        current_level = calc_level_by_exp(current_exp)
        if current_level >= 50:
            return {
                'current_level': current_level,
                'next_level': current_level,
                'current_exp': current_exp,
                'target_exp': current_exp,
                'progress_percent': 100
            }
        target_exp = current_exp
        while target_exp < 200000 and calc_level_by_exp(target_exp) <= current_level:
            target_exp += 1
        previous_exp = current_exp
        while previous_exp > 0 and calc_level_by_exp(previous_exp - 1) == current_level:
            previous_exp -= 1
        denominator = max(1, target_exp - previous_exp)
        progress_percent = int(max(0, min(100, ((current_exp - previous_exp) / denominator) * 100)))
        return {
            'current_level': current_level,
            'next_level': current_level + 1,
            'current_exp': current_exp,
            'target_exp': target_exp,
            'progress_percent': progress_percent
        }

    def calc_level_by_exp(exp):
        exp_value = max(0, int(exp or 0))
        if exp_value < 200:
            return 1 + exp_value // 100
        if exp_value < 1000:
            return 3 + (exp_value - 200) // 160
        if exp_value < 3000:
            return 8 + (exp_value - 1000) // 250
        return min(50, 16 + (exp_value - 3000) // 400)

    def circle_admin_limit(level):
        safe_level = max(1, int(level or 1))
        base = 1 + safe_level // 3
        if safe_level >= 10:
            base += 1
        if safe_level >= 20:
            base += 1
        return max(1, min(18, base))

    def is_circle_admin_user(user_id, circle_obj):
        if not user_id or not circle_obj:
            return False
        if circle_obj.creator_id == user_id:
            return True
        return circle_obj.admins.filter(User.id == user_id).first() is not None

    def circle_admin_permission_dict(circle_obj, user_id):
        empty = {
            'can_manage_posts': False,
            'can_manage_comments': False,
            'can_feature_posts': False,
            'can_pin_posts': False
        }
        if not circle_obj or not user_id:
            return empty
        if circle_obj.creator_id == user_id:
            return {
                'can_manage_posts': True,
                'can_manage_comments': True,
                'can_feature_posts': True,
                'can_pin_posts': True
            }
        if circle_obj.admins.filter(User.id == user_id).first() is None:
            return empty
        permission = CircleAdminPermission.query.filter_by(circle_id=circle_obj.id, user_id=user_id).first()
        unlocks = circle_level_unlocks(circle_obj.meta.level if circle_obj.meta else 1)
        if not permission:
            return {
                'can_manage_posts': True,
                'can_manage_comments': True,
                'can_feature_posts': bool(unlocks['feature_post']),
                'can_pin_posts': bool(unlocks['pin_post'])
            }
        return {
            'can_manage_posts': bool(permission.can_manage_posts),
            'can_manage_comments': bool(permission.can_manage_comments),
            'can_feature_posts': bool(permission.can_feature_posts) and bool(unlocks['feature_post']),
            'can_pin_posts': bool(permission.can_pin_posts) and bool(unlocks['pin_post'])
        }

    def can_moderate_circle_post(post_obj, user_obj, permission_key='can_manage_posts'):
        if not post_obj or not user_obj or not getattr(post_obj, 'circle_id', None):
            return False
        circle_obj = Circle.query.get(post_obj.circle_id)
        if not circle_obj:
            return False
        permissions = circle_admin_permission_dict(circle_obj, user_obj.id)
        return bool(permissions.get(permission_key))

    def refresh_circle_meta(circle_obj):
        if not circle_obj:
            return None
        meta = get_or_create_circle_meta(circle_obj.id)
        members_count = circle_obj.members.count()
        posts_count = Post.query.filter_by(circle_id=circle_obj.id, status='active').count()
        likes_count = db.session.query(func.coalesce(func.sum(Post.like_count), 0)).filter(Post.circle_id == circle_obj.id, Post.status == 'active').scalar() or 0
        comments_count = db.session.query(func.coalesce(func.sum(Post.comment_count), 0)).filter(Post.circle_id == circle_obj.id, Post.status == 'active').scalar() or 0
        checkin_exp_sum = db.session.query(func.coalesce(func.sum(CircleCheckin.exp_gained), 0)).filter(CircleCheckin.circle_id == circle_obj.id).scalar() or 0
        member_level_sum = db.session.query(func.coalesce(func.sum(CircleMemberStats.level), 0)).filter(CircleMemberStats.circle_id == circle_obj.id).scalar() or 0
        active_members_count = CircleMemberStats.query.filter(CircleMemberStats.circle_id == circle_obj.id, CircleMemberStats.exp >= 30).count()
        meta.checkin_score = int(checkin_exp_sum + active_members_count * 3)
        meta.post_score = int(posts_count * 6 + members_count * 0.5)
        meta.interaction_score = int(likes_count * 2 + comments_count * 3 + member_level_sum * 0.8 + members_count * 2)
        meta.exp = meta.checkin_score + meta.post_score + meta.interaction_score
        meta.level = calc_level_by_exp(meta.exp)
        return meta

    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            app.logger.info(f"Request {request.path} took {elapsed:.4f} seconds")
        
        # 确保响应使用UTF-8字符集
        if response.content_type.startswith('text/'):
            response.headers.setdefault('Content-Type', f"{response.content_type}; charset=utf-8")
        
        return response
    
    # 加载用户
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 全局上下文处理器
    @app.context_processor
    def inject_global_vars():
        # 获取未读通知数
        unread_count = 0
        if current_user and current_user.is_authenticated:
            unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        
        # 获取所有贴吧
        boards = Board.query.all()
        
        # 获取所有圈子
        circles = Circle.query.all()
        
        # 按类型分组圈子
        basic_circles = Circle.query.filter_by(circle_type='basic').all()
        interest_circles = Circle.query.filter_by(circle_type='interest').all()
        temporary_circles = Circle.query.filter_by(circle_type='temporary').all()
        
        return {
            'unread_count': unread_count,
            'boards': boards,
            'circles': circles,
            'basic_circles': basic_circles,
            'interest_circles': interest_circles,
            'temporary_circles': temporary_circles,
            'datetime': datetime,
            'post_images': post_images,
            'second_hand_meta': second_hand_meta,
            'resolve_avatar_url': resolve_avatar_url
        }
    
    # 核心路由
    @app.route('/')
    def home():
        # 处理搜索
        search_query = (request.args.get('search') or '').strip()
        tab = request.args.get('tab', 'discover')
        page = safe_page_value(request.args.get('page', 1))
        per_page = 10
        
        query = Post.query
        
        if search_query:
            query = query.filter(
                (Post.title.contains(search_query)) | 
                (Post.content.contains(search_query))
            )
        
        if tab == 'discover':
            # 发现页：按热度推荐
            query = query.order_by(
                Post.is_sticky.desc(),
                Post.is_essence.desc(),
                Post.like_count.desc(),
                Post.comment_count.desc(),
                Post.views.desc(),
                Post.date_posted.desc()
            )
        elif tab == 'follow':
            # 关注页
            query = query.order_by(Post.is_sticky.desc(), Post.date_posted.desc())
        else:
            query = query.order_by(Post.is_sticky.desc(), Post.date_posted.desc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        posts = pagination.items
        
        return render_template('home.html', posts=posts, search_query=search_query, 
                               tab=tab, pagination=pagination)

    @app.route('/api/mobile/feed')
    @login_required
    def api_mobile_feed():
        page = safe_page_value(request.args.get('page', 1))
        per_page = max(1, min(request.args.get('per_page', 10, type=int), 20))
        search_query = (request.args.get('search') or '').strip()
        query = Post.query
        if search_query:
            query = query.filter(or_(Post.title.contains(search_query), Post.content.contains(search_query)))
        query = query.order_by(Post.is_sticky.desc(), Post.is_essence.desc(), Post.date_posted.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        items = []
        for post_obj in pagination.items:
            items.append({
                'id': post_obj.id,
                'title': post_obj.title,
                'content': post_obj.content[:180],
                'post_type': post_obj.post_type,
                'status': post_obj.status,
                'price': post_obj.price,
                'author': {
                    'id': post_obj.author.id if post_obj.author else None,
                    'username': post_obj.author.username if post_obj.author else '用户',
                    'level': post_obj.author.level if post_obj.author else 1,
                    'avatar': resolve_avatar_url(post_obj.author)
                },
                'images': post_images(post_obj),
                'like_count': post_obj.like_count or 0,
                'comment_count': post_obj.comment_count or 0,
                'created_at': post_obj.date_posted.isoformat()
            })
        return jsonify({
            'success': True,
            'items': items,
            'page': pagination.page,
            'pages': pagination.pages,
            'total': pagination.total
        })
    
    # 注册路由
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # 验证输入
            if not username or not password:
                flash('用户名和密码不能为空', 'error')
                return redirect(url_for('register'))
            
            if len(username) < 2 or len(username) > 20:
                flash('用户名长度应在2-20个字符之间', 'error')
                return redirect(url_for('register'))
            
            if len(password) < 6:
                flash('密码长度至少为6个字符', 'error')
                return redirect(url_for('register'))
            
            # 检查用户名是否已存在
            user = User.query.filter_by(username=username).first()
            if user:
                flash('用户名已存在', 'error')
                return redirect(url_for('register'))
            
            # 创建新用户
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password)
            db.session.add(new_user)
            db.session.commit()
            
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        
        return render_template('register.html')
    
    # 登录路由
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = request.form.get('remember') == 'on'
            
            # 验证输入
            if not username or not password:
                flash('用户名和密码不能为空', 'error')
                return redirect(url_for('login'))
            
            user = User.query.filter_by(username=username).first()
            if user:
                valid = False
                try:
                    if check_password_hash(user.password, password):
                        valid = True
                    else:
                        # 兼容旧账号：如果为明文匹配则升级为哈希
                        if user.password == password:
                            user.password = generate_password_hash(password)
                            db.session.commit()
                            valid = True
                except Exception:
                    # 非标准密码字段时的兜底
                    if user.password == password:
                        user.password = generate_password_hash(password)
                        db.session.commit()
                        valid = True
                if valid:
                    login_user(user, remember=remember)
                    flash('登录成功', 'success')
                    return redirect(url_for('home'))
                else:
                    flash('用户名或密码错误', 'error')
                    return redirect(url_for('login'))
            flash('用户名或密码错误', 'error')
            return redirect(url_for('login'))
        
        return render_template('login.html')
    
    # 登出路由
    @app.route('/logout')
    def logout():
        logout_user()
        flash('登出成功', 'success')
        return redirect(url_for('home'))
    
    # 健康检查路由
    @app.route('/health')
    def health():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })

    @app.route('/@vite/client')
    def vite_client_placeholder():
        return '', 204
    
    # 服务页面路由
    @app.route('/services')
    @app.route('/services/<string:type>')
    def services(type=None):
        service_type = (type or request.args.get('type') or 'all').strip()
        if service_type not in valid_service_types:
            service_type = 'all'

        search_query = (request.args.get('search') or '').strip()
        category = (request.args.get('category') or '').strip()
        price_sort = (request.args.get('price_sort') or '').strip()
        condition = (request.args.get('condition') or '').strip()
        page = safe_page_value(request.args.get('page', 1))
        per_page = 12

        if category not in valid_second_hand_categories:
            category = ''
        if price_sort not in valid_price_sort:
            price_sort = ''
        if condition not in valid_conditions:
            condition = ''
        if service_type != 'second_hand':
            category = ''
            price_sort = ''
            condition = ''

        try:
            query = Post.query.filter(Post.status == 'active')
            if service_type != 'all':
                query = query.filter(Post.post_type == service_type)

            if search_query:
                query = query.filter(
                    or_(
                        Post.title.contains(search_query),
                        Post.content.contains(search_query),
                        Post.location.contains(search_query)
                    )
                )

            if service_type == 'second_hand' and category:
                category_keywords = {
                    'electronics': ['电脑', '笔记本', '手机', '平板', '耳机', '相机', '数码'],
                    'books': ['书', '教材', '资料', '笔记', '题库'],
                    'daily': ['生活', '日用', '桌椅', '宿舍', '厨具'],
                    'clothes': ['衣', '裤', '鞋', '帽', '包', '服饰'],
                    'other': ['其他']
                }
                keywords = category_keywords.get(category, [])
                if keywords:
                    keyword_filters = []
                    for keyword in keywords:
                        keyword_filters.append(Post.title.contains(keyword))
                        keyword_filters.append(Post.content.contains(keyword))
                    query = query.filter(or_(*keyword_filters))

            if service_type == 'second_hand' and condition:
                condition_keywords = {
                    'new': ['全新', '未拆封', '未使用'],
                    'like_new': ['几乎全新', '95新', '9成新'],
                    'good': ['轻微使用', '8成新', '正常使用'],
                    'fair': ['明显磨损', '7成新', '有划痕']
                }
                condition_filter = []
                for keyword in condition_keywords.get(condition, []):
                    condition_filter.append(Post.title.contains(keyword))
                    condition_filter.append(Post.content.contains(keyword))
                if condition_filter:
                    query = query.filter(or_(*condition_filter))

            if service_type == 'second_hand' and price_sort == 'asc':
                query = query.order_by(Post.price.asc(), Post.date_posted.desc())
            elif service_type == 'second_hand' and price_sort == 'desc':
                query = query.order_by(Post.price.desc(), Post.date_posted.desc())
            else:
                query = query.order_by(
                    Post.is_sticky.desc(),
                    Post.is_essence.desc(),
                    Post.date_posted.desc()
                )

            pagination = query.paginate(page=page, per_page=per_page, error_out=False)
            posts = pagination.items
        except Exception:
            db.session.rollback()
            posts = []
            pagination = None
            flash('服务页加载出现异常，已为你切换到安全模式。', 'error')

        return render_template('services.html', 
                               service_type=service_type,
                               posts=posts,
                               pagination=pagination,
                               search_query=search_query,
                               category=category,
                               price_sort=price_sort,
                               condition=condition)
    
    # 新建帖子路由
    @app.route('/new_post', methods=['GET', 'POST'])
    @app.route('/post/new', methods=['GET', 'POST'])
    @login_required
    def new_post():
        boards = Board.query.order_by(Board.id.asc()).all()
        circles = Circle.query.order_by(Circle.id.asc()).all()

        if request.method == 'POST':
            form_data = request.form.to_dict()
            title = (request.form.get('title') or '').strip()
            content = (request.form.get('content') or '').strip()
            post_type = (request.form.get('post_type') or 'normal').strip()
            location = (request.form.get('location') or '').strip()
            contact_info = (request.form.get('contact_info') or '').strip()
            is_anonymous = request.form.get('is_anonymous') == 'on'
            circle_id_raw = request.form.get('circle_id')
            circle_search = (request.form.get('circle_search') or '').strip()
            price_raw = (request.form.get('price') or '').strip()
            second_hand_category = (request.form.get('second_hand_category') or 'other').strip()
            second_hand_condition = (request.form.get('second_hand_condition') or '').strip()
            second_hand_trade_method = (request.form.get('second_hand_trade_method') or 'face').strip()
            second_hand_escrow = request.form.get('second_hand_escrow') == 'on'

            if post_type not in valid_post_types:
                post_type = 'normal'

            if len(title) < 3 or len(title) > 100:
                flash('标题长度需在 3~100 字之间。', 'error')
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)

            if len(content) < 5 or len(content) > 5000:
                flash('正文长度需在 5~5000 字之间。', 'error')
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)

            board = get_or_create_board_for_type(post_type)

            circle_id = None
            circle_obj = None
            if circle_id_raw:
                try:
                    circle_id = int(circle_id_raw)
                except (TypeError, ValueError):
                    circle_id = None
                if circle_id:
                    circle_obj = Circle.query.get(circle_id)
                    if not circle_obj:
                        circle_id = None
                    else:
                        is_member = circle_obj.members.filter(User.id == current_user.id).first() is not None
                        if circle_obj.creator_id != current_user.id and not is_member:
                            flash('加入圈子后才可在该圈子发帖。', 'error')
                            return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)
            elif circle_search:
                candidate = Circle.query.filter(func.lower(Circle.name) == circle_search.lower()).first()
                if candidate:
                    joined = candidate.members.filter(User.id == current_user.id).first() is not None
                    if candidate.creator_id == current_user.id or joined:
                        circle_id = candidate.id
                        circle_obj = candidate

            price = None
            if price_raw:
                try:
                    price = float(price_raw)
                    if price < 0:
                        raise ValueError()
                except ValueError:
                    flash('价格格式不正确。', 'error')
                    return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)
            if post_type == 'second_hand' and price is None:
                flash('二手交易请填写价格。', 'error')
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)
            if post_type == 'second_hand' and len(second_hand_condition) < 2:
                flash('二手交易请填写成色信息。', 'error')
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)

            saved_images = []
            image_files = request.files.getlist('images')
            for index, image_file in enumerate(image_files):
                if not image_file or not image_file.filename:
                    continue
                if not allowed_file(image_file.filename, app.config['ALLOWED_EXTENSIONS']):
                    flash('仅支持 png/jpg/jpeg/gif 图片格式。', 'error')
                    return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)
                original_name = secure_filename(image_file.filename)
                unique_name = f"{int(time.time() * 1000)}_{current_user.id}_{index}_{original_name}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                image_file.save(save_path)
                saved_images.append(f"uploads/{unique_name}")

            try:
                post_obj = Post(
                    title=title,
                    content=content,
                    user_id=current_user.id,
                    board_id=board.id,
                    circle_id=circle_id,
                    post_type=post_type,
                    is_anonymous=is_anonymous,
                    price=price,
                    location=location[:200] if location else None,
                    contact_info=contact_info[:200] if contact_info else None,
                    images=','.join(saved_images) if saved_images else None,
                    metadata_json=dump_metadata({
                        'category': second_hand_category if post_type == 'second_hand' else '',
                        'condition_label': second_hand_condition if post_type == 'second_hand' else '',
                        'trade_method': second_hand_trade_method if post_type == 'second_hand' else 'face',
                        'escrow_enabled': bool(second_hand_escrow) if post_type == 'second_hand' else False,
                        'listing_state': 'on_sale'
                    })
                )
                db.session.add(post_obj)
                current_user.post_count = (current_user.post_count or 0) + 1
                if post_obj.circle_id:
                    refresh_circle_meta(circle_obj or Circle.query.get(post_obj.circle_id))
                db.session.commit()
                flash('发布成功，快去看看你的帖子吧！', 'success')
                return redirect(url_for('post', post_id=post_obj.id))
            except Exception:
                db.session.rollback()
                flash('发布失败，请稍后重试。', 'error')
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)

        post_type = (request.args.get('type') or 'normal').strip()
        if post_type not in valid_post_types:
            post_type = 'normal'
        preset_circle_id = request.args.get('circle_id', type=int)
        if preset_circle_id:
            preset_circle = Circle.query.get(preset_circle_id)
            if not preset_circle:
                preset_circle_id = None
            else:
                joined = preset_circle.members.filter(User.id == current_user.id).first() is not None
                if preset_circle.creator_id != current_user.id and not joined:
                    preset_circle_id = None
        form_data = {
            'circle_id': str(preset_circle_id) if preset_circle_id else '',
            'circle_search': preset_circle.name if preset_circle_id and preset_circle else '',
            'post_type': post_type,
            'title': '',
            'content': '',
            'price': '',
            'location': '',
            'contact_info': '',
            'is_anonymous': '',
            'second_hand_category': 'other',
            'second_hand_condition': '',
            'second_hand_trade_method': 'face',
            'second_hand_escrow': ''
        }
        return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=False)
    
    # 帖子详情路由
    @app.route('/post/<int:post_id>', methods=['GET', 'POST'])
    @login_required
    def post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        circle_obj = Circle.query.get(post_obj.circle_id) if post_obj.circle_id else None
        circle_meta = refresh_circle_meta(circle_obj) if circle_obj else None
        circle_unlocks = circle_level_unlocks(circle_meta.level if circle_meta else 1)
        my_circle_permissions = circle_admin_permission_dict(circle_obj, current_user.id) if circle_obj else {}

        def build_comment_threads(target_post_id):
            all_comments = Comment.query.filter_by(post_id=target_post_id).order_by(Comment.date_posted.asc(), Comment.id.asc()).all()
            comment_by_id = {item.id: item for item in all_comments}
            children_map = {}
            root_comments = []
            floor_map = {}
            floor_seq = 0

            for item in all_comments:
                parent = comment_by_id.get(item.parent_id) if item.parent_id else None
                if parent:
                    children_map.setdefault(parent.id, []).append(item)
                else:
                    floor_seq += 1
                    floor_map[item.id] = floor_seq
                    root_comments.append(item)

            for item in all_comments:
                if item.id in floor_map:
                    continue
                cursor = item
                guard = 0
                while cursor.parent_id and cursor.parent_id in comment_by_id and guard < 30:
                    cursor = comment_by_id[cursor.parent_id]
                    guard += 1
                floor_map[item.id] = floor_map.get(cursor.id, 0)

            def to_node(comment_item, depth):
                children = [to_node(child, depth + 1) for child in children_map.get(comment_item.id, [])]
                return {
                    'comment': comment_item,
                    'depth': depth,
                    'floor': floor_map.get(comment_item.id, 0),
                    'children': children
                }

            return [to_node(root, 0) for root in root_comments]

        if request.method == 'POST':
            content = (request.form.get('content') or '').strip()
            parent_id = request.form.get('parent_id', type=int)
            if len(content) < 2 or len(content) > 1000:
                flash('评论长度需在 2~1000 字之间。', 'error')
                return redirect(url_for('post', post_id=post_id) + '#comments')
            parent_comment = None
            reply_depth = 1
            if parent_id:
                parent_comment = Comment.query.filter_by(id=parent_id, post_id=post_id).first()
                if not parent_comment:
                    flash('回复目标不存在。', 'error')
                    return redirect(url_for('post', post_id=post_id) + '#comments')
                parent_cursor = parent_comment
                while parent_cursor and parent_cursor.parent_id and reply_depth < 8:
                    reply_depth += 1
                    parent_cursor = parent_cursor.parent
            try:
                comment = Comment(
                    content=content,
                    user_id=current_user.id,
                    post_id=post_id,
                    parent_id=parent_comment.id if parent_comment else None
                )
                db.session.add(comment)
                db.session.flush()
                attachments = request.files.getlist('images')
                valid_attachments = [item for item in attachments if item and item.filename]
                if valid_attachments and post_obj.circle_id and len(valid_attachments) > circle_unlocks['max_comment_images']:
                    flash(f'当前圈子等级评论最多上传 {circle_unlocks["max_comment_images"]} 张图片。', 'error')
                    db.session.rollback()
                    return redirect(url_for('post', post_id=post_id) + '#comments')
                for index, image_file in enumerate(valid_attachments):
                    if not image_file or not image_file.filename:
                        continue
                    if not allowed_file(image_file.filename, app.config['ALLOWED_EXTENSIONS']):
                        flash('评论图片仅支持 png/jpg/jpeg/gif 格式。', 'error')
                        db.session.rollback()
                        return redirect(url_for('post', post_id=post_id) + '#comments')
                    file_name = secure_filename(image_file.filename)
                    final_name = f"comment_{int(time.time() * 1000)}_{current_user.id}_{index}_{file_name}"
                    image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))
                    db.session.add(CommentAttachment(comment_id=comment.id, image_path=f"uploads/{final_name}"))
                post_obj.comment_count = (post_obj.comment_count or 0) + 1
                current_user.comment_count = (current_user.comment_count or 0) + 1
                if post_obj.circle_id:
                    user_stats = get_or_create_circle_member_stats(post_obj.circle_id, current_user.id)
                    gained_exp = 3 + min(4, reply_depth - 1)
                    user_stats.exp += gained_exp
                    user_stats.level = calc_level_by_exp(user_stats.exp)
                    refresh_circle_meta(Circle.query.get(post_obj.circle_id))
                if parent_comment and parent_comment.user_id != current_user.id:
                    db.session.add(Notification(
                        user_id=parent_comment.user_id,
                        content=f'{current_user.username} 回复了你在《{post_obj.title}》中的评论。',
                        notification_type='reply',
                        related_id=comment.id,
                        related_type='comment'
                    ))
                elif not parent_comment and post_obj.user_id != current_user.id:
                    db.session.add(Notification(
                        user_id=post_obj.user_id,
                        content=f'{current_user.username} 评论了你的帖子《{post_obj.title}》。',
                        notification_type='comment',
                        related_id=comment.id,
                        related_type='comment'
                    ))
                db.session.commit()
                flash('评论发布成功。', 'success')
            except Exception:
                db.session.rollback()
                flash('评论发布失败，请稍后重试。', 'error')
            return redirect(url_for('post', post_id=post_id) + '#comments')

        post_obj.views = (post_obj.views or 0) + 1
        db.session.commit()
        comment_threads = build_comment_threads(post_id)
        trade_reviews = Comment.query.filter(
            Comment.post_id == post_id,
            Comment.content.contains('【交易评价】')
        ).order_by(Comment.date_posted.desc()).limit(4).all() if post_obj.post_type == 'second_hand' else []
        return render_template(
            'post.html',
            post=post_obj,
            comment_threads=comment_threads,
            circle_unlocks=circle_unlocks,
            my_circle_permissions=my_circle_permissions,
            trade_reviews=trade_reviews
        )
    
    # 二手交易页面路由
    @app.route('/trade')
    @login_required
    def trade():
        search_query = (request.args.get('search') or '').strip()
        category = (request.args.get('category') or '').strip()
        condition = (request.args.get('condition') or '').strip()
        sort_by = (request.args.get('sort') or request.args.get('price_sort') or 'latest').strip()
        my_location = (request.args.get('my_location') or '').strip()
        page = safe_page_value(request.args.get('page', 1))
        per_page = 12
        valid_category = {'books', 'electronics', 'daily', 'clothes', 'other'}
        valid_sort = {'latest', 'price_asc', 'price_desc', 'nearest'}
        if category not in valid_category:
            category = ''
        if sort_by not in valid_sort:
            sort_by = 'latest'

        query = Post.query.filter(Post.post_type == 'second_hand', Post.status.in_(['active', 'trading']))
        if search_query:
            query = query.filter(or_(Post.title.contains(search_query), Post.content.contains(search_query), Post.location.contains(search_query)))
        if category:
            query = query.filter(Post.metadata_json.contains(f'"category": "{category}"'))
        if condition:
            query = query.filter(Post.metadata_json.contains(f'"condition_label": "{condition}"'))

        if sort_by == 'price_asc':
            query = query.order_by(Post.price.asc(), Post.date_posted.desc())
        elif sort_by == 'price_desc':
            query = query.order_by(Post.price.desc(), Post.date_posted.desc())
        elif sort_by == 'nearest':
            near_key = my_location
            if near_key:
                query = query.order_by(Post.location.contains(near_key).desc(), Post.date_posted.desc())
            else:
                query = query.order_by(Post.date_posted.desc())
        else:
            query = query.order_by(Post.is_sticky.desc(), Post.date_posted.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        posts = pagination.items
        return render_template('trade_list.html',
                               posts=posts,
                               pagination=pagination,
                               search_query=search_query,
                               category=category,
                               sort_by=sort_by,
                               my_location=my_location,
                               condition=condition)
    
    # 跑腿服务路由
    @app.route('/create_runner_order', methods=['GET', 'POST'])
    @login_required
    def create_runner_order():
        if request.method == 'POST':
            # 处理表单提交
            try:
                title = (request.form.get('title') or '').strip()
                service_type = (request.form.get('service_type') or '').strip()
                pick_up_location = (request.form.get('pick_up_location') or '').strip()
                delivery_location = (request.form.get('delivery_location') or '').strip()
                tip = float(request.form.get('tip', 0) or 0)
                description = (request.form.get('description') or '').strip()

                if len(title) < 3:
                    flash('订单标题至少 3 个字。', 'error')
                    return render_template('create_runner_order.html')
                if not service_type or not pick_up_location or not delivery_location:
                    flash('请完整填写服务类型、取件地点和送达地点。', 'error')
                    return render_template('create_runner_order.html')
                if tip < 0:
                    flash('跑腿费不能为负数。', 'error')
                    return render_template('create_runner_order.html')
                if len(description) < 5:
                    flash('请补充更具体的订单描述（至少 5 字）。', 'error')
                    return render_template('create_runner_order.html')
                
                # 创建跑腿订单
                order_number = generate_order_number()
                runner_order = RunnerOrder(
                    order_number=order_number,
                    title=title,
                    service_type=service_type,
                    pick_up_location=pick_up_location,
                    delivery_location=delivery_location,
                    tip=tip,
                    description=description,
                    creator_id=current_user.id,
                    status='pending'
                )
                
                db.session.add(runner_order)
                db.session.flush()

                escrow_payment = Payment(
                    runner_order_id=runner_order.id,
                    user_id=current_user.id,
                    payment_method='balance',
                    amount=tip,
                    status='completed',
                    transaction_id=build_payment_transaction_id('RUNNER_ESCROW', current_user.id),
                    description=json.dumps({
                        'flow': 'runner_escrow',
                        'stage': 'held',
                        'order_number': order_number
                    }, ensure_ascii=False),
                    paid_at=datetime.utcnow()
                )
                db.session.add(escrow_payment)
                db.session.commit()
                
                flash('跑腿订单发布成功，跑腿费已由平台暂管。', 'success')
                return redirect(url_for('runner_orders', status='my_orders'))
                
            except Exception as e:
                db.session.rollback()
                flash(f'发布订单失败：{str(e)}', 'error')
                return render_template('create_runner_order.html')
        
        # GET请求：显示表单
        return render_template('create_runner_order.html')
    
    @app.route('/runner_dashboard')
    @login_required
    def runner_dashboard():
        # 跑腿员仪表盘
        can_accept_orders = is_verified_runner(current_user)
        # 尝试获取真实数据，否则使用虚拟数据
        try:
            total_orders = RunnerOrder.query.filter_by(runner_id=current_user.id).count()
            completed_orders = RunnerOrder.query.filter_by(runner_id=current_user.id, status='completed').count()
            today = datetime.utcnow().date()
            today_orders = RunnerOrder.query.filter(
                RunnerOrder.runner_id == current_user.id,
                RunnerOrder.created_at >= today
            ).count()
            total_tips = db.session.query(db.func.sum(RunnerOrder.tip)).filter(
                RunnerOrder.runner_id == current_user.id,
                RunnerOrder.status == 'completed'
            ).scalar() or 0.0
            
            pending_orders = RunnerOrder.query.filter_by(status='pending').order_by(RunnerOrder.created_at.desc()).limit(10).all()
            in_progress_orders = RunnerOrder.query.filter_by(runner_id=current_user.id, status='in_progress').order_by(RunnerOrder.accepted_at.desc(), RunnerOrder.created_at.desc()).limit(5).all()
            available_orders = RunnerOrder.query.filter_by(status='pending').order_by(RunnerOrder.created_at.desc()).limit(10).all()
            recent_orders = RunnerOrder.query.filter_by(runner_id=current_user.id).order_by(RunnerOrder.completed_at.desc(), RunnerOrder.accepted_at.desc(), RunnerOrder.created_at.desc()).limit(5).all()
            
        except Exception as e:
            # 数据库错误或表不存在，使用虚拟数据
            total_orders = 8
            completed_orders = 5
            today_orders = 1
            total_tips = 25.5
            
            # 创建虚拟订单列表
            pending_orders = []
            in_progress_orders = []
            available_orders = []
            recent_orders = []
            
            # 添加一些虚拟订单示例
            for i in range(3):
                class MockOrder:
                    id = i + 1
                    order_number = f"RUN{(i+1):06d}"
                    title = f"代取快递示例{i+1}"
                    service_type = "代取快递"
                    pick_up_location = "菜鸟驿站"
                    delivery_location = f"{i+1}号楼215"
                    tip = 5.0
                    status = 'pending'
                    created_at = datetime.utcnow()
                pending_orders.append(MockOrder())
                available_orders.append(MockOrder())
            
            for i in range(2):
                class MockOrder:
                    id = i + 4
                    order_number = f"RUN{(i+4):06d}"
                    title = f"代买饭示例{i+1}"
                    service_type = "代买饭"
                    pick_up_location = "食堂"
                    delivery_location = f"{i+2}号楼315"
                    tip = 8.0
                    status = 'in_progress'
                    created_at = datetime.utcnow()
                in_progress_orders.append(MockOrder())
                recent_orders.append(MockOrder())
        
        return render_template('runner_dashboard.html',
                               total_orders=total_orders,
                               completed_orders=completed_orders,
                               today_orders=today_orders,
                               total_tips=total_tips,
                               pending_orders=pending_orders,
                               in_progress_orders=in_progress_orders,
                               available_orders=available_orders,
                               recent_orders=recent_orders,
                               can_accept_orders=can_accept_orders)
    
    @app.route('/runner_orders/<status>')
    @login_required
    def runner_orders(status):
        # 跑腿订单列表
        page = request.args.get('page', 1, type=int)
        per_page = 10
        can_accept_orders = is_verified_runner(current_user)
        
        # 根据状态过滤订单
        try:
            if status == 'my_orders':
                # 我发布的订单
                query = RunnerOrder.query.filter_by(creator_id=current_user.id)
            elif status == 'accepted':
                # 我已接的订单
                query = RunnerOrder.query.filter_by(runner_id=current_user.id, status='accepted')
            elif status == 'in_progress':
                query = RunnerOrder.query.filter_by(runner_id=current_user.id, status='in_progress')
            elif status == 'completed':
                # 已完成订单
                query = RunnerOrder.query.filter_by(status='completed')
                if current_user.id:
                    query = query.filter(RunnerOrder.runner_id == current_user.id)
            elif status == 'available':
                # 可接订单（未分配）
                query = RunnerOrder.query.filter_by(status='pending', runner_id=None)
            elif status == 'pending':
                # 待处理订单
                query = RunnerOrder.query.filter_by(status='pending', runner_id=None)
            elif status == 'my_runs':
                query = RunnerOrder.query.filter_by(runner_id=current_user.id).filter(RunnerOrder.status.in_(['accepted', 'in_progress', 'completed']))
            else:
                # 默认显示我的订单
                query = RunnerOrder.query.filter_by(creator_id=current_user.id)
            
            # 分页
            pagination = query.order_by(RunnerOrder.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
            orders = pagination.items
            
        except Exception as e:
            # 数据库错误或表不存在，使用虚拟数据
            pagination = None
            orders = []
            
            # 创建虚拟订单示例
            for i in range(6):
                class MockOrder:
                    id = i + 1
                    order_number = f"RUN{(i+1):06d}"
                    title = f"示例订单{i+1}"
                    service_type = "代取快递"
                    pick_up_location = "菜鸟驿站"
                    delivery_location = f"{i+1}号楼215"
                    tip = 5.0 if i % 2 == 0 else 8.0
                    status = 'pending' if i < 3 else 'in_progress'
                    created_at = datetime.utcnow()
                    creator = type('User', (), {'username': f'用户{i+1}'})()
                orders.append(MockOrder())
        
        return render_template('runner_orders.html', status_filter=status, orders=orders, pagination=pagination, can_accept_orders=can_accept_orders)
    
    # 跑腿订单详情路由
    @app.route('/runner_order_detail/<int:order_id>')
    @login_required
    def runner_order_detail(order_id):
        # 跑腿订单详情（占位符）
        # 尝试获取真实订单，否则返回虚拟订单
        order = RunnerOrder.query.get(order_id)
        if not order:
            # 创建虚拟订单对象
            class MockOrder:
                id = order_id
                order_number = f"RUN{order_id:06d}"
                title = "示例跑腿订单"
                description = "这是一个示例跑腿订单，用于演示。"
                service_type = "代取快递"
                pick_up_location = "菜鸟驿站"
                delivery_location = "3号楼215"
                tip = 5.0
                status = 'pending'
                creator_reviewed = False
                runner_reviewed = False
                creator_id = 1
                runner_id = None
                created_at = datetime.utcnow()
                accepted_at = None
                completed_at = None
                cancelled_at = None
                creator = type('User', (), {'username': '系统用户'})()
                runner = None
            order = MockOrder()
        can_accept_orders = is_verified_runner(current_user)
        delivery_proof_image = None
        try:
            proof_payment = Payment.query.filter(
                Payment.runner_order_id == order.id,
                Payment.description.contains('"flow": "runner_payout"')
            ).order_by(Payment.created_at.desc()).first()
            if proof_payment and proof_payment.description:
                try:
                    proof_data = json.loads(proof_payment.description)
                    delivery_proof_image = proof_data.get('delivery_proof_image')
                except Exception:
                    delivery_proof_image = None
        except Exception:
            delivery_proof_image = None
        return render_template('runner_order_detail.html', order=order, can_accept_orders=can_accept_orders, delivery_proof_image=delivery_proof_image)
    
    # 接受订单路由（对应模板中的 accept_runner_order）
    @app.route('/accept_runner_order/<int:order_id>', methods=['POST'])
    @login_required
    def accept_runner_order(order_id):
        try:
            order = RunnerOrder.query.get_or_404(order_id)
            if order.status != 'pending':
                flash('该订单已被接单或已完成', 'error')
            elif not is_verified_runner(current_user):
                flash('请您先成为跑腿员（管理员认证）后再接单。', 'error')
            elif order.runner_id and order.runner_id != current_user.id:
                flash('该订单已被其他跑腿员接单', 'error')
            elif order.creator_id == current_user.id:
                flash('您不能接自己发布的订单', 'error')
            else:
                order.runner_id = current_user.id
                order.status = 'accepted'
                order.accepted_at = datetime.utcnow()
                db.session.add(Notification(
                    user_id=order.creator_id,
                    content=f'你的跑腿订单《{order.title}》已有跑腿员 {current_user.username} 接单。',
                    notification_type='runner',
                    related_id=order.id,
                    related_type='order'
                ))
                db.session.commit()
                flash('接单成功！请及时开始配送', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'接单失败：{str(e)}', 'error')
        return redirect(url_for('runner_order_detail', order_id=order_id))
    
    # 开始配送路由（对应模板中的 start_runner_order）
    @app.route('/start_runner_order/<int:order_id>', methods=['POST'])
    @login_required
    def start_runner_order(order_id):
        try:
            order = RunnerOrder.query.get_or_404(order_id)
            if order.status != 'accepted':
                flash('订单状态不正确，无法开始配送', 'error')
            elif not is_verified_runner(current_user):
                flash('请您先成为跑腿员（管理员认证）后再接单。', 'error')
            elif order.runner_id != current_user.id:
                flash('您不是该订单的跑腿员，无法开始配送', 'error')
            else:
                order.status = 'in_progress'
                db.session.commit()
                flash('已开始配送！请及时送达', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'开始配送失败：{str(e)}', 'error')
        return redirect(url_for('runner_order_detail', order_id=order_id))
    
    # 完成订单路由（对应模板中的 complete_runner_order）
    @app.route('/complete_runner_order/<int:order_id>', methods=['POST'])
    @login_required
    def complete_runner_order(order_id):
        try:
            order = RunnerOrder.query.get_or_404(order_id)
            if order.status != 'in_progress':
                flash('订单状态不正确，无法完成', 'error')
            elif not is_verified_runner(current_user):
                flash('请您先成为跑腿员（管理员认证）后再接单。', 'error')
            elif order.runner_id != current_user.id:
                flash('您不是该订单的跑腿员，无法完成', 'error')
            else:
                proof_file = request.files.get('delivery_proof')
                if not proof_file or not proof_file.filename:
                    flash('请上传送达照片作为凭证。', 'error')
                    return redirect(url_for('runner_order_detail', order_id=order_id))
                if not allowed_file(proof_file.filename, app.config['ALLOWED_EXTENSIONS']):
                    flash('送达凭证仅支持 png/jpg/jpeg/gif 格式。', 'error')
                    return redirect(url_for('runner_order_detail', order_id=order_id))

                proof_name = secure_filename(proof_file.filename)
                final_name = f"runner_proof_{int(time.time() * 1000)}_{current_user.id}_{proof_name}"
                proof_relative_path = f"uploads/{final_name}"
                proof_file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))

                order.status = 'completed'
                order.completed_at = datetime.utcnow()

                payout_exists = Payment.query.filter(
                    Payment.runner_order_id == order.id,
                    Payment.user_id == current_user.id,
                    Payment.description.contains('"flow": "runner_payout"')
                ).first()
                if not payout_exists:
                    payout = Payment(
                        runner_order_id=order.id,
                        user_id=current_user.id,
                        payment_method='platform_escrow',
                        amount=order.tip or 0.0,
                        status='completed',
                        transaction_id=build_payment_transaction_id('RUNNER_PAYOUT', current_user.id),
                        description=json.dumps({
                            'flow': 'runner_payout',
                            'stage': 'released',
                            'order_number': order.order_number,
                            'delivery_proof_image': proof_relative_path
                        }, ensure_ascii=False),
                        paid_at=datetime.utcnow()
                    )
                    db.session.add(payout)
                db.session.add(Notification(
                    user_id=order.creator_id,
                    content=f'你的跑腿订单《{order.title}》已送达并完成，平台已完成结算。',
                    notification_type='runner',
                    related_id=order.id,
                    related_type='order'
                ))

                db.session.commit()
                flash('订单已完成，平台已结算跑腿费给跑腿员。', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'完成订单失败：{str(e)}', 'error')
        return redirect(url_for('runner_order_detail', order_id=order_id))
    
    # 取消订单路由（对应模板中的 cancel_runner_order）
    @app.route('/cancel_runner_order/<int:order_id>', methods=['POST'])
    @login_required
    def cancel_runner_order(order_id):
        try:
            order = RunnerOrder.query.get_or_404(order_id)
            # 订单创建者或跑腿员可以取消
            if order.creator_id == current_user.id or order.runner_id == current_user.id:
                if order.status in ['pending', 'accepted', 'in_progress']:
                    order.status = 'cancelled'
                    if order.runner_id and order.tip and order.tip > 0:
                        refund = Payment(
                            runner_order_id=order.id,
                            user_id=order.creator_id,
                            payment_method='platform_escrow',
                            amount=order.tip,
                            status='refunded',
                            transaction_id=build_payment_transaction_id('RUNNER_REFUND', order.creator_id),
                            description=json.dumps({
                                'flow': 'runner_refund',
                                'stage': 'returned',
                                'order_number': order.order_number
                            }, ensure_ascii=False),
                            refunded_at=datetime.utcnow()
                        )
                        db.session.add(refund)
                    db.session.commit()
                    flash('订单已取消', 'success')
                else:
                    flash('订单状态不正确，无法取消', 'error')
            else:
                flash('您没有权限取消这个订单', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'取消订单失败：{str(e)}', 'error')
        return redirect(url_for('runner_order_detail', order_id=order_id))
    
    # 显示评价表单路由
    @app.route('/review_runner_order/<int:order_id>')
    @login_required
    def review_runner_order(order_id):
        """显示评价表单"""
        order = RunnerOrder.query.get_or_404(order_id)
        
        # 检查是否有权限评价
        if order.creator_id != current_user.id and order.runner_id != current_user.id:
            flash('您没有权限评价这个订单', 'error')
            return redirect(url_for('runner_order_detail', order_id=order_id))
        
        # 检查订单是否已完成
        if order.status != 'completed':
            flash('只有已完成的订单才能进行评价', 'error')
            return redirect(url_for('runner_order_detail', order_id=order_id))
        
        # 检查是否已经评价过
        review_type = 'creator_to_runner' if current_user.id == order.creator_id else 'runner_to_creator'
        existing_review = RunnerReview.query.filter_by(
            runner_order_id=order_id,
            reviewer_id=current_user.id,
            review_type=review_type
        ).first()
        
        # 获取对方用户信息
        other_user = order.creator if current_user.id == order.runner_id else order.runner
        other_username = other_user.username if other_user else '用户'
        
        return render_template('review_runner_order.html',
                               order=order,
                               other_username=other_username,
                               review_type=review_type,
                               existing_review=existing_review)
    
    # 提交评价路由
    @app.route('/submit_runner_review/<int:order_id>', methods=['POST'])
    @login_required
    def submit_runner_review(order_id):
        """提交评价"""
        try:
            order = RunnerOrder.query.get_or_404(order_id)
            
            # 检查是否有权限评价
            if order.creator_id != current_user.id and order.runner_id != current_user.id:
                flash('您没有权限评价这个订单', 'error')
                return redirect(url_for('runner_order_detail', order_id=order_id))
            
            # 检查订单是否已完成
            if order.status != 'completed':
                flash('只有已完成的订单才能进行评价', 'error')
                return redirect(url_for('runner_order_detail', order_id=order_id))
            
            # 获取表单数据
            rating = request.form.get('rating', type=int)
            content = request.form.get('content', '').strip()
            review_type = 'creator_to_runner' if current_user.id == order.creator_id else 'runner_to_creator'
            
            # 验证评分
            if not rating or rating < 1 or rating > 5:
                flash('请选择1-5星的评分', 'error')
                return redirect(url_for('review_runner_order', order_id=order_id))
            
            # 检查是否已经评价过
            existing_review = RunnerReview.query.filter_by(
                runner_order_id=order_id,
                reviewer_id=current_user.id,
                review_type=review_type
            ).first()
            
            if existing_review:
                # 更新现有评价
                existing_review.rating = rating
                existing_review.content = content
                existing_review.updated_at = datetime.utcnow()
                message = '评价已更新'
            else:
                # 创建新评价
                reviewed_id = order.runner_id if current_user.id == order.creator_id else order.creator_id
                review = RunnerReview(
                    runner_order_id=order_id,
                    reviewer_id=current_user.id,
                    reviewed_id=reviewed_id,
                    review_type=review_type,
                    rating=rating,
                    content=content
                )
                db.session.add(review)
                message = '评价已提交'
            
            # 更新订单评价状态
            if current_user.id == order.creator_id:
                order.creator_reviewed = True
            else:
                order.runner_reviewed = True
            
            # 发送通知
            other_user_id = order.runner_id if current_user.id == order.creator_id else order.creator_id
            notification = Notification(
                user_id=other_user_id,
                content=f'您的跑腿订单《{order.title}》收到了新的评价',
                notification_type='runner_review',
                related_id=order.id,
                related_type='order'
            )
            db.session.add(notification)
            
            db.session.commit()
            flash(message, 'success')
            
        except Exception as e:
            db.session.rollback()
            flash(f'提交评价失败：{str(e)}', 'error')
        
        return redirect(url_for('runner_order_detail', order_id=order_id))
    
    @app.route('/become_runner', methods=['POST'])
    @login_required
    def become_runner():
        if current_user.role in ['runner', 'admin']:
            flash('你已经是认证跑腿员。', 'info')
            return redirect(url_for('runner_orders', status='pending'))
        flash('跑腿员申请已提交，请联系管理员完成认证。', 'success')
        return redirect(url_for('runner_orders', status='pending'))

    @app.route('/admin/runner/approve/<int:user_id>', methods=['POST'])
    @login_required
    def approve_runner(user_id):
        if current_user.role != 'admin':
            flash('仅管理员可认证跑腿员。', 'error')
            return redirect(url_for('profile', user_id=user_id))
        target_user = User.query.get_or_404(user_id)
        target_user.role = 'runner'
        db.session.commit()
        flash(f'已将 {target_user.username} 认证为跑腿员。', 'success')
        return redirect(url_for('profile', user_id=user_id))
    
    @app.route('/forum')
    @login_required
    def forum():
        search_query = (request.args.get('search') or '').strip()

        joined_circles = current_user.joined_circles.order_by(Circle.created_at.desc()).all()
        all_circles_query = Circle.query
        if search_query:
            all_circles_query = all_circles_query.filter(or_(Circle.name.contains(search_query), Circle.description.contains(search_query)))
        all_circles = all_circles_query.order_by(Circle.created_at.desc()).limit(30).all()

        enriched_circles = []
        for circle in all_circles:
            meta = refresh_circle_meta(circle)
            member_count = circle.members.count()
            joined = circle.members.filter(User.id == current_user.id).first() is not None
            unlocks = circle_level_unlocks(meta.level if meta else 1)
            enriched_circles.append({
                'circle': circle,
                'meta': meta,
                'member_count': member_count,
                'joined': joined,
                'admin_limit': circle_admin_limit(meta.level if meta else 1),
                'admin_count': circle.admins.count(),
                'unlocks': unlocks,
                'hot_score': int((meta.exp if meta else 0) + member_count * 5)
            })
        db.session.commit()

        post_query = Post.query.filter(Post.status == 'active', Post.post_type == 'normal')
        if search_query:
            post_query = post_query.filter(or_(Post.title.contains(search_query), Post.content.contains(search_query)))
        recent_posts = post_query.order_by(Post.date_posted.desc()).limit(12).all()

        post_type_summary = {
            'normal': Post.query.filter_by(post_type='normal', status='active').count(),
            'second_hand': Post.query.filter_by(post_type='second_hand', status='active').count(),
            'runner': Post.query.filter_by(post_type='runner', status='active').count(),
            'lost_found': Post.query.filter_by(post_type='lost_found', status='active').count(),
        }

        return render_template('forum.html',
                               circles=joined_circles,
                               search_query=search_query,
                               recent_posts=recent_posts,
                               post_type_summary=post_type_summary,
                               all_circles=enriched_circles)

    @app.route('/create_circle', methods=['GET', 'POST'])
    @login_required
    def create_circle():
        if request.method == 'POST':
            name = (request.form.get('name') or '').strip()
            description = (request.form.get('description') or '').strip()
            circle_type = (request.form.get('type') or 'interest').strip()
            icon = (request.form.get('icon') or '🌟').strip()
            is_public = request.form.get('is_public') == 'on'

            if len(name) < 2 or len(name) > 40:
                flash('圈子名称长度需在 2~40 字之间。', 'error')
                return render_template('create_circle.html')
            normalized_name = normalize_circle_name(name)
            duplicate = Circle.query.filter(func.lower(Circle.name) == name.lower()).first()
            if not duplicate and normalized_name:
                for existed_name, existed_id in Circle.query.with_entities(Circle.name, Circle.id).all():
                    if existed_id and normalize_circle_name(existed_name) == normalized_name:
                        duplicate = existed_id
                        break
            if duplicate:
                flash('圈子名称已存在，请换一个名称。', 'error')
                return render_template('create_circle.html')
            icon_value = icon[0] if icon else '🌟'
            if len(description) < 5 or len(description) > 300:
                flash('圈子简介长度需在 5~300 字之间。', 'error')
                return render_template('create_circle.html')

            circle = Circle(name=name, description=description, circle_type=circle_type, is_public=is_public, creator_id=current_user.id)
            db.session.add(circle)
            db.session.flush()
            circle.members.append(current_user)
            meta = get_or_create_circle_meta(circle.id)
            meta.icon = icon_value
            creator_stats = get_or_create_circle_member_stats(circle.id, current_user.id)
            creator_stats.exp += 20
            creator_stats.level = calc_level_by_exp(creator_stats.exp)
            refresh_circle_meta(circle)
            db.session.commit()
            flash('圈子创建成功，你已成为圈主。', 'success')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        return render_template('create_circle.html')

    @app.route('/circle/<int:circle_id>')
    @login_required
    def circle_detail(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        is_member = circle.members.filter(User.id == current_user.id).first() is not None
        is_creator = circle.creator_id == current_user.id
        is_admin = is_circle_admin_user(current_user.id, circle)
        if not circle.is_public and not is_member and not is_creator:
            flash('该圈子为私密圈子，加入后可查看内容。', 'error')
            return redirect(url_for('forum'))

        meta = refresh_circle_meta(circle)
        page = safe_page_value(request.args.get('page', 1))
        posts_pagination = Post.query.filter_by(circle_id=circle.id, status='active').order_by(Post.date_posted.desc()).paginate(page=page, per_page=15, error_out=False)
        posts = posts_pagination.items

        member_stats = CircleMemberStats.query.filter_by(circle_id=circle.id, user_id=current_user.id).first() if is_member else None
        top_members = CircleMemberStats.query.filter_by(circle_id=circle.id).order_by(CircleMemberStats.exp.desc(), CircleMemberStats.checkin_days.desc()).limit(12).all()
        top_members_enriched = [{'item': item, 'badge': circle_member_badge(item.level)} for item in top_members]
        admin_limit = circle_admin_limit(meta.level if meta else 1)
        admins = circle.admins.order_by(User.level.desc(), User.id.asc()).all()
        admin_permissions = {
            admin_user.id: circle_admin_permission_dict(circle, admin_user.id) for admin_user in admins
        }
        unlocks = circle_level_unlocks(meta.level if meta else 1)
        current_streak = circle_checkin_streak(circle.id, current_user.id, datetime.utcnow().date()) if is_member else 0
        current_badge = circle_member_badge(member_stats.level) if member_stats else ''
        member_level_progress = next_level_progress(member_stats.exp if member_stats else 0)
        member_card_balance = circle_checkin_card_balance(circle.id, current_user.id) if is_member else 0
        now_utc = datetime.utcnow()
        repair_max_date = (now_utc.date() - timedelta(days=1)).isoformat()
        monthly_repairs_used = CircleCheckinRepair.query.filter(
            CircleCheckinRepair.circle_id == circle.id,
            CircleCheckinRepair.user_id == current_user.id,
            func.strftime('%Y-%m', CircleCheckinRepair.created_at) == now_utc.strftime('%Y-%m')
        ).count() if is_member else 0
        can_view_logs = bool(is_creator or is_admin or current_user.role == 'admin')
        recent_logs = CircleActionLog.query.filter_by(circle_id=circle.id).order_by(CircleActionLog.created_at.desc()).limit(20).all() if can_view_logs else []

        db.session.commit()
        return render_template('circle_detail.html',
                               circle=circle,
                               posts=posts,
                               pagination=posts_pagination,
                               is_member=is_member,
                               is_creator=is_creator,
                               is_admin=is_admin,
                               member_stats=member_stats,
                               member_badge=current_badge,
                               current_streak=current_streak,
                               member_level_progress=member_level_progress,
                               member_card_balance=member_card_balance,
                               monthly_repairs_used=monthly_repairs_used,
                               repair_max_date=repair_max_date,
                               circle_meta=meta,
                               circle_unlocks=unlocks,
                               top_members=top_members_enriched,
                               admins=admins,
                               admin_permissions=admin_permissions,
                               recent_logs=recent_logs,
                               can_view_logs=can_view_logs,
                               admin_limit=admin_limit)

    @app.route('/circle/<int:circle_id>/join', methods=['POST'])
    @login_required
    def join_circle(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        already = circle.members.filter(User.id == current_user.id).first() is not None
        if already:
            flash('你已加入该圈子。', 'info')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        circle.members.append(current_user)
        stats = get_or_create_circle_member_stats(circle.id, current_user.id)
        stats.exp += 5
        stats.level = calc_level_by_exp(stats.exp)
        record_circle_action(circle.id, current_user.id, 'join_circle', f'{current_user.username} 加入圈子')
        refresh_circle_meta(circle)
        db.session.commit()
        flash('加入圈子成功，去签到和发帖吧。', 'success')
        return redirect(url_for('circle_detail', circle_id=circle.id))

    @app.route('/circle/<int:circle_id>/leave', methods=['POST'])
    @login_required
    def leave_circle(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        if circle.creator_id == current_user.id:
            flash('圈主不能退出圈子。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        member = circle.members.filter(User.id == current_user.id).first()
        if not member:
            flash('你还未加入该圈子。', 'info')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        circle.members.remove(current_user)
        db.session.execute(circle_admins.delete().where(circle_admins.c.circle_id == circle.id, circle_admins.c.user_id == current_user.id))
        record_circle_action(circle.id, current_user.id, 'leave_circle', f'{current_user.username} 退出圈子')
        refresh_circle_meta(circle)
        db.session.commit()
        flash('已退出圈子。', 'success')
        return redirect(url_for('forum'))

    @app.route('/circle/<int:circle_id>/checkin', methods=['POST'])
    @login_required
    def circle_checkin(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        is_member = circle.members.filter(User.id == current_user.id).first() is not None
        if not is_member:
            flash('加入圈子后才能签到。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        today = datetime.utcnow().date()
        existed = CircleCheckin.query.filter_by(circle_id=circle.id, user_id=current_user.id, checkin_date=today).first()
        if existed:
            flash('今天已经签到过了。', 'info')
            return redirect(url_for('circle_detail', circle_id=circle.id))

        stats = get_or_create_circle_member_stats(circle.id, current_user.id)
        yesterday_streak = circle_checkin_streak(circle.id, current_user.id, today - timedelta(days=1))
        streak_bonus = min(18, yesterday_streak * 2)
        weekly_bonus = 10 if (yesterday_streak + 1) % 7 == 0 else 0
        gained = 10 + streak_bonus + weekly_bonus
        checkin = CircleCheckin(circle_id=circle.id, user_id=current_user.id, checkin_date=today, exp_gained=gained)
        db.session.add(checkin)
        stats.exp += gained
        stats.level = calc_level_by_exp(stats.exp)
        stats.checkin_days = (stats.checkin_days or 0) + 1
        stats.last_checkin_date = today
        bonus_card = 1 if (yesterday_streak + 1) % 7 == 0 else 0
        if bonus_card > 0:
            db.session.add(CircleCheckinCardRecord(
                circle_id=circle.id,
                user_id=current_user.id,
                change_amount=bonus_card,
                reason='连续签到奖励'
            ))
        refresh_circle_meta(circle)
        record_circle_action(
            circle.id,
            current_user.id,
            'circle_checkin',
            f'签到 +{gained}经验，连签{yesterday_streak + 1}天' + ('，获得补签卡1张' if bonus_card else ''),
            target_type='checkin'
        )
        db.session.commit()
        flash(f'签到成功，获得 {gained} 经验，连续签到 {yesterday_streak + 1} 天。', 'success')
        return redirect(url_for('circle_detail', circle_id=circle.id))

    @app.route('/circle/<int:circle_id>/repair_checkin', methods=['POST'])
    @login_required
    def repair_circle_checkin(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        is_member = circle.members.filter(User.id == current_user.id).first() is not None
        if not is_member:
            flash('加入圈子后才能补签。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        meta = refresh_circle_meta(circle)
        unlocks = circle_level_unlocks(meta.level if meta else 1)
        if unlocks['checkin_repair_days'] <= 0:
            flash('圈子等级达到 Lv.3 后开放补签。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        date_raw = (request.form.get('repair_date') or '').strip()
        if not date_raw:
            flash('请选择要补签的日期。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        try:
            repair_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
        except ValueError:
            flash('补签日期格式不正确。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        today = datetime.utcnow().date()
        if repair_date >= today:
            flash('只能补签今天之前的日期。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        max_back_days = unlocks['checkin_repair_days']
        if (today - repair_date).days > max_back_days:
            flash(f'当前圈子最多补签近 {max_back_days} 天。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        existed = CircleCheckin.query.filter_by(circle_id=circle.id, user_id=current_user.id, checkin_date=repair_date).first()
        if existed:
            flash('该日期已签到，无需补签。', 'info')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        current_month = datetime.utcnow().strftime('%Y-%m')
        used_repairs = CircleCheckinRepair.query.filter(
            CircleCheckinRepair.circle_id == circle.id,
            CircleCheckinRepair.user_id == current_user.id,
            func.strftime('%Y-%m', CircleCheckinRepair.created_at) == current_month
        ).count()
        monthly_quota = max(1, unlocks['checkin_repair_days'] // 2 + 1)
        if used_repairs >= monthly_quota:
            flash(f'本月补签次数已用完（{monthly_quota} 次）。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        stats = get_or_create_circle_member_stats(circle.id, current_user.id)
        card_balance = circle_checkin_card_balance(circle.id, current_user.id)
        exp_cost = 4 + min(6, (today - repair_date).days)
        if card_balance <= 0:
            flash('补签卡不足，请通过连续签到获取补签卡。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        if (stats.exp or 0) < exp_cost:
            flash(f'圈子经验不足，补签仍需 {exp_cost} 经验。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        repair_exp_gained = 6
        db.session.add(CircleCheckin(circle_id=circle.id, user_id=current_user.id, checkin_date=repair_date, exp_gained=repair_exp_gained))
        db.session.add(CircleCheckinRepair(circle_id=circle.id, user_id=current_user.id, repaired_date=repair_date, exp_cost=exp_cost))
        db.session.add(CircleCheckinCardRecord(
            circle_id=circle.id,
            user_id=current_user.id,
            change_amount=-1,
            reason='补签消耗'
        ))
        stats.exp = max(0, (stats.exp or 0) - exp_cost + repair_exp_gained)
        stats.level = calc_level_by_exp(stats.exp)
        stats.checkin_days = (stats.checkin_days or 0) + 1
        refresh_circle_meta(circle)
        record_circle_action(circle.id, current_user.id, 'repair_checkin', f'补签 {repair_date.isoformat()}，消耗1张补签卡与{exp_cost}经验', target_type='checkin')
        db.session.commit()
        flash(f'补签成功：消耗1张补签卡与 {exp_cost} 经验，返还 {repair_exp_gained} 经验。', 'success')
        return redirect(url_for('circle_detail', circle_id=circle.id))

    @app.route('/circle/<int:circle_id>/set_admin/<int:user_id>', methods=['POST'])
    @login_required
    def set_circle_admin(circle_id, user_id):
        circle = Circle.query.get_or_404(circle_id)
        if circle.creator_id != current_user.id:
            flash('仅圈主可设置管理员。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        if user_id == circle.creator_id:
            flash('圈主无需设置为管理员。', 'info')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        target = User.query.get_or_404(user_id)
        is_member = circle.members.filter(User.id == target.id).first() is not None
        if not is_member:
            flash('对方尚未加入圈子。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        meta = refresh_circle_meta(circle)
        limit = circle_admin_limit(meta.level if meta else 1)
        admins_count = circle.admins.count()
        already_admin = circle.admins.filter(User.id == target.id).first() is not None
        if not already_admin and admins_count >= limit:
            flash(f'当前圈子最多只能设置 {limit} 位管理员。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        if already_admin:
            circle.admins.remove(target)
            permission = CircleAdminPermission.query.filter_by(circle_id=circle.id, user_id=target.id).first()
            if permission:
                db.session.delete(permission)
            record_circle_action(circle.id, current_user.id, 'remove_admin', f'移除管理员 {target.username}', target_type='user', target_id=target.id)
            flash('已取消该管理员权限。', 'success')
        else:
            circle.admins.append(target)
            permission = get_or_create_circle_admin_permission(circle.id, target.id)
            unlocks = circle_level_unlocks(meta.level if meta else 1)
            permission.can_manage_posts = True
            permission.can_manage_comments = True
            permission.can_pin_posts = bool(unlocks['pin_post'])
            permission.can_feature_posts = bool(unlocks['feature_post'])
            record_circle_action(circle.id, current_user.id, 'set_admin', f'新增管理员 {target.username}', target_type='user', target_id=target.id)
            flash('已设置为圈子管理员。', 'success')
        db.session.commit()
        return redirect(url_for('circle_detail', circle_id=circle.id))

    @app.route('/circle/<int:circle_id>/admin_permission/<int:user_id>', methods=['POST'])
    @login_required
    def update_circle_admin_permission(circle_id, user_id):
        circle = Circle.query.get_or_404(circle_id)
        if circle.creator_id != current_user.id:
            flash('仅圈主可调整管理员权限。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        target = User.query.get_or_404(user_id)
        if circle.admins.filter(User.id == target.id).first() is None:
            flash('该用户不是当前圈子的管理员。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        meta = refresh_circle_meta(circle)
        unlocks = circle_level_unlocks(meta.level if meta else 1)
        permission = get_or_create_circle_admin_permission(circle.id, target.id)
        permission.can_manage_posts = request.form.get('can_manage_posts') == 'on'
        permission.can_manage_comments = request.form.get('can_manage_comments') == 'on'
        requested_feature = request.form.get('can_feature_posts') == 'on'
        requested_pin = request.form.get('can_pin_posts') == 'on'
        permission.can_feature_posts = requested_feature and bool(unlocks['feature_post'])
        permission.can_pin_posts = requested_pin and bool(unlocks['pin_post'])
        record_circle_action(
            circle.id,
            current_user.id,
            'update_admin_permission',
            f'更新 {target.username} 权限：帖{int(permission.can_manage_posts)} 评{int(permission.can_manage_comments)} 置顶{int(permission.can_pin_posts)} 加精{int(permission.can_feature_posts)}',
            target_type='user',
            target_id=target.id
        )
        db.session.commit()
        flash('管理员权限已更新。', 'success')
        return redirect(url_for('circle_detail', circle_id=circle.id))

    @app.route('/circle/<int:circle_id>/post', methods=['POST'])
    @login_required
    def create_circle_post(circle_id):
        circle = Circle.query.get_or_404(circle_id)
        meta = refresh_circle_meta(circle)
        unlocks = circle_level_unlocks(meta.level if meta else 1)
        member = circle.members.filter(User.id == current_user.id).first()
        if not member and circle.creator_id != current_user.id:
            flash('加入圈子后才能在圈子发帖。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        title = (request.form.get('title') or '').strip()
        content = (request.form.get('content') or '').strip()
        if len(title) < 3 or len(title) > 100:
            flash('帖子标题长度需在 3~100 字之间。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        if len(content) < 5 or len(content) > 5000:
            flash('帖子内容长度需在 5~5000 字之间。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        board = Board.query.first()
        if not board:
            board = Board(name='普通交流')
            db.session.add(board)
            db.session.flush()
        images = request.files.getlist('images')
        valid_images = [item for item in images if item and item.filename]
        if len(valid_images) > unlocks['max_post_images']:
            flash(f'当前圈子等级最多上传 {unlocks["max_post_images"]} 张图片。', 'error')
            return redirect(url_for('circle_detail', circle_id=circle.id))
        saved_images = []
        for index, image_file in enumerate(valid_images):
            if not image_file or not image_file.filename:
                continue
            if not allowed_file(image_file.filename, app.config['ALLOWED_EXTENSIONS']):
                flash('圈子帖子图片仅支持 png/jpg/jpeg/gif。', 'error')
                return redirect(url_for('circle_detail', circle_id=circle.id))
            name = secure_filename(image_file.filename)
            final_name = f"circle_post_{int(time.time() * 1000)}_{current_user.id}_{index}_{name}"
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))
            saved_images.append(f"uploads/{final_name}")
        post_obj = Post(
            title=title,
            content=content,
            user_id=current_user.id,
            board_id=board.id,
            circle_id=circle.id,
            post_type='normal',
            images=','.join(saved_images) if saved_images else None,
            status='active'
        )
        db.session.add(post_obj)
        user_stats = get_or_create_circle_member_stats(circle.id, current_user.id)
        user_stats.exp += 8
        user_stats.level = calc_level_by_exp(user_stats.exp)
        refresh_circle_meta(circle)
        record_circle_action(circle.id, current_user.id, 'create_post', f'发布帖子《{title[:20]}》', target_type='post')
        db.session.commit()
        flash('发帖成功，欢迎大家盖楼互动。', 'success')
        return redirect(url_for('post', post_id=post_obj.id))
    # 通知页面路由
    @app.route('/notifications')
    def notifications():
        # 简单的通知页面，返回模板
        # 获取当前用户的通知
        notifications_list = []
        if current_user and current_user.is_authenticated:
            notifications_list = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.date_created.desc()).all()
        
        return render_template('notifications.html', notifications=notifications_list)
    
    # 个人资料页面路由
    @app.route('/profile')
    @login_required
    def profile():
        # 简单的个人资料页面，返回模板
        user_id = request.args.get('user_id', type=int)
        if user_id:
            # 查看其他用户的资料
            user = User.query.get_or_404(user_id)
            is_following = False  # 简化：默认未关注
            is_blocked = False   # 简化：默认未屏蔽
        else:
            # 查看自己的资料
            user = current_user
            is_following = False  # 自己不能关注自己
            is_blocked = False    # 自己不能屏蔽自己

        sold_second_hand_posts = Post.query.filter_by(
            user_id=user.id,
            post_type='second_hand',
            status='sold'
        ).order_by(Post.date_updated.desc(), Post.date_posted.desc()).limit(12).all()
        
        return render_template('profile.html', user=user, is_following=is_following, is_blocked=is_blocked, sold_second_hand_posts=sold_second_hand_posts)
    
    # 编辑个人资料页面路由
    @app.route('/edit_profile', methods=['GET', 'POST'])
    @login_required
    def edit_profile():
        if request.method == 'POST':
            bio = (request.form.get('bio') or '').strip()
            avatar_file = request.files.get('avatar') or request.files.get('file')
            current_user.bio = bio if bio else None
            if avatar_file and avatar_file.filename:
                avatar_path, avatar_error = save_upload_file(avatar_file, 'avatar', current_user.id)
                if avatar_error:
                    flash(avatar_error, 'error')
                    return render_template('edit_profile.html')
                current_user.avatar = avatar_path
            try:
                db.session.commit()
                flash('个人资料更新成功！', 'success')
                return redirect(url_for('profile', user_id=current_user.id))
            except Exception:
                db.session.rollback()
                flash('保存失败，请稍后重试。', 'error')
                return render_template('edit_profile.html')
        return render_template('edit_profile.html')

    @app.route('/api/profile/avatar', methods=['POST'])
    @login_required
    def api_update_avatar():
        avatar_file = request.files.get('avatar') or request.files.get('file')
        avatar_path, avatar_error = save_upload_file(avatar_file, 'avatar', current_user.id)
        if avatar_error:
            return jsonify({'success': False, 'message': avatar_error}), 400
        current_user.avatar = avatar_path
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'message': '头像保存失败，请稍后重试。'}), 500
        return jsonify({'success': True, 'avatar': resolve_avatar_url(current_user), 'avatar_path': avatar_path})
    
    # 消息列表页面路由
    @app.route('/messages')
    @login_required
    def messages_list():
        all_messages = PrivateMessage.query.filter(
            or_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == current_user.id)
        ).order_by(PrivateMessage.sent_at.desc()).all()
        grouped = {}
        for item in all_messages:
            other_user_id = item.receiver_id if item.sender_id == current_user.id else item.sender_id
            if other_user_id not in grouped:
                unread_count = PrivateMessage.query.filter_by(sender_id=other_user_id, receiver_id=current_user.id, is_read=False).count()
                grouped[other_user_id] = {
                    'other_user': User.query.get(other_user_id),
                    'last_message': item,
                    'unread_count': unread_count
                }
        conversations = [value for value in grouped.values() if value['other_user']]
        return render_template('messages_list.html', conversations=conversations)
    
    # 私信对话页面路由
    @app.route('/conversation/<int:user_id>', methods=['GET', 'POST'])
    @login_required
    def conversation(user_id):
        other_user = User.query.get_or_404(user_id)
        if other_user.id == current_user.id:
            flash('不能给自己发私信。', 'error')
            return redirect(url_for('messages_list'))

        prefill_message = (request.args.get('prefill') or '').strip()
        if request.method == 'POST':
            content = (request.form.get('content') or '').strip()
            bargain_price_raw = (request.form.get('bargain_price') or '').strip()
            image_file = request.files.get('image')
            image_segment = ''
            if image_file and image_file.filename:
                if not allowed_file(image_file.filename, app.config['ALLOWED_EXTENSIONS']):
                    flash('私信图片仅支持 png/jpg/jpeg/gif。', 'error')
                    return redirect(url_for('conversation', user_id=other_user.id))
                img_name = secure_filename(image_file.filename)
                final_name = f"pm_{int(time.time() * 1000)}_{current_user.id}_{img_name}"
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], final_name))
                image_segment = f"[img]uploads/{final_name}[/img]"
            bargain_segment = ''
            if bargain_price_raw:
                try:
                    bargain_price = float(bargain_price_raw)
                    if bargain_price > 0:
                        bargain_segment = f"[bargain]{bargain_price:.2f}[/bargain]"
                except ValueError:
                    flash('砍价金额格式不正确。', 'error')
                    return redirect(url_for('conversation', user_id=other_user.id))
            content_final = content
            if image_segment:
                content_final = f"{content_final}\n{image_segment}".strip()
            if bargain_segment:
                content_final = f"{content_final}\n{bargain_segment}".strip()
            if len(content_final) < 1:
                flash('请输入消息内容或上传图片。', 'error')
                return redirect(url_for('conversation', user_id=other_user.id))
            db.session.add(PrivateMessage(sender_id=current_user.id, receiver_id=other_user.id, content=content_final))
            db.session.add(Notification(
                user_id=other_user.id,
                content=f'{current_user.username} 给你发来一条私信。',
                notification_type='message',
                related_id=current_user.id,
                related_type='user'
            ))
            db.session.commit()
            return redirect(url_for('conversation', user_id=other_user.id))

        messages = PrivateMessage.query.filter(
            or_(
                db.and_(PrivateMessage.sender_id == current_user.id, PrivateMessage.receiver_id == other_user.id),
                db.and_(PrivateMessage.sender_id == other_user.id, PrivateMessage.receiver_id == current_user.id)
            )
        ).order_by(PrivateMessage.sent_at.asc()).all()
        unread = [item for item in messages if item.receiver_id == current_user.id and not item.is_read]
        for item in unread:
            item.mark_as_read()
        if unread:
            db.session.commit()
        return render_template('conversation.html', messages=messages, other_user=other_user, prefill_message=prefill_message)
    
    # 我的帖子路由
    @app.route('/my_posts')
    @login_required
    def my_posts():
        filter_type = (request.args.get('filter') or '').strip()
        query = Post.query.filter_by(user_id=current_user.id)
        if filter_type == 'sticky':
            query = query.filter(Post.is_sticky.is_(True))
        if filter_type == 'recent':
            query = query.order_by(Post.date_posted.desc())
        else:
            query = query.order_by(Post.date_posted.desc())
        user_posts = query.limit(100).all()
        return render_template('my_posts.html', user_posts=user_posts)

    @app.route('/my_comments')
    @login_required
    def my_comments():
        user_comments = Comment.query.filter_by(user_id=current_user.id).order_by(Comment.date_posted.desc()).limit(100).all()
        return render_template('my_comments.html', user_comments=user_comments)

    @app.route('/edit_post/<int:post_id>', methods=['GET', 'POST'])
    @login_required
    def edit_post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        if post_obj.user_id != current_user.id and current_user.role != 'admin':
            flash('你没有权限编辑此帖子。', 'error')
            return redirect(url_for('post', post_id=post_id))

        boards = Board.query.order_by(Board.id.asc()).all()
        circles = Circle.query.order_by(Circle.id.asc()).all()

        if request.method == 'POST':
            title = (request.form.get('title') or '').strip()
            content = (request.form.get('content') or '').strip()
            post_type = (request.form.get('post_type') or post_obj.post_type).strip()
            location = (request.form.get('location') or '').strip()
            contact_info = (request.form.get('contact_info') or '').strip()
            circle_id = request.form.get('circle_id', type=int)
            price_raw = (request.form.get('price') or '').strip()
            is_anonymous = request.form.get('is_anonymous') == 'on'
            second_hand_category = (request.form.get('second_hand_category') or 'other').strip()
            second_hand_condition = (request.form.get('second_hand_condition') or '').strip()
            second_hand_trade_method = (request.form.get('second_hand_trade_method') or 'face').strip()
            second_hand_escrow = request.form.get('second_hand_escrow') == 'on'

            if post_type not in valid_post_types:
                post_type = 'normal'

            if len(title) < 3 or len(title) > 100 or len(content) < 5 or len(content) > 5000:
                flash('标题或正文长度不合法。', 'error')
                form_data = request.form.to_dict()
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)

            board = get_or_create_board_for_type(post_type)

            if circle_id:
                circle_obj = Circle.query.get(circle_id)
                if not circle_obj:
                    circle_id = None
                else:
                    is_member = circle_obj.members.filter(User.id == current_user.id).first() is not None
                    if circle_obj.creator_id != current_user.id and not is_member:
                        flash('加入圈子后才可在该圈子发帖。', 'error')
                        form_data = request.form.to_dict()
                        return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)

            price = None
            if price_raw:
                try:
                    price = float(price_raw)
                    if price < 0:
                        raise ValueError()
                except ValueError:
                    flash('价格格式不正确。', 'error')
                    form_data = request.form.to_dict()
                    return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)
            if post_type == 'second_hand' and price is None:
                flash('二手交易请填写价格。', 'error')
                form_data = request.form.to_dict()
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)

            image_files = request.files.getlist('images')
            saved_images = []
            for index, image_file in enumerate(image_files):
                if not image_file or not image_file.filename:
                    continue
                if not allowed_file(image_file.filename, app.config['ALLOWED_EXTENSIONS']):
                    flash('仅支持 png/jpg/jpeg/gif 图片格式。', 'error')
                    form_data = request.form.to_dict()
                    return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)
                original_name = secure_filename(image_file.filename)
                unique_name = f"{int(time.time() * 1000)}_{current_user.id}_{index}_{original_name}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                image_file.save(save_path)
                saved_images.append(f"uploads/{unique_name}")

            try:
                post_obj.title = title
                post_obj.content = content
                post_obj.post_type = post_type
                post_obj.board_id = board.id
                post_obj.circle_id = circle_id
                post_obj.location = location[:200] if location else None
                post_obj.contact_info = contact_info[:200] if contact_info else None
                post_obj.price = price
                post_obj.is_anonymous = is_anonymous
                post_obj.date_updated = datetime.utcnow()
                post_obj.metadata_json = dump_metadata({
                    'category': second_hand_category if post_type == 'second_hand' else '',
                    'condition_label': second_hand_condition if post_type == 'second_hand' else '',
                    'trade_method': second_hand_trade_method if post_type == 'second_hand' else 'face',
                    'escrow_enabled': bool(second_hand_escrow) if post_type == 'second_hand' else False,
                    'listing_state': second_hand_meta(post_obj).get('listing_state', 'on_sale')
                })
                if saved_images:
                    post_obj.images = ','.join(saved_images)
                if post_obj.circle_id:
                    refresh_circle_meta(Circle.query.get(post_obj.circle_id))
                db.session.commit()
                flash('帖子已更新。', 'success')
                return redirect(url_for('post', post_id=post_obj.id))
            except Exception:
                db.session.rollback()
                flash('更新失败，请稍后重试。', 'error')
                form_data = request.form.to_dict()
                return render_template('new_post.html', post_type=post_type, boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)

        form_data = {
            'circle_id': str(post_obj.circle_id or ''),
            'post_type': post_obj.post_type or 'normal',
            'title': post_obj.title or '',
            'content': post_obj.content or '',
            'price': post_obj.price if post_obj.price is not None else '',
            'location': post_obj.location or '',
            'contact_info': post_obj.contact_info or '',
            'is_anonymous': 'on' if post_obj.is_anonymous else '',
            'second_hand_category': second_hand_meta(post_obj).get('category', 'other'),
            'second_hand_condition': second_hand_meta(post_obj).get('condition_label', ''),
            'second_hand_trade_method': second_hand_meta(post_obj).get('trade_method', 'face'),
            'second_hand_escrow': 'on' if second_hand_meta(post_obj).get('escrow_enabled') else '',
            'circle_search': post_obj.circle.name if post_obj.circle else ''
        }
        return render_template('new_post.html', post_type=post_obj.post_type or 'normal', boards=boards, circles=circles, form_data=form_data, edit_mode=True, post_to_edit=post_obj)

    @app.route('/delete_post/<int:post_id>', methods=['POST'])
    @login_required
    def delete_post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        can_circle_delete = can_moderate_circle_post(post_obj, current_user, 'can_manage_posts')
        if post_obj.user_id != current_user.id and current_user.role != 'admin' and not can_circle_delete:
            flash('你没有权限删除此帖子。', 'error')
            return redirect(url_for('post', post_id=post_id))
        try:
            owner = User.query.get(post_obj.user_id)
            circle_id = post_obj.circle_id
            post_title = post_obj.title
            db.session.delete(post_obj)
            if owner:
                owner.post_count = max((owner.post_count or 0) - 1, 0)
            if circle_id:
                refresh_circle_meta(Circle.query.get(circle_id))
                record_circle_action(circle_id, current_user.id, 'delete_post', f'删除帖子《{post_title[:20]}》', target_type='post', target_id=post_id)
            db.session.commit()
            flash('帖子已删除。', 'success')
            return redirect(url_for('my_posts'))
        except Exception:
            db.session.rollback()
            flash('删除失败，请稍后重试。', 'error')
            return redirect(url_for('post', post_id=post_id))

    @app.route('/post/<int:post_id>/status/<string:status>', methods=['POST'])
    @login_required
    def update_post_status(post_id, status):
        post_obj = Post.query.get_or_404(post_id)
        can_circle_update = can_moderate_circle_post(post_obj, current_user, 'can_manage_posts')
        if post_obj.user_id != current_user.id and current_user.role != 'admin' and not can_circle_update:
            flash('你没有权限修改帖子状态。', 'error')
            return redirect(url_for('post', post_id=post_id))
        valid_status = {'active', 'trading', 'sold', 'resolved', 'closed'}
        if status not in valid_status:
            flash('状态值无效。', 'error')
            return redirect(url_for('post', post_id=post_id))
        try:
            post_obj.status = status
            post_obj.date_updated = datetime.utcnow()
            if post_obj.circle_id:
                record_circle_action(post_obj.circle_id, current_user.id, 'update_post_status', f'帖子《{post_obj.title[:20]}》状态改为 {status}', target_type='post', target_id=post_obj.id)
            db.session.commit()
            flash('帖子状态已更新。', 'success')
        except Exception:
            db.session.rollback()
            flash('更新状态失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=post_id))

    @app.route('/collect_post/<int:post_id>', methods=['POST'])
    @login_required
    def collect_post(post_id):
        Post.query.get_or_404(post_id)
        existing = Collection.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if existing:
            flash('你已收藏过该帖子。', 'info')
            return redirect(url_for('post', post_id=post_id))
        try:
            db.session.add(Collection(user_id=current_user.id, post_id=post_id))
            db.session.commit()
            flash('收藏成功。', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('你已收藏过该帖子。', 'info')
        except Exception:
            db.session.rollback()
            flash('收藏失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=post_id))

    @app.route('/like_post/<int:post_id>', methods=['POST'])
    @login_required
    def like_post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
        if existing:
            flash('你已点赞过该帖子。', 'info')
            return redirect(url_for('post', post_id=post_id))
        try:
            db.session.add(Like(user_id=current_user.id, post_id=post_id))
            post_obj.like_count = (post_obj.like_count or 0) + 1
            if post_obj.circle_id:
                refresh_circle_meta(Circle.query.get(post_obj.circle_id))
            db.session.commit()
            flash('点赞成功。', 'success')
        except IntegrityError:
            db.session.rollback()
            flash('你已点赞过该帖子。', 'info')
        except Exception:
            db.session.rollback()
            flash('点赞失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=post_id))

    @app.route('/sticky_post/<int:post_id>', methods=['POST'])
    @login_required
    def sticky_post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        can_circle_pin = can_moderate_circle_post(post_obj, current_user, 'can_pin_posts')
        if current_user.role != 'admin' and not can_circle_pin:
            flash('仅管理员可操作。', 'error')
            return redirect(url_for('post', post_id=post_id))
        try:
            post_obj.is_sticky = not bool(post_obj.is_sticky)
            post_obj.date_updated = datetime.utcnow()
            if post_obj.circle_id:
                record_circle_action(post_obj.circle_id, current_user.id, 'toggle_sticky', f'帖子《{post_obj.title[:20]}》置顶状态：{int(post_obj.is_sticky)}', target_type='post', target_id=post_obj.id)
            db.session.commit()
            flash('置顶状态已切换。', 'success')
        except Exception:
            db.session.rollback()
            flash('操作失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=post_id))

    @app.route('/essence_post/<int:post_id>', methods=['POST'])
    @login_required
    def essence_post(post_id):
        post_obj = Post.query.get_or_404(post_id)
        can_circle_feature = can_moderate_circle_post(post_obj, current_user, 'can_feature_posts')
        if current_user.role != 'admin' and not can_circle_feature:
            flash('仅管理员可操作。', 'error')
            return redirect(url_for('post', post_id=post_id))
        try:
            post_obj.is_essence = not bool(post_obj.is_essence)
            post_obj.date_updated = datetime.utcnow()
            if post_obj.circle_id:
                record_circle_action(post_obj.circle_id, current_user.id, 'toggle_essence', f'帖子《{post_obj.title[:20]}》精华状态：{int(post_obj.is_essence)}', target_type='post', target_id=post_obj.id)
            db.session.commit()
            flash('精华状态已切换。', 'success')
        except Exception:
            db.session.rollback()
            flash('操作失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=post_id))

    @app.route('/delete_comment/<int:comment_id>', methods=['POST'])
    @login_required
    def delete_comment(comment_id):
        comment = Comment.query.get_or_404(comment_id)
        post_obj = Post.query.get(comment.post_id)
        can_circle_delete_comment = can_moderate_circle_post(post_obj, current_user, 'can_manage_comments')
        if comment.user_id != current_user.id and current_user.role != 'admin' and not can_circle_delete_comment:
            flash('你没有权限删除此评论。', 'error')
            return redirect(url_for('post', post_id=comment.post_id) + '#comments')
        try:
            target_comment_id = comment.id
            db.session.delete(comment)
            if post_obj:
                post_obj.comment_count = max((post_obj.comment_count or 0) - 1, 0)
                if post_obj.circle_id:
                    refresh_circle_meta(Circle.query.get(post_obj.circle_id))
                    record_circle_action(post_obj.circle_id, current_user.id, 'delete_comment', '删除一条评论', target_type='comment', target_id=target_comment_id)
            db.session.commit()
            flash('评论已删除。', 'success')
        except Exception:
            db.session.rollback()
            flash('删除评论失败，请稍后重试。', 'error')
        return redirect(url_for('post', post_id=comment.post_id) + '#comments')
    
    # 我的二手路由
    @app.route('/my_second_hand')
    @login_required
    def my_second_hand():
        return render_template('my_second_hand.html')
    
    # 我的订单路由
    @app.route('/my_orders')
    @login_required
    def my_orders():
        order_type = (request.args.get('type') or 'all').strip()
        orders = []
        if order_type in ('all', 'second_hand'):
            trades = Trade.query.filter(or_(Trade.buyer_id == current_user.id, Trade.seller_id == current_user.id)).order_by(Trade.created_at.desc()).all()
            for trade_obj in trades:
                post_obj = trade_obj.post
                if not post_obj:
                    continue
                display_status_map = {
                    'pending': '待付款',
                    'paid': '待发货',
                    'shipped': '待收货',
                    'delivered': '待确认',
                    'completed': '已完成',
                    'cancelled': '已取消',
                    'disputed': '售后中'
                }
                orders.append({
                    'id': post_obj.id,
                    'title': post_obj.title,
                    'date_posted': trade_obj.created_at,
                    'post_type': 'second_hand',
                    'status': trade_obj.trade_status,
                    'status_label': display_status_map.get(trade_obj.trade_status, trade_obj.trade_status),
                    'content': post_obj.content,
                    'price': trade_obj.price,
                    'location': post_obj.location
                })
        if order_type in ('all', 'runner'):
            runner_orders = RunnerOrder.query.filter(or_(RunnerOrder.creator_id == current_user.id, RunnerOrder.runner_id == current_user.id)).order_by(RunnerOrder.created_at.desc()).all()
            for runner_item in runner_orders:
                orders.append({
                    'id': runner_item.post_id or 0,
                    'title': runner_item.title,
                    'date_posted': runner_item.created_at,
                    'post_type': 'runner',
                    'status': runner_item.status,
                    'status_label': runner_item.status,
                    'content': runner_item.description,
                    'price': runner_item.tip,
                    'location': runner_item.delivery_location
                })
        orders.sort(key=lambda x: x['date_posted'], reverse=True)
        return render_template('my_orders.html', orders=orders, order_type=order_type)
    
    # 我的收藏路由
    @app.route('/my_collections')
    @login_required
    def my_collections():
        return render_template('my_collections.html')
    
    # 我的关注路由
    @app.route('/my_following')
    @login_required
    def my_following():
        return render_template('my_following.html')
    
    # 我的粉丝路由
    @app.route('/my_followers')
    @login_required
    def my_followers():
        return render_template('my_followers.html')
    
    # 隐私设置路由
    @app.route('/privacy_settings')
    @login_required
    def privacy_settings():
        return render_template('privacy_settings.html')
    
    # 关注用户路由
    @app.route('/follow_user/<int:user_id>', methods=['POST'])
    @login_required
    def follow_user(user_id):
        flash('关注成功', 'success')
        return redirect(url_for('profile', user_id=user_id))
    
    # 取消关注用户路由
    @app.route('/unfollow_user/<int:user_id>', methods=['POST'])
    @login_required
    def unfollow_user(user_id):
        flash('已取消关注', 'success')
        return redirect(url_for('profile', user_id=user_id))
    
    # 屏蔽用户路由
    @app.route('/block_user/<int:user_id>', methods=['POST'])
    @login_required
    def block_user(user_id):
        flash('用户已屏蔽', 'success')
        return redirect(url_for('profile', user_id=user_id))
    
    # 取消屏蔽用户路由
    @app.route('/unblock_user/<int:user_id>', methods=['POST'])
    @login_required
    def unblock_user(user_id):
        flash('已取消屏蔽', 'success')
        return redirect(url_for('profile', user_id=user_id))
    
    # 举报路由
    @app.route('/report')
    @login_required
    def report():
        # 获取被举报用户ID（如果存在）
        user_id = request.args.get('user_id', type=int)
        return render_template('report.html', user_id=user_id)

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template('about.html'), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        db.session.rollback()
        flash('系统繁忙，请稍后重试。', 'error')
        return redirect(url_for('home'))
    
    return app

# 创建应用实例
app = create_app()

# 数据库初始化函数
def init_database():
    with app.app_context():
        try:
            # 创建表（如果不存在）
            db.create_all()
            print("数据库表创建成功")
            
            # 检查是否需要初始化数据
            if not Board.query.first():
                # 创建默认贴吧
                default_boards = ['校园生活', '学习交流', '兴趣爱好', '求助问答', '二手交易']
                for board_name in default_boards:
                    try:
                        board = Board(name=board_name)
                        db.session.add(board)
                        print(f"创建贴吧: {board_name}")
                    except Exception as e:
                        print(f"创建贴吧 {board_name} 时出错: {e}")
                
                # 创建默认圈子
                # 基础圈子
                basic_circles = [
                    {'name': '广场', 'description': '全校性综合交流区', 'circle_type': 'basic'},
                    {'name': '学院圈', 'description': '按学院划分的交流空间', 'circle_type': 'basic'},
                    {'name': '年级圈', 'description': '同年级学生的交流平台', 'circle_type': 'basic'},
                    {'name': '宿舍楼圈', 'description': '基于地理位置的近距离交流', 'circle_type': 'basic'}
                ]
                
                # 兴趣圈子
                interest_circles = [
                    {'name': '摄影圈', 'description': '分享摄影作品和技巧', 'circle_type': 'interest'},
                    {'name': '电竞圈', 'description': '游戏爱好者的交流空间', 'circle_type': 'interest'},
                    {'name': '考研圈', 'description': '考研信息分享和交流', 'circle_type': 'interest'},
                    {'name': '美食圈', 'description': '分享校园内外美食', 'circle_type': 'interest'}
                ]
                
                # 临时圈子
                temporary_circles = [
                    {'name': '校园马拉松', 'description': '马拉松活动交流', 'circle_type': 'temporary'},
                    {'name': '十佳歌手', 'description': '校园歌手大赛交流', 'circle_type': 'temporary'}
                ]
                
                # 创建所有圈子
                all_circles = basic_circles + interest_circles + temporary_circles
                for circle_data in all_circles:
                    try:
                        circle = Circle(
                            name=circle_data['name'],
                            description=circle_data['description'],
                            circle_type=circle_data['circle_type']
                        )
                        db.session.add(circle)
                        print(f"创建圈子: {circle_data['name']}")
                    except Exception as e:
                        print(f"创建圈子 {circle_data['name']} 时出错: {e}")
                
                # 创建默认徽章
                default_badges = [
                    {'name': '学习博主', 'description': '优质学习内容创作者', 'icon': 'book.png'},
                    {'name': '探店达人', 'description': '校园周边探店专家', 'icon': 'food.png'},
                    {'name': '摄影大师', 'description': '优秀摄影作品创作者', 'icon': 'camera.png'},
                    {'name': '校园红人', 'description': '校园内有影响力的用户', 'icon': 'star.png'}
                ]
                
                for badge_data in default_badges:
                    try:
                        badge = Badge(
                            name=badge_data['name'],
                            description=badge_data['description'],
                            icon=badge_data['icon']
                        )
                        db.session.add(badge)
                        print(f"创建徽章: {badge_data['name']}")
                    except Exception as e:
                        print(f"创建徽章 {badge_data['name']} 时出错: {e}")
                
                # 创建默认管理员账号
                try:
                    admin = User(username='Socrates', password=generate_password_hash('Jiang0531'), role='admin')
                    db.session.add(admin)
                    print("创建管理员账号: Socrates")
                    
                    # 提交以获取用户ID
                    db.session.commit()
                    
                    # 创建默认通知
                    try:
                        system_notification = Notification(
                            content='欢迎使用校园贴吧！这是一个交流分享的平台，希望大家遵守吧规，共同维护良好的社区环境。',
                            user_id=admin.id,
                            notification_type='system'
                        )
                        db.session.add(system_notification)
                        print("创建系统通知")
                    except Exception as e:
                        print(f"创建系统通知时出错: {e}")
                except Exception as e:
                    print(f"创建管理员账号时出错: {e}")
                
                # 提交所有更改
                db.session.commit()
                print("数据库初始化成功")
            else:
                print("数据库已初始化，跳过初始化步骤")
        except Exception as e:
            print(f"数据库初始化时出错: {e}")
            db.session.rollback()

# 初始化数据库
init_database()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
app = app
