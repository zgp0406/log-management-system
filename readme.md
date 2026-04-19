# Pandora 日志管理系统

## 项目简介

Pandora是一个功能完善的日志管理系统，旨在帮助团队高效地管理日志、任务和员工信息。系统采用Django框架开发，支持Web端和移动端访问，提供了丰富的功能模块，包括日志管理、任务管理、员工管理、AI辅助等。

## 功能特性

### 核心功能

- **日志管理** (log_app)
  - 日志的创建、查看、编辑和删除
  - 支持移动端日志操作
  - 日志分类与检索

- **任务管理** (task_app)
  - 任务的创建、分配、跟踪和完成
  - 任务通知功能
  - 支持移动端任务管理
  - 任务报告生成

- **员工管理** (dashboard)
  - 员工信息管理
  - 员工权限管理
  - 员工工作日历视图
  - 公告管理

- **AI辅助** (ai_app)
  - AI智能缓存
  - AI辅助功能接口

### 系统特性

- 响应式设计，支持PC和移动端
- 单会话管理
- 消息推送服务
- 完善的API接口
- 支持PWA（渐进式Web应用）

## 技术栈

- **后端框架**: Django
- **前端**: HTML5, CSS3, JavaScript
- **数据库**: Django ORM (支持多种数据库)
- **测试**: Pytest
- **API文档**: OpenAPI (api.yaml)

## 项目结构

```
pandora-log-management-system-xue/
├── pandora/              # 项目配置目录
├── dashboard/            # 仪表盘应用
├── log_app/             # 日志管理应用
├── task_app/            # 任务管理应用
├── ai_app/              # AI辅助应用
├── login_app/           # 登录应用
├── static/              # 静态资源
├── templates/           # 模板文件
├── media/               # 媒体文件
├── tests/               # 测试文件
└── manage.py            # Django管理脚本
```

## 快速开始

### 环境要求

- Python 3.x
- Django 4.x
- 其他依赖见 requirements.txt

### 安装步骤

1. 克隆项目到本地
   ```bash
   git clone [项目地址]
   cd pandora-log-management-system-xue
   ```

2. 安装依赖
   ```bash
   pip install -r requirements.txt
   ```

3. 配置数据库
   - 修改 `pandora/settings.py` 中的数据库配置
   - 执行数据库迁移
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

4. 创建超级用户
   ```bash
   python manage.py createsuperuser
   ```

5. 运行开发服务器
   ```bash
   python manage.py runserver
   ```

6. 访问系统
   - Web端: http://127.0.0.1:8000
   - 管理后台: http://127.0.0.1:8000/admin

## API文档

项目包含完整的API文档，详见 `api.yaml` 文件。可以使用Postman导入 `tests/postman/pandora.postman_collection.json` 进行API测试。

## 测试

项目使用Pytest进行测试，运行测试：

```bash
pytest
```

测试报告会生成在 `tests/reports/` 目录。

## 部署建议

1. 生产环境使用WSGI服务器（如Gunicorn）
2. 配置Nginx作为反向代理
3. 使用PostgreSQL或MySQL作为生产数据库
4. 配置HTTPS
5. 设置静态文件服务

## 文档

- [Pandora_软件需求规格说明书.doc](Pandora_软件需求规格说明书.doc) - 系统需求文档
- [Pandora_系统测试用例.xls](Pandora_系统测试用例.xls) - 系统测试用例
- [Pandora_功能测试报告.doc](Pandora_功能测试报告.doc) - 功能测试报告

## 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。

## 许可证

[添加许可证信息]

## 联系方式

如有问题或建议，请联系项目维护者。

---

**注意**: 本项目仅供学习和参考使用。
