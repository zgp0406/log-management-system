# Pandora 日志管理系统

Pandora 是一个基于 Django 的企业工作管理系统，覆盖日志、任务、员工、公告、AI 分析和移动端访问等场景。项目支持桌面端与移动端页面，并提供对应的 JSON API、PWA 入口和测试用例。

## 项目特点

- 日志管理：创建、查看、编辑、删除、标签筛选、移动端查看
- 任务管理：任务创建、分配、状态跟踪、子任务、通知
- 员工管理：员工信息、权限、角色、上级关系、个人资料
- AI 分析：个人画像、部门建议、MBTI 分析、周报生成
- 多端支持：桌面端页面、移动端页面、PWA 入口
- 辅助能力：OpenAPI 文档、Postman 集合、Pytest 测试

## 技术栈

- Python 3.10
- Django 5.2
- HTML / CSS / JavaScript
- SQLite（默认）或 MySQL（可选）
- Pytest

## 目录结构

```text
pandora-log-management-system-xue/
├── pandora/          # 项目配置、URL、通用工具和中间件
├── dashboard/        # 仪表盘、员工、日历、公告
├── log_app/          # 日志管理
├── task_app/         # 任务管理与通知
├── ai_app/           # AI 分析与周报
├── login_app/        # 登录与退出
├── static/           # 静态资源
├── templates/        # 公共模板
├── media/            # 上传文件和生成内容
├── tests/            # 测试、Postman、报告
└── manage.py         # Django 管理脚本
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

项目支持在根目录 `.env` 中配置变量。常用项如下：

```env
DEBUG=True
SECRET_KEY=your-secret-key
DB_ENGINE=sqlite
SQLITE_NAME=pandora_local.sqlite3
AI_API_KEY=your-ai-key
AI_PROVIDER=zhipu
AI_MODEL=glm-4
```

如果使用 MySQL，可改为：

```env
DB_ENGINE=mysql
DB_NAME=pandora
DB_USER=root
DB_PASSWORD=your-password
DB_HOST=127.0.0.1
DB_PORT=3306
```

### 3. 初始化数据库

```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. 创建管理员账号

```bash
python manage.py createsuperuser
```

### 5. 启动服务

```bash
python manage.py runserver
```

浏览器访问：

- 前台：`http://127.0.0.1:8000`
- 后台：`http://127.0.0.1:8000/admin`
- 手机端：`http://127.0.0.1:8000/m/`

如果需要让手机访问电脑上的服务，可以改为：

```bash
python manage.py runserver 0.0.0.0:8000
```

然后用电脑局域网 IP 访问。

## 测试

```bash
pytest
```

测试配置见 `pytest.ini`，测试文件放在 `tests/` 目录。

## API 与文档

- OpenAPI 文档：`api.yaml`
- Postman 集合：`tests/postman/pandora.postman_collection.json`
- 测试报告：`tests/reports/`

## 功能模块

### dashboard

仪表盘、员工管理、权限、公告、日历、移动端主页。

### log_app

日志的创建、查询、编辑、删除、标签和移动端展示。

### task_app

任务管理、子任务、任务通知、任务视图、移动端任务页。

### ai_app

AI 画像、部门分析、MBTI 分析、周报生成和报告查看。

### login_app

登录、退出和会话管理。

## 注意事项

- 项目默认使用 SQLite，适合本地开发和演示。
- 生产环境建议改用 MySQL 或 PostgreSQL，并配置 HTTPS。
- 当前仓库包含演示数据和测试数据，适合直接打开查看界面效果。
- 若要在手机上访问，请不要使用 `127.0.0.1`，而应使用电脑局域网 IP 或部署域名。

## 文档

- [Pandora_软件需求规格说明书.doc](Pandora_软件需求规格说明书.doc)
- [Pandora_系统测试用例.xls](Pandora_系统测试用例.xls)
- [Pandora_功能测试报告.doc](Pandora_功能测试报告.doc)

## 许可证

暂无正式许可证，默认仅用于学习和演示。
