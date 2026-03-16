# 🎨 AI Recommendation System - Visual Guide

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTIONS                         │
├─────────────────────────────────────────────────────────────────┤
│  👁️ View    🔍 Search    🛒 Add to Cart    ❤️ Wishlist    💰 Buy │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Track & Store
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     USER BEHAVIOR TABLE                          │
├─────────────────────────────────────────────────────────────────┤
│  user  │  product  │  type  │  timestamp  │  session_id         │
│  john  │  Book #5  │  view  │  2026-01-15 │  abc123            │
│  john  │  Book #5  │  cart  │  2026-01-15 │  abc123            │
│  john  │  Book #5  │  buy   │  2026-01-16 │  abc123            │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Calculate Genre Scores
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                  GENRE PREFERENCE TABLE                          │
├─────────────────────────────────────────────────────────────────┤
│  user  │        genre_scores         │     last_updated         │
│  john  │  {"self-help": 5.0,        │     2026-01-16          │
│        │   "finance": 3.5,           │                          │
│        │   "fiction": 2.0}           │                          │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Feed into AI Engine
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI RECOMMENDATION ENGINE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  Content-Based   │  │  Collaborative   │  │   Trending   │ │
│  │    Filtering     │  │    Filtering     │  │   Analysis   │ │
│  │                  │  │                  │  │              │ │
│  │  Genre Matching  │  │  Similar Users   │  │  Popular in  │ │
│  │   (40% weight)   │  │   (35% weight)   │  │ User Genres  │ │
│  │                  │  │                  │  │ (25% weight) │ │
│  └─────────┬────────┘  └─────────┬────────┘  └──────┬───────┘ │
│            │                     │                    │         │
│            └──────────┬──────────┴────────────────────┘         │
│                       │                                         │
│                       ▼                                         │
│              Weighted Combination                               │
│              Score = 0.4C + 0.35Co + 0.25T                     │
│                       │                                         │
│                       ▼                                         │
│              Sort by Score & Return Top 8                       │
└────────────┬────────────────────────────────────────────────────┘
             │
             │ Display Results
             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     USER INTERFACE                               │
├─────────────────────────────────────────────────────────────────┤
│  🏠 Home Page: "Recommended For You" (8 books)                  │
│  📖 Product Page: "You May Also Like" (6 similar books)         │
└─────────────────────────────────────────────────────────────────┘
```

## 🔄 Recommendation Flow

```
User Action
    │
    ├─► View Book ──────► Track (weight 0.5) ─┐
    │                                          │
    ├─► Search ────────► Track & Log ─────────┤
    │                                          │
    ├─► Add to Cart ───► Track (weight 1.5) ──┤
    │                                          │
    ├─► Add to Wishlist ► Track (weight 1.0) ─┤
    │                                          │
    └─► Purchase ──────► Track (weight 3.0) ──┤
                                               │
                                               ▼
                                    Update Genre Preferences
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │   Calculate Recommendations When:   │
                    │   • User visits home page           │
                    │   • User views product detail       │
                    └──────────────┬───────────────────────┘
                                   │
                                   ▼
                        Run AI Recommendation Engine
                                   │
                                   ▼
                             Return Results
```

## 🧮 Score Calculation Example

```
User: John
Purchases: 
  - "Atomic Habits" (Self-Help)
  - "Rich Dad Poor Dad" (Finance)
Wishlist:
  - "Think and Grow Rich" (Finance, Self-Help)

Genre Scores:
  self-help: 3.0 (purchase) + 1.0 (wishlist) = 4.0
  finance: 3.0 (purchase) + 1.0 (wishlist) = 4.0

───────────────────────────────────────────────────────────

Candidate Book: "The Power of Now"
Genre: Self-Help, Spirituality

Content-Based Score:
  - Matches "self-help" (4.0 points)
  - New genre "spirituality" (0 points)
  - Average: 4.0 / 2 = 2.0

