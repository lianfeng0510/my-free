from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
import json
from models import db, Post, Trade, RunnerOrder, PrivateMessage, Comment
from services.trade_service import TradeService
from services.notification_service import NotificationService
from utils.helpers import generate_order_number

trade_bp = Blueprint('trade', __name__)

def update_post_trade_listing(post_obj, listing_state=None, post_status=None):
    if not post_obj:
        return
    try:
        meta = json.loads(post_obj.metadata_json) if post_obj.metadata_json else {}
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    if listing_state:
        meta['listing_state'] = listing_state
    post_obj.metadata_json = json.dumps(meta, ensure_ascii=False)
    if post_status:
        post_obj.status = post_status

@trade_bp.route('/trade/create/<int:post_id>', methods=['POST'])
@login_required
def create_trade(post_id):
    """创建担保交易（购买二手商品）"""
    post = Post.query.get_or_404(post_id)
    
    if post.post_type != 'second_hand':
        flash('此帖子不是二手交易帖子', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    if post.author.id == current_user.id:
        flash('不能购买自己的商品', 'error')
        return redirect(url_for('post', post_id=post_id))
    
    # 检查是否已有进行中的交易
    existing_trade = Trade.query.filter_by(post_id=post_id, buyer_id=current_user.id).filter(Trade.trade_status.in_(['pending', 'payment_pending', 'paid', 'shipped'])).first()
    if existing_trade:
        flash('您已经有一个进行中的交易', 'info')
        return redirect(url_for('trade.view_trade', trade_id=existing_trade.id))
    
    # 创建交易
    trade = TradeService.create_trade(
        post_id=post_id,
        buyer_id=current_user.id,
        seller_id=post.author.id,
        price=post.price if post.price else 0.0
    )
    update_post_trade_listing(post, listing_state='trading', post_status='trading')
    db.session.commit()
    
    flash('交易创建成功，请尽快支付', 'success')
    return redirect(url_for('trade.view_trade', trade_id=trade.id))

@trade_bp.route('/trade/<int:trade_id>')
@login_required
def view_trade(trade_id):
    """查看交易详情"""
    trade = Trade.query.get_or_404(trade_id)
    
    # 检查权限
    if trade.buyer_id != current_user.id and trade.seller_id != current_user.id and current_user.role != 'admin':
        flash('无权查看此交易', 'error')
        return redirect(url_for('home'))
    
    bargain_offer = None
    if trade.dispute_reason and trade.dispute_reason.startswith('BARGAIN:'):
        payload = trade.dispute_reason.split(':')
        if len(payload) == 3:
            bargain_offer = {
                'price': payload[1],
                'buyer_id': int(payload[2])
            }
    return render_template('trade.html', trade=trade, bargain_offer=bargain_offer)

@trade_bp.route('/trade/<int:trade_id>/bargain', methods=['POST'])
@login_required
def bargain_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if current_user.id != trade.buyer_id:
        flash('仅买家可发起砍价。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if trade.trade_status not in ['pending']:
        flash('当前交易状态不支持砍价。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))

    offer_price = request.form.get('offer_price', type=float)
    if not offer_price or offer_price <= 0:
        flash('请输入有效砍价金额。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if offer_price >= trade.price:
        flash('砍价金额需低于当前成交价。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))

    trade.dispute_reason = f'BARGAIN:{offer_price}:{current_user.id}'
    db.session.add(PrivateMessage(
        sender_id=current_user.id,
        receiver_id=trade.seller_id,
        content=f'我对商品《{trade.post.title}》发起砍价：¥{offer_price}，请考虑。'
    ))
    pay_link = url_for('trade.view_trade', trade_id=trade.id, _external=True)
    db.session.add(PrivateMessage(
        sender_id=current_user.id,
        receiver_id=trade.seller_id,
        content=f'可通过改价交易链接继续沟通并支付：{pay_link}'
    ))
    db.session.commit()
    flash('砍价请求已发送给卖家。', 'success')
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/accept_bargain', methods=['POST'])
@login_required
def accept_bargain_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if current_user.id != trade.seller_id:
        flash('仅卖家可同意砍价。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if not trade.dispute_reason or not trade.dispute_reason.startswith('BARGAIN:'):
        flash('当前没有待处理砍价请求。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))

    payload = trade.dispute_reason.split(':')
    if len(payload) != 3:
        flash('砍价数据异常。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))

    offered_price = float(payload[1])
    buyer_id = int(payload[2])
    trade.price = offered_price
    trade.dispute_reason = None
    db.session.add(PrivateMessage(
        sender_id=current_user.id,
        receiver_id=buyer_id,
        content=f'我已同意你的砍价，成交价更新为 ¥{offered_price}，可继续支付担保交易。'
    ))
    pay_link = url_for('trade.view_trade', trade_id=trade.id, _external=True)
    db.session.add(PrivateMessage(
        sender_id=current_user.id,
        receiver_id=buyer_id,
        content=f'改价链接：{pay_link}'
    ))
    db.session.commit()
    flash('已同意砍价并更新成交价。', 'success')
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/request_runner', methods=['POST'])
@login_required
def request_runner_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if current_user.id != trade.buyer_id:
        flash('仅买家可发起配送跑腿。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if trade.trade_status not in ['paid', 'shipped']:
        flash('当前状态不支持呼叫跑腿配送。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))

    existing_order = RunnerOrder.query.filter(
        RunnerOrder.post_id == trade.post_id,
        RunnerOrder.creator_id == trade.buyer_id,
        RunnerOrder.status.in_(['pending', 'accepted', 'in_progress'])
    ).first()
    if existing_order:
        flash('你已发起过配送跑腿，请勿重复提交。', 'info')
        return redirect(url_for('runner_order_detail', order_id=existing_order.id))

    pick_up_location = (request.form.get('pick_up_location') or trade.post.location or '与卖家协商地点').strip()
    delivery_location = (request.form.get('delivery_location') or '与买家协商地点').strip()
    runner_order = RunnerOrder(
        order_number=generate_order_number(),
        title=f'二手交易配送：{trade.post.title[:30]}',
        description=f'交易#{trade.id} 专属配送，平台免跑腿费。卖家：{trade.seller.username}，买家：{trade.buyer.username}',
        service_type='二手交易配送',
        pick_up_location=pick_up_location,
        delivery_location=delivery_location,
        tip=0.0,
        status='pending',
        creator_id=trade.buyer_id,
        post_id=trade.post_id
    )
    db.session.add(runner_order)
    db.session.commit()
    flash('已创建二手交易专属跑腿单（免跑腿费）。', 'success')
    return redirect(url_for('runner_order_detail', order_id=runner_order.id))

@trade_bp.route('/trade/<int:trade_id>/pay', methods=['POST'])
@login_required
def pay_trade(trade_id):
    """支付交易（模拟支付）"""
    try:
        payment = TradeService.process_payment(
            trade_id=trade_id,
            user_id=current_user.id
        )
        
        # 发送通知
        NotificationService.create_payment_success_notification(
            user_id=current_user.id,
            trade_id=trade_id,
            amount=payment.amount
        )
        
        flash('支付成功，等待卖家发货', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/ship', methods=['POST'])
@login_required
def ship_trade(trade_id):
    """卖家发货"""
    try:
        trade = TradeService.ship_trade(
            trade_id=trade_id,
            user_id=current_user.id
        )
        
        flash('发货成功，等待买家确认收货', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/deliver', methods=['POST'])
@login_required
def deliver_trade(trade_id):
    """买家确认收货"""
    try:
        trade = TradeService.deliver_trade(
            trade_id=trade_id,
            user_id=current_user.id
        )
        
        flash('确认收货成功，交易完成', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/complete', methods=['POST'])
@login_required
def complete_trade(trade_id):
    """卖家确认收款（担保释放）"""
    try:
        trade = TradeService.complete_trade(
            trade_id=trade_id,
            user_id=current_user.id
        )
        update_post_trade_listing(trade.post, listing_state='sold', post_status='sold')
        db.session.commit()
        
        flash('交易完成，款项已释放', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('trade.view_trade', trade_id=trade_id))

@trade_bp.route('/trade/<int:trade_id>/cancel', methods=['POST'])
@login_required
def cancel_trade(trade_id):
    """取消交易"""
    try:
        trade = TradeService.cancel_trade(
            trade_id=trade_id,
            user_id=current_user.id
        )
        active_trades = Trade.query.filter(
            Trade.post_id == trade.post_id,
            Trade.trade_status.in_(['pending', 'payment_pending', 'paid', 'shipped', 'delivered'])
        ).count()
        if active_trades == 0:
            update_post_trade_listing(trade.post, listing_state='on_sale', post_status='active')
            db.session.commit()
        
        flash('交易已取消', 'success')
    except PermissionError as e:
        flash(str(e), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    
    return redirect(url_for('home'))

@trade_bp.route('/trade/<int:trade_id>/review', methods=['POST'])
@login_required
def review_trade(trade_id):
    trade = Trade.query.get_or_404(trade_id)
    if current_user.id not in [trade.buyer_id, trade.seller_id]:
        flash('无权限评价该交易。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if trade.trade_status != 'completed':
        flash('仅已完成交易可评价。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    score = request.form.get('score', type=int)
    content = (request.form.get('content') or '').strip()
    if not score or score < 1 or score > 5:
        flash('评分范围需在1~5。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    if len(content) < 2:
        flash('评价内容至少2个字。', 'error')
        return redirect(url_for('trade.view_trade', trade_id=trade_id))
    role = '买家' if current_user.id == trade.buyer_id else '卖家'
    comment_text = f'【交易评价】{role}评分：{score}/5。{content}'
    db.session.add(Comment(content=comment_text[:1000], user_id=current_user.id, post_id=trade.post_id))
    db.session.commit()
    flash('评价提交成功。', 'success')
    return redirect(url_for('post', post_id=trade.post_id) + '#comments')
