"""
URL configuration for tutorialproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, reverse, include
#from django_filters.views import FilterView
from .views import TransactionUpdateView
from . import views

app_name = 'pdfstatement'

urlpatterns = [
    path('', views.pdfstatement_list, name="list"),
    path('transactions-list', views.pdfstatement_transactions_list, name="transactions-list"),
    path('new-statement/', views.pdfstatement_new, name="new-statement"),
    path('chat', views.pdfstatement_chat, name="chat"),
    path('chatbot-view', views.pdfstatement_chatbot_view, name="chatbot-view"),
    path('<slug:slug>', views.pdfstatement_view, name="view"),
    path('change-categories/', views.pdfstatement_change_categories, name="change-categories"),
    path('category-add/', views.pdfstatement_category_add, name="category-add"),
    path('transaction/<slug:slug>/update', TransactionUpdateView.as_view(), name="transaction-update"),
    path('categorize-statements/<slug:slug>', views.pdfstatement_categorize_statement_transactions, name="categorize-transactions"),
    path('ajax/load-pdfparserversions/', views.load_pdfparserversions, name="ajax_load_pdfparserversions"),
    path('ajax/load-changecategoriestransactions/', views.load_changecategoriestransactions, name="ajax_load_changecategoriestransactions"),
    path('select2/', include("django_select2.urls"))
]