Collaborative Score:
  - User B also bought "Atomic Habits"
  - User B bought "The Power of Now"
  - Similarity: 0.6
  - Score: 0.6

Trending Score:
  - 45 purchases in last 60 days in "Self-Help"
  - Normalized: 0.8

───────────────────────────────────────────────────────────

Final Score:
  (2.0 × 0.4) + (0.6 × 0.35) + (0.8 × 0.25)
  = 0.8 + 0.21 + 0.2
  = 1.21

✅ High score → Recommended!
```

## 🎯 Similar Books Algorithm

```
Product: "Atomic Habits"
Author: James Clear
Genre: Self-Help

Step 1: Find books with same genre
  ├─► Query: genre contains "Self-Help"
  └─► Result: 15 books

Step 2: Prioritize same author
  ├─► Filter: author = "James Clear"
  └─► Result: 3 books (get top 3)

Step 3: Fill remaining slots
  ├─► Get other Self-Help books
  └─► Result: 3 more books

Step 4: Return 6 similar books
  └─► [3 same author, 3 same genre]
```

## 📈 Learning Process

```
Time: Day 1
User Activity: View "Fiction" book
Genre Scores: {"fiction": 0.5}
Recommendations: Mix of all genres (not enough data)

───────────────────────────────────────────────────────────

Time: Day 2
User Activity: Buy "Fiction" book
Genre Scores: {"fiction": 3.5}
Recommendations: 60% Fiction, 40% Others

───────────────────────────────────────────────────────────

Time: Day 5
User Activity: Buy 2 more "Fiction", 1 "Mystery"
Genre Scores: {"fiction": 9.5, "mystery": 3.0}
Recommendations: 70% Fiction, 20% Mystery, 10% Others

───────────────────────────────────────────────────────────

Time: Day 10
User Activity: Regular browsing
Genre Scores: {"fiction": 12.0, "mystery": 5.5, "thriller": 2.0}
Recommendations: Highly personalized!
  + Similar users' choices
  + Trending in preferred genres
```

## 🏗️ Database Schema

```
┌─────────────────────┐
│      Product        │
├─────────────────────┤
│ id (PK)            │
│ Book_name          │
│ Author             │
│ genre              │◄──────────┐
│ price              │           │
│ description        │           │
└─────────────────────┘           │
                                  │
                                  │ Foreign Key
┌─────────────────────┐           │
│   UserBehavior      │           │
├─────────────────────┤           │
│ id (PK)            │           │
│ user               │           │
│ product (FK)       ├───────────┘
│ interaction_type   │
│ search_query       │
│ timestamp          │
│ session_id         │
└────────┬────────────┘
         │
         │ Aggregates into
         ▼
┌─────────────────────┐
│ UserGenrePreference │
├─────────────────────┤
│ id (PK)            │
│ user (Unique)      │
│ genre_scores (JSON)│
│ last_updated       │
└─────────────────────┘

Example genre_scores:
{
  "fiction": 8.5,
  "self-help": 6.0,
  "finance": 4.5,
  "mystery": 3.0
}
```

## 🎬 User Journey Visualization

```
👤 New User
    │
    └─► Visits Home Page
         │
         ├─► Not logged in → See Popular Books
         │
         └─► Logged in → See "Recommended For You"
              (Initially based on popular books)
                      │
                      ▼
              Browse & Click Books
                      │
                      ▼
              View Product Details
                      │
                      ├─► See "You May Also Like"
                      │
                      └─► Tracked: +0.5 to genre
                                │
                                ▼
                      Add to Wishlist/Cart
                                │
                                └─► Tracked: +1.0 or +1.5 to genre
                                          │
                                          ▼
                                  Make Purchase
                                          │
                                          └─► Tracked: +3.0 to genre
                                                    │
                                                    ▼
                                          Return to Home Page
                                                    │
                                                    └─► SEE PERSONALIZED RECOMMENDATIONS! 🎯
