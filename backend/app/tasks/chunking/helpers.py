import json
import uuid
import logging
import re
from typing import List, Any, Tuple, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.app.models import Job, Chunk
from backend.app.services.reading_service import ReadingService
from .validators import IdentifyHeadingsTool, GenerateContentSummaryTool

logger = logging.getLogger(__name__)

CONTEXT_MAX_HEADINGS = 15
MAX_LINE_LENGTH_IN_CONTEXT = 200
# Stricter enforcement based on user feedback
MIN_CHUNK_CHARS = 512
# Safe upper limit for merging, as requested
MERGE_THRESHOLD_CHARS = 8192

class _ChunkDraft(BaseModel):
    """A temporary Pydantic model to hold chunk data before merging and DB insertion."""
    type: str
    level: int
    start_line: int
    end_line: int
    raw_content: str
    summary: str
    paraphrase: Optional[str]
    parent_heading_text: Optional[str]
    parent_id: Optional[uuid.UUID] = None

def build_llm_context(db: Session, reading_service: ReadingService, job: Job, megachunk_text: str, start_line_offset: int) -> str:
    # This function remains the same as it's for building the input to the LLM.
    processed_headings = db.query(Chunk).filter(
        Chunk.document_id == job.document_id,
        Chunk.type == 'heading'
    ).order_by(Chunk.start_line.desc()).limit(CONTEXT_MAX_HEADINGS).all()

    heading_lines = []
    if processed_headings:
        heading_lines.append("## Processed Headings")
        for h in reversed(processed_headings):
            heading_lines.append(f"[L{h.level}] {h.raw_content.strip()} (Lines {h.start_line}-{h.end_line})")

    assets_metadata = reading_service.list_assets_by_document_id(job.document_id)

    asset_lines = []
    if assets_metadata:
        asset_lines.append("## Available Assets")
        for asset_meta in assets_metadata:
            asset_id = asset_meta['asset_id']
            asset_details = reading_service._get_assets_in_content(f"asset://{asset_id}", job.document_id)
            description = "[ANALYSIS PENDING]"
            if asset_details and asset_details[0].get('description'):
                description = asset_details[0]['description'].strip().replace('\n', ' ')
            asset_lines.append(f"ID: {asset_id}, Type: {asset_meta['asset_type']}, Description: \"{description}\"")

    content_lines = [f"# Content for Analysis (Lines {start_line_offset}-...)"]
    for i, line in enumerate(megachunk_text.splitlines()):
        line_num = start_line_offset + i
        truncated_line = line[:MAX_LINE_LENGTH_IN_CONTEXT] + ('...' if len(line) > MAX_LINE_LENGTH_IN_CONTEXT else '')
        content_lines.append(f"{line_num}: {truncated_line}")

    context_parts = []
    if heading_lines:
        context_parts.extend(["# Document Context", *heading_lines])
    if asset_lines:
        context_parts.extend(asset_lines if not heading_lines else ["", *asset_lines])
    context_parts.extend(["---", *content_lines])
    return "\n".join(context_parts)

def _is_image_caption(text: str) -> bool:
    """Check if a heading text is likely an image caption."""
    # Regex to find patterns like "图1", "图 1-2", "Figure 3", etc.
    return bool(re.match(r'^(图|figure)\s*\d+([\-–—.]\d+)*', text, re.IGNORECASE))

