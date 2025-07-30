# Kosmos Knowledge Base System - README

Welcome to Kosmos, a pluggable semantic knowledge base system designed for modern enterprises and teams. Kosmos helps you build, manage, and leverage large-scale, multi-modal memory, transforming unstructured data into actionable intelligence.

## Core Value

- **Semantic Understanding**: Goes beyond keyword search. Kosmos understands the deep meaning of your data to provide more accurate and intelligent search results.
- **Multi-modal**: Seamlessly processes and indexes various data types, including text documents, images, and code snippets, creating a unified knowledge view.
- **Pluggable Architecture**: A flexible, modular design allows you to easily integrate different model services (e.g., Embedding, Reranking, LLM) to adapt to evolving technological needs.
- **Enterprise-Ready**: Provides comprehensive user permission management, multi-tenant knowledge bases, and asynchronous task processing to meet the stability and security requirements of enterprise applications.

## Core Concepts

The Kosmos knowledge system is built upon four core abstractions that progressively structure raw data into retrievable knowledge.

1.  **Knowledge Base (KB)**
    - **Definition**: The highest-level container, representing an independent knowledge domain or project space. Each KB has its own members, permission settings, model configurations, and tag system.
    - **Features**:
        - **Multi-tenancy**: Data and configurations are isolated between different knowledge bases.
        - **Configurability**: Each KB can be independently configured with its own AI models for Embedding, Reranking, LLM, etc.
        - **Tag Dictionary**: A hierarchical tag dictionary can be defined for precise content classification and filtering.

2.  **Document**
    - **Definition**: The raw material uploaded by users into a knowledge base, serving as the direct source of knowledge. Kosmos distinguishes between **Logical Documents** and **Physical Documents**.
    - **Logical Document**: A record of a user's upload action, containing metadata like filename and type.
    - **Physical Document**: The actual stored file. The system uses content hashing (SHA256) for deduplication, allowing multiple logical documents to point to a single physical file, thus saving storage space.

3.  **Fragment**
    - **Definition**: The smallest unit of knowledge, produced by intelligently parsing a document. It is the fundamental unit for system understanding, indexing, and retrieval.
    - **Types**:
        - **Text**: Paragraphs, sentences, or code blocks extracted from a document.
        - **Screenshot**: Page captures from a document.
        - **Figure**: Identified charts, tables, flowcharts, etc.
    - **Features**: Each fragment retains its positional information (e.g., page number) from the original document, enabling context traceability.

4.  **Index**
    - **Definition**: A retrievable record created by deeply processing a **Text Fragment**. It is the core of semantic search.
    - **Components**:
        - **Embedding**: A mathematical representation of the fragment's content, used for calculating semantic similarity.
        - **Tags**: Keywords or categories automatically generated for the fragment based on the KB's tag system and LLM understanding.
        - **Metadata**: Other information used for retrieval and filtering.
    - **Storage**: Index data is stored in a relational database (PostgreSQL), while embeddings are stored in a specialized vector database (e.g., Milvus) for efficient similarity search.

## System Architecture

Kosmos employs a classic three-tier architecture, ensuring high cohesion, low coupling, and ease of maintenance and extension.

- **Router Layer**: Located in `app/routers`. Receives external HTTP requests, validates parameters, and calls the appropriate service to handle them. It defines the system's API.
- **Service Layer**: Located in `app/services`. Contains the core business logic. It orchestrates data models and external services (like AI models) to perform specific business functions.
- **Model Layer**: Located in `app/models`. Defines the system's data structures and database table mappings (using SQLAlchemy ORM), forming the system's backbone.

**Data and Task Flow**:

1.  **Asynchronous Task Processing**: For time-consuming operations like document parsing and batch indexing, Kosmos uses an `asyncio`-based task queue (`UnifiedJobService`). Requests receive an immediate response while tasks run in the background. Users can query task status via the `jobs` API.
2.  **AI Model Integration**: The system manages access to external AI models through `CredentialService` and `KBModelConfig`. This makes it easy to swap or upgrade models by simply changing the configuration without altering core code.

## Key Features

- **User & Auth Management** (`auth`, `users`):
    - User registration, login, logout.
    - JWT-based authentication with refresh tokens.
    - Role-based access control (user, admin, system_admin).

- **Knowledge Base Management** (`knowledge_bases`):
    - Create, update, and delete knowledge bases.
    - Manage KB members and their roles (owner, admin, member).
    - Configure AI models and the tag dictionary for each KB.

- **Credential Management** (`credentials`):
    - Securely store and manage API keys and other credentials for AI models (with encryption).
    - Supports various model types (Embedding, Reranker, LLM, VLM).

- **Document Management** (`documents`):
    - Upload, download, and delete documents.
    - Batch operations for documents.
    - View the parsing and indexing status of documents.

- **Content Parsing** (`parser`):
    - Asynchronously parse uploaded documents to generate various fragment types.
    - Supports forced re-parsing.
    - Provides status queries for document parsing.

- **Index Management** (`index`):
    - Asynchronously create vector indexes and tags for text fragments.
    - Supports indexing tasks for single fragments, single documents, or batches of documents.
    - Provides indexing statistics for knowledge bases.

- **Semantic Search** (`search`):
    - **Hybrid Search**: Combines vector similarity with tag filtering for precise results.
    - **Advanced Query Syntax**: Supports `+tag` (must include), `-tag` (must not include), and `~tag` (preferred) syntax directly in the search box.
    - **Context-Aware**: Search results can be linked with related screenshots and figures for richer context.

- **Job Management** (`jobs`):
    - A unified interface to query and manage all background asynchronous tasks.
    - View task details, progress, and execution results.

## Quick Start

1.  **Run Dependency Services (Recommended)**
    This project relies on PostgreSQL and Milvus. We provide a `docker-compose.yml` file to launch both services with a single command.
    ```bash
    # This will start PostgreSQL and Milvus containers in the background
    docker-compose up -d
    ```

2.  **Configure Environment Variables**
    Copy the environment variable template and modify it as needed (especially the security keys).
    ```bash
    cp .env.example .env
    ```
    **Important**: Be sure to generate new, strong random values for `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, and `CREDENTIAL_ENCRYPTION_KEY` in your `.env` file.

3.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Launch the Backend Application**
    ```bash
    uvicorn app.main:app --reload
    ```
    Once the service is running, you can access the API documentation at `http://127.0.0.1:8000/docs`.

For more detailed deployment options and explanations of the environment variables, please refer to the [Deployment Guide (Chinese)](./部署指南.md).

---
*This documentation was generated with the assistance of Gemini CLI.*