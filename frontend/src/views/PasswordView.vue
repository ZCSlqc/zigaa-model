<template>
  <AppLayout>
    <div class="password-page">
      <div class="password-card">
        <h2 class="password-title">修改密码</h2>
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          @submit.prevent="handleChange"
        >
          <el-form-item label="原密码" prop="old">
            <el-input v-model="form.old" type="password" show-password size="large" />
          </el-form-item>
          <el-form-item label="新密码" prop="new">
            <el-input v-model="form.new" type="password" show-password size="large" />
          </el-form-item>
          <el-form-item label="确认密码" prop="confirm">
            <el-input v-model="form.confirm" type="password" show-password size="large" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" size="large" :loading="loading" class="submit-btn" native-type="submit">
              确认修改
            </el-button>
          </el-form-item>
        </el-form>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppLayout from '../components/Layout/AppLayout.vue'
import { changePassword } from '../api/auth'

const router = useRouter()
const loading = ref(false)
const formRef = ref()
const form = reactive({ old: '', new: '', confirm: '' })

const validateConfirm = (_rule: any, value: string, callback: any) => {
  if (value !== form.new) {
    callback(new Error('两次输入不一致'))
  } else {
    callback()
  }
}

const rules = {
  old: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  new: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少6位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleChange() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await changePassword(form.old, form.new)
    ElMessage.success('密码修改成功，请重新登录')
    router.push('/login')
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.password-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 60px);
  padding: var(--spacing-lg);
}

.password-card {
  width: 420px;
  padding: 40px;
  background: var(--bg-card);
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.password-title {
  text-align: center;
  margin: 0 0 32px;
  font-size: 20px;
  color: var(--text-primary);
}

.submit-btn {
  width: 100%;
}
</style>
