# HRSG Fouling Advisor — 프론트엔드 빌드 전용
# 결과물(dist)을 Nginx 컨테이너가 가져가 서빙한다.
FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# 빌드 산출물만 남긴 최소 이미지. compose 가 여기서 dist 를 꺼내 간다.
FROM busybox:1.36
COPY --from=build /app/dist /dist
CMD ["true"]
