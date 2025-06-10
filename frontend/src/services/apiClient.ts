// src/services/apiClient.ts
import axios from 'axios';
import { API_BASE_URL } from './config';

// 创建axios实例
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  withCredentials: true, // 添加这行以支持跨域凭证
});

// 请求拦截器 - 添加认证token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // 确保Content-Type正确设置
  if (!config.headers['Content-Type']) {
    config.headers['Content-Type'] = 'application/json';
  }
  return config;
});

// 响应拦截器 - 处理错误
apiClient.interceptors.response.use(
  (response) => {
    // 处理204状态码 - 删除成功但无内容返回
    if (response.status === 204) {
      return { ...response, data: { success: true } };
    }
    // 处理202状态码 - 异步任务已接受
    if (response.status === 202) {
      return { ...response, data: { success: true } }; // 202通常有响应体，直接返回
    }
    return response;
  },
  (error) => {
    console.error('API请求错误:', error);

    // 处理超时错误
    if (error.code === 'ECONNABORTED' && error.message.includes('timeout')) {
      console.warn('请求超时，但操作可能已成功完成');
      // 对于删除操作，超时不一定意味着失败
      if (error.config?.method === 'delete') {
        return Promise.resolve({
          data: { success: true, message: '删除请求已发送，请稍后刷新页面确认结果' },
          status: 204,
          statusText: 'No Content'
        });
      }
      // 对于摄取操作，超时也可能成功
      if (error.config?.url?.includes('/ingest')) {
        return Promise.resolve({
          data: { success: true, message: '摄取任务已启动，请稍后查看任务状态' },
          status: 202,
          statusText: 'Accepted'
        });
      }
    }

    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
