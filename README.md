# 市政道路桥梁养护管理平台

面向市政道路桥梁日常巡查、定期检测、病害维修、除雪防汛与占道施工的一体化养护管理后台。

前后端分离：前端 **Vue 3 + Vite + TypeScript**，后端 **FastAPI（Python 3.10+）**，数据存内存（启动自动灌入示例数据，无需数据库）。

---

## 一条命令跑起来（推荐）

前置条件：**Node.js ≥ 20**、**Python ≥ 3.10**（Linux 下若提示缺 venv，Debian/Ubuntu 执行 `sudo apt-get install python3-venv`）。

```bash
make dev          # 等价于 ./scripts/dev.sh
```

这条命令会依次完成：

1. 检查 Node / Python 版本，缺了会明确指出是哪一项；
2. 创建后端虚拟环境，按 **锁定版本**安装依赖（首次运行）；
3. 做后端启动前诊断（依赖是否缺失、环境变量是否合法、示例数据是否完整）；
4. 按 `package-lock.json` 安装前端依赖，并执行类型检查 + 构建；
5. 同时启动后端（`:8000`）与前端（`:5173`），**启动后自动灌入示例数据**。

启动后访问：

| 入口 | 地址 |
| --- | --- |
| 前端页面 | http://127.0.0.1:5173 |
| 后端健康检查 | http://127.0.0.1:8000/api/health |
| 接口文档（Swagger） | http://127.0.0.1:8000/docs |

按 `Ctrl+C` 一并停止前后端。

### 从零到能用（手动分步，只想跑一端时用）

```bash
# 后端
cd backend
python3 -m venv .venv                                   # Debian/Ubuntu 需先装 python3-venv
.venv/bin/pip install -r requirements.txt               # 按锁定版本安装
./run.sh                                                # 内含启动诊断

# 前端（另开一个终端）
cd frontend
npm ci                                                  # 严格按 package-lock.json 安装
npm run dev
```

---

## 确认占道施工链路可用（检查入口）

服务启动后，**另开一个终端**执行：

```bash
make check
# 或：backend/.venv/bin/python backend/scripts/check_occupy.py
```

它通过真实 HTTP 请求验证整条链路，全部通过会打印 `17/17 项通过`：

- 健康检查、示例数据覆盖 **待审批 → 已批准 → 施工中 → 已完工 → 已恢复** 五个阶段；
- **申请提交**：`POST /api/occupy` 能登记一条新申请并落在「待审批」；缺字段 / 重复编号会返回可读原因；
- **审批接口**：审批时缺「审批人 / 占用期限」会被拦；补全后 `审批通过 → 开始施工 → 施工完成 → 恢复通行` 逐级流转；
- 终态上重复 / 回退动作会被拒绝；并经前端 `:5173` 代理再访问一次，确认浏览器侧链路也通。

页面侧：打开 http://127.0.0.1:5173 进入「占道施工」，每行只显示当前状态允许的**下一步动作**；
点「登记占道施工」提交申请，在「待审批」记录上点「审批通过」并填写审批人、占用期限，即可亲手走完整条链路。

---

## 依赖版本是怎么锁定的

为避免「别人拉下来构建失败」，所有依赖都固定到具体版本，不使用 `^` / `>=` 浮动范围：

| 端 | 直接依赖 | 完整锁定（含传递依赖） |
| --- | --- | --- |
| 后端 | `backend/requirements.txt`（`==` 固定） | `backend/requirements.lock`（`pip freeze` 生成） |
| 前端 | `frontend/package.json`（精确版本） | `frontend/package-lock.json`（`npm ci` 使用） |

- 后端默认按 `requirements.txt` 安装；要与本仓库完全一致的传递依赖时：
  `backend/.venv/bin/pip install -r backend/requirements.lock`
- 升级依赖后重新生成锁定文件：
  - 后端：`.venv/bin/pip freeze --all | grep -viE '^(pip|setuptools|wheel)==' > requirements.lock`
  - 前端：`npm install <pkg>@<version> --save-exact`（会同步更新 `package-lock.json`）

> 注意：`backend/.venv` 不要跨操作系统 / 机器拷贝（它内部记录了解释器绝对路径），已被 `.gitignore` 忽略；
> 在新机器上让 `make dev` 或 `./run.sh` 自动重建即可。

