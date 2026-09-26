.PHONY: help install dev backend frontend build check clean

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-10s %s\n", $$1, $$2}'

install: ## 安装前后端锁定依赖（不启动）
	cd backend && python3 -m venv .venv 2>/dev/null || virtualenv .venv
	cd backend && .venv/bin/pip install --disable-pip-version-check -r requirements.txt
	cd frontend && npm ci

dev: ## 一条命令：装依赖校验 + 构建前端 + 同时启动前后端
	./scripts/dev.sh

backend: ## 只启动后端（含启动前依赖/环境变量诊断）
	cd backend && ./run.sh

frontend: ## 只启动前端 dev server
	cd frontend && npm run dev

build: ## 构建校验：后端诊断 + 前端类型检查与打包
	cd backend && .venv/bin/python scripts/preflight.py
	cd frontend && npm run build

check: ## 占道施工链路自检（确认申请提交与审批接口可用，需先启动服务）
	cd backend && .venv/bin/python scripts/check_occupy.py

clean: ## 清理虚拟环境与前端依赖/产物
	rm -rf backend/.venv frontend/node_modules frontend/dist
