# 医院叙事生成助手 - Hospital Narrative Assistant

基于**大语言模型（LLM）**与**Neo4j医疗知识图谱**双引擎驱动的医院科室历史数据智能分析与叙事生成平台。

为科室管理者与临床医生提供从**数据统计分析**到**深度医疗叙事**的完整智能辅助能力。

---

## 🎯 核心能力

### 📊 一、统计分析与报告
基于Excel原始数据进行多维度统计分析，结合大模型自动生成结构化报告。

| 功能 | 说明 |
|------|------|
| **数据概览** | 整合入院/出院/检查/检验/手术等多源数据，ECharts交互式图表展示 |
| **科室运营简报生成** | LLM驱动，自动生成科室数据分析报告（Word/PDF导出），默认加载最近一次报告 |
| **每周临床简报** | 按周聚合运营数据，自动生成7大模块周简报，运行分析后即时展示结果 |
| **文档导出** | 支持科室运营简报与周简报分别导出为 DOCX / PDF |

### 🧠 二、知识图谱叙事
构建患者-就诊-疾病-药品-检查-手术等多实体医疗知识图谱，挖掘深层关联模式。

| 功能 | 说明 |
|------|------|
| **患者故事线** | 输入患者ID，基于图谱就诊链条生成完整就诊故事线 |
| **诊疗路径** | 挖掘"疾病→常用药品→常规检查→手术"的典型路径 |
| **合并症分析** | 基于二阶关系发现常见合并症组合与三元疾病组合 |
| **用药模式** | 分析药品共现网络，识别中西医结合用药特点 |
| **再入院分析** | 识别多次就诊患者，生成纵向医疗叙事 |
| **RAG问答** | LLM基于图谱真实子图回答医疗问题，避免"编造" |
| **图谱可视化** | ECharts力导向图展示患者子图、疾病关联、药品联用 |
| **中医特色** | 证型-用药关联、中西医结合对比、证型分布趋势 |
| **质控异常** | 缺失必要检查、住院天数异常、30天再入院、诊断-药品不匹配、药物相互作用 |
| **科室运营** | 多周期运营指标对比（病种、用药、合并症、中西医结合占比等） |
| **相似患者** | 基于图谱共同邻居算法（Jaccard）计算患者相似度，推荐参考病例 |
| **风险预警** | 多因素风险评分（就诊频率、多病共存、住院天数、年龄、恶性肿瘤等） |

---

## 🏗️ 技术栈

- **前端**: React 18 + Vite + Ant Design + ECharts (SPA，含医生前台与后台管理)
- **后端**: FastAPI + Uvicorn
- **知识图谱**: Neo4j (32,694 节点 / 788,119 关系)
- **数据库**: MySQL (结构化数据) + ChromaDB (向量检索) + JSON文件存储
- **大模型**: OpenAI API 兼容接口
- **LLM缓存**: 基于内容哈希的持久化缓存，支持TTL与命名空间管理
- **文档生成**: python-docx
- **数据可视化**: ECharts (echarts-for-react)

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/liyan24/hospital-narrative-assistant.git
cd hospital-narrative-assistant

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，填写实际配置：

```bash
cp .env.example .env
```

关键配置项：
- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` — 大模型接口
- `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` — Neo4j连接
- `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DATABASE` — MySQL连接（数据库名已设为 `hna`）
- `SECRET_KEY` — JWT 签名密钥（生产环境务必修改）
- `APP_PORT` / `FRONTEND_PORT` — 服务端/前端端口（默认 8005 / 8501）

### 4. 初始化 MySQL 数据库

确保 MySQL 已启动，并在 `.env` 中配置正确的数据库密码，然后执行：

```bash
# 创建表 + 插入默认角色/权限/用户/配置/功能开关
python scripts/init_database.py

