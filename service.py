# -*- coding: utf-8 -*-

import os
import sys
import xbmc
import urllib
import xbmcvfs
import xbmcaddon
import xbmcgui
import xbmcplugin
import shutil
import unicodedata
import re
import string
import difflib
import HTMLParser
import time
import datetime
import urllib2
import gzip
import zlib
import StringIO
import zipfile

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString

__cwd__ = unicode(xbmc.translatePath(__addon__.getAddonInfo('path')), 'utf-8')
__profile__ = unicode(xbmc.translatePath(__addon__.getAddonInfo('profile')), 'utf-8')
__resource__ = unicode(xbmc.translatePath(os.path.join(__cwd__, 'resources', 'lib')), 'utf-8')
__temp__ = unicode(xbmc.translatePath(os.path.join(__profile__, 'temp')), 'utf-8')


def log(module, msg):
    xbmc.log((u"### [%s] - %s" % (module, msg,)).encode('utf-8'))

# remove file and dir with 30 days before / now after time
def clear_tempdir(strpath):
    if xbmcvfs.exists(strpath):
        try:
            low_time = time.mktime((datetime.date.today() - datetime.timedelta(days=15)).timetuple())
            now_time = time.time()
            for file_name in xbmcvfs.listdir(strpath)[1]:
                if sys.platform.startswith('win'):
                    full_path = os.path.join(strpath, file_name)
                else:
                    full_path = os.path.join(strpath.encode('utf-8'), file_name)
                cfile_time = os.stat(full_path).st_mtime
                if low_time >= cfile_time or now_time <= cfile_time:
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path)
                    else:
                        os.remove(full_path)
        except:
            log(__scriptname__,"error on cleaning temp dir")

clear_tempdir(__temp__)

xbmcvfs.mkdirs(__temp__)

sys.path.append(__resource__)

from engchartohan import engtypetokor

load_page_enum = [1,2,3,4,5,6,7,8,9,10]
load_file_enum = [10,15,20,25,30,35,40,45,50,55,60,65,70,75,80]

max_pages = load_page_enum[int(__addon__.getSetting("max_load_page"))]
max_file_count = load_file_enum[int(__addon__.getSetting("max_load_files"))]
use_titlename = __addon__.getSetting("use_titlename")
user_agent = __addon__.getSetting("user_agent")
use_engkeyhan = __addon__.getSetting("use_engkeyhan")
use_se_ep_check = __addon__.getSetting("use_se_ep_check")

nscreen_base = "http://nscreen.info"
nscreen_query = "/subtitle/default.aspx?keyword=%s&f=%s&page=%d"

pattern_file = "<div id=\"subt\" class=\"sub_downsmall\">\s+?<a href=\"([^\"]+)\"[^>]+>\s+?<b>([^<]+|)<"
pattern_rate = "<span id=\"ctl00_MainContent_lblRating\"><div class='basic'[^>]+></div><div [^>]+>([^\(']+)\("
expr_file = re.compile(pattern_file, re.IGNORECASE)
expr_rate = re.compile(pattern_rate, re.IGNORECASE)
pattern_query = "<div id=\"subt\" class=\"sub_search_subsearch\">\s+?<span [^>]+>([^<]+)</span>\s+?<span [^>]+><a href='([^']+)'[^>]+>([^<]+)</a></span>"
expr_query = re.compile(pattern_query, re.IGNORECASE)
ep_expr = re.compile("\d{1,2}[^\d\s]\d{1,3}")

def prepare_search_string(s):
    s = string.strip(s)
    s = re.sub(r'\(\d\d\d\d\)$', '', s)  # remove year from title
    return s
    
def log(module, msg):
    xbmc.log((u"### [%s] - %s" % (module, msg,)).encode('utf-8'))    

# get subtitle pages
def get_subpages(query,list_mode=0):
    file_count = 0
    total_page = 0
    newquery = urllib2.quote(prepare_search_string(query))
    for lang in item['sub_lang']:
        page_count=1
        if lang=="":
            lang = "en"
        while total_page<max_pages and file_count<max_file_count:
            ## log(__scriptname__,"%d - %d" %(max_file_count, file_count))
            result_count = nscreen_list(newquery,lang,page_count,max_file_count-file_count,list_mode)
            if result_count == 0:
                break
            file_count += result_count
            # next page
            page_count+=1
            total_page+=1
    return file_count

def check_ext(str):
        ext_str = [".smi",".srt",".sub",".ssa",".ass",".txt"]
        retval = -1
        if os.path.splitext(str)[1] in ext_str:
            retval = 1
        return retval

# support compressed content
def decode_content (page):
    encoding = page.info().get("Content-Encoding")    
    if encoding in ('gzip', 'x-gzip', 'deflate'):
        content = page.read()
        if encoding == 'deflate':
            data = StringIO.StringIO(zlib.decompress(content))
        else:
            data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(content))
        page = data.read()
    else:
        page = page.read()
    return page

def read_url(url):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-Agent',user_agent), ('Referer',url), ('Accept-Encoding','gzip,deflate')]
    rep = opener.open(url)
    res = decode_content(rep)
    rep.close()
    return res

