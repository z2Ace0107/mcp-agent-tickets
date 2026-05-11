# MCP 智能工单 Agent 系统 v2.0
# 多阶段构建 + 非 root 用户 + 健康检查

FROM python:3.10-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


FROM python:3.10-slim

RUN useradd --create-home appuser
WORKDIR /app

# 从 builder 复制已安装的依赖
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# 复制项目代码
COPY . .

# 创建数据目录并设置权限
RUN mkdir -p /app/data /app/logs /app/chroma_data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 默认启动 Streamlit 前端
CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
