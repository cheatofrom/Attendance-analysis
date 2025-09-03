import React, { useState } from 'react'
import { Layout, Typography, Space, Divider } from 'antd'
import FileUpload from './components/FileUpload'
import ConfigForm from './components/ConfigForm'
import ProcessControl from './components/ProcessControl'
import FileDownload from './components/FileDownload'
import './App.css'

const { Content } = Layout
const { Title } = Typography

interface ConfigData {
  year: number
  month: number
  holidays: string[]
}

function App() {
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [configData, setConfigData] = useState<ConfigData | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [processLogs, setProcessLogs] = useState<string>('')
  const [refreshDownloads, setRefreshDownloads] = useState(0)

  const handleUploadComplete = (files: string[]) => {
    setUploadedFiles(files)
  }

  const handleConfigSubmit = (config: ConfigData) => {
    setConfigData(config)
  }

  const handleProcessStart = () => {
    setIsProcessing(true)
    setProcessLogs('')
  }

  const handleProcessComplete = () => {
    setIsProcessing(false)
    setRefreshDownloads(prev => prev + 1)
  }

  const handleLogUpdate = (log: string) => {
    // 限制日志字符串长度，防止超出JavaScript字符串长度限制
    // 保留最新的100KB日志内容
    const maxLength = 100 * 1024; // 100KB
    let newLog = log;
    
    if (log.length > maxLength) {
      // 如果单次日志超过限制，只保留末尾部分
      newLog = log.slice(log.length - maxLength);
    }
    
    setProcessLogs(prev => {
      const combined = prev + newLog + '\n';
      // 如果组合后的日志超过限制，只保留末尾部分
      return combined.length > maxLength ? 
        combined.slice(combined.length - maxLength) : 
        combined;
    });
  }

  const canStartProcess = uploadedFiles.length === 7 && configData !== null

  return (
    <div className="app-container">
      <div className="main-content">
        <div className="header">
          <Title level={1} style={{ color: 'white', margin: 0 }}>
            考勤分析系统
          </Title>
          <p style={{ margin: '8px 0 0 0', opacity: 0.9 }}>
            上传考勤文档，配置分析参数，生成统计报告
          </p>
        </div>
        
        <div className="content-wrapper">
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 文件上传区域 */}
            <div className="section-card">
              <div className="section-header">
                📁 文件上传
              </div>
              <div className="section-content">
                <FileUpload onUploadComplete={handleUploadComplete} />
              </div>
            </div>

            {/* 参数配置区域 */}
            <div className="section-card">
              <div className="section-header">
                ⚙️ 参数配置
              </div>
              <div className="section-content">
                <ConfigForm onConfigSubmit={handleConfigSubmit} />
              </div>
            </div>

            {/* 处理控制区域 */}
            <div className="section-card">
              <div className="section-header">
                🚀 数据处理
              </div>
              <div className="section-content">
                <ProcessControl
                  canStart={canStartProcess}
                  isProcessing={isProcessing}
                  onProcessStart={handleProcessStart}
                  onProcessComplete={handleProcessComplete}
                  onLogUpdate={handleLogUpdate}
                  processLogs={processLogs}
                />
              </div>
            </div>

            {/* 结果下载区域 */}
            <div className="section-card">
              <div className="section-header">
                📥 结果下载
              </div>
              <div className="section-content">
                <FileDownload refreshTrigger={refreshDownloads} />
              </div>
            </div>
          </Space>
        </div>
      </div>
    </div>
  )
}

export default App