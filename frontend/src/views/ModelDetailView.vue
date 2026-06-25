<template>
  <AppLayout>
    <div class="model-detail">
      <!-- 顶部导航栏 -->
      <div class="model-header">
        <div class="header-left">
          <el-button text @click="router.push('/project')">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <h2 class="model-title">{{ model.name }}</h2>
          <el-tag size="small" :type="dataStatusType">{{ dataStatusText }}</el-tag>
          <el-tag size="small" :type="trainingStatusType">{{ trainingStatusText }}</el-tag>
          <el-tag size="small" :type="testStatusType">{{ testStatusText }}</el-tag>
        </div>
        <div class="header-desc">{{ model.description || "暂无描述" }}</div>
      </div>

      <!-- 三资源区域 -->
      <div class="resource-grid">
        <!-- 良品数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            良品数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'good'"
                @click="showZipUpload('good')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'good'"
                :disabled="!goodLoaded"
                @click="download('good')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!goodLoaded"
                :loading="isLoading('delete-good')"
                @click="confirmDelete('good')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!goodLoaded"
                @click="annotate('good')"
                >标注</el-button
              >
              <el-button
                size="small"
                class="btn-reprocess"
                :disabled="!goodLoaded"
                :loading="isLoading('reprocess-good')"
                @click="handleReprocess('good')"
                >重新入库</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!goodLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag
                  v-if="Object.keys(goodErrors).length === 0"
                  type="success"
                  size="small"
                >
                  成功 {{ goodPassed }} 张
                </el-tag>
                <el-button
                  v-else
                  type="warning"
                  size="small"
                  text
                  @click="showErrors('good')"
                >
                  问题 ({{ goodFailed }})
                </el-button>
              </template>
            </div>
          </div>
        </div>

        <!-- 缺陷数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            缺陷数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'defect'"
                @click="showZipUpload('defect')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'defect'"
                :disabled="!defectLoaded"
                @click="download('defect')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!defectLoaded"
                :loading="isLoading('delete-defect')"
                @click="confirmDelete('defect')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!defectLoaded"
                @click="annotate('defect')"
                >标注</el-button
              >
              <el-button
                size="small"
                class="btn-reprocess"
                :disabled="!defectLoaded"
                :loading="isLoading('reprocess-defect')"
                @click="handleReprocess('defect')"
                >重新入库</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!defectLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag
                  v-if="Object.keys(defectErrors).length === 0"
                  type="success"
                  size="small"
                >
                  成功 {{ defectPassed }} 张
                </el-tag>
                <el-button
                  v-else
                  type="warning"
                  size="small"
                  text
                  @click="showErrors('defect')"
                >
                  问题 ({{ defectFailed }})
                </el-button>
              </template>
            </div>
          </div>
        </div>

        <!-- 模型参数 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Document /></el-icon>
            模型参数
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button size="small" @click="showJsonUpload"
                >上传 JSON</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'parameter'"
                :disabled="!paramLoaded"
                @click="download('parameter')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!paramLoaded"
                :loading="isLoading('delete-parameter')"
                @click="confirmDelete('parameter')"
                >删除</el-button
              >
              <el-button size="small" type="primary" class="btn-solid" :loading="isLoading('open-param')" @click="openParamEditor">编辑</el-button>
            </div>
            <div class="resource-status">
              <span v-if="!paramLoaded" class="empty-text">暂无数据</span>
              <el-tag v-else type="success" size="small">已上传</el-tag>
            </div>
          </div>
        </div>

        <!-- 测试数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            测试数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'test'"
                @click="showZipUpload('test')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'test'"
                :disabled="!testLoaded"
                @click="download('test')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!testLoaded"
                :loading="isLoading('delete-test')"
                @click="confirmDelete('test')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!testLoaded"
                @click="annotate('test')"
                >预览</el-button
              >
              <el-button
                size="small"
                class="btn-reprocess"
                :disabled="!testLoaded"
                :loading="isLoading('reprocess-test')"
                @click="handleReprocess('test')"
                >重新入库</el-button
              >
              <el-button
                size="small"
                :loading="isLoading('test-logs')"
                :disabled="!testLoaded"
                @click="handleTestLogs"
                >测试日志</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!testLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag type="success" size="small">成功 {{ testPassed }} 张</el-tag>
              </template>
            </div>
          </div>
        </div>

        <!-- 模板数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            模板数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'template'"
                @click="showZipUpload('template')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'template'"
                :disabled="!templateLoaded"
                @click="download('template')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!templateLoaded"
                :loading="isLoading('delete-template')"
                @click="confirmDelete('template')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!templateLoaded"
                @click="annotate('template')"
                >预览</el-button
              >
              <el-button
                size="small"
                class="btn-reprocess"
                :disabled="!templateLoaded"
                :loading="isLoading('reprocess-template')"
                @click="handleReprocess('template')"
                >重新入库</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!templateLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag type="success" size="small">成功 {{ templatePassed }} 张</el-tag>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ZIP 上传弹窗 -->
      <el-dialog
        v-model="showZipDialog"
        :title="zipDialogTitle"
        width="500px"
      >
        <ZipUpload
          :model-id="modelId"
          :type="zipType"
          @uploaded="handleZipUploaded"
          @all-uploaded="handleZipAllUploaded"
        />
      </el-dialog>

      <!-- JSON 上传弹窗 -->
      <el-dialog v-model="showJsonDialog" title="上传模型参数" width="400px">
        <JsonUpload :model-id="modelId" @uploaded="handleJsonUploaded" />
      </el-dialog>

      <!-- JSON 编辑器 -->
      <JsonEditor
        v-model="showParamEditor"
        title="编辑模型参数"
        :initial-content="paramEditorContent"
        @save="handleParamSave"
      />

      <!-- 错误详情弹窗 -->
      <el-dialog v-model="showErrorDialog" title="错误详情" width="600px">
        <el-table :data="sortedErrors" size="small" max-height="400">
          <el-table-column prop="path" label="图片路径" />
          <el-table-column prop="type" label="错误类型" width="140" />
          <el-table-column prop="message" label="错误信息" />
        </el-table>
      </el-dialog>

      <!-- 测试日志弹窗 -->
      <el-dialog v-model="showTestLogsDialog" title="测试日志" width="700px">
        <pre class="logs-content">{{ testLogsContent || '暂无日志' }}</pre>
      </el-dialog>

      <BatchDownloadDialog
        ref="batchDownloadDialogRef"
        :model-id="modelId"
        :resource-type="batchDownloadType"
        :arrange-names="batchArrangeNames"
        :resource-label="batchDownloadLabel"
        :download-api="batchDownloadApi"
        @all-done="handleBatchAllDone"
      />

      <!-- 重新入库弹窗 -->
      <el-dialog v-model="showReprocessDialog" title="重新入库" width="420px" :close-on-click-modal="false">
        <div class="reprocess-status">
          <el-icon v-if="reprocessStatus === 'processing'" class="is-loading" style="font-size: 32px; color: #409eff"><Loading /></el-icon>
          <el-icon v-else-if="reprocessStatus === 'completed'" style="font-size: 32px; color: #67c23a"><CircleCheckFilled /></el-icon>
          <el-icon v-else-if="reprocessStatus === 'failed'" style="font-size: 32px; color: #f56c6c"><CircleCloseFilled /></el-icon>
          <p class="reprocess-text">{{ reprocessMessage }}</p>
          <p v-if="reprocessStatus === 'completed'" class="reprocess-detail">
            处理 {{ reprocessResult?.passed_count ?? 0 }} 张，失败 {{ reprocessResult?.failed_count ?? 0 }} 张
          </p>
          <p v-if="reprocessStatus === 'failed'" class="reprocess-error">{{ reprocessError }}</p>
        </div>
        <template #footer>
          <el-button v-if="reprocessStatus !== 'processing'" @click="closeReprocessDialog">确定</el-button>
          <el-button v-if="reprocessStatus === 'processing'" @click="cancelReprocess">取消</el-button>
        </template>
      </el-dialog>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Folder, Document, Loading, CircleCheckFilled, CircleCloseFilled } from "@element-plus/icons-vue";
