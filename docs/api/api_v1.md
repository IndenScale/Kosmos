# Kosmos API v1.0.0

This document provides a comprehensive reference for the Kosmos API.

## **Table of Contents**
1.  [Authentication](#authentication)
2.  [Knowledge Bases](#knowledge-bases)
3.  [Documents](#documents)
4.  [Ingestion](#ingestion)
5.  [Search](#search)
6.  [Tagging](#tagging)
7.  [SDTM (Streaming Domain Topic Modeling)](#sdtm)
8.  [Screenshots](#screenshots)

---

## **1. Authentication**

Base Path: `/api/v1/auth`

### **Register User**
*   **Endpoint:** `POST /register`
*   **Description:** Creates a new user account.
*   **Request Body:** `UserRegister`
    ```json
    {
      "username": "newuser",
      "email": "newuser@example.com",
      "password": "a_strong_password"
    }
    ```
*   **Response (201):** `UserResponse`
    ```json
    {
      "id": "user_uuid",
      "username": "newuser",
      "email": "newuser@example.com",
      "role": "user",
      "created_at": "2025-07-07T10:00:00Z",
      "is_active": true
    }
    ```

### **Login for Access Token**
*   **Endpoint:** `POST /token`
*   **Description:** Authenticates a user and returns a JWT access token. The request should be `application/x-www-form-urlencoded`.
*   **Request Body:** `OAuth2PasswordRequestForm`
    ```
    username=newuser&password=a_strong_password
    ```
*   **Response (200):** `Token`
    ```json
    {
      "access_token": "your_jwt_token",
      "token_type": "bearer",
      "user": {
        "id": "user_uuid",
        "username": "newuser",
        "email": "newuser@example.com",
        "role": "user",
        "created_at": "2025-07-07T10:00:00Z",
        "is_active": true
      }
    }
    ```

---

## **2. Knowledge Bases**

Base Path: `/api/v1/kbs`

### **Create Knowledge Base**
*   **Endpoint:** `POST /`
*   **Description:** Creates a new knowledge base.
*   **Request Body:** `KBCreate`
    ```json
    {
      "name": "My New KB",
      "description": "A description for my new knowledge base.",
      "is_public": false
    }
    ```
*   **Response (201):** `KBResponse`

### **List My Knowledge Bases**
*   **Endpoint:** `GET /`
*   **Description:** Lists all knowledge bases the current user is a member of.
*   **Response (200):** `List[KBResponse]`

### **Get Knowledge Base Details**
*   **Endpoint:** `GET /{kb_id}`
*   **Description:** Retrieves details for a specific knowledge base, including members.
*   **Response (200):** `KBDetailResponse`

### **Update Knowledge Base**
*   **Endpoint:** `PUT /{kb_id}`
*   **Description:** Updates a knowledge base's name, description, or public status.
*   **Request Body:** `KBUpdate`
*   **Response (200):** `KBResponse`

### **Delete Knowledge Base**
*   **Endpoint:** `DELETE /{kb_id}`
*   **Description:** Deletes a knowledge base and all associated data.
*   **Response (204):** No Content

### **Update Tag Dictionary**
*   **Endpoint:** `PUT /{kb_id}/tags`
*   **Description:** Updates the knowledge base's tag dictionary directly.
*   **Request Body:** `TagDictionaryUpdate`
    ```json
    {
      "tag_dictionary": {
        "Category 1": ["Tag A", "Tag B"],
        "Category 2": {
          "Sub-Category": ["Tag C"]
        }
      }
    }
    ```
*   **Response (200):** `KBResponse`

### **Manage Members**
*   **Endpoint:** `POST /{kb_id}/members` (Add/Update Member), `DELETE /{kb_id}/members/{user_id}` (Remove Member)
*   **Description:** Manages members and their roles within a knowledge base.

---

## **3. Documents**

Base Path: `/api/v1/kbs/{kb_id}/documents`

### **Upload Document**
*   **Endpoint:** `POST /`
*   **Description:** Uploads a document to a knowledge base. The request must be `multipart/form-data`.
*   **Response (200):** `DocumentResponse`

### **List Documents**
*   **Endpoint:** `GET /`
*   **Description:** Lists all documents in a knowledge base, including chunk count and ingestion status.
*   **Response (200):** `DocumentListResponse`

### **Get Document Details**
*   **Endpoint:** `GET /{document_id}`
*   **Description:** Retrieves metadata for a specific document.
*   **Response (200):** `KBDocumentResponse`

### **Download Document**
*   **Endpoint:** `GET /{document_id}/download`
*   **Description:** Downloads the original uploaded file.
*   **Response (200):** File Stream

### **Remove Document**
*   **Endpoint:** `DELETE /{document_id}`
*   **Description:** Removes a document from a knowledge base and deletes its chunks and vectors.
*   **Response (204):** No Content

### **Batch Remove Documents**
*   **Endpoint:** `DELETE /batch`
*   **Description:** Removes multiple documents from a knowledge base in a single request.
*   **Request Body:** `BatchDeleteRequest` (`{"document_ids": ["id1", "id2"]}`)
*   **Response (200):** `BatchDeleteResponse`

---

## **4. Ingestion**

Base Path: `/api/v1`

### **Start Ingestion Job**
*   **Endpoint:** `POST /kbs/{kb_id}/documents/{document_id}/ingest`
*   **Description:** Starts an asynchronous job to process a document, turning it into searchable chunks.
*   **Query Parameters:**
    *   `skip_tagging` (bool, optional): If true, skips the LLM tagging step. Defaults to false.
*   **Response (202):** `IngestionJobResponse`

### **Re-ingest Document**
*   **Endpoint:** `POST /kbs/{kb_id}/documents/{document_id}/reingest`
*   **Description:** Deletes all existing data for a document and starts a new ingestion job.
*   **Response (202):** `IngestionJobResponse`

### **Get Job Status**
*   **Endpoint:** `GET /jobs/{job_id}`
*   **Description:** Retrieves the status of a specific ingestion job.
*   **Response (200):** `IngestionJobResponse`

### **List Knowledge Base Jobs**
*   **Endpoint:** `GET /kbs/{kb_id}/jobs`
*   **Description:** Lists all ingestion jobs for a specific knowledge base.
*   **Response (200):** `IngestionJobListResponse`

---

## **5. Search**

Base Path: `/api/v1`

### **Search Knowledge Base**
*   **Endpoint:** `POST /kbs/{kb_id}/search`
*   **Description:** Performs a hybrid search (semantic + keyword + tag filtering) within a knowledge base.
*   **Request Body:** `SearchQuery`
    ```json
    {
      "query": "main query text +must_have_tag -must_not_have_tag ~preferred_tag",
      "top_k": 10
    }
    ```
*   **Response (200):** `SearchResponse`

### **Get Chunk by ID**
*   **Endpoint:** `GET /chunks/{chunk_id}`
*   **Description:** Retrieves a specific chunk by its ID.
*   **Response (200):** `ChunkResponse`

---

## **6. Tagging**

Base Path: `/api/v1/tagging`

### **Tag Chunks**
*   **Endpoint:** `POST /{kb_id}/tag-chunks`
*   **Description:** Generates tags for specific chunks using the existing tag dictionary. If `chunk_ids` is null, it processes all untagged chunks.
*   **Request Body (optional):** `{"chunk_ids": ["id1", "id2"]}`
*   **Response (200):** `{ "success": true, "message": "...", "processed_count": X, "failed_count": Y }`

### **Tag Document**
*   **Endpoint:** `POST /{kb_id}/tag-document/{document_id}`
*   **Description:** Generates tags for all chunks within a specific document.
*   **Response (200):** `{ "success": true, "message": "...", "processed_count": X, "failed_count": Y }`

### **Get Tagging Stats**
*   **Endpoint:** `GET /{kb_id}/stats`
*   **Description:** Retrieves statistics about tagged vs. untagged chunks in a knowledge base.
*   **Response (200):** `{ "total_chunks": X, "tagged_chunks": Y, "untagged_chunks": Z, "tagging_progress": 95.5 }`

---

## **7. SDTM (Streaming Domain Topic Modeling)**

Base Path: `/api/v1/sdtm`

### **Get SDTM Statistics**
*   **Endpoint:** `GET /{kb_id}/stats`
*   **Description:** Retrieves detailed quality and progress metrics for the knowledge base's tag dictionary and document annotations.
*   **Response (200):** `SDTMStatsResponse`

### **Start Tag Dictionary Optimization Job**
*   **Endpoint:** `POST /{kb_id}/optimize`
*   **Description:** Starts an asynchronous job to optimize the tag dictionary and re-annotate documents based on the SDTM engine's analysis.
*   **Request Body:** `TagDictionaryOptimizeRequest`
    ```json
    {
      "mode": "edit", // "edit", "annotate", or "shadow"
      "batch_size": 10,
      "auto_apply": true,
      "max_iterations": 50
    }
    ```
*   **Response (200):** `{ "success": true, "message": "SDTM任务已启动", "job_id": "job_uuid" }`

### **Get SDTM Job Status**
*   **Endpoint:** `GET /{kb_id}/jobs/{job_id}`
*   **Description:** Retrieves the status and results of a specific SDTM job.
*   **Response (200):** `SDTMJob` schema

### **List SDTM Jobs**
*   **Endpoint:** `GET /{kb_id}/jobs`
*   **Description:** Lists all SDTM jobs for a knowledge base.
*   **Response (200):** List of `SDTMJob` schemas

---

## **8. Screenshots**

Base Path: `/screenshots`

### **Get Screenshot Info**
*   **Endpoint:** `GET /{screenshot_id}/info`
*   **Description:** Retrieves metadata for a specific page screenshot.
*   **Response (200):** `ScreenshotInfo`

### **Get Screenshot Image**
*   **Endpoint:** `GET /{screenshot_id}/image`
*   **Description:** Returns the PNG image file for a specific screenshot.
*   **Response (200):** `image/png`

### **Get All Screenshots for a Document**
*   **Endpoint:** `GET /document/{document_id}`
*   **Description:** Retrieves metadata for all page screenshots associated with a document.
*   **Response (200):** List of `ScreenshotInfo`

### **Batch Get Screenshot Info**
*   **Endpoint:** `POST /batch`
*   **Description:** Retrieves metadata for multiple screenshots in a single request.
*   **Request Body:** `{"screenshot_ids": ["id1", "id2"]}`
*   **Response (200):** List of `ScreenshotInfo`
