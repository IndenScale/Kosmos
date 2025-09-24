# **Kosmos: 平台数据模型详解**

本文档系统性地梳理了Kosmos知识管理平台所涉及的所有核心数据模型。这些模型被划分为两大类：**业务数据模型**，它们直接体现了Kosmos的核心业务价值；以及**管理数据模型**，它们为平台的稳定运行和协作功能提供必要的基础支持。

## **1\. 业务数据模型 (Business Data Models)**

这些模型是用户直接感知和消费的核心，构成了知识的存储、结构化和检索功能。

### **1.1. Document (文档)**

这是Kosmos中最核心的业务对象，代表用户摄入系统的一份完整知识。

* **存储位置**: SQL 数据库 (例如 PostgreSQL)  
* **核心字段**:  
  * doc\_id: string (主键)  
  * knowledge\_space\_id: string (外键)  
  * original\_content\_hash: string (外键，关联到Original表，指向原始文件)  
  * canonical\_asset\_hash: string | None (外键，指向其“规范化资产”)  
  * original\_filename: string  
  * uploaded\_by: string (外键，关联到User表)  
  * created\_at: timestamp (注册时间)  
  * last\_accessed\_at: timestamp  
  * status: string (文档的初始处理状态, e.g., "uploaded", "processing", "processed", "failed")

> **注意**: 文档的后续生命周期（如分块、打标）不再由`Document`模型自身的状态字段管理，而是通过独立的`Job`模型进行跟踪，实现了更清晰的关注点分离。

### **1.2. Chunk (数据块)**

Chunk是文档被结构化拆分后的原子单元，是知识检索和消费的基本单位。我们使用统一的Chunk模型来表示标题和内容。

* **存储位置**: SQL 数据库  
* **核心字段**:  
  * id: string (主键)  
  * doc\_id: string (外键)  
  * parent\_id: string | None (父级Chunk的ID)  
  * type: string ("heading" 或 "content")  
  * level: int (标题级别, content类型此字段为-1)  
  * start\_line, end\_line: int (在“规范化资产”中的行号)  
  * raw\_content, summary, paraphrase: string | None  
  * tags: list\[str\] | None

### **1.3. Index (向量索引)**

这是实现语义搜索的关键，是Chunk内容的数学表示。

* **存储位置**: 向量数据库 (例如 Milvus, Weaviate, Pinecone)  
* **设计讨论**:  
  * **过滤字段**: 为支持高效的混合搜索，索引中除了向量本身，还必须包含chunk\_id, doc\_id, knowledge\_space\_id, type, 和 tags作为元数据。  
  * **多嵌入策略**: 推荐使用支持单实体多向量功能的向量数据库（如Milvus）。每个chunk\_id可以关联两个独立的向量（一个来自summary，一个来自内容），在查询时可以同时搜索这两个向量，大大提高召回率和相关性，且无需管理多个Collection。  
  * **多租户策略**: 推荐在整个知识库中使用**单个Collection**，并通过在Collection内创建基于knowledge\_space\_id的\*\*分区（Partition）\*\*来实现知识空间的隔离。这种方式既能保证单知识空间内查询的高效率，又能灵活支持未来可能的跨知识空间查询，是伸缩性最佳的方案。  
* **核心字段**:  
  * chunk\_id: string (主键/外键)  
  * vectors: dict (包含多个向量, e.g., {"summary": \[...\], "content": \[...\]})  
  * (元数据) doc\_id, knowledge\_space\_id, type, tags

## **2\. 管理数据模型 (Management Data Models)**

这些模型为平台提供用户协作、资产管理和并发控制等核心支持功能。

### **2.1. KnowledgeSpace (知识空间)**

知识空间是协作的基本单位，是一个包含了文档、成员和本体论的容器。

* **存储位置**: SQL 数据库  
* **核心字段**:  
  * knowledge\_space\_id: string (主键)  
  * owner\_id: string (外键，关联到用户)  
  * name: string  
  * ontology\_dictionary: json (定义该空间内标签和关系的本体论)  
  * created\_at: timestamp

### **2.2. User & Membership (用户与成员关系)**

管理平台的用户及其在不同知识空间中的角色和权限。

* **存储位置**: SQL 数据库  
* **User 核心字段**:  
  * user\_id: string (主键)  
  * email: string  
  * name: string  
  * hashed\_password: string (存储哈希后的密码)
  * role: string ("super\_admin", "admin", "user")。系统中的第一个注册用户自动成为super\_admin。  
  * created\_at: timestamp  
* **KnowledgeSpace\_Members 核心字段**:  
  * knowledge\_space\_id: string (外键)  
  * user\_id: string (外键)  
  * role: string (e.g., "owner", "editor", "viewer")

#### **2.2.1. 认证机制 (Authentication Mechanism)**

平台采用基于 **JWT (JSON Web Token)** 的无状态认证机制。

*   **登录流程**:
    1.  用户通过登录接口提供 `email` 和 `password`。
    2.  服务器验证凭据的正确性。
    3.  验证成功后，服务器使用预设的 `SECRET_KEY` 和 `ALGORITHM` (如 HS256) 生成一个有时效性（例如30分钟）的 `access_token` 并返回给客户端。
*   **访问控制**:
    1.  客户端在后续所有需要授权的API请求中，必须在 HTTP Header 的 `Authorization` 字段中携带此 Token，格式为 `Bearer <access_token>`。
    2.  后端通过解析和验证 Token 来确认用户的身份和访问权限，无需再次查询数据库。

### **2.3. Original (原始文件)**

代表用户上传的、不可变的“原始证据”，通过内容寻址存储（CAS）进行管理。

* **存储位置**:  
  * 元数据: SQL 数据库  
  * 物理文件: 对象存储 (专用存储桶，如 kosmos-originals/)  
* **核心字段**:  
  * original\_hash: string (主键)  
  * file\_type: string  
  * size: int  
  * storage\_path: string  
  * created\_at: timestamp  
* **缓存复用**: 如果一个用户上传的文件其哈希已存在于Original表中，系统可以复用之前对该文件进行的所有处理结果（如已完成的Document和Chunk），避免重复计算。

### **2.4. Asset (派生资产)**

通过CAS管理的、经过系统处理的、可再生的中间文件。

* **存储位置**:  
  * 元数据: SQL 数据库  
  * 物理文件: 对象存储 (如 kosmos-assets/)  
* **设计讨论**:  
  * **last\_accessed\_at的必要性**: 添加此字段可以支持高级的缓存策略（如将热数据置于更快的存储层）或数据生命周期管理（如归档冷数据）。但它会为每次读操作增加一次写开销。考虑到Kosmos的设计目标，**建议初期添加此字段**，以便为未来的性能优化和成本控制预留可能性。  
* **核心字段**:  
  * asset\_hash: string (主键)  
  * file\_type: string (e.g., "markdown", "png")  
  * size: int  
  * storage\_path: string  
  * reference\_count: int (用于垃圾回收)  
  * created\_at: timestamp  
  * last\_accessed\_at: timestamp

### **2.5. Lock (分布式锁)**

用于确保对同一文档的写操作在同一时间只有一个Agent在进行，保证数据一致性。

* **存储位置**: Redis  
* **核心结构**:  
  * **Key**: lock:document:{doc\_id}:{task\_type}  
  * **Value**: lock\_id (唯一的随机字符串)  
  * **TTL (Time-To-Live)**: 锁会自动设置一个过期时间，以防止因Agent崩溃导致死锁。