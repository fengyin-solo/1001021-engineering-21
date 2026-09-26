# 市政道路桥梁养护管理平台

面向市政道路桥梁日常巡查、定期检测、病害维修、除雪防汛与占道施工的一体化养护管理后台。

这是一个前后端分离的管理平台：前端 Vue 3 + Vite + TypeScript，后端 FastAPI（Python）。
两边各自独立启动，前端 dev server 已关掉自动打开页面，启动后按终端打印的地址手工打开。

## 目录结构

```text
.
├── frontend/                 Vue 3 + Vite + TypeScript 前端
│   ├── src/views/            每个业务模块一个页面
│   ├── src/api/              统一请求封装
│   ├── src/stores/           会话与筛选状态
│   └── vite.config.ts        dev/preview 配置（/api 代理到后端）
├── backend/                  FastAPI（Python） 后端
│   ├── app/routers/          每个业务模块一组接口
│   ├── app/services/         业务规则与状态流转
│   ├── app/store.py          内存数据仓库
│   ├── app/seed.py           示例数据（启动时自动灌入）
│   ├── requirements.txt      直接依赖（版本锁定）
│   └── requirements.lock     完整依赖锁（pip freeze，含传递依赖）
├── scripts/
│   ├── preflight.sh          启动预检：命令、依赖、环境变量逐项检查
│   ├── install.sh            装齐前后端依赖（幂等）
│   ├── dev-up.sh             一条命令：预检→装依赖→构建→起服务→自检
│   └── smoke_check.py        占道施工审批链路自检
├── Makefile
├── .env.example              环境变量样例（local 环境不配也能起）
└── docker-compose.yml
```

## 从零到能用

前置要求：Python 3.10+（建议 3.11/3.12）、Node.js 18+（建议 20 LTS）、npm。
Debian/Ubuntu 若 `python3 -m venv` 报 ensurepip 缺失，先 `sudo apt-get install python3-venv`。

```bash
git clone <仓库地址> && cd <仓库目录>
make up
```

`make up` 一条命令依次完成：

1. **预检**：检查 python3/node/npm 是否可用、依赖是否安装、环境变量是否配齐；
2. **装依赖**：缺失才装，后端按 `requirements.lock`、前端按 `package-lock.json` 锁定安装；
3. **前端构建**：`vue-tsc` 类型检查 + `vite build`，构建不过直接终止并指出错误；
4. **起服务**：后端 `http://127.0.0.1:8000`（启动时自动灌入示例数据），
   前端 `http://127.0.0.1:5173`（serve 刚构建的产物，`/api` 代理到后端）；
5. **链路自检**：自动提交一条占道申请并走完整条审批链，结果打印在终端。

停止：在 `make up` 的终端按 `Ctrl-C`，前后端会一起退出。

### 确认链路可用

服务运行期间随时可以重复自检（这就是「检查入口」）：

```bash
make check
```

自检覆盖：健康检查 → 种子数据含 待审批/已批准/施工中/已完工/已恢复 全状态 →
提交占道申请 → 审批通过（回写审批人）→ 开始施工 → 完工确认 → 恢复通行 →
终态明细 → 非法动作拦截 → 前端代理链路。全部通过会输出
`自检完成：占道申请提交与整条审批链路（含前端代理）全部可用。`

也可以手工验证：

```bash
curl http://127.0.0.1:8000/api/health          # 服务存活
curl http://127.0.0.1:8000/api/occupy          # 占道施工列表（含示例数据）
```

浏览器打开 `http://127.0.0.1:5173` 进入「占道施工」页面，可登记申请、
按状态筛选、点「审批通过 / 开始施工 / 完工确认 / 恢复通行」逐步流转。

### 分开启动（调试单个端时用）

```bash
make install    # 只装依赖
make backend    # 只起后端（启动前同样会预检）
make frontend   # 只起前端 dev server（热更新）
```

## 启动失败排查

预检会把失败原因分成两类，按终端里 ✗ 条目的指引处理即可：

