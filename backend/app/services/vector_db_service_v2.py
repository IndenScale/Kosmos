import logging
from typing import List, Dict, Any, Optional
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

class VectorDBServiceV2:
    """
    Enhanced VectorDB service that supports independent collections per knowledge space.
    This allows different knowledge spaces to have different embedding dimensions.
    """
    
    def __init__(self):
        """
        Initializes the service and establishes a connection to Milvus.
        """
        self._collections = {}  # Cache for created collections
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
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}", exc_info=True)
            raise

    def _get_collection_name(self, knowledge_space_id: str, embedding_dim: int) -> str:
        """
        Generate collection name based on knowledge space ID and embedding dimension.
        """
        sanitized_ks_id = knowledge_space_id.replace("-", "_")
        return f"kosmos_ks_{sanitized_ks_id}_dim_{embedding_dim}"

    def _create_collection_with_dimension(self, collection_name: str, embedding_dim: int):
        """
        Creates a new collection with the specified embedding dimension.
        """
        logger.info(f"Creating collection '{collection_name}' with dimension {embedding_dim}...")

        fields = [
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, is_primary=True, max_length=36),
            FieldSchema(name="knowledge_space_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
            FieldSchema(
                name="summary_embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=embedding_dim,
            ),
            FieldSchema(
                name="content_embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=embedding_dim,
            ),
        ]

        schema = CollectionSchema(
            fields,
            description=f"Collection for knowledge space with {embedding_dim}D embeddings.",
            enable_dynamic_field=False
        )

        collection = Collection(
            name=collection_name,
            schema=schema,
            using="default",
            shards_num=2,
            consistency_level="Strong"
        )
        logger.info(f"Collection '{collection_name}' created successfully.")

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

    def _get_or_create_collection(self, knowledge_space_id: str, embedding_dim: int) -> Collection:
        """
        Get existing collection or create a new one for the given knowledge space and dimension.
        """
        collection_name = self._get_collection_name(knowledge_space_id, embedding_dim)
        
        if collection_name not in self._collections:
            if not utility.has_collection(collection_name):
                self._create_collection_with_dimension(collection_name, embedding_dim)
            self._collections[collection_name] = Collection(collection_name)
            logger.info(f"Using collection '{collection_name}' for knowledge space {knowledge_space_id}")
        
        return self._collections[collection_name]

    def insert(self, knowledge_space_id: str, data: List[Dict[str, Any]], embedding_dim: int) -> List[str]:
        """
        Inserts a batch of chunk data into the appropriate collection.
        """
        collection = self._get_or_create_collection(knowledge_space_id, embedding_dim)
        
        for item in data:
            item['knowledge_space_id'] = knowledge_space_id

        logger.info(f"Inserting {len(data)} entities into collection for KS {knowledge_space_id} (dim={embedding_dim}).")
        mutation_result = collection.insert(data)
        collection.flush()
        logger.info(f"Successfully inserted {mutation_result.insert_count} entities.")
        return mutation_result.primary_keys

    def delete_by_document_id(self, knowledge_space_id: str, document_id: str, embedding_dim: int) -> int:
        """
        Deletes all chunks associated with a specific document ID from the collection.
        """
        collection_name = self._get_collection_name(knowledge_space_id, embedding_dim)
        if not utility.has_collection(collection_name):
            return 0

        collection = Collection(collection_name)
        collection.load()

        expr = f"document_id == '{document_id}'"
        delete_result = collection.delete(expr)
        collection.flush()
        
        return delete_result.delete_count

    def delete_collection(self, knowledge_space_id: str, embedding_dim: int) -> bool:
        """
        删除指定知识空间的整个collection。
        这是一个危险操作，通常只在删除知识空间时调用。
        
        Args:
            knowledge_space_id: 知识空间ID
            embedding_dim: 嵌入维度
            
        Returns:
            bool: 如果collection存在并成功删除返回True，如果collection不存在返回False
        """
        collection_name = self._get_collection_name(knowledge_space_id, embedding_dim)
        
        if not utility.has_collection(collection_name):
            logger.info(f"Collection '{collection_name}' does not exist, nothing to delete.")
            return False
        
        try:
            logger.info(f"Deleting collection '{collection_name}' for knowledge space {knowledge_space_id}")
            utility.drop_collection(collection_name)
            # Remove from cache
            if collection_name in self._collections:
                del self._collections[collection_name]
            logger.info(f"Successfully deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            raise

    def search(self, knowledge_space_id: str, query_vector: List[float], top_k: int, embedding_dim: int, **kwargs) -> List[Dict[str, Any]]:
        """
        Performs a hybrid search on both summary and content embeddings,
        using RRFRanker to fuse the results.
        """
        collection = self._get_or_create_collection(knowledge_space_id, embedding_dim)
        collection.load()

        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        # Create two AnnSearchRequest objects, one for each vector field.
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

        # Define the reranking strategy
        reranker = RRFRanker()

        # Execute the hybrid search
        results = collection.hybrid_search(
            reqs=[summary_req, content_req],
            rerank=reranker,
            limit=top_k,
            output_fields=["chunk_id"]
        )
        
        # Format and return the results
        final_hits = results[0]
        return [{"chunk_id": hit.id, "score": hit.score} for hit in final_hits]

    def fetch_by_chunk_ids(self, knowledge_space_id: str, chunk_ids: List[str], embedding_dim: int) -> List[str]:
        """
        Fetches records from Milvus based on a list of chunk IDs.
        Returns a list of chunk IDs that were found in the database.
        """
        if not chunk_ids:
            return []

        collection_name = self._get_collection_name(knowledge_space_id, embedding_dim)
        if not utility.has_collection(collection_name):
            return []
            
        collection = Collection(collection_name)
        collection.load()

        # Milvus expects a comma-separated list of quoted strings for the 'in' operator
        chunk_ids_str = ", ".join([f'"{cid}"' for cid in chunk_ids])
        expr = f"chunk_id in [{chunk_ids_str}]"
        
        results = collection.query(
            expr=expr,
            output_fields=["chunk_id"]
        )
        
        return [item['chunk_id'] for item in results]

    def list_collections_for_knowledge_space(self, knowledge_space_id: str) -> List[Dict[str, Any]]:
        """
        List all collections for a given knowledge space.
        Returns list of dicts with collection_name and embedding_dim.
        """
        sanitized_ks_id = knowledge_space_id.replace("-", "_")
        prefix = f"kosmos_ks_{sanitized_ks_id}_dim_"
        
        all_collections = utility.list_collections()
        ks_collections = []
        
        for collection_name in all_collections:
            if collection_name.startswith(prefix):
                # Extract dimension from collection name
                dim_str = collection_name[len(prefix):]
                try:
                    embedding_dim = int(dim_str)
                    ks_collections.append({
                        "collection_name": collection_name,
                        "embedding_dim": embedding_dim
                    })
                except ValueError:
                    logger.warning(f"Could not parse dimension from collection name: {collection_name}")
        
        return ks_collections

    def get_collection_stats(self, knowledge_space_id: str, embedding_dim: int) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific collection.
        """
        collection_name = self._get_collection_name(knowledge_space_id, embedding_dim)
        if not utility.has_collection(collection_name):
            return None
            
        collection = Collection(collection_name)
        collection.load()
        
        return {
            "collection_name": collection_name,
            "num_entities": collection.num_entities,
            "embedding_dim": embedding_dim,
            "knowledge_space_id": knowledge_space_id
        }