from models import db, Trade, Payment, Notification
from datetime import datetime

class TradeService:
    """交易服务类，封装交易相关的业务逻辑"""
    
    @staticmethod
    def create_trade(post_id, buyer_id, seller_id, price):
        """创建交易"""
        trade = Trade(
            post_id=post_id,
            buyer_id=buyer_id,
            seller_id=seller_id,
            price=price,
            trade_status='pending',
            payment_status='unpaid',
            escrow_held=True
        )
        db.session.add(trade)
        db.session.commit()
        return trade
    
    @staticmethod
    def process_payment(trade_id, user_id, payment_method='simulated'):
        """处理支付"""
        trade = Trade.query.get_or_404(trade_id)
        
        # 验证权限
        if trade.buyer_id != user_id:
            raise PermissionError("无权操作此交易")
        
        # 验证状态
        if trade.payment_status != 'unpaid':
            raise ValueError("交易已支付或已取消")
        
        # 创建支付记录
        payment = Payment(
            trade_id=trade.id,
            user_id=user_id,
            payment_method=payment_method,
            amount=trade.price,
            currency='CNY',
            status='completed',
            description=f'二手交易支付：{trade.post.title}',
            paid_at=datetime.utcnow()
        )
        db.session.add(payment)
        
        # 更新交易状态
        trade.payment_status = 'paid'
        trade.trade_status = 'paid'
        trade.payment_date = datetime.utcnow()
        
        db.session.commit()
        return payment
    
    @staticmethod
    def ship_trade(trade_id, user_id):
        """卖家发货"""
        trade = Trade.query.get_or_404(trade_id)
        
        if trade.seller_id != user_id:
            raise PermissionError("无权操作此交易")
        
        if trade.trade_status != 'paid':
            raise ValueError("交易未支付，无法发货")
        
        trade.trade_status = 'shipped'
        trade.shipping_date = datetime.utcnow()
        db.session.commit()
        
        return trade
    
    @staticmethod
    def deliver_trade(trade_id, user_id):
        """买家确认收货"""
        trade = Trade.query.get_or_404(trade_id)
        
        if trade.buyer_id != user_id:
            raise PermissionError("无权操作此交易")
        
        if trade.trade_status != 'shipped':
            raise ValueError("交易未发货，无法确认收货")
        
        trade.trade_status = 'delivered'
        trade.delivery_date = datetime.utcnow()
        db.session.commit()
        
        return trade
    
    @staticmethod
    def complete_trade(trade_id, user_id):
        """卖家确认收款（担保释放）"""
        trade = Trade.query.get_or_404(trade_id)
        
        if trade.seller_id != user_id:
            raise PermissionError("无权操作此交易")
        
        if trade.trade_status != 'delivered':
            raise ValueError("交易未确认收货，无法完成")
        
        trade.trade_status = 'completed'
        trade.completed_at = datetime.utcnow()
        db.session.commit()
        
        return trade
    
    @staticmethod
    def cancel_trade(trade_id, user_id):
        """取消交易"""
        trade = Trade.query.get_or_404(trade_id)
        
        if trade.buyer_id != user_id and trade.seller_id != user_id:
            raise PermissionError("无权操作此交易")
        
        if trade.trade_status in ['completed', 'cancelled']:
            raise ValueError("交易已结束，无法取消")
        
        trade.trade_status = 'cancelled'
        trade.cancelled_at = datetime.utcnow()
        db.session.commit()
        
        return trade
