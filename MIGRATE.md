# 换电脑迁移指南（MIGRATE）

> 生成时间：2026-08-07 by pi
> 一句话：**代码和数据都在 Git 里，clone 下来 + 手动拷 3 样东西即可**

## 一、迁移清单总览

| 内容 | 在哪 | 迁移方式 |
|------|------|----------|
| 全部代码（src/ docs/） | GitHub 私有仓库 luo080104/first-try | ✅ git clone |
| 数据库 data/shopping.db（价格历史/盯价/评论缓存/补搜缓存） | Git 已跟踪 | ✅ clone 自带 |
| data/bloggers.json、raw_titles.json | Git 已跟踪 | ✅ clone 自带 |
| **.env（4 个 API 密钥）** | 本地，**不在 Git**（安全） | ⚠️ **手动拷** |
| **data/jd_profile（京东登录态 cookies）** | 本地，**不在 Git** | ⚠️ **手动拷** |
| **data/tb_profile（淘宝登录态 cookies）** | 本地，**不在 Git** | ⚠️ **手动拷** |
| venv/ 虚拟环境 | 本地 | ❌ 不要拷，新电脑重建 |
| reference/（京东 SDK 参考） | 本地，已 gitignore | ❌ 不需要（当前方案不用 SDK） |

## 二、手动拷贝的 3 样东西（U盘/微信文件传输/网盘）

1. `.env` —— 4 个密钥：DTK_APP_KEY、DTK_APP_SECRET、JD_APP_KEY、JD_APP_SECRET
   （丢了也没关系，去 dataoke.com 和 京东联盟后台重新复制，但手动拷最快）
2. `data/jd_profile/` 整个文件夹 —— 京东登录态（不拷 = 新电脑首次搜索要手动登录京东）
3. `data/tb_profile/` 整个文件夹 —— 淘宝登录态（不拷 = 新电脑首次搜索要手动登录淘宝）

⚠️ 两个 profile 文件夹可能较大（几十 MB 缓存），传之前可删掉里面的
`Cache/`、`Code Cache/`、`GPUCache/`、`ShaderCache/` 等缓存目录，只保留
`Default/` 下的 Cookies、Local Storage、Login Data 等登录相关文件
（偷懒做法：整个拷，能用就行）。

## 三、新电脑操作步骤（Windows）

```bash
# 1. 安装 Python 3.11+（3.14 实测可用）
#    https://www.python.org/downloads/  安装时勾选 Add to PATH

# 2. 克隆代码（需 GitHub 账号配置，或用 Personal Access Token）
git clone https://github.com/luo080104/first-try.git
cd first-try

# 3. 创建虚拟环境并装依赖
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 4. 放回 3 样手动拷贝的东西
#    - .env 放到项目根目录
#    - jd_profile/ tb_profile/ 放到 data/ 下

# 5. 启动
cd src
python -m uvicorn app:app --port 8001 --host 0.0.0.0
```

## 四、启动后自检

- 浏览器打开 http://127.0.0.1:8001
- 搜"耀世16Ultra"：应能搜出淘宝+拼多多（验证 .env 密钥）
- 若快通道 <5 条触发补搜：京东/淘宝自动开浏览器（验证 profile 登录态）
- 盯价清单/历史价格：验证 shopping.db 数据完整

## 五、常见问题

- **端口被占**：8000 常被无关软件占用，用 8001；或换端口 `--port 任意`
- **京东搜索返回 0 条**：profile 没拷对 → 删除 data/jd_profile 重新搜索，浏览器会弹登录
- **淘宝验证码**：正常现象，等 1 分钟再搜（低频约束，防封）
- **Git push 失败 SSL**：历史遇到过 schannel 问题，重试或配代理即可
