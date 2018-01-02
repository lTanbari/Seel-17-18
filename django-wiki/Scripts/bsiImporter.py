import argparse
import django
import configparser
import sys
from os.path import isdir, join, isfile, basename, split, splitext
from os import listdir, environ, walk
import pdb
from django.http import Http404
from datetime import datetime

sys.path.append(r'..')
environ.setdefault("DJANGO_SETTINGS_MODULE", "bsiwiki.settings")
django.setup()

from bsiwiki import settings
from bsi.models.article_extensions import BSI, BSI_Article_type
from wiki.models import URLPath, ArticleRevision, Article
from archive.models import Archive, ArchiveTransaction

new_temp_bsi_folder = './mdNew'
crfDir = './CRF/'
system_devices = ["APP", "SYS", "IND", "CON", "ISMS", "ORP", "OPS", "DER", "NET", "INF"]

# temporary variable for cross reference files. If set to TRUE, append CR to files, otherwise don't
# for testing, we should not append the CR everytime we run the importer, because then the files would contain 
# multiple CR
doCR = False

def readConfig(varname):
    configParser = configparser.RawConfigParser()
    configParser.read("config.cfg")
    return configParser.get('bsi', varname)


def parseArgs():
    parser = argparse.ArgumentParser('Imports new or updated BSI contents to the database')
    parser.add_argument('-u', '--update', help='Use this option only when it is an update, it should be followed by '
                        'the path to the text file containing the modified files')

    args = parser.parse_args()
    if(args.update is not None):
        if(not isfile(args.update)):
            raise ValueError("Please give a valid file path!")
        if(not args.update.endswith('txt')):
            raise ValueError("The file may only be a text file!")

    return args.update


def main(update):
    if(update):
        doUpdate(update)
    else:
        doImport()

    cleanUp()


def doImport():
        # go through the dir and read the content of each file
        # if it's a component, append the threat-measures relationships
        # just in case, look in DB, find if an article with the same headerID exists
        # if it doesn't (it should always be this case)
        # then create a new article and its urlpath
        bsi_root = BSI.get_or_create_bsi_root('')
        for dirpath, dirnames, filenames in walk(settings.CRAWLER_DIRECTORY):
            if not filenames:
                continue

            # check the bsi article type is a component or threat or implementation notes
            sub_article_type = basename(dirpath)
            if sub_article_type == "C":
                article_type = BSI_Article_type.COMPONENT
                parent = BSI.get_or_create_bsi_subroots(bsi_root, "components", "BSI.importer", "", "Components")
            elif sub_article_type == "N":
                article_type = BSI_Article_type.IMPLEMENTATIONNOTES
                parent = BSI.get_or_create_bsi_subroots(bsi_root, "implementationnotes", "BSI.importer", "",
                                                        "Implementation Notes")
            elif sub_article_type == "T":
                article_type = BSI_Article_type.THREAT
                parent = BSI.get_or_create_bsi_subroots(bsi_root, "threats", "BSI.importer", "", "Threats")
            else:
                continue

            for filename in [f for f in filenames if f.endswith(".md")]:
                # get the drive and the filepath
                path_and_file = join(dirpath, filename)
                # get the path and file name
                location, file = split(path_and_file)
                # get the file id and the titel
                file_name = splitext(file)[0]
                id = get_bsi_article_id(sub_article_type, file_name)

                # append the Cross reference relation files to the content
                # of each component article before import it in the database
                if sub_article_type == "C" and isdir(crfDir) and doCR:
                    appendThreatMeasureRelation(path_and_file, id)

                # import the content to the database
                with open(path_and_file) as data_file:
                    content = data_file.read()
                    revision_kwargs = {'content': content, 'user_message': 'BSI.importer',
                                       'ip_address': '0.0.0.0'}
                    BSI.create(parent=parent, slug=id, title=file_name, article_type=article_type, **revision_kwargs)
                    print(file_name + " is saved")

