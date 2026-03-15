#!/usr/bin/env python
"""
测试二手交易功能：扮演卖家和买家
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Post, Trade
from werkzeug.security import generate_password_hash
from datetime import datetime
import json

def test_seller_create_product():
    """测试卖家创建二手商品"""
    print("=== 测试卖家创建二手商品 ===")
    
    # 检查是否已有测试卖家
    seller = User.query.filter_by(username='test_seller').first()
    if not seller:
        seller = User(
            username='test_seller',
            password=generate_password_hash('test123')
        )
        db.session.add(seller)
        db.session.commit()
        print(f"创建卖家用户: {seller.username} (ID: {seller.id})")
    else:
        print(f"使用现有卖家用户: {seller.username} (ID: {seller.id})")
    
    # 创建二手商品帖子
    post = Post(
        title='测试二手教科书 - 计算机科学导论',
        content='几乎全新的计算机科学导论教科书，原价200元，现价100元转让。',
        author=seller,
        board_id=1,  # 假设贴吧ID为1
        post_type='second_hand',
        price=100.0,
        location='图书馆门口',
        contact_info='微信: seller_test'
    )
    
    db.session.add(post)
    db.session.commit()
    
    print(f"卖家创建二手商品成功!")
    print(f"商品标题: {post.title}")
    print(f"商品价格: ¥{post.price}")
    print(f"商品ID: {post.id}")
    print(f"商品类型: {post.post_type}")
    
    return seller, post

def test_buyer_purchase_product(seller_id, post_id):
    """测试买家购买二手商品"""
    print("\n=== 测试买家购买二手商品 ===")
    
    # 重新查询卖家和商品
    seller = User.query.get(seller_id)
    post = Post.query.get(post_id)
    
    # 创建测试买家用户
    buyer = User.query.filter_by(username='test_buyer').first()
    if not buyer:
        buyer = User(
            username='test_buyer',
            password=generate_password_hash('test123')
        )
        db.session.add(buyer)
        db.session.commit()
        print(f"创建买家用户: {buyer.username} (ID: {buyer.id})")
    else:
        print(f"使用现有买家用户: {buyer.username} (ID: {buyer.id})")
    
    # 检查是否可以创建交易
    existing_trade = Trade.query.filter_by(post_id=post_id, buyer_id=buyer.id).filter(
        Trade.trade_status.in_(['pending', 'payment_pending', 'paid', 'shipped'])
    ).first()
    
    if existing_trade:
        print(f"买家已有进行中的交易: 交易ID {existing_trade.id}")
        return buyer, existing_trade
    
    # 创建担保交易
    trade = Trade(
        post_id=post_id,
        buyer_id=buyer.id,
        seller_id=seller_id,
        price=post.price,
        trade_status='pending',
        payment_status='unpaid',
        escrow_held=True
    )
    
    db.session.add(trade)
    db.session.commit()
    
    print(f"买家创建担保交易成功!")
    print(f"交易ID: {trade.id}")
    print(f"交易金额: ¥{trade.price}")
    print(f"交易状态: {trade.trade_status}")
    print(f"支付状态: {trade.payment_status}")
    
    return buyer, trade

def test_payment_process(trade):
    """测试支付流程"""
    print("\n=== 测试支付流程 ===")
    
    # 模拟支付
    if trade.payment_status == 'unpaid':
        trade.payment_status = 'paid'
        trade.trade_status = 'paid'
        trade.payment_date = datetime.utcnow()
        db.session.commit()
        
        print(f"支付成功!")
        print(f"支付时间: {trade.payment_date}")
        print(f"支付后状态: {trade.trade_status}")
    else:
        print(f"交易已支付或已取消: {trade.payment_status}")
    
    return trade

def test_seller_ship(trade):
    """测试卖家发货"""
    print("\n=== 测试卖家发货 ===")
    
    if trade.trade_status == 'paid':
        trade.trade_status = 'shipped'
        trade.shipping_date = datetime.utcnow()
        db.session.commit()
        
        print(f"卖家发货成功!")
        print(f"发货时间: {trade.shipping_date}")
        print(f"发货后状态: {trade.trade_status}")
    else:
        print(f"交易未支付，无法发货: {trade.trade_status}")
    
    return trade

def test_buyer_receive(trade):
    """测试买家确认收货"""
    print("\n=== 测试买家确认收货 ===")
    
    if trade.trade_status == 'shipped':
        trade.trade_status = 'delivered'
        trade.delivery_date = datetime.utcnow()
        db.session.commit()
        
        print(f"买家确认收货成功!")
        print(f"收货时间: {trade.delivery_date}")
        print(f"收货后状态: {trade.trade_status}")
    else:
        print(f"交易未发货，无法确认收货: {trade.trade_status}")
    
    return trade

def test_seller_complete(trade):
    """测试卖家确认收款"""
    print("\n=== 测试卖家确认收款 ===")
    
    if trade.trade_status == 'delivered':
        trade.trade_status = 'completed'
        trade.completed_at = datetime.utcnow()
        db.session.commit()
        
        print(f"卖家确认收款成功!")
        print(f"完成时间: {trade.completed_at}")
        print(f"最终状态: {trade.trade_status}")
        print("✅ 交易完整流程测试完成!")
    else:
        print(f"交易未确认收货，无法完成: {trade.trade_status}")
    
    return trade

def main():
    """主测试函数"""
    print("开始测试二手交易功能...")
    
    with app.app_context():
        try:
            # 1. 卖家创建商品
            seller, post = test_seller_create_product()
            
            # 2. 买家购买商品
            buyer, trade = test_buyer_purchase_product(seller.id, post.id)
            
            # 3. 支付流程
            trade = test_payment_process(trade)
            
            # 4. 卖家发货
            trade = test_seller_ship(trade)
            
            # 5. 买家收货
            trade = test_buyer_receive(trade)
            
            # 6. 卖家确认收款
            trade = test_seller_complete(trade)
            
            print("\n" + "="*50)
            print("🎉 二手交易功能测试完成!")
            print(f"商品: {post.title}")
            print(f"卖家: {seller.username}")
            print(f"买家: {buyer.username}")
            print(f"交易金额: ¥{trade.price}")
            print(f"最终状态: {trade.trade_status}")
            
        except Exception as e:
            print(f"测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)