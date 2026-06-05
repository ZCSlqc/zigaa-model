import axios from 'axios'
import router from '../router'

const DEFAULT_TIMEOUT = 30000

const client = axios.create({
  baseURL: '/api',
  timeout: DEFAULT_TIMEOUT,
})

// 请求拦截器：附加 JWT
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：401 跳转登录
client.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(error)
  }
)

export default client
