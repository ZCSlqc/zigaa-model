<template>
  <AppLayout>
    <div class="admin-panel">
      <h2>管理后台</h2>
      <el-tabs v-model="activeTab">
        <!-- 用户管理 -->
        <el-tab-pane label="用户管理" name="users">
          <div class="admin-toolbar">
            <el-button type="primary" @click="showCreateUser = true">新建用户</el-button>
            <el-input
              v-model="userSearch"
              placeholder="搜索用户名"
              clearable
              style="width: 200px; margin-left: auto"
              @input="onUserSearch"
            />
          </div>
          <el-table :data="users" border stripe>
            <el-table-column prop="username" label="用户名" width="120" />
            <el-table-column label="权限" width="100">
              <template #default="{ row }">
                <el-tag :type="roleTagType(row.role)" size="small">
                  {{ roleLabel(row.role) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="project_count" label="项目数量" width="100" />
            <el-table-column :formatter="(row: any) => formatDate(row.created_at)" label="创建时间" width="160" />
            <el-table-column label="操作" min-width="280">
              <template #default="{ row }">
                <el-button size="small" @click="showResetPassword(row)">重置密码</el-button>
                <el-button size="small" class="btn-role-change" @click="showChangeRole(row)">权限修改</el-button>
                <el-button type="danger" size="small" :loading="isLoading('delete-user-' + row.id)" @click="confirmDeleteUser(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 项目管理 -->
        <el-tab-pane label="项目管理" name="projects">
          <div class="admin-toolbar">
            <div class="search-group">
              <el-input
                v-model="projectNameSearch"
                placeholder="搜索项目名称"
                clearable
                style="width: 180px"
                @input="onProjectSearch"
              />
              <el-input
                v-model="ownerNameSearch"
                placeholder="搜索所属用户"
                clearable
                style="width: 160px; margin-left: 8px"
                @input="onProjectSearch"
              />
            </div>
          </div>
          <el-table :data="allProjects" border stripe>
            <el-table-column prop="name" label="项目名称" width="140" />
            <el-table-column prop="owner_name" label="所属用户" width="120" />
            <el-table-column prop="description" label="描述" min-width="200" />
            <el-table-column :formatter="(row: any) => formatDate(row.created_at)" label="创建时间" width="180" />
            <el-table-column label="操作" min-width="200">
              <template #default="{ row }">
                <el-button size="small" @click="showModelsDialog(row)">模型列表</el-button>
                <el-button type="danger" size="small" :loading="isLoading('delete-project-' + row.id)" @click="confirmDeleteProject(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 模型子表格 -->
          <el-dialog
            v-model="showModelDialog"
            :title="`项目「${selectedProject?.name}」的模型（${selectedProject?.models?.length || 0}）`"
            width="700px"
          >
            <el-table :data="selectedProject?.models || []" border stripe size="small">
              <el-table-column prop="name" label="模型名称" width="150" />
              <el-table-column prop="description" label="描述" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="dataStatusTagType(resolveDataStatus(row.status))">{{ dataStatusDisplayText(resolveDataStatus(row.status)) }}</el-tag>
                  <el-tag size="small" :type="trainingStatusTagType(resolveTrainingStatus(row.status))">{{ trainingStatusDisplayText(resolveTrainingStatus(row.status)) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column :formatter="(row: any) => formatDate(row.created_at)" label="创建时间" width="200" />
            </el-table>
          </el-dialog>
        </el-tab-pane>

      </el-tabs>

      <!-- 新建用户对话框 -->
      <el-dialog v-model="showCreateUser" title="新建用户" width="400px">
        <el-form @submit.prevent="handleCreateUser">
          <el-form-item label="用户名">
            <el-input v-model="newUser.username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="newUser.password" type="password" />
          </el-form-item>
          <el-form-item label="权限">
            <el-select v-model="newUser.role">
              <el-option label="普通用户" value="user" />
              <el-option label="高级用户" value="advanced" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showCreateUser = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleCreateUser">创建</el-button>
        </template>
      </el-dialog>

      <!-- 重置密码对话框 -->
      <el-dialog v-model="showResetPwd" title="重置密码" width="400px">
        <el-form @submit.prevent="handleResetPwd">
          <el-form-item label="新用户密码">
            <el-input v-model="resetPwdForm.password" type="password" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showResetPwd = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleResetPwd">确认</el-button>
        </template>
      </el-dialog>

      <!-- 权限修改对话框 -->
      <el-dialog v-model="showRoleDialog" title="权限修改" width="400px">
        <el-form @submit.prevent="handleChangeRole">
          <el-form-item label="权限">
            <el-select v-model="roleForm.role">
              <el-option label="普通用户" value="user" />
              <el-option label="高级用户" value="advanced" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showRoleDialog = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleChangeRole">确认</el-button>
        </template>
      </el-dialog>

    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import AppLayout from '../components/Layout/AppLayout.vue'
import { useSingleLoading } from '../composables/useDelayedLoading'
import { useDebounceSearch } from '../composables/useDebounce'
import { formatDate } from '../utils/format'
import { resolveDataStatus, dataStatusTagType, dataStatusDisplayText, resolveTrainingStatus, trainingStatusTagType, trainingStatusDisplayText, roleLabel, roleTagType } from '../utils/model-status'
import {
  listUsers, createUser, updateUserRole, resetPassword, deleteUser,
  listAllProjects, adminDeleteProject,
} from '../api/admin'

const activeTab = ref('users')
const loading = ref(false)
const { startLoading, stopLoading, isLoading } = useSingleLoading()
const users = ref<any[]>([])
const allProjects = ref<any[]>([])

// 用户搜索
const userSearch = ref('')
const onUserSearch = useDebounceSearch(() => fetchUsers())

// 项目搜索
const projectNameSearch = ref('')
const ownerNameSearch = ref('')
const onProjectSearch = useDebounceSearch(() => fetchProjects())

// 模型弹窗
const showModelDialog = ref(false)
const selectedProject = ref<any>(null)

function showModelsDialog(project: any) {
  selectedProject.value = project
  showModelDialog.value = true
}

const showCreateUser = ref(false)
const newUser = ref({ username: '', password: '', role: 'user' })

const showResetPwd = ref(false)
const resetPwdForm = ref({ userId: '', password: '' })

const showRoleDialog = ref(false)
const roleForm = ref({ userId: '', role: 'user' })

async function fetchUsers() {
  const res = await listUsers(userSearch.value)
  users.value = res.data
}

async function fetchProjects() {
  const res = await listAllProjects(projectNameSearch.value, ownerNameSearch.value)
  allProjects.value = res.data
}

onMounted(() => {
  fetchUsers()
  fetchProjects()
})

watch(activeTab, (tab) => {
  if (tab === 'users') fetchUsers()
  if (tab === 'projects') fetchProjects()
})

async function handleCreateUser() {
  if (!newUser.value.username || !newUser.value.password) {
    ElMessage.warning('请填写完整')
    return
  }
  startLoading('create-user')
  loading.value = true
  try {
    await createUser(newUser.value.username, newUser.value.password, newUser.value.role)
    showCreateUser.value = false
    newUser.value = { username: '', password: '', role: 'user' }
    ElMessage.success('用户创建成功')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    stopLoading()
    loading.value = false
  }
}

function showResetPassword(row: any) {
  resetPwdForm.value = { userId: row.id, password: '' }
  showResetPwd.value = true
}

async function handleResetPwd() {
  if (!resetPwdForm.value.password) {
    ElMessage.warning('请输入密码')
    return
  }
  startLoading('reset-pwd')
  loading.value = true
  try {
    await resetPassword(resetPwdForm.value.userId, resetPwdForm.value.password)
    showResetPwd.value = false
    ElMessage.success('密码重置成功')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '重置失败')
  } finally {
    stopLoading()
    loading.value = false
  }
}

function showChangeRole(row: any) {
  roleForm.value = { userId: row.id, role: row.role }
  showRoleDialog.value = true
}

async function handleChangeRole() {
  startLoading('change-role')
  loading.value = true
  try {
    await updateUserRole(roleForm.value.userId, roleForm.value.role)
    showRoleDialog.value = false
    ElMessage.success('权限更新成功')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '更新失败')
  } finally {
    stopLoading()
    loading.value = false
  }
}

async function confirmDeleteUser(row: any) {
  await ElMessageBox.confirm(`确定删除用户 "${row.username}"？`, '确认删除', { type: 'warning' })
  startLoading('delete-user-' + row.id)
  try {
    await deleteUser(row.id)
    ElMessage.success('用户已删除')
    fetchUsers()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    stopLoading()
  }
}

async function confirmDeleteProject(row: any) {
  await ElMessageBox.confirm(`确定删除项目 "${row.name}"？`, '确认删除', { type: 'warning' })
  startLoading('delete-project-' + row.id)
  try {
    await adminDeleteProject(row.id)
    ElMessage.success('项目已删除')
    fetchProjects()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  } finally {
    stopLoading()
  }
}
</script>

<style scoped lang="scss">
.admin-panel {
  width: 100%;
}

.admin-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: var(--spacing-md);
}

.btn-role-change {
  color: #f56c6c !important;
}
</style>
