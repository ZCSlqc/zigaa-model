<template>
  <AppLayout>
    <div class="user-center">
      <h2>个人中心</h2>

      <!-- 我的信息 -->
      <h3 class="section-title">我的信息</h3>
      <el-table :data="[userInfo]" border stripe>
        <el-table-column width="140">
          <template #header>用户名</template>
          <template #default>
            {{ userInfo.username }}
          </template>
        </el-table-column>
        <el-table-column width="120">
          <template #header>权限</template>
          <template #default>
            <el-tag :type="roleTagType(userInfo.role)" size="small">
              {{ roleLabel(userInfo.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column min-width="200" label="项目数量">
          <template #default>
            {{ userInfo.project_count }}
          </template>
        </el-table-column>
        <el-table-column width="180" label="创建时间">
          <template #default>
            {{ formatDate(userInfo.created_at) }}
          </template>
        </el-table-column>
        <el-table-column width="120" label="操作">
          <template #default>
            <router-link to="/user/password">
              <el-button size="small">修改密码</el-button>
            </router-link>
          </template>
        </el-table-column>
      </el-table>

      <!-- 我的项目 -->
      <h3 class="section-title">我的项目</h3>
      <el-table :data="projects" border stripe v-loading="projectsLoading">
        <el-table-column width="140" prop="name" label="项目名称" />
        <el-table-column width="120" label="模型数量">
          <template #default="{ row }">
            {{ row.models?.length || 0 }}
          </template>
        </el-table-column>
        <el-table-column min-width="200" prop="description" label="描述" />
        <el-table-column width="180" label="创建时间">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column width="120" label="操作">
          <template #default="{ row }">
            <el-button size="small" @click="router.push(`/project?select=${row.id}`)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppLayout from '../components/Layout/AppLayout.vue'
import { formatDate } from '../utils/format'
import { roleLabel, roleTagType } from '../utils/model-status'
import { getMe } from '../api/auth'
import { listProjects } from '../api/project'

const router = useRouter()

const userInfo = ref({
  username: '',
  role: '',
  user_id: '',
  created_at: '',
  project_count: 0,
})

const projects = ref<any[]>([])
const projectsLoading = ref(false)
async function fetchMe() {
  const res = await getMe()
  userInfo.value = res.data
}

async function fetchProjects() {
  projectsLoading.value = true
  try {
    const res = await listProjects()
    projects.value = res.data.items || res.data || []
  } finally {
    projectsLoading.value = false
  }
}

onMounted(() => {
  fetchMe()
  fetchProjects()
})
</script>

<style scoped lang="scss">
.user-center {
  width: 100%;
}

.section-title {
  margin: 24px 0 12px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
</style>