# 将 data/ 目录下的 Excel 业务数据导入 MySQL（首次运行耗时约 10-15 分钟）
python scripts/import_data.py --clear --batch-size 5000
```

详细说明见 [`scripts/README.md`](scripts/README.md)。

### 5. 安装并启动前端

```bash
cd frontend
npm install
npm run dev        # http://localhost:8501
```

### 6. 启动后端

```bash
# 终端：启动后端 API (http://localhost:8005)
python main.py
```

### 5. 构建知识图谱（首次运行）

进入前端页面 **⚙️ 知识图谱管理** → 点击「构建知识图谱」按钮，或调用API：

```bash
curl -X POST http://localhost:8005/api/kg/build \
  -H "Content-Type: application/json" \
  -d '{"clear": false}'
```

---

## 📁 项目结构

```
hospital-narrative-assistant/
├── main.py                          # FastAPI 主入口
├── streamlit_app.py                 # Streamlit 前端导航入口（遗留，已逐步迁移到 React）
├── frontend/                        # React + Vite + Ant Design 新前端
│   ├── src/
│   │   ├── views/portal/            # 医生前台：工作台、患者全息视图、查房助手、晨会简报
│   │   ├── views/admin/             # 后台管理：用户、功能开关、系统配置、缓存
│   │   ├── layouts/                 # 前台/后台布局
│   │   ├── api/                     # Axios API 封装
│   │   └── stores/                  # 认证状态
│   ├── package.json
│   └── vite.config.js
├── config.py                        # Pydantic Settings 配置管理
├── requirements.txt                 # Python 依赖
├── .env / .env.example              # 环境变量
│
├── database/                        # 数据库模块
│   ├── neo4j_client.py              # Neo4j 连接
│   ├── mysql_client.py              # MySQL 连接
│   ├── vector_store.py              # ChromaDB 向量存储
│   ├── json_store.py                # JSON 文件存储
│   └── llm_cache.py                 # LLM输出缓存存储（内容哈希+TTL+命名空间）
│
├── models/
│   └── schemas.py                   # Pydantic 数据模型
│
├── services/                        # 业务服务层
│   ├── llm_service.py               # 大模型通用接口（含缓存集成）
│   ├── narrative_service.py         # 统计报告叙事
│   ├── data_analysis_service.py     # 数据分析
│   ├── chart_service.py             # ECharts 图表生成
│   ├── document_service.py          # Word/PDF 导出
│   ├── weekly_analysis_service.py   # 周简报分析
│   ├── weekly_narrative_service.py  # 周简报叙事
│   ├── weekly_document_service.py   # 周简报导出
│   ├── knowledge_graph_service.py   # 知识图谱构建
│   ├── kg_data_cleaner.py           # 数据清洗（疾病/药品标准化）
│   ├── patient_narrative_service.py # 患者故事线
│   ├── pathway_narrative_service.py # 诊疗路径
│   ├── comorbidity_service.py       # 合并症分析
│   ├── drug_pattern_service.py      # 用药模式
│   ├── readmission_service.py       # 再入院分析
│   ├── kg_rag_service.py            # 图谱RAG问答（含模糊疾病匹配）
│   ├── kg_visual_service.py         # 图谱可视化数据
│   ├── tcm_narrative_service.py     # 中医特色叙事
│   ├── quality_control_service.py   # 质控异常
│   ├── department_operation_service.py  # 科室运营
│   ├── similar_patient_service.py   # 相似患者推荐
│   └── risk_prediction_service.py   # 风险预警
│
├── routers/                         # API 路由
│   ├── data.py                      # 数据管理 / 健康检查
│   ├── narrative.py                 # 叙事生成 + LLM缓存管理
│   ├── document.py                  # 文档导出
    ├── weekly.py                    # 周简报分析与导出
    ├── knowledge_graph.py           # 知识图谱构建/查询/统计
    ├── daily.py                     # 每日简报
    ├── auth.py                      # 登录认证
    └── admin.py                     # 后台管理（用户/角色/配置/功能开关）
