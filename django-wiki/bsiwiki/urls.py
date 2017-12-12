"""bsiwiki URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django_nyt.urls import get_pattern as get_nyt_pattern
from wiki.urls import get_pattern

from bsi import views
from .init import init

urlpatterns = [
    url(r'^login/', auth_views.login, {'template_name': 'bsi/account/login.html'}, name='login'),
    url(r'^logout/', auth_views.logout, {'next_page': '/'}, name='logout'),
    url(r'^register/', views.register, name='register'),
    url(r'changePassword/', auth_views.password_change, {'template_name': 'bsi/account/accountsSettings.html'},
        name='password_change'),
    url(r'^accounts/password/change/done/$', auth_views.password_change_done,
        {'template_name': 'bsi/account/passwordChangeDone.html'}, name='password_change_done'),
    url(r'^admin/', admin.site.urls),
    url(r'^notifications/', get_nyt_pattern()),
    url(r'^archive/', include('archive.urls')),
    url(r'^', include('bsi.urls')),
    # so far anything that cannot be handled by our urls, is forwarded to django-wiki
    url(r'^', get_pattern()),
]

"""
if necessary, this init function creates a root article, uga, bsi and archive head articles (below root).
todo this is not the best place to put a startup script because dummy threads may run it over time :/
"""
init()
