-- 为 kb_documents 表添加 last_ingest_time 字段
ALTER TABLE kb_documents ADD COLUMN last_ingest_time DATETIME;

-- 为 knowledge_bases 表添加 last_tag_directory_update_time 字段
ALTER TABLE knowledge_bases ADD COLUMN last_tag_directory_update_time DATETIME;

-- 为现有记录设置默认值（可选）
UPDATE kb_documents SET last_ingest_time = upload_at WHERE last_ingest_time IS NULL;
UPDATE knowledge_bases SET last_tag_directory_update_time = created_at WHERE last_tag_directory_update_time IS NULL;