| 现象 | 类别 | 处理 |
| --- | --- | --- |
| `后端虚拟环境不存在` / `后端依赖缺失` | 依赖缺失 | `make install` |
| `前端依赖缺失：frontend/node_modules 未安装` | 依赖缺失 | `make install` |
| `python3 -m venv 失败` | 依赖缺失 | `sudo apt-get install python3-venv` |
| `环境变量 APP_SECRET_KEY 未配置` | 环境变量没配 | 非 local 环境必须提供，见下表 |
| `环境变量 APP_PORT 必须是整数` | 环境变量没配 | 修正 `.env` 里的取值 |

## 环境变量

本地开发（`APP_ENV=local`）全部有默认值，clone 下来不配也能启动。
需要覆盖时复制 `.env.example` 为 `.env` 再改：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `APP_ENV` | `local` | 运行环境；非 local 时 `APP_SECRET_KEY` 必填 |
| `APP_SECRET_KEY` | 本地内置 | 非 local 环境必填，缺失时预检直接报错 |
| `APP_PORT` | `8000` | 后端监听端口 |
| `APP_CORS_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` | 允许跨域来源，逗号分隔 |
| `VITE_PROXY_TARGET` | `http://127.0.0.1:8000` | 前端 dev/preview 的 `/api` 代理目标 |

## 依赖版本锁定

- 后端：`requirements.txt` 锁定直接依赖版本，`requirements.lock` 是
  `pip freeze` 生成的完整锁（含传递依赖），安装与 Docker 构建都走 lock 文件。
- 前端：`package.json` 去掉 `^` 前缀锁死版本，`package-lock.json` 提交入库，
  安装一律用 `npm ci`（版本漂移会直接失败而不是悄悄装错）。

## 业务模块

| 模块 | 目录 | 业务对象 | 主要字段 |
| --- | --- | --- | --- |
| 设施台账 | `facility` | 设施 | 设施编号、设施名称、设施类型 |
| 桥梁档案 | `bridge` | 桥梁 | 桥梁编号、桥梁名称、桥型结构 |
| 隧道管理 | `tunnel` | 隧道 | 隧道编号、隧道名称、隧道长度 |
| 路面状况 | `pavement` | 路面评价 | 评价编号、道路名称、评价路段 |
| 日常巡查 | `patrol` | 巡查记录 | 巡查编号、巡查路段、巡查人员 |
| 病害记录 | `disease` | 病害 | 病害编号、所属设施、病害类型 |
| 养护维修 | `repair` | 维修任务 | 任务编号、任务类型、维修对象 |
| 养护材料 | `material2` | 养护材料 | 材料编号、材料名称、规格型号 |
| 养护机械 | `machine` | 养护机械 | 机械编号、机械名称、规格型号 |
| 应急抢险 | `emergency` | 应急事件 | 事件编号、事件类型、发生地点 |
| 除雪防汛 | `deicing` | 除雪防汛 | 作业编号、作业类型、作业路段 |
| 占道施工 | `occupy` | 占道施工 | 施工编号、施工位置、占用范围、审批人、占用期限 |
| 绿化管护 | `greening` | 绿化管护 | 管护编号、管护区域、植被类型 |
| 交安设施 | `safety2` | 交安设施 | 设施编号、设施类型、所在路段 |
| 边坡挡墙 | `geom` | 边坡挡墙 | 边坡编号、所属路段、边坡类型 |
| 路灯管养 | `light` | 路灯设施 | 灯杆编号、所在路段、灯型类别 |
| 排水设施 | `drain` | 排水设施 | 设施编号、设施类型、所在路段 |
| 养护计划 | `plan` | 养护计划 | 计划编号、计划周期、计划类型 |
| 市民热线 | `complaint` | 热线记录 | 记录编号、来电人、来电内容 |
| 车辆超限 | `load` | 超限记录 | 记录编号、抓拍路段、车辆类型 |

## 约定

- 每个模块的前端页面在 `frontend/src/views/<模块>/index.vue`，后端接口在
  `backend/app/routers/<模块>.py`，业务规则在 `backend/app/services/<模块>.py`。
- 列表接口统一返回 `{ items, total, page, size }`，动作接口统一返回 `{ ok, message }`。
- 状态流转只允许在 `app/services` 里改，路由层不做业务判断。
- 占道施工状态链：待审批 → 已批准 → 施工中 → 已完工 → 已恢复，
  对应动作：审批通过 / 开始施工 / 完工确认 / 恢复通行。
