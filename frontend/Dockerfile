FROM node:20-alpine
WORKDIR /srv/web
# 先拷锁文件利用缓存；npm ci 严格按 package-lock.json 安装，版本漂移会直接失败
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
