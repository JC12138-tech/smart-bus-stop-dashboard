"""
URL configuration for config project.

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
from django.contrib import admin
from django.urls import path
from core.views import home, upload_csv, dashboard

urlpatterns = [
    path("", home, name="home"),
    path("upload/", upload_csv, name="upload_csv"),
    path("admin/", admin.site.urls),
]


urlpatterns = [
    path("", home, name="home"),
    path("upload/", upload_csv, name="upload_csv"),
    path("dashboard/", dashboard, name="dashboard"),
    path("admin/", admin.site.urls),
]

from core.views import home, upload_csv, dashboard, export_xlsx

urlpatterns = [
    path("", home, name="home"),
    path("upload/", upload_csv, name="upload_csv"),
    path("dashboard/", dashboard, name="dashboard"),
    path("export.xlsx", export_xlsx, name="export_xlsx"),
    path("admin/", admin.site.urls),
]
