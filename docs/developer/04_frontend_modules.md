# 开发者文档：04 - 前端模块深入解析

本章将详细介绍 Kosmos 前端（位于 `/frontend` 目录）的代码结构。前端项目使用 React 和 TypeScript 构建，旨在提供一个功能丰富、体验流畅的用户界面。

## 技术栈

- **框架**: [React](https://reactjs.org/)
- **语言**: [TypeScript](https://www.typescriptlang.org/)
- **UI 组件库**: (根据目录结构推断，可能为 Ant Design, Material-UI, 或自定义组件)
- **CSS 方案**: [Tailwind CSS](https://tailwindcss.com/) (根据 `tailwind.config.js` 推断)
- **状态管理**: (根据 `stores` 目录推断，可能为 Zustand, MobX, 或 Redux Toolkit)
- **HTTP 客户端**: [Axios](https://axios-http.com/) 或 Fetch API (封装在 `services` 中)

## 目录结构总览

```
/frontend
├── public/               # 静态资源，如 index.html, favicon.ico
├── src/                  # 源代码主目录
│   ├── App.tsx             # React 应用根组件
│   ├── index.tsx           # 应用入口，渲染 App 组件
│   ├── components/         # 可复用的 UI 组件
│   │   ├── layout/         # 布局组件 (如导航栏, 侧边栏)
│   │   ├── KnowledgeBase/  # 知识库相关组件
│   │   └── ...
│   ├── pages/              # 页面级组件
│   │   ├── auth/           # 认证页面 (登录, 注册)
│   │   └── KnowledgeBase/  # 知识库主页面
│   ├── services/           # API 服务层
│   │   ├── apiClient.ts    # 封装的 HTTP 客户端实例
│   │   ├── documentService.ts # 文档相关 API 调用
│   │   └── ...
│   ├── stores/             # 全局状态管理
│   │   └── authStore.ts    # 认证状态
│   ├── styles/             # 全局样式
│   │   └── globals.css
│   ├── types/              # TypeScript 类型定义
│   │   ├── document.ts
│   │   └── ...
│   └── utils/              # 通用工具函数
├── package.json          # 项目依赖和脚本
└── tsconfig.json         # TypeScript 编译器配置
```

## 各模块职责详解

### `src/components/`
此目录存放**可复用的 UI 组件**。这些组件是构成页面的基础模块，它们通常是无状态的或拥有自己的局部状态，不直接与路由或全局状态强耦合。
- **`layout/`**: 包含构成应用整体布局的组件，如顶部的导航栏、侧边的菜单栏、页面页脚等。
- **`KnowledgeBase/`**, **`DocumentManage/`**, **`SemanticSearch/`**: 这些子目录按照功能领域组织相关的组件。例如，`SemanticSearch/` 可能包含搜索输入框、结果列表、筛选器等组件。

### `src/pages/`
此目录存放**页面级组件**。每个文件或子目录通常对应应用中的一个特定路由（页面）。页面组件负责组合 `components` 中的原子组件，构建完整的用户界面，并处理页面级别的业务逻辑和状态。
- **`auth/`**: 包含与用户认证相关的页面，如登录页 (`Login.tsx`) 和注册页 (`Register.tsx`)。
- **`KnowledgeBase/`**: 包含与单个知识库相关的页面，如知识库详情页、文档管理页、搜索结果页���。

### `src/services/`
API 服务层，负责封装所有与后端 API 的通信。这一层将数据获取的逻辑与 UI 组件分离，使得组件更纯粹，代码更易于维护。
- **`apiClient.ts`**: 创建并配置一个中心化的 HTTP 客户端实例（通常是 Axios）。这里会处理一些通用逻辑，比如设置 API 的 `baseURL`、统一处理请求头（如附加认证 Token）、以及全局的错误处理。
- **`knowledgeBase.ts`**, **`documentService.ts`**, etc.: 每个文件对应后端的一个或多个 API `router`，封装了具体的 API 调用函数。例如，`knowledgeBase.ts` 会包含 `getKnowledgeBases()`, `createKnowledgeBase()` 等函数。

### `src/stores/`
全局状态管理目录。当多个组件需要共享或响应同一个状态时，该状态就应该被提升到全局 store 中进行管理。
- **`authStore.ts`**: 一个典型的例子，用于管理用户的登录状态、JWT Token 和个人信息。应用中的任何组件都可以从这个 store 中读取认证信息，或者触发登录/登出的 action。

### `src/types/`
存放所有自定义的 TypeScript 类型定义。这些类型通常与后端 API 的 `schemas` 相对应，为前端应用提供了强大的类型安全保障。
- **`knowledgeBase.ts`**, **`document.ts`**: 定义了 `KnowledgeBase`, `Document`, `Chunk` 等核心数据结构的类型接口。这使得在编码时可以获得自动补全和编译时错误检查，极大提升了开发效率和代码质量。

### `src/utils/`
存放项目范围内的通用工具函数。这些函数通常是纯函数，不依赖于特定的组件或状态。例如，日期格式化函数、数据转换函数、或者一些自定义的 React Hooks。

### `App.tsx` 和 `index.tsx`
- **`index.tsx`**: 应用的起点。它负责将根组件 `App` 渲染到 `public/index.html` 的 DOM 节点上。通常还会在这里包裹全局的上下文提供者（Context Providers），如状态管理库的 Provider、UI 库的主题 Provider 等。
- **`App.tsx`**: 应用的根组件。它通常负责设置应用的路由系统（如使用 `react-router-dom`），并渲染与当前 URL 匹配的页面组件。

理解前端的模块化结构后，您可以快速地找到需要修改或查看的代码：
- **修改 UI 样式？** -> `components/` 或 `pages/` 中对应的组件。
- **处理 API 数据？** -> `services/` 中对应的服务。
- **管理全局状态？** -> `stores/` 中对应的 store。
- **添加新页面？** -> 在 `pages/` 中创建新组件，并在 `App.tsx` 中为其配置路由。