---

## 环境变量

本地开发**可以一个都不配**，全部有默认值。需要时复制一份再改：

```bash
cp .env.example .env
```

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | `local` / `dev` / `staging` / `production` 等，非法值启动前会报错 |
| `APP_HOST` | `127.0.0.1` | 后端监听地址 |
| `APP_PORT` | `8000` | 后端端口（必须是 1024–65535 的整数，前端代理默认指向它） |
| `APP_NAME` | 市政道路桥梁养护管理平台 | 应用名 |
| `CORS_ORIGINS` | 本地两个 5173 来源 | 多个用英文逗号分隔 |

前端代理目标可用 `VITE_PROXY_TARGET` 覆盖（见 `frontend/vite.config.ts`）。

### 启动失败时如何判断原因

后端 `./run.sh` 与 `make dev` 在拉起 uvicorn 前会先跑 `backend/scripts/preflight.py`，并用退出码区分原因：

- **退出码 2 — 依赖问题**：Python/Node 版本过低、虚拟环境不可用、`fastapi` 等包没装。提示会给出安装命令；
- **退出码 3 — 环境变量问题**：如 `APP_PORT=abc`、`APP_ENV=wat`，提示指向 `.env.example`；
- **退出码 4 — 代码 / 示例数据问题**：应用无法导入或占道施工状态样例缺失。

---

## 常用命令

```bash
make dev        # 装依赖 + 构建校验 + 同时启动前后端（日常开发）
make build      # 只做构建校验（后端诊断 + 前端类型检查/打包），不启动
make backend    # 只启动后端（含启动诊断）
make frontend   # 只启动前端
make check      # 占道施工提交 + 审批链路自检（需服务在跑）
make install    # 只安装两端锁定依赖
make clean      # 删除 .venv / node_modules / dist
```

---

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/<模块>/      每个业务模块一个页面（occupy 为占道施工）
│   ├── src/api/              统一请求封装
│   └── package-lock.json     前端依赖锁定
├── backend/                  FastAPI（Python）后端
│   ├── app/routers/<模块>.py  接口层（不写业务判断）
│   ├── app/services/<模块>.py 状态流转与校验（占道施工状态机在此）
│   ├── app/seed.py           启动自动灌入的示例数据
│   ├── scripts/preflight.py  启动前诊断（区分依赖/环境变量问题）
│   ├── scripts/check_occupy.py 占道链路自检
│   ├── requirements.txt      后端直接依赖（== 固定）
│   └── requirements.lock     后端完整依赖锁定
├── scripts/dev.sh            make dev 的编排脚本
├── .env.example              环境变量示例（复制为 .env）
└── Makefile                  上述 make 命令
```

## 业务模块

| 模块 | 目录 | 业务对象 |
| --- | --- | --- |
| 设施台账 | `facility` | 设施 |
| 桥梁档案 | `bridge` | 桥梁 |
| 隧道管理 | `tunnel` | 隧道 |
| 路面状况 | `pavement` | 路面评价 |
| 日常巡查 | `patrol` | 巡查记录 |
| 病害记录 | `disease` | 病害 |
| 养护维修 | `repair` | 维修任务 |
| 养护材料 | `material2` | 养护材料 |
| 养护机械 | `machine` | 养护机械 |
| 应急抢险 | `emergency` | 应急事件 |
| 除雪防汛 | `deicing` | 除雪防汛 |
| **占道施工** | **`occupy`** | **占道施工（含完整审批链路）** |
| 绿化管护 | `greening` | 绿化管护 |
| 交安设施 | `safety2` | 交安设施 |
| 边坡挡墙 | `geom` | 边坡挡墙 |
| 路灯管养 | `light` | 路灯设施 |
| 排水设施 | `drain` | 排水设施 |
| 养护计划 | `plan` | 养护计划 |
| 市民热线 | `complaint` | 热线记录 |
| 车辆超限 | `load` | 超限记录 |

## 约定

- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message, entry? }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
- 占道施工链路：`待审批 → 已批准 → 施工中 → 已完工 → 已恢复`，动作只能逐级前进，不可跨级或回退；
  `审批通过` 必须带「审批人」「占用期限」。
