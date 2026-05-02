from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('chat/', views.chat_view, name='chat_post'),
    path('reset/', views.reset_chat, name='reset'),
    path('models/', views.get_models, name='get_models'),
    path('set_model/', views.set_model, name='set_model'),
    path('tasks/', views.get_tasks, name='get_tasks'),
]
