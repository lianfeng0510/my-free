import uuid
from datetime import datetime

def generate_order_number():
    """生成订单号"""
    return f'RUN{datetime.utcnow().strftime("%Y%m%d%H%M%S")}{str(uuid.uuid4())[:6].upper()}'
