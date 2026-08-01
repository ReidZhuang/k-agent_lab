<template>
  <div class="login-page">
    <div class="login-card">
      <div class="logo">📊</div>
      <h2>股神的秘密</h2>
      <p class="subtitle">Stock Report System</p>
      <el-form @submit.prevent="handleLogin" style="text-align:left;" label-width="70px">
        <el-form-item label="用户名" style="margin-bottom:22px;">
          <el-input v-model="username" placeholder="请输入用户名" size="large" />
        </el-form-item>
        <el-form-item label="密码" style="margin-bottom:24px;">
          <el-input v-model="password" type="password" placeholder="请输入密码" size="large" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width:100%;margin-top:8px;" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </el-form>
      <p class="footer-text">仅供授权用户使用</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api/index.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const loading = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const data = await login(username.value, password.value)
    localStorage.setItem('token', data.token)
    localStorage.setItem('user', JSON.stringify({ id: data.user_id, name: data.username }))
    ElMessage.success(`欢迎回来，${data.username}！`)
    router.push('/main')
  } catch (e) {
    ElMessage.error('用户名或密码错误')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--wood-50) 0%, var(--wood-100) 100%);
  padding: 20px;
}
.login-card {
  background: #fff;
  border-radius: 16px;
  padding: 48px 40px 40px;
  width: 100%;
  max-width: 420px;
  box-shadow: 0 1px 4px rgba(74,55,40,0.06), 0 2px 12px rgba(74,55,40,0.04);
  text-align: center;
}
.login-card .logo {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--wood-400), var(--wood-600));
  margin: 0 auto 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 28px;
}
.login-card h2 { margin-bottom: 4px; }
.login-card .subtitle {
  font-size: 0.9rem;
  color: var(--wood-600);
  margin-bottom: 32px;
}
.footer-text {
  margin-top: 20px;
  font-size: 0.8rem;
  color: var(--wood-400);
}
:deep(.el-form-item) {
  width: 100%;
  display: flex;
  flex-wrap: nowrap;
}
:deep(.el-form-item__label) {
  font-size: 1rem;
  height: 48px;
  line-height: 48px;
  color: var(--wood-700);
  padding: 0 12px 0 0;
  flex-shrink: 0;
  width: 70px;
}
:deep(.el-form-item__content) {
  flex: 1;
}
:deep(.el-input) {
  width: 100% !important;
}
:deep(.el-input__wrapper) {
  height: 48px;
  width: 100%;
  padding-right: 11px !important;
}
:deep(.el-input__inner) { height: 100% !important; }
:deep(.el-input__suffix) {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
}
:deep(.el-input--password) { position: relative; }
:deep(.el-input__suffix-inner) { margin-left: 0; }
</style>
