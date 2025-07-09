## **1\. 概述**

语义搜索模块是Kosmos的核心功能入口，它为用户提供了一个强大且可预期的查询接口。该模块实现了一个“召回-过滤-重排序”（Retrieve-Filter-Re-rank）的三阶段搜索流水线，完美结合了向量搜索的模糊匹配能力和标签系统的精确筛选能力。

## **2\. API 端点设计**

| 方法 | 路径 | 描述 | 所需权限 |  
| POST | /api/v1/kbs/{kb\_id}/search | 在指定知识库中执行复合语义搜索 | KB Member |

### **2.1. 请求体模型 (Pydantic)**

from pydantic import BaseModel, Field  
from typing import List, Optional

class SearchQuery(BaseModel):  
    query: str \= Field(..., description="复合查询字符串，例如：'AI未来发展 \+技术 \-历史 \~应用'")  
    top\_k: int \= Field(10, gt=0, le=50, description="最终返回的结果数量")

### **2.2. 响应体模型 (Pydantic)**

from pydantic import BaseModel  
from typing import List, Dict

class SearchResult(BaseModel):  
    chunk\_id: str  
    document\_id: str  
    content: str  
    tags: List\[str\]  
    score: float \# 相似度或重排序分数

class RecommendedTag(BaseModel):  
    tag: str  
    freq: int \# 频数  
    eig\_score: float \# 信息增益分数

class SearchResponse(BaseModel):  
    results: List\[SearchResult\]  
    recommended\_tags: List\[RecommendedTag\]

## **3\. 核心流程与时序图**

### **3.1. "召回-过滤-重排序" 搜索流水线**

此流程详细描述了系统如何解析用户输入，分阶段执行搜索，并最终生成结构化的、包含智能推荐的响应。

sequenceDiagram  
    participant User as "KB Member"  
    participant API as "POST /kbs/{kb\_id}/search"  
    participant SearchService  
    participant QueryParser  
    participant MilvusRepo as "MilvusRepository"  
    participant Reranker  
    participant Recommender

    User-\>\>+API: 发送查询请求 (query, top\_k)  
    Note right of User: (拥有对kb\_id的Member权限)

    API-\>\>+SearchService: search(kb\_id, query, top\_k)  
      
    SearchService-\>\>+QueryParser: parse(query)  
    QueryParser--\>\>-SearchService: 返回解析后的对象 (text, must\_tags, must\_not\_tags, like\_tags)  
      
    %% \-- 1\. 召回 (Retrieve) & 过滤 (Filter) \--  
    SearchService-\>\>+MilvusRepo: retrieve\_with\_filter(kb\_id, text, must\_tags, must\_not\_tags)  
    Note over MilvusRepo: 使用文本进行向量搜索，\<br/\>同时使用 must/must\_not 标签构建 filter 表达式  
    MilvusRepo--\>\>-SearchService: 返回过滤后的 top N 个 chunk 结果  
      
    %% \-- 2\. 重排序 (Re-rank) \--  
    SearchService-\>\>+Reranker: rerank(retrieved\_docs, like\_tags)  
    Note over Reranker: 根据 'like\_tags' 命中情况\<br/\>对结果进行内存打分和排序  
    Reranker--\>\>-SearchService: 返回重排序后的文档列表 (reranked\_docs)  
      
    %% \-- 3\. 推荐 (Recommend) \--  
    SearchService-\>\>+Recommender: generate\_recommendations(reranked\_docs)  
    Note over Recommender: 统计标签频数 (freq) 和\<br/\>计算信息增益分数 (EIG Score)  
    Recommender--\>\>-SearchService: 返回推荐标签列表 (recommended\_tags)  
      
    SearchService-\>\>SearchService: 截取 top\_k 个结果  
    SearchService--\>\>-API: 组合最终响应对象 (SearchResponse)  
      
    API--\>\>-User: 返回 200 OK 和搜索结果

## **4\. 关键组件逻辑**

### **4.1. QueryParser**

* **职责：** 解析原始查询字符串。  
* **逻辑：**  
  1. 按空格分割字符串。  
  2. 第一个子串作为text。  
  3. 遍历剩余部分，根据前缀（+, \-, \~）分别放入must\_tags, must\_not\_tags, like\_tags列表。无前缀的默认为like\_tags。

### **4.2. MilvusRepository (retrieve\_with\_filter)**

* **职责：** 执行向量召回和元数据过滤。  
* **逻辑：**  
  1. 将查询text转换为向量。  
  2. 构建Milvus的bool\_expr过滤表达式。例如：  
     * tags in \["A", "B"\] and tags not in \["C"\]  
  3. 执行collection.search()方法，同时传入query\_vector和bool\_expr。这利用了Milvus的标量字段过滤能力，效率远高于在应用层过滤。

### **4.3. Reranker**

* **职责：** 对过滤后的结果集进行重排序。  
* **逻辑：**  
  1. 遍历每个召回的chunk。  
  2. 计算其重排序分数，一个简单的策略可以是：rerank\_score \= initial\_score \+ (number\_of\_matched\_like\_tags \* weight)。  
  3. 根据rerank\_score降序排序。

### **4.4. Recommender**

* **职责：** 生成推荐标签。  
* **逻辑：**  
  1. **统计频数 (freq):** 遍历重排序后的结果，用一个字典统计每个标签出现的次数。  
  2. **计算信息增益 (EIG Score):** 对每个标签，应用公式 EIG\_Score \= abs(freq \- (N\_reranked / 2))，其中N\_reranked是重排序后结果的总数。分数越接近0，代表该标签越能将当前结果集对半分，筛选能力越强。  
  3. 根据EIG\_Score（升序）和freq（降序）对标签排序后返回。