import AppLayout from "../components/Layout/AppLayout.vue";
import ZipUpload from "../components/Upload/ZipUpload.vue";
import JsonUpload from "../components/Upload/JsonUpload.vue";
import JsonEditor from "../components/Editor/JsonEditor.vue";
import BatchDownloadDialog from "../components/Download/BatchDownloadDialog.vue";
import { useDelayedLoading } from "../composables/useDelayedLoading";
import { useProjectStore } from "../stores/project";
import { resolveDataStatus, dataStatusTagType, dataStatusDisplayText, resolveTrainingStatus, trainingStatusTagType, trainingStatusDisplayText, resolveTestStatus, testStatusTagType, testStatusDisplayText } from "../utils/model-status";
import { getModel } from "../api/model";
import {
  deleteGood,
  deleteDefect,
  deleteParameter,
  deleteTest,
  deleteTemplate,
  downloadParameter,
  getParameter,
  editParameter,
  deleteParameterFile,
  checkDiskSpace,
  reprocessResource,
  getUploadStatus,
} from "../api/resource";

const route = useRoute();
const router = useRouter();
const store = useProjectStore();

const modelId = computed(() => route.params.modelId as string);

// 模型信息
const model = ref({
  id: "",
  name: "",
  description: "",
  status: {
    file_status: { status: "idle" },
    training_status: { status: "idle" },
    test_status: { status: "idle" },
  },
  packages: [] as any[],
});