import json
def doUpdate(file):
    # find out which files should be m/a/d
    modified, added, deleted = checkFileAction(file)
    # just to see how they look
    print(json.dumps(modified, indent=4))
    print(json.dumps(added, indent=4))
    print(json.dumps(deleted, indent=4))

    new_page = createNewPage()

    # go through the dir and read the content of each file
    for dirpath, dirnames, filenames in walk(new_temp_bsi_folder):
        if not filenames:
            continue
        sub_article_type = basename(dirpath)
        if sub_article_type == "C":
            article_type = BSI_Article_type.COMPONENT
            bsi_type = 'component'
            new_bsi_subroot = BSI.get_or_create_bsi_subroots(new_page, "components", "BSI.importer", "", "Components")
        elif sub_article_type == "N":
            article_type = BSI_Article_type.IMPLEMENTATIONNOTES
            bsi_type = 'implementationnotes'
            new_bsi_subroot = BSI.get_or_create_bsi_subroots(new_page, "implementationnotes", "BSI.importer", "",
                                                                "Implementation Notes")
        elif sub_article_type == "T":
            article_type = BSI_Article_type.THREAT
            bsi_type = 'threat'
            new_bsi_subroot = BSI.get_or_create_bsi_subroots(new_page, "threats", "BSI.importer", "", "Threats")
        else:
            continue

        for filename in [f for f in filenames if f.endswith(".md")]:
            # get the drive and the filepath
            path_and_file = join(dirpath, filename)
            # get the path and file name
            location, file = split(path_and_file)
            # get the file id and the titel
            file_name = splitext(file)[0]
            id = get_bsi_article_id(sub_article_type, file_name)
            # if the file is new or modified, add to database under /new
            if(is_contained_in(modified, bsi_type, id) or is_contained_in(added, bsi_type, id)):
                if sub_article_type == "C" and isdir(crfDir):
                    appendThreatMeasureRelation(path_and_file, id)

                # import the content to the database
                with open(path_and_file) as data_file:
                    content = data_file.read()
                    revision_kwargs = {'content': content, 'user_message': 'BSI.importer',
                                       'ip_address': '0.0.0.0'}
                    BSI.create(parent=new_bsi_subroot, slug=id, title=file_name, article_type=article_type, **revision_kwargs)
                    print(new_bsi_subroot)
                    print(file_name + " " + id +" "+ bsi_type + " is saved")

    fillNewPage(modified, added, deleted, new_page)

    return


def createNewPage():
    # first check if it is already there
    # this is just sanity check, the new page should not exist
    try:
        new = URLPath.objects.get(slug='new')
    except Exception:
        # it does not exist, so create it
        root = URLPath.root()
        rev_kwargs = {'content': '', 'user_message': 'Importer.create', 'ip_address': '0.0.0.0'}
        new = URLPath.create_urlpath(parent=root, slug='new', title='What\'s new', **rev_kwargs)
    return new


def is_contained_in(dic, bsi_type, bsi_id):
    for elem in dic.get('type'):
        if(elem.get('name') == bsi_type):
            for file in elem.get('files'):
                if(file.get('file') == bsi_id):
                    return True
    return False


