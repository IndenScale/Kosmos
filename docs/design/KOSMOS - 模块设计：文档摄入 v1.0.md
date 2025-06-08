## **1\. 概述**

文档摄入模块负责执行一个复杂的、异步的流水线，将用户上传的原始文档转化为结构化的、可被搜索的“片段”（Chunks）。这是连接“原始数据”和“可用知识”的桥梁。

## **2\. 数据模型 (SQLite)**

\-- 文档片段表  
CREATE TABLE chunks (  
    id TEXT PRIMARY KEY,            \-- UUID  
    kb\_id TEXT NOT NULL,            \-- 所属知识库  
    document\_id TEXT NOT NULL,      \-- 所属文档  
    chunk\_index INTEGER NOT NULL,   \-- 在文档中的顺序  
    content TEXT NOT NULL,          \-- 片段的文本内容 (Markdown格式)  
    tags TEXT NOT NULL,             \-- LLM生成的标签 (JSON数组格式)  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    FOREIGN KEY (kb\_id) REFERENCES knowledge\_bases(id) ON DELETE CASCADE,  
    FOREIGN KEY (document\_id) REFERENCES documents(id) ON DELETE CASCADE  
);

\-- 摄入任务表  
CREATE TABLE ingestion\_jobs (  
    id TEXT PRIMARY KEY,            \-- UUID  
    kb\_id TEXT NOT NULL,  
    document\_id TEXT NOT NULL,  
    status TEXT NOT NULL,           \-- 'pending', 'processing', 'completed', 'failed'  
    error\_message TEXT,  
    created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,  
    FOREIGN KEY (kb\_id) REFERENCES knowledge\_bases(id) ON DELETE CASCADE,  
    FOREIGN KEY (document\_id) REFERENCES documents(id) ON DELETE CASCADE  
);

## **3\. API 端点设计**

摄入操作不直接通过自己的API启动，而是作为上传文档后的一个建议步骤。它通过一个任务（Job）系统来管理。

| 方法 | 路径 | 描述 | 所需权限 |
| :---- | :---- | :---- | :---- |
| POST | /api/v1/kbs/{kb\_id}/documents/{doc\_id}/ingest | 为指定文档创建并启动一个摄入任务 | KB Owner, Admin |
| GET | /api/v1/jobs/{job\_id} | 获取摄入任务的状态和结果 | 任务发起者 |
| GET | /api/v1/kbs/{kb\_id}/jobs | 列出指定知识库的所有摄入任务 | KB Owner, Admin |

## **4\. 核心流程与时序图**

### **4.1. 异步文档摄入流水线**

这是系统中最核心、最复杂的流程。用户请求启动摄入后，API立即返回一个任务ID，实际工作在后台异步执行。

sequenceDiagram  
    participant User as "KB Admin/Owner"  
    participant API as "POST .../ingest"  
    participant IngestionService  
    participant JobRepo as "JobRepository"  
      
    box "同步响应"  
        User-\>\>+API: 请求摄入 doc\_id  
        API-\>\>+IngestionService: start\_ingestion\_job(kb\_id, doc\_id)  
        IngestionService-\>\>+JobRepo: create\_job(kb\_id, doc\_id, status='pending')  
        JobRepo--\>\>-IngestionService: 返回 job\_id  
        IngestionService-\>\>IngestionService: asyncio.create\_task(self.\_run\_pipeline(...))  
        IngestionService--\>\>-API: 返回 job\_id  
        API--\>\>-User: 返回 202 Accepted 和 job\_id  
    end

    box "异步后台处理"  
        participant Pipeline as "IngestionPipeline"  
        participant DocRepo as "DocumentRepository"  
        participant Extractor  
        participant VLMService  
        participant TextSplitter  
        participant LLMService  
        participant EmbeddingService  
        participant ChunkRepo as "ChunkRepository"  
        participant MilvusRepo as "MilvusRepository"

        IngestionService-\>\>+Pipeline: \_run\_pipeline(job\_id, doc\_id)  
        Pipeline-\>\>+JobRepo: update\_job\_status(job\_id, 'processing')  
        JobRepo--\>\>-Pipeline: OK  
          
        Pipeline-\>\>+DocRepo: get\_document\_path(doc\_id)  
        DocRepo--\>\>-Pipeline: file\_path  
          
        Pipeline-\>\>+Extractor: extract\_content(file\_path)  
        Note right of Extractor: 分离文本和图片  
        Extractor--\>\>-Pipeline: text, images  
          
        Pipeline-\>\>+VLMService: describe\_images(images)  
        VLMService--\>\>-Pipeline: image\_descriptions  
          
        Pipeline-\>\>Pipeline: 将图片描述整合进文本，形成完整Markdown  
          
        Pipeline-\>\>+TextSplitter: split\_text(markdown\_content)  
        TextSplitter--\>\>-Pipeline: 返回文本片段列表 (chunks\_text)  
          
        loop 为每个文本片段  
            Pipeline-\>\>+LLMService: generate\_tags(chunk\_text, tag\_dictionary)  
            LLMService--\>\>-Pipeline: tags  
              
            Pipeline-\>\>+EmbeddingService: generate\_embedding(chunk\_text)  
            EmbeddingService--\>\>-Pipeline: embedding\_vector  
              
            Pipeline-\>\>Pipeline: 组装完整的Chunk对象  
        end  
          
        Pipeline-\>\>+ChunkRepo: save\_chunks\_to\_sqlite(chunks)  
        ChunkRepo--\>\>-Pipeline: OK  
          
        Pipeline-\>\>+MilvusRepo: save\_embeddings\_to\_milvus(chunks)  
        MilvusRepo--\>\>-Pipeline: OK  
          
        Pipeline-\>\>+JobRepo: update\_job\_status(job\_id, 'completed')  
        JobRepo--\>\>-Pipeline: OK  
          
        deactivate Pipeline  
    end  
