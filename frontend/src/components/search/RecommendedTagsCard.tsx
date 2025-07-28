import React from 'react';
import { Card, Typography, Tooltip } from 'antd';
import { RecommendedTagsProps } from '../../types/search';

const { Text } = Typography;

export const RecommendedTagsCard: React.FC<RecommendedTagsProps> = ({
  tags,
  onTagClick,
  searchResultsLength
}) => {
  if (tags.length === 0) return null;

  // 计算理想标签偏移 (ITD) - 与后端算法保持一致
  // const calculateITD = (count: number, totalResults: number) => {
  //   const idealPosition = totalResults / 2;
  //   return Math.abs(count - idealPosition);
  // };

  return (
    <Card
      title={
        <div className="flex items-center space-x-2">
          <span>推荐标签</span>
          <Tooltip title="基于搜索结果推荐的相关标签，点击可添加到搜索条件中">
            <Text type="secondary" className="text-xs">
              (智能推荐)
            </Text>
          </Tooltip>
        </div>
      }
      className="sticky top-4 shadow-md"
      headStyle={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #e9ecef' }}
    >
      <div>
        {tags.map(({ tag, count, relevance }, index) => {
          // const itd = calculateITD(count, searchResultsLength);
          
          return (
            <div key={tag}>
              <div
                className="p-3 cursor-pointer hover:bg-blue-50 transition-all duration-200"
                onClick={() => onTagClick(tag)}
              >
                {/* 第一行：标签文本 - 左对齐，粗体 */}
                <div className="flex justify-start mb-2">
                  <Text 
                    strong 
                    className="text-base text-gray-800 font-bold"
                  >
                    {tag}
                  </Text>
                </div>
                
                {/* 第二行：出现次数和相关度 */}
                <div className="flex items-center justify-between text-xs">
                  <Text type="secondary" className="bg-gray-100 px-2 py-1 rounded">
                    出现: {count}次
                  </Text>
                  {/* ITD相关显示已注销 */}
                  {/* <div className="flex items-center space-x-2">
                    <Text type="secondary" className="bg-gray-100 px-2 py-1 rounded">
                      出现: {count}次
                    </Text>
                    <Tooltip title={`理想标签偏移值，越小越好。当前值: ${itd.toFixed(2)}`}>
                      <Text 
                        className={`px-2 py-1 rounded font-mono ${
                          itd < 2 ? 'bg-green-100 text-green-700' :
                          itd < 5 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}
                      >
                        ITD: {itd.toFixed(1)}
                      </Text>
                    </Tooltip>
                  </div> */}
                  <Tooltip title="基于算法计算的相关度分数，值越高表示越相关">
                    <Text 
                      type="secondary" 
                      className="bg-blue-100 px-2 py-1 rounded font-mono"
                    >
                      相关度: {relevance.toFixed(3)}
                    </Text>
                  </Tooltip>
                </div>
              </div>
              
              {/* 分割线 - 除了最后一个标签 */}
              {index < tags.length - 1 && (
                <div className="border-b border-gray-200"></div>
              )}
            </div>
          );
        })}
      </div>
      
      {/* 算法说明已注销 */}
      {/* <div className="mt-4 pt-3 border-t border-gray-200">
        <Text type="secondary" className="text-xs">
          <div className="space-y-1">
            <div><strong>相关度计算:</strong> 基于ITD(理想标签偏移)算法</div>
            <div><strong>ITD公式:</strong> |出现次数 - 结果总数/2|</div>
            <div><strong>相关度公式:</strong> 1 - (ITD / 最大可能ITD)</div>
            <div><strong>排序规则:</strong> 相关度降序 → 出现次数降序</div>
          </div>
        </Text>
      </div> */}
    </Card>
  );
};