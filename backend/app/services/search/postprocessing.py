"""
Postprocessing steps for search results.
This includes deduplication and re-ranking.
"""
from typing import List
from .schemas import SearchResultItem

class Postprocessor:
    def deduplicate(self, results: List[SearchResultItem]) -> List[SearchResultItem]:
        """
        Removes duplicate chunks from the result list based on their ID.
        """
        seen_ids = set()
        unique_results = []
        for item in results:
            if item.chunk_id not in seen_ids:
                unique_results.append(item)
                seen_ids.add(item.chunk_id)
        return unique_results
