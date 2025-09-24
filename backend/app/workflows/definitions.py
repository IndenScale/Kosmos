"""
This file contains the static definitions for all workflows in the system.

It uses a declarative, object-oriented approach to build a graph of Nodes,
which are then assembled into named Workflows. This provides a single,
clear source of truth for how background processes are structured and chained.
"""
from enum import Enum

class NodeType(str, Enum):
    """
    Enumeration of all possible Node types. Each type corresponds to a
    distinct, reusable task that can be performed by an actor.
    """
    DECOMPOSE_CONTAINER = "decompose_container"
    CONVERT_TO_PDF = "convert_to_pdf"
    EXTRACT_CONTENT = "extract_content"
    CHUNK_DOCUMENT = "chunk_document"
    TAG_CHUNKS = "tag_chunks"
    INDEX_CHUNKS = "index_chunks"
    ANALYZE_ASSET = "analyze_asset"

class Node:
    """
    Represents a node in a workflow graph. This is the static, definitional
    blueprint for a single step in a process.

    Attributes:
        node_type: The type of this node, from the NodeType enum.
        actor_name: The string name of the Dramatiq actor that executes this task.
        on_success: A direct object reference to the next Node in the sequence,
                    forming the edge of the graph. If None, this is a terminal node.
    """
    def __init__(self, node_type: NodeType, actor_name: str, on_success: 'Node' = None):
        self.node_type = node_type
        self.actor_name = actor_name
        self.on_success = on_success

class Workflow:
    """
    Represents the static definition of an entire workflow, identified by a
    unique name and an entry point Node.
    """
    def __init__(self, name: str, entry_node: Node):
        self.name = name
        self.entry_node = entry_node

# --- Workflow Graph Construction ---
# The graph is defined by creating instances of Nodes and linking them together.
# We define the chains from end to start to make the linking logic cleaner.

# 1. Define nodes for the "Knowledge Processing" branch
node_index = Node(NodeType.INDEX_CHUNKS, "index_chunks_actor")
node_tag = Node(NodeType.TAG_CHUNKS, "tag_chunks_actor", on_success=node_index)
node_chunk = Node(NodeType.CHUNK_DOCUMENT, "chunk_document_actor", on_success=node_tag)

# 2. Define nodes for the "Document Processing" branch, which chains into the above
node_extract_content = Node(NodeType.EXTRACT_CONTENT, "extract_content_actor", on_success=node_chunk)
node_convert = Node(NodeType.CONVERT_TO_PDF, "convert_to_pdf_actor", on_success=node_extract_content)
node_decompose = Node(NodeType.DECOMPOSE_CONTAINER, "decompose_container_actor", on_success=node_convert)

# 3. Define the main "process_document" workflow
doc_processing_workflow = Workflow(
    name="process_document",
    entry_node=node_decompose
)

# 4. Define a separate, simple workflow for asset analysis
asset_analysis_node = Node(NodeType.ANALYZE_ASSET, "analyze_asset_actor")
asset_workflow = Workflow(
    name="analyze_asset",
    entry_node=asset_analysis_node
)

# 5. A central registry to easily find and start any defined workflow by name.
#    This is the primary interface for the runtime service to interact with the definitions.
WORKFLOW_REGISTRY = {
    "process_document": doc_processing_workflow,
    "analyze_asset": asset_workflow,
}
