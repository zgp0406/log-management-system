
class EmployeeManager {
    constructor() {
        this.employees = [];
        this.filteredEmployees = [];
        this.currentPage = 1;
        this.itemsPerPage = 12;
        this.currentEmployee = null;
        this.isEditing = false;

        this.init();
    }

    // 初始化
    init() {
        this.bindEvents();
        this.loadEmployees();
        this.setupFilters();
    }

    // 绑定事件
    bindEvents() {
        // 添加员工按钮
        document.getElementById('addEmployeeBtn').addEventListener('click', () => {
            this.openModal();
        });

        // 刷新按钮
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.loadEmployees();
        });

        // 搜索输入
        document.getElementById('searchInput').addEventListener('input', (e) => {
            this.handleSearch(e.target.value);
        });

        // 部门筛选
        document.getElementById('departmentFilter').addEventListener('change', (e) => {
            this.handleFilter();
        });

        // 职位筛选
        document.getElementById('positionFilter').addEventListener('change', (e) => {
            this.handleFilter();
        });

        // 模态框事件
        document.getElementById('closeModal').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('cancelBtn').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('saveBtn').addEventListener('click', () => {
            this.saveEmployee();
        });

        document.getElementById('deleteBtn').addEventListener('click', () => {
            this.showDeleteConfirm();
        });

        // 确认删除模态框
        document.getElementById('confirmCancelBtn').addEventListener('click', () => {
            this.hideDeleteConfirm();
        });

        document.getElementById('confirmDeleteBtn').addEventListener('click', () => {
            this.deleteEmployee();
        });

        // 表单提交
        document.getElementById('employeeForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveEmployee();
        });

        // 点击模态框外部关闭
        document.getElementById('employeeModal').addEventListener('click', (e) => {
            if (e.target.id === 'employeeModal') {
                this.closeModal();
            }
        });

        document.getElementById('confirmModal').addEventListener('click', (e) => {
            if (e.target.id === 'confirmModal') {
                this.hideDeleteConfirm();
            }
        });

        // ESC键关闭模态框
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.closeModal();
                this.hideDeleteConfirm();
            }
        });
    }

    // 显示加载指示器
    showLoading() {
        document.getElementById('loadingIndicator').classList.add('show');
    }

    // 隐藏加载指示器
    hideLoading() {
        document.getElementById('loadingIndicator').classList.remove('show');
    }

    // 显示通知
    showNotification(message, type = 'success') {
        const notification = document.getElementById('notification');
        const messageElement = notification.querySelector('.notification-message');

        messageElement.textContent = message;
        notification.className = `notification ${type}`;
        notification.classList.add('show');

        setTimeout(() => {
            notification.classList.remove('show');
        }, 3000);
    }

    // 加载员工数据
    async loadEmployees() {
        this.showLoading();
        try {
            // 模拟API调用 - 替换为实际的数据库查询
            await this.delay(500); // 模拟网络延迟

            // 这里应该是实际的数据库查询代码
            // 例如: const response = await fetch('/api/employees');
            // this.employees = await response.json();

            // 示例数据 - 实际使用时请替换为数据库查询
            this.employees = this.generateSampleData();

            this.filteredEmployees = [...this.employees];
            this.updateFilters();
            this.renderEmployees();
            this.renderPagination();

            this.showNotification('员工数据加载成功');
        } catch (error) {
            console.error('加载员工数据失败:', error);
            this.showNotification('加载员工数据失败', 'error');
        } finally {
            this.hideLoading();
        }
    }

    // 生成示例数据（实际使用时删除此方法）
    generateSampleData() {
        const departments = ['技术部', '销售部', '人事部', '财务部', '市场部'];
        const positions = ['工程师', '经理', '主管', '专员', '总监'];
        const names = ['张三', '李四', '王五', '赵六', '钱七', '孙八', '周九', '吴十'];

        return Array.from({ length: 50 }, (_, i) => ({
            id: i + 1,
            name: names[Math.floor(Math.random() * names.length)] + (i + 1),
            email: `employee${i + 1}@company.com`,
            phone: `138${String(Math.floor(Math.random() * 100000000)).padStart(8, '0')}`,
            department: departments[Math.floor(Math.random() * departments.length)],
            position: positions[Math.floor(Math.random() * positions.length)],
            hireDate: new Date(2020 + Math.floor(Math.random() * 4), Math.floor(Math.random() * 12), Math.floor(Math.random() * 28) + 1).toISOString().split('T')[0],
            salary: Math.floor(Math.random() * 50000) + 50000,
            address: `北京市朝阳区某某街道${i + 1}号`
        }));
    }

    // 延迟函数
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // 更新筛选器选项
    updateFilters() {
        const departments = [...new Set(this.employees.map(emp => emp.department))].sort();
        const positions = [...new Set(this.employees.map(emp => emp.position))].sort();

        this.updateSelectOptions('departmentFilter', departments);
        this.updateSelectOptions('positionFilter', positions);
    }

    // 更新选择框选项
    updateSelectOptions(selectId, options) {
        const select = document.getElementById(selectId);
        const currentValue = select.value;

        // 保留第一个选项（全部）
        const firstOption = select.options[0];
        select.innerHTML = '';
        select.appendChild(firstOption);

        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            optionElement.textContent = option;
            select.appendChild(optionElement);
        });

        // 恢复之前的选择
        select.value = currentValue;
    }

    // 设置筛选器
    setupFilters() {
        this.updateFilters();
    }

    // 处理搜索
    handleSearch(searchTerm) {
        this.currentPage = 1;
        this.applyFilters();
    }

    // 处理筛选
    handleFilter() {
        this.currentPage = 1;
        this.applyFilters();
    }

    // 应用筛选
    applyFilters() {
        const searchTerm = document.getElementById('searchInput').value.toLowerCase();
        const departmentFilter = document.getElementById('departmentFilter').value;
        const positionFilter = document.getElementById('positionFilter').value;

        this.filteredEmployees = this.employees.filter(employee => {
            const matchesSearch = !searchTerm ||
                employee.name.toLowerCase().includes(searchTerm) ||
                employee.email.toLowerCase().includes(searchTerm) ||
                employee.department.toLowerCase().includes(searchTerm) ||
                employee.position.toLowerCase().includes(searchTerm);

            const matchesDepartment = !departmentFilter || employee.department === departmentFilter;
            const matchesPosition = !positionFilter || employee.position === positionFilter;

            return matchesSearch && matchesDepartment && matchesPosition;
        });

        this.renderEmployees();
        this.renderPagination();
    }

    // 渲染员工列表
    renderEmployees() {
        const grid = document.getElementById('employeeGrid');
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = startIndex + this.itemsPerPage;
        const employeesToShow = this.filteredEmployees.slice(startIndex, endIndex);

        if (employeesToShow.length === 0) {
            grid.innerHTML = `
                <div class="empty-state" style="grid-column: 1 / -1;">
                    <i class="fas fa-users"></i>
                    <h3>暂无员工数据</h3>
                    <p>没有找到符合条件的员工，请尝试调整搜索条件或添加新员工。</p>
                </div>
            `;
            return;
        }

        grid.innerHTML = employeesToShow.map(employee => `
            <div class="employee-card" onclick="employeeManager.openModal(${employee.id})">
                <div class="employee-header">
                    <div class="employee-avatar">
                        ${employee.name.charAt(0)}
                    </div>
                    <div class="employee-info">
                        <h3>${employee.name}</h3>
                        <div class="employee-id">ID: ${employee.id}</div>
                    </div>
                </div>
                <div class="employee-details">
                    <div class="detail-item">
                        <i class="fas fa-envelope"></i>
                        <span>${employee.email}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-phone"></i>
                        <span>${employee.phone || '未填写'}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-building"></i>
                        <span>${employee.department}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-briefcase"></i>
                        <span>${employee.position}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-calendar"></i>
                        <span>${employee.hireDate || '未填写'}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-dollar-sign"></i>
                        <span>${employee.salary ? '¥' + employee.salary.toLocaleString() : '未填写'}</span>
                    </div>
                </div>
            </div>
        `).join('');
    }

    // 渲染分页
    renderPagination() {
        const pagination = document.getElementById('pagination');
        const totalPages = Math.ceil(this.filteredEmployees.length / this.itemsPerPage);

        if (totalPages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        const startIndex = (this.currentPage - 1) * this.itemsPerPage + 1;
        const endIndex = Math.min(this.currentPage * this.itemsPerPage, this.filteredEmployees.length);

        let paginationHTML = `
            <button ${this.currentPage === 1 ? 'disabled' : ''} onclick="employeeManager.goToPage(${this.currentPage - 1})">
                <i class="fas fa-chevron-left"></i> 上一页
            </button>
        `;

        // 页码按钮
        const maxVisiblePages = 5;
        let startPage = Math.max(1, this.currentPage - Math.floor(maxVisiblePages / 2));
        let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

        if (endPage - startPage < maxVisiblePages - 1) {
            startPage = Math.max(1, endPage - maxVisiblePages + 1);
        }

        if (startPage > 1) {
            paginationHTML += `<button onclick="employeeManager.goToPage(1)">1</button>`;
            if (startPage > 2) {
                paginationHTML += `<span>...</span>`;
            }
        }

        for (let i = startPage; i <= endPage; i++) {
            paginationHTML += `
                <button class="${i === this.currentPage ? 'active' : ''}" onclick="employeeManager.goToPage(${i})">
                    ${i}
                </button>
            `;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) {
                paginationHTML += `<span>...</span>`;
            }
            paginationHTML += `<button onclick="employeeManager.goToPage(${totalPages})">${totalPages}</button>`;
        }

        paginationHTML += `
            <div class="page-info">
                显示 ${startIndex}-${endIndex} 条，共 ${this.filteredEmployees.length} 条
            </div>
            <button ${this.currentPage === totalPages ? 'disabled' : ''} onclick="employeeManager.goToPage(${this.currentPage + 1})">
                下一页 <i class="fas fa-chevron-right"></i>
            </button>
        `;

        pagination.innerHTML = paginationHTML;
    }

    // 跳转到指定页面
    goToPage(page) {
        this.currentPage = page;
        this.renderEmployees();
        this.renderPagination();

        // 滚动到顶部
        document.querySelector('.main-content').scrollIntoView({ behavior: 'smooth' });
    }

    // 打开模态框
    openModal(employeeId = null) {
        this.currentEmployee = employeeId ? this.employees.find(emp => emp.id === employeeId) : null;
        this.isEditing = !!employeeId;

        const modal = document.getElementById('employeeModal');
        const title = document.getElementById('modalTitle');
        const deleteBtn = document.getElementById('deleteBtn');
        const form = document.getElementById('employeeForm');

        title.textContent = this.isEditing ? '编辑员工' : '添加员工';
        deleteBtn.style.display = this.isEditing ? 'block' : 'none';

        if (this.isEditing && this.currentEmployee) {
            this.populateForm(this.currentEmployee);
        } else {
            form.reset();
            document.getElementById('employeeId').value = '';
        }

        modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        // 聚焦到第一个输入框
        setTimeout(() => {
            document.getElementById('name').focus();
        }, 300);
    }

    // 关闭模态框
    closeModal() {
        const modal = document.getElementById('employeeModal');
        modal.classList.remove('show');
        document.body.style.overflow = '';

        this.currentEmployee = null;
        this.isEditing = false;
    }

    // 填充表单
    populateForm(employee) {
        document.getElementById('employeeId').value = employee.id;
        document.getElementById('name').value = employee.name;
        document.getElementById('email').value = employee.email;
        document.getElementById('phone').value = employee.phone || '';
        document.getElementById('department').value = employee.department;
        document.getElementById('position').value = employee.position;
        document.getElementById('hireDate').value = employee.hireDate || '';
        document.getElementById('salary').value = employee.salary || '';
        document.getElementById('address').value = employee.address || '';
    }

    // 保存员工
    async saveEmployee() {
        const form = document.getElementById('employeeForm');
        const formData = new FormData(form);

        // 验证表单
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const employeeData = {
            name: formData.get('name').trim(),
            email: formData.get('email').trim(),
            phone: formData.get('phone').trim(),
            department: formData.get('department').trim(),
            position: formData.get('position').trim(),
            hireDate: formData.get('hireDate'),
            salary: formData.get('salary') ? parseFloat(formData.get('salary')) : null,
            address: formData.get('address').trim()
        };

        // 验证邮箱格式
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(employeeData.email)) {
            this.showNotification('请输入有效的邮箱地址', 'error');
            return;
        }

        // 验证邮箱唯一性
        const existingEmployee = this.employees.find(emp =>
            emp.email === employeeData.email &&
            (!this.isEditing || emp.id !== this.currentEmployee.id)
        );

        if (existingEmployee) {
            this.showNotification('该邮箱已被使用', 'error');
            return;
        }

        this.showLoading();

        try {
            await this.delay(500); // 模拟API调用延迟

            if (this.isEditing) {
                // 更新员工
                const index = this.employees.findIndex(emp => emp.id === this.currentEmployee.id);
                if (index !== -1) {
                    this.employees[index] = { ...this.employees[index], ...employeeData };
                }
                this.showNotification('员工信息更新成功');
            } else {
                // 添加新员工
                const newEmployee = {
                    id: Math.max(...this.employees.map(emp => emp.id), 0) + 1,
                    ...employeeData
                };
                this.employees.push(newEmployee);
                this.showNotification('员工添加成功');
            }

            // 这里应该是实际的数据库保存代码
            // 例如: await fetch('/api/employees', { method: 'POST', body: JSON.stringify(employeeData) });

            this.applyFilters();
            this.updateFilters();
            this.closeModal();

        } catch (error) {
            console.error('保存员工失败:', error);
            this.showNotification('保存失败，请重试', 'error');
        } finally {
            this.hideLoading();
        }
    }

    // 显示删除确认
    showDeleteConfirm() {
        document.getElementById('confirmModal').classList.add('show');
    }

    // 隐藏删除确认
    hideDeleteConfirm() {
        document.getElementById('confirmModal').classList.remove('show');
    }

    // 删除员工
    async deleteEmployee() {
        if (!this.currentEmployee) return;

        this.showLoading();

        try {
            await this.delay(500); // 模拟API调用延迟

            // 这里应该是实际的数据库删除代码
            // 例如: await fetch(`/api/employees/${this.currentEmployee.id}`, { method: 'DELETE' });

            this.employees = this.employees.filter(emp => emp.id !== this.currentEmployee.id);

            this.applyFilters();
            this.updateFilters();
            this.hideDeleteConfirm();
            this.closeModal();

            this.showNotification('员工删除成功');

        } catch (error) {
            console.error('删除员工失败:', error);
            this.showNotification('删除失败，请重试', 'error');
        } finally {
            this.hideLoading();
        }
    }
}

// 初始化员工管理系统
let employeeManager;

document.addEventListener('DOMContentLoaded', () => {
    employeeManager = new EmployeeManager();
});

// 导出功能（可选）
window.EmployeeManager = EmployeeManager;