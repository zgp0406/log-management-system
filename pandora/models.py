"""
统一的模型定义文件
所有数据库模型都集中在这里，避免重复定义和不一致问题
"""
from django.db import models
from django.utils import timezone


# ==================== 部门表 ====================
class Department(models.Model):
    department_id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'department'
        verbose_name = '部门'
        verbose_name_plural = '部门'
        managed = True
        app_label = 'dashboard'  # 指定应用标签

    def __str__(self):
        return self.department_name


# ==================== 员工表 ====================
class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    employee_name = models.CharField(max_length=50)
    work_id = models.CharField(max_length=20, unique=True)
    email = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    department_id = models.IntegerField(blank=True, null=True, db_column='department_id')
    position = models.CharField(max_length=50, null=True, blank=True)
    join_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('ACTIVE', '活跃'), ('LEAVE', '请假')],
        default='ACTIVE'
    )
    manager = models.ForeignKey(
        'self',
        related_name='subordinates',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        db_column='manager_id'
    )
    password = models.CharField(max_length=255, default='', verbose_name="密码")
    pc_login_token = models.CharField(max_length=64, null=True, blank=True, verbose_name="PC端登录Token")
    mobile_login_token = models.CharField(max_length=64, null=True, blank=True, verbose_name="移动端登录Token")

    class Meta:
        db_table = 'employee'
        verbose_name = '员工'
        verbose_name_plural = '员工'
        managed = True
        app_label = 'dashboard'  # 指定应用标签

    def __str__(self):
        return self.employee_name


# ==================== 员工权限表 ====================
class EmployeePermission(models.Model):
    """
    员工权限扩展表
    用于存储更细粒度的权限控制（任务查看、日志查看等）
    """
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='employee_id',
        related_name='permissions'
    )
    can_view_all_tasks = models.BooleanField(default=False, verbose_name="查看所有任务")
    can_view_all_logs = models.BooleanField(default=False, verbose_name="查看所有日志")
    
    # 是否是管理员（拥有所有权限）
    @property
    def is_super_admin(self):
        return self.can_view_all_tasks and self.can_view_all_logs

    class Meta:
        db_table = 'employee_permission'
        managed = True
        verbose_name = '员工权限'
        verbose_name_plural = '员工权限'
        app_label = 'dashboard'


# ==================== 角色表 ====================
class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_name = models.CharField(max_length=50, unique=True, verbose_name="角色名称")

    class Meta:
        db_table = 'role'
        managed = True
        verbose_name = '角色'
        verbose_name_plural = '角色'
        app_label = 'dashboard'  # 指定应用标签

    def __str__(self):
        return self.role_name


# ==================== 员工角色关联表 ====================
class EmployeeRole(models.Model):
    # 注意：这个表在数据库中没有id主键字段
    # Django ORM默认需要主键，但我们可以通过使用values()方法来避免访问id字段
    # 或者添加一个虚拟的主键（使用employee_id和role_id组合）
    # 为了兼容Django ORM，我们使用employee_id作为主键（虽然不唯一，但managed=False时不影响）
    employee_id = models.IntegerField(verbose_name="员工ID", db_column='employee_id', primary_key=True)
    role_id = models.IntegerField(verbose_name="角色ID", db_column='role_id')

    class Meta:
        db_table = 'employee_role'
        managed = True
        # 数据库表使用(employee_id, role_id)作为唯一约束
        unique_together = (('employee_id', 'role_id'),)
        verbose_name = '员工角色关联'
        verbose_name_plural = '员工角色关联'
        app_label = 'dashboard'  # 指定应用标签

    def __str__(self):
        return f"Employee {self.employee_id} - Role {self.role_id}"


