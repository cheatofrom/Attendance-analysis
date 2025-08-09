import React, { useState, useEffect, useRef } from 'react'
import { Button, Progress, Typography, Space, Alert, Card, Divider, Tag, Spin, Switch } from 'antd'
import { PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, CheckCircleOutlined, ExclamationCircleOutlined, StopOutlined, RobotOutlined, VerticalAlignBottomOutlined } from '@ant-design/icons'
import axios from 'axios'

const { Text, Title } = Typography

interface ProcessControlProps {
  canStart: boolean
  isProcessing: boolean
  onProcessStart: () => void
  onProcessComplete: () => void
  onLogUpdate: (log: string) => void
  processLogs: string
}

interface ProcessStatus {
  is_running: boolean
  start_time: string | null
  end_time: string | null
  exit_code: number | null
  output: string
  error: string
}

const ProcessControl: React.FC<ProcessControlProps> = ({
  canStart,
  isProcessing,
  onProcessStart,
  onProcessComplete,
  onLogUpdate,
  processLogs
}) => {
  const [processStatus, setProcessStatus] = useState<ProcessStatus | null>(null)
  const [progress, setProgress] = useState(0)
  const [currentStep, setCurrentStep] = useState('')
  const [isPolling, setIsPolling] = useState(false)
  const [aiAgentEnabled, setAiAgentEnabled] = useState(false)
  const [displayLogs, setDisplayLogs] = useState('')
  const [logQueue, setLogQueue] = useState<string[]>([])
  const [isNearBottom, setIsNearBottom] = useState(true) // 跟踪是否接近底部
  const logContainerRef = useRef<HTMLDivElement>(null)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const logUpdateIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastProcessedLogLength = useRef(0)
  const hasInitialized = useRef(false)

  // 组件挂载时检查后台脚本状态
  useEffect(() => {
    const checkInitialStatus = async () => {
      if (hasInitialized.current) return
      hasInitialized.current = true
      
      try {
        const response = await axios.get('/api/script-status')
        const status: ProcessStatus = response.data.status
        
        if (status.is_running) {
          // 发现脚本正在运行，恢复前端状态
          console.log('检测到脚本正在运行，恢复前端状态...')
          setProcessStatus(status)
          onProcessStart() // 通知父组件进入处理状态
          
          // 恢复日志内容
          if (status.output) {
            setDisplayLogs(status.output)
            onLogUpdate(status.output)
            lastProcessedLogLength.current = status.output.length
            analyzeLogProgress(status.output)
          }
          
          // 启动轮询监控
          setIsPolling(true)
          setCurrentStep('恢复监控中...')
          
          const restoreMsg = '\n[系统] 页面刷新后自动恢复脚本监控状态\n'
          setLogQueue(prev => [...prev, restoreMsg])
          onLogUpdate((status.output || '') + restoreMsg)
        }
      } catch (error) {
        console.error('检查初始状态失败:', error)
      }
    }
    
    checkInitialStatus()
  }, [])

  // 检查是否接近底部
  const checkIfNearBottom = () => {
    if (logContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logContainerRef.current
      const threshold = 50 // 距离底部50px内认为是接近底部
      const isNear = scrollHeight - scrollTop - clientHeight <= threshold
      setIsNearBottom(isNear)
      return isNear
    }
    return true
  }

  // 滚动事件监听器
  useEffect(() => {
    const container = logContainerRef.current
    if (container) {
      const handleScroll = () => {
        checkIfNearBottom()
      }
      
      container.addEventListener('scroll', handleScroll)
      return () => {
        container.removeEventListener('scroll', handleScroll)
      }
    }
  }, [])

  // 智能自动滚动到日志底部
  useEffect(() => {
    if (logContainerRef.current && isNearBottom) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [displayLogs, isNearBottom])

  // 处理日志队列，控制更新频率和批处理
  const processLogQueue = () => {
    if (logQueue.length > 0) {
      // 批处理：一次最多处理3条日志，提升流畅度
      const batchSize = Math.min(3, logQueue.length)
      const batch = logQueue.slice(0, batchSize)
      const batchText = batch.join('')
      
      setLogQueue(prev => prev.slice(batchSize))
      setDisplayLogs(prev => prev + batchText)
    }
  }

  // 启动日志更新定时器
  useEffect(() => {
    if (isProcessing || logQueue.length > 0) {
      logUpdateIntervalRef.current = setInterval(processLogQueue, 250) // 每250ms处理一批日志，平衡流畅度和性能
      return () => {
        if (logUpdateIntervalRef.current) {
          clearInterval(logUpdateIntervalRef.current)
        }
      }
    }
  }, [isProcessing, logQueue.length])

  // 处理新日志，添加到队列而非直接更新
  const handleNewLogs = (newLogs: string) => {
    if (newLogs.length > lastProcessedLogLength.current) {
      const newContent = newLogs.slice(lastProcessedLogLength.current)
      const lines = newContent.split('\n').filter(line => line.trim())
      
      if (lines.length > 0) {
        setLogQueue(prev => [...prev, ...lines.map(line => line + '\n')])
        lastProcessedLogLength.current = newLogs.length
      }
    }
  }

  // 轮询获取脚本状态
  const pollScriptStatus = async () => {
    try {
      const response = await axios.get('/api/script-status')
      const status: ProcessStatus = response.data.status
      
      setProcessStatus(status)
      
      if (status.output && status.output !== processLogs) {
        handleNewLogs(status.output)
        onLogUpdate(status.output)
        
        // 分析日志内容来更新进度和当前步骤
        analyzeLogProgress(status.output)
      }
      
      if (status.error) {
        const errorMsg = `\n[错误] ${status.error}`
        setLogQueue(prev => [...prev, errorMsg])
        onLogUpdate(processLogs + errorMsg)
      }
      
      // 如果脚本完成，停止轮询
      if (!status.is_running && status.end_time) {
        setIsPolling(false)
        onProcessComplete()
        
        if (status.exit_code === 0) {
          const successMsg = '\n[完成] 所有脚本执行成功！'
          setLogQueue(prev => [...prev, successMsg])
          onLogUpdate(processLogs + successMsg)
          setProgress(100)
          setCurrentStep('处理完成')
        } else {
          const failMsg = `\n[失败] 脚本执行失败，退出代码: ${status.exit_code}`
          setLogQueue(prev => [...prev, failMsg])
          onLogUpdate(processLogs + failMsg)
          setCurrentStep('处理失败')
        }
      }
    } catch (error) {
      console.error('Failed to poll script status:', error)
      const errorMsg = `\n[错误] 获取脚本状态失败: ${error}`
      setLogQueue(prev => [...prev, errorMsg])
      onLogUpdate(processLogs + errorMsg)
    }
  }

  // 分析日志内容来估算进度
  const analyzeLogProgress = (logs: string) => {
    const lines = logs.split('\n')
    const totalSteps = 8 // 根据运行顺序文件，总共8个步骤
    let completedSteps = 0
    let currentStepName = ''
    
    // 定义步骤关键词
    const stepKeywords = [
      { keyword: 'basic_combined.py', name: '处理基础考勤数据', step: 1 },
      { keyword: 'business_combine.py', name: '合并出差数据', step: 2 },
      { keyword: 'freework_combine.py', name: '合并请假数据', step: 3 },
      { keyword: 'overwork_combine.py', name: '合并加班数据', step: 4 },
      { keyword: 'business_chage.py', name: '处理出差变更', step: 5 },
      { keyword: 'freework_chage.py', name: '处理请假变更', step: 6 },
      { keyword: 'overwork_chage.py', name: '处理加班变更', step: 7 },
      { keyword: 'attendance_summary.py', name: '生成考勤汇总', step: 8 }
    ]
    
    // 分析每一行日志
    for (const line of lines) {
      for (const step of stepKeywords) {
        if (line.includes(step.keyword)) {
          if (line.includes('开始执行') || line.includes('正在处理')) {
            currentStepName = step.name
            completedSteps = Math.max(completedSteps, step.step - 1)
          } else if (line.includes('完成') || line.includes('成功')) {
            completedSteps = Math.max(completedSteps, step.step)
          }
        }
      }
    }
    
    const progressPercent = Math.round((completedSteps / totalSteps) * 100)
    setProgress(progressPercent)
    
    if (currentStepName) {
      setCurrentStep(currentStepName)
    }
  }

  // 开始轮询
  useEffect(() => {
    if (isPolling) {
      pollingIntervalRef.current = setInterval(pollScriptStatus, 2000) // 每2秒轮询一次
      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
        }
      }
    }
  }, [isPolling])

  // 启动处理
  const handleStartProcess = async () => {
    try {
      // 立即清空之前的日志和状态
      setDisplayLogs('')
      setLogQueue([])
      onLogUpdate('')
      lastProcessedLogLength.current = 0
      setProgress(0)
      setCurrentStep('')
      setProcessStatus(null)
      setIsNearBottom(true) // 重置为接近底部状态
      
      onProcessStart()
      setProgress(0)
      setCurrentStep('准备启动...')
      const agentStatus = aiAgentEnabled ? '启用AI agent' : '不启用AI agent'
      const startMsg = `[开始] 启动考勤数据处理脚本... (${agentStatus})\n`
      setDisplayLogs('')
      setLogQueue([startMsg])
      lastProcessedLogLength.current = 0
      onLogUpdate(startMsg)
      
      // 启动异步脚本执行，传递AI agent参数
      const response = await axios.post('/api/run-script-async', {
        ai_agent_enabled: aiAgentEnabled
      })
      
      if (response.data.success) {
        const infoMsg = '[信息] 脚本已在后台启动，开始监控执行状态...\n'
        setLogQueue(prev => [...prev, infoMsg])
        onLogUpdate(processLogs + infoMsg)
        setIsPolling(true)
        setCurrentStep('脚本执行中...')
      } else {
        throw new Error('启动脚本失败')
      }
    } catch (error) {
      console.error('Failed to start process:', error)
      const errorMsg = `[错误] 启动处理失败: ${error}\n`
      setLogQueue(prev => [...prev, errorMsg])
      onLogUpdate(processLogs + errorMsg)
      onProcessComplete()
      setCurrentStep('启动失败')
    }
  }

  // 停止轮询（用于手动停止监控）
  const handleStopMonitoring = () => {
    setIsPolling(false)
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
    }
    const stopMsg = '[信息] 已停止监控脚本状态\n'
    setLogQueue(prev => [...prev, stopMsg])
    onLogUpdate(processLogs + stopMsg)
  }

  // 中断脚本执行
  const handleStopScript = async () => {
    try {
      const stoppingMsg = '[信息] 正在停止脚本执行...\n'
      setLogQueue(prev => [...prev, stoppingMsg])
      onLogUpdate(processLogs + stoppingMsg)
      
      const response = await axios.post('/api/stop-script')
      
      if (response.data.success) {
        const successMsg = `[信息] ${response.data.message}\n`
        setLogQueue(prev => [...prev, successMsg])
        onLogUpdate(processLogs + stoppingMsg + successMsg)
        setIsPolling(false)
        setCurrentStep('已中断')
        onProcessComplete()
        
        // 更新状态
        if (response.data.status) {
          setProcessStatus(response.data.status)
        }
      } else {
        throw new Error('停止脚本失败')
      }
    } catch (error: any) {
      console.error('Failed to stop script:', error)
      const errorMessage = error.response?.data?.detail || error.message || '未知错误'
      const errorMsg = `[错误] 停止脚本失败: ${errorMessage}\n`
      setLogQueue(prev => [...prev, errorMsg])
      onLogUpdate(processLogs + errorMsg)
    }
  }

  // 清空日志
  const handleClearLogs = () => {
    onLogUpdate('')
    setDisplayLogs('')
    setLogQueue([])
    lastProcessedLogLength.current = 0
    setProgress(0)
    setCurrentStep('')
    setProcessStatus(null)
    setIsNearBottom(true) // 重置为接近底部状态
  }

  // 跳转到最新日志并释放缓存
  const handleJumpToLatest = () => {
    // 清空日志队列缓存
    setLogQueue([])
    // 强制滚动到底部
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
    // 设置为接近底部状态
    setIsNearBottom(true)
  }

  // 获取状态标签
  const getStatusTag = () => {
    if (!processStatus) return null
    
    if (processStatus.is_running) {
      return <Tag color="processing" icon={<Spin size="small" />}>运行中</Tag>
    } else if (processStatus.exit_code === 0) {
      return <Tag color="success" icon={<CheckCircleOutlined />}>成功完成</Tag>
    } else if (processStatus.exit_code === -2) {
      return <Tag color="warning" icon={<StopOutlined />}>已中断</Tag>
    } else if (processStatus.exit_code !== null) {
      return <Tag color="error" icon={<ExclamationCircleOutlined />}>执行失败</Tag>
    }
    
    return <Tag>就绪</Tag>
  }

  return (
    <div>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 控制按钮区域 */}
        <Card size="small" title="处理控制">
          <Space wrap>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Button
                type="primary"
                size="large"
                icon={<PlayCircleOutlined />}
                onClick={handleStartProcess}
                disabled={!canStart || isProcessing}
                loading={isProcessing && !isPolling}
              >
                开始处理
              </Button>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: '6px', background: '#fafafa' }}>
                <RobotOutlined style={{ color: aiAgentEnabled ? '#1890ff' : '#8c8c8c' }} />
                <span style={{ fontSize: '14px', color: '#595959' }}>AI Agent:</span>
                <Switch
                  checked={aiAgentEnabled}
                  onChange={setAiAgentEnabled}
                  disabled={isProcessing}
                  size="small"
                  checkedChildren="启用"
                  unCheckedChildren="禁用"
                />
              </div>
            </div>
            
            {processStatus?.is_running && (
              <Button
                danger
                icon={<StopOutlined />}
                onClick={handleStopScript}
                size="large"
              >
                中断执行
              </Button>
            )}
            
            {isPolling && (
              <Button
                icon={<PauseCircleOutlined />}
                onClick={handleStopMonitoring}
              >
                停止监控
              </Button>
            )}
            
            <Button
              icon={<ReloadOutlined />}
              onClick={handleClearLogs}
              disabled={isProcessing}
            >
              清空日志
            </Button>
            
            {getStatusTag()}
          </Space>
          
          {!canStart && (
            <Alert
              message="请先完成文件上传和参数配置"
              type="warning"
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
        </Card>

        {/* 进度显示区域 */}
        {(isProcessing || progress > 0) && (
          <Card size="small" title="处理进度">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text strong>当前步骤：</Text>
                <Text>{currentStep || '准备中...'}</Text>
              </div>
              
              <Progress
                percent={progress}
                status={isProcessing ? 'active' : progress === 100 ? 'success' : 'normal'}
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#87d068',
                }}
              />
              
              {processStatus && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    开始时间: {processStatus.start_time ? new Date(processStatus.start_time).toLocaleString() : '未开始'}
                    {processStatus.end_time && (
                      <> | 结束时间: {new Date(processStatus.end_time).toLocaleString()}</>
                    )}
                  </Text>
                </div>
              )}
            </Space>
          </Card>
        )}

        {/* 实时日志显示区域 */}
        <Card size="small" title="处理日志" extra={
          <Space size="small">
            <Button 
              size="small" 
              type="text" 
              icon={<VerticalAlignBottomOutlined />}
              onClick={handleJumpToLatest}
              title="跳转到最新日志并释放缓存"
            >
              跳转到最新
            </Button>
            <Text type="secondary" style={{ fontSize: 12 }}>
              实时更新 • 自动滚动
            </Text>
          </Space>
        }>
          <div
            ref={logContainerRef}
            className="log-container"
            style={{
              minHeight: '200px',
              maxHeight: '400px',
              overflow: 'auto',
              background: '#001529',
              color: '#fff',
              padding: '16px',
              borderRadius: '6px',
              fontFamily: 'Courier New, monospace',
              fontSize: '12px',
              lineHeight: '1.5',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all'
            }}
          >
            {displayLogs || '等待开始处理...'}
            {isProcessing && (
              <div style={{ marginTop: '8px' }}>
                <Text style={{ color: '#1890ff' }}>● 正在处理中...</Text>
              </div>
            )}
            {logQueue.length > 0 && (
              <div style={{ marginTop: '4px', opacity: 0.7 }}>
                <Text style={{ color: '#52c41a', fontSize: '11px' }}>● 缓冲中 ({logQueue.length} 条待显示)</Text>
              </div>
            )}
          </div>
        </Card>

        {/* 处理步骤说明 */}
        <Card size="small" title="处理步骤说明">
          <div style={{ fontSize: '12px', color: '#666' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <p style={{ margin: 0 }}>数据处理将按以下顺序执行：</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '4px 8px', background: aiAgentEnabled ? '#e6f7ff' : '#f5f5f5', borderRadius: '4px', border: `1px solid ${aiAgentEnabled ? '#91d5ff' : '#d9d9d9'}` }}>
                <RobotOutlined style={{ color: aiAgentEnabled ? '#1890ff' : '#8c8c8c', fontSize: '12px' }} />
                <span style={{ fontSize: '11px', color: aiAgentEnabled ? '#1890ff' : '#8c8c8c', fontWeight: 500 }}>
                  {aiAgentEnabled ? 'AI增强模式' : '标准模式'}
                </span>
              </div>
            </div>
            <ol style={{ paddingLeft: '20px', margin: 0 }}>
              <li>处理基础考勤数据 (basic_combined.py)</li>
              <li>合并出差数据 (business_combine.py)</li>
              <li>合并请假数据 (freework_combine.py)</li>
              <li>合并加班数据 (overwork_combine.py)</li>
              <li>处理出差变更 (business_chage.py)</li>
              <li>处理请假变更 (freework_chage.py)</li>
              <li>处理加班变更 (overwork_chage.py)</li>
              <li>生成考勤汇总 (attendance_summary.py)</li>
              {aiAgentEnabled && (
                <li style={{ color: '#1890ff', fontWeight: 500 }}>AI智能分析</li>
              )}
            </ol>
            {aiAgentEnabled && (
              <div style={{ marginTop: '8px', padding: '8px', background: '#e6f7ff', borderRadius: '4px', border: '1px solid #91d5ff' }}>
                <Text style={{ fontSize: '11px', color: '#1890ff' }}>
                  <RobotOutlined /> AI增强模式将提供智能数据分析
                </Text>
              </div>
            )}
          </div>
        </Card>
      </Space>
    </div>
  )
}

export default ProcessControl