// 评估服务相关的类型定义

// 判断枚举
export enum JudgementEnum {
  CONFORMANT = "符合",
  NON_CONFORMANT = "不符合", 
  PARTIALLY_CONFORMANT = "部分符合",
  NOT_APPLICABLE = "不涉及",
  UNCONFIRMED = "无法确认"
}

// 证据类型
export interface Evidence {
  id: string;
  finding_id: string;
  doc_id: string;
  start_line: number;
  end_line: number;
}

// 控制项定义
export interface ControlItemDefinition {
  id: string;
  display_id: string;
  content: string;
  parent_id: string | null;
  assessment_guidance: string | null;
  details: {
    condition: string;
    heading: string;
    method: string;
  };
}

// 评估发现
export interface AssessmentFinding {
  id: string;
  job_id: string;
  control_item_def_id: string;
  judgement: JudgementEnum | null;
  comment: string | null;
  supplement: string | null;
  evidences: Evidence[];
  control_item_definition: ControlItemDefinition;
}

// 知识空间链接
export interface KnowledgeSpaceLink {
  ks_id: string;
  role: string; // 'target' or 'reference'
}

// 作业摘要
export interface JobSummary {
  id: string;
  name: string;
  framework_id: string;
  status: string;
  findings_summary: Record<string, number>;
  knowledge_spaces: KnowledgeSpaceLink[];
}

// 作业详情
export interface JobDetail {
  id: string;
  name: string;
  framework_id: string;
  status: string;
  findings: AssessmentFinding[];
  knowledge_spaces: KnowledgeSpaceLink[];
}

// API响应类型
export interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}