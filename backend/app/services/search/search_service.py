"""
The main Search Service, acting as an orchestrator for the entire search process.
"""
import uuid
from sqlalchemy.orm import Session, joinedload
from .schemas import SearchRequest, SearchResponse, SearchResultItem, ScoreBreakdown, SearchFunnel
from .recallers import Recallers
from .postprocessing import Postprocessor
from ..ai_provider_service import AIProviderService
from ...models import Chunk, KnowledgeSpace

class SearchService:
    def __init__(self, db: Session):
        self.db = db
        self.recallers = Recallers(db)
        self.postprocessor = Postprocessor()
        self.ai_provider = AIProviderService(db)

    def search(self, request: SearchRequest, user_id: uuid.UUID) -> SearchResponse:
        """
        Orchestrates the search flow:
        1. Get query embedding.
        2. Perform multi-channel recall.
        3. Combine and rank results.
        4. Fetch chunk details and apply filters/boosters.
        5. Postprocess results (deduplicate, aggregate).
        6. Format and return the response.
        """
        print(f"--- [SEARCH PIPELINE] Query: '{request.query}' in KS: {request.knowledge_space_id} ---")

        # 1. Get query embedding
        query_vector = None
        try:
            embedding_client = self.ai_provider.get_client_for_embedding(user_id, request.knowledge_space_id)
            ks = self.db.query(KnowledgeSpace).filter(KnowledgeSpace.id == request.knowledge_space_id).first()
            if not ks: raise ValueError("Knowledge space not found")
            embedding_dim = ks.ai_configuration.get("embedding", {}).get("dimension")
            if not embedding_dim: raise ValueError("Embedding dimension not configured.")

            embedding_response = embedding_client.embeddings.create(
                model=getattr(embedding_client, 'model_name'),
                input=[request.query]
            )
            query_vector = embedding_response.data[0].embedding
        except Exception as e:
            print(f"DEBUG WARNING: Could not get query embedding. Error: {e}")

        # 2. Multi-channel recall
        recall_multiplier = 3
        # Widen recall if performing slow in-memory content filtering
        if request.filters and (request.filters.keywords_include_all or request.filters.keywords_exclude_any or request.filters.keywords):
            recall_multiplier = 10
            print(f"--- [SEARCH PIPELINE] In-memory content filter detected. Widening recall to {request.top_k * recall_multiplier} ---")

        vector_results = []
        if query_vector:
            vector_results = self.recallers.vector_recall(request.knowledge_space_id, query_vector, request.top_k * recall_multiplier, embedding_dim)

        keyword_results = self.recallers.keyword_recall(
            query=request.query,
            knowledge_space_id=request.knowledge_space_id,
            document_id=request.filters.document_id if request.filters else None,
            top_k=request.top_k * recall_multiplier
        )
        
        recalled_items = {}
        for item in vector_results:
            recalled_items[item['chunk_id']] = {'vector_score': item['score'], 'keyword_score': 0.0}
        for item in keyword_results:
            chunk_id = item['chunk_id']
            if chunk_id in recalled_items:
                recalled_items[chunk_id]['keyword_score'] = item['score']
            else:
                recalled_items[chunk_id] = {'vector_score': 0.0, 'keyword_score': item['score']}

        search_funnel = SearchFunnel(
            vector_recalled=len(vector_results),
            keyword_recalled=len(keyword_results),
            combined_recalled=len(recalled_items),
            filtered=0,
            final_aggregated=0
        )

        if not recalled_items:
            return SearchResponse(results=[], suggested_tags=[], search_funnel=search_funnel if request.detailed else None)

        # 3. Fetch chunk details & Apply Filters
        chunk_ids = [uuid.UUID(cid) for cid in recalled_items.keys()]
        
        # Base query with eager loading for related data that will be *displayed*
        query = self.db.query(Chunk).options(
            joinedload(Chunk.document),
            joinedload(Chunk.ontology_tags)
        )
        
        # --- APPLY HARD FILTERS ---
        # We need to join with Document to filter on its attributes like filename
        from ...models import Document
        from sqlalchemy import or_
        query = query.join(Document, Chunk.document_id == Document.id)

        if request.filters:
            # Document ID filters
            if request.filters.document_ids_include:
                query = query.filter(Chunk.document_id.in_(request.filters.document_ids_include))
            
            if request.filters.document_ids_exclude:
                query = query.filter(~Chunk.document_id.in_(request.filters.document_ids_exclude))

            # Backward compatibility for the old single document_id filter
            if request.filters.document_id and not request.filters.document_ids_include:
                query = query.filter(Chunk.document_id == request.filters.document_id)

            # Filename filters
            if request.filters.filename_contains:
                query = query.filter(Document.original_filename.ilike(f"%{request.filters.filename_contains}%"))
            
            if request.filters.filename_does_not_contain:
                query = query.filter(~Document.original_filename.ilike(f"%{request.filters.filename_does_not_contain}%"))

            # Extension filters
            if request.filters.extensions_include:
                conditions = [Document.original_filename.ilike(f"%.{ext}") for ext in request.filters.extensions_include]
                query = query.filter(or_(*conditions))

            if request.filters.extensions_exclude:
                conditions = [Document.original_filename.ilike(f"%.{ext}") for ext in request.filters.extensions_exclude]
                query = query.filter(~or_(*conditions))

            # Tags filter (database-level for efficiency)
            if request.filters.tags:
                from ...models import OntologyNode
                # This requires a separate join for the tags relationship
                query = query.join(Chunk.ontology_tags)
                for tag_name in request.filters.tags:
                    query = query.filter(OntologyNode.name == tag_name)

        db_chunks = query.all()
        
        # Keywords filter (post-DB query, as it's a slow text scan)
        if request.filters and (request.filters.keywords_include_all or request.filters.keywords_exclude_any or request.filters.keywords):
            filtered_chunks = []
            
            # Backward compatibility for old `keywords` field
            keywords_to_include = request.filters.keywords_include_all or request.filters.keywords
            keywords_to_exclude = request.filters.keywords_exclude_any

            for chunk in db_chunks:
                content_lower = (chunk.raw_content or "").lower()
                
                # Positive filtering (AND logic)
                include_match = True
                if keywords_to_include:
                    if not all(kw.lower() in content_lower for kw in keywords_to_include):
                        include_match = False
                
                # Negative filtering (NOT (A OR B) logic)
                exclude_match = False
                if keywords_to_exclude:
                    if any(kw.lower() in content_lower for kw in keywords_to_exclude):
                        exclude_match = True
                
                if include_match and not exclude_match:
                    filtered_chunks.append(chunk)

            db_chunks = filtered_chunks

        search_funnel.filtered = len(db_chunks)

        # 4. Format for post-processing & Apply Boosters
        VECTOR_WEIGHT = 0.6
        KEYWORD_WEIGHT = 0.4
        search_result_items = []
        for chunk in db_chunks:
            chunk_id_str = str(chunk.id)
            scores = recalled_items.get(chunk_id_str, {'vector_score': 0.0, 'keyword_score': 0.0})
            
            base_score = (scores['vector_score'] * VECTOR_WEIGHT) + (scores['keyword_score'] * KEYWORD_WEIGHT)
            
            # --- APPLY BOOSTERS ---
            booster_multiplier = 1.0
            if request.boosters:
                chunk_tags_set = {tag.name.lower() for tag in chunk.ontology_tags} if chunk.ontology_tags else set()
                content_lower = (chunk.raw_content or "").lower()
                
                for booster_term in request.boosters:
                    term_lower = booster_term.lower()
                    # Boost if the term is in content OR in tags
                    if term_lower in content_lower or term_lower in chunk_tags_set:
                        booster_multiplier *= 1.2 # Boost score by 20%

            final_score = base_score * booster_multiplier
            
            full_content = chunk.paraphrase or chunk.raw_content or ""
            content_preview = full_content[:request.max_content_length]
            unshown_char_count = len(full_content) - len(content_preview)

            scores_breakdown = None
            tags = [tag.name for tag in chunk.ontology_tags] if chunk.ontology_tags else None

            if request.detailed:
                scores_breakdown = ScoreBreakdown(
                    vector_score=scores['vector_score'],
                    keyword_score=scores['keyword_score'],
                    booster_multiplier=booster_multiplier,
                    final_score=final_score
                )

            search_result_items.append(SearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_filename=chunk.document.original_filename if chunk.document else "Unknown",
                content=content_preview,
                unshown_char_count=unshown_char_count,
                score=final_score,
                scores_breakdown=scores_breakdown,
                tags=tags,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
            ))
            
        # 5. Postprocess & Sort
        search_result_items.sort(key=lambda x: x.score, reverse=True)
        unique_items = self.postprocessor.deduplicate(search_result_items)
        search_funnel.final_aggregated = len(unique_items)
        
        # 6. Implement advanced tag suggestion logic based on discriminative power
        suggested_tags = []
        if unique_items: # Only run if there are results to analyze
            try:
                from collections import Counter

                # Step 1: Create a set of terms the user already used, for exclusion.
                user_used_terms = set()
                if request.filters and request.filters.tags:
                    user_used_terms.update([t.lower() for t in request.filters.tags])
                if request.boosters:
                    user_used_terms.update([b.lower() for b in request.boosters])

                # Step 2: Collect all tags from the result set.
                all_tags_in_results = [
                    tag
                    for item in unique_items
                    if item.tags
                    for tag in item.tags
                ]

                if all_tags_in_results:
                    # Step 3: Count frequencies and calculate the ideal target.
                    tag_counts = Counter(all_tags_in_results)
                    total_chunks = len(unique_items)
                    target_count = total_chunks / 2.0

                    candidate_tags = []
                    for tag, count in tag_counts.items():
                        # Condition A: Exclude already used terms.
                        if tag.lower() in user_used_terms:
                            continue
                        
                        # Condition B: Score based on proximity to 50% distribution.
                        score = abs(count - target_count)
                        candidate_tags.append((score, tag))
                    
                    # Step 4: Sort by the score (lower is better) and select the top 5.
                    candidate_tags.sort(key=lambda x: x[0])
                    suggested_tags = [tag for score, tag in candidate_tags[:5]]

            except ImportError:
                pass # Fallback to empty list if collections is not available
        
        return SearchResponse(
            results=unique_items[:request.top_k], 
            suggested_tags=suggested_tags,
            search_funnel=search_funnel if request.detailed else None
        )