│
├── pages/                           # Streamlit Pages (v2)
│   ├── 🏠_首页.py
│   ├── 📊_数据概览.py
│   ├── 📊_报告生成.py              # 科室运营简报生成
│   ├── 📊_周简报.py
│   ├── 📊_文档导出.py
│   ├── 🧠_患者故事线.py
│   ├── 🧠_诊疗路径.py
│   ├── 🧠_合并症分析.py
│   ├── 🧠_用药模式.py
│   ├── 🧠_再入院分析.py
│   ├── 🧠_RAG问答.py
│   ├── 🧠_图谱可视化.py
│   ├── 🧠_中医特色.py
│   ├── 🧠_质控异常.py
│   ├── 🧠_科室运营.py
│   ├── 🧠_相似患者.py
│   └── 🧠_风险预警.py
│
├── utils/                           # 工具函数
│   ├── api_client.py                # 前端共享API客户端
│   ├── helpers.py
│   ├── report_layout.py             # 报告文本与图表穿插布局
│   └── weekly_charts.py             # 周简报ECharts渲染
│
├── data/                            # 数据目录
│   ├── json_store/                  # JSON 数据缓存
│   ├── llm_cache/                   # LLM输出缓存
│   ├── kg_cleaned/                  # 清洗后数据缓存
│   ├── vector_db/                   # ChromaDB向量库
│   └── outputs/                     # 报告输出目录
│
├── scripts/                         # 数据库与管理脚本
│   ├── create_tables.sql            # 创建业务表与后台管理表
│   ├── init_data.sql                # 默认角色/权限/用户/配置/功能开关
│   ├── init_database.py             # 一键初始化数据库
│   ├── import_data.py               # Excel 业务数据导入 MySQL
│   └── build_knowledge_graph.py     # 构建 Neo4j 知识图谱
│
├── scripts/                         # 数据库与管理脚本
│   ├── create_tables.sql            # 创建业务表与后台管理表
│   ├── init_data.sql                # 默认角色/权限/用户/配置/功能开关
│   ├── init_database.py             # 一键初始化数据库
│   ├── import_data.py               # Excel 业务数据导入 MySQL
│   └── build_knowledge_graph.py     # 构建 Neo4j 知识图谱
│
└── output/                          # 示例输出文档
```

---

## 📡 API 文档

启动后端后访问：
- **Swagger UI**: http://localhost:8005/docs
- **ReDoc**: http://localhost:8005/redoc

### 主要接口分组

| 前缀 | 功能 |
|------|------|
| `GET /health` | 服务健康检查 |
| `/api/data/...` | 数据分析、统计图表 |
| `/api/narrative/...` | 全部叙事生成接口（报告、患者故事线、诊疗路径、合并症、用药、再入院、RAG、中医、质控、运营、相似患者、风险预警） |
| `/api/narrative/cache/...` | LLM缓存管理（统计/清理/按命名空间清理） |
| `/api/document/...` | 报告导出（DOCX/PDF） |
| `/api/weekly/...` | 周简报分析与导出 |
| `/api/kg/...` | 知识图谱构建、统计、Cypher查询、子图可视化 |

---

## 📈 知识图谱规模（示例数据）

基于肿瘤血液科真实脱敏数据构建：

| 类型 | 数量 |
|------|------|
| 患者 (Patient) | 3,989 |
| 就诊 (Visit) | 13,743 |
| 西医疾病 (Disease::western) | 1,596 |
| 中医病名/证型 (Disease::tcm) | 1,391 |
| 药品 (Drug) | 3,888 |
| 检查 (Exam) | 69 |
| 手术 (Surgery) | 58 |
| 主诉 (ChiefComplaint) | 5,778 |
| **关系总数** | **788,119** |


## 📝 开发说明

本项目为持续迭代的医院科室数据智能辅助平台。当前版本已完成从基础统计分析到深度知识图谱叙事的完整能力闭环。

### 扩展新功能
1. 在 `services/` 目录下新增服务类，调用 `llm_service.chat(cache_namespace="your:namespace")`
2. 在 `routers/narrative.py` 中注册API
3. 在 `frontend/src/views/` 下新增 React 页面与路由
4. 在 `frontend/src/router/index.jsx` 中注册路由

### LLM缓存管理
通过API或前端可管理LLM缓存：
```bash
# 查看缓存统计
curl http://localhost:8005/api/narrative/cache/stats

# 清理过期缓存
curl -X POST http://localhost:8005/api/narrative/cache/clear-expired

# 按命名空间清理（如 narrative:basic）
curl -X POST http://localhost:8005/api/narrative/cache/clear/narrative:basic
```

---

## 📄 License

MIT License