# ==================== 任务表 ====================
class Task(models.Model):
    task_id = models.AutoField(primary_key=True)
    task_name = models.CharField(max_length=16)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(
        max_length=6,
        choices=[('HIGH', 'HIGH'), ('MEDIUM', 'MEDIUM'), ('LOW', 'LOW')],
        default='MEDIUM'
    )
    project_source = models.CharField(max_length=50, blank=True, null=True)
    creator = models.ForeignKey(
        Employee,
        related_name='created_tasks',
        on_delete=models.RESTRICT,
        db_column='creator_id'
    )
    assignee = models.ForeignKey(
        Employee,
        related_name='assigned_tasks',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        db_column='assignee_id'
    )
    start_time = models.DateTimeField(blank=True, null=True)
    due_time = models.DateTimeField(blank=True, null=True)
    estimated_duration = models.IntegerField(blank=True, null=True)
    status = models.CharField(
        max_length=11,
        choices=[('TO_DO', 'TO_DO'), ('IN_PROGRESS', 'IN_PROGRESS'), ('COMPLETED', 'COMPLETED')],
        default='TO_DO'
    )
    creation_time = models.DateTimeField(default=timezone.now)
    completion_time = models.DateTimeField(blank=True, null=True)
    task_code = models.CharField(max_length=12, unique=True, blank=True)
    attachment_url = models.CharField(max_length=255, blank=True, null=True)

    def save(self, *args, **kwargs):
        """自动生成任务编号：YYMMDD###"""
        if not self.task_code:
            today_prefix = timezone.now().strftime('%y%m%d')
            # 查找今天最大的任务编号
            last_task = Task.objects.filter(
                task_code__startswith=today_prefix
            ).order_by('-task_code').first()
            
            if last_task and last_task.task_code:
                try:
                    # 提取最后三位序号并+1
                    last_seq = int(last_task.task_code[-3:])
                    new_seq = last_seq + 1
                except ValueError:
                    # 如果格式异常，回退到默认
                    new_seq = 1
            else:
                new_seq = 1
            
            self.task_code = f"{today_prefix}{new_seq:03d}"
            
        super().save(*args, **kwargs)

    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=0, verbose_name="乐观锁版本号")

    class Meta:
        db_table = 'task'
        unique_together = ('task_name', 'project_source')
        managed = True
        verbose_name = '任务'
        verbose_name_plural = '任务'
        app_label = 'task_app'  # 指定应用标签

    def __str__(self):
        return self.task_name


# ==================== 子任务表 ====================
class SubTask(models.Model):
    """子任务表（只有一层父子关系）"""
    subtask_id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        db_column='task_id',
        related_name='subtasks'
    )
    subtask_name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=11,
        choices=[('TO_DO', 'TO_DO'), ('IN_PROGRESS', 'IN_PROGRESS'), ('COMPLETED', 'COMPLETED')],
        default='TO_DO'
    )
    creation_time = models.DateTimeField(default=timezone.now)
    completion_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'subtask'
        managed = True
        verbose_name = '子任务'
        verbose_name_plural = '子任务'
        app_label = 'task_app'

    def __str__(self):
        return self.subtask_name


# ==================== 消息提醒组表 ====================
class NotificationGroup(models.Model):
    """消息提醒组配置表"""
    GROUP_TYPE_CHOICES = [
        ('SMS', '短信'),
        ('EMAIL', '邮件'),
    ]
    
    group_id = models.AutoField(primary_key=True, db_column='group_id')
    group_name = models.CharField(max_length=50, verbose_name="提醒组名称")
    group_type = models.CharField(
        max_length=5,
        choices=GROUP_TYPE_CHOICES,
        verbose_name="提醒类型"
    )
    
    class Meta:
        db_table = 'notification_group'
        managed = True
        verbose_name = '消息提醒组'
        verbose_name_plural = '消息提醒组'
        app_label = 'task_app'  # 指定应用标签
    
    def __str__(self):
        return f"{self.group_name} ({self.get_group_type_display()})"


