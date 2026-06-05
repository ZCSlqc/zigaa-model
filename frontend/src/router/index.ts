import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: () => useAuthStore().isLoggedIn ? '/project' : '/login',
    },
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/user',
      name: 'UserCenter',
      component: () => import('../views/UserCenterView.vue'),
    },
    {
      path: '/user/password',
      name: 'Password',
      component: () => import('../views/PasswordView.vue'),
    },
    {
      path: '/project',
      name: 'Project',
      component: () => import('../views/ProjectView.vue'),
    },
    {
      path: '/model/:modelId',
      name: 'ModelDetail',
      component: () => import('../views/ModelDetailView.vue'),
    },
    {
      path: '/annotate/:modelId',
      name: 'Annotate',
      component: () => import('../views/AnnotateView.vue'),
    },
    {
      path: '/preview/:modelId',
      name: 'Preview',
      component: () => import('../views/PreviewView.vue'),
    },
    {
      path: '/guide',
      name: 'Guide',
      component: () => import('../views/GuideView.vue'),
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('../views/AdminPanel.vue'),
      meta: { requiresAdmin: true },
    },
  ],
})

// 导航守卫
router.beforeEach((to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    if (auth.isLoggedIn) return '/project'
    return true
  }

  if (to.meta.requiresAdmin) {
    if (!auth.isLoggedIn) return '/login'
    if (!auth.isAdmin) return '/project'
    return true
  }

  if (!auth.isLoggedIn) return '/login'
  return true
})

export default router
