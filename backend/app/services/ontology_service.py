import uuid
import json
import hashlib
from typing import List, Dict, Any
from sqlalchemy.orm import Session, joinedload

from .. import models

import logging

# Add a logger for this service
logger = logging.getLogger(__name__)

def _calculate_node_hash(node_data: Dict[str, Any]) -> str:
    """
    Calculates a deterministic SHA256 hash for the node's content,
    ensuring that identical nodes can be identified and deduplicated.
    """
    # Use a canonical JSON representation for consistent hashing.
    # We only hash the data content, not identifiers.
    canonical_string = json.dumps(
        {
            "name": node_data.get("name"),
            "constraints": node_data.get("constraints"),
            "node_metadata": node_data.get("node_metadata"),
        },
        sort_keys=True,
        separators=( ",", ":")
    )
    return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

class OntologyService:
    def __init__(self, db: Session):
        self.db = db

    def _create_ontology_for_knowledge_space(
        self,
        knowledge_space: models.KnowledgeSpace,
        creator: models.User,
        initial_tree: Dict[str, Any] | None = None
    ) -> models.Ontology:
        """
        (Internal use) Initializes the ontology repository and its first version.
        This robust, non-recursive implementation ensures atomic creation of the
        entire initial ontology tree.
        """
        # 1. Create the Ontology repository, the container for all versions.
        ontology = models.Ontology(knowledge_space=knowledge_space)
        self.db.add(ontology)
        self.db.flush()

        # 2. Create the mandatory internal root node.
        root_node_data = {"name": "__root__", "constraints": None, "node_metadata": {"description": "Internal root of the ontology."}}
        root_db_node = models.OntologyNode(
            knowledge_space_id=knowledge_space.knowledge_space_id,
            stable_id=uuid.uuid4(),
            name=root_node_data["name"],
            constraints=root_node_data["constraints"],
            node_metadata=root_node_data["node_metadata"],
            content_hash=_calculate_node_hash(root_node_data)
        )
        self.db.add(root_db_node)

        # 3. Iteratively build the initial tree using a queue (BFS approach).
        nodes_to_process = []
        if initial_tree:
            for name, data in initial_tree.items():
                nodes_to_process.append({'parent_db_node': root_db_node, 'name': name, 'data': data})

        # This map holds the DB objects and their children's JSON representations
        # Key: db_node object, Value: {'children_json': [...]} 
        node_map = {root_db_node: {'children_json': []}}
        links_to_create = [{'node': root_db_node, 'parent_node': None}]

        while nodes_to_process:
            item = nodes_to_process.pop(0)
            parent_db_node, name, data = item['parent_db_node'], item['name'], item['data']

            node_data = {'name': name, 'constraints': data if isinstance(data, list) else None}
            new_db_node = models.OntologyNode(
                knowledge_space_id=knowledge_space.knowledge_space_id,
                stable_id=uuid.uuid4(),
                name=node_data["name"],
                constraints=node_data.get("constraints"),
                content_hash=_calculate_node_hash(node_data)
            )
            self.db.add(new_db_node)
            
            links_to_create.append({'node': new_db_node, 'parent_node': parent_db_node})
            node_map[new_db_node] = {'children_json': []}

            if isinstance(data, dict):
                for child_name, child_data in data.items():
                    nodes_to_process.append({'parent_db_node': new_db_node, 'name': child_name, 'data': child_data})

        # 4. Flush the session once to assign IDs to all newly created nodes.
        self.db.flush()

        # 5. Build the serialized JSON tree from the bottom up using the flushed objects.
        for link_info in reversed(links_to_create):
            node, parent_node = link_info['node'], link_info['parent_node']
            
            node_json = {
                "stable_id": str(node.stable_id), "name": node.name, "constraints": node.constraints,
                "node_metadata": node.node_metadata, "children": node_map[node]['children_json']
            }
            
            if parent_node:
                node_map[parent_node]['children_json'].insert(0, node_json)

        serialized_tree = {
            "stable_id": str(root_db_node.stable_id), "name": root_db_node.name, "constraints": root_db_node.constraints,
            "node_metadata": root_db_node.node_metadata, "children": node_map[root_db_node]['children_json']
        }

        # 6. Create the first version record with the complete serialized tree.
        first_version = models.OntologyVersion(
            ontology_id=ontology.id, parent_version_id=None, version_number=1,
            commit_message="Initial ontology structure.", created_by_user_id=creator.id,
            serialized_nodes=serialized_tree
        )
        self.db.add(first_version)
        self.db.flush()

        # 7. Link all nodes to this first version in the link table.
        for link_info in links_to_create:
            self.db.add(models.OntologyVersionNodeLink(
                version_id=first_version.id,
                node_id=link_info['node'].id,
                parent_node_id=link_info['parent_node'].id if link_info['parent_node'] else None
            ))

        # 8. Set the 'HEAD' pointer to this first version.
        ontology.active_version_id = first_version.id
        return ontology

    def _get_raw_active_ontology_tree(self, knowledge_space_id: uuid.UUID) -> Dict[str, Any]:
        """
        (Internal) Retrieves the raw, complete tree structure of the active
        ontology version, including the internal `__root__` node. This is for
        internal service use only.
        """
        ontology = self.db.query(models.Ontology).options(
            joinedload(models.Ontology.active_version)
        ).filter(
            models.Ontology.knowledge_space_id == knowledge_space_id
        ).first()

        if not ontology:
            raise Exception(f"Ontology for knowledge space {knowledge_space_id} not found.")

        if not ontology.active_version or not ontology.active_version.serialized_nodes:
            return {}
        
        return ontology.active_version.serialized_nodes

    def get_active_ontology_tree(
        self,
        knowledge_space_id: uuid.UUID
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        """
        Retrieves the user-visible tree structure of the active ontology version.

        This method is optimized for performance by reading from the denormalized
        `serialized_nodes` of the active OntologyVersion. It also handles stripping
        the internal `__root__` node to return only the user-defined top-level nodes.
        """
        full_tree = self._get_raw_active_ontology_tree(knowledge_space_id)

        if not full_tree:
            return {}

        # If the root is the internal `__root__`, return its children.
        # This correctly returns a list of top-level user concepts.
        if full_tree.get("name") == "__root__":
            return full_tree.get("children", [])
        
        # For legacy ontologies, return the old single-root structure.
        return full_tree

    def add_node(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        parent_stable_id: uuid.UUID,
        node_data: Dict[str, Any],
        commit_message: str,
    ) -> models.OntologyVersion:
        """
        Adds a new node to the ontology under a specified parent.
        This creates a new version of the ontology.
        """
        # This is a simplified change set for the internal commit engine.
        change = {
            "type": "add",
            "parent_stable_id": parent_stable_id,
            "node_data": node_data,
        }

        return self._commit_new_version_from_changes(
            knowledge_space_id=knowledge_space_id,
            author=author,
            commit_message=commit_message,
            changes=[change]
        )

    def update_node(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        stable_id: uuid.UUID,
        new_node_data: Dict[str, Any],
        commit_message: str,
    ) -> models.OntologyVersion:
        """
        Updates the content of an existing node (e.g., its name or constraints).
        This creates a new version of the ontology.
        """
        change = {
            "type": "update",
            "stable_id": stable_id,
            "new_node_data": new_node_data,
        }

        return self._commit_new_version_from_changes(
            knowledge_space_id=knowledge_space_id,
            author=author,
            commit_message=commit_message,
            changes=[change]
        )

    def move_node(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        stable_id: uuid.UUID,
        new_parent_stable_id: uuid.UUID,
        commit_message: str,
    ) -> models.OntologyVersion:
        """
        Moves a node to a new parent within the ontology.
        This creates a new version of the ontology.
        """
        change = {
            "type": "move",
            "stable_id": stable_id,
            "new_parent_stable_id": new_parent_stable_id,
        }

        return self._commit_new_version_from_changes(
            knowledge_space_id=knowledge_space_id,
            author=author,
            commit_message=commit_message,
            changes=[change]
        )

    def delete_node(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        stable_id: uuid.UUID,
        commit_message: str,
    ) -> models.OntologyVersion:
        """
        Deletes a node and all its descendants from the ontology.
        This creates a new version of the ontology.
        """
        change = {
            "type": "delete",
            "stable_id": stable_id,
        }

        return self._commit_new_version_from_changes(
            knowledge_space_id=knowledge_space_id,
            author=author,
            commit_message=commit_message,
            changes=[change]
        )

    def _find_descendant_node_ids(self, version_id: uuid.UUID, parent_node_id: uuid.UUID) -> set:
        """
        (Internal) Recursively finds all descendant node IDs of a given node
        within a specific version's tree structure.
        """
        descendants = set()
        children_q = self.db.query(models.OntologyVersionNodeLink.node_id).filter(
            models.OntologyVersionNodeLink.version_id == version_id,
            models.OntologyVersionNodeLink.parent_node_id == parent_node_id
        ).all()

        children_ids = {row.node_id for row in children_q}
        descendants.update(children_ids)

        for child_id in children_ids:
            descendants.update(self._find_descendant_node_ids(version_id, child_id))

        return descendants

    def _rebuild_serialized_tree(self, version_id: uuid.UUID) -> Dict[str, Any]:
        """
        (Internal) Reconstructs the full, hierarchical JSON object for a given version
        by querying the link table. This implementation is robust and handles complex trees.
        """
        # 1. Fetch all nodes and their parent relationships for this specific version in one go.
        links = self.db.query(
            models.OntologyNode,
            models.OntologyVersionNodeLink.parent_node_id
        ).join(
            models.OntologyVersionNodeLink,
            models.OntologyNode.id == models.OntologyVersionNodeLink.node_id
        ).filter(
            models.OntologyVersionNodeLink.version_id == version_id
        ).all()

        if not links:
            return {}

        # 2. Create a lookup map for all nodes and initialize their children list.
        nodes_map = {}
        for node, _ in links:
            nodes_map[node.id] = {
                "stable_id": str(node.stable_id), "name": node.name, "constraints": node.constraints,
                "node_metadata": node.node_metadata,
                "children": []
            }

        # 3. Build the tree structure by linking children to their parents.
        root_node_json = None
        for node, parent_node_id in links:
            node_json = nodes_map[node.id]
            
            if parent_node_id is None:
                # This should be the __root__ node.
                root_node_json = node_json
            else:
                # It's a child node, find its parent in the map and append.
                if parent_node_id in nodes_map:
                    nodes_map[parent_node_id]["children"].append(node_json)
                else:
                    # This case should ideally not happen in a consistent database.
                    logger.warning(f"Orphan node detected: Node ID {node.id} has parent ID {parent_node_id} which is not in the version.")

        # 4. Ensure children are sorted by name for deterministic output (optional but good practice).
        for node_json in nodes_map.values():
            node_json["children"].sort(key=lambda x: x["name"])

        return root_node_json or {}

    def _commit_new_version_from_changes(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        commit_message: str,
        changes: List[Dict[str, Any]]
    ) -> models.OntologyVersion:
        """
        (Internal) The core engine for creating new ontology versions.
        It performs a copy-on-write operation based on a list of changes.
        """
        logger.info("--- OntologyService: Starting new version commit engine ---")
        
        # 1. Get the parent version (current active version)
        ontology = self.db.query(models.Ontology).filter(
            models.Ontology.knowledge_space_id == knowledge_space_id
        ).first()
        if not ontology or not ontology.active_version_id:
            raise Exception("Cannot commit to an ontology with no active version.")

        parent_version = self.db.query(models.OntologyVersion).get(ontology.active_version_id)
        logger.info(f"Parent version ID: {parent_version.id}, Version number: {parent_version.version_number}")

        # 2. Create the new version record
        new_version = models.OntologyVersion(
            ontology_id=ontology.id,
            parent_version_id=parent_version.id,
            version_number=parent_version.version_number + 1,
            commit_message=commit_message,
            created_by_user_id=author.id,
            serialized_nodes={} # Will be filled later
        )
        self.db.add(new_version)
        self.db.flush()
        logger.info(f"Created new version record with ID: {new_version.id}")

        # 3. Copy links from parent to new version
        parent_links = self.db.query(models.OntologyVersionNodeLink).filter(
            models.OntologyVersionNodeLink.version_id == parent_version.id
        ).all()

        new_links_map = {}
        for link in parent_links:
            new_link = models.OntologyVersionNodeLink(
                version_id=new_version.id,
                node_id=link.node_id,
                parent_node_id=link.parent_node_id
            )
            self.db.add(new_link)
            new_links_map[link.node_id] = new_link
        
        logger.info(f"Copied {len(parent_links)} links from parent version to new version.")
        self.db.flush()

        # 4. Apply all changes in a logical order
        logger.info(f"Applying {len(changes)} calculated changes...")
        changes_by_type = {
            "delete": [c for c in changes if c['type'] == 'delete'],
            "add": [c for c in changes if c['type'] == 'add'],
            "update": [c for c in changes if c['type'] == 'update'],
            "move": [c for c in changes if c['type'] == 'move'],
        }

        # --- Process Deletions First ---
        for change in changes_by_type['delete']:
            stable_id = uuid.UUID(str(change["stable_id"]))
            logger.info(f"  - Processing DELETE for stable_id: {stable_id}")
            node_to_delete_q = self.db.query(models.OntologyNode).join(
                models.OntologyVersionNodeLink,
                models.OntologyNode.id == models.OntologyVersionNodeLink.node_id
            ).filter(
                models.OntologyVersionNodeLink.version_id == new_version.id,
                models.OntologyNode.stable_id == stable_id
            ).first()
            if not node_to_delete_q:
                logger.warning(f"    - Node with stable_id {stable_id} not found in new version links. It might have been deleted as a descendant. Skipping.")
                continue

            descendant_ids = self._find_descendant_node_ids(new_version.id, node_to_delete_q.id)
            ids_to_remove = descendant_ids.union({node_to_delete_q.id})
            logger.info(f"    - Found {len(descendant_ids)} descendants. Deleting links for {len(ids_to_remove)} total nodes.")

            links_to_delete_q = self.db.query(models.OntologyVersionNodeLink).filter(
                models.OntologyVersionNodeLink.version_id == new_version.id,
                models.OntologyVersionNodeLink.node_id.in_(ids_to_remove)
            )
            links_to_delete_q.delete(synchronize_session=False)

        # --- Process Additions (Two-phase commit) ---
        newly_created_nodes_map = {} # Maps name -> OntologyNode object
        add_changes = changes_by_type['add']
        if add_changes:
            logger.info("  - Processing ADDITIONS (Phase 1: Creating node objects)...")
            for change in add_changes:
                node_data = change["node_data"]
                logger.info(f"    - Creating node object for '{node_data['name']}'")
                new_node = models.OntologyNode(
                    knowledge_space_id=knowledge_space_id,
                    stable_id=uuid.uuid4(),
                    name=node_data["name"],
                    constraints=node_data.get("constraints"),
                    node_metadata=node_data.get("node_metadata"),
                    content_hash=_calculate_node_hash(node_data)
                )
                self.db.add(new_node)
                newly_created_nodes_map[new_node.name] = new_node
            self.db.flush() # Flush to assign IDs to all new nodes
            logger.info("    - Flushed to assign IDs to all new nodes.")

            logger.info("  - Processing ADDITIONS (Phase 2: Creating links)...")
            # Build a map of all nodes (old and new) in the new version for parent lookup
            all_nodes_q = self.db.query(models.OntologyVersionNodeLink).options(joinedload(models.OntologyVersionNodeLink.node)).filter(
                models.OntologyVersionNodeLink.version_id == new_version.id
            ).all()
            all_nodes_in_new_version_map = {link.node.name: link.node for link in all_nodes_q if link.node}
            all_nodes_in_new_version_map.update(newly_created_nodes_map)
            logger.info(f"    - Built a map of {len(all_nodes_in_new_version_map)} total nodes for parent lookup.")

            for change in add_changes:
                node_name = change["node_data"]["name"]
                parent_name = change.get("parent_name")
                logger.info(f"    - Linking node '{node_name}' to parent '{parent_name}'")
                new_node = newly_created_nodes_map.get(node_name)
                parent_node = all_nodes_in_new_version_map.get(parent_name) if parent_name else None
                
                if not new_node:
                    logger.error(f"      - CRITICAL: Newly created node '{node_name}' not found in map!")
                    continue
                if parent_name and not parent_node:
                    logger.error(f"      - CRITICAL: Parent node '{parent_name}' not found in map!")
                    continue

                self.db.add(models.OntologyVersionNodeLink(
                    version_id=new_version.id,
                    node_id=new_node.id,
                    parent_node_id=parent_node.id if parent_node else None
                ))

        # --- Process Updates ---
        for change in changes_by_type['update']:
            stable_id, new_node_data = uuid.UUID(str(change["stable_id"])), change["new_node_data"]
            logger.info(f"  - Processing UPDATE for stable_id: {stable_id}")
            old_node_q = self.db.query(models.OntologyNode).join(
                models.OntologyVersionNodeLink,
                models.OntologyNode.id == models.OntologyVersionNodeLink.node_id
            ).filter(
                models.OntologyVersionNodeLink.version_id == new_version.id,
                models.OntologyNode.stable_id == stable_id
            ).first()
            if not old_node_q:
                logger.error(f"    - Node to update {stable_id} not found. Skipping.")
                continue

            logger.info(f"    - Creating new node version for '{new_node_data['name']}'")
            new_node = models.OntologyNode(
                knowledge_space_id=knowledge_space_id, stable_id=stable_id,
                name=new_node_data["name"], constraints=new_node_data.get("constraints"),
                node_metadata=new_node_data.get("node_metadata"), content_hash=_calculate_node_hash(new_node_data)
            )
            self.db.add(new_node)
            self.db.flush()

            logger.info(f"    - Updating link from old node ID {old_node_q.id} to new node ID {new_node.id}")
            self.db.query(models.OntologyVersionNodeLink).filter(
                models.OntologyVersionNodeLink.version_id == new_version.id,
                models.OntologyVersionNodeLink.node_id == old_node_q.id
            ).update({"node_id": new_node.id})

        # --- Process Moves ---
        # (Logging for moves can be added here if the functionality is used)

        # 5. Rebuild the serialized tree for the new version
        logger.info("Rebuilding serialized tree for the new version...")
        new_version.serialized_nodes = self._rebuild_serialized_tree(new_version.id)
        logger.info(f"Final serialized tree:\n{json.dumps(new_version.serialized_nodes, indent=2, ensure_ascii=False)}")

        # 6. Update the 'HEAD' pointer
        logger.info(f"Updating ontology's active_version_id to {new_version.id}")
        ontology.active_version_id = new_version.id

        self.db.commit()
        self.db.refresh(new_version)
        logger.info("--- Commit engine finished successfully. ---")

        return new_version

    def commit_version_from_json_tree(
        self,
        knowledge_space_id: uuid.UUID,
        author: models.User,
        commit_message: str,
        new_tree: Dict[str, Any]
    ) -> models.OntologyVersion:
        """
        通过对比当前活跃本体论与新的JSON树结构，计算必要的原子变更并提交新版本。

        Args:
            knowledge_space_id: 知识空间ID
            author: 提交作者
            commit_message: 提交消息
            new_tree: 新的本体论树结构

        Returns:
            新创建的本体论版本
        """
        # 1. 获取当前活跃的本体论树
        current_tree = self._get_raw_active_ontology_tree(knowledge_space_id)
        logger.info(f"--- Ontology Update ---")
        logger.info(f"Current Tree: {json.dumps(current_tree, indent=2, ensure_ascii=False)}")
        logger.info(f"New Tree Received: {json.dumps(new_tree, indent=2, ensure_ascii=False)}")

        # 2. 计算差异以生成变更指令集
        changes = self._calculate_diff(current_tree, new_tree)
        logger.info(f"Calculated Changes ({len(changes)}): {json.dumps(changes, indent=2, ensure_ascii=False)}")

        # 如果没有变更，不创建新版本，返回当前版本
        if not changes:
            logger.info("No changes detected in ontology tree. Skipping new version creation.")
            ontology = self.db.query(models.Ontology).filter_by(knowledge_space_id=knowledge_space_id).first()
            return self.db.query(models.OntologyVersion).get(ontology.active_version_id)

        # 3. 调用底层提交引擎执行变更
        return self._commit_new_version_from_changes(
            knowledge_space_id=knowledge_space_id,
            author=author,
            commit_message=commit_message,
            changes=changes
        )

    def _flatten_tree_to_map(self, tree: Dict[str, Any]) -> Dict[str, Dict]:
        """
        (内部方法) 将标准的内部树结构（带stable_id）扁平化为以stable_id为键的映射。
        """
        nodes_map = {}

        def recurse(node, parent_stable_id=None):
            if not isinstance(node, dict) or 'stable_id' not in node:
                return

            stable_id = node['stable_id']
            node_data = {
                "name": node.get('name'),
                "constraints": node.get('constraints'),
                "node_metadata": node.get('node_metadata'),
            }
            nodes_map[stable_id] = {
                "parent_stable_id": parent_stable_id,
                "data": node_data,
                "content_hash": _calculate_node_hash(node_data)
            }

            for child in node.get('children', []):
                recurse(child, stable_id)

        if tree:
            recurse(tree)
        return nodes_map

    def _calculate_diff(self, old_tree: Dict, new_tree: Dict) -> List[Dict]:
        """
        Performs a true diff between the old and new ontology states, preserving
        node identity (stable_id) for unchanged nodes. It correctly calculates
        add, delete, and update operations.
        """
        
        def flatten_internal_tree(node: Dict, parent_name: str | None, flat_map: Dict):
            """
            Recursively flattens the existing tree structure (from the database)
            into a map with a (parent_name, node_name) key.
            """
            node_name = node['name']
            key = (parent_name, node_name)
            
            # Extract data used for content hashing
            node_data_for_hash = {
                "name": node.get("name"),
                "constraints": node.get("constraints"),
                "node_metadata": node.get("node_metadata"),
            }
            
            flat_map[key] = {
                'stable_id': node['stable_id'],
                'data': node,
                'hash': _calculate_node_hash(node_data_for_hash)
            }
            
            for child in node.get('children', []):
                flatten_internal_tree(child, node_name, flat_map)

        def flatten_new_tree(new_children: Dict, parent_name: str, flat_map: Dict):
            """
            Recursively flattens the new, user-provided tree structure into the
            same map format for comparison.
            """
            for name, data in new_children.items():
                key = (parent_name, name)
                
                node_data = {'name': name}
                if isinstance(data, list):  # Leaf node with constraints
                    node_data['constraints'] = data
                
                flat_map[key] = {
                    'stable_id': None, # New nodes don't have a stable_id yet
                    'data': node_data,
                    'hash': _calculate_node_hash(node_data)
                }
                
                if isinstance(data, dict):  # Node with children, recurse
                    flatten_new_tree(data, name, flat_map)

        # --- Main Diff Logic ---
        if not old_tree:
            return []

        # 1. Flatten both the old tree and the new tree into comparable maps.
        old_map = {}
        flatten_internal_tree(old_tree, None, old_map)

        # The new map represents the complete desired state. It starts with the
        # old root, and then the user's `new_tree` is flattened as its children.
        new_map = {}
        root_key = (None, old_tree['name'])
        if root_key in old_map:
            new_map[root_key] = old_map[root_key] # Preserve the root
        
        flatten_new_tree(new_tree, old_tree['name'], new_map)

        logger.info(f"Old Map ({len(old_map)}): {json.dumps({str(k): v for k, v in old_map.items()}, indent=2, ensure_ascii=False)}")
        logger.info(f"New Map ({len(new_map)}): {json.dumps({str(k): v for k, v in new_map.items()}, indent=2, ensure_ascii=False)}")

        changes = []
        
        # 2. Identify Deletions: Nodes present in the old map but not in the new map.
        for key, old_node in old_map.items():
            if key not in new_map:
                changes.append({"type": "delete", "stable_id": old_node["stable_id"]})

        # 3. Identify Additions and Updates: Iterate through the new map.
        for key, new_node in new_map.items():
            if key not in old_map:
                # It's a new node.
                parent_name, _ = key
                changes.append({
                    "type": "add",
                    "parent_name": parent_name,
                    "node_data": new_node['data']
                })
            else:
                # Node exists in both. Check if its content has been updated.
                old_node = old_map[key]
                if old_node['hash'] != new_node['hash']:
                    changes.append({
                        "type": "update",
                        "stable_id": old_node["stable_id"],
                        "new_node_data": new_node['data']
                    })

        # Process deletions first to avoid conflicts (e.g., moving a node to a
        # parent that is about to be deleted).
        changes.sort(key=lambda x: 1 if x['type'] == 'delete' else 2)
        
        logger.info(f"Calculated Changes ({len(changes)}): {json.dumps(changes, indent=2, ensure_ascii=False)}")
        return changes

    def get_active_ontology_as_simple_dict(self, knowledge_space_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieves the active ontology and formats it into a simple, nested dictionary
        containing only node names, suitable for display or for LLM prompts.
        """
        full_tree = self.get_active_ontology_tree(knowledge_space_id)
        if not full_tree:
            return {}

        def simplify_tree(node: Dict[str, Any]) -> Dict[str, Any]:
            simple_node = {}
            children = node.get("children", [])
            if not children:
                return {}
            
            child_dict = {}
            for child in children:
                child_dict[child["name"]] = simplify_tree(child)
            return child_dict

        # Handle the case where full_tree is a list (when __root__ is stripped)
        if isinstance(full_tree, list):
            # Return a dictionary with each top-level node as a key
            result = {}
            for node in full_tree:
                if isinstance(node, dict) and "name" in node:
                    result[node["name"]] = simplify_tree(node)
            return result
        
        # Handle the case where full_tree is a single dictionary (legacy format)
        if isinstance(full_tree, dict) and "name" in full_tree:
            return {full_tree["name"]: simplify_tree(full_tree)}
        
        # Fallback for unexpected formats
        return {}
    
    def delete_ontology_for_knowledge_space(self, knowledge_space_id: uuid.UUID) -> None:
        """
        删除指定知识空间的所有本体数据，包括本体、版本、节点和链接。
        这是一个危险操作，通常只在删除知识空间时调用。
        """
        try:
            logger.info(f"Deleting ontology data for knowledge space {knowledge_space_id}")
            
            # 获取本体
            ontology = self.db.query(models.Ontology).filter(
                models.Ontology.knowledge_space_id == knowledge_space_id
            ).first()
            
            if not ontology:
                logger.warning(f"No ontology found for knowledge space {knowledge_space_id}")
                return
            
            # 删除所有版本的节点链接
            self.db.query(models.OntologyVersionNodeLink).filter(
                models.OntologyVersionNodeLink.version_id.in_(
                    self.db.query(models.OntologyVersion.id).filter(
                        models.OntologyVersion.ontology_id == ontology.id
                    )
                )
            ).delete(synchronize_session=False)
            
            # 删除所有本体节点
            self.db.query(models.OntologyNode).filter(
                models.OntologyNode.knowledge_space_id == knowledge_space_id
            ).delete(synchronize_session=False)
            
            # 删除所有本体版本
            self.db.query(models.OntologyVersion).filter(
                models.OntologyVersion.ontology_id == ontology.id
            ).delete(synchronize_session=False)
            
            # 删除本体本身
            self.db.delete(ontology)
            
            logger.info(f"Successfully deleted ontology data for knowledge space {knowledge_space_id}")
            
        except Exception as e:
            logger.error(f"Error deleting ontology for knowledge space {knowledge_space_id}: {e}")
            raise
