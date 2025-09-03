import React, { useState, useEffect } from 'react'
import { Form, DatePicker, Select, Button, Space, Typography, Card, Row, Col, Tag, message, Checkbox } from 'antd'
import { CalendarOutlined, SettingOutlined, CheckCircleOutlined } from '@ant-design/icons'
import dayjs, { Dayjs } from 'dayjs'
import axios from 'axios'

const { Text, Title } = Typography
const { Option } = Select

interface ConfigFormProps {
  onConfigSubmit: (config: { year: number; month: number; holidays: string[] }) => void
}

interface HolidayOption {
  value: string
  label: string
  disabled?: boolean
}

const ConfigForm: React.FC<ConfigFormProps> = ({ onConfigSubmit }) => {
  const [form] = Form.useForm()
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(dayjs())
  const [holidayOptions, setHolidayOptions] = useState<HolidayOption[]>([])
  const [selectedHolidays, setSelectedHolidays] = useState<string[]>([])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isConfigured, setIsConfigured] = useState(false)

  // 生成指定年月的所有日期选项
  const generateDateOptions = (year: number, month: number): HolidayOption[] => {
    const daysInMonth = dayjs(`${year}-${month}`).daysInMonth()
    const options: HolidayOption[] = []

    for (let day = 1; day <= daysInMonth; day++) {
      const date = dayjs(`${year}-${month}-${day}`)
      const dayOfWeek = date.day() // 0=Sunday, 6=Saturday
      const isWeekend = dayOfWeek === 0 || dayOfWeek === 6
      
      options.push({
        value: day.toString().padStart(2, '0'),
        label: `${day}日 (${['日', '一', '二', '三', '四', '五', '六'][dayOfWeek]})`,
        disabled: false // 可以选择任何日期作为休息日
      })
    }

    return options
  }

  // 当选择的年月改变时，更新日期选项
  useEffect(() => {
    if (selectedDate) {
      const year = selectedDate.year()
      const month = selectedDate.month() + 1
      const options = generateDateOptions(year, month)
      setHolidayOptions(options)
      
      // 清空之前选择的休息日
      setSelectedHolidays([])
      form.setFieldsValue({ holidays: [] })
    }
  }, [selectedDate, form])

  // 处理日期选择
  const handleDateChange = (date: Dayjs | null) => {
    setSelectedDate(date)
    setIsConfigured(false)
  }

  // 处理休息日选择
  const handleHolidayChange = (values: string[]) => {
    setSelectedHolidays(values)
    setIsConfigured(false)
  }

  // 快速选择周末
  const selectWeekends = () => {
    if (!selectedDate) return
    
    const year = selectedDate.year()
    const month = selectedDate.month() + 1
    const weekends: string[] = []
    
    const daysInMonth = dayjs(`${year}-${month}`).daysInMonth()
    for (let day = 1; day <= daysInMonth; day++) {
      const date = dayjs(`${year}-${month}-${day}`)
      const dayOfWeek = date.day()
      if (dayOfWeek === 0 || dayOfWeek === 6) { // 周日或周六
        weekends.push(day.toString().padStart(2, '0'))
      }
    }
    
    setSelectedHolidays(weekends)
    form.setFieldsValue({ holidays: weekends })
  }

  // 清空选择
  const clearSelection = () => {
    setSelectedHolidays([])
    form.setFieldsValue({ holidays: [] })
    setIsConfigured(false)
  }

  // 提交配置
  const handleSubmit = async (values: any) => {
    if (!selectedDate) {
      message.error('请选择年月')
      return
    }

    const year = selectedDate.year()
    const month = selectedDate.month() + 1
    const holidays = values.holidays || []

    setIsSubmitting(true)

    try {
      // 调用后端API更新配置
      const response = await axios.post('/api/config/update_config', {
        year,
        month,
        holidays
      })

      if (response.data.status === 'success') {
        message.success('配置更新成功！')
        setIsConfigured(true)
        onConfigSubmit({ year, month, holidays })
      } else {
        throw new Error('配置更新失败')
      }
    } catch (error) {
      console.error('Config update failed:', error)
      message.error('配置更新失败，请重试')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getWorkingDays = () => {
    if (!selectedDate) return 0
    
    const year = selectedDate.year()
    const month = selectedDate.month() + 1
    const daysInMonth = dayjs(`${year}-${month}`).daysInMonth()
    
    return daysInMonth - selectedHolidays.length
  }

  return (
    <div>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{
          date: dayjs(),
          holidays: []
        }}
      >
        <Row gutter={24}>
          <Col xs={24} md={12}>
            <Card size="small" title={<><CalendarOutlined /> 选择年月</>}>
              <Form.Item
                name="date"
                label="分析年月"
                rules={[{ required: true, message: '请选择年月' }]}
              >
                <DatePicker
                  picker="month"
                  placeholder="选择年月"
                  style={{ width: '100%' }}
                  onChange={handleDateChange}
                  value={selectedDate}
                  format="YYYY年MM月"
                />
              </Form.Item>
              
              {selectedDate && (
                <div style={{ marginTop: 16 }}>
                  <Text strong>选择的月份：</Text>
                  <Tag color="blue" style={{ marginLeft: 8 }}>
                    {selectedDate.format('YYYY年MM月')}
                  </Tag>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    该月共 {dayjs(selectedDate).daysInMonth()} 天
                  </Text>
                </div>
              )}
            </Card>
          </Col>
          
          <Col xs={24} md={12}>
            <Card 
              size="small" 
              title={<><SettingOutlined /> 配置休息日</>}
              extra={
                <Space>
                  <Button size="small" onClick={selectWeekends}>
                    选择周末
                  </Button>
                  <Button size="small" onClick={clearSelection}>
                    清空
                  </Button>
                </Space>
              }
            >
              <Form.Item
                name="holidays"
                label="休息日"
                help="选择该月的休息日（不计入出勤天数）"
              >
                <Checkbox.Group
                  options={holidayOptions.map(option => ({
                    label: option.label,
                    value: option.value,
                    disabled: option.disabled
                  }))}
                  value={selectedHolidays}
                  onChange={handleHolidayChange}
                  style={{ 
                    display: 'grid', 
                    gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                    gap: '8px'
                  }}
                />
              </Form.Item>
              
              {selectedHolidays.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Text strong>已选择休息日：</Text>
                  <div style={{ marginTop: 8 }}>
                    {selectedHolidays.map(day => (
                      <Tag key={day} color="orange" style={{ marginBottom: 4 }}>
                        {day}日
                      </Tag>
                    ))}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      应出勤天数：{getWorkingDays()} 天
                    </Text>
                  </div>
                </div>
              )}
            </Card>
          </Col>
        </Row>

        <div style={{ textAlign: 'center', marginTop: 24 }}>
          <Button
            type="primary"
            size="large"
            htmlType="submit"
            loading={isSubmitting}
            disabled={!selectedDate || isConfigured}
            icon={isConfigured ? <CheckCircleOutlined /> : <SettingOutlined />}
          >
            {isConfigured ? '配置已保存' : '保存配置'}
          </Button>
        </div>
      </Form>

      {isConfigured && (
        <div style={{ 
          textAlign: 'center', 
          marginTop: 16, 
          padding: '16px', 
          background: '#f6ffed', 
          border: '1px solid #b7eb8f', 
          borderRadius: '6px' 
        }}>
          <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
          <Text type="success">
            配置已保存：{selectedDate?.format('YYYY年MM月')}，
            休息日 {selectedHolidays.length} 天，应出勤 {getWorkingDays()} 天
          </Text>
        </div>
      )}
    </div>
  )
}

export default ConfigForm