# ==================== 任务通知关联表 ====================
class TaskNotification(models.Model):
    """任务与消息提醒组多对多关联表"""
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        db_column='task_id',
        related_name='notification_groups',
        null=True,  # 允许为空，避免迁移问题
        blank=True
    )
    notification_group = models.ForeignKey(
        NotificationGroup,
        on_delete=models.CASCADE,
        db_column='group_id',
        related_name='tasks',
        null=True,  # 允许为空，避免迁移问题
        blank=True
    )
    
    class Meta:
        db_table = 'task_notification'
        managed = True
        unique_together = ('task', 'notification_group')
        verbose_name = '任务通知关联'
        verbose_name_plural = '任务通知关联'
        app_label = 'task_app'  # 指定应用标签
    
    def __str__(self):
        return f"Task {self.task.task_id} - Group {self.notification_group.group_id}"


# ==================== 任务通知消息表 ====================
class TaskNotificationMessage(models.Model):
    """任务通知消息表"""
    NOTIFICATION_TYPE_CHOICES = [
        ('NEW_TASK', '新任务通知'),
        ('DUE_SOON', '即将到期提醒'),
        ('OVERDUE', '任务逾期提醒'),
        ('TASK_COMPLETED', '任务完成通知'),
    ]
    
    notification_id = models.AutoField(primary_key=True, db_column='notification_id')
    employee = models.ForeignKey(
        'dashboard.Employee',
        on_delete=models.CASCADE,
        db_column='employee_id',
        related_name='notifications',
        null=True,
        blank=True
    )
    task = models.ForeignKey(
        'task_app.Task',
        on_delete=models.CASCADE,
        db_column='task_id',
        related_name='notifications',
        null=True,
        blank=True
    )
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPE_CHOICES,
        verbose_name="通知类型"
    )
    message = models.TextField(verbose_name="通知内容")
    is_read = models.BooleanField(default=False, verbose_name="是否已读")
    created_time = models.DateTimeField(default=timezone.now, verbose_name="创建时间")
    
    class Meta:
        db_table = 'task_notification_message'
        managed = True  # 数据库表已存在，Django不管理
        verbose_name = '任务通知消息'
        verbose_name_plural = '任务通知消息'
        app_label = 'task_app'
        ordering = ['-created_time']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.employee.employee_name}"


