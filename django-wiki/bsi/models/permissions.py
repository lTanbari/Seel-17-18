from wiki.models import URLPath

from . import article_extensions


def can_check(article, user):
    urlpath = URLPath.objects.get(article=article)
    return not user.is_anonymous() and user.has_perm('wiki.check_article') and article_extensions.UGA.objects.filter(
        url=urlpath)


def can_uncheck(article, user):
    urlpath = URLPath.objects.get(article=article)
    return not user.is_anonymous() and user.has_perm('wiki.uncheck_article') and article_extensions.UGA.objects.filter(
        url=urlpath)


def can_add_change_delete_users(user):
    return user.is_active and user.has_perm('auth.add_user') and user.has_perm('auth.change_user') and user.has_perm(
        'auth.delete_user')
