.PHONY: install up backend frontend check

# 装齐前后端依赖（后端 requirements.lock / 前端 package-lock.json，版本已锁定）
install:
	scripts/install.sh

# 一条命令跑通工程链路：预检 → 装依赖 → 前端构建 → 起前后端 → 自检占道审批链路
up:
	scripts/dev-up.sh

# 只起后端（启动前预检，失败会说明是依赖缺失还是环境变量没配）
backend:
	cd backend && ./run.sh

# 只起前端 dev server（热更新调页面用）
frontend:
	cd frontend && npm run dev

# 服务运行中重复自检：占道申请提交与审批链路是否都能返回
check:
	python3 scripts/smoke_check.py