const { startLoading, stopLoading, isLoading } = useDelayedLoading();

const dataStatusType = computed(() => dataStatusTagType(resolveDataStatus(model.value.status)))
const dataStatusText = computed(() => dataStatusDisplayText(resolveDataStatus(model.value.status)))
const trainingStatusType = computed(() => trainingStatusTagType(resolveTrainingStatus(model.value.status)))
const trainingStatusText = computed(() => trainingStatusDisplayText(resolveTrainingStatus(model.value.status)))
const testStatusType = computed(() => testStatusTagType(resolveTestStatus(model.value.status)))
const testStatusText = computed(() => testStatusDisplayText(resolveTestStatus(model.value.status)))
const zipDialogTitle = computed(() => {
  const titles: Record<string, string> = { good: '上传良品数据包', defect: '上传缺陷数据包', test: '上传测试数据包', template: '上传模板数据包' }
  return titles[zipType.value] || '上传数据包'
})

// 资源状态
const goodLoaded = ref(false);
const goodPassed = ref(0);
const goodFailed = ref(0);
const goodErrors = ref<any>({});

const defectLoaded = ref(false);
const defectPassed = ref(0);
const defectFailed = ref(0);
const defectErrors = ref<any>({});

const paramLoaded = ref(false);

const testLoaded = ref(false);
const testPassed = ref(0);
const testFailed = ref(0);
const testErrors = ref<any[]>([]);

const templateLoaded = ref(false);
const templatePassed = ref(0);
const templateFailed = ref(0);
const templateErrors = ref<any[]>([]);

// 上传状态
const uploading = ref<"good" | "defect" | "test" | "template" | null>(null);
const downloading = ref<"good" | "defect" | "parameter" | "test" | "template" | null>(null);
const batchDownloadDialogRef = ref<InstanceType<typeof BatchDownloadDialog>>();

// Batch download state
const batchArrangeNames = ref<string[]>([]);
const batchDownloadType = ref<"good" | "defect" | "test" | "template">("good");
const batchDownloadLabel = ref("");
const batchDownloadApi = ref<any>({
  init: async () => ({}),
  chunk: () => Promise.resolve(),
  cleanup: () => Promise.resolve(),
});

// 弹窗控制
const showZipDialog = ref(false);
const zipType = ref<"good" | "defect" | "test" | "template">("good");
const showJsonDialog = ref(false);

// 参数编辑器
const showParamEditor = ref(false);
const paramEditorContent = ref("");

// 错误弹窗
const showErrorDialog = ref(false);
const currentErrors = ref<any[]>([]);
const sortedErrors = computed(() => {
  return [...currentErrors.value].sort((a, b) => (a.path || '').localeCompare(b.path || ''));
});

function showErrors(type: "good" | "defect" | "test" | "template") {
  const errorDicts: Record<string, any> = { good: goodErrors.value, defect: defectErrors.value, test: testErrors.value, template: templateErrors.value };
  const dict = errorDicts[type] || {};
  currentErrors.value = Object.entries(dict).map(([path, entry]: [string, any]) => ({ path, type: entry.type || 'error', message: entry.message, level: entry.level }));
  showErrorDialog.value = true;
}

// 测试日志
const showTestLogsDialog = ref(false)
const testLogsContent = ref('')

async function handleTestLogs() {
  startLoading('test-logs')
  try {
    const res = await store.getTestLogs(modelId.value)
    testLogsContent.value = res.log
    showTestLogsDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '获取测试日志失败')
  } finally {
    stopLoading()
  }
}

