import React, { useState, useEffect } from 'react'
import { Table, Button, Space, Typography, Card, message, Tag, Tooltip, Empty, Spin, Popconfirm } from 'antd'
import { DownloadOutlined, ReloadOutlined, FileExcelOutlined, ClockCircleOutlined, DeleteOutlined, ExclamationCircleOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import axios from 'axios'
import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

// 扩展 dayjs 以支持相对时间
dayjs.extend(relativeTime)

const { Text, Title } = Typography

interface FileDownloadProps {
  refreshTrigger: number
}

interface FileInfo {
  name: string
  size: number
  size_mb: number
  modified_time: string
  download_url: string
}

interface FilesResponse {
  success: boolean
  files: FileInfo[]
  total_count: number
  message?: string
}

const FileDownload: React.FC<FileDownloadProps> = ({ refreshTrigger }) => {
  const [files, setFiles] = useState<FileInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [downloading, setDownloading] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  // 获取文件列表
  const fetchFiles = async () => {
    setLoading(true)
    try {
      const response = await axios.get<FilesResponse>('/api/files')
      
      if (response.data.success) {
        setFiles(response.data.files)
      } else {
        message.warning(response.data.message || '获取文件列表失败')
        setFiles([])
      }
    } catch (error) {
      console.error('Failed to fetch files:', error)
      message.error('获取文件列表失败，请检查网络连接')
      setFiles([])
    } finally {
      setLoading(false)
    }
  }

  // 初始加载和刷新触发
  useEffect(() => {
    fetchFiles()
  }, [refreshTrigger])

  // 下载文件
  const handleDownload = async (file: FileInfo) => {
    setDownloading(file.name)
    
    try {
      // 直接使用浏览器下载
      const response = await axios.get(file.download_url, {
        responseType: 'blob'
      })
      
      // 创建下载链接
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', file.name)
      document.body.appendChild(link)
      link.click()
      
      // 清理
      link.remove()
      window.URL.revokeObjectURL(url)
      
      message.success(`文件 ${file.name} 下载成功`)
    } catch (error) {
      console.error('Download failed:', error)
      message.error(`下载文件 ${file.name} 失败`)
    } finally {
      setDownloading(null)
    }
  }

  // 删除文件
  const handleDelete = async (file: FileInfo) => {
    setDeleting(file.name)
    try {
      // 使用axios保持与其他API请求一致的基础URL配置
      const response = await axios.delete(`/api/delete/${encodeURIComponent(file.name)}`)
      
      message.success(`文件 ${file.name} 删除成功`)
      // 删除成功后刷新文件列表
      await fetchFiles()
    } catch (error) {
      console.error('Delete failed:', error)
      message.error(`删除文件 ${file.name} 失败: ${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setDeleting(null)
    }
  }

  // 格式化文件大小
  const formatFileSize = (sizeInBytes: number): string => {
    if (sizeInBytes < 1024) {
      return `${sizeInBytes} B`
    } else if (sizeInBytes < 1024 * 1024) {
      return `${(sizeInBytes / 1024).toFixed(1)} KB`
    } else {
      return `${(sizeInBytes / (1024 * 1024)).toFixed(2)} MB`
    }
  }

  // 格式化时间
  const formatTime = (timeString: string): string => {
    return dayjs(timeString).format('YYYY-MM-DD HH:mm:ss')
  }

  // 获取文件类型标签
  const getFileTypeTag = (fileName: string) => {
    if (fileName.toLowerCase().endsWith('.xlsx')) {
      return <Tag color="green" icon={<FileExcelOutlined />}>Excel</Tag>
    }
    return <Tag>文件</Tag>
  }

  // 表格列定义
  const columns: ColumnsType<FileInfo> = [
    {
      title: '文件名',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <Space>
          {getFileTypeTag(name)}
          <Text strong>{name}</Text>
        </Space>
      ),
      sorter: (a, b) => a.name.localeCompare(b.name),
    },
    {
      title: '文件大小',
      dataIndex: 'size',
      key: 'size',
      render: (size: number) => (
        <Text type="secondary">{formatFileSize(size)}</Text>
      ),
      sorter: (a, b) => a.size - b.size,
      width: 120,
    },
    {
      title: '修改时间',
      dataIndex: 'modified_time',
      key: 'modified_time',
      render: (time: string) => (
        <Tooltip title={formatTime(time)}>
          <Space>
            <ClockCircleOutlined style={{ color: '#999' }} />
            <Text type="secondary">{dayjs(time).fromNow()}</Text>
          </Space>
        </Tooltip>
      ),
      sorter: (a, b) => dayjs(a.modified_time).unix() - dayjs(b.modified_time).unix(),
      defaultSortOrder: 'descend',
      width: 150,
    },
    {
      title: '操作',
      key: 'action',
      render: (_, file) => (
        <Space size="small">
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => handleDownload(file)}
            loading={downloading === file.name}
            size="small"
            disabled={deleting === file.name}
          >
            下载
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定要删除文件 "${file.name}" 吗？此操作不可恢复。`}
            onConfirm={() => handleDelete(file)}
            okText="确认删除"
            cancelText="取消"
            okType="danger"
            icon={<ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              loading={deleting === file.name}
              size="small"
              disabled={downloading === file.name}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
      width: 160,
    },
  ]

  return (
    <div>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 头部信息 */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Text strong>生成的文件</Text>
            {files.length > 0 && (
              <Text type="secondary" style={{ marginLeft: 8 }}>
                共 {files.length} 个文件
              </Text>
            )}
          </div>
          
          <Button
            icon={<ReloadOutlined />}
            onClick={fetchFiles}
            loading={loading}
          >
            刷新列表
          </Button>
        </div>

        {/* 文件列表 */}
        <Card size="small">
          {loading ? (
            <div style={{ textAlign: 'center', padding: '40px' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">正在获取文件列表...</Text>
              </div>
            </div>
          ) : files.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div>
                  <Text type="secondary">暂无生成的文件</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    完成数据处理后，生成的文件将显示在这里
                  </Text>
                </div>
              }
            />
          ) : (
            <Table
              columns={columns}
              dataSource={files}
              rowKey="name"
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total, range) => 
                  `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
              }}
              size="small"
            />
          )}
        </Card>

        {/* 下载说明 */}
        {files.length > 0 && (
          <Card size="small" title="下载说明">
            <div style={{ fontSize: '12px', color: '#666' }}>
              <ul style={{ paddingLeft: '20px', margin: 0 }}>
                <li>点击"下载"按钮可下载对应的Excel文件</li>
                <li>文件按修改时间倒序排列，最新生成的文件在最前面</li>
                <li>建议下载最新生成的文件以获取最准确的分析结果</li>
                <li>如果下载失败，请检查网络连接或联系管理员</li>
              </ul>
            </div>
          </Card>
        )}

        {/* 批量下载功能 */}
        {files.length > 1 && (
          <div style={{ textAlign: 'center' }}>
            <Button
              type="dashed"
              size="large"
              onClick={() => {
                files.forEach((file, index) => {
                  setTimeout(() => handleDownload(file), index * 1000) // 间隔1秒下载
                })
              }}
              disabled={downloading !== null}
            >
              批量下载所有文件
            </Button>
            <div style={{ marginTop: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                将依次下载所有文件，每个文件间隔1秒
              </Text>
            </div>
          </div>
        )}
      </Space>
    </div>
  )
}

export default FileDownload