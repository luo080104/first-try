# Go购 Constitution

> Pi 每次启动必须先读本文件。TXT 格式供 Pi 的 system prompt 注入。

## Always

- 改任何文件前先用 Read 工具读当前内容
- 修改后跑测试或用 curl 验证关键 API 返回 200
- API 路由变更同步更新 app.py 的路由注释
- 采集逻辑变更（crawl.py/browser_pool.py）后通知更新 SYNC.md
- 服务重启后用 curl 验证 /health /guide /search_sse 三个端点

## Ask First

- 数据库 schema 变更（改表结构、加字段）
- 新增 pip 依赖包
- 浏览器池行为变更（headless/有头切换、profile 目录改动）
- 改 .vbs 启动脚本
- 超过 10 行代码的重构

## Never

- 硬编码 API Key、Secret、Token（含日志/公开推送——泄漏即轮换）
- 删除其他模块的代码（即使是"顺手清理"）
- 改 app.py 的同时忘了改对应的前端模板
- 修改后不验证直接推代码
- 跳过 Read 工具直接用 Bash 读文件
- 删除 GitHub 仓库或项目目录（gh repo delete / rm -rf 项目）
- 删除系统文件/目录（rm -rf /、~/.ssh/、~/.config/ 等同级危险操作）
- force-push 到共享分支（main/master）
- git reset --hard 共享分支（回滚用 revert 或 checkout 局部还原）
- 绕过验证码/违规爬取（个人自用只读、不绕验证码、不下单——合规底线）

> 护栏来源：Auto-Company 安全护栏清单（2026-08-12 精读对照补齐）
