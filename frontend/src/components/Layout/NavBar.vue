<template>
  <div class="nav-bar">
    <div class="nav-brand" @click="router.push('/project')">
      <span>ZIGAA 大模型云平台</span>
    </div>
    <div class="nav-links">
      <router-link to="/project" class="nav-link">项目</router-link>
      <router-link to="/guide" class="nav-link">教程</router-link>
      <router-link v-if="auth.isAdmin" to="/admin" class="nav-link">管理</router-link>
    </div>
    <div class="nav-user">
      <el-dropdown @command="handleCommand">
        <span class="user-trigger">
          {{ auth.username }}
          <el-tag size="small" :type="roleTagType(auth.role)">{{ roleLabel(auth.role) }}</el-tag>
          <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="user">个人中心</el-dropdown-item>
            <el-dropdown-item command="password">修改密码</el-dropdown-item>
            <el-dropdown-item command="logout" divided>登出</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '../../stores/auth'
import { logout } from '../../api/auth'
import { roleLabel, roleTagType } from '../../utils/model-status'

const router = useRouter()
const auth = useAuthStore()

async function handleCommand(command: string) {
  switch (command) {
    case 'user':
      router.push('/user')
      break
    case 'password':
      router.push('/user/password')
      break
    case 'logout':
      try {
        await logout().catch(() => {})
      } finally {
        auth.clearAuth()
      }
      ElMessage.success('已登出')
      await router.replace('/login')
      break
  }
}
</script>

<style scoped lang="scss">
.nav-bar {
  display: flex;
  align-items: center;
  height: var(--spacing-xl);
  padding: 0 var(--spacing-lg);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  box-shadow: var(--shadow-sm);
}

.nav-brand {
  cursor: pointer;
  font-weight: 600;
  font-size: 16px;
  color: var(--color-primary);
  margin-right: auto;
}

.nav-links {
  display: flex;
  gap: var(--spacing-lg);
  margin-right: var(--spacing-lg);
}

.nav-link {
  text-decoration: none;
  color: var(--text-regular);
  font-size: 14px;
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: all 0.2s;

  &:hover,
  &.router-link-exact-active {
    color: var(--color-primary);
    background: var(--bg-hover);
  }
}

.user-trigger {
  cursor: pointer;
  color: var(--text-regular);
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
