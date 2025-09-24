
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional

# 模拟依赖项，实际项目中应替换为真实的服务和模型
from ..dependencies import get_current_user, get_bookmark_service
from ..services.bookmark_service import BookmarkService
from ..models.user import User
from pydantic import BaseModel, Field

# --- Pydantic 模型 ---

class BookmarkBase(BaseModel):
    name: str = Field(..., description="书签的名称，例如 'data_security_guideline'。")
    knowledge_space_id: uuid.UUID = Field(..., description="所属知识空间的ID。")
    parent_id: Optional[uuid.UUID] = Field(None, description="父书签的ID，用于创建层级结构。")
    visibility: str = Field("private", description="可见性: 'private' 或 'public'。")
    document_id: Optional[uuid.UUID] = Field(None, description="（可选）指向的文档ID。")
    start_line: Optional[int] = Field(None, description="（可选）起始行号。")
    end_line: Optional[int] = Field(None, description="（可选）结束行号。")

class BookmarkCreate(BookmarkBase):
    pass

class BookmarkUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    visibility: Optional[str] = None

class BookmarkInDB(BookmarkBase):
    id: uuid.UUID
    owner_id: uuid.UUID

    class Config:
        from_attributes = True

# --- 路由器 ---

router = APIRouter(
    tags=["Bookmarks"],
    dependencies=[Depends(get_current_user)],
)

@router.post("/", response_model=BookmarkInDB, status_code=201, summary="创建新书签")
def create_bookmark(
    bookmark: BookmarkCreate,
    current_user: User = Depends(get_current_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    """
    创建一个新的书签，可以是顶级书签或嵌套在另一个书签下。
    """
    return service.create_bookmark(bookmark_data=bookmark, owner_id=current_user.id)


@router.get("/", response_model=List[BookmarkInDB], summary="列出知识空间中的书签")
def list_bookmarks(
    knowledge_space_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    """
    列出指定知识空间中所有对当前用户可见的书签。
    (所有公共书签 + 用户自己的私有书签)
    """
    return service.list_bookmarks_in_ks(ks_id=knowledge_space_id, user_id=current_user.id)

@router.patch("/{bookmark_id}", response_model=BookmarkInDB, summary="更新书签")
def update_bookmark(
    bookmark_id: uuid.UUID,
    update_data: BookmarkUpdate,
    current_user: User = Depends(get_current_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    """
    更新一个书签的名称、父节点或可见性。
    """
    # return service.update(bookmark_id=bookmark_id, update_data=update_data, user_id=current_user.id)
    # 模拟响应
    return {"id": bookmark_id, "name": update_data.name or "old_name", **update_data.dict()}


@router.delete("/{bookmark_id}", status_code=204, summary="删除书签")
def delete_bookmark(
    bookmark_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: BookmarkService = Depends(get_bookmark_service),
):
    """
    删除一个书签。其子书签将被提升为根节点。
    """
    # service.delete(bookmark_id=bookmark_id, user_id=current_user.id)
    return None

