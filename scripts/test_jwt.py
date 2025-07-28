from jose import jwt
import os
from datetime import datetime, timezone

# 使用默认密钥（因为环境变量可能没设置）
REFRESH_SECRET_KEY = os.getenv('JWT_REFRESH_SECRET_KEY', 'your-refresh-secret-key-here')
ALGORITHM = 'HS256'

refresh_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyZTEzZWYwNS0zZjRiLTRmZDAtOWNmZC04N2YyMTA5NGE5MWMiLCJleHAiOjE3NTQwMDMwNDUsInR5cGUiOiJyZWZyZXNoIn0.Pjd6DJXraqTNcSR2YdLwsAzhBU0B-VlxngS05CJcDfc'

try:
    payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
    print('Token解码成功:')
    print(f'用户ID: {payload.get("sub")}')
    print(f'过期时间: {payload.get("exp")}')
    print(f'Token类型: {payload.get("type")}')
    
    # 检查是否过期
    exp_timestamp = payload.get('exp')
    if exp_timestamp:
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        print(f'当前时间: {now}')
        print(f'过期时间: {exp_datetime}')
        print(f'是否过期: {now > exp_datetime}')
except Exception as e:
    print(f'Token解码失败: {e}')