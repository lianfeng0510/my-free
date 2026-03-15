#!/usr/bin/env python
"""
测试跑腿功能：扮演客户和跑腿员
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Post, RunnerOrder, generate_order_number
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def test_customer_create_order():
    """测试客户创建跑腿订单"""
    print("=== 测试客户创建跑腿订单 ===")
    
    # 创建测试客户用户
    customer = User.query.filter_by(username='test_customer').first()
    if not customer:
        customer = User(
            username='test_customer',
            password=generate_password_hash('test123')
        )
        db.session.add(customer)
        db.session.commit()
        print(f"创建客户用户: {customer.username} (ID: {customer.id})")
    else:
        print(f"使用现有客户用户: {customer.username} (ID: {customer.id})")
    
    # 创建跑腿帖子
    post = Post(
        title='急需帮忙取快递 - 东门快递点',
        content='需要帮忙从东门快递点取一个包裹送到宿舍3号楼，包裹不大，愿意支付10元小费。',
        author=customer,
        board_id=1,
        post_type='runner',
        price=10.0,  # 小费
        location='东门快递点',
        contact_info='电话: 13800138000'
    )
    
    db.session.add(post)
    db.session.commit()
    
    print(f"客户创建跑腿订单成功!")
    print(f"订单标题: {post.title}")
    print(f"订单小费: ¥{post.price}")
    print(f"订单ID: {post.id}")
    
    return customer, post

def test_runner_accept_order(post_id):
    """测试跑腿员接单"""
    print("\n=== 测试跑腿员接单 ===")
    
    # 创建测试跑腿员用户
    runner = User.query.filter_by(username='test_runner').first()
    if not runner:
        runner = User(
            username='test_runner',
            password=generate_password_hash('test123')
        )
        db.session.add(runner)
        db.session.commit()
        print(f"创建跑腿员用户: {runner.username} (ID: {runner.id})")
    else:
        print(f"使用现有跑腿员用户: {runner.username} (ID: {runner.id})")
    
    # 查询跑腿帖子
    post = Post.query.get(post_id)
    
    # 创建跑腿订单记录，使用帖子信息填充必需字段
    order_number = generate_order_number()
    runner_order = RunnerOrder(
        order_number=order_number,
        title=f"跑腿订单：{post.title}",
        description=post.content,
        service_type='代取快递',
        pick_up_location=post.location if post.location else '东门快递点',
        delivery_location='宿舍3号楼',
        tip=post.price if post.price else 10.0,
        creator_id=post.author.id,
        runner_id=runner.id,
        post_id=post_id,
        status='accepted',
        accepted_at=datetime.utcnow()
    )
    
    db.session.add(runner_order)
    db.session.commit()
    
    print(f"跑腿员接单成功!")
    print(f"跑腿订单ID: {runner_order.id}")
    print(f"订单号: {runner_order.order_number}")
    print(f"小费金额: ¥{runner_order.tip}")
    print(f"订单状态: {runner_order.status}")
    
    return runner, runner_order

def test_runner_start_delivery(runner_order_id):
    """测试跑腿员开始配送"""
    print("\n=== 测试跑腿员开始配送 ===")
    
    runner_order = RunnerOrder.query.get(runner_order_id)
    
    if runner_order.status == 'accepted':
        runner_order.status = 'in_progress'
        # 没有started_at字段，可以记录日志
        db.session.commit()
        
        print(f"跑腿员开始配送!")
        print(f"当前状态: {runner_order.status}")
    else:
        print(f"订单状态不符，无法开始配送: {runner_order.status}")
    
    return runner_order

def test_runner_complete_delivery(runner_order_id):
    """测试跑腿员完成配送"""
    print("\n=== 测试跑腿员完成配送 ===")
    
    runner_order = RunnerOrder.query.get(runner_order_id)
    
    if runner_order.status == 'in_progress':
        runner_order.status = 'completed'
        runner_order.completed_at = datetime.utcnow()
        db.session.commit()
        
        print(f"跑腿员完成配送!")
        print(f"完成时间: {runner_order.completed_at}")
        print(f"最终状态: {runner_order.status}")
    else:
        print(f"订单状态不符，无法完成配送: {runner_order.status}")
    
    return runner_order

def test_customer_cancel_order(post_id):
    """测试客户取消订单（取消关联的跑腿订单）"""
    print("\n=== 测试客户取消订单 ===")
    
    # 查找关联的跑腿订单
    runner_order = RunnerOrder.query.filter_by(post_id=post_id).first()
    
    if runner_order and runner_order.status == 'pending':
        runner_order.status = 'cancelled'
        runner_order.cancelled_at = datetime.utcnow()
        db.session.commit()
        
        print(f"客户取消订单成功!")
        print(f"取消后状态: {runner_order.status}")
    elif runner_order:
        print(f"订单状态不符，无法取消: {runner_order.status}")
    else:
        print(f"未找到关联的跑腿订单")
    
    return runner_order

def main():
    """主测试函数"""
    print("开始测试跑腿功能...")
    
    with app.app_context():
        try:
            # 1. 客户创建跑腿订单
            customer, post = test_customer_create_order()
            
            # 2. 跑腿员接单
            runner, runner_order = test_runner_accept_order(post.id)
            
            # 3. 跑腿员开始配送
            runner_order = test_runner_start_delivery(runner_order.id)
            
            # 4. 跑腿员完成配送
            runner_order = test_runner_complete_delivery(runner_order.id)
            
            print("\n" + "="*50)
            print("🎉 跑腿功能测试完成!")
            print(f"跑腿任务: {post.title}")
            print(f"客户: {customer.username}")
            print(f"跑腿员: {runner.username}")
            print(f"小费金额: ¥{runner_order.tip}")
            print(f"最终状态: {runner_order.status}")
            
            # 5. 测试取消订单场景（创建新订单并取消）
            print("\n" + "="*50)
            print("测试取消订单场景...")
            customer2, post2 = test_customer_create_order()
            runner_order2 = RunnerOrder(
                order_number=generate_order_number(),
                title=f"测试取消订单：{post2.title}",
                description=post2.content,
                service_type='代取快递',
                pick_up_location=post2.location if post2.location else '东门快递点',
                delivery_location='宿舍3号楼',
                tip=post2.price if post2.price else 10.0,
                creator_id=post2.author.id,
                post_id=post2.id,
                status='pending'
            )
            db.session.add(runner_order2)
            db.session.commit()
            runner_order2 = test_customer_cancel_order(post2.id)
            
        except Exception as e:
            print(f"测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)