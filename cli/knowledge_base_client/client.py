"""
全新的、基于类的、有状态的Kosmos API客户端。
"""
import requests
import json
import sys
import os
from urllib.parse import urljoin
from . import auth

# --- 全局配置 ---
KOSMOS_API_BASE_URL = os.getenv("KOSMOS_API_URL", "http://127.0.0.1:8011/api/v1/")
KOSMOS_API_KEY = os.getenv("KOSMOS_API_KEY")

def _handle_api_error(e: requests.exceptions.RequestException):
    """统一的API错误处理器。"""
    print(f"错误: API请求失败 - {e}", file=sys.stderr)
    if e.response is not None:
        try:
            response_data = e.response.json()
            if isinstance(response_data, dict):
                detail = response_data.get("detail", e.response.text)
            else:
                detail = str(response_data)
            if e.response.status_code == 401:
                detail += "\n提示: 您的会话可能已过期，请尝试 'kosmos login'。"
            print(f"响应 ({e.response.status_code}): {detail}", file=sys.stderr)
        except json.JSONDecodeError:
            print(f"响应 ({e.response.status_code}): {e.response.text}", file=sys.stderr)
    sys.exit(1)

class KosmosClient:
    """用于与Kosmos API交互的有状态客户端。"""

    def __init__(self, skip_auth=False):
        self._session = requests.Session()
        self._access_token = None
        self._skip_auth = skip_auth
        if not skip_auth:
            self._load_credentials()

    def _load_credentials(self):
        """
        加载凭证，优先使用API Key，其次是本地会话Token。
        并处理Token的自动刷新。
        """
        if KOSMOS_API_KEY:
            self._access_token = KOSMOS_API_KEY
            return

        token_data = auth.load_tokens()
        if not token_data:
            return

        if auth.is_token_expired(token_data):
            print("会话已过期，正在尝试刷新...", file=sys.stderr)
            try:
                self._refresh_token(token_data['refresh_token'])
            except SystemExit:
                self._access_token = None
        else:
            self._access_token = token_data['access_token']

    def _refresh_token(self, refresh_token):
        """使用Refresh Token获取新的Access Token。"""
        refresh_url = urljoin(KOSMOS_API_BASE_URL, "auth/token/refresh")
        try:
            response = self._session.post(refresh_url, json={"refresh_token": refresh_token})
            response.raise_for_status()
            new_token_data = response.json()
            self._access_token = new_token_data['access_token']
            
            auth.save_tokens(self._access_token, refresh_token)
            print("会话刷新成功。", file=sys.stderr)
        except requests.exceptions.RequestException as e:
            _handle_api_error(e)

    def _get_auth_header(self):
        """获取认证头，如果未认证则抛出错误。"""
        if self._skip_auth:
            return {}
        if not self._access_token:
            print("错误: 未进行身份验证。请先运行 'kosmos login'。", file=sys.stderr)
            sys.exit(1)
        return {"Authorization": f"Bearer {self._access_token}"}

    def get_raw_token(self):
        """返回原始的 access token 字符串。"""
        if not self._access_token:
            print("错误: 未进行身份验证。请先运行 'kosmos login'。", file=sys.stderr)
            sys.exit(1)
        return self._access_token

    def _request(self, method, endpoint, **kwargs):
        """执行已认证请求的通用包装器。"""
        url = urljoin(KOSMOS_API_BASE_URL, endpoint)
        headers = self._get_auth_header()
        if 'json' in kwargs:
            headers['Content-Type'] = 'application/json'
        
        try:
            response = self._session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json() if response.status_code != 204 else None
        except requests.exceptions.RequestException as e:
            _handle_api_error(e)

    # --- 登录 (特殊方法，不使用标准请求流程) ---
    def login(self, username, password):
        """使用用户名/密码登录以获取Tokens。"""
        login_url = urljoin(KOSMOS_API_BASE_URL, "auth/token")
        payload = {"username": username, "password": password}
        try:
            response = self._session.post(login_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            
            if not access_token or not refresh_token:
                raise KeyError()

            auth.save_tokens(access_token, refresh_token)
            print("登录成功，凭证已保存。")
            return token_data
        except requests.exceptions.RequestException as e:
            _handle_api_error(e)
        except KeyError:
            print(f"错误：登录响应无效。", file=sys.stderr)
            sys.exit(1)

    # --- API 方法 (逐步迁移) ---
    
    def search(self, ks_id, query, **filters):
        """(已迁移) 执行搜索查询。"""
        payload = {
            "query": query, "knowledge_space_id": ks_id, "top_k": filters.pop('top_k', 10),
            "filters": filters, "boosters": filters.pop('boosters', []), "max_content_length": 500,
            "detailed": True
        }
        return self._request("POST", "search/", json=payload)

    # --- Knowledge Space Methods ---
    
    def list_knowledge_spaces(self, **params):
        """获取用户所属的知识空间列表。"""
        return self._request("GET", "knowledge-spaces/", params=params)

    def create_knowledge_space(self, name: str):
        """创建一个新的知识空间。"""
        payload = {"name": name}
        return self._request("POST", "knowledge-spaces/", json=payload)

    def update_knowledge_space(self, ks_id: str, new_name: str):
        """更新一个知识空间的名称。"""
        payload = {"name": new_name}
        return self._request("PATCH", f"knowledge-spaces/{ks_id}", json=payload)

    def delete_knowledge_space(self, ks_id: str):
        """删除一个知识空间。"""
        return self._request("DELETE", f"knowledge-spaces/{ks_id}")

    def get_documents(self, ks_id: str, status: str = None, filename: str = None, extension: str = None, cursor: str = None, page_size: int = 100):
        """
        从知识空间检索分页的文档列表，并可选择应用筛选条件。
        """
        endpoint = f"knowledge-spaces/{ks_id}/documents"
        params = {
            "status": status,
            "filename": filename,
            "extension": extension,
            "cursor": cursor,
            "page_size": page_size,
        }
        valid_params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", endpoint, params=valid_params)

    def list_assets(self, ks_id: str = None, doc_id: str = None, asset_type: str = None, status: str = None, limit: int = 20, cursor: str = None):
        """获取资产列表，并可选择应用筛选条件。"""
        endpoint = "assets/"
        params = {
            "knowledge_space_id": ks_id,
            "document_id": doc_id,
            "asset_type": asset_type,
            "analysis_status": status,
            "limit": limit,
            "cursor": cursor,
        }
        valid_params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", endpoint, params=valid_params)

    def get_asset_analysis_in_doc_context(self, doc_id: str, asset_id: str):
        """在文档上下文中获取资产分析结果。"""
        endpoint = f"documents/{doc_id}/assets/{asset_id}/analysis"
        return self._request("GET", endpoint)

    def read(self, doc_ref: str, start: any, end: any, max_lines: int, max_chars: int, preserve_integrity: bool, ks_id: str = None):
        """读取文档的特定部分，支持UUID或书签引用。"""
        endpoint = f"read/{doc_ref}"
        params = {
            "start": start,
            "end": end,
            "max_lines": max_lines,
            "max_chars": max_chars,
            "preserve_integrity": preserve_integrity,
            "knowledge_space_id": ks_id,
        }
        valid_params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", endpoint, params=valid_params)

    def multi_document_grep(self, pattern: str, knowledge_space_id: str = None, document_ids: list = None,
                            doc_ext: str = None, case_sensitive: bool = False, max_matches_per_doc: int = None,
                            context_lines_before: int = 0, context_lines_after: int = 0):
        """执行多文档grep（正则表达式搜索）API调用。"""
        endpoint = "grep/"
        
        scope = {}
        if knowledge_space_id:
            scope["knowledge_space_id"] = knowledge_space_id
        elif document_ids:
            # 确保document_ids始终是一个列表，即使只有一个元素
            if isinstance(document_ids, str):
                document_ids = [document_ids]
            elif not isinstance(document_ids, list):
                document_ids = list(document_ids) if document_ids else []
            scope["document_ids"] = document_ids

        if doc_ext:
            scope["doc_ext"] = doc_ext

        payload = {
            "pattern": pattern,
            "case_sensitive": case_sensitive,
            "scope": scope,
            "max_matches_per_doc": max_matches_per_doc,
            "context_lines_before": context_lines_before,
            "context_lines_after": context_lines_after
        }
        
        # Remove None values for optional fields that should not be sent if absent
        if payload.get("max_matches_per_doc") is None:
            del payload["max_matches_per_doc"]

        valid_payload = {k: v for k, v in payload.items() if v is not None}
        
        return self._request("POST", endpoint, json=valid_payload)

    # ... 其他所有API方法将在此处逐步添加 ...

    # --- Job Methods ---
    def list_jobs(self, **params):
        """列出并过滤作业。"""
        valid_params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", "jobs/", params=valid_params)

    def abort_jobs(self, document_ids: list, job_type: str = None):
        """中止与特定文档关联的作业。"""
        payload = {"document_ids": document_ids}
        if job_type:
            payload["job_type"] = job_type
        return self._request("POST", "jobs/abort-by-documents", json=payload)

    def delete_jobs(self, job_ids: list, force: bool = False):
        """按ID批量删除作业。"""
        payload = {"job_ids": job_ids, "force": force}
        return self._request("DELETE", "jobs/", json=payload)

    # --- Ingestion Methods ---
    def ingest_document(self, ks_id: str, file_path: str, **params):
        """使用新的 ingestion 端点上传文档。"""
        endpoint = "ingest/upload"
        
        # 清理 params 字典，只保留有效参数
        valid_params = {k: v for k, v in params.items() if v is not None}
        valid_params["knowledge_space_id"] = ks_id

        # 获取文件名，如果指定了 --filename 参数则使用它，否则使用原始文件名
        file_name = valid_params.get("filename", os.path.basename(file_path))
        # 从 params 中移除 filename 参数，因为它不是 API 参数
        valid_params.pop("filename", None)

        with open(file_path, 'rb') as f:
            files = {'file': (file_name, f)}
            # 注意：对于文件上传，我们不设置 Content-Type header，requests 会自动处理
            url = urljoin(KOSMOS_API_BASE_URL, endpoint)
            headers = self._get_auth_header()
            
            try:
                response = self._session.post(url, headers=headers, params=valid_params, files=files)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                _handle_api_error(e)

    def reingest_documents(self, document_ids: list = None, knowledge_space_id: str = None, **params):
        """Triggers re-ingestion for existing documents."""
        endpoint = "ingest/re-ingest"
        
        payload = {
            "document_ids": document_ids,
            "knowledge_space_id": knowledge_space_id,
        }
        # Add optional strategy params
        payload.update(params)

        # Clean up None values
        valid_payload = {k: v for k, v in payload.items() if v is not None}

        return self._request("POST", endpoint, json=valid_payload)

    def get_document_ingestion_status(self, ks_id: str = None, doc_id: str = None):
        """获取文档摄入状态。"""
        if ks_id:
            endpoint = f"knowledge-spaces/{ks_id}/ingestion-status"
        elif doc_id:
            endpoint = f"documents/{doc_id}/ingestion-status"
        else:
            raise ValueError("必须提供知识空间ID或文档ID")
        
        return self._request("GET", endpoint)

    def delete_document(self, doc_id: str):
        """删除指定文档。"""
        endpoint = f"documents/{doc_id}"
        return self._request("DELETE", endpoint)

    # --- Bookmark Methods ---
    def list_bookmarks(self, knowledge_space_id: str):
        """列出知识空间中的书签。"""
        params = {"knowledge_space_id": knowledge_space_id}
        return self._request("GET", "bookmarks/", params=params)

    def create_bookmark(self, bookmark_data: dict):
        """创建新书签。"""
        return self._request("POST", "bookmarks/", json=bookmark_data)

    def delete_bookmark(self, bookmark_id: str):
        """删除书签。"""
        return self._request("DELETE", f"bookmarks/{bookmark_id}")

    # --- Domain Event Methods ---
    def list_events(self, **params):
        """列出并过滤领域事件。"""
        # 清理 params 字典，移除值为 None 的键
        valid_params = {k: v for k, v in params.items() if v is not None}
        return self._request("GET", "events/", params=valid_params)
    
    # --- User Management Methods ---
    def register_user(self, username: str, email: str, display_name: str, password: str, role: str = "user"):
        """注册新用户。"""
        register_data = {
            "username": username,
            "email": email,
            "display_name": display_name,
            "password": password
        }
        return self._request("POST", "users/", json=register_data)

    # --- Credential Management Methods ---
    def list_credentials(self):
        """获取用户的凭证列表。"""
        return self._request("GET", "credentials/")

    def create_credential(self, credential_type: str, model_family: str, 
                         provider: str, model_name: str, base_url: str, api_key: str, 
                         is_default: bool = False):
        """创建新的凭证。"""
        credential_data = {
            "credential_type": credential_type,
            "model_family": model_family,
            "provider": provider,
            "model_name": model_name,
            "base_url": base_url,
            "api_key": api_key,
            "is_default": is_default
        }
        return self._request("POST", "credentials/", json=credential_data)

    def update_credential(self, credential_id: str, model_name: str = None, 
                         base_url: str = None, api_key: str = None, is_default: bool = None):
        """更新现有凭证。"""
        update_data = {}
        if model_name is not None:
            update_data["model_name"] = model_name
        if base_url is not None:
            update_data["base_url"] = base_url
        if api_key is not None:
            update_data["api_key"] = api_key
        if is_default is not None:
            update_data["is_default"] = is_default
        
        return self._request("PUT", f"credentials/{credential_id}", json=update_data)

    def delete_credential(self, credential_id: str):
        """删除指定的凭证。"""
        return self._request("DELETE", f"credentials/{credential_id}")

    def get_credential(self, credential_id: str):
        """获取指定凭证的详细信息。"""
        return self._request("GET", f"credentials/{credential_id}")

    def set_default_credential(self, credential_id: str):
        """设置默认凭证。"""
        return self._request("PATCH", f"credentials/{credential_id}/set-default")
