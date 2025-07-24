# **Kosmos 知识库系统设计文档 (v2.0)**

## **1\. 核心设计哲学**

Kosmos 旨在成为一个可扩展、智能且高度解耦的知识管理系统。其核心哲学基于以下两点：

1. **内容与语境分离**: 通过区分**物理文档 (Physical Document)** 和 **逻辑文档 (Logical Document)**，实现原始文件存储与知识库应用的解耦。物理文档代表独一无二的内容实体，而逻辑文档是该内容在特定知识库中的“化身”，携带了上下文相关的元数据。这极大地提高了存储效率和系统灵活性。  
2. **所指与能指分离**: 借鉴符号学理论，我们将知识单元进行二元划分：  
   * **片段 (Fragment)**: 作为“所指”(Signified)，是构成物理文档的原子内容单元（文本、图像），代表着客观存在的事实本身。  
   * **索引 (Index)**: 作为“能指”(Signifier)，是对片段内容的描述和解释（关键词、标签、向量嵌入），是语义层面的表达，用于检索和理解。

这种分离使得系统可以灵活地采用多种索引技术，并实现从查询到具体知识点的精准定位。

## **2\. 实体关系图 (ERD)**

下图展示了 Kosmos 系统的核心实体及其关系。

erDiagram  
    User {  
        int user\_id PK  
        string name  
        string role "ENUM('superadmin', 'admin', 'user')"  
    }

    KnowledgeBase {  
        int kb\_id PK  
        string name  
        int owner\_id FK  
        jsonb tag\_directory\_config "version, tags"  
        jsonb embedding\_config "model, dim, version"  
        jsonb search\_config "weights, top\_k"  
    }

    PhysicalDocument {  
        int phys\_doc\_id PK  
        string content\_hash "UNIQUE"  
        string mime\_type  
        string url  
        int reference\_count  
    }

    LogicalDocument {  
        int log\_doc\_id PK  
        int kb\_id FK  
        int phys\_doc\_id FK  
        string name  
        string status "ENUM('pending', 'processing', 'ready', 'error')"  
        timestamp uploaded\_at  
    }

    Fragment {  
        bigint fragment\_id PK  
        int phys\_doc\_id FK  
        string type "ENUM('text', 'figure', 'screenshot')"  
        text content  
        text description  
        int sequence\_order  
        int page\_start  
        int page\_end  
    }

    Index {  
        bigint index\_id PK  
        int kb\_id FK  
        bigint fragment\_id FK  
        \-- embedding is stored in vector DB  
    }

    Tag {  
        int tag\_id PK  
        int kb\_id FK  
        string tag\_name  
        UNIQUE(kb\_id, tag\_name)  
    }

    Index\_Tag\_Link {  
        bigint index\_id FK  
        int tag\_id FK  
        PRIMARY KEY(index\_id, tag\_id)  
    }

    Job {  
        uuid job\_id PK  
        int kb\_id FK  
        string type "ENUM('DOC\_INGESTION', 'KB\_REINDEX', ...)"  
        string status "ENUM('pending', 'running', 'completed', 'failed')"  
        jsonb payload  
        timestamp created\_at  
    }

    Task {  
        uuid task\_id PK  
        uuid job\_id FK  
        string type "ENUM('PARSE', 'EMBED', 'TAG', ...)"  
        string status "ENUM('pending', 'running', 'completed', 'failed')"  
        jsonb result  
        timestamp started\_at  
        timestamp finished\_at  
    }

    User ||--o{ KnowledgeBase : owns  
    KnowledgeBase ||--|{ LogicalDocument : contains  
    KnowledgeBase ||--|{ Tag : defines  
    KnowledgeBase }o--o{ Job : initiates  
    PhysicalDocument ||--o{ LogicalDocument : is\_represented\_by  
    PhysicalDocument ||--|{ Fragment : is\_composed\_of  
    LogicalDocument ||--|{ Index : has  
    Fragment ||--|| Index : points\_to  
    Index }o--o{ Tag : is\_described\_by (via Index\_Tag\_Link)  
    Job ||--|{ Task : consists\_of

## **3\. 数据库表结构设计**

### **3.1 核心实体**

**Users**

CREATE TABLE Users (  
    user\_id SERIAL PRIMARY KEY,  
    name VARCHAR(100) NOT NULL,  
    password\_hash VARCHAR(255) NOT NULL,  
    email VARCHAR(255) NOT NULL UNIQUE,  
    role VARCHAR(20) NOT NULL DEFAULT 'user', \-- superadmin, admin, user  
    created\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP  
);

**KnowledgeBases**

CREATE TABLE KnowledgeBases (  
    kb\_id SERIAL PRIMARY KEY,  
    owner\_id INT NOT NULL REFERENCES Users(user\_id),  
    name VARCHAR(255) NOT NULL,  
    description TEXT,  
    tag\_directory\_config JSONB, \-- { "version": 1, "tags": \["tag1", "tag2"\] }  
    embedding\_config JSONB,   \-- { "version": 1, "model": "text-embedding-ada-002", "dim": 1536 }  
    search\_config JSONB,      \-- { "like\_tag\_weight": 0.3, "reranker\_top\_k": 5 }  
    created\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP  
);

* **设计亮点**: 将易变的配置（标签字典、模型、搜索权重）存入 JSONB 字段并引入版本号，为后续的治理和索引更新提供了依据。

**PhysicalDocuments**

CREATE TABLE PhysicalDocuments (  
    phys\_doc\_id SERIAL PRIMARY KEY,  
    content\_hash VARCHAR(64) NOT NULL UNIQUE, \-- SHA-256  
    mime\_type VARCHAR(100) NOT NULL,  
    extension VARCHAR(10),  
    url VARCHAR(1024) NOT NULL, \-- S3/MinIO URL  
    reference\_count INT NOT NULL DEFAULT 0,  
    created\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP  
);

* **设计亮点**: reference\_count 用于实现物理文件的垃圾回收机制。

**LogicalDocuments**

CREATE TABLE LogicalDocuments (  
    log\_doc\_id SERIAL PRIMARY KEY,  
    kb\_id INT NOT NULL REFERENCES KnowledgeBases(kb\_id) ON DELETE CASCADE,  
    phys\_doc\_id INT NOT NULL REFERENCES PhysicalDocuments(phys\_doc\_id),  
    name VARCHAR(512) NOT NULL,  
    status VARCHAR(20) NOT NULL DEFAULT 'pending', \-- pending, processing, ready, error  
    uploaded\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP,  
    processed\_at TIMESTAMPTZ, \-- a composite of parsed\_at and indexed\_at  
    UNIQUE (kb\_id, phys\_doc\_id)  
);

* **设计亮点**: status 字段为前端展示和后台任务管理提供了清晰的状态机。

**Fragments**

CREATE TABLE Fragments (  
    fragment\_id BIGSERIAL PRIMARY KEY,  
    phys\_doc\_id INT NOT NULL REFERENCES PhysicalDocuments(phys\_doc\_id) ON DELETE CASCADE,  
    type VARCHAR(20) NOT NULL, \-- text, figure, screenshot  
    content TEXT NOT NULL, \-- For text, it's content; for images, it's the image URL  
    description TEXT, \-- For text, a summary; for images, a VLM-generated description  
    sequence\_order INT NOT NULL, \-- Order within the same type of fragments  
    page\_start INT, \-- PDF page start, nullable  
    page\_end INT,   \-- PDF page end, nullable  
    metadata JSONB \-- e.g., character count, image resolution  
);

* **优化**: index \-\> sequence\_order，page\_index \-\> page\_start/page\_end。

**Indexes**

CREATE TABLE Indexes (  
    index\_id BIGSERIAL PRIMARY KEY,  
    kb\_id INT NOT NULL REFERENCES KnowledgeBases(kb\_id) ON DELETE CASCADE,  
    fragment\_id BIGINT NOT NULL REFERENCES Fragments(fragment\_id) ON DELETE CASCADE,  
    tagging\_version INT, \-- Corresponds to kb.tag\_directory\_config.version  
    embedding\_version INT, \-- Corresponds to kb.embedding\_config.version  
    \-- The embedding vector itself is stored in a dedicated vector database like Milvus/Weaviate  
    UNIQUE (kb\_id, fragment\_id)  
);

* **设计亮点**: 索引记录了其生成时所依据的配置版本，便于检测和处理“过时”索引。

**Tags & Index\_Tag\_Links** (标签规范化)

\-- Tags defined within a knowledge base  
CREATE TABLE Tags (  
    tag\_id SERIAL PRIMARY KEY,  
    kb\_id INT NOT NULL REFERENCES KnowledgeBases(kb\_id) ON DELETE CASCADE,  
    tag\_name VARCHAR(100) NOT NULL,  
    UNIQUE (kb\_id, tag\_name)  
);

\-- Link table for many-to-many relationship  
CREATE TABLE Index\_Tag\_Links (  
    index\_id BIGINT NOT NULL REFERENCES Indexes(index\_id) ON DELETE CASCADE,  
    tag\_id INT NOT NULL REFERENCES Tags(tag\_id) ON DELETE CASCADE,  
    PRIMARY KEY (index\_id, tag\_id)  
);

* **优化**: 彻底解决了字符串存储标签的性能和准确性问题，是系统可扩展性的关键。

### **3.2 调度系统实体**

**Jobs**

CREATE TABLE Jobs (  
    job\_id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    kb\_id INT REFERENCES KnowledgeBases(kb\_id),  
    user\_id INT REFERENCES Users(user\_id),  
    type VARCHAR(50) NOT NULL, \-- e.g., DOC\_INGESTION, KB\_REINDEX, KB\_TAG\_SYNC  
    status VARCHAR(20) NOT NULL DEFAULT 'pending', \-- pending, running, completed, failed, partially\_completed  
    payload JSONB, \-- For DOC\_INGESTION, { "log\_doc\_id": 123 }; for KB\_REINDEX, { "target\_version": 2 }  
    created\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP,  
    finished\_at TIMESTAMPTZ  
);

**Tasks**

CREATE TABLE Tasks (  
    task\_id UUID PRIMARY KEY DEFAULT gen\_random\_uuid(),  
    job\_id UUID NOT NULL REFERENCES Jobs(job\_id) ON DELETE CASCADE,  
    type VARCHAR(50) NOT NULL, \-- e.g., DOWNLOAD\_FILE, PARSE\_PDF, CHUNK\_TEXT, EMBED\_FRAGMENT, TAG\_FRAGMENT  
    status VARCHAR(20) NOT NULL DEFAULT 'pending', \-- pending, running, completed, failed  
    payload JSONB, \-- e.g., { "fragment\_id": 456, "text": "..." }  
    result JSONB, \-- e.g., { "chunk\_count": 10 } or { "error\_message": "..." }  
    dependency\_task\_id UUID, \-- ID of the task that must complete before this one starts  
    created\_at TIMESTAMPTZ DEFAULT CURRENT\_TIMESTAMP,  
    started\_at TIMESTAMPTZ,  
    finished\_at TIMESTAMPTZ  
);

## **4\. 调度系统 (Job/Task) 详细设计**

Kosmos 的所有长耗时操作均由调度系统异步执行，确保了 API 的快速响应和系统的健壮性。

### **4.1 架构**

采用标准的 **生产者-消费者** 模型：

* **生产者 (Producer)**: API 服务。当用户上传文档或触发重索引时，API 服务仅在 Jobs 和 Tasks 表中创建记录，然后立即返回 job\_id 给用户。  
* **消息队列 (Queue)**: 使用 Redis 或 RabbitMQ。新创建的 Task 被推送到相应的队列中（例如 parsing\_queue, embedding\_queue）。  
* **消费者 (Consumer/Worker)**: 一组独立的后台服务进程，监听队列，获取并执行 Task。Worker 可以根据负载水平扩展。

### **4.2 核心 Job 与 Task 流程**

#### **Job: DOC\_INGESTION (文档入库)**

1. **触发**: 用户上传文件，API 创建 LogicalDocument (status='pending') 和一个 Job (type='DOC\_INGESTION')。  
2. **任务分解**: 系统根据文件类型创建一系列有依赖关系的 Task。  
   * **示例 (处理 PDF)**:  
     1. Task(type=DOWNLOAD\_FILE): 从存储中下载文件到本地。  
     2. Task(type=PARSE\_PDF, depends\_on=DOWNLOAD\_FILE):  
        * 逐页截图，为每页创建 ScreenshotFragment。  
        * 提取文本和原生图片，创建 TextFragment 和 FigureFragment。  
        * 此任务完成后，LogicalDocument.status 更新为 'processing'。  
     3. Task(type=EMBED\_FRAGMENT, depends\_on=PARSE\_PDF): *为每个文本片段创建一个*。调用 Embedding 模型，将向量存入 Milvus。  
     4. Task(type=TAG\_FRAGMENT, depends\_on=PARSE\_PDF): *为每个文本片段创建一个*。调用 LLM，根据知识库的标签字典生成标签。  
3. **状态更新**:  
   * 每个 Task 完成后，更新自身状态。  
   * Worker 检查 Job 的所有 Task 是否都已 completed。  
   * 全部完成后，Job.status 更新为 'completed'，LogicalDocument.status 更新为 'ready'。  
   * 任何 Task 失败，则 Task.status 和 Job.status 均更新为 'failed'，并记录错误信息。

#### **Job: KB\_REINDEX (知识库重索引)**

1. **触发**: 用户更新了 KnowledgeBase 的 embedding\_config 或 tag\_directory\_config。  
2. **任务分解**:  
   1. 系统查询该 KB 下所有 Index 记录，对比 embedding\_version 和 tagging\_version 与 KB 的当前版本。  
   2. 为每个需要更新的 Fragment 创建 EMBED\_FRAGMENT 和/或 TAG\_FRAGMENT 任务。  
3. **执行**: Worker 执行这些独立的更新任务。此过程不影响现有索引的可用性。更新是原子的（先写新索引，再更新版本号）。

## **5\. 配置管理**

系统参数支持多级来源指定，优先级从高到低：

**API 调用参数 \> 知识库属性 \> 环境变量 \> 系统默认值**

* 1\. API 调用参数: 在搜索等请求的 Body 中直接指定。  
  POST /api/kbs/1/search {"query": "...", "retrieval\_top\_k": 20}  
* 2\. 知识库属性: 在 KnowledgeBases.search\_config 中为特定知识库配置。  
  { "retrieval\_top\_k": 15, "like\_tag\_weight": 0.4 }  
* 3\. 环境变量: 为整个服务实例设置全局配置。  
  KOSMOS\_RETRIEVAL\_TOP\_K=10  
* 4\. 系统默认值: 硬编码在代码中的最终回退值。  
  DEFAULT\_RETRIEVAL\_TOP\_K \= 5

**解析逻辑示例 (获取 retrieval\_top\_k)**:

def get\_retrieval\_top\_k(api\_params, kb\_settings, env\_vars, defaults):  
    if api\_params.get("retrieval\_top\_k") is not None:  
        return api\_params.get("retrieval\_top\_k")  
    if kb\_settings.get("retrieval\_top\_k") is not None:  
        return kb\_settings.get("retrieval\_top\_k")  
    if env\_vars.get("KOSMOS\_RETRIEVAL\_TOP\_K") is not None:  
        return int(env\_vars.get("KOSMOS\_RETRIEVAL\_TOP\_K"))  
    return defaults.get("DEFAULT\_RETRIEVAL\_TOP\_K")

## **6\. 核心工作流**

### **6.1 知识库搜索**

**Query \-\> 1.召回 \-\> 2.过滤 \-\> 3.重排 \-\> 4.标签推荐**

1. **召回 (Retrieval)**:  
   * 将用户查询文本进行 embedding。  
   * 在 Milvus 中进行向量相似度搜索，召回 retrieval\_top\_k 个最相关的 Fragment。  
2. **过滤 (Filtering)**:  
   * **Must Tags**: 如果用户指定了 must\_tags，则从召回结果中剔除**不包含所有**这些标签的 Fragment。通过高效的 Index\_Tag\_Links 表查询实现。  
   * **Like Tags**: 识别出召回结果中命中了 like\_tags 的 Fragment，用于下一步重排。  
3. **重排 (Reranking)**:  
   * 对过滤后的 Fragment 列表进行打分。  
   * fragment\_score \= (1 \- like\_tag\_weight) \* semantic\_score \+ like\_tag\_weight \* like\_tags\_hits\_score  
     * semantic\_score: 向量搜索返回的原始相似度分（需归一化）。  
     * like\_tags\_hits\_score: 命中 like\_tags 的数量或权重得分（需归一化）。  
     * like\_tag\_weight: 从配置中解析得到的权重值。  
   * 按 fragment\_score 降序排序，取前 reranker\_top\_k 个结果。  
4. **标签推荐 (Tag Recommendation)**:  
   * 在**重排后**的 reranker\_top\_k 个结果中，统计所有关联标签的出现次数。  
   * 计算每个标签的**理想标签偏移 (ITD)**: ITD \= abs(hits \- reranker\_top\_k / 2)。  
   * ITD 越小，说明该标签在结果中分布越“均匀”，既不过于普遍也不过于稀有，是区分结果的理想候选。  
   * 取 tag\_suggestion\_top\_k 个 ITD 最小的标签作为推荐，引导用户进行探索式查询。

### **6.2 删除与维护**

* **逻辑删除**: 删除 LogicalDocument 时，会级联删除其所有 Index 记录。同时，对应 PhysicalDocument 的 reference\_count 减 1。  
* **物理删除 (垃圾回收)**: 一个后台 Job 定期扫描 PhysicalDocuments 表，删除 reference\_count 为 0 的记录及其对应的物理文件和所有 Fragment。

## **7\. 总结**

这份 v2.0 设计文档在 v1.0 的基础上，通过**标签规范化**、**引入调度系统**、**细化配置管理**和**完善实体属性**，构建了一个更加健壮、可扩展和易于维护的知识库后端系统。它为开发一个企业级的智能知识管理平台提供了坚实的技术蓝图。