## **1\. 整体架构概览**

Kosmos采用前后端分离的现代Web应用架构，后端负责核心业务逻辑和数据处理，前端提供用户交互界面。核心服务依赖关系如下：

graph TD  
    subgraph 用户端  
        A\[Frontend/Client\]  
    end

    subgraph 后端服务 (FastAPI)  
        B\[API Gateway\]  
        C\[Service Layer\]  
        D\[Data Access Layer\]  
    end

    subgraph 核心存储  
        E\[SQLite\]  
        F\[Milvus\]  
        G\[Local File Storage\]  
    end  
      
    subgraph 外部AI服务  
        H\[LLM Service\]  
        I\[VLM Service\]  
    end

    A \-- HTTP/HTTPS \--\> B  
    B \-- 调用 \--\> C  
    C \-- 调用 \--\> D  
    C \-- 调用 \--\> H  
    C \-- 调用 \--\> I  
    D \-- 读写 \--\> E  
    D \-- 读写 \--\> F  
    D \-- 读写 \--\> G

* **Frontend/Client:** 任何可以调用HTTP API的客户端，如Web浏览器、桌面应用或脚本。  
* **Backend (FastAPI):** 基于Python的异步Web框架，提供所有API接口。  
* **SQLite:** 轻量级关系型数据库，存储除向量外的所有结构化数据，如用户信息、知识库元数据、文档信息、文本片段和任务状态。非常适合小团队部署。  
* **Milvus:** 高性能的向量数据库，专门用于存储和检索由文档片段内容生成的向量嵌入（Embeddings）。  
* **Local File Storage:** 本地文件系统，用于存储用户上传的原始文档。每个文件以其内容的SHA256哈希值命名，以实现内容寻址和去重。  
* **External AI Services:** 调用外部大语言模型（LLM）和视觉语言模型（VLM）的API，用于标签生成、图片理解等功能。

## **2\. 后端架构 (FastAPI)**

后端遵循经典的三层架构模式，以实现逻辑解耦和高可维护性。

/api/v1/  
├── auth/          \# 认证授权  
├── users/         \# 用户管理  
├── kbs/           \# 知识库管理  
├── documents/     \# 文档管理 (上传、下载、删除)  
└── jobs/          \# 摄入任务管理

* **API Layer (Routers):** 负责处理HTTP请求，验证输入数据（Pydantic模型），并调用相应的服务层方法。包含权限依赖注入。  
* **Service Layer:** 包含核心业务逻辑。例如，SearchService会编排查询解析、向量召回、标签过滤和重排序的整个流程。服务层是无状态的。  
* **Data Access Layer (Repositories):** 数据访问层，负责与数据库（SQLite）、向量存储（Milvus）和文件系统进行交互。它将底层数据操作封装成简单的方法供服务层调用。

## **3\. 数据模型设计**

### **3.1 SQLite 数据库ER图**

erDiagram  
    users {  
        TEXT id PK  
        TEXT username UK  
        TEXT email UK  
        TEXT password\_hash  
        TEXT role "system\_admin, user"  
    }

    knowledge\_bases {  
        TEXT id PK  
        TEXT name  
        TEXT description  
        TEXT owner\_id FK  
        TEXT tag\_dictionary "JSON"  
        BOOLEAN is\_public  
    }

    kb\_members {  
        TEXT kb\_id PK, FK  
        TEXT user\_id PK, FK  
        TEXT role "owner, admin, member"  
    }

    documents {  
        TEXT id PK "SHA256 hash"  
        TEXT filename  
        TEXT file\_type  
        INTEGER file\_size  
        TEXT file\_path  
    }

    kb\_documents {  
        TEXT kb\_id PK, FK  
        TEXT document\_id PK, FK  
        TEXT uploaded\_by FK  
        DATETIME upload\_at  
    }

    chunks {  
        TEXT id PK  
        TEXT kb\_id FK  
        TEXT document\_id FK  
        INTEGER chunk\_index  
        TEXT content  
        TEXT tags "JSON array"  
    }  
      
    ingestion\_jobs {  
        TEXT id PK  
        TEXT kb\_id FK  
        TEXT document\_id FK  
        TEXT status "pending, processing, completed, failed"  
        TEXT error\_message  
    }

    users ||--o{ knowledge\_bases : "owns"  
    users ||--|{ kb\_members : "is member of"  
    knowledge\_bases ||--|{ kb\_members : "has"  
    knowledge\_bases ||--o{ kb\_documents : "contains"  
    documents ||--o{ kb\_documents : "is part of"  
    users ||--o{ kb\_documents : "uploaded"  
    knowledge\_bases ||--o{ chunks : "contains"  
    documents ||--o{ chunks : "is split into"  
    knowledge\_bases ||--o{ ingestion\_jobs : "has"  
    documents ||--o{ ingestion\_jobs : "is for"

### **3.2 Milvus Collection 设计**

每个知识库（knowledge\_base）在Milvus中对应一个独立的Collection，以kb\_{kb\_id}命名，实现多租户数据隔离。

* **chunk\_id** (VARCHAR, Primary Key): 与SQLite中chunks表的id对应。  
* **document\_id** (VARCHAR): 便于按文档进行过滤。  
* **tags** (ARRAY of VARCHAR): 用于存储标签列表，实现高效的元数据过滤。  
* **embedding** (FLOAT\_VECTOR): 存储文档片段内容的向量。

## **4\. 部署与运维**

* **部署方式:** 推荐使用Docker Compose进行一键部署，将FastAPI应用、Milvus实例打包在一起。  
* **配置管理:** 所有敏感信息和可变参数（如模型名称、数据库路径、JWT密钥）通过环境变量进行配置，使用pydantic-settings库加载。  
* **备份:** 定期备份SQLite数据库文件和整个本地文件存储目录即可完成系统状态的完整备份。Milvus中的数据可以由SQLite中的chunks表重建。