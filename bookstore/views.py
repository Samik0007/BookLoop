from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def admin_logout_view(request):
    """Handle admin logout for both GET and POST.

    Jazzmin renders the logout as a plain anchor (GET) while Django 4.1+
    requires POST + CSRF for the built-in admin logout, causing 403 errors.
    This view accepts either method, logs the user out, and redirects safely.
    """
    auth_logout(request)
    return redirect('/admin/login/')
