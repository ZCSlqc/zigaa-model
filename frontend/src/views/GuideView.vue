<template>
  <AppLayout>
    <div class="guide-page">
      <h2 class="page-title">使用教程</h2>

      <div class="guide-steps">
        <div class="step-card" v-for="(step, i) in steps" :key="i">
          <div class="step-header">
            <span class="step-number">{{ i + 1 }}</span>
            <h3>{{ step.title }}</h3>
          </div>
          <p class="step-desc">{{ step.desc }}</p>
          <ul class="step-list">
            <li v-for="(item, j) in step.items" :key="j">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
defineOptions({ name: 'Guide' })
import AppLayout from '../components/Layout/AppLayout.vue'

const steps = [
  {
    title: '创建项目与模型',
    desc: '项目是数据的容器，模型是训练的基本单位。',
    items: [
      '进入"项目"页面，左侧边栏点击"新建项目"，填写项目名称后创建',
      '选中一个项目，右侧点击"新建模型"，填写模型名称',
      '每个模型独立管理数据上传、标注和训练',
      '点击卡片上的编辑按钮可修改名称和描述',
    ],
  },
  {
    title: '上传数据',
    desc: '模型支持四种数据库：良品、缺陷（必传）和测试、模板（可选）。',
    items: [
      '点击模型卡片进入详情页',
      '"良品数据库"区域点击"上传 ZIP"，选择 ZIP 压缩包（内含图片和标注 JSON）',
      '"缺陷数据库"同上，上传缺陷图片 ZIP',
      '"测试数据库"和"模板数据库"可选，上传方式和良品相同',
      '大文件自动分片上传（64MB/片），支持断点续传和取消恢复',
      '上传中点"取消上传"可中断，下次重选文件可自动续传',
      '点"清除缓存"会删除前后端临时分片，下次从零开始',
      '上传后系统自动校验：图片与 JSON 配对、格式正确性、尺寸一致性',
      '校验有错误会在页面展示"问题 (N)"，点击查看详情',
      '再次上传是追加模式（同名图片不覆盖，冲突自动加后缀），不会删除已有数据',
      '修正标注后重新上传 ZIP 即可追加',
    ],
  },
  {
    title: '标注图片',
    desc: '上传数据后进入标注编辑器，绘制缺陷轮廓。测试和模板数据库为只读预览模式。',
    items: [
      '模型详情页点击"标注"进入标注编辑器',
      '左侧目录树浏览图片，绿色 ✓ 表示已标注，红点/黄点表示有错误',
      '目录树支持全部展开/全部折叠',
      '工具栏可切换"良品"/"缺陷"/"测试"/"模板"数据库',
      '良品和缺陷数据库可绘制和编辑标注',
      '测试和模板数据库进入只读预览模式，不可绘制，可删除图片',
    ],
  },
  {
    title: '绘制轮廓',
    desc: '点击打点绘制缺陷轮廓，悬停起点后闭合。',
    items: [
      '左键点击画布连续打点画出多边形轮廓',
      '鼠标悬停起点（绿色）后松手闭合多边形',
      '鼠标悬停末点（红色）可撤回上一个点',
      'Ctrl+Z 取消当前未闭合的绘制，Space 撤回上一个点',
      '闭合后输入标签名，Ctrl+S 保存标注',
      'Tab 切换到"编辑/选择"模式',
    ],
  },
  {
    title: '编辑标注',
    desc: '拖拽顶点调整轮廓，精确编辑每个标注点。',
    items: [
      '左键拖拽蓝点调整顶点位置',
      '左键点击蓝边可在边上添加新顶点',
      '按住 Shift 后蓝点变红，左键点击删除该顶点（需至少 3 个顶点）',
      '左键点击标签可修改标签名称',
      '左键点击标注下方红点可删除整个标注',
      'Tab 切换回"绘制轮廓"模式',
    ],
  },
  {
    title: '画布操作',
    desc: '平移、缩放画布，快速浏览图片。',
    items: [
      '鼠标滚轮缩放画布（0.1x ~ 10x）',
      '右键拖拽平移画布（任何模式下可用）',
      '← → 方向键切换上一张/下一张图片',
      '画布禁止浏览器默认手势（缩放、拖拽、右键菜单）',
    ],
  },
  {
    title: '编辑模型参数',
    desc: '训练需要参数文件（product_type 等），可以上传或在线编辑。',
    items: [
      '模型详情页"模型参数"区域上传 JSON 文件',
      '点击"编辑"使用在线编辑器修改参数',
      '编辑后自动保存，支持 JSON 语法高亮',
    ],
  },
  {
    title: '传输与训练',
    desc: '数据准备完成后传输到本地训练目录，由外部系统检测执行。',
    items: [
      '模型状态为"数据完整"（ready）时点击"传输文件"，复制到本地训练目录',
      '传输完成后点击"训练模型"，系统写入注册索引并等待外部执行',
      '训练中状态栏实时轮询，可随时"检查日志"查看进度',
      '需要终止训练点击"训练终止"',
      '训练失败时点击状态可查看详细报错原因',
      '训练完成后可下载模型（"下载模型"按钮）',
      '点击"返回提交"可回到数据阶段修改后重新训练',
    ],
  },
  {
    title: '模型状态说明',
    desc: '模型状态分为数据状态和训练状态两个维度。',
    items: [
      '数据状态：无数据（idle）→ 数据完整（ready）/ 数据有误（invalid）',
      '训练状态：未训练（idle）→ 训练中（training）→ 训练成功（success）/ 训练失败（failure）',
      '点击"训练模型"将自动传输数据并触发训练',
      '两个状态独立，数据修改不影响训练进度',
    ],
  },
  {
    title: '管理后台',
    desc: '管理员可以管理用户和项目。',
    items: [
      '管理员账号进入"管理"页面',
      '用户管理：创建账号、切换角色、重置密码、删除用户',
      '项目管理：查看全量项目（含模型列表）、删除项目',
    ],
  },
  {
    title: '个人中心',
    desc: '查看个人信息和管理密码。',
    items: [
      '点击右上角头像下拉菜单，选择"个人中心"',
      '查看用户名、权限、项目数量和创建时间',
      '查看所属项目列表，点击"查看"跳转到项目页面',
      '点击"修改密码"进入密码修改页面（需验证原密码）',
    ],
  },
]
</script>

<style scoped lang="scss">
.guide-page {
  padding: var(--spacing-lg);
}

.page-title {
  margin: 0 0 var(--spacing-xl);
  font-size: 20px;
  font-weight: 600;
}

.guide-steps {
  display: grid;
  gap: var(--spacing-md);
  max-width: 800px;
}

.step-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-sm);
}

.step-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.step-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.step-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.step-desc {
  margin: 0 0 var(--spacing-sm);
  color: var(--text-secondary);
  font-size: 14px;
}

.step-list {
  margin: 0;
  padding-left: var(--spacing-lg);
  color: var(--text-regular);
  font-size: 14px;
  line-height: 1.8;
}
</style>