def fillNewPage(modified, added, deleted, new_page):
    bsi = BSI.get_or_create_bsi_root('')
    content = 'The following articles have been changed in the new BSI Catalogue:<br />'
    for bsi_type in new_page.get_children():
        if(bsi_type.slug == 'components'):
            bsi_parent = URLPath.objects.filter(slug='components', parent=bsi)[0]
            content += '<br />Components:<br />'
            for article in bsi_type.get_children():
                if(is_contained_in(modified, 'component', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (modified)<br />'
                elif(is_contained_in(added, 'component', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (new)<br />'
            for del_article in deleted.get('type'):
                if(del_article.get('name') == 'component'):
                    for file in del_article.get('files'):
                        content += '[' + file.get('file') + '](' + URLPath.objects.get(slug=file.get('file'), parent=bsi_parent).path + ') (deleted)<br />'
        if(bsi_type.slug == 'threats'):
            bsi_parent = URLPath.objects.filter(slug='threats', parent=bsi)[0]
            content += '<br />Threats:<br />'
            for article in bsi_type.get_children():
                if(is_contained_in(modified, 'threat', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (modified)<br />'
                elif(is_contained_in(added, 'threat', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (new)<br />'
            for del_article in deleted.get('type'):
                if(del_article.get('name') == 'threat'):
                    for file in del_article.get('files'):
                        content += '[' + file.get('file') + '](' + URLPath.objects.get(slug=file.get('file'), parent=bsi_parent).path + ') (deleted)<br />'
        elif(bsi_type.slug == 'implementationnotes'):
            bsi_parent = URLPath.objects.filter(slug='implementationnotes', parent=bsi)[0]
            content += '<br />Implementation Notes:<br />'
            for article in bsi_type.get_children():
                if(is_contained_in(modified, 'implementationnotes', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (modified)<br />'
                elif(is_contained_in(added, 'implementationnotes', article.slug)):
                    content += '[' + article.slug + '](' + article.path.replace('new/', '') + ') (new)<br />'
            for del_article in deleted.get('type'):
                if(del_article.get('name') == 'implementationnotes'):
                    for file in del_article.get('files'):
                        content += '[' + file.get('file') + '](' + URLPath.objects.get(slug=file.get('file'), parent=bsi_parent).path + ') (deleted)<br />'
    revision = ArticleRevision()
    revision.inherit_predecessor(new_page.article)
    from markdownify import markdownify as md
    revision.content = md(content)
    new_page.article.add_revision(revision)
    print('Content of ' + new_page.path + ' is updated!')

def find_between(s, first, last):
    # find the Implementation Notes id in the file name
    try:
        start = s.index(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

def get_bsi_article_id(type, file_name):
    # search the BSI id in the file name
    id = ''
    if type == 'C':
        id = file_name.split(" ", 1)[0]
    elif type == "T":
        id = "".join(file_name.split(" ", 2)[:2])
    elif type == "N":
        for n_id in system_devices:
            if n_id in file_name:
                id = find_between(file_name, n_id, " ")

    return id

import pdb
def post_phase(archiving_data):
        # after 30 days
        # create archive
        # move the old bsi articles with their related uga articles to archive
        # change the url of he new one to the old one
        # delete the new (change log) page
        archive = Archive.get_or_create(archiving_data)
        new = URLPath.objects.get(slug='new')
        bsi = URLPath.objects.get(slug='bsi')
        types = URLPath.objects.filter(parent=new)
        # print(type)
        for new_type in types:
              if new_type.slug == "components":
                  post_phase_move_bsi(new_type=new_type, default_type= "components",old_parent = bsi, archive = archive)
              elif new_type.slug == "threats":
                   post_phase_move_bsi(new_type=new_type, default_type="threats", old_parent=bsi, archive=archive)
              elif new_type.slug == "implementationnotes":
                   post_phase_move_bsi(new_type=new_type, default_type="implementationnotes", old_parent=bsi, archive=archive)

        #post_phase_delete_url(new)
        #updateModificationTime()


def post_phase_move_bsi(new_type, default_type, old_parent, archive):
    # for each type append the new updates
    pdb.set_trace()
    new_articles = []
    articles = []
    if default_type == "components":
        type_symbol = BSI_Article_type.COMPONENT
        # print(type_symbol)
    elif default_type == "threats":
        type_symbol = BSI_Article_type.THREAT
    elif default_type == "implementationnotes":
        type_symbol = BSI_Article_type.IMPLEMENTATIONNOTES
    if new_type.slug == default_type:
        bsi_type = URLPath.objects.get(parent=old_parent, slug= default_type)
        # print(bsi_type)
        new_articles = new_type.get_children()
        for new_article in new_articles:
            try:
                old_article = URLPath.objects.get(parent=bsi_type, slug=new_article.slug)
                for ancestor in old_article.article.ancestor_objects():
                    ancestor.article.clear_cache()
                old_article.slug = type_symbol.label.lower()[:1] +"_" + old_article.slug
                old_article.save()
                ArchiveTransaction.create(archive, old_article).archive()
                post_phase_move_references(archive, old_article)
            except Exception:
                # do nothing
                print('old article not found')
            #articles = BSI.get_articles_by_type(type_symbol)
            # print(articles)
            #for article in articles:
            #    if article.slug == new_article.slug:
            #        article.slug = type_symbol.label.lower()[:1] +"_" + article.slug
            #        ArchiveTransaction.create(archive, article).archive()
            #        post_phase_move_references(archive, article)

            new_article.save()
            bla1 = URLPath.objects.get(pk=new_article.pk)
            for ancestor in new_article.article.ancestor_objects():
                ancestor.article.clear_cache()
            new_article.save()
            bla = URLPath.objects.get(pk=new_article.pk)
            new_article.parent = bsi_type
            new_article.save()
            #new_article.cached_ancestors = new_article.parent.cached_ancestors + [new_article.parent]
            new_article.set_cached_ancestors_from_parent(new_article.parent)
            bla2 = URLPath.objects.get(pk=new_article.pk)
            new_article.save()
            # Reload url path form database
            new = URLPath.objects.get(pk=new_article.pk)
            # print(urlpath_article.path)
            # Use a copy of ourself (to avoid cache) and update article links again
            #for ancestor in Article.objects.get(pk=new_article.article.pk).ancestor_objects():
            #        ancestor.article.clear_cache()

def post_phase_move_references(archive, bsi_article):
    # move the uga articles that related to the old bsi to archive
    uga_ref = bsi_article.bsi.references.all()
    for ref in uga_ref:
        ArchiveTransaction.create(archive, ref.url).archive()

def post_phase_delete_url(path):
    # delete the new page and its subroots
    children = path.get_children()
    #print(children)
    if children:
        for child in children:
            # print(child)
            child.article.delete()
            print('deleted ' + child.path)
    #        child.save()
    #path.delete_subtree()
    path.article.delete()
    #return path.is_deleted()
    print("new path is deleted")

def updateModificationTime():
    # update the date for all unchange and change articles
    new_date = datetime.now()
    # new = datetime(2009, 10, 5)
    for bsi in BSI.objects.all():
        bsi.url.article.modified = new_date
        bsi.url.article.current_revision.modified = new_date
        bsi.url.article.current_revision.save()
        bsi.url.article.save()
    #for revision in ArticleRevision.objects.all():
    #     revision.modified = new_date
    #     revision.save()
    return

def checkFileAction(filepath):
    modified = initDict()
    added = initDict()
    deleted = initDict()

    # sanity check
    assert(filepath is not None)

    # look in the text file and check if the files shoul be m/a/d
    file = open(filepath, "r")
    currentSep1 = file.readline().rstrip()
    currentSep2 = file.readline().rstrip()

    for line in file:
        line = line.rstrip()
        if(line.startswith('#')):
            currentSep1 = line
            continue
        if(line.startswith('%')):
            currentSep2 = line
            continue

        if(currentSep2.startswith('%m')):
            types = modified.get('type')
        elif(currentSep2.startswith('%a')):
            types = added.get('type')
        elif(currentSep2.startswith('%d')):
            types = deleted.get('type')
        else:
            raise ValueError('Input file might be corrupted.')

        if(currentSep1.startswith('#C')):
            name = 'component'
            sub = 'C'
        elif(currentSep1.startswith('#T')):
            name = 'threat'
            sub = 'T'
        elif(currentSep1.startswith('#N')):
            name = 'implementationnotes'
            sub = 'N'
        else:
            raise ValueError('Input file might be corrupted.')

        obj = [c for c in types if c.get('name') == name][0]
        if obj:
            obj['files'].append({'file': get_bsi_article_id(sub, line)})

    return modified, added, deleted


def initDict():
    return {'type': [
            {'name': 'component', 'files': []},
            {'name': 'threat', 'files': []},
            {'name': 'implementationnotes', 'files': []}]}


def appendThreatMeasureRelation(path_and_file, id):
    try:
        for cr_file in [f for f in listdir(crfDir) if f.endswith(".md")]:
            path_and_ref = join(crfDir, cr_file)
            if id in cr_file:
                with open(path_and_ref, 'r')as cr:
                    cr_data = cr.read()
                cr.close()
                with open(path_and_file, 'a') as data_file:
                    data_file.write(cr_data)
                data_file.close()
    except IOError:
        print('An error occurred trying to open (read/write) the file.')


def cleanUp():
    # TODO remove all temp dirs and update files in current dirs
    # We need the path to old BSI dir to update its content?
    return


# should not be imported by other module
if __name__ == '__main__':
      file = parseArgs()
      main(file)
      #updateModificationTime()
      #post_phase("2017-12")
      #new = URLPath.objects.get(slug='new')
      #post_phase_delete_url(new)
      # print(post_phase_delete_url(new))
      # components = URLPath.objects.get(slug='threats', parent=new)
      # print(components.path)
      # # print(components)
      print("finished!")
