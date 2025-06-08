from pymilvus import Collection, connections, utility, FieldSchema, CollectionSchema, DataType
from typing import List, Dict, Any, Optional
import os
import re
from dotenv import load_dotenv

load_dotenv()

class MilvusRepository:
    """Milvus向量数据库访问层"""

    def __init__(self):
        self.host = os.getenv("MILVUS_HOST", "localhost")
        self.port = os.getenv("MILVUS_PORT", "19530")
        self.token = os.getenv("MILVUS_TOKEN", "root:Milvus")
        self.embedding_dim = int(os.getenv("OPENAI_EMBEDDING_DIM", "1024"))  # 从环境变量读取
        self._connect()

    def _connect(self):
        """连接到Milvus"""
        connections.connect(
            alias="default",
            host=self.host,
            port=self.port,
            token=self.token
        )

    def _normalize_collection_name(self, kb_id: str) -> str:
        """规范化collection名称，移除连字符和特殊字符"""
        # 移除连字符，替换为下划线
        normalized = re.sub(r'[^a-zA-Z0-9_]', '_', kb_id)
        return f"kb_{normalized}"

    def create_collection(self, kb_id: str) -> str:
        """为知识库创建Milvus Collection"""
        collection_name = self._normalize_collection_name(kb_id)

        if utility.has_collection(collection_name):
            return collection_name

        # 定义Collection schema
        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=64, is_primary=True),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="tags", dtype=DataType.ARRAY, element_type=DataType.VARCHAR, max_capacity=100, max_length=50),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim)  # 使用环境变量
        ]

        schema = CollectionSchema(fields, description=f"Knowledge base {kb_id} chunks")
        collection = Collection(collection_name, schema)

        # 创建索引
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128}
        }
        collection.create_index("embedding", index_params)

        return collection_name

    def _collection_exists(self, kb_id: str) -> bool:
        """检查知识库对应的Collection是否存在"""
        collection_name = self._normalize_collection_name(kb_id)
        return utility.has_collection(collection_name)

    def get_collection(self, kb_id: str) -> Collection:
        """获取知识库对应的Collection"""
        collection_name = self._normalize_collection_name(kb_id)
        if not self._collection_exists(kb_id):
            raise Exception(f"Collection {collection_name} 不存在")
        return Collection(collection_name)

    def insert_chunks(self, kb_id: str, chunks_data: List[Dict[str, Any]]) -> bool:
        """插入chunks到Milvus"""
        collection = self.get_collection(kb_id)

        # 准备数据
        chunk_ids = [item["chunk_id"] for item in chunks_data]
        document_ids = [item["document_id"] for item in chunks_data]
        tags = [item["tags"] for item in chunks_data]
        embeddings = [item["embedding"] for item in chunks_data]

        # 插入数据
        entities = [chunk_ids, document_ids, tags, embeddings]
        collection.insert(entities)
        collection.flush()

        return True

    def retrieve_with_filter(
        self,
        kb_id: str,
        query_vector: List[float],
        must_tags: List[str] = None,
        must_not_tags: List[str] = None,
        top_k: int = 100
    ) -> List[Dict[str, Any]]:
        """执行向量召回和元数据过滤"""
        collection = self.get_collection(kb_id)
        collection.load()  # 确保collection已加载

        # 构建过滤表达式
        filter_expr = self._build_filter_expression(must_tags, must_not_tags)

        # 执行搜索
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 10}
        }

        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr if filter_expr else None,
            output_fields=["chunk_id", "document_id", "tags"]
        )

        # 转换结果格式
        formatted_results = []
        for hit in results[0]:
            formatted_results.append({
                "chunk_id": hit.entity.get("chunk_id"),
                "document_id": hit.entity.get("document_id"),
                "tags": hit.entity.get("tags"),
                "score": hit.score
            })

        return formatted_results

    def _build_filter_expression(self, must_tags: List[str] = None, must_not_tags: List[str] = None) -> str:
        """构建Milvus过滤表达式"""
        expressions = []

        if must_tags:
            # 所有must_tags都必须存在
            for tag in must_tags:
                expressions.append(f'array_contains(tags, "{tag}")')

        if must_not_tags:
            # 所有must_not_tags都不能存在
            for tag in must_not_tags:
                expressions.append(f'not array_contains(tags, "{tag}")')

        return " and ".join(expressions) if expressions else ""

    def delete_collection(self, kb_id: str) -> bool:
        """删除知识库对应的Collection"""
        collection_name = self._normalize_collection_name(kb_id)
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)
            return True
        return False