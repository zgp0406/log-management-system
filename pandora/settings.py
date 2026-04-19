import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# 简单的 .env 加载器 (避免依赖 python-dotenv)
def load_env_file():
    env_path = BASE_DIR / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    if key not in os.environ:
                        os.environ[key] = value

load_env_file()

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-demo-key-change-in-prod')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*', 'tanesha-unantagonised-zariah.ngrok-free.dev', 'localhost', '127.0.0.1']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'task_app',
    'log_app',
    'dashboard',
    'login_app',
    'ai_app',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'pandora.mobile_redirect_middleware.MobileRedirectMiddleware',
    'pandora.single_session_middleware.SingleSessionMiddleware',
]

ROOT_URLCONF = 'pandora.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.media',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.navbar_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'pandora.wsgi.application'

# Database settings
DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite').strip().lower()
DB_NAME = os.getenv('DB_NAME', 'pandora')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
SQLITE_NAME = os.getenv('SQLITE_NAME', 'pandora_local.sqlite3')

if DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'mysql.connector.django',
            'NAME': DB_NAME,
            'USER': DB_USER,
            'PASSWORD': DB_PASSWORD,
            'HOST': DB_HOST,
            'PORT': DB_PORT,
            'OPTIONS': {
                'charset': 'utf8mb4',
                'raise_on_warnings': False,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / SQLITE_NAME,
        }
    }



LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False

STATIC_URL = 'static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    'https://tanesha-unantagonised-zariah.ngrok-free.dev',
]

CSRF_TRUSTED_ORIGINS = [
    'https://tanesha-unantagonised-zariah.ngrok-free.dev',
]

if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
    CSRF_TRUSTED_ORIGINS += [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]

AI_API_KEY = os.getenv('AI_API_KEY') or '7eefbeb7a0d445a2a33cceab01d9a5a9.09pucGl7mQc6122v'
AI_MODEL = os.getenv('AI_MODEL') or 'glm-4'
AI_PROVIDER = os.getenv('AI_PROVIDER') or 'zhipu'
WECOM_WEBHOOK_URL = os.getenv('WECOM_WEBHOOK_URL') or ''
DINGTALK_WEBHOOK_URL = os.getenv('DINGTALK_WEBHOOK_URL') or 'https://oapi.dingtalk.com/robot/send?access_token=77cee9843cf3f5791896011e38eb31212651c57b8d44b18f08b5f54f350ee76b'
AMAP_WEB_KEY = os.getenv('AMAP_WEB_KEY') or 'fe21e12956d3d68570ff36a16edc992e'
AMAP_SECURITY_JS_CODE = os.getenv('AMAP_SECURITY_JS_CODE') or 'f8c3a05922be825e149d80dcba133975'
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Trust HTTPS from ngrok and secure cookies for mobile access
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Production Security Settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    # X_FRAME_OPTIONS = 'SAMEORIGIN' # Kept at bottom

SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