# ==================== 日志系统表 ====================
class LogEntry(models.Model):
    LOG_TYPE_CHOICES = [
        ('WORK', '工作'),
        ('MEETING', '会议'),
        ('COMMUNICATION', '沟通'),
        ('DEVELOPMENT', '开发'),
        ('STUDY', '学习'),
    ]

    EMOTION_CHOICES = [
        ('ACTIVE', '积极'),
        ('FOCUSED', '专注'),
        ('SATISFIED', '满意'),
        ('TIRED', '疲惫'),
    ]

    log_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        db_column='employee_id',
        related_name='logs'
    )
    log_time = models.DateTimeField(auto_now_add=True)
    content = models.TextField()
    image_url = models.CharField(max_length=255, blank=True, null=True)
    location_lat = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    location_lng = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    location_name = models.CharField(max_length=100, blank=True, null=True)
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES)
    emotion_tag = models.CharField(
        max_length=20,
        choices=EMOTION_CHOICES,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'log_entry'
        verbose_name = '日志条目'
        verbose_name_plural = '日志条目'
        managed = True
        app_label = 'log_app'  # 指定应用标签

    def __str__(self):
        return f"{self.employee.employee_name} - {self.get_log_type_display()}"


class LogTag(models.Model):
    tag_id = models.AutoField(primary_key=True)
    tag_name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'log_tag'
        verbose_name = '日志标签'
        verbose_name_plural = '日志标签'
        managed = True
        app_label = 'log_app'  # 指定应用标签

    def __str__(self):
        return self.tag_name


class EntryTagLink(models.Model):
    log_entry = models.ForeignKey(
        LogEntry,
        on_delete=models.CASCADE,
        db_column='log_id'
    )
    tag = models.ForeignKey(
        LogTag,
        on_delete=models.CASCADE,
        db_column='tag_id'
    )

    class Meta:
        db_table = 'entry_tag_link'
        unique_together = ('log_entry', 'tag')
        verbose_name = '日志与标签关联'
        verbose_name_plural = '日志与标签关联'
        managed = True
        app_label = 'log_app'  # 指定应用标签

    def __str__(self):
        return f"{self.log_entry.log_id} - {self.tag.tag_name}"


# ==================== 个人十大任务配置 ====================
class PersonalTopTaskConfig(models.Model):
    """
    存储员工在桌面端/移动端配置的个人十大重要事项，使不同终端共享同一份配置
    """
    employee = models.OneToOneField(
        Employee,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='employee_id',
        related_name='personal_top_task_config'
    )
    task_ids = models.JSONField(default=list, verbose_name='任务ID列表')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'personal_top_task_config'
        verbose_name = '个人十大任务配置'
        verbose_name_plural = '个人十大任务配置'
        managed = True
        app_label = 'dashboard'


# ==================== AI 分析持久化 ====================
class AiAnalysisProfile(models.Model):
    employee = models.OneToOneField(
        'dashboard.Employee',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='employee_id',
        related_name='ai_analysis_profile'
    )
    ai_advice = models.TextField(blank=True, null=True, verbose_name='AI建议')
    mbti_type = models.CharField(max_length=5, blank=True, null=True, verbose_name='MBTI类型')
    mbti_analysis = models.TextField(blank=True, null=True, verbose_name='MBTI分析')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_analysis_profile'
        verbose_name = 'AI分析档案'
        verbose_name_plural = 'AI分析档案'
        managed = True
        app_label = 'ai_app'


class AiMbtiCache(models.Model):
    """
    MBTI分析历史缓存表
    用于切换MBTI类型时，无需重新生成即可显示之前的分析结果
    """
    employee = models.ForeignKey(
        'dashboard.Employee',
        on_delete=models.CASCADE,
        db_column='employee_id',
        related_name='ai_mbti_caches'
    )
    mbti_type = models.CharField(max_length=5, verbose_name='MBTI类型')
    content = models.TextField(verbose_name='分析内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'ai_mbti_cache'
        verbose_name = 'MBTI分析缓存'
        verbose_name_plural = 'MBTI分析缓存'
        managed = True
        app_label = 'ai_app'
        # 同一个用户同一种类型只保留一份最新的即可，或者多份历史
        # 这里为了简单，我们查询时取最新的
        indexes = [
            models.Index(fields=['employee', 'mbti_type']),
        ]


class AiDeptAnalysisProfile(models.Model):
    department = models.ForeignKey(
        'dashboard.Department',
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='department_id',
        related_name='ai_dept_analysis_profiles'
    )
    ai_advice = models.TextField(blank=True, null=True, verbose_name='部门AI建议')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'ai_dept_analysis_profile'
        verbose_name = '部门AI分析档案'
        verbose_name_plural = '部门AI分析档案'
        managed = True
        app_label = 'ai_app'

    def __str__(self):
        return f"{self.department.department_name} Analysis"

# ==================== 公司十大任务配置 ====================
class CompanyTopTaskConfig(models.Model):
    """
    存储全公司共享的十大任务配置，管理员维护，所有用户读取同一份
    """
    id = models.AutoField(primary_key=True)
    task_ids = models.JSONField(default=list, verbose_name='任务ID列表')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'company_top_task_config'
        verbose_name = '公司十大任务配置'
        verbose_name_plural = '公司十大任务配置'
        managed = True
        app_label = 'dashboard'


# ==================== 系统公告表 ====================
class Announcement(models.Model):
    announcement_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=100, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        db_column='created_by',
        related_name='created_announcements'
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    is_active = models.BooleanField(default=True, verbose_name="是否有效")
    is_pinned = models.BooleanField(default=False, verbose_name="是否置顶")
    priority = models.CharField(
        max_length=10,
        choices=[('NORMAL', '普通'), ('IMPORTANT', '重要'), ('URGENT', '紧急')],
        default='NORMAL',
        verbose_name="优先级"
    )

    class Meta:
        db_table = 'announcement'
        verbose_name = '系统公告'
        verbose_name_plural = '系统公告'
        managed = True
        app_label = 'dashboard'
        ordering = ['-is_pinned', '-created_at']

    def __str__(self):
        return self.title
