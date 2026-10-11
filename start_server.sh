#!/bin/bash

# OpenMontage 本地服务器启动脚本

PORT=${1:-8888}
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "================================"
echo "🚀 启动 OpenMontage 文档服务器"
echo "================================"
echo ""

# 检查是否已有进程运行
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 $PORT 已在使用中"
    echo "请使用其他端口或先关闭已有的服务："
    echo "   kill \$(lsof -t -i :$PORT)"
    exit 1
fi

echo "📁 项目目录: $PROJECT_DIR"
echo "🔌 端口: $PORT"
echo ""

# 启动服务器
cd "$PROJECT_DIR"
python3 -m http.server $PORT > /tmp/openmontage_server.log 2>&1 &
SERVER_PID=$!

# 等待服务器启动
sleep 2

if ps -p $SERVER_PID > /dev/null; then
    echo "✅ 服务器已启动 (PID: $SERVER_PID)"
    echo ""
    echo "================================"
    echo "📍 访问地址："
    echo "================================"
    echo ""
    echo "本地访问："
    echo "  🌐 http://127.0.0.1:$PORT/capabilites.html"
    echo ""
    echo "================================"
    echo "🔒 远程访问（SSH隧道）："
    echo "================================"
    echo ""
    echo "在客户端执行："
    echo "  ssh -NfL $PORT:127.0.0.1:$PORT root@[服务器IP]"
    echo ""
    echo "然后打开浏览器访问："
    echo "  http://127.0.0.1:$PORT/capabilites.html"
    echo ""
    echo "================================"
    echo "📋 日志文件："
    echo "  /tmp/openmontage_server.log"
    echo ""
    echo "❌ 停止服务器："
    echo "  kill $SERVER_PID"
    echo "================================"
else
    echo "❌ 服务器启动失败"
    cat /tmp/openmontage_server.log
    exit 1
fi
