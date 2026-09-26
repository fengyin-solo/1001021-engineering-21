FROM node:20-alpine
WORKDIR /srv/web
# npm ci 严格按 lock 文件安装，保证镜像里依赖可复现
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
