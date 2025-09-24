
import uuid
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from fastapi import HTTPException, status

from .. import models, schemas

class BookmarkService:
    def __init__(self, db: Session):
        self.db = db

    def get_bookmark_by_id(self, bookmark_id: uuid.UUID) -> models.Bookmark:
        """获取单个书签，如果不存在则抛出异常。"""
        bookmark = self.db.query(models.Bookmark).filter(models.Bookmark.id == bookmark_id).first()
        if not bookmark:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bookmark not found")
        return bookmark

    def create_bookmark(self, bookmark_data: schemas.BookmarkCreate, owner_id: uuid.UUID) -> models.Bookmark:
        """创建新的书签，并进行唯一性校验。"""
        # 检查父节点是否存在
        if bookmark_data.parent_id:
            parent_bookmark = self.get_bookmark_by_id(bookmark_data.parent_id)
            if parent_bookmark.knowledge_space_id != bookmark_data.knowledge_space_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent bookmark must be in the same knowledge space.")

        # 检查名称唯一性
        query = self.db.query(models.Bookmark).filter(
            models.Bookmark.knowledge_space_id == bookmark_data.knowledge_space_id,
            models.Bookmark.name == bookmark_data.name
        )
        if bookmark_data.visibility == 'public':
            # 公共书签在整个知识空间中必须唯一
            existing = query.filter(models.Bookmark.visibility == 'public').first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A public bookmark with the name '{bookmark_data.name}' already exists.")
        else: # private
            # 私有书签在用户范围内必须唯一
            existing = query.filter(and_(models.Bookmark.visibility == 'private', models.Bookmark.owner_id == owner_id)).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A private bookmark with the name '{bookmark_data.name}' already exists for you.")

        db_bookmark = models.Bookmark(**bookmark_data.dict(), owner_id=owner_id)
        self.db.add(db_bookmark)
        self.db.commit()
        self.db.refresh(db_bookmark)
        return db_bookmark

    def list_bookmarks_in_ks(self, ks_id: uuid.UUID, user_id: uuid.UUID) -> List[models.Bookmark]:
        """列出对用户可见的所有书签。"""
        bookmarks = self.db.query(models.Bookmark).filter(
            models.Bookmark.knowledge_space_id == ks_id,
            or_(
                models.Bookmark.visibility == 'public',
                models.Bookmark.owner_id == user_id
            )
        ).all()
        return bookmarks

    def delete_bookmark(self, bookmark_id: uuid.UUID, user_id: uuid.UUID):
        """删除一个书签，并将其子节点的 parent_id 设为 null。"""
        bookmark_to_delete = self.get_bookmark_by_id(bookmark_id)
        
        # 权限检查：只有所有者能删除
        if bookmark_to_delete.owner_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this bookmark.")

        # 将子节点的 parent_id 设为 null
        self.db.query(models.Bookmark).filter(models.Bookmark.parent_id == bookmark_id).update({"parent_id": None})
        
        self.db.delete(bookmark_to_delete)
        self.db.commit()

    def resolve_bookmark_by_name(self, name: str, ks_id: uuid.UUID, user_id: uuid.UUID) -> models.Bookmark:
        """根据名称解析对用户可见的书签。"""
        # 优先查找用户的私有书签，然后查找公共书签
        bookmark = self.db.query(models.Bookmark).filter(
            models.Bookmark.knowledge_space_id == ks_id,
            models.Bookmark.name == name,
            or_(
                models.Bookmark.visibility == 'public',
                and_(
                    models.Bookmark.visibility == 'private',
                    models.Bookmark.owner_id == user_id
                )
            )
        ).order_by(models.Bookmark.visibility.desc()).first() # 'private' > 'public'
        
        if not bookmark:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bookmark '@{name}' not found or you don't have permission to view it.")
        
        return bookmark
