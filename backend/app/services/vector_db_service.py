import logging
from typing import List, Dict, Any
from pymilvus import (
    connections,
    utility,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    AnnSearchRequest,
    RRFRanker,
)
from ..core.config import settings

logger = logging.getLogger(__name__)

class VectorDBService:
    """
    A service to encapsulate all interactions with the Milvus vector database.
    """
    _collection_name = "kosmos_chunks"
    _collection = None

    def __init__(self):
        """
        Initializes the service and establishes a connection to Milvus.
        """
        try:
            if "default" not in connections.list_connections():
                connections.connect(
                    alias="default",
                    user=settings.MILVUS_USER,
                    password=settings.MILVUS_PASSWORD,
                    host=settings.MILVUS_HOST,
                    port=str(settings.MILVUS_PORT),
                )
                logger.info("Successfully connected to Milvus.")
            else:
                logger.info("Already connected to Milvus.")
            
            self.create_collection_if_not_exists()
            self._collection = Collection(self._collection_name)
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            raise

    def create_collection_if_not_exists(self):
        """
        Creates the 'kosmos_chunks' collection with the required schema if it doesn't exist.
        This method is idempotent.
        """
        if utility.has_collection(self._collection_name):
            logger.info(f"Collection '{self._collection_name}' already exists.")
            return

        logger.info(f"Collection '{self._collection_name}' not found. Creating...")

        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
            FieldSchema(name="knowledge_space_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(
                name="summary_embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=settings.DEFAULT_AI_CONFIGURATION["embedding"]["dimension"],
            ),
            FieldSchema(
                name="content_embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=settings.DEFAULT_AI_CONFIGURATION["embedding"]["dimension"],
            ),
        ]

        schema = CollectionSchema(
            fields,
            description="Collection for storing Kosmos document chunks with dual embeddings.",
            enable_dynamic_field=False
        )

        collection = Collection(
            name=self._collection_name,
            schema=schema,
            using="default",
            shards_num=2,
            consistency_level="Strong"
        )
        logger.info(f"Collection '{self._collection_name}' created successfully.")

        logger.info("Creating indexes for vector fields...")
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024},
        }
        collection.create_index(field_name="summary_embedding", index_params=index_params)
        collection.create_index(field_name="content_embedding", index_params=index_params)
        logger.info("Indexes for vector fields created successfully.")
        
        logger.info("Creating scalar index for 'knowledge_space_id'...")
        collection.create_index(field_name="knowledge_space_id")
        logger.info("Scalar index created successfully.")

    def create_partition(self, knowledge_space_id: str):
        """
        Creates a partition for the given knowledge space ID if it doesn't exist.
        """
        partition_name = self._sanitize_partition_name(knowledge_space_id)
        if not self._collection.has_partition(partition_name):
            logger.info(f"Creating partition '{partition_name}' for knowledge space {knowledge_space_id}.")
            self._collection.create_partition(partition_name)

    def insert(self, knowledge_space_id: str, data: List[Dict[str, Any]]) -> List[str]:
        """
        Inserts a batch of chunk data into the appropriate partition.
        """
        partition_name = self._sanitize_partition_name(knowledge_space_id)
        self.create_partition(knowledge_space_id)
        
        for item in data:
            item['knowledge_space_id'] = knowledge_space_id

        logger.info(f"Inserting {len(data)} entities into partition '{partition_name}'.")
        mutation_result = self._collection.insert(data, partition_name=partition_name)
        self._collection.flush()
        logger.info(f"Successfully inserted {mutation_result.insert_count} entities.")
        return mutation_result.primary_keys

    def delete_by_document_id(self, knowledge_space_id: str, document_id: str) -> int:
        """
        Deletes all chunks associated with a specific document ID from a partition.
        """
        partition_name = self._sanitize_partition_name(knowledge_space_id)
        if not self._collection.has_partition(partition_name):
            return 0

        self._collection.load(partition_names=[partition_name])

        expr = f"document_id == '{document_id}'"
        delete_result = self._collection.delete(expr, partition_name=partition_name)
        self._collection.flush()
        
        return delete_result.delete_count

    def delete_partition(self, knowledge_space_id: str) -> bool:
        """
        删除指定知识空间的分区及其所有数据。
        这是一个危险操作，通常只在删除知识空间时调用。
        
        Args:
            knowledge_space_id: 知识空间ID
            
        Returns:
            bool: 如果分区存在并成功删除返回True，如果分区不存在返回False
        """
        partition_name = self._sanitize_partition_name(knowledge_space_id)
        
        if not self._collection.has_partition(partition_name):
            logger.info(f"Partition '{partition_name}' does not exist, nothing to delete.")
            return False
        
        try:
            logger.info(f"Deleting partition '{partition_name}' for knowledge space {knowledge_space_id}")
            self._collection.drop_partition(partition_name)
            logger.info(f"Successfully deleted partition '{partition_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete partition '{partition_name}': {e}")
            raise

    def search(self, knowledge_space_id: str, query_vector: List[float], top_k: int, **kwargs) -> List[Dict[str, Any]]:
        """
        Performs a hybrid search on both summary and content embeddings,
        using RRFRanker to fuse the results.
        """
        partition_name = self._sanitize_partition_name(knowledge_space_id)
        self._collection.load(partition_names=[partition_name])

        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        # 1. Create two AnnSearchRequest objects, one for each vector field.
        # We search for more results initially (e.g., top_k * 3) to give the reranker more candidates.
        rerank_candidate_count = top_k * 3
        
        summary_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="summary_embedding",
            param=search_params,
            limit=rerank_candidate_count
        )
        content_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="content_embedding",
            param=search_params,
            limit=rerank_candidate_count
        )

        # 2. Define the reranking strategy. RRFRanker is a balanced choice.
        reranker = RRFRanker()

        # 3. Execute the hybrid search
        results = self._collection.hybrid_search(
            reqs=[summary_req, content_req],
            rerank=reranker,
            limit=top_k,
            partition_names=[partition_name],
            output_fields=["chunk_id"]
        )
        
        # 4. Format and return the results
        # The result is a list containing one list of hits.
        final_hits = results[0]
        # The score from RRFRanker is a similarity score (higher is better)
        return [{"chunk_id": hit.id, "score": hit.score} for hit in final_hits]

    def fetch_by_chunk_ids(self, knowledge_space_id: str, chunk_ids: List[str]) -> List[str]:
        """
        Fetches records from Milvus based on a list of chunk IDs.
        Returns a list of chunk IDs that were found in the database.
        """
        if not chunk_ids:
            return []

        partition_name = self._sanitize_partition_name(knowledge_space_id)
        if not self._collection.has_partition(partition_name):
            return []
            
        self._collection.load(partition_names=[partition_name])

        # Milvus expects a comma-separated list of quoted strings for the 'in' operator
        chunk_ids_str = ", ".join([f'"{cid}"' for cid in chunk_ids])
        expr = f"chunk_id in [{chunk_ids_str}]"
        
        results = self._collection.query(
            expr=expr,
            partition_names=[partition_name],
            output_fields=["chunk_id"]
        )
        
        return [item['chunk_id'] for item in results]

    def _sanitize_partition_name(self, uuid_str: str) -> str:
        """
        Sanitizes a UUID string to be a valid Milvus partition name.
        """
        return "ks_" + uuid_str.replace("-", "_")
