from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.db.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.kb_auth import get_kb_or_public
from app.services.search_service import SearchService
from app.schemas.search import (
    SearchQuery, SearchResponse, FragmentDetailResponse,
    SearchStats, FragmentType, QueryParseResult
)
from app.schemas.fragment import FragmentStatsResponse
from app.models.user import User
from app.config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["search"])

@router.get("/fragments/{fragment_id}", response_model=FragmentDetailResponse, operation_id="search_get_fragment")
def get_fragment(
    fragment_id: str = Path(..., description="Fragment ID"),
    kb_id: Optional[str] = Query(None, description="知识库ID（可选，用于权限验证）"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """根据ID获取Fragment详情"""
    try:
        search_service = SearchService(db)
        fragment = search_service.get_fragment_by_id(fragment_id, kb_id)

        if not fragment:
            raise HTTPException(status_code=404, detail="Fragment不存在")

        return FragmentDetailResponse(**fragment)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Fragment详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Fragment详情失败: {str(e)}")

@router.post("/kbs/{kb_id}/search", response_model=SearchResponse)
def search_knowledge_base(
    query: SearchQuery,
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kb_or_public)
):
    """在指定知识库中执行语义搜索"""
    try:
        search_service = SearchService(db)

        # 执行搜索
        results = search_service.search(
            kb_id=kb_id,
            query=query.query,
            top_k=query.top_k,
            fragment_types=query.fragment_types,
            must_tags=query.must_tags,
            must_not_tags=query.must_not_tags,
            like_tags=query.like_tags,
            parse_query=query.parse_query,
            include_screenshots=query.include_screenshots,
            include_figures=query.include_figures
        )

        # 检查是否有错误
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        return SearchResponse(**results)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")



@router.get("/kbs/{kb_id}/search", response_model=SearchResponse)
def search_knowledge_base_get(
    kb_id: str = Path(..., description="知识库ID"),
    q: str = Query(..., description="搜索查询字符串，支持标签语法：' +tag'（必须有）、' -tag'（必须没有）、' ~tag'（偏好）"),
    top_k: int = Query(10, ge=1, le=50, description="返回结果数量"),
    fragment_types: List[str] = Query(["text"], description="Fragment类型过滤，支持的类型：text, image, table, code等"),
    must_tags: List[str] = Query([], description="必须包含的标签"),
    must_not_tags: List[str] = Query([], description="必须不包含的标签"),
    like_tags: List[str] = Query([], description="偏好标签"),
    parse_query: bool = Query(True, description="是否解析查询字符串中的标签语法"),
    include_screenshots: bool = Query(True, description="是否包含相关截图"),
    include_figures: bool = Query(True, description="是否包含相关图表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kb_or_public)
):
    """GET方式的搜索接口（便于URL调用）"""
    try:
        search_service = SearchService(db)

        # 将字符串类型转换为FragmentType枚举
        fragment_type_enums = []
        for ft_str in fragment_types:
            try:
                fragment_type_enums.append(FragmentType(ft_str))
            except ValueError:
                # 如果转换失败，记录警告并跳过无效类型
                logger.warning(f"无效的fragment_type: {ft_str}")
                continue

        # 如果没有有效的类型，使用默认值
        if not fragment_type_enums:
            fragment_type_enums = [FragmentType.TEXT]

        # 执行搜索
        results = search_service.search(
            kb_id=kb_id,
            query=q,
            top_k=top_k,
            fragment_types=fragment_type_enums,
            must_tags=must_tags,
            must_not_tags=must_not_tags,
            like_tags=like_tags,
            parse_query=parse_query,
            include_screenshots=include_screenshots,
            include_figures=include_figures
        )

        # 检查是否有错误
        if "error" in results:
            raise HTTPException(status_code=500, detail=results["error"])

        return SearchResponse(**results)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"搜索失败: {str(e)}")

@router.get("/kbs/{kb_id}/fragments/stats", response_model=FragmentStatsResponse)
def get_kb_fragments_stats(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kb_or_public)
):
    """获取知识库Fragment统计信息"""
    try:
        search_service = SearchService(db)
        stats = search_service.get_kb_fragments_stats(kb_id)

        # 检查是否有错误
        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])

        return FragmentStatsResponse(**stats)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取Fragment统计信息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Fragment统计信息失败: {str(e)}")

@router.get("/kbs/{kb_id}/search/types", response_model=List[str])
def get_available_fragment_types(
    kb_id: str = Path(..., description="知识库ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_kb_or_public)
):
    """获取知识库中可用的Fragment类型"""
    try:
        from app.models import Fragment, KBFragment
        from sqlalchemy import distinct

        # 查询知识库中存在的Fragment类型
        types = db.query(distinct(Fragment.fragment_type)).join(
            KBFragment, Fragment.id == KBFragment.fragment_id
        ).filter(KBFragment.kb_id == kb_id).all()

        return [t[0] for t in types if t[0]]

    except Exception as e:
        logger.error(f"获取Fragment类型失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取Fragment类型失败: {str(e)}")

@router.get("/fragment-types", response_model=List[str])
def get_all_fragment_types():
    """获取所有支持的Fragment类型"""
    return [ft.value for ft in FragmentType]

@router.post("/parse-query", response_model=QueryParseResult)
def parse_search_query(
    query: str = Query(..., description="要解析的查询字符串"),
    current_user: User = Depends(get_current_user)
):
    """解析搜索查询字符串，返回解析结果供用户确认"""
    try:
        from app.utils.query_parser import QueryParser

        parser = QueryParser()
        parsed = parser.parse(query)

        return QueryParseResult(
            text_query=parsed.text,
            must_tags=parsed.must_tags,
            must_not_tags=parsed.must_not_tags,
            like_tags=parsed.like_tags,
            original_query=parsed.original_query
        )

    except Exception as e:
        logger.error(f"解析查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"解析查询失败: {str(e)}")