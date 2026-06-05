/** Resolve data status (idle | ready | invalid) from status.file_status or legacy status.status */
export function resolveDataStatus(status: any): string {
  if (!status || typeof status !== 'object') return 'idle'
  // New format: status.file_status.status
  if (status.file_status && typeof status.file_status === 'object') {
    return status.file_status.status || 'idle'
  }
  // Legacy format: status.status
  if (typeof status.status === 'string') return status.status
  return 'idle'
}

/** Get Element Plus tag type for data status */
export function dataStatusTagType(status: string): string {
  if (status === 'idle') return 'info'
  if (status === 'ready') return 'success'
  if (status === 'invalid') return 'warning'
  return ''
}

/** Get display text for data status */
export function dataStatusDisplayText(status: string): string {
  const map: Record<string, string> = {
    idle: '无数据',
    ready: '数据完整',
    invalid: '数据有误',
  }
  return map[status] || status
}

/** Resolve training status from status.training_status.status */
export function resolveTrainingStatus(status: any): string {
  if (!status || typeof status !== 'object') return 'idle'
  if (status.training_status && typeof status.training_status === 'object') {
    return status.training_status.status || 'idle'
  }
  return 'idle'
}

/** Get Element Plus tag type for training status */
export function trainingStatusTagType(status: string): string {
  if (status === 'idle') return 'info'
  if (status === 'training') return 'warning'
  if (status === 'success') return 'success'
  if (status === 'failure') return 'danger'
  return ''
}

/** Get display text for training status */
export function trainingStatusDisplayText(status: string): string {
  const map: Record<string, string> = {
    idle: '未训练',
    training: '训练中',
    success: '训练成功',
    failure: '训练失败',
  }
  return map[status] || status
}

/** Check if training is in progress */
export function isTraining(status: string): boolean {
  return status === 'training'
}

/** Check if training succeeded */
export function isTrainingSuccess(status: string): boolean {
  return status === 'success'
}

/** Get button text for train/stop action */
export function trainButtonText(status: string): string {
  if (status === 'training') return '训练终止'
  return '训练模型'
}

/** Get failure reason from training_status object */
export function getTrainingFailureReason(trainingStatus: any): string {
  if (trainingStatus && typeof trainingStatus === 'object') return trainingStatus.error || '未知原因'
  return '未知原因'
}

/** Resolve test status from status.test_status.status */
export function resolveTestStatus(status: any): string {
  if (!status || typeof status !== 'object') return 'idle'
  if (status.test_status && typeof status.test_status === 'object') {
    return status.test_status.status || 'idle'
  }
  return 'idle'
}

/** Get Element Plus tag type for test status */
export function testStatusTagType(status: string): string {
  if (status === 'idle') return 'info'
  if (status === 'generating') return 'warning'
  if (status === 'success') return 'success'
  if (status === 'failure') return 'danger'
  return ''
}

/** Get display text for test status */
export function testStatusDisplayText(status: string): string {
  const map: Record<string, string> = {
    idle: '未测试',
    generating: '生成中',
    success: '测试成功',
    failure: '测试失败',
  }
  return map[status] || status
}

/** Get button text for test generate/stop action */
export function testButtonText(status: string): string {
  if (status === 'generating') return '测试终止'
  return '测试生成'
}

/** Get display text for user role */
export function roleLabel(role: string): string {
  const map: Record<string, string> = { admin: '管理员', advanced: '高级用户', user: '普通用户' }
  return map[role] || role
}

/** Get Element Plus tag type for user role */
export function roleTagType(role: string): string {
  const map: Record<string, string> = { admin: 'danger', advanced: 'warning', user: 'info' }
  return map[role] || 'info'
}