```

## 🔄 Collaborative Filtering Example

```
Books in Database:
  Book A, Book B, Book C, Book D, Book E

User Interactions:
┌──────┬───────┬───────┬───────┬───────┬───────┐
│ User │ Book A│ Book B│ Book C│ Book D│ Book E│
├──────┼───────┼───────┼───────┼───────┼───────┤
│ John │   ✓   │   ✓   │   ✓   │   ✗   │   ✗   │
│ Sarah│   ✓   │   ✓   │   ✗   │   ✓   │   ✓   │
│ Mike │   ✗   │   ✓   │   ✓   │   ✓   │   ✗   │
└──────┴───────┴───────┴───────┴───────┴───────┘

Similarity Calculation (John vs Sarah):
  Common: {Book A, Book B}
  Total: {Book A, Book B, Book C, Book D, Book E}
  Jaccard Similarity = 2/5 = 0.4

Recommendation for John:
  Sarah bought Book D and Book E
  Recommend with score 0.4 each

Most Similar User to John: Sarah (0.4)
  → Recommend: Book D, Book E
```

## 🎨 UI Components

```
┌─────────────────────────────────────────────────────────┐
│                     HOME PAGE                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  🎯 Recommended For You                                 │
│  Based on your interests and browsing history           │
│  ─────────────────────────────────────────────────      │
│                                                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐               │
│  │ 📚   │  │ 📚   │  │ 📚   │  │ 📚   │               │
│  │ Book1│  │ Book2│  │ Book3│  │ Book4│               │
│  │ $299 │  │ $399 │  │ $199 │  │ $499 │               │
│  └──────┘  └──────┘  └──────┘  └──────┘               │
│                                                          │
│  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐               │
│  │ 📚   │  │ 📚   │  │ 📚   │  │ 📚   │               │
│  │ Book5│  │ Book6│  │ Book7│  │ Book8│               │
│  │ $349 │  │ $449 │  │ $299 │  │ $399 │               │
│  └──────┘  └──────┘  └──────┘  └──────┘               │
│                                                          │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                PRODUCT DETAIL PAGE                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  📚 Atomic Habits                                        │
│  by James Clear                                          │
│  Genre: Self-Help                                        │
│  Price: Rs. 499                                          │
│  [Add to Cart] [Add to Wishlist]                       │
│                                                          │
│  ─────────────────────────────────────────────────      │
│                                                          │
│  📖 You May Also Like                                   │
│  Similar books based on genre and author                │
│  ─────────────────────────────────────────────────      │
│                                                          │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐      │
│  │ 📚  │ │ 📚  │ │ 📚  │ │ 📚  │ │ 📚  │ │ 📚  │      │
│  │Book1│ │Book2│ │Book3│ │Book4│ │Book5│ │Book6│      │
│  └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘      │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## 📊 Performance Metrics

```
Query Performance:
┌──────────────────────────┬─────────────┬────────────┐
│ Operation                │ Time (ms)   │ Queries    │
├──────────────────────────┼─────────────┼────────────┤
│ Get Recommendations      │ 50-100      │ 4-6        │
│ Track Interaction        │ 5-10        │ 1-2        │
│ Get Similar Books        │ 20-40       │ 2-3        │
│ Update Genre Preference  │ 10-20       │ 1-2        │
└──────────────────────────┴─────────────┴────────────┘

Scalability:
┌──────────────────┬──────────────────────────────────┐
│ Users            │ Performance                      │
├──────────────────┼──────────────────────────────────┤
│ 1-100            │ ⚡ Instant (<50ms)               │
│ 100-1,000        │ ✓ Very Fast (<100ms)            │
│ 1,000-10,000     │ ✓ Fast (<200ms)                 │
│ 10,000+          │ ✓ Good (add caching)            │
└──────────────────┴──────────────────────────────────┘
```

---

This visual guide helps understand the complete system flow and architecture! 🎨