// ── 重新入库 ──
const showReprocessDialog = ref(false);
const reprocessStatus = ref<'idle' | 'processing' | 'completed' | 'failed'>('idle');
const reprocessMessage = ref('');
const reprocessError = ref('');
const reprocessResult = ref<any>(null);
let reprocessPollTimer: ReturnType<typeof setInterval> | null = null;
let reprocessCountdownTimer: ReturnType<typeof setInterval> | null = null;

function clearReprocessTimers() {
  if (reprocessPollTimer) { clearInterval(reprocessPollTimer); reprocessPollTimer = null; }
  if (reprocessCountdownTimer) { clearInterval(reprocessCountdownTimer); reprocessCountdownTimer = null; }
}

function closeReprocessDialog() {
  showReprocessDialog.value = false;
  clearReprocessTimers();
  stopLoading();
}

function cancelReprocess() {
  // 轮询是单向的，取消不了后端任务，只需关闭弹窗
  clearReprocessTimers();
  showReprocessDialog.value = false;
  stopLoading();
}

async function handleReprocess(type: "good" | "defect" | "test" | "template") {
  const typeNames: Record<string, string> = { good: '良品', defect: '缺陷', test: '测试', template: '模板' }

  // 磁盘空间检查
  let freeGb: number
  try {
    const res: any = await checkDiskSpace(modelId.value, type)
    freeGb = res.data.free_gb
  } catch {
    ElMessage.warning('磁盘空间检查失败，跳过')
    return
  }
  if (freeGb < 2) {
    ElMessage.warning(`剩余空间 ${freeGb.toFixed(1)}GB，不足 2GB，请联系管理员`)
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要对"${typeNames[type]}"资源重新入库吗？将重新生成压缩图和预览图。`,
      '确认重新入库',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
    );
  } catch { return; }

  startLoading('reprocess-' + type)
  reprocessStatus.value = 'processing';
  reprocessMessage.value = '正在重新入库...';
  reprocessError.value = '';
  reprocessResult.value = null;
  showReprocessDialog.value = true;

  try {
    const res: any = await reprocessResource(modelId.value, type);
    const reprocessId = res.data.reprocess_id;

    let countdownSeconds = 30;
    reprocessCountdownTimer = setInterval(() => {
      if (reprocessStatus.value !== 'processing') {
        clearInterval(reprocessCountdownTimer!);
        reprocessCountdownTimer = null;
        return;
      }
      if (countdownSeconds > 2) { countdownSeconds--; }
    }, 1000);

    reprocessPollTimer = setInterval(async () => {
      if (reprocessStatus.value !== 'processing') return;
      try {
        const statusRes: any = await getUploadStatus(modelId.value, type, reprocessId);
        const d = statusRes.data;
        if (d.status === 'completed') {
          reprocessStatus.value = 'completed';
          reprocessMessage.value = '重新入库完成';
          reprocessResult.value = d.result;
          clearInterval(reprocessPollTimer!);
          reprocessPollTimer = null;
          clearInterval(reprocessCountdownTimer!);
          reprocessCountdownTimer = null;
          await fetchModel();
        } else if (d.status === 'failed') {
          reprocessStatus.value = 'failed';
          reprocessMessage.value = '重新入库失败';
          reprocessError.value = d.error || '处理失败';
          clearInterval(reprocessPollTimer!);
          reprocessPollTimer = null;
          clearInterval(reprocessCountdownTimer!);
          reprocessCountdownTimer = null;
        }
      } catch { /* ignore polling errors */ }
    }, 5000);
  } catch (e: any) {
    reprocessStatus.value = 'failed';
    reprocessMessage.value = '重新入库失败';
    reprocessError.value = e.response?.data?.detail || '操作失败';
  } finally {
    stopLoading()
  }
}

// 加载模型详情（先清零再填充）
async function fetchModel() {
  try {
    const res = await getModel(modelId.value);
    model.value = res.data;
    const pkgs = res.data.packages || [];

    // 清零
    goodLoaded.value = false;
    goodPassed.value = 0;
    goodFailed.value = 0;
    goodErrors.value = {};
    defectLoaded.value = false;
    defectPassed.value = 0;
    defectFailed.value = 0;
    defectErrors.value = {};
    paramLoaded.value = false;
    testLoaded.value = false;
    testPassed.value = 0;
    testFailed.value = 0;
    testErrors.value = {};
    templateLoaded.value = false;
    templatePassed.value = 0;
    templateFailed.value = 0;
    templateErrors.value = {};

    // 填充
    const good = pkgs.find((p: any) => p.resource_type === "good");
    const defect = pkgs.find((p: any) => p.resource_type === "defect");
    const param = pkgs.find((p: any) => p.resource_type === "parameter");
    const test = pkgs.find((p: any) => p.resource_type === "test");
    const template = pkgs.find((p: any) => p.resource_type === "template");

    if (good) {
      goodLoaded.value = true;
      goodPassed.value = good.passed_count || 0;
      goodFailed.value = good.failed_count || 0;
      goodErrors.value = good.errors || {};
    }
    if (defect) {
      defectLoaded.value = true;
      defectPassed.value = defect.passed_count || 0;
      defectFailed.value = defect.failed_count || 0;
      defectErrors.value = defect.errors || {};
    }
    if (param) {
      paramLoaded.value = true;
    }
    if (test) {
      testLoaded.value = true;
      testPassed.value = test.passed_count || 0;
      testFailed.value = test.failed_count || 0;
      testErrors.value = test.errors || {};
    }
    if (template) {
      templateLoaded.value = true;
      templatePassed.value = template.passed_count || 0;
      templateFailed.value = template.failed_count || 0;
      templateErrors.value = template.errors || {};
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "加载模型失败");
  }
}

// ZIP 上传
async function showZipUpload(type: "good" | "defect" | "test" | "template") {
  let freeGb: number
  try {
    const res: any = await checkDiskSpace(modelId.value, type)
    freeGb = res.data.free_gb
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "磁盘检查失败")
    return
  }
  if (freeGb < 2) {
    ElMessage.warning("剩余空间不足2GB，请联系管理员")
    return
  }
  zipType.value = type
  showZipDialog.value = true
}

function handleZipUploaded(result: any) {
  uploading.value = null;
  if (result) {
    const updates: Record<string, any> = {
      good: { loaded: goodLoaded, passed: goodPassed, failed: goodFailed, errors: goodErrors },
      defect: { loaded: defectLoaded, passed: defectPassed, failed: defectFailed, errors: defectErrors },
      test: { loaded: testLoaded, passed: testPassed, failed: testFailed, errors: testErrors },
      template: { loaded: templateLoaded, passed: templatePassed, failed: templateFailed, errors: templateErrors },
    }
    const u = updates[zipType.value]
    if (u) {
      u.loaded.value = true;
      u.passed.value += result.passed_count || 0;
      u.failed.value += result.failed_count || 0;
      // Merge errors dict
      if (result.errors) {
        u.errors.value = { ...u.errors.value, ...result.errors };
      }
      // Merge msgs dict
      if (result.msgs) {
        // Not stored locally, but tree will reload on next loadModel call
      }
    }
  }
}

function handleZipAllUploaded() {
  showZipDialog.value = false;
  fetchModel();
}

// JSON 上传
function showJsonUpload() {
  showJsonDialog.value = true;
}

function handleJsonUploaded() {
  showJsonDialog.value = false;
  fetchModel();
}

// 下载
async function download(type: "good" | "defect" | "parameter" | "test" | "template") {
  if (!getTypeLoaded(type)) {
    ElMessage.warning("暂无数据");
    return;
  }

  // JSON 参数直接下载
  if (type === "parameter") {
    downloading.value = type;
    try {
      const res = await downloadParameter(modelId.value);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = "parameter.json";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || "下载失败");
    } finally {
      downloading.value = null;
    }
    return;
  }

  // ZIP 分片下载：先拉取时间戳文件夹列表，弹 BatchDownloadDialog
  const resourceLabels: Record<string, string> = { good: "良品数据库", defect: "缺陷数据库", test: "测试数据库", template: "模板数据库" };
  const { downloadInit, downloadChunk, downloadCleanup, arrangeList } = await import('../api/resource');

  try {
    const listRes: any = await arrangeList(modelId.value, type);
    const names = listRes.data.arrange_dirs || [];

    if (names.length === 0) {
      ElMessage.warning("暂无可下载的批次");
      return;
    }

    batchArrangeNames.value = names;
    batchDownloadType.value = type;
    batchDownloadLabel.value = resourceLabels[type] || type;
    batchDownloadApi.value = {
      init: async (mid: string, rt: string, arrange: string) => {
        const res: any = await downloadInit(mid, rt, { arrange_name: arrange });
        return res;
      },
      chunk: (mid: string, rt: string, sid: string, idx: number, signal?: AbortSignal) => downloadChunk(mid, rt, sid, idx, signal),
      cleanup: (mid: string, rt: string, sid: string) => downloadCleanup(mid, rt, sid),
    };
    batchDownloadDialogRef.value?.openDialog();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "获取批次列表失败");
  }
}

function handleBatchAllDone() {
  downloading.value = null;
}

// 删除
async function confirmDelete(type: "good" | "defect" | "parameter" | "test" | "template") {
  const labels: Record<string, string> = {
    good: "良品数据库",
    defect: "缺陷数据库",
    parameter: "模型参数",
    test: "测试数据库",
    template: "模板数据库",
  };
  try {
    await ElMessageBox.confirm(
      `确定删除${labels[type]}？此操作不可撤销。`,
      "确认删除",
      { type: "warning" },
    );
  } catch {
    return;
  }

  startLoading('delete-' + type)
  try {
    if (type === "good") await deleteGood(modelId.value);
    else if (type === "defect") await deleteDefect(modelId.value);
    else if (type === "test") await deleteTest(modelId.value);
    else if (type === "template") await deleteTemplate(modelId.value);
    else await deleteParameter(modelId.value);
    ElMessage.success("删除成功");
    fetchModel();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  } finally {
    stopLoading()
  }
}

// 参数编辑器
async function openParamEditor() {
  startLoading('open-param')
  paramEditorContent.value = "";
  try {
    const res = await getParameter(modelId.value);
    paramEditorContent.value = JSON.stringify(res.data.data, null, 2);
  } catch {
    // 文件不存在，空编辑
  } finally {
    stopLoading()
  }
  showParamEditor.value = true;
}

async function handleParamSave(content: string) {
  showParamEditor.value = false;
  if (!content.trim()) {
    // 空内容 = 删除文件
    startLoading('save-param')
    try {
      await deleteParameterFile(modelId.value);
      ElMessage.success("模型参数已删除");
      fetchModel();
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || "删除失败");
    } finally {
      stopLoading()
    }
    return;
  }
  startLoading('save-param')
  try {
    const parsed = JSON.parse(content);
    await editParameter(modelId.value, parsed);
    ElMessage.success("模型参数已保存");
    fetchModel();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    stopLoading()
  }
}

// 标注/预览
async function annotate(type: string) {
  if (type === 'test') {
    const testStatus = resolveTestStatus(model.value.status)
    if (testStatus === 'success') {
      ElMessage.success('测试已成功，加载对应JSON标注')
    } else {
      ElMessage.warning('测试未完成，标注数据可能为空')
    }
    router.push(`/preview/${modelId.value}?type=${type}`)
  } else if (type === 'template') {
    router.push(`/preview/${modelId.value}?type=${type}`)
  } else {
    router.push(`/annotate/${modelId.value}?type=${type}`)
  }
}

function getTypeLoaded(type: string): boolean {
  if (type === "good") return goodLoaded.value;
  if (type === "defect") return defectLoaded.value;
  if (type === "parameter") return paramLoaded.value;
  if (type === "test") return testLoaded.value;
  if (type === "template") return templateLoaded.value;
  return false;
}

onMounted(() => {
  fetchModel();

});
</script>

<style scoped lang="scss">
.model-detail {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--spacing-lg);
}

.model-header {
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.model-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin-left: calc(28px + var(--spacing-sm) * 2);
}

.resource-grid {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md) var(--spacing-lg);
  box-shadow: var(--shadow-sm);
}

.resource-title {
  margin: 0 0 var(--spacing-sm);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);

  .el-icon {
    font-size: 18px;
    color: var(--color-primary);
  }
}

.resource-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.resource-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.resource-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.empty-text {
  color: var(--text-secondary);
  font-size: 13px;
}

.resource-actions .btn-solid {
  color: #fff !important;

  &.is-loading,
  &.is-disabled {
    color: #fff !important;

    .el-button__text {
      color: #fff !important;
    }
  }
}

.logs-content {
  background: var(--bg-page);
  color: var(--text-primary);
  padding: var(--spacing-md);
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.5;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.btn-reprocess {
  color: #e6a23c !important;
  &:disabled {
    opacity: 0.5 !important;
    pointer-events: none !important;
  }
}

.reprocess-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 24px 0;
}

.reprocess-text {
  font-size: 16px;
  color: var(--text-regular);
  margin: 0;
}

.reprocess-detail {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.reprocess-error {
  font-size: 14px;
  color: #f56c6c;
  margin: 0;
}
</style>
