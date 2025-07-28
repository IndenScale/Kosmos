import apiClient from './apiClient';

export interface UpdateProfileRequest {
  username?: string;
  email?: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export const userService = {
  async updateProfile(data: UpdateProfileRequest) {
    const response = await apiClient.put('/api/v1/users/me', data);
    return response.data;
  },

  async changePassword(data: ChangePasswordRequest) {
    const response = await apiClient.post('/api/v1/users/me/change-password', data);
    return response.data;
  },

  async deactivateAccount() {
    const response = await apiClient.delete('/api/v1/users/me');
    return response.data;
  }
};