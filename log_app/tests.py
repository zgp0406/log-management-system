from django.test import SimpleTestCase, RequestFactory, override_settings
from django.template.loader import render_to_string
from django.contrib.auth.models import AnonymousUser
from types import SimpleNamespace
from datetime import date

@override_settings(TEMPLATES=[{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [],
    },
}])
class LogPageTemplateTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Mock employee object
        self.employee = SimpleNamespace(
            employee_id=1,
            employee_name="Test User",
            work_id="1001",
            status="ACTIVE"
        )

    def test_log_page_render(self):
        # Create a request
        request = self.factory.get('/logs/?view_mode=all')
        request.user = AnonymousUser()
        
        # Mock session as a simple dict
        request.session = {
            'current_employee_id': 1
        }

        # Context required for the template
        context = {
            'view_mode': 'all',
            'has_admin_access': True,
            'is_boss': False,
            'can_view_all_logs': False,
            'all_employees': [self.employee],
            'request': request,
            'selected_date': date.today(),
            'search': '',
            'logs': [],
            'MEDIA_URL': '/media/',
            # Context variables expected by base.html usually provided by context processors
            'current_employee_name': 'Test User',
            'has_admin_role': True,
        }

        # Try to render the template
        try:
            render_to_string('log_page.html', context, request=request)
        except Exception as e:
            # Re-raise to see full traceback if needed, or fail with message
            import traceback
            traceback.print_exc()
            self.fail(f"Template rendering failed: {e}")
