import React, { useState, useRef } from 'react'
import { Upload, Button, message, Progress, Space, Typography, List, Tag } from 'antd'
import { UploadOutlined, DeleteOutlined, CheckCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import type { UploadFile, UploadProps } from 'antd/es/upload/interface'
import axios from 'axios'

const { Text } = Typography

interface FileUploadProps {
  onUploadComplete: (files: string[]) => void
}

interface FileStatus {
  name: string
  status: 'pending' | 'uploading' | 'success' | 'error'
  progress: number
  size?: number
}

const REQUIRED_FILES = [
  { key: 'basic', name: 'basic.xlsx', label: '基础考勤数据' },
  { key: 'business01', name: 'business01.xlsx', label: '飞书出差' },
  { key: 'business02', name: 'business02.xlsx', label: '钉钉出差' },
  { key: 'freework01', name: 'freework01.xlsx', label: '飞书请假' },
  { key: 'freework02', name: 'freework02.xlsx', label: '钉钉请假' },
  { key: 'overwork01', name: 'overwork01.xlsx', label: '飞书加班' },
  { key: 'overwork02', name: 'overwork02.xlsx', label: '钉钉加班' }
]

const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete }) => {
  const [fileStatuses, setFileStatuses] = useState<Record<string, FileStatus>>(
    REQUIRED_FILES.reduce((acc, file) => {
      acc[file.key] = {
        name: file.name,
        status: 'pending',
        progress: 0
      }
      return acc
    }, {} as Record<string, FileStatus>)
  )
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({})

  const updateFileStatus = (key: string, updates: Partial<FileStatus>) => {
    setFileStatuses(prev => ({
      ...prev,
      [key]: { ...prev[key], ...updates }
    }))
  }

  const handleFileSelect = (key: string, file: File) => {
    if (!file.name.toLowerCase().endsWith('.xlsx')) {
      message.error('请选择Excel文件(.xlsx格式)')
      return
    }

    updateFileStatus(key, {
      status: 'pending',
      progress: 0,
      size: file.size
    })
  }

  const uploadSingleFile = async (key: string, file: File): Promise<boolean> => {
    updateFileStatus(key, { status: 'uploading', progress: 0 })

    try {
      const formData = new FormData()
      formData.append(key, file)

      await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            updateFileStatus(key, { progress })
          }
        }
      })

      updateFileStatus(key, { status: 'success', progress: 100 })
      return true
    } catch (error) {
      console.error(`Upload failed for ${key}:`, error)
      updateFileStatus(key, { status: 'error', progress: 0 })
      message.error(`上传 ${REQUIRED_FILES.find(f => f.key === key)?.label} 失败`)
      return false
    }
  }

  const handleUploadAll = async () => {
    const filesToUpload: { key: string; file: File }[] = []

    // 收集所有选中的文件
    for (const fileConfig of REQUIRED_FILES) {
      const input = fileInputRefs.current[fileConfig.key]
      if (input?.files?.[0]) {
        filesToUpload.push({
          key: fileConfig.key,
          file: input.files[0]
        })
      }
    }

    if (filesToUpload.length !== 7) {
      message.error('请选择所有7个必需的文件')
      return
    }

    setIsUploading(true)

    try {
      // 创建包含所有文件的FormData
      const formData = new FormData()
      filesToUpload.forEach(({ key, file }) => {
        formData.append(key, file)
      })

      // 更新所有文件状态为上传中
      filesToUpload.forEach(({ key }) => {
        updateFileStatus(key, { status: 'uploading', progress: 0 })
      })

      const response = await axios.post('/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            // 更新所有文件的进度
            filesToUpload.forEach(({ key }) => {
              updateFileStatus(key, { progress })
            })
          }
        }
      })

      if (response.data.success) {
        // 更新所有文件状态为成功
        filesToUpload.forEach(({ key }) => {
          updateFileStatus(key, { status: 'success', progress: 100 })
        })
        
        message.success('所有文件上传成功！')
        onUploadComplete(REQUIRED_FILES.map(f => f.name))
      } else {
        throw new Error(response.data.errors?.join(', ') || '上传失败')
      }
    } catch (error) {
      console.error('Upload failed:', error)
      
      // 更新所有文件状态为失败
      filesToUpload.forEach(({ key }) => {
        updateFileStatus(key, { status: 'error', progress: 0 })
      })
      
      message.error('文件上传失败，请重试')
    } finally {
      setIsUploading(false)
    }
  }

  const handleRemoveFile = (key: string) => {
    const input = fileInputRefs.current[key]
    if (input) {
      input.value = ''
    }
    updateFileStatus(key, {
      status: 'pending',
      progress: 0,
      size: undefined
    })
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'error':
        return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
      case 'uploading':
        return <div className="file-status uploading" />
      default:
        return <div className="file-status" />
    }
  }

  const getStatusTag = (status: string) => {
    switch (status) {
      case 'success':
        return <Tag color="success">已上传</Tag>
      case 'error':
        return <Tag color="error">上传失败</Tag>
      case 'uploading':
        return <Tag color="processing">上传中</Tag>
      default:
        return <Tag>待上传</Tag>
    }
  }

  const allFilesSelected = REQUIRED_FILES.every(file => {
    const input = fileInputRefs.current[file.key]
    return input?.files?.[0]
  })

  const allFilesUploaded = REQUIRED_FILES.every(file => 
    fileStatuses[file.key]?.status === 'success'
  )

  return (
    <div>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Text strong>请选择以下7个Excel文件：</Text>
          <List
            size="small"
            dataSource={REQUIRED_FILES}
            renderItem={(file) => {
              const status = fileStatuses[file.key]
              return (
                <List.Item
                  actions={[
                    status.status !== 'pending' && (
                      <Button
                        type="text"
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={() => handleRemoveFile(file.key)}
                        disabled={isUploading}
                      />
                    )
                  ]}
                >
                  <List.Item.Meta
                    avatar={getStatusIcon(status.status)}
                    title={
                      <Space>
                        <span>{file.label}</span>
                        {getStatusTag(status.status)}
                      </Space>
                    }
                    description={
                      <div>
                        <input
                          ref={(el) => {
                            fileInputRefs.current[file.key] = el
                          }}
                          type="file"
                          accept=".xlsx"
                          onChange={(e) => {
                            const selectedFile = e.target.files?.[0]
                            if (selectedFile) {
                              handleFileSelect(file.key, selectedFile)
                            }
                          }}
                          disabled={isUploading}
                          style={{ marginTop: 8 }}
                        />
                        {status.status === 'uploading' && (
                          <Progress
                            percent={status.progress}
                            size="small"
                            style={{ marginTop: 8 }}
                          />
                        )}
                        {status.size && (
                          <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                            文件大小: {(status.size / 1024 / 1024).toFixed(2)} MB
                          </Text>
                        )}
                      </div>
                    }
                  />
                </List.Item>
              )
            }}
          />
        </div>

        <div style={{ textAlign: 'center' }}>
          <Button
            type="primary"
            size="large"
            icon={<UploadOutlined />}
            onClick={handleUploadAll}
            loading={isUploading}
            disabled={!allFilesSelected || allFilesUploaded}
          >
            {allFilesUploaded ? '所有文件已上传' : '上传所有文件'}
          </Button>
        </div>

        {allFilesUploaded && (
          <div style={{ textAlign: 'center', padding: '16px', background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: '6px' }}>
            <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
            <Text type="success">所有文件上传完成，可以进行下一步操作</Text>
          </div>
        )}
      </Space>
    </div>
  )
}

export default FileUpload