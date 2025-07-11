// frontend/src/services/auth.ts:
import { LoginRequest, RegisterRequest, AuthResponse, User } from '../types/auth';
import apiClient from './apiClient';

export const authService = {
  async login(data: LoginRequest): Promise<AuthResponse> {
    // 使用 FormData 格式发送请求，符合 OAuth2PasswordRequestForm 要求
    const formData = new FormData();
    formData.append('username', data.username);
    formData.append('password', data.password);

    const response = await apiClient.post('/api/v1/auth/token', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  async register(data: RegisterRequest): Promise<AuthResponse> {
    const response = await apiClient.post('/api/v1/auth/register', data);
    return response.data;
  },

  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get('/api/v1/users/me');
    return response.data;
  },

  logout() {
    localStorage.removeItem('access_token');
  }
};
