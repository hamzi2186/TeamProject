FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_SMS_API_BASE_URL=http://localhost:8002
ARG VITE_DEMO_USER_ID=33333333-3333-4333-8333-333333333333
ARG VITE_SMS_PROVIDER=mock
ENV VITE_SMS_API_BASE_URL=$VITE_SMS_API_BASE_URL
ENV VITE_DEMO_USER_ID=$VITE_DEMO_USER_ID
ENV VITE_SMS_PROVIDER=$VITE_SMS_PROVIDER
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