def _validate_and_merge_drafts(drafts: List[_ChunkDraft], trace_logger: logging.Logger) -> List[_ChunkDraft]:
    """
    Filters out invalid drafts and merges content chunks based on size and hierarchy rules.
    Enhanced merging strategy to aggressively combine small chunks.
    """
    if not drafts:
        return []

    # Step 1: Pre-filter invalid headings (e.g., image captions)
    valid_drafts = []
    for draft in drafts:
        if draft.type == 'heading' and _is_image_caption(draft.raw_content):
            trace_logger.warning(f"""--- FILTERED INVALID HEADING ---\n- Reason: Likely an image caption.\n- Content: '{draft.raw_content}'""")
            continue
        valid_drafts.append(draft)

    # Step 2: Enhanced merging with aggressive small chunk handling
    if not valid_drafts:
        return []

    final_chunks = []
    current_merged_chunk: Optional[_ChunkDraft] = None
    pending_small_chunks = []  # Buffer for small chunks that need merging

    def _finalize_current_chunk():
        """Helper to finalize the current merged chunk with pending small chunks."""
        nonlocal current_merged_chunk, pending_small_chunks

        if not current_merged_chunk:
            return

        # Try to merge pending small chunks first
        for small_chunk in pending_small_chunks:
            if (len(current_merged_chunk.raw_content) + len(small_chunk.raw_content)) < MERGE_THRESHOLD_CHARS:
                current_merged_chunk.raw_content += "\n" + small_chunk.raw_content
                current_merged_chunk.end_line = small_chunk.end_line
                current_merged_chunk.summary += f" | {small_chunk.summary}"
                trace_logger.info(f"""--- MERGED SMALL CHUNK ---\n- Small chunk lines: {small_chunk.start_line}-{small_chunk.end_line}\n- Into chunk lines: {current_merged_chunk.start_line}-{current_merged_chunk.end_line}""")
            else:
                # If can't merge, add the small chunk as-is (will be handled later)
                final_chunks.append(small_chunk)

        pending_small_chunks.clear()

        # Check final size and add to results
        if len(current_merged_chunk.raw_content) < MIN_CHUNK_CHARS:
            trace_logger.warning(f"""--- UNDERSIZED CHUNK ---\n- Parent: {current_merged_chunk.parent_heading_text}\n- Lines: {current_merged_chunk.start_line}-{current_merged_chunk.end_line}\n- Size: {len(current_merged_chunk.raw_content)} chars (min: {MIN_CHUNK_CHARS})""")
        final_chunks.append(current_merged_chunk)
        current_merged_chunk = None

    for draft in valid_drafts:
        if draft.type == 'heading':
            _finalize_current_chunk()
            final_chunks.append(draft)
            continue

        # It's a content chunk
        if not current_merged_chunk:
            current_merged_chunk = draft
            continue

        # Enhanced merging conditions
        same_parent = current_merged_chunk.parent_id == draft.parent_id
        within_threshold = (len(current_merged_chunk.raw_content) + len(draft.raw_content)) < MERGE_THRESHOLD_CHARS
        current_is_small = len(current_merged_chunk.raw_content) < MIN_CHUNK_CHARS
        draft_is_small = len(draft.raw_content) < MIN_CHUNK_CHARS

        # More aggressive merging: merge if same parent OR if either chunk is small
        can_merge = within_threshold and (same_parent or current_is_small or draft_is_small)

        if can_merge:
            current_merged_chunk.raw_content += "\n" + draft.raw_content
            current_merged_chunk.end_line = draft.end_line
            current_merged_chunk.summary += f" | {draft.summary}"
            trace_logger.info(f"""--- MERGED CHUNKS ---\n- Reason: {'Same parent' if same_parent else 'Small chunk handling'}\n- Result lines: {current_merged_chunk.start_line}-{current_merged_chunk.end_line}\n- Result size: {len(current_merged_chunk.raw_content)} chars""")
        else:
            # If current chunk is too small, try to buffer it for later merging
            if len(current_merged_chunk.raw_content) < MIN_CHUNK_CHARS:
                pending_small_chunks.append(current_merged_chunk)
                trace_logger.info(f"""--- BUFFERING SMALL CHUNK ---\n- Lines: {current_merged_chunk.start_line}-{current_merged_chunk.end_line}\n- Size: {len(current_merged_chunk.raw_content)} chars""")
            else:
                final_chunks.append(current_merged_chunk)
            current_merged_chunk = draft

    # Handle remaining chunks
    _finalize_current_chunk()

    # Final pass: try to merge any remaining small chunks with adjacent chunks
    if len(final_chunks) > 1:
        merged_final = []
        i = 0
        while i < len(final_chunks):
            current = final_chunks[i]

            # If current chunk is small and content type, try to merge with next
            if (current.type == 'content' and
                len(current.raw_content) < MIN_CHUNK_CHARS and
                i + 1 < len(final_chunks) and
                final_chunks[i + 1].type == 'content' and
                (len(current.raw_content) + len(final_chunks[i + 1].raw_content)) < MERGE_THRESHOLD_CHARS):

                next_chunk = final_chunks[i + 1]
                current.raw_content += "\n" + next_chunk.raw_content
                current.end_line = next_chunk.end_line
                current.summary += f" | {next_chunk.summary}"
                trace_logger.info(f"""--- FINAL MERGE ---\n- Merged small chunk {current.start_line}-{current.end_line} with {next_chunk.start_line}-{next_chunk.end_line}""")
                i += 1  # Skip the next chunk as it's been merged

            merged_final.append(current)
            i += 1

        final_chunks = merged_final

    return final_chunks

