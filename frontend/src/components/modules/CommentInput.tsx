import React from 'react'
import { Input, Button, Space, Typography } from 'antd'

const { TextArea } = Input
const { Text } = Typography

interface CommentInputProps {
  activeControl: string | null
}

const CommentInput: React.FC<CommentInputProps> = ({ activeControl }) => {
  const [comment, setComment] = React.useState('')
  
  const handleSubmit = () => {
    if (comment.trim() && activeControl) {
      console.log(`针对控制项 ${activeControl} 的评论:`, comment)
      setComment('')
    }
  }
  
  if (!activeControl) {
    return (
      <div style={{ textAlign: 'center' }}>
        <Text type="secondary">请选择一个控制项以添加评论</Text>
      </div>
    )
  }
  
  return (
    <div>
      <div style={{ marginBottom: '8px' }}>
        <Text strong>针对控制项 {activeControl} 的修改意见:</Text>
      </div>
      <TextArea
        rows={3}
        placeholder="请输入您的修改意见..."
        value={comment}
        onChange={e => setComment(e.target.value)}
      />
      <div style={{ marginTop: '8px', textAlign: 'right' }}>
        <Space>
          <Button onClick={() => setComment('')}>清空</Button>
          <Button type="primary" onClick={handleSubmit}>
            提交
          </Button>
        </Space>
      </div>
    </div>
  )
}

export default CommentInput