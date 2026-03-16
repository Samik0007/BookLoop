# 🚀 BookLoop - Setup Instructions

## 📋 What's Been Done

### ✅ Completed Features

1. **Branding Updates**
   - Changed all "Bookworld" references to "BookLoop"
   - Updated site title, meta tags, and admin panel
   - Added developer credit: "Developed by **Samik Bhandari**"
   - Updated contact email to: samikisdope07@gmail.com

2. **Enhanced UI**
   - **Modern Login Page** with gradient background and card design
   - **Beautiful Register Page** with improved styling
   - Google OAuth button UI integrated
   - Hover effects and smooth transitions
   - Mobile-responsive design

3. **Google OAuth Integration** (Requires Configuration)
   - django-allauth installed and configured
   - PyJWT and cryptography dependencies installed
   - Google sign-in button added to login/register pages
   - Backend setup complete

4. **Sample Books Added**
   - 60+ books across multiple genres:
     - Self-Help (5 books)
     - Fiction (5 books)
     - Fantasy/Sci-Fi (5 books)
     - Mystery/Thriller (5 books)
     - Biography/Non-Fiction (5 books)
     - Business (5 books)
     - Romance (5 books)

5. **AI Recommendation System**
   - Smart book recommendations based on user behavior
   - Genre-based recommendations
   - Purchase history tracking
   - Collaborative filtering

---

## 🔐 Google OAuth Setup (Required)

To enable "Sign in with Google", follow these steps:

### Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable **Google+ API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Configure OAuth consent screen:
   - App name: **BookLoop**
   - User support email: samikisdope07@gmail.com
   - Developer contact: samikisdope07@gmail.com
6. Create OAuth 2.0 Client ID:
   - Application type: **Web application**
   - Name: **BookLoop**
   - Authorized redirect URIs:
     ```
     http://127.0.0.1:8000/accounts/google/login/callback/
     http://localhost:8000/accounts/google/login/callback/
     ```
   - For production, add your domain:
     ```
     https://yourdomain.com/accounts/google/login/callback/
     ```

7. Copy **Client ID** and **Client Secret**

### Step 2: Configure Django Settings

Open `bookstore/settings.py` and update:

```python
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'APP': {
            'client_id': 'YOUR_GOOGLE_CLIENT_ID_HERE',  # Paste your Client ID
            'secret': 'YOUR_GOOGLE_CLIENT_SECRET_HERE',  # Paste your Client Secret
            'key': ''
        }
    }
}
```

### Step 3: Add Social App in Django Admin

1. Start server: `python manage.py runserver`
2. Go to admin: http://127.0.0.1:8000/admin/
3. Navigate to **Sites** → Edit the existing site:
   - Domain: `127.0.0.1:8000` (or your domain)
   - Display name: `BookLoop`
4. Go to **Social applications** → Add social application:
   - Provider: **Google**
   - Name: **Google OAuth**
   - Client id: (paste your Client ID)
   - Secret key: (paste your Client Secret)
   - Sites: Select your site and move to "Chosen sites"
5. Save

### Step 4: Test Google Login

1. Visit: http://127.0.0.1:8000/login/
2. Click "Continue with Google" button
3. Should redirect to Google login
4. After authentication, redirects back to BookLoop

---

## 🏃 Running the Project

```bash
# Navigate to project directory
cd /Users/samikbhandari/Downloads/bookworld/Bookworld

# Activate virtual environment
source .venv/bin/activate

# Run migrations (if needed)
python manage.py migrate

# Start server
python manage.py runserver

# Access the site
# Open browser: http://127.0.0.1:8000/
```

---

## 📚 Adding More Books

To add more books, use the custom management command:

```bash
# Edit the command file
# Path: books/management/commands/add_sample_books.py

# Add your book data in the books_data list:
{
    'Book_name': 'Your Book Title',
    'Author': 'Author Name',
    'price': 500,
    'description': 'Book description here',
    'genre': 'Genre Name',
    'quantity': 20
}

# Run the command
python manage.py add_sample_books
```

---

## 🎨 Customizing Styles

### Login/Register Pages
- Files: `templates/login.html` and `templates/register.html`
- Gradient colors can be changed in the `<style>` section
- Current gradient: Purple to Blue (`#667eea` to `#764ba2`)

### Main Site
- CSS files in: `static/css/`
- Main stylesheets:
  - `style.css` - Main site styles
  - `bootstrap.css` - Bootstrap framework
  - `main.css` - Additional custom styles

---

## 📧 Contact Information

- **Developer**: Samik Bhandari
- **Email**: samikisdope07@gmail.com
- **Project**: BookLoop - Online Bookstore
- **Framework**: Django 6.0.2
- **Python**: 3.12.2

---

## 🐛 Troubleshooting

### Issue: Google OAuth not working
**Solution**: 
1. Check Google credentials are correct in settings.py
2. Verify redirect URIs match exactly (including trailing slash)
3. Ensure Social Application is added in Django admin
4. Check site domain matches in admin

### Issue: Static files not loading
**Solution**:
```bash
python manage.py collectstatic
```

### Issue: Database errors
**Solution**:
```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 🚀 Deployment Checklist

When deploying to production:

1. **Update Settings**:
   - Set `DEBUG = False`
   - Update `ALLOWED_HOSTS = ['yourdomain.com']`
   - Use environment variables for secrets
   - Configure production database

2. **Google OAuth**:
   - Add production redirect URI
   - Update site domain in admin

3. **Static Files**:
   - Configure static files hosting
   - Run `collectstatic`

4. **Security**:
   - Change SECRET_KEY
   - Enable HTTPS
   - Configure CSRF settings

---

## 📝 Features Overview

### For Users:
- ✅ Browse 60+ books across multiple genres
- ✅ AI-powered personalized recommendations
- ✅ Google OAuth quick login
- ✅ Add to cart and wishlist
- ✅ Search functionality
- ✅ User profile management
- ✅ Order tracking

### For Admin:
- ✅ Jazzmin admin interface
- ✅ Manage books, orders, users
- ✅ Track user behavior
- ✅ View analytics

---

**Built with ❤️ by Samik Bhandari**
**For academic project purposes**
