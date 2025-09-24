"""
包含事件驱动的资产分析Dramatiq Actor。
"""
import dramatiq
import uuid
import base64
import mimetypes
import io
import requests
from datetime import datetime
from PIL import Image


def _preprocess_image(image_data: bytes, max_size: int = 2048) -> bytes:
    """调整图片尺寸以防止OOM错误。"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            if max(img.width, img.height) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                img_format = img.format if img.format in ['JPEG', 'PNG', 'WEBP'] else 'JPEG'
                img.save(buffer, format=img_format)
                return buffer.getvalue()
            return image_data
    except Exception as e:
        print(f"警告: 无法预处理图片，将使用原图。错误: {e}")
        return image_data

@dramatiq.actor(
    queue_name="asset_analysis",
    max_retries=3,
    min_backoff=5000, # 5 seconds
    time_limit=300_000 # 5 minutes
)
def analyze_asset_actor(
    asset_id: str,
    document_id: str,
    knowledge_space_id: str,
    initiator_id: str, # 理论上应该从KS的配置中获取默认用户
    correlation_id: str
):
    """
    一个事件驱动的Actor，负责分析单个资产。
    它不直接与Job模型交互，而是通过创建领域事件来报告其结果。
    """
    # --- [FIX] Defer imports to prevent circular dependencies during worker startup ---
    from sqlalchemy.orm import Session
    from backend.app.models import DocumentAssetContext
    from backend.app.models.domain_events.ingestion_events import (
        AssetAnalysisCompletedPayload,
        AnalysisTraceabilityInfo
    )
    from .event_helpers import create_asset_analysis_completed_event
    from ..service_factory import get_services_scope
    # --- End of Fix ---

    asset_uuid = uuid.UUID(asset_id)
    doc_uuid = uuid.UUID(document_id)
    ks_uuid = uuid.UUID(knowledge_space_id)
    user_uuid = uuid.UUID(initiator_id)
    
    # [FIX] Handle cases where correlation_id is None or the string 'None'
    corr_uuid = uuid.UUID(correlation_id) if correlation_id and correlation_id != 'None' else None

    print(f"--- [资产分析Actor] 开始处理资产: {asset_id} (文档: {document_id}) ---")

    with get_services_scope() as services:
        db = services["db"]
        try:
            # 1. 获取必要的上下文和数据
            context = db.query(DocumentAssetContext).filter_by(document_id=doc_uuid, asset_id=asset_uuid).first()
            if not context or not context.asset:
                raise ValueError(f"未找到文档-资产上下文 Document {doc_uuid}, Asset {asset_uuid}")

            # 2. 获取AI客户端和图片数据
            vlm_client, credential = services["ai_provider_service"].get_vlm_client_with_fallback(user_uuid, ks_uuid)
            
            # 打印调用信息以供调试
            print(f"  - [资产分析Actor] 调用VLM服务: {vlm_client.base_url}, 模型: {vlm_client.model_name}")
            
            # 在调用VLM之前，先测试连接
            try:
                # 构造正确的模型端点URL
                base_url = str(vlm_client.base_url).rstrip('/')
                models_url = f"{base_url}/models"
                models_response = requests.get(models_url, timeout=5)
                print(f"  - [资产分析Actor] VLM服务模型列表: {models_response.json()}")
            except Exception as e:
                print(f"  - [资产分析Actor] VLM服务连接测试失败: {e}")
            
            storage_path = context.asset.storage_path.lstrip('/')
            bucket, object_name = storage_path.split('/', 1)
            image_data = services["minio_client"].get_object(bucket, object_name).read()
            processed_image_data = _preprocess_image(image_data)
            
            mime_type, _ = mimetypes.guess_type(object_name)
            data_url = f"data:{mime_type or 'image/jpeg'};base64,{base64.b64encode(processed_image_data).decode('utf-8')}"

            # 3. 执行VLM调用
            analysis_prompt = "请详细描述这幅图片的内容，并提取3-5个最相关的关键词作为标签。"
            start_time = datetime.utcnow()
            
            print(f"  - [资产分析Actor] 开始调用VLM: {vlm_client.model_name}")
            try:
                response = vlm_client.chat.completions.create(
                    model=vlm_client.model_name,
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": analysis_prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ]},
                    ],
                    max_tokens=1024,
                )
                print(f"  - [资产分析Actor] VLM调用成功。耗时: {datetime.utcnow() - start_time}。")
            except Exception as e:
                print(f"  - [资产分析Actor] VLM调用失败: {e}")
                raise
            
            end_time = datetime.utcnow()
            description = response.choices[0].message.content.strip()
            print(f"  - [资产分析Actor] VLM调用成功。耗时: {end_time - start_time}。")
            
            # 简单的标签提取逻辑 (可以替换为更复杂的模型调用)
            tags = [tag.strip() for tag in description.splitlines()[-1].replace("标签：", "").split(',') if tag.strip()]

            # 4. 更新DocumentAssetContext中的分析结果 (作为读取模型的缓存)
            context.analysis_result = description
            context.model_provider = credential.provider if credential else "system_default"
            context.model_name = vlm_client.model_name
            
            # 5. 创建领域事件
            payload = AssetAnalysisCompletedPayload(
                asset_id=asset_uuid,
                document_id=doc_uuid,
                description=description,
                tags=tags,
                trace_info=AnalysisTraceabilityInfo(
                    model_credential_id=credential.id if credential else None,
                    model_name=vlm_client.model_name,
                    prompt_used=analysis_prompt,
                    start_time=start_time,
                    end_time=end_time
                )
            )
            create_asset_analysis_completed_event(db, payload, corr_uuid)

            # 6. 提交事务
            print(f"  - [资产分析Actor] 即将提交数据库事务...")
            db.commit()
            print(f"  - [资产分析Actor] 数据库事务已成功提交。")
            print(f"--- [资产分析Actor] 成功完成资产: {asset_id} ---")

        except Exception as e:
            print(f"--- [资产分析Actor] 处理资产 {asset_id} 时失败: {e} ---")
            db.rollback()
            # 重新抛出异常，以便Dramatiq根据策略进行重试
            raise
