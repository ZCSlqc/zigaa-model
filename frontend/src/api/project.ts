import client from './client'

export function listProjects() {
  return client.get('/projects/')
}

export function createProject(name: string, description: string) {
  return client.post('/projects/', { name, description })
}

export function updateProject(id: string, name?: string, description?: string) {
  return client.put(`/projects/${id}`, { name, description })
}

export function deleteProject(id: string) {
  return client.delete(`/projects/${id}`)
}
