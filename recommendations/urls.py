from django.urls import path

from . import views

app_name = "recommendations"

urlpatterns = [
    path("recommendations/", views.ai_recommendations, name="ai_recommendations"),
    path("recommendations/api/trending/", views.trending_books_api, name="trending_api"),
    path("recommendations/api/homepage/", views.homepage_recommendations_api, name="homepage_api"),
]