# file link, filename, file rating
def nscreen_file(link):
    item_file = []
    url_file = nscreen_base+link.replace(" ","%20")
    content_file = read_url(url_file)
    file_rate = expr_rate.search(content_file)
    try:
        if file_rate:
            file_rating="%d" % (int(float(file_rate.group(1))/10*5+0.5))
        else:
            file_rating="0"
    except:
        file_rating="0"
    file_info = expr_file.findall(content_file)
    if file_info:
        for flink, fname in file_info:
            item_file.append([flink.replace(" ","%20"),fname,file_rating])
    return item_file

def check_season_episode(str_title, se, ep):
    result = 0
    re_str = ep_expr.search(str_title)
    new_season = ""
    new_episode = ""    
    if re_str:
        str_temp = re_str.group(0)
        for i in range(0, len(str_temp)):
            c = str_temp[i]
            if c.isdigit():
                       new_season += c
            else:
                break
        for i in range(len(str_temp)-1, -1, -1):
            c = str_temp[i]
            if c.isdigit():
                       new_episode = c + new_episode
            else:
                break
    if new_season=="":
        new_season="0"            
    if new_episode=="":
        new_episode="0"
    if se=="":
        se="0"
    if ep=="":
        ep="0"
    if int(new_season)==int(se):
        result = 1
        if int(new_episode)==int(ep):
            result = 2
    return result    
    
def parse_itemlist(item_list,lang,file_limit,list_mode):
    result=0
    for lang, link, titlename in item_list:
        if use_se_ep_check=="true":
            if list_mode==1 and 2!=check_season_episode(titlename,item['season'],item['episode']):
                continue
        if result<file_limit:
            ## log(__scriptname__,"%d-%d %s" % (result,file_limit,link))
            file_info = nscreen_file(link)
            file_len = len(file_info)
            if file_len:
                result+=file_len
                link = nscreen_base+link.replace(" ","%20")
                file_no = 1
                for file_link, file_name, file_rating in file_info:
                    if file_name=="":
                        file_name = titlename+"_%d.xxx" %(file_no)
                    file_link = nscreen_base+file_link.replace(" ","%20")
                    listitem = xbmcgui.ListItem(label          = lang[lang.find('[')+1:lang.find(']')] ,
                                                label2         = file_name if use_titlename == "false" else titlename,
                                                iconImage      = file_rating,
                                                thumbnailImage = ""
                                                )
                    listitem.setProperty( "sync", "false" )
                    listitem.setProperty( "hearing_imp", "false" )
                    listurl = "plugin://%s/?action=download&url=%s&furl=%s&name=%s" % (__scriptid__,
                                                                                    urllib2.quote(link),
                                                                                    urllib2.quote(file_link),
                                                                                    urllib2.quote(file_name)
                                                                                    )
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=listurl,listitem=listitem,isFolder=False)
                    file_no += 1
    return result
    
# list per pages
def nscreen_list(query, lang, pageno, file_limit, list_mode):
    url_list = nscreen_base+nscreen_query % (query, lang, pageno)
    content_list = read_url(url_list)
    result = 0
    item_list = expr_query.findall(content_list)
    if item_list:
        result=parse_itemlist(item_list,lang,file_limit,list_mode)
    return result

def zip_filelist(fname):
    files = []
    zfile = zipfile.ZipFile(fname)
    fileid = 1
    name = os.path.splittext(fname)[0]
    for finfo in zfile.infolist():
        if findo.file_size>0:
            if check_ext(findo.filename)==1:
                ext = os.path.splittext(findo.filename)[1]
                oname = "%s%d%s" % (name,fileid,ext)
                ifile=zfile.open(findo)
                try:
                    ofile=open(oname,"wb")
                    ofile.write(ifile.read())
                    ofile.close()
                    files.append(oname)
                except:
                    log(__scriptname__,"File Error (zip)")
                ifile.close()
                fileid += 1
    zfile.close()
    return files

# download file
def nscreen_download(file_link, file_name, link):
    subtitle_list = []
    local_temp_file = os.path.join(__temp__.encode('utf-8'), urllib2.unquote(file_name))
    file_link = urllib2.unquote(file_link).replace(" ","%20")
    link = urllib2.unquote(link).replace(" ","%20")
    req_download = urllib2.Request(file_link, headers={ 'User-Agent' : user_agent, 'Referer': link})
    resp_download = urllib2.urlopen(req_download)
    IsPack = 0
    UseZipList = 0
    # save file
    try:
        file_handle = open(local_temp_file, "wb")
        file_handle.write(resp_download.read())
        file_handle.close()
        # check zip
        if zipfile.is_zipfile(local_temp_file):
            UseZipList = 1
        else:
            # check rar archive type
            file_handle = open(local_temp_file, "rb")
            file_handle.seek(0)
            if file_handle.read(4)=='Rar!':
                IsPack = 1
            file_handle.close()

    except:
        log(__scriptname__,"File Error (Download)")

    if IsPack==1:
        xbmc.sleep(500)
        xbmc.executebuiltin(('XBMC.Extract("%s","%s")' % (local_temp_file, __temp__,)).encode('utf-8'), True)

    packfile_time = os.stat(local_temp_file).st_mtime

    if UseZipList==1:
        flist = zip_filelist(local_temp_file)
        for name in flist:
            subtitle_list.append(name)

    else:
        if IsPack==0:
            subtitle_list.append(local_temp_file)

    if len(subtitle_list)==0 and IsPack==1:
        for file in xbmcvfs.listdir(__temp__)[1]:
            if sys.platform.startswith('win'):
                file = os.path.join(__temp__, file)
            else:
                file = os.path.join(__temp__.encode('utf-8'), file)
            if check_ext(file)!=-1:
                cfile_time = os.stat(file).st_mtime
                if cfile_time >= packfile_time and cfile_time <= time.time():
                    subtitle_list.append(file)
    
    return subtitle_list
 
