import client from './client'

export function listUsers(search: string = '') {
  return client.get('/admin/users', { params: { search } })
}

export function createUser(username: string, password: string, role: string) {
  return client.post('/admin/users', { username, password, role })
}

export function updateUserRole(userId: string, role: string) {
  return client.put(`/admin/users/${userId}`, { role })
}

export function resetPassword(userId: string, password: string) {
  return client.post(`/admin/users/${userId}/reset-password`, { password })
}

export function deleteUser(userId: string) {
  return client.delete(`/admin/users/${userId}`)
}

export function listAllProjects(projectName: string = '', ownerName: string = '') {
  return client.get('/admin/projects', {
    params: { project_name: projectName, owner_name: ownerName },
  })
}

export function adminDeleteProject(projectId: string) {
  return client.delete(`/admin/projects/${projectId}`)
}
