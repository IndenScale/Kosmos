# 开发者文档：02 - 部署与配置指南

本指南将引导您完成在本地开发环境中部署 Kosmos 的所有步骤。我们将分别设置后端、前端以及所需的依赖服务。

## 1. 环境准备 (Prerequisites)

在开始之前，请确保您的系统上安装了以下软件：

- **Python**: 3.9 或更高版本。
- **Node.js**: 16.x 或更高版本 (附带 npm)。
- **Docker** 和 **Docker Compose**: 用于快速启动数据库等依赖服务。这是最推荐的方式。
- **Git**: 用于克隆项目仓库。

## 2. 获取代码

首先，克隆 Kosmos 的代码仓库到您的本地机器：

```bash
git clone <your-kosmos-repo-url>
cd Kosmos
```

## 3. 部署依赖服务 (Docker)

Kosmos 依赖一个关系型数据库（如 PostgreSQL）和 Milvus 向量数据库。我们强烈建议使用 Docker Compose 来一键启动和管理这些服务。

项目根目录下应包含一个 `docker-compose.yml` 文件（如果不存在，您可能需要根据 `docker-compose.example.yml` 创建一个），其���容大致如下：

```yaml
# 这是一个示例 docker-compose.yml，请以项目中的为准
version: '3.8'

services:
  postgres:
    image: postgres:13
    container_name: kosmos_postgres
    environment:
      POSTGRES_DB: kosmos_db
      POSTGRES_USER: kosmos_user
      POSTGRES_PASSWORD: kosmos_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  milvus:
    image: milvusdb/milvus:v2.3.x-cpu # 请根据项目需求选择版本
    container_name: kosmos_milvus
    ports:
      - "19530:19530" # Milvus gRPC port
      - "9091:9091"   # Milvus HTTP port
    volumes:
      - milvus_data:/milvus/data

volumes:
  postgres_data:
  milvus_data:
```

在项目根目录下，执行以下命令启动服务：

```bash
docker-compose up -d
```

等待几分钟，直到 PostgreSQL 和 Milvus 完全启动。

## 4. 后端部署 (Backend Setup)

1.  **创建并激活 Python 虚拟环境**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

2.  **安装依赖**:
    所有后端依赖都列在 `requirements.txt` 文件中。
    ```bash
    pip install -r requirements.txt
    ```

3.  **配置环境变量**:
    后端服务的配置通过环境变量加载。请根据 `.env.example` 文件创建一个 `.env` 文件：
    ```bash
    cp .env.example .env
    ```
    然后，编辑 `.env` 文件，确保数据库和 Milvus 的连接信息与您在 `docker-compose.yml` 中设置的一致。

    一个典型的 `.env` 文件内容如下：
    ```dotenv
    # 数据库 URL
    DATABASE_URL="postgresql://kosmos_user:kosmos_password@localhost:5432/kosmos_db"

    # Milvus 配置
    MILVUS_HOST="localhost"
    MILVUS_PORT="19530"

    # JWT 密钥
    SECRET_KEY="your-super-secret-key"
    ALGORITHM="HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    # 其他模型或服务配置...
    ```

4.  **数据库迁移**:
    (此步骤取决于项目是否使用 Alembic 等迁移工具) 如果项目有数据库迁移脚本，需要运行它们来初始化数据库表结构。
    ```bash
    # 示例命令，具体请参考项目脚本
    # alembic upgrade head
    ```
    如果项目提供了 SQL 初始化脚本 (如 `db/scripts/`), 您可能需要手动执行它们。

5.  **启动后端服务**:
    后端服务由 `app/main.py` 启动。
    ```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --timeout-keep-alive 600
```
    `--reload` 参数会使服务在代码变更时自动重启，非常适合开发环境。现在，您应该可以在 `http://localhost:8000/docs` 看到 FastAPI 自动生成的 API 文档。

## 5. 前端部署 (Frontend Setup)

1.  **进入前端目录**:
    ```bash
    cd frontend
    ```

2.  **安装依赖**:
    所有前端依赖都列在 `package.json` 文件中。
    ```bash
    npm install
    ```

3.  **配置环境变量**:
    与后端类似，前端也可能需要配置环境变量来指定 API 服务器的地址。根据 `frontend/.env_example` 创建一个 `.env` 文件。
    ```bash
    # 示例 .env 文件
    REACT_APP_API_BASE_URL=http://localhost:8000
    ```

4.  **启动前端开发服务器**:
    ```bash
    npm start
    ```
    这将启动一个开发服务器，通常在 `http://localhost:3000`。浏览器会自动打开应用页面。所有对前端代码的修改都会热更新到浏览器上。

## 总结

至此，您已经成功在本地运���了 Kosmos 的完整开发环境。

- **前端访问**: `http://localhost:3000`
- **后端 API**: `http://localhost:8000`
- **PostgreSQL**: `localhost:5432`
- **Milvus**: `localhost:19530`

现在您可以开始探索代码、开发新功能或修复问题了。
