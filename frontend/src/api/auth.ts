import client from './client'

export function login(username: string, password: string) {
  return client.post('/auth/login', { username, password })
}

export function logout() {
  return client.post('/auth/logout')
}

export function getMe() {
  return client.get('/auth/me')
}

export function changePassword(oldPassword: string, newPassword: string) {
  return client.post('/auth/change-password', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}
