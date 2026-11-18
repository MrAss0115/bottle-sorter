"""使用项目专属 Python 启动 HTTP 服务。"""

import os
import sys

sys.dont_write_bytecode = True

import uvicorn


if __name__ == "__main__":
    # 普通入口保持本机访问；单独的局域网入口供实际板子联调。
    uvicorn.run("app:app", host=os.environ.get("BOTTLE_SORTER_HOST", "127.0.0.1"), port=8000, reload=False)