def identify_headings_in_megachunk(
    db: Session,
    job: Job,
    llm_client: Any,
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger
) -> List[dict]:
    """第一步：识别当前megachunk中的标题，基于全局标题树结构"""
    from .prompts import HEADING_IDENTIFICATION_PROMPT
    from .validators import IdentifyHeadingsTool

    # 构建全局标题树上下文
    existing_headings = db.query(Chunk).filter(
        Chunk.document_id == job.document_id,
        Chunk.type == 'heading'
    ).order_by(Chunk.start_line).all()

    heading_tree_context = ""
    if existing_headings:
        heading_tree_context = "\n\n## 现有全局标题树结构：\n"
        for h in existing_headings:
            indent = "  " * (h.level - 1)
            heading_tree_context += f"{indent}[L{h.level}] {h.raw_content.strip()} (行 {h.start_line}-{h.end_line})\n"
    else:
        heading_tree_context = "\n\n## 现有全局标题树结构：\n（当前为空，这是文档的开始部分）\n"

    current_text = "\n".join(megachunk_lines)

    # 构建完整提示
    full_prompt = f"{HEADING_IDENTIFICATION_PROMPT}\n{heading_tree_context}\n\n## 当前需要分析的文本块：\n{current_text}\n\n请识别当前文本块中属于主文档结构的标题。"

    # 调用LLM进行标题识别
    schema = IdentifyHeadingsTool.model_json_schema()
    schema["name"] = "identify_headings"
    tools = [{
        "type": "function",
        "function": schema
    }]

    try:
        response = llm_client.chat.completions.create(
            model=getattr(llm_client, 'model_name', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": "你是一个专业的文档结构分析器。"},
                {"role": "user", "content": full_prompt}
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.1
        )

        identified_headings = []
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "identify_headings":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        headings_data = arguments.get('headings', [])
                        identified_headings.extend(headings_data)
                        trace_logger.info(f"""--- IDENTIFIED HEADINGS ---\n- Count: {len(headings_data)}")
                        for h in headings_data:
                            trace_logger.info(f"  - L{h.get('level')}: {h.get('text')} (行 {h.get('line_number')})""")
                    except json.JSONDecodeError as e:
                        trace_logger.warning(f"""--- HEADING IDENTIFICATION ERROR ---\n- JSON decode error: {e}""")

        return identified_headings

    except Exception as e:
        trace_logger.error(f"""--- HEADING IDENTIFICATION FAILED ---\n- Error: {e}""")
        return []

def split_megachunk_with_llm(
    db: Session,
    job: Job,
    llm_client: Any,
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger,
    is_final_batch: bool = False
) -> Tuple[int, int]:
    """两步法分块处理：第一步识别标题，第二步基于标题树分割内容"""

    # 第一步：识别标题
    identified_headings = identify_headings_in_megachunk(
        db, job, llm_client, megachunk_lines, megachunk_start_line, trace_logger
    )

    # 如果LLM没有返回任何标题，则启用基于规则的备用分割方案
    if not identified_headings:
        trace_logger.warning(f"""--- LLM IDENTIFIED NO HEADINGS ---""")
        trace_logger.warning(f"""--- SWITCHING TO RULE-BASED SPLITTING for lines {megachunk_start_line}-{megachunk_start_line + len(megachunk_lines) - 1} ---""")
        return split_megachunk_with_rules(
            db, job, megachunk_lines, megachunk_start_line, trace_logger, llm_client
        )

    # 第二步：基于标题结构分割内容并创建分块
    return _create_chunks_from_headings(
        db, job, identified_headings, megachunk_lines, megachunk_start_line,
        trace_logger, llm_client, is_final_batch
    )

def split_megachunk_with_rules(
    db: Session,
    job: Job,
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger,
    llm_client: Any  # llm_client is no longer used but kept for signature consistency
) -> Tuple[int, int]:
    """
    受 LangChain 的 RecursiveCharacterTextSplitter 启发的、基于规则的备用分块方法。
    该方法合并小段落以达到目标尺寸，并分割过大的段落。
    此版本已修改为完全不依赖LLM。
    """
    TARGET_CHUNK_SIZE = 1200
    MIN_CHUNK_SIZE = 256

    class Paragraph:
        def __init__(self, start_line, end_line, text):
            self.start_line = start_line
            self.end_line = end_line
            self.text = text
            self.char_count = len(text)

    # 1. 段落化：将行组合成段落
    paragraphs: List[Paragraph] = []
    current_lines = []
    p_start_line = megachunk_start_line
    for i, line in enumerate(megachunk_lines):
        line_num = megachunk_start_line + i
        if line.strip():
            if not current_lines:
                p_start_line = line_num
            current_lines.append(line)
        else:
            if current_lines:
                paragraphs.append(Paragraph(p_start_line, line_num - 1, "\n".join(current_lines)))
                current_lines = []
    if current_lines:
        paragraphs.append(Paragraph(p_start_line, megachunk_start_line + len(megachunk_lines) - 1, "\n".join(current_lines)))

    if not paragraphs:
        return megachunk_start_line + len(megachunk_lines) - 1, 0

    # 2. 获取父级上下文
    parent_heading = db.query(Chunk).filter(
        Chunk.document_id == job.document_id,
        Chunk.type == 'heading',
        Chunk.start_line < megachunk_start_line
    ).order_by(Chunk.start_line.desc()).first()
    parent_id = parent_heading.id if parent_heading else None
    parent_level = parent_heading.level if parent_heading else 0
    parent_name = parent_heading.raw_content if parent_heading else "[DOCUMENT ROOT]"

    # 3. 合并-分割逻辑
    final_chunks = []
    current_chunk_paragraphs: List[Paragraph] = []
    current_chunk_chars = 0

    def finalize_chunk():
        nonlocal current_chunk_chars, current_chunk_paragraphs
        if not current_chunk_paragraphs:
            return

        chunk_text = "\n\n".join(p.text for p in current_chunk_paragraphs)
        start_line = current_chunk_paragraphs[0].start_line
        end_line = current_chunk_paragraphs[-1].end_line

        if len(chunk_text) < MIN_CHUNK_SIZE and final_chunks:
             # 如果当前块太小，尝试合并到前一个块
            last_chunk = final_chunks[-1]
            if last_chunk.char_count + len(chunk_text) < TARGET_CHUNK_SIZE * 1.2:
                last_chunk.raw_content += "\n\n" + chunk_text
                last_chunk.end_line = end_line
                last_chunk.char_count = len(last_chunk.raw_content)
                trace_logger.info(f"""--- MERGED TINY RULE-BASED CHUNK ---\n- Merged lines {start_line}-{end_line} into previous chunk.""")
                current_chunk_paragraphs = []
                current_chunk_chars = 0
                return

        # --- MODIFIED: No LLM Call ---
        clean_text = re.sub(r'\s+', ' ', chunk_text).strip()
        preview = clean_text[:200]
        if len(clean_text) > 200:
            preview += "..."
        summary = f"[{parent_name or '文档开头'}] {preview}"
        
        new_chunk = Chunk(
            id=uuid.uuid4(), document_id=job.document_id, parent_id=parent_id,
            start_line=start_line, end_line=end_line, raw_content=chunk_text,
            char_count=len(chunk_text), summary=summary,
            paraphrase=None, type='content', level=parent_level + 1
        )
        final_chunks.append(new_chunk)
        log_message = (
            f"""--- CREATED RULE-BASED CHUNK (NO LLM) ---\n- Parent: {parent_name}
- Lines: {start_line}-{end_line}
- Size: {len(chunk_text)} chars"""
        )
        trace_logger.info(log_message)

        current_chunk_paragraphs = []
        current_chunk_chars = 0

    for p in paragraphs:
        # 如果单个段落就超长，直接处理并作为一个块
        if p.char_count > TARGET_CHUNK_SIZE:
            finalize_chunk() # 先将之前的块保存
            
            # --- MODIFIED: No LLM Call ---
            clean_text = re.sub(r'\s+', ' ', p.text).strip()
            preview = clean_text[:200]
            if len(clean_text) > 200:
                preview += "..."
            summary = f"[{parent_name or '文档开头'}] {preview}"

            final_chunks.append(Chunk(
                id=uuid.uuid4(), document_id=job.document_id, parent_id=parent_id,
                start_line=p.start_line, end_line=p.end_line, raw_content=p.text,
                char_count=p.char_count, summary=summary,
                paraphrase=None, type='content', level=parent_level + 1
            ))
            log_message = (
                f"""--- CREATED OVERSIZED RULE-BASED CHUNK (NO LLM) ---\n- Lines: {p.start_line}-{p.end_line}
- Size: {p.char_count} chars"""
            )
            trace_logger.warning(log_message)
            continue

        if current_chunk_chars + p.char_count > TARGET_CHUNK_SIZE and current_chunk_paragraphs:
            finalize_chunk()

        current_chunk_paragraphs.append(p)
        current_chunk_chars += p.char_count

    finalize_chunk() # 保存最后一个块

    for chunk in final_chunks:
        db.add(chunk)

    last_processed_line = megachunk_start_line + len(megachunk_lines) - 1
    return last_processed_line, len(final_chunks)




def _create_chunks_from_headings(
    db: Session,
    job: Job,
    identified_headings: List[dict],
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger,
    llm_client,
    is_final_batch: bool = False
) -> Tuple[int, int]:
    """基于识别出的标题创建分块"""

    heading_chunks = []
    search_from_idx = 0  # Start searching from the beginning of the megachunk

    for heading_data in identified_headings:
        level = heading_data.get('level')
        text = heading_data.get('text', "").strip()
        parent_text = heading_data.get('parent_text')

        if not text or _is_image_caption(text):
            trace_logger.warning(f"""--- SKIPPED INVALID HEADING ---\n- Reason: Empty or image caption.\n- Content: '{heading_data.get('text')}'""")
            continue

        # --- NEW: Search-and-Index Logic ---
        found_match = False
        line_number = -1
        for i in range(search_from_idx, len(megachunk_lines)):
            # Use a reasonably flexible match: strip whitespace and compare
            if megachunk_lines[i].strip() == text:
                line_number = megachunk_start_line + i
                search_from_idx = i + 1  # Next search starts after this line
                found_match = True
                break
        
        if not found_match:
            trace_logger.error(f"""--- HEADING TEXT NOT FOUND ---\n- LLM returned heading text that could not be found in the megachunk.\n- Text: '{text}'""")
            continue
        # --- END: New Logic ---

        parent_id = None
        if parent_text:
            parent_chunk = db.query(Chunk).filter_by(
                document_id=job.document_id,
                type='heading',
                raw_content=parent_text.strip()
            ).order_by(Chunk.start_line.desc()).first()
            if parent_chunk:
                parent_id = parent_chunk.id

        heading_chunk = Chunk(
            id=uuid.uuid4(),
            document_id=job.document_id,
            parent_id=parent_id,
            start_line=line_number,
            end_line=line_number,
            raw_content=text,
            char_count=len(text),
            summary=f"标题: {text}",
            paraphrase=None,
            type='heading',
            level=level
        )

        db.add(heading_chunk)
        heading_chunks.append(heading_chunk)

        trace_logger.info(f"""--- CREATED HEADING CHUNK ---\n- Level: {level}\n- Text: {text}\n- Line: {line_number} (Determined by search)\n- Parent: {parent_text or 'None'} """)

    # Then based on the now-accurate headings, create content chunks
    content_chunks = _create_content_chunks_between_headings(
        db, job, heading_chunks, megachunk_lines, megachunk_start_line,
        trace_logger, llm_client, is_final_batch
    )

    total_chunks = len(heading_chunks) + len(content_chunks)
    last_processed_line = megachunk_start_line - 1

    # 计算最后处理的行号
    all_chunks = heading_chunks + content_chunks
    if all_chunks:
        last_processed_line = max(chunk.end_line for chunk in all_chunks)

    # 处理最后一个批次的特殊情况
    if is_final_batch and content_chunks:
        megachunk_end_line = megachunk_start_line + len(megachunk_lines) - 1
        last_content_chunk = content_chunks[-1]

        if last_content_chunk.end_line < megachunk_end_line:
            # 将剩余行附加到最后一个内容分块
            remaining_start_idx = last_content_chunk.end_line - megachunk_start_line + 1
            remaining_lines = megachunk_lines[remaining_start_idx:]

            if remaining_lines:
                remaining_content = "\n".join(remaining_lines)
                last_content_chunk.raw_content += "\n" + remaining_content
                last_content_chunk.end_line = megachunk_end_line
                last_content_chunk.char_count = len(last_content_chunk.raw_content)
                last_content_chunk.summary += " | 包含文档末尾剩余内容"
                last_processed_line = megachunk_end_line

                trace_logger.info(f"""--- FINAL BATCH MERGE ---\n- Appended lines {remaining_start_idx + megachunk_start_line}-{megachunk_end_line} to last content chunk""")

    if total_chunks == 0:
        # 如果没有创建任何分块，推进到megachunk末尾防止无限循环
        fallback_line = megachunk_start_line + len(megachunk_lines) - 1
        trace_logger.info(f"""--- FALLBACK PROGRESS ---\n- No chunks created, advancing to line {fallback_line}""")
        return fallback_line, 0

    return last_processed_line, total_chunks

def _create_content_chunks_between_headings(
    db: Session,
    job: Job,
    heading_chunks: List[Chunk],
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger,
    llm_client,
    is_final_batch: bool = False
) -> List[Chunk]:
    """在标题之间创建内容分块"""

    content_chunks = []
    megachunk_end_line = megachunk_start_line + len(megachunk_lines) - 1

    # 获取所有相关的标题（包括已存在的和新创建的）
    all_headings = db.query(Chunk).filter(
        Chunk.document_id == job.document_id,
        Chunk.type == 'heading',
        Chunk.start_line <= megachunk_end_line
    ).order_by(Chunk.start_line).all()

    # 添加新创建的标题
    for new_heading in heading_chunks:
        if new_heading not in all_headings:
            all_headings.append(new_heading)

    # 重新排序
    all_headings.sort(key=lambda h: h.start_line)

    # --- 鲁棒性修复：确保总有一个“根”边界 ---
    boundaries = []
    # 查找此megachunk之前的最后一个标题，作为上下文根
    last_heading_before_megachunk = db.query(Chunk).filter(
        Chunk.document_id == job.document_id,
        Chunk.type == 'heading',
        Chunk.start_line < megachunk_start_line
    ).order_by(Chunk.start_line.desc()).first()

    if last_heading_before_megachunk:
        boundaries.append(last_heading_before_megachunk)
    else:
        # 如果整个文档到目前为止都没有标题，则创建一个虚拟的文档根
        is_doc_empty_of_headings = db.query(Chunk.id).filter(
            Chunk.document_id == job.document_id,
            Chunk.type == 'heading'
        ).first() is None
        if is_doc_empty_of_headings:
            doc_root_dummy_heading = Chunk(end_line=0, raw_content="[DOCUMENT ROOT]", id=None, level=0)
            boundaries.append(doc_root_dummy_heading)

    boundaries.extend(all_headings)

    # 在标题之间创建内容分块
    for i in range(len(boundaries)):
        current_boundary = boundaries[i]
        # 跳过不在当前megachunk处理范围内的旧边界
        if current_boundary in all_headings and current_boundary.start_line < megachunk_start_line:
             continue

        parent_heading = current_boundary if current_boundary.id is not None else None

        # 确定内容区域的开始和结束
        content_start_line = current_boundary.end_line + 1

        # 找到下一个标题或megachunk结束
        next_boundary_found = False
        for j in range(i + 1, len(boundaries)):
            # Find the next heading that is actually a heading
            if boundaries[j].type == 'heading':
                next_boundary = boundaries[j]
                content_end_line = next_boundary.start_line - 1
                next_boundary_found = True
                break

        if not next_boundary_found:
            content_end_line = megachunk_end_line

        # 检查是否有内容需要处理
        if content_start_line <= content_end_line and content_start_line <= megachunk_end_line:
            # 确保内容区域在当前megachunk范围内
            actual_start = max(content_start_line, megachunk_start_line)
            actual_end = min(content_end_line, megachunk_end_line)

            if actual_start <= actual_end:
                # 提取内容
                start_idx = actual_start - megachunk_start_line
                end_idx = actual_end - megachunk_start_line + 1
                content_lines = megachunk_lines[start_idx:end_idx]

                if content_lines and any(line.strip() for line in content_lines):
                    content_text = "\n".join(content_lines).strip()

                    # 生成内容摘要
                    parent_name = parent_heading.raw_content if parent_heading else "[DOCUMENT ROOT]"
                    summary_result = _generate_content_summary(content_text, parent_name, llm_client)

                    # 创建内容分块
                    content_chunk = Chunk(
                        id=uuid.uuid4(),
                        document_id=job.document_id,
                        parent_id=parent_heading.id if parent_heading else None,
                        start_line=actual_start,
                        end_line=actual_end,
                        raw_content=content_text,
                        char_count=len(content_text),
                        summary=summary_result["summary"],
                        paraphrase=summary_result["paraphrase"],
                        type='content',
                        level=(parent_heading.level + 1) if parent_heading else 0
                    )

                    db.add(content_chunk)
                    content_chunks.append(content_chunk)

                    trace_logger.info(f"""--- CREATED CONTENT CHUNK ---\n- Parent: {parent_name or '[DOCUMENT ROOT]'}\n- Lines: {actual_start}-{actual_end}\n- Size: {len(content_text)} chars\n- Summary: {summary_result['summary'][:100]}...""")

    return content_chunks



def _generate_content_summary(content_text: str, parent_heading: str, llm_client) -> dict:
    """使用LLM为内容生成摘要和释义"""
    if not content_text.strip():
        return {
            "summary": f"空内容区域（属于: {parent_heading}）",
            "paraphrase": None
        }

    # 构建提示词
    prompt = f"""请为以下内容生成摘要和释义：

标题上下文：{parent_heading}

内容：
{content_text}

请生成：
1. 一个简洁的摘要（50-100字）
2. 如果需要，提供一个改写版本（可选）"""

    # 准备工具定义
    schema = GenerateContentSummaryTool.model_json_schema()
    schema["name"] = "generate_content_summary"
    tools = [{
        "type": "function",
        "function": schema
    }]

    try:
        response = llm_client.chat.completions.create(
            model=getattr(llm_client, 'model_name', 'gpt-4o-mini'),
            messages=[
                {"role": "system", "content": "你是一个专业的内容摘要生成器。请为给定的内容生成准确、简洁的摘要。"},
                {"role": "user", "content": prompt}
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0.1
        )

        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "generate_content_summary":
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        return {
                            "summary": arguments.get("summary", f"内容摘要（属于: {parent_heading}）"),
                            "paraphrase": arguments.get("paraphrase")
                        }
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse LLM response for content summary")

        # 如果LLM没有返回工具调用，使用简单的备用方案
        lines = content_text.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        preview_lines = non_empty_lines[:2] if non_empty_lines else []
        preview = " ".join(preview_lines)[:150]

        return {
            "summary": f"""内容摘要（属于: {parent_heading}）: {preview}...""",
            "paraphrase": None
        }

    except Exception as e:
        logger.warning(f"LLM summary generation failed for parent '{parent_heading}'. Falling back to simple extraction. Error: {e}")
        
        # Fallback: 提取前200个字符作为摘要
        clean_text = re.sub(r'\s+', ' ', content_text).strip()
        preview = clean_text[:200]
        if len(clean_text) > 200:
            preview += "..."

        return {
            "summary": f"[{parent_heading or '文档开头'}] {preview}",
            "paraphrase": None
        }

def process_llm_response(
    db: Session,
    job: Job,
    tool_calls: List[Any],
    megachunk_lines: List[str],
    megachunk_start_line: int,
    trace_logger: logging.Logger,
    is_final_batch: bool = False
) -> Tuple[int, int]:
    if not tool_calls:
        logger.warning(f"Job {job.id}: LLM returned no tool calls for megachunk starting at line {megachunk_start_line}.")
        trace_logger.warning(f"""--- LLM RETURNED NO TOOL CALLS ---""")
        return megachunk_start_line - 1, 0

    try:
        tool_calls.sort(key=lambda call: json.loads(call.function.arguments).get('start_line', float('inf')))
    except (json.JSONDecodeError, AttributeError, KeyError) as e:
        logger.warning(f"""Job {job.id}: Could not sort tool_calls due to malformed arguments: {e}""")
        trace_logger.warning(f"""--- FAILED TO SORT TOOL CALLS ---
- Error: {e}""")

    # Step 1: Parse all tool calls into a list of draft objects
    drafts: List[_ChunkDraft] = []
    for tool_call in tool_calls:
        # ... (parsing logic remains the same)
        function_name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            trace_logger.warning(f"""--- SKIPPED INVALID CHUNK ---
- Function: {function_name}
- Reason: Invalid JSON in arguments.""")
            continue

        start_line_abs = arguments.get('start_line')
        end_line_abs = arguments.get('end_line')

        if not all(isinstance(i, int) for i in [start_line_abs, end_line_abs]) or not (start_line_abs > 0 and end_line_abs >= start_line_abs):
            trace_logger.warning(f"""--- SKIPPED INVALID CHUNK ---
- Function: {function_name}
- Reason: Invalid or illogical line numbers. start={start_line_abs}, end={end_line_abs}""")
            continue

        megachunk_end_line = megachunk_start_line + len(megachunk_lines) - 1
        if not (megachunk_start_line <= start_line_abs and end_line_abs <= megachunk_end_line):
            trace_logger.warning(f"""--- SKIPPED INVALID CHUNK ---
- Function: {function_name}
- Reason: Line numbers out of megachunk bounds ({megachunk_start_line}-{megachunk_end_line}). start={start_line_abs}, end={end_line_abs}""")
            continue

        start_idx_rel = start_line_abs - megachunk_start_line
        end_idx_rel = end_line_abs - megachunk_start_line + 1
        raw_content = "\n".join(megachunk_lines[start_idx_rel:end_idx_rel])

        parent_id = None
        parent_heading_text = arguments.get('parent_heading_text')
        if parent_heading_text:
            parent_chunk = db.query(Chunk).filter_by(document_id=job.document_id, type='heading', raw_content=parent_heading_text).order_by(Chunk.start_line.desc()).first()
            if parent_chunk:
                parent_id = parent_chunk.id

        draft = _ChunkDraft(
            type='heading' if function_name == "create_heading_chunk" else 'content',
            level=arguments.get('level', -1),
            start_line=start_line_abs,
            end_line=end_line_abs,
            raw_content=raw_content.lstrip('# ').strip() if function_name == "create_heading_chunk" else raw_content,
            summary=arguments['summary'],
            paraphrase=arguments.get('paraphrase'),
            parent_heading_text=parent_heading_text,
            parent_id=parent_id
        )
        drafts.append(draft)

    # Step 2: Run the new validation and merging logic
    final_drafts = _validate_and_merge_drafts(drafts, trace_logger)

    # Step 3: Create DB objects from the final, validated drafts
    last_processed_line = megachunk_start_line - 1

    # Handle final batch special case: append remaining lines to last content chunk
    if is_final_batch and final_drafts:
        # Find the last content chunk
        last_content_chunk = None
        for draft in reversed(final_drafts):
            if draft.type == 'content':
                last_content_chunk = draft
                break

        if last_content_chunk:
            # Calculate unprocessed lines
            megachunk_end_line = megachunk_start_line + len(megachunk_lines) - 1
            if last_content_chunk.end_line < megachunk_end_line:
                # Get remaining lines
                remaining_start_idx = last_content_chunk.end_line - megachunk_start_line + 1
                remaining_lines = megachunk_lines[remaining_start_idx:]

                if remaining_lines:
                    remaining_content = "\n".join(remaining_lines)
                    last_content_chunk.raw_content += "\n" + remaining_content
                    last_content_chunk.end_line = megachunk_end_line
                    last_content_chunk.summary += " | 包含文档末尾剩余内容"

                    trace_logger.info(f"""--- FINAL BATCH MERGE ---
- Appended remaining lines {last_content_chunk.end_line - len(remaining_lines) + 1}-{megachunk_end_line} to last content chunk
- Final chunk lines: {last_content_chunk.start_line}-{last_content_chunk.end_line}
- Final chunk size: {len(last_content_chunk.raw_content)} chars""")

    for draft in final_drafts:
        new_chunk = Chunk(
            id=uuid.uuid4(),
            document_id=job.document_id,
            parent_id=draft.parent_id,
            start_line=draft.start_line,
            end_line=draft.end_line,
            raw_content=draft.raw_content,
            char_count=len(draft.raw_content),
            summary=draft.summary,
            paraphrase=draft.paraphrase,
            type=draft.type,
            level=draft.level
        )
        trace_logger.info(f"""--- CREATING CHUNK (post-validation) ---
- Type: {new_chunk.type}
- Level: {new_chunk.level}
- Parent ID: {new_chunk.parent_id}
- Lines: {new_chunk.start_line}-{new_chunk.end_line}
- Summary: {new_chunk.summary}
- Raw Content Preview: '{new_chunk.raw_content[:100].replace(chr(10), ' ')}...' """)
        db.add(new_chunk)
        last_processed_line = max(last_processed_line, new_chunk.end_line)

    created_chunk_count = len(final_drafts)
    if created_chunk_count == 0:
        if tool_calls:
            trace_logger.warning("""--- ALL TOOL CALLS WERE INVALID OR FILTERED ---""")
        else:
            trace_logger.warning("""--- NO TOOL CALLS RECEIVED ---""")

        # Ensure progress by advancing to the end of the megachunk
        # This prevents infinite loops when LLM fails to generate valid chunks
        fallback_line = megachunk_start_line + len(megachunk_lines) - 1
        trace_logger.info(f"""--- FALLBACK PROGRESS ---\n- Advancing to line {fallback_line} to prevent infinite loop""")
        return fallback_line, 0

    return last_processed_line, created_chunk_count
