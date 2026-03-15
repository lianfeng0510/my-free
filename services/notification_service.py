from models import db, Notification
from datetime import datetime

class NotificationService:
    """通知服务类，封装通知相关的业务逻辑"""
    
    @staticmethod
    def create_payment_success_notification(user_id, trade_id, amount):
        """创建支付成功通知"""
        notification = Notification(
            content=f'您的交易 #{trade_id} 支付成功，金额 ¥{amount}',
            user_id=user_id,
            notification_type='trade',
            related_id=trade_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def create_trade_status_notification(user_id, trade_id, status):
        """创建交易状态变更通知"""
        status_messages = {
            'active': '帖子已重新激活',
            'sold': '帖子已标记为已出',
            'resolved': '帖子已标记为已解决',
            'closed': '帖子已关闭'
        }
        content = f'您的交易 #{trade_id} 状态已更新为{status_messages.get(status, status)}'
        
        notification = Notification(
            content=content,
            user_id=user_id,
            notification_type='trade',
            related_id=trade_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def create_reply_notification(user_id, post_id, content):
        """创建回复通知"""
        notification = Notification(
            content=f'有人回复了你的评论: {content[:50]}...',
            user_id=user_id,
            notification_type='reply',
            related_id=post_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def create_runner_order_notification(user_id, order_id, message):
        """创建跑腿订单通知"""
        notification = Notification(
            content=message,
            user_id=user_id,
            notification_type='runner',
            related_id=order_id
        )
        db.session.add(notification)
        db.session.commit()
        return notification
    
    @staticmethod
    def mark_notifications_as_read(user_id):
        """标记所有通知为已读"""
        Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
        db.session.commit()