def search(item):
    filename = os.path.splitext(os.path.basename(item['file_original_path']))[0]
    lastgot = 0
    list_mode = 0
    if item['mansearch']:
        lastgot = get_subpages(item['mansearchstr'])
        if use_engkeyhan == "true":
            lastgot += get_subpages(engtypetokor(item['mansearchstr']))
    elif item['tvshow']:
        list_mode = 1
        lastgot = get_subpages(item['tvshow'],1)
    elif item['title'] and item['year']:
        lastgot = get_subpages(item['title'])
    ##if lastgot == 0 and list_mode != 1:
    ##    if not filename.startswith("video."):
    ##        lastgot = get_subpages(filename)
        
def normalizeString(str):
    return unicodedata.normalize(
        'NFKD', unicode(unicode(str, 'utf-8'))
    ).encode('ascii', 'ignore')

def get_params(string=""):
  param=[]
  if string == "":
    paramstring=sys.argv[2]
  else:
    paramstring=string
  if len(paramstring)>=2:
    params=paramstring
    cleanedparams=params.replace('?','')
    if (params[len(params)-1]=='/'):
      params=params[0:len(params)-2]
    pairsofparams=cleanedparams.split('&')
    param={}
    for i in range(len(pairsofparams)):
      splitparams={}
      splitparams=pairsofparams[i].split('=')
      if (len(splitparams))==2:
        param[splitparams[0]]=splitparams[1]

  return param

params = get_params()

if params['action'] == 'search' or params['action'] == 'manualsearch':
  item = {}
  item['temp']               = False
  item['rar']                = False
  item['mansearch']          = False
  item['year']               = xbmc.getInfoLabel("VideoPlayer.Year")                         # Year
  item['season']             = str(xbmc.getInfoLabel("VideoPlayer.Season"))                  # Season
  item['episode']            = str(xbmc.getInfoLabel("VideoPlayer.Episode"))                 # Episode
  item['tvshow']             = normalizeString(xbmc.getInfoLabel("VideoPlayer.TVshowtitle"))  # Show
  item['title']              = normalizeString(xbmc.getInfoLabel("VideoPlayer.OriginalTitle"))# try to get original title
  item['file_original_path'] = xbmc.Player().getPlayingFile().decode('utf-8')                 # Full path of a playing file
  item['3let_language']      = [] #['scc','eng']
  item['sub_lang']               = []
  PreferredSub		      = params.get('preferredlanguage')

  if 'searchstring' in params:
    item['mansearch'] = True
    item['mansearchstr'] = params['searchstring']

  for lang in urllib.unquote(params['languages']).decode('utf-8').split(","):
    if lang == "Portuguese (Brazil)":
      lan = "pob"
    else:
      lan = xbmc.convertLanguage(lang,xbmc.ISO_639_2)
      if lan == "gre":
        lan = "ell"

    item['3let_language'].append(lan)
    lang_short = xbmc.convertLanguage(lang,xbmc.ISO_639_1)
    if lang_short!="en":
        item['sub_lang'].append(lang_short)

  item['sub_lang'].append("en")

  if item['title'] == "":
    item['title']  = normalizeString(xbmc.getInfoLabel("VideoPlayer.Title"))      # no original title, get just Title

  if item['episode'].lower().find("s") > -1:                                      # Check if season is "Special"
    item['season'] = "0"                                                          #
    item['episode'] = item['episode'][-1:]

  if ( item['file_original_path'].find("http") > -1 ):
    item['temp'] = True

  elif ( item['file_original_path'].find("rar://") > -1 ):
    item['rar']  = True
    item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

  elif ( item['file_original_path'].find("stack://") > -1 ):
    stackPath = item['file_original_path'].split(" , ")
    item['file_original_path'] = stackPath[0][8:]

  search(item)

elif params['action'] == 'download':
  subs = nscreen_download(urllib2.unquote(params['furl']),urllib2.unquote(params['name']),urllib2.unquote(params['url']))
  for sub in subs:
    listitem = xbmcgui.ListItem(label=sub)
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=sub,listitem=listitem,isFolder=False)


xbmcplugin.endOfDirectory(int(sys.argv[1]))
