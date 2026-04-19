// 全局变量
let isEditMode = false;
let currentWorkId = '';

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 获取当前员工工号
    const employeeItems = document.querySelectorAll('.employee-item.active');
    if (employeeItems.length > 0) {
        currentWorkId = employeeItems[0].dataset.workId;
    }

    // 初始化搜索功能
    initializeSearch();

    // 保存当前员工到localStorage
    if (currentWorkId) {
        localStorage.setItem('last_employee_work_id', currentWorkId);
    }
});

// 初始化搜索功能
function initializeSearch() {
    const searchInput = document.getElementById('employeeSearch');
    const employeeItems = document.querySelectorAll('.employee-item');

    searchInput.addEventListener('input', function() {
        const searchTerm = this.value.toLowerCase();

        employeeItems.forEach(item => {
            const name = item.querySelector('.employee-name').textContent.toLowerCase();
            const workId = item.querySelector('.employee-work-id').textContent.toLowerCase();

            if (name.includes(searchTerm) || workId.includes(searchTerm)) {
                item.style.display = 'flex';
            } else {
                item.style.display = 'none';
            }
        });
    });
}

// 切换员工
function switchEmployee(workId) {
    // 保存到localStorage
    localStorage.setItem('last_employee_work_id', workId);

    // 跳转到新的员工页面
    window.location.href = `/employee/${workId}/`;
}

// 切换编辑模式
function toggleEditMode() {
    isEditMode = !isEditMode;
    const formInputs = document.querySelectorAll('#employeeForm input, #employeeForm select');
    const editButtons = document.querySelector('.edit-buttons');

    formInputs.forEach(input => {
        if (input.id !== 'work_id') { // 工号不允许编辑
            input.readOnly = !isEditMode;
            input.disabled = !isEditMode;
        }
    });

    if (isEditMode) {
        editButtons.style.display = 'block';
    } else {
        editButtons.style.display = 'none';
    }
}

// 取消编辑
function cancelEdit() {
    isEditMode = false;
    const formInputs = document.querySelectorAll('#employeeForm input, #employeeForm select');
    const editButtons = document.querySelector('.edit-buttons');

    formInputs.forEach(input => {
        input.readOnly = true;
        input.disabled = true;
    });

    editButtons.style.display = 'none';

    // 重新加载页面以恢复原始数据
    location.reload();
}

// 保存员工信息
function saveEmployee() {
    const formData = new FormData();
    const form = document.getElementById('employeeForm');

    // 收集表单数据
    const inputs = form.querySelectorAll('input, select');
    inputs.forEach(input => {
        if (input.value) {
            formData.append(input.id, input.value);
        }
    });

    // 发送更新请求（注意：您需要在Django中添加更新员工的视图）
    fetch(`/employee/${currentWorkId}/update/`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('员工信息更新成功！', 'success');
            toggleEditMode();
            // 可选择性地重新加载页面
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast('更新失败：' + (data.message || '未知错误'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('网络错误，请稍后重试', 'error');
    });
}

// 删除员工
function deleteEmployee() {
    if (!confirm('确定要删除这个员工吗？此操作不可撤销！')) {
        return;
    }

    fetch(`/employee/${currentWorkId}/delete/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken'),
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('员工删除成功！', 'success');
            // 跳转到员工列表或dashboard
            setTimeout(() => {
                window.location.href = '/dashboard/';
            }, 1000);
        } else {
            showToast('删除失败：' + (data.message || '未知错误'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('网络错误，请稍后重试', 'error');
    });
}

// 显示下属员工
function showSubordinates() {
    const subordinatesCard = document.getElementById('subordinatesCard');
    const subordinatesList = document.getElementById('subordinatesList');

    fetch(`/employee/${currentWorkId}/subordinates/`)
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (data.subordinates.length === 0) {
                subordinatesList.innerHTML = '<p class="text-muted">该员工暂无下属</p>';
            } else {
                let html = '<div class="row">';
                data.subordinates.forEach(sub => {
                    html += `
                        <div class="col-md-6 mb-3">
                            <div class="card subordinate-card">
                                <div class="card-body">
                                    <h6 class="card-title">${sub.employee_name}</h6>
                                    <p class="card-text">
                                        <small class="text-muted">工号: ${sub.work_id}</small><br>
                                        <small class="text-muted">职位: ${sub.position || '未设置'}</small><br>
                                        <span class="status-badge status-${sub.status.toLowerCase()}">${sub.status}</span>
                                    </p>
                                    <button class="btn btn-sm btn-outline-primary" onclick="switchEmployee('${sub.work_id}')">
                                        查看详情
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
                subordinatesList.innerHTML = html;
            }
            subordinatesCard.style.display = 'block';
        } else {
            showToast('获取下属信息失败：' + (data.message || '未知错误'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('网络错误，请稍后重试', 'error');
    });
}

// 添加员工
function addEmployee() {
    const form = document.getElementById('addEmployeeForm');
    const formData = new FormData(form);

    // 验证必填字段
    const requiredFields = ['employee_name', 'work_id', 'email'];
    let isValid = true;

    requiredFields.forEach(field => {
        const input = form.querySelector(`[name="${field}"]`);
        if (!input.value.trim()) {
            input.classList.add('is-invalid');
            isValid = false;
        } else {
            input.classList.remove('is-invalid');
        }
    });

    if (!isValid) {
        showToast('请填写所有必填字段', 'error');
        return;
    }

    fetch('/employee/add/', {
        method: 'POST',
        body: formData,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showToast('员工添加成功！', 'success');
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('addEmployeeModal'));
            modal.hide();
            // 清空表单
            form.reset();
            // 重新加载页面
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast('添加失败：' + (data.message || '未知错误'), 'error');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('网络错误，请稍后重试', 'error');
    });
}

// 显示Toast通知
function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');

    toastMessage.textContent = message;

    // 根据类型设置样式
    toast.className = 'toast';
    if (type === 'success') {
        toast.classList.add('bg-success', 'text-white');
    } else if (type === 'error') {
        toast.classList.add('bg-danger', 'text-white');
    } else {
        toast.classList.add('bg-info', 'text-white');
    }

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
}

// 获取CSRF Token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 格式化日期
function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN');
}

// 页面离开时保存状态
window.addEventListener('beforeunload', function() {
    if (currentWorkId) {
        localStorage.setItem('last_employee_work_id', currentWorkId);
    }
});