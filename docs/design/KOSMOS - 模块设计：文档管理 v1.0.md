## **1\. 概述**

文档管理模块负责处理用户上传的原始文档。它的核心设计原则是**内容寻址存储（Content-Addressable Storage）**，即通过文件内容的哈希值来唯一标识和存储文件，从而实现自动去重和数据完整性校验。

此模块仅处理**原始文档的上传、存储、下载和删除**。文档的解析、分割、打标签等过程由“文档摄入模块”负责。

## **2\. 数据模型 (SQLite)**

\-- 原始文档表 (全局唯一)  
CREATE TABLE documents (  
    id TEXT PRIMARY KEY,          \-- 文件内容的 SHA256 哈希值  
    filename TEXT NOT NULL,       \-- 上传时的原始文件名  
    file\_type TEXT NOT NULL,      \-- MIME 类型  
    file\_size INTEGER NOT NULL,     \-- 文件大小 (bytes)  
    file\_path TEXT NOT NULL UNIQUE, \-- 在本地文件系统的存储路径  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP  
);

\-- 知识库-文档关联表  
CREATE TABLE kb\_documents (  
    kb\_id TEXT NOT NULL,  
    document\_id TEXT NOT NULL,      \-- 关联到 documents(id)  
    uploaded\_by TEXT NOT NULL,      \-- 关联到 users(id)  
    upload\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    PRIMARY KEY (kb\_id, document\_id),  
    FOREIGN KEY (kb\_id) REFERENCES knowledge\_bases(id) ON DELETE CASCADE,  
    FOREIGN KEY (document\_id) REFERENCES documents(id) ON DELETE CASCADE,  
    FOREIGN KEY (uploaded\_by) REFERENCES users(id)  
);

## **3\. API 端点设计**

| 方法 | 路径 | 描述 | 所需权限 |
| :---- | :---- | :---- | :---- |
| POST | /api/v1/kbs/{kb\_id}/documents | 上传一个新文档到知识库 | KB Owner, Admin |
| GET | /api/v1/kbs/{kb\_id}/documents | 列出知识库中的所有文档 | KB Member |
| GET | /api/v1/kbs/{kb\_id}/documents/{doc\_id} | 获取文档元数据 | KB Member |
| GET | /api/v1/kbs/{kb\_id}/documents/{doc\_id}/download | 下载原始文档文件 | KB Member (可配置) |
| DELETE | /api/v1/kbs/{kb\_id}/documents/{doc\_id} | 从知识库中移除一个文档 | KB Owner, Admin |

**注意：** DELETE 操作仅从kb\_documents表中移除关联记录。如果一个文档不再被任何知识库引用，一个后台清理任务可以安全地删除documents记录和对应的物理文件。

## **4\. 核心流程与时序图**

### **4.1. 上传文档到知识库**

这是本模块最核心的流程，完整地展示了内容寻址存储的实现方式。

sequenceDiagram  
    participant User as "KB Admin/Owner"  
    participant API as "POST /kbs/{kb\_id}/documents"  
    participant DocService as "DocumentService"  
    participant DocRepo as "DocumentRepository"  
    participant FileStorage

    User-\>\>+API: 上传文件 (e.g., report.pdf)  
    Note right of User: (拥有对kb\_id的Admin/Owner权限)  
      
    API-\>\>+DocService: handle\_upload(kb\_id, user\_id, uploaded\_file)  
    DocService-\>\>DocService: 1\. 读取文件内容并计算SHA256哈希 (doc\_id)  
    DocService-\>\>+DocRepo: get\_document\_by\_id(doc\_id)  
    DocRepo--\>\>-DocService: 返回文档记录或 null

    alt 文档已存在 (doc\_id in 'documents' table)  
        DocService-\>\>+DocRepo: link\_document\_to\_kb(kb\_id, doc\_id, user\_id)  
        DocRepo--\>\>-DocService: 创建关联成功  
        DocService--\>\>-API: 返回现有文档信息  
    else 文档不存在  
        DocService-\>\>+FileStorage: save\_file(content, file\_path=hash)  
        FileStorage--\>\>-DocService: 文件存储成功  
          
        DocService-\>\>+DocRepo: 在事务中执行:  
        DocRepo-\>\>DocRepo: 1\. 插入到 \`documents\` 表  
        DocRepo-\>\>DocRepo: 2\. 插入到 \`kb\_documents\` 表  
        DocRepo--\>\>-DocService: 事务成功  
        DocService--\>\>-API: 返回新文档信息  
    end  
      
    API--\>\>-User: 返回 201 Created 和文档详情  
    Note over API, User: 响应中应建议用户触发下一步的“摄入”操作

