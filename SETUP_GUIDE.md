# 🚀 Quick Setup Guide - AI Recommendation System

## Step-by-Step Installation

### Step 1: Activate Your Virtual Environment
```bash
cd /Users/samikbhandari/Downloads/bookworld/Bookworld
source .venv/bin/activate  # On Mac/Linux
# OR
.venv\Scripts\activate  # On Windows
```

### Step 2: Install Required Packages (if not already installed)
```bash
pip install django pillow
```

### Step 3: Create Database Migrations
```bash
python manage.py makemigrations books
```

You should see output like:
```
Migrations for 'books':
  books/migrations/0003_userbehavior_usergenrepreference.py
    - Create model UserBehavior
    - Create model UserGenrePreference
    - Add index to UserBehavior
```

### Step 4: Apply Migrations to Database
```bash
python manage.py migrate
```

You should see:
```
Running migrations:
  Applying books.0003_userbehavior_usergenrepreference... OK
```

### Step 5: Start Development Server
```bash
python manage.py runserver
```

Visit: `http://127.0.0.1:8000/`

## ✅ Verification Checklist

### Test 1: Home Page Recommendations
1. ✅ Go to home page
2. ✅ Look for "Recommended For You" section (if logged in)
3. ✅ Or "Popular Books" section (if not logged in)
4. ✅ Should see 8 book recommendations in nice cards

### Test 2: Product Detail Similar Books
1. ✅ Click on any book
2. ✅ Scroll to bottom
3. ✅ Look for "You May Also Like" section
4. ✅ Should see 6 similar books

### Test 3: User Behavior Tracking
1. ✅ Login to your account
2. ✅ Browse a few books (view detail pages)
3. ✅ Add a book to wishlist
4. ✅ Add a book to cart
5. ✅ Search for books
6. ✅ All interactions are now being tracked!

### Test 4: Admin Panel (Optional)
1. ✅ Go to `http://127.0.0.1:8000/admin/`
2. ✅ Login with superuser credentials
3. ✅ Look for "User Behaviors" and "User Genre Preferences"
4. ✅ You can see all tracked interactions

## 🎯 How to Test Recommendations

### Scenario 1: Build a Profile
1. **Login** to your account
2. **Browse** 5-6 books in same genre (e.g., "Fiction" or "Self-Help")
3. **Add 2-3 to wishlist**
4. **Purchase 1 book**
5. **Go back to home page**
6. **Result:** Should see more books from that genre recommended!

### Scenario 2: Similar Books
1. **Go to any book detail page** (e.g., "Atomic Habits")
2. **Scroll down** to "You May Also Like"
3. **Result:** Should see other Self-Help or similar author books

## 🔧 Troubleshooting

### Problem: No recommendations showing
**Solution:** 
- Make sure you're logged in
- Add some books to cart/wishlist first
- System needs some interaction data to learn

### Problem: Migration error
**Solution:**
```bash
python manage.py makemigrations books --empty
# Then run makemigrations again
python manage.py makemigrations books
python manage.py migrate
```

### Problem: Import errors
**Solution:**
- Make sure virtual environment is activated
- Reinstall: `pip install django pillow`

## 📊 Understanding the System

### What Gets Tracked:
- 👁️ **Views**: When you open a book detail page
- 🔍 **Searches**: What you search for
- 🛒 **Cart Adds**: Books added to cart
- ❤️ **Wishlist Adds**: Books saved to wishlist
- 💰 **Purchases**: Completed orders

### How Scoring Works:
- Purchase = 3.0 points (highest)
- Cart Add = 1.5 points
- Wishlist Add = 1.0 points
- View = 0.5 points (lowest)

### Example:
If you purchase "Atomic Habits" (Self-Help):
- ✅ Self-Help genre gets +3.0 points
- ✅ Next time: More Self-Help books recommended
- ✅ Also finds users who bought same book
- ✅ Recommends what they bought too

## 🎓 For Presentation

### Key Points to Highlight:
1. ✅ **Hybrid AI Approach** - Combines 3 algorithms
2. ✅ **Real-time Learning** - Gets better with use
3. ✅ **Personalized** - Each user gets unique recommendations
4. ✅ **Production-Ready** - Professional code quality
5. ✅ **Scalable** - Can handle many users

### Demo Flow:
1. Show home page with recommendations
2. Click a book, show similar books section
3. Open admin panel, show tracked behavior
4. Explain the AI algorithms briefly

## 📈 Advanced Features

Already included:
- ✅ Collaborative filtering (similar users)
- ✅ Content-based filtering (genre matching)
- ✅ Trending analysis (popular in your genres)
- ✅ Session tracking
- ✅ Fallback mechanisms
- ✅ Database optimization (indexes)

## 🎉 Success!

If you see recommendations on your home page, **congratulations!** 🎊

Your AI recommendation system is now:
- ✅ Installed
- ✅ Configured
- ✅ Running
- ✅ Learning from users

## 💡 Tips

1. **More data = Better recommendations**
   - Have friends/test users try the system
   - More interactions = More accurate

2. **Genre is key**
   - Make sure books have genres set
   - System learns based on genres

3. **Be patient**
   - First few recommendations might be generic
   - Gets personalized after 5-10 interactions

---

**Need Help?**
Check [AI_RECOMMENDATION_SYSTEM.md](AI_RECOMMENDATION_SYSTEM.md) for detailed documentation.

**Ready to impress your supervisor!** 🚀
