from django.contrib.auth.models import User
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
#from .models import <tableName>
# from bsi.core.paginator import WikiPaginator
from wiki.models.article import Article
#from wiki.tests.test_views import SearchViewTest
<<<<<<< HEAD
from wiki.views.article import SearchView
from wiki.views.article import ArticleView
=======
from wiki.views.article import SearchView, Create
from wiki import forms
>>>>>>> origin/templates
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from django import forms
from wiki.views.mixins import ArticleMixin
from wiki.models.urlpath import URLPath


class BSIArticleView(ArticleView):
    template_name = "bsi/article.html"

    def dispatch(self, request, article, *args, **kwargs):
        return super(BSIArticleView, self).dispatch(request, article, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return ArticleMixin.get_context_data(self, **kwargs)

class UGACreate(Create):
    template_name = 'bsi/create_article.html'
    def dispatch(self, request, article, *args, **kwargs):
        return super(UGACreate, self).dispatch(request, article, *args, **kwargs)



class BSISearchView(SearchView):
    template_name = "bsi/search.html"
    
    def dispatch(self, request, *args, **kwargs):
        return super(BSISearchView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super(BSISearchView, self).get_queryset()

    def get_context_data(self, **kwargs):
        return super(BSISearchView, self).get_context_data(**kwargs)


def index(request):
    all_articles = Article.objects.all()

    template = loader.get_template('bsi/index.html')
    context = {
        'all_articles':all_articles,
    }  
    return HttpResponse(template.render(context, request))


def bsicatalog(request):
    all_articles = Article.objects.all()

    template = loader.get_template('bsi/article.html')
    context = {
        'all_articles':all_articles,
    }
    return HttpResponse(template.render(context, request))


@login_required
def home(request):
    return render(request, 'home.html')


class UserRegistrationForm(forms.Form):
    username = forms.CharField(
        required=True,
        label='Username',
        max_length=32
    )
    email = forms.CharField(
        required=True,
        label='Email',
        max_length=32,
    )
    password = forms.CharField(
        required=True,
        label='Password',
        max_length=32,
        widget=forms.PasswordInput()
    )

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'bsi/account/register.html', {'form': form})

def create(request):
    return render(request, 'bsi/create_article.html')