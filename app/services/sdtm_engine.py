import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.models.sdtm import (
    SDTMMode, ProgressMetrics, QualityMetrics, 
    DocumentInfo, AbnormalDocument, EditOperation, 
    DocumentAnnotation, SDTMEngineResponse
)
from app.utils.ai_utils import get_openai_client
import os

# 配置日志
logger = logging.getLogger(__name__)

class SDTMEngine:
    """SDTM引擎 - 负责调用LLM生成编辑操作和文档标注"""
    
    def __init__(self):
        self.client = get_openai_client()
        self.llm_model = os.getenv("OPENAI_LLM_MODEL", "deepseek-v3")
        self.system_prompt = self._get_system_prompt()
    
    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """
你是一个专业的知识管理智能体，负责维护和优化一个层次化的标签字典。你的任务是：
1. 分析给定的文档批次
2. 基于当前字典状态和遥测数据做出明智的编辑决策
3. 生成原子化的编辑操作来改进标签字典
4. 为文档提供准确的标注

请严格遵循原子化操作原则，每个操作必须是可逆的、幂等的。

## 重要工作流程

**关键：你的工作分为两个阶段，必须按顺序进行：**

### 阶段1：更新标签字典
- 首先分析当前标签字典和文档内容
- 生成必要的编辑操作来改进标签字典
- 这些操作会立即应用到标签字典中

### 阶段2：文档标注
- 使用经过第1阶段编辑后的标签字典进行标注
- 标注时必须使用更新后的标签字典中的标签
- 不能使用原始字典中的过时标签

## 任务要求

请分析上述文档和当前字典状态，然后：

1. **生成编辑操作** (JSON格式):
   使用update操作完成添加、删除、修改、合并等复杂操作

2. **提供文档标注** (JSON格式):
   为每个文档分配合适的标签列表
   **关键约束：`tags` 字段中的每一个标签，都必须是来自经过你编辑后的标签字典中的标签。标注时无需附带上级标签**

**输出格式:**
```json
{
  "operations": [
    {
      "position": "数据安全评估.控制域.安全组织与人员",
      "payload": {
        "安全组织与人员": [
          "治理架构",
          "管理机构", 
          "数据安全负责人",
          "岗位职责"
        ]
      }
    }
  ],
  "annotations": [
    {
      "doc_id": "document_1",
      "tags": ["治理架构", "管理机构"],
      "confidence": 0.95
    }
  ],
  "reasoning": "简要说明你的决策逻辑"
}
```

**编辑操作说明:**
- `position`: 指定要修改的字典路径，使用"."分隔层级
- `payload`: 包含要更新的内容，键名应该与position的最后一级匹配
- 如果要在同一层级添加多个键，可以在payload中包含多个键值对

**标注说明:**
- `tags`: 必须使用经过编辑操作后的标签字典中的标签
- 示例中的"治理架构"和"管理机构"来自编辑后的字典
"""
    
    async def process_documents(
        self,
        mode: SDTMMode,
        progress_metrics: ProgressMetrics,
        quality_metrics: QualityMetrics,
        current_tag_dictionary: Dict[str, Any],
        documents_to_process: List[DocumentInfo],
        abnormal_documents: List[AbnormalDocument] = None
    ) -> SDTMEngineResponse:
        """处理文档批次，生成编辑操作和标注"""
        
        logger.info(f"开始处理文档批次 (模式: {mode.value}, 文档数: {len(documents_to_process)})")
        
        # 首先清理当前的标签字典，确保LLM看到的是干净的结构
        cleaned_dictionary = self._clean_redundant_nesting(current_tag_dictionary)
        if len(str(cleaned_dictionary)) != len(str(current_tag_dictionary)):
            logger.info("预处理清理完成，字典结构已优化")
        
        # 构建提示词 (使用清理后的字典)
        prompt = self._build_prompt(
            mode, progress_metrics, quality_metrics, 
            cleaned_dictionary, documents_to_process, abnormal_documents
        )
        
        try:
            # 调用LLM (OpenAI客户端是同步的)
            logger.info(f"调用LLM模型: {self.llm_model}")
            response = self.client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            # 解析响应
            content = response.choices[0].message.content
            parsed_response = self._parse_response(content)
            
            # 自动应用编辑操作到标签字典
            if parsed_response.operations and mode != SDTMMode.SHADOW:
                logger.info(f"应用 {len(parsed_response.operations)} 个编辑操作到标签字典")
                
                # 记录操作前的字典状态 (使用清理后的字典)
                original_dict_size = self._count_tags_in_dictionary(cleaned_dictionary)
                
                # 应用编辑操作 (基于清理后的字典)
                updated_dictionary = self.apply_edit_operations(cleaned_dictionary, parsed_response.operations)
                
                # 记录操作后的字典状态
                new_dict_size = self._count_tags_in_dictionary(updated_dictionary)
                
                # 记录详细的修改日志
                self._log_dictionary_changes(cleaned_dictionary, updated_dictionary, parsed_response.operations)
                
                logger.info(f"标签字典更新完成: {original_dict_size} → {new_dict_size} 个标签")
                
                # 更新响应中的字典信息
                parsed_response.updated_dictionary = updated_dictionary
            elif mode == SDTMMode.SHADOW:
                logger.info(f"影子模式: 生成了 {len(parsed_response.operations)} 个编辑操作但未应用")
            
            # 记录文档标注信息
            if parsed_response.annotations:
                logger.info(f"生成了 {len(parsed_response.annotations)} 个文档标注")
                for annotation in parsed_response.annotations:
                    logger.debug(f"   - 文档 {annotation.doc_id}: {len(annotation.tags)} 个标签 (置信度: {annotation.confidence:.2f})")
            
            logger.info("文档处理完成")
            return parsed_response
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            return SDTMEngineResponse(
                operations=[],
                annotations=[],
                reasoning=f"LLM调用失败: {str(e)}"
            )
    
    def _build_prompt(
        self,
        mode: SDTMMode,
        progress_metrics: ProgressMetrics,
        quality_metrics: QualityMetrics,
        current_tag_dictionary: Dict[str, Any],
        documents_to_process: List[DocumentInfo],
        abnormal_documents: List[AbnormalDocument] = None
    ) -> str:
        """构建提示词"""
        
        # 格式化文档信息
        docs_text = ""
        for i, doc in enumerate(documents_to_process, 1):
            docs_text += f"## 文档 {i}\n"
            docs_text += f"ID: {doc.doc_id}\n"
            docs_text += f"当前标签: {doc.current_tags}\n"
            docs_text += f"内容: {doc.content[:500]}...\n\n"
        
        # 格式化异常文档信息 - 按类型分类处理
        abnormal_docs_text = ""
        if abnormal_documents:
            # 按异常类型分类
            indistinguishable_docs = [doc for doc in abnormal_documents if doc.anomaly_type == "indistinguishable"]
            other_abnormal_docs = [doc for doc in abnormal_documents if doc.anomaly_type != "indistinguishable"]
            
            # 优先显示无法区分的文档
            if indistinguishable_docs:
                abnormal_docs_text += f"### 🔥 无法区分文档 (最高优先级)\n"
                abnormal_docs_text += f"**说明**: 这些文档具有相同的标签，但内容不同，需要细化标签或引入新标签来准确区分。\n\n"
                
                max_indistinguishable = min(3, len(indistinguishable_docs))
                for i, doc in enumerate(indistinguishable_docs[:max_indistinguishable], 1):
                    abnormal_docs_text += f"#### 无法区分文档 {i}\n"
                    abnormal_docs_text += f"ID: {doc.doc_id}\n"
                    abnormal_docs_text += f"问题: {doc.reason}\n"
                    abnormal_docs_text += f"当前标签: {doc.current_tags}\n"
                    abnormal_docs_text += f"内容: {doc.content}\n\n"
                
                if len(indistinguishable_docs) > max_indistinguishable:
                    abnormal_docs_text += f"还有 {len(indistinguishable_docs) - max_indistinguishable} 个其他无法区分的文档...\n\n"
            
            # 其他异常文档
            if other_abnormal_docs:
                abnormal_docs_text += f"### ⚡ 其他异常文档\n"
                max_other_abnormal = min(2, len(other_abnormal_docs))
                for i, doc in enumerate(other_abnormal_docs[:max_other_abnormal], 1):
                    abnormal_docs_text += f"#### 异常文档 {i}\n"
                    abnormal_docs_text += f"ID: {doc.doc_id}\n"
                    abnormal_docs_text += f"异常类型: {doc.anomaly_type}\n"
                    abnormal_docs_text += f"异常原因: {doc.reason}\n"
                    abnormal_docs_text += f"当前标签: {doc.current_tags}\n"
                    abnormal_docs_text += f"内容: {doc.content[:200]}...\n\n"
        
        # 格式化质量指标
        quality_info = f"""
- 标签-文档分布: {quality_metrics.tags_document_distribution}
- 标注不足文档数: {quality_metrics.under_annotated_docs_count}
- 标注过度文档数: {quality_metrics.over_annotated_docs_count}
- 使用不足标签数: {quality_metrics.under_used_tags_count}
- 使用过度标签数: {quality_metrics.over_used_tags_count}
- 无法区分文档数: {quality_metrics.indistinguishable_docs_count}
"""
        
        # 构建完整提示词
        prompt = f"""
## 当前系统状态

**进度指标:**
- 当前迭代: {progress_metrics.current_iteration}/{progress_metrics.total_iterations} ({progress_metrics.progress_pct:.1f}%)
- 字典容量: {progress_metrics.current_tags_dictionary_size}/{progress_metrics.max_tags_dictionary_size} ({progress_metrics.capacity_pct:.1f}%)

**质量指标:**
{quality_info}

**运行模式:** {mode.value}

## 当前标签字典

{json.dumps(current_tag_dictionary, ensure_ascii=False, indent=2)}

## 待处理文档

{docs_text}

## 异常文档

{abnormal_docs_text}

**注意事项:**
- 你可以根据处理进度与标签容量的相对关系，评估应当扩展标签规模还是优化标签结构
- 容量 > 85% 是一个负面信号，此时应优先考虑合并和优化现有标签
- 避免创建孤儿标签，确保每个标签都有实际用途
- 质量指标是参考信号，可以指导标签字典完善后的优化方向，但是在标签字典非常不完善时参考价值较弱

**🔥 无法区分文档处理策略（最高优先级）:**
- 对于具有相同标签但内容不同的文档，这是标签体系不够精细的信号
- 必须通过以下方式之一解决：
  1. **细化现有标签**: 将粗粒度标签分解为更具体的子标签
  2. **引入新标签**: 基于文档内容的差异性，创建新的区分性标签
  3. **调整标签组合**: 为不同文档分配不同的标签组合来实现区分
- 处理原则：宁可引入新标签也不要让文档无法区分，这是提高标签体系精确度的关键

**⚡ 其他异常文档处理:**
- 标签错误文档：立即修复，确保标签格式正确
- 标注不足文档：补充合适的标签，确保每个文档都有充分的标注
- 标注过度文档：移除冗余标签，保持标注的精炼性

根据当前模式({mode.value})，请：
"""
        
        if mode == SDTMMode.EDIT:
            prompt += """
1. 重点生成编辑操作来优化标签字典
   - **针对无法区分文档**: 必须引入新标签或细化现有标签来实现区分
   - **标签字典扩展**: 基于文档内容的差异性，勇于创建新的区分性标签
2. 为文档提供标注，**必须使用编辑后的标签字典中的标签**
3. 考虑异常文档的反馈来调整字典结构

**无法区分文档处理要求**: 
- 分析具有相同标签的文档之间的内容差异
- 创建能够准确区分这些文档的新标签或标签组合
- 确保每个文档都有独特的标签特征

**特别提醒：标注时使用的标签必须来自经过你编辑操作后的标签字典，不能使用原始字典中的标签**
"""
        elif mode == SDTMMode.ANNOTATE:
            prompt += """
1. 重点为文档提供准确的标注
   - **针对无法区分文档**: 仔细分析内容差异，分配不同的标签组合
   - **标注精确性**: 确保具有相同标签的文档确实内容相似
2. 可以生成少量编辑操作来修正明显的字典问题
3. **确保标注的标签都存在于经过编辑后的字典中**

**无法区分文档处理要求**: 
- 如果发现标签字典不足以区分文档，请适当扩展字典
- 为每个文档分配最能体现其内容特征的标签组合
- 避免机械性地给相似文档分配完全相同的标签

**特别提醒：标注时使用的标签必须来自经过你编辑操作后的标签字典，不能使用原始字典中的标签**
"""
        elif mode == SDTMMode.SHADOW:
            prompt += """
1. 生成编辑操作但不要求应用（用于监测语义漂移）
   - **监测标签区分能力**: 识别是否存在无法区分的文档群体
   - **语义漂移检测**: 发现标签含义的变化趋势
2. 提供标注建议，**标签必须来自经过编辑后的字典**
3. 识别可能的语义漂移信号

**无法区分文档分析要求**: 
- 分析标签体系的区分能力是否足够
- 提出改进建议，包括新标签的引入方案
- 评估当前标签字典的完整性和精确性

**特别提醒：即使在影子模式下，标注建议也必须基于经过编辑后的标签字典**
"""
        
        return prompt
    
    def _parse_response(self, content: str) -> SDTMEngineResponse:
        """解析LLM响应"""
        try:
            # 尝试从响应中提取JSON
            start_idx = content.find('{')
            end_idx = content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                raise ValueError("No JSON found in response")
            
            json_content = content[start_idx:end_idx]
            data = json.loads(json_content)
            
            # 解析编辑操作
            operations = []
            for op_data in data.get('operations', []):
                operations.append(EditOperation(
                    position=op_data.get('position', ''),
                    payload=op_data.get('payload', {})
                ))
            
            # 解析文档标注
            annotations = []
            for ann_data in data.get('annotations', []):
                annotations.append(DocumentAnnotation(
                    doc_id=ann_data.get('doc_id', ''),
                    tags=ann_data.get('tags', []),
                    confidence=ann_data.get('confidence', 0.0)
                ))
            
            return SDTMEngineResponse(
                operations=operations,
                annotations=annotations,
                reasoning=data.get('reasoning', '')
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Error parsing LLM response: {e}")
            print(f"Response content: {content}")
            
            # 返回空响应
            return SDTMEngineResponse(
                operations=[],
                annotations=[],
                reasoning=f"解析响应失败: {str(e)}"
            )
    
    def apply_edit_operations(
        self, 
        current_dictionary: Dict[str, Any], 
        operations: List[EditOperation]
    ) -> Dict[str, Any]:
        """应用编辑操作到标签字典"""
        result_dict = current_dictionary.copy()
        
        # 首先清理现有的重复嵌套结构
        logger.debug("清理现有重复嵌套结构...")
        result_dict = self._clean_redundant_nesting(result_dict)
        
        for operation in operations:
            try:
                self._apply_single_operation(result_dict, operation)
            except Exception as e:
                logger.error(f"Error applying operation {operation.position}: {e}")
        
        # 操作完成后再次清理
        logger.debug("最终清理重复嵌套结构...")
        result_dict = self._clean_redundant_nesting(result_dict)
        
        return result_dict
    
    def _clean_redundant_nesting(self, dictionary: Dict[str, Any]) -> Dict[str, Any]:
        """清理重复嵌套结构"""
        if not isinstance(dictionary, dict):
            return dictionary
        
        cleaned_dict = {}
        
        for key, value in dictionary.items():
            if isinstance(value, dict):
                # 递归清理子字典
                cleaned_value = self._clean_redundant_nesting(value)
                
                # 检查是否存在重复嵌套
                if (len(cleaned_value) == 1 and 
                    key in cleaned_value and 
                    isinstance(cleaned_value[key], (list, dict))):
                    # 发现重复嵌套，提升内层值
                    promoted_value = cleaned_value[key]
                    if isinstance(promoted_value, dict):
                        # 如果提升的值是字典，继续递归清理
                        cleaned_dict[key] = self._clean_redundant_nesting(promoted_value)
                    else:
                        # 如果提升的值是列表，直接使用
                        cleaned_dict[key] = promoted_value
                    logger.debug(f"清理重复嵌套: '{key}' -> 提升内层值")
                else:
                    # 没有重复嵌套，使用清理后的值
                    cleaned_dict[key] = cleaned_value
            else:
                # 非字典值，直接使用
                cleaned_dict[key] = value
        
        return cleaned_dict
    
    def _apply_single_operation(self, dictionary: Dict[str, Any], operation: EditOperation):
        """应用单个编辑操作 - 支持叶子节点到非叶子节点的转换"""
        position_parts = operation.position.split('.')
        
        logger.debug(f"开始应用操作: {operation.position}")
        logger.debug(f"   Payload: {operation.payload}")
        logger.debug(f"   路径部分: {position_parts}")
        
        # 导航到目标位置，支持结构转换
        current_dict = dictionary
        for i, part in enumerate(position_parts[:-1]):
            logger.debug(f"   导航到第 {i+1} 层: '{part}'")
            logger.debug(f"      当前节点类型: {type(current_dict)}")
            
            # 检查current_dict是否是字典类型
            if not isinstance(current_dict, dict):
                logger.error(f"无法导航到 '{part}' 因为当前不是字典类型: {type(current_dict)}")
                return
            
            logger.debug(f"      当前节点包含的键: {list(current_dict.keys()) if isinstance(current_dict, dict) else 'N/A'}")
            
            if part not in current_dict:
                current_dict[part] = {}
                logger.debug(f"创建新的中间节点: '{part}'")
            elif not isinstance(current_dict[part], dict):
                # 如果当前节点不是字典，需要进行结构转换
                old_value = current_dict[part]
                logger.debug(f"将节点 '{part}' 从 {type(old_value)} 转换为字典")
                logger.debug(f"      原始值: {old_value}")
                
                if isinstance(old_value, list):
                    # 如果原来是列表，转换为字典结构
                    new_dict = {}
                    for item in old_value:
                        if isinstance(item, str):
                            # 将字符串项转换为字典键，值为空字典（准备接收子结构）
                            new_dict[item] = {}
                        else:
                            # 非字符串项保持原样
                            new_dict[str(item)] = item
                    current_dict[part] = new_dict
                    logger.debug(f"  将列表转换为字典: {list(new_dict.keys())}")
                else:
                    # 其他类型直接转换为字典
                    current_dict[part] = {}
                    logger.debug(f"  将 {type(old_value)} 转换为空字典")
            else:
                logger.debug(f"      节点 '{part}' 已存在且为字典类型")
                    
            current_dict = current_dict[part]
            logger.debug(f"      移动到节点 '{part}', 类型: {type(current_dict)}")
            if isinstance(current_dict, dict):
                logger.debug(f"      节点内容: {list(current_dict.keys())}")
        
        # 应用操作到最终目标
        if position_parts:
            target_key = position_parts[-1]
            logger.debug(f"   处理目标键: '{target_key}'")
            logger.debug(f"      目标位置的节点类型: {type(current_dict)}")
            
            # 检查current_dict是否是字典类型
            if not isinstance(current_dict, dict):
                logger.error(f"无法应用操作到 '{target_key}' 因为当前不是字典类型: {type(current_dict)}")
                logger.error(f"      当前节点值: {current_dict}")
                return
            
            logger.debug(f"      目标位置现有键: {list(current_dict.keys())}")
            logger.debug(f"      目标键是否存在: {target_key in current_dict}")
            if target_key in current_dict:
                logger.debug(f"      现有目标键类型: {type(current_dict[target_key])}")
                logger.debug(f"      现有目标键值: {current_dict[target_key]}")
            
            # 处理目标键的操作
            if target_key in current_dict:
                # 目标键已存在
                existing_value = current_dict[target_key]
                
                if isinstance(existing_value, dict):
                    # 如果是字典，智能合并内容
                    if len(operation.payload) == 1 and target_key in operation.payload:
                        # 特殊情况：如果payload只包含与target_key同名的键，直接替换
                        current_dict[target_key] = operation.payload[target_key]
                        logger.debug(f"替换现有节点 '{target_key}' 避免重复嵌套")
                    else:
                        # 正常情况：更新字典内容
                        existing_value.update(operation.payload)
                        logger.debug(f"更新现有字典节点 '{target_key}'")
                else:
                    # 如果不是字典，智能转换
                    if len(operation.payload) == 1 and target_key in operation.payload:
                        # 特殊情况：避免重复嵌套
                        current_dict[target_key] = operation.payload[target_key]
                        logger.debug(f"将 '{target_key}' 替换为新值，避免重复嵌套")
                    else:
                        # 正常情况：转换为字典并应用payload
                        old_value = existing_value
                        current_dict[target_key] = operation.payload.copy()
                        logger.debug(f"将 '{target_key}' 从 {type(old_value)} 转换为字典")
            else:
                # 目标键不存在，创建新键
                # 智能处理重复嵌套问题
                if len(operation.payload) == 1 and target_key in operation.payload:
                    # 特殊情况：避免创建重复嵌套结构
                    # 例如：position="数据分类分级", payload={"数据分类分级": [...]}
                    # 应该创建 current_dict["数据分类分级"] = [...] 而不是 current_dict["数据分类分级"] = {"数据分类分级": [...]}
                    current_dict[target_key] = operation.payload[target_key]
                    logger.debug(f"创建新节点 '{target_key}' 避免重复嵌套")
                else:
                    # 正常情况：使用整个payload作为值
                    current_dict[target_key] = operation.payload.copy()
                    logger.debug(f"创建新节点 '{target_key}' 使用整个payload")
                
                # 如果payload中还有其他键（除了target_key），也添加到当前层级
                # 但只有在非重复嵌套情况下才执行
                if not (len(operation.payload) == 1 and target_key in operation.payload):
                    for key, value in operation.payload.items():
                        if key != target_key and key not in current_dict:
                            current_dict[key] = value
                            logger.debug(f"添加额外键 '{key}' 到当前层级")
        else:
            # 根级别更新
            if isinstance(dictionary, dict):
                dictionary.update(operation.payload)
                logger.debug("更新根级别字典")
            else:
                logger.error(f"无法更新根级别，因为字典不是字典类型: {type(dictionary)}")
                
        logger.debug(f"成功应用操作到 '{operation.position}'")
    
    def preview_edit_operations(
        self, 
        current_dictionary: Dict[str, Any], 
        operations: List[EditOperation]
    ) -> Dict[str, Any]:
        """预览编辑操作的效果，不修改原字典"""
        return self.apply_edit_operations(current_dictionary, operations)
    
    def clean_tag_dictionary(self, dictionary: Dict[str, Any]) -> Dict[str, Any]:
        """清理标签字典中的重复嵌套结构"""
        logger.debug("开始清理标签字典...")
        logger.debug(f"   清理前字典大小: {len(str(dictionary))} 字符")
        
        cleaned_dict = self._clean_redundant_nesting(dictionary)
        
        logger.debug(f"   清理后字典大小: {len(str(cleaned_dict))} 字符")
        if len(str(cleaned_dict)) != len(str(dictionary)):
            logger.debug("   清理完成，字典结构已优化")
        else:
            logger.debug("   清理完成，未发现重复嵌套")
        
        return cleaned_dict
    
    def _count_tags_in_dictionary(self, tag_dict: Dict[str, Any]) -> int:
        """递归计算标签字典中的标签数量"""
        if not tag_dict:
            return 0
        
        count = 0
        for key, value in tag_dict.items():
            if isinstance(value, dict):
                count += self._count_tags_in_dictionary(value)
            elif isinstance(value, list):
                count += len(value)
            else:
                count += 1
        return count
    
    def _log_dictionary_changes(self, original_dict: Dict[str, Any], updated_dict: Dict[str, Any], operations: List[EditOperation]):
        """记录标签字典修改的详细日志"""
        logger.debug("标签字典修改详情:")
        
        # 首先显示原始字典的结构（调试用）
        logger.debug("原始字典结构:")
        self._print_dictionary_structure(original_dict, indent=2)
        
        for i, operation in enumerate(operations, 1):
            logger.debug(f"  操作 {i}: {operation.position}")
            
            # 提取操作的具体内容
            if operation.payload:
                for key, value in operation.payload.items():
                    if isinstance(value, list):
                        logger.debug(f"    - 设置 '{key}': {len(value)} 个子标签")
                        for tag in value:
                            logger.debug(f"      * {tag}")
                    elif isinstance(value, dict):
                        logger.debug(f"    - 设置 '{key}': 嵌套字典 ({len(value)} 个子项)")
                        for sub_key in value.keys():
                            logger.debug(f"      * {sub_key}")
                    else:
                        logger.debug(f"    - 设置 '{key}': {value}")
            
        # 显示更新后的字典结构（调试用）
        logger.debug("更新后字典结构:")
        self._print_dictionary_structure(updated_dict, indent=2)
            
        # 计算总体变化
        original_size = self._count_tags_in_dictionary(original_dict)
        updated_size = self._count_tags_in_dictionary(updated_dict)
        change = updated_size - original_size
        
        if change > 0:
            logger.debug(f"  📈 新增 {change} 个标签")
        elif change < 0:
            logger.debug(f"  📉 删除 {abs(change)} 个标签")
        else:
            logger.debug(f"  🔄 标签数量保持不变 (可能有结构调整)")
        
        # 记录字典结构变化
        self._log_structure_changes(original_dict, updated_dict)
    
    def _log_structure_changes(self, original_dict: Dict[str, Any], updated_dict: Dict[str, Any], prefix: str = ""):
        """记录字典结构的具体变化"""
        original_keys = set(original_dict.keys()) if original_dict else set()
        updated_keys = set(updated_dict.keys()) if updated_dict else set()
        
        # 新增的键
        new_keys = updated_keys - original_keys
        if new_keys:
            for key in new_keys:
                logger.debug(f"  ➕ 新增分类: {prefix}{key}")
        
        # 删除的键
        removed_keys = original_keys - updated_keys
        if removed_keys:
            for key in removed_keys:
                logger.debug(f"  ➖ 删除分类: {prefix}{key}")
        
        # 修改的键
        common_keys = original_keys & updated_keys
        for key in common_keys:
            original_value = original_dict[key]
            updated_value = updated_dict[key]
            
            if isinstance(original_value, dict) and isinstance(updated_value, dict):
                # 递归检查子字典
                self._log_structure_changes(original_value, updated_value, f"{prefix}{key}.")
            elif isinstance(original_value, list) and isinstance(updated_value, list):
                # 检查列表变化
                if set(original_value) != set(updated_value):
                    added_items = set(updated_value) - set(original_value)
                    removed_items = set(original_value) - set(updated_value)
                    
                    if added_items:
                        logger.debug(f"  ➕ {prefix}{key} 新增标签: {', '.join(added_items)}")
                    if removed_items:
                        logger.debug(f"  ➖ {prefix}{key} 删除标签: {', '.join(removed_items)}")
            elif original_value != updated_value:
                logger.debug(f"  🔄 {prefix}{key}: {original_value} → {updated_value}")
    
    def _print_dictionary_structure(self, dictionary: Dict[str, Any], indent: int = 0, max_depth: int = 3):
        """打印字典结构（用于调试）"""
        if not dictionary or indent > max_depth:
            return
        
        prefix = "  " * indent
        for key, value in dictionary.items():
            if isinstance(value, dict):
                logger.debug(f"{prefix}📁 {key}/ ({len(value)} 个子项)")
                self._print_dictionary_structure(value, indent + 1, max_depth)
            elif isinstance(value, list):
                logger.debug(f"{prefix}📋 {key}: [{len(value)} 个标签]")
                if len(value) <= 5:  # 只显示前5个
                    for item in value:
                        logger.debug(f"{prefix}  * {item}")
                else:
                    for item in value[:3]:
                        logger.debug(f"{prefix}  * {item}")
                    logger.debug(f"{prefix}  ... 还有 {len(value) - 3} 个")
            else:
                logger.debug(f"{prefix}📄 {key}: {value}")