#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# LICENSE:  see LICENSE file
#
# bbs mode:
# You must rewrite Download,GetCurrentDir,CheckThreadsValid,
# GetThreadUrl and GetTitle function.
# single-page mode:
# You must rewrite Download function.

import sys
import logging
import os
import os.path
import requests
import requesocks
import re
import ConfigParser
import argparse
import imghdr
from HTMLParser import HTMLParser

def success(val): return val,None
def error(why): return None,why
def get_val(m_val): return m_val[0]
def get_error(m_val): return m_val[1]

#global variables
init_with_config_file = True
has_log_file = True

if os.name != 'nt':
    WindowsError = OSError

class Downloader(object):
    """docstring for ClassName"""
    def __init__(self):
        super(Downloader, self).__init__()

        self.type = 'none'
        self._isUrlFormat = re.compile(r'https?://([\w-]+\.)+[\w-]+(/[\w\- ./?%&=]*)?');
        self._path = get_val(self.DealDir("Images"))
        self.currentDir = ""
        self.cf = ConfigParser.ConfigParser()
        self.pageNum = 1
        self.pageTo = 1
        self.isMono = False
        self.keepOriginTitle = True
        self.numToDownload = -1
        self.loggingFile = 'log.txt'
        self.retryTimes = 5
        self.encode = None
        self.useProxy = False
        self.httpProxy = '127.0.0.1:1080'
        self.httpsProxy = '127.0.0.1:1080'
        self.imageCount = 0
        self.verbose = False
        self.silent = False
        self.targetThread = "" # single thread
        self.targetThreadRegex = ""

        #moeimg specific
        self.moeimgdomain = 'moeimg.net'
        self.moeimgTags = False
        self.moeimgSortWithTags = False
        self.currentTag = 'default'

        #caoliu specific
        self.caoliudomain = 't66y.com'

        #jandan specific
        self.jandandomain = 'jandan.net'
        self.jandanPageToDownload = 1

        global init_with_config_file
        global has_log_file
        if init_with_config_file:
            if not os.path.exists('config'):
                self.InternalPrint('No config file. Creating a default one.', False)
                self.SetDefaultConfig();
            self.LoadConfig()
        #init logging file
        if has_log_file:
            logging.basicConfig(filename = os.path.join(os.getcwd(), self.loggingFile), level = logging.WARN, filemode = 'a+', format = '%(asctime)s - %(levelname)s: %(message)s')

    def InternalPrint(self, msg, is_verbose):
        if not self.silent:
            if is_verbose:
                if(self.verbose):
                    print(msg)
            else:
                print(msg)

    def LoadConfig(self):
        self.cf.read("config")
        self.pageNum = self.cf.getint('web','page_from')
        self.pageTo = self.cf.getint('web','page_to')
        self.isMono = self.cf.getboolean('file','mono')
        self.numToDownload = self.cf.getint('web','num_to_download')
        self.loggingFile = self.cf.get('basic','log_file')
        self.retryTimes = self.cf.getint('web','retry_times')
        self.caoliudomain = self.cf.get('caoliu','domain')
        self.moeimgdomain = self.cf.get('moeimg','domain')
        self.keepOriginTitle = self.cf.getboolean('file','keep_origin_title')
        self.jandandomain = self.cf.get('jandan','domain')
        self.jandanPageToDownload = self.cf.getint('jandan','pages_to_download')
        self.moeimgTags = self.cf.getboolean('moeimg','tags')
        self.moeimgSortWithTags = self.cf.getboolean('moeimg','sort_with_tags')
        self.useProxy = self.cf.getboolean('basic','use_proxy')
        self.httpProxy = self.cf.get('basic','http_proxy')
        self.httpsProxy = self.cf.get('basic','https_proxy')


    def SetDefaultConfig(self):
        self.cf.add_section('basic')
        self.cf.set('basic','log_file','log.txt')
        self.cf.set('basic','use_proxy','false')
        self.cf.set('basic','http_proxy','127.0.0.1:1080')
        self.cf.set('basic','https_proxy','127.0.0.1:1080')
        self.cf.add_section('web')
        self.cf.set('web','page_from','1')
        self.cf.set('web','page_to','1')
        self.cf.set('web','num_to_download','-1')
        self.cf.set('web','retry_times','5')
        self.cf.add_section('caoliu')
        self.cf.set('caoliu','domain','t66y.com')
        self.cf.add_section('moeimg')
        self.cf.set('moeimg','domain','moeimg.net')
        self.cf.set('moeimg','tags','false')
        self.cf.set('moeimg','sort_with_tags','false')
        self.cf.add_section('jandan')
        self.cf.set('jandan','domain','jandan.net')
        self.cf.set('jandan','pages_to_download','1')
        self.cf.add_section('file')
        self.cf.set('file','mono','false')
        self.cf.set('file','keep_origin_title','true')
        with open('config', 'wb') as configfile:
            self.cf.write(configfile)

    def StripIllegalChar(self, path):
        return path.strip('>').strip('<').strip('*').strip('|').strip('?').strip(':').strip('"').strip('/')

    def DealDir(self, path):
        solved = False
        while True:
            try:
                if not os.path.exists(path):
                    os.mkdir(path)
                return success(path)
            except WindowsError:
                #windows specific
                global has_log_file
                if has_log_file:
                    logging.error('Windows error with path %s' % path)
                if not solved:
                    path = self.StripIllegalChar(path)
                    solved = True
                else:
                    return error('Invalid path name %s' % path)

    def FetchHtml(self, url):
        retry = 0
        proxies = {
            'http':self.httpProxy,
            'https':self.httpsProxy,
        }
        headers = {
            'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/601.3.9 (KHTML, like Gecko) Version/9.0.2 Safari/601.3.9',
        }
        while True:
            try:
                self.InternalPrint("Fetching HTML: %s" % url, True)
                session = requesocks.session()
                session.headers = headers;
                if self.useProxy:
                    self.InternalPrint("Using proxy: http %s, https %s" % (self.httpProxy, self.httpsProxy), True)
                    session.proxies = proxies
                else:
                    self.InternalPrint("No proxy.", True)
                response = session.get(url)
                if response.status_code != 200:
                    self.InternalPrint(response.text, True)
                    return error("Failed to fetch html. CODE:%i" % response.status_code)
                elif (response.text) == 0:
                    return error("Empty html.")
                else:
                    if self.encode != None:
                        response.encoding = self.encode
                    return success(response.text)
            #except requests.ConnectionError:
            except requesocks.exceptions.ConnectionError:
                if retry<self.retryTimes:
                    retry+=1
                    self.InternalPrint('Can\'t retrive html. retry %i' % retry, False)
                    continue
                global has_log_file
                if has_log_file:
                    logging.error('Can not connect to %s' % url)
                return error("The server is not responding.")

    def DoFetch(self, domain):
        self.InternalPrint("Fetching main html...", True)
        res = self.FetchHtml(domain)
        self.InternalPrint("Main html fetched.", True)
        if get_error(res):
            return res
        html = get_val(res)
        self.FetchPageHtml(html);
        return success(0)

    def FetchPageHtml(self, htmlSource):
        prog = re.compile(self.ThreadsRegex, re.IGNORECASE)
        matchesThreads = prog.findall(htmlSource)
        num = 0
        for href in matchesThreads:
            if self.CheckThreadsValid(href) is True:
                #print href
                threadurl = self.GetThreadUrl(href)
                self.InternalPrint('Thread '+str(num + 1)+':'+threadurl, False)
                if self.keepOriginTitle:
                    self.currentDir = self.GetTitle(href)
                else:
                    self.currentDir = self.GetCurrentDir(href)

                #TODO: gb2312 bug
                try:
                    self.InternalPrint(self.currentDir.encode(sys.getfilesystemencoding())+'/', False)
                except UnicodeEncodeError:
                    global has_log_file
                    if has_log_file:
                        logging.warning('Unicode encode error at %s' % threadurl)
                    self.currentDir = self.GetCurrentDir(href)
                    self.InternalPrint(self.currentDir+'/', False)

                res = self.FetchThreadHtml(threadurl)
                if(get_error(res)):
                    self.InternalPrint(get_error(res), False)
                num+=1
                if self.numToDownload>0 and num>=self.numToDownload:
                    break

    def DoFetchSingleThread(self, url):
        self.InternalPrint('Thread:'+url, False)

        self.InternalPrint("Fetching thread html...", True)
        res = self.FetchHtml(url)
        if get_error(res):
            return res
        self.InternalPrint("Thread html fetched.", True)

        html = get_val(res)
        #get current directory
        if self.keepOriginTitle:
            # get thread title
            #self.currentDir = self.GetTitle(href)
            prog = re.compile(self.targetThreadRegex, re.IGNORECASE)
            matches = prog.findall(html)
            self.currentDir = matches[0]
        else:
            self.currentDir = url.split('/')[-1].split('.')[-2]
        #TODO: gb2312 bug
        try:
            self.InternalPrint(self.currentDir.encode(sys.getfilesystemencoding())+'/', False)
        except UnicodeEncodeError:
            global has_log_file
            if has_log_file:
                logging.warning('Unicode encode error at %s' % url)
            self.currentDir = 'tmp'
            self.InternalPrint(self.currentDir+'/', False)

        html = get_val(res)
        self.currentTag = self.GetThreadTagName(html)
        self.FetchImgLinksFromThread(html);
        return success(0)

    # need to rewrite
    def GetThreadUrl(self, href):pass
    def GetTitle(self, href):pass
    def CheckThreadsValid(self, href):pass
    def GetCurrentDir(self, href):pass
    def GetThreadTagName(self, html):return 'default'
    def Download(self):
        self.init()

    def PreHandleImgLink(self, href):
        return href

    def PreHandleTagName(self, local_file):
        return local_file

    def FetchThreadHtml(self, threadurl):
        self.InternalPrint("Fetching thread html...", True)
        res = self.FetchHtml(threadurl)
        self.InternalPrint("Thread html fetched.", True)
        if get_error(res):
            return res
        html = get_val(res)
        self.currentTag = self.GetThreadTagName(html)
        self.FetchImgLinksFromThread(html);
        return success(html)

    def FetchImgLinksFromThread(self, htmlSource):
        prog = re.compile(self.ImgRegex, re.IGNORECASE)
        matchesImgSrc = prog.findall(htmlSource)
        global has_log_file
        if not self.isMono:
            self.imageCount = 0
        for href in matchesImgSrc:
            self.InternalPrint(href, True)
            href = self.PreHandleImgLink(href)
            if not self.CheckIsUrlFormat(href):
            #warning: requests library does not support non-http(s) url
                self.InternalPrint('Invalid url format %s' % href, False)
                if has_log_file:
                    logging.error('Invalid url format %s' % href)
                continue;
            res = self.download_file(href)
            if get_error(res):
                self.InternalPrint(get_error(res).encode(sys.getfilesystemencoding()), False)
            self.imageCount += 1

    def CheckIsUrlFormat(self, value):
        return self._isUrlFormat.match(value) is not None

    def GetImageType(self, img_path):
        type = imghdr.what(img_path)
        if type != None:
            return type
        else:
            return "jpg"

    def ImageExists(self, path, img_name):
        files = os.listdir(path)
        for f in files:
            if img_name == os.path.splitext(f)[0]:
                return True
        return False

    def download_file(self, url):
        dir = self.type
        local_directory = ""
        if self.isMono:
            local_directory = "Images/"+ dir + '/'
            self.DealDir(local_directory)
            local_directory = self.PreHandleTagName(local_directory)
        else:
            local_directory = "Images/" + dir + '/'
            self.DealDir(local_directory)
            local_directory = self.PreHandleTagName(local_directory)
            # deal windows directory error
            res = self.DealDir(local_directory + self.currentDir + '/')
            if get_error(res):
                #self.InternalPrint(get_error(res), False)
                self.DealDir(local_directory + 'tmp/')
                local_directory += 'tmp/'
            else:
                local_directory += self.currentDir + '/'

        #local_filename = local_filename + self.StripIllegalChar(url.split('/')[-1])#has bug in windows
        image_path = local_directory + str(self.imageCount)# so use image count instead
        if self.ImageExists(local_directory, str(self.imageCount)):
            if not self.isMono:
                return error('\t skip '+image_path)
            else:
                while(self.ImageExists(local_directory, str(self.imageCount))):
                    self.imageCount+=1
                image_path = local_directory + str(self.imageCount)

        self.InternalPrint('\t=>'+image_path.encode(sys.getfilesystemencoding()), False)
        # NOTE the stream=True parameter
        retry = 0
        proxies = {
            'http':self.httpProxy,
            'https':self.httpsProxy,
        }
        global has_log_file
        while True:
            try:
                session = requesocks.session()
                if self.useProxy:
                    self.InternalPrint("Using proxy: http %s, https %s" % (self.httpProxy, self.httpsProxy), True)
                    session.proxies = proxies
                    #r = requests.get(url, stream=True, proxies=proxies)
                #else:
                    #r = requests.get(url, stream=True)
                r = session.get(url)
                break
            #except requests.ConnectionError:
            except requesocks.exceptions.ConnectionError:
                if retry<self.retryTimes:
                    retry+=1
                    self.InternalPrint('\tCan\'t retrive image. retry %i' % retry, False)
                    continue
                if has_log_file:
                    logging.error('Can not connect to %s' % url)
                return error('The server is not responding.')
        try:
            with open(image_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
            #rename image file by its type
            os.rename(image_path, local_directory+str(self.imageCount)+"."+self.GetImageType(image_path))
        except IOError:
            if has_log_file:
                logging.error('Can not save file %s' % url)
            self.InternalPrint('Can\'t save image %s' % url, False)

        return success(image_path)

class MoeimgDownloader(Downloader):
    def __init__(self):
        super(MoeimgDownloader, self).__init__()

        self.type = 'moeimg'
        self.encode = 'utf-8'
        self.tag_file = 'tags'
        self.ImgRegex = r'<img\s*src=["\']?([^\'" >]+?)[ \'"]\s*(?:alt="\d*")?\s*class="thumbnail_image"'
        #self.ThreadsRegex = r'<h[23]\s*class="entry-header"\s*>\s*<a\s*href=["\']?([^\'">]+?)[\'"]\s*title=["\']?([^\'"]+?)[\'"]'
        self.ThreadsRegex = r'<h2 class="title">\s*<a href="(http://moeimg.net/\d*.html)"\s*title="[^"]+?">\s*([^<]+?)\s*</a>\s*</h2>'
        self.targetThreadRegex = r'<div\s*class="post">\s*<h1\s*class="title">\s*([^<]+?)\s*</h1>'

    def Download(self):
        if self.moeimgTags:
            res = self.LoadTags()
            if get_error(res):
                self.InternalPrint(get_error(res), False)
                return
            tags = get_val(res)
        else:
            tags = ['default']
        self.InternalPrint("===============   start   ===============", False)
        i = self.pageNum
        domain = ''
        for tag in tags:
            self.currentTag = tag
            if self.targetThread == "":
                for i in range(self.pageNum, self.pageTo+1):
                    if not self.moeimgTags:
                        self.InternalPrint("===============   loading page {0}   ===============".format(i), False)
                        if i == 1:
                            domain = "http://"+self.moeimgdomain
                        else:
                            domain = "http://"+self.moeimgdomain+"/page/{0}".format(i)
                    else:
                        self.InternalPrint("===============   loading tag: %s page %i  ===============" % (tag.decode('utf-8').encode(sys.getfilesystemencoding()),i), False)
                        if i == 1:
                            domain = "http://"+self.moeimgdomain+"/tag/%s" % (tag)
                        else:
                            domain = "http://"+self.moeimgdomain+"/tag/%s/page/%i" % (tag,i)
                    res = self.DoFetch(domain)
                    if get_error(res):
                        self.InternalPrint(get_error(res), False)
            else:
                self.InternalPrint("===============   loading target thread {0}   ===============".format(self.targetThread), False)
                res = self.DoFetchSingleThread(self.targetThread)
                if get_error(res):
                    self.InternalPrint(get_error(res), False)
        self.InternalPrint("===============   end   ===============", False)

    def FetchAllTags(self):
        res = self.FetchHtml('http://'+self.moeimgdomain+'/taglist')
        if get_error(res):
            return res
        html = get_val(res)
        tagRegex = r'<a\s*href=[\'"]([^\'"]+?)[\'"]\s*class=[\'"][^\'"]*[\'"]\s*title=[\'"][^\'"]*[\'"]\s*style=[\'"][^\'"]*[\'"]>([^<]+?)</a>'
        prog = re.compile(tagRegex, re.IGNORECASE)
        matches = prog.findall(html)
        tags = []
        for m in matches:
            if re.search('tag', m[0]):
                if not m[1] in tags:
                    tags.append(m[1])
        self.InternalPrint('Fetched %s tags.' % len(tags), True)
        return success(tags)

    def LoadTags(self):
        if os.path.exists(self.tag_file):
            tagsfile = open(self.tag_file, 'r')
        else:
            return error('No tags file.')

        tags = []
        for tag in tagsfile:
            tags.append(tag.strip('\n').strip(';').decode('utf-8').replace(' ', '-').lower())
        self.InternalPrint('Loaded %s tags.' % len(tags), True)
        return success(tags)

    def GetCurrentDir(self, href):
        dir = href[0].split('/')[-1]
        dir = dir.split('.')[-2]
        return dir

    def GetThreadTagName(self, html):
        #tagRegex = r'<li\s*class="path">\s*<a\s*href=["\']?([^\'" >]+?)[ \'"]\s*>([^<]*)</a></li>'
        tagRegex = r'<li\s*class="tag"><i\s*class="fa fa-tags"></i><a\s*href=["\']?([^\'" >]+?)[ \'"]\s*rel="tag">([^<]*)</a>'
        prog = re.compile(tagRegex, re.IGNORECASE)
        matches = prog.findall(html)
        for m in matches:
            if re.search('http://moeimg.net/tag/',m[0]):
                return m[1]
        return 'default'

    def PreHandleTagName(self, local_file):
        if self.moeimgSortWithTags:
            if self.moeimgTags:
                local_file += self.currentTag.encode(sys.getfilesystemencoding()) + '/'
            else:
                local_file += self.currentTag + '/'
            self.DealDir(local_file)
        return local_file

    def CheckThreadsValid(self, href):
        return True

    def GetThreadUrl(self, href):
        return href[0]

    def GetTitle(self, href):
        return href[1]

class CaoliuDownloader(Downloader):
    def __init__(self):
        super(CaoliuDownloader, self).__init__()

        self.type = 'caoliu'
        self.encode = 'gbk'
        self.ImgRegex = r'<input\s*src\s*=\s*["\']?([^\'" >]+?)[ \'"]\s*type=\'image\''
        self.ThreadsRegex = r'<h3><a\s*href\s*=\s*["\']?([^\'">]+?)[ \'"][^>]*?>(?:<font color=green>)?([^<]*)(?:</font>)?</a></h3>'
        self.targetThreadRegex = r'<tr><td\s*class="h"> --> <b>[^<]+?</b>\s*([^<]+?)\s*</td>'

    def Download(self):
        self.InternalPrint("===============   start   ===============", False)
        if self.targetThread == "":
            for i in range(self.pageNum, self.pageTo+1):
                self.InternalPrint("===============   loading page {0}   ===============".format(i), False)
                domain = "http://"+self.caoliudomain+"/thread0806.php?fid=16&search=&page={0}".format(i)
                res = self.DoFetch(domain)
                if get_error(res):
                    self.InternalPrint(get_error(res), False)
        else:
            self.InternalPrint("===============   loading target thread {0}   ===============".format(self.targetThread), False)
            res = self.DoFetchSingleThread(self.targetThread)
            if get_error(res):
                self.InternalPrint(get_error(res), False)
        self.InternalPrint("===============   end   ===============", False)

    def GetCurrentDir(self, href):
        dir = href[0].split('/')[-3] + href[0].split('/')[-2] + href[0].split('/')[-1]
        dir = dir.split('.')[-2]
        return dir

    def CheckThreadsValid(self, href):
        return href[0][0:8] == "htm_data"

    def GetThreadUrl(self, href):
        return 'http://'+self.caoliudomain+'/' + href[0]

    def GetTitle(self, href):
        return href[1]

class MLStripper(HTMLParser):
    def __init__(self):
        self.reset()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

class JanDanDownloader(Downloader):
    def __init__(self):
        super(JanDanDownloader, self).__init__()

        self.isMono = True

        self.type = 'jandan'
        self.encode = 'utf-8'
        self.ImgRegex = r'<p>\s*<a\s*href=["\']?([^\'" >]+?)[ \'"]\s*target="_blank"\s*class="view_img_link"\s*>'

    def Download(self):
        #get max
        res = self.FetchHtml("http://"+self.jandandomain+"/ooxx")
        if get_error(res):
            self.InternalPrint(get_error(res), False)
            return res
        html = get_val(res)
        newest = self.get_max(html)

        self.InternalPrint("===============   start   ===============", False)
        for i in range(newest-self.jandanPageToDownload+1, newest+1):
            self.InternalPrint("===============   loading page {0}   ===============".format(i), False)
            domain = "http://"+self.jandandomain+"/ooxx/page-{0}#comments".format(i)
            res = self.FetchThreadHtml(domain)
            if get_error(res):
                self.InternalPrint(get_error(res), False)
        self.InternalPrint("===============   end   ===============", False)

    def strip_tags(self, html):
        s = MLStripper()
        s.feed(html)
        return s.get_data()

    def get_max(self, html_code):
        m = re.search('.+cp-pagenavi.+', html_code)
        m = re.search('\d+', self.strip_tags(m.group(0)).strip())
        return int(m.group(0))

    def download_file(self, url):
        dir = self.type
        local_directory = "Images/"+ dir + '/'
        self.DealDir(local_directory)
        image_path = local_directory + url.split('/')[-1]
        if os.path.exists(image_path):
            return error('\t skip '+image_path)
        self.InternalPrint('\t=>'+image_path.encode(sys.getfilesystemencoding()), False)
        # NOTE the stream=True parameter
        retry = 0
        proxies = {
            'http':self.httpProxy,
            'https':self.httpsProxy,
        }
        global has_log_file
        while True:
            try:
                if self.useProxy:
                    r = requests.get(url, stream=True, proxies=proxies)
                else:
                    r = requests.get(url, stream=True)
                break
            except requests.ConnectionError:
                if retry<self.retryTimes:
                    retry+=1
                    self.InternalPrint('\tCan\'t retrive image. retry %i' % retry, False)
                    continue
                if has_log_file:
                    logging.error('Can not connect to %s' % url)
                return error('The server is not responding.')
        try:
            with open(image_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
        except IOError:
            if has_log_file:
                logging.error('Can not save file %s' % url)
            self.InternalPrint('Can\'t save image %s' % url, False)
        return success(image_path)

def process_pages(d, num):
    if num > 0:
        d.pageTo = d.pageNum + num - 1

def parse_general_args(obj, args):
    if args.no_log:
        obj.hasLog = False
    if args.threads:
        obj.numToDownload = args.threads
    if args.single:
        obj.targetThread = args.single[0]
    if args.proxy:
        obj.useProxy = True
        obj.httpProxy = args.proxy[0]
        obj.httpsProxy = args.proxy[0]
    if args.direct:
        obj.useProxy = False
    if args.retry:
        obj.retryTimes = args.retry
    if args.mono:
        obj.isMono = True
    if args.verbose:
        obj.verbose = True
    if args.quiet:
        obj.silent = True

def caoliu(args):
    cl = CaoliuDownloader()
    if args.pages:
        process_pages(cl, args.pages)
    if args.domain:
        cl.caoliudomain = args.domain
    parse_general_args(cl, args)
    cl.InternalPrint("Processing caoliu...", False)
    cl.Download()

def moeimg(args):
    moe = MoeimgDownloader()
    if args.pages:
        process_pages(moe, args.pages)
    if args.domain:
        moe.moeimgdomain = args.domain
    if args.sort_with_tags:
        moe.moeimgSortWithTags = True
    parse_general_args(moe, args)
    moe.InternalPrint("Processing moeimg...", False)
    if args.fetch_all_tags:
        res = moe.FetchAllTags()
        if get_error(res):
            print(get_error(res))
            return
        tags = get_val(res)
        with open('all_tags.txt', 'w') as all_tags_file:
            for t in tags:
                all_tags_file.write(t + '\n')
            print('Fetched all tags.')
    elif args.with_tags:
        if args.tag_file:
            moe.tag_file = args.tag_file
        moe.moeimgTags = True
        moe.Download()
    else:
        moe.Download()

def jandan(args):
    j = JanDanDownloader()
    if args.pages:
        j.jandanPageToDownload = args.pages
    if args.domain:
        j.jandandomain = args.domain
    parse_general_args(j, args)
    j.InternalPrint("Processing jandan...", False)
    j.Download()

#def all():pass

def main():
    global init_with_config_file
    global has_log_file
    ap = argparse.ArgumentParser(description='This tool can download ooxx image from some websites. :P',
                                 epilog=" Please report bugs to https://github.com/KanagiMiss/MoeDownloader/issues")
    sp = ap.add_subparsers(title='subcommands',
                           description='available subcommands',
                           help='')

    p_caoliu = sp.add_parser("caoliu", help="download caoliu images")
    p_caoliu.set_defaults(func=caoliu)
    p_moeimg = sp.add_parser("moeimg", help="download moeimg images")
    p_moeimg.set_defaults(func=moeimg)
    p_jandan = sp.add_parser("jandan", help="download jandan images")
    p_jandan.set_defaults(func=jandan)
#   p_all = sp.add_parser("all", help="download all images")

    g1 = ap.add_mutually_exclusive_group()
    g2 = ap.add_mutually_exclusive_group()
    ap.add_argument("-p", "--pages", type=int,
                    help="number of pages to download")

    #general options
    ap.add_argument("-i", "--ignore_config", action="store_true", help="ignore config file and load with default options")
    ap.add_argument("-n", "--no_log", action="store_true", help="run without log")
    ap.add_argument("-r", "--retry", type=int, help="retry times if failed")
    ap.add_argument("-m", "--mono", action="store_true", help="set if mono file")
    ap.add_argument("-t", "--threads", type=int, help="number of threads to download")
    ap.add_argument("-S", "--single", nargs=1, help="download single thread")
    g1.add_argument("-q", "--quiet", action="store_true", help="run quietly and briefly")
    g1.add_argument("-v", "--verbose", action="store_true", help="run verbosely")
    g2.add_argument("-d", "--direct", action="store_true", help="connect directly(without proxy)")
    g2.add_argument("--proxy", nargs=1, help='set http and https proxy')
    ap.add_argument('--version', action='version', version='%(prog)s 1.0')

    #moeimg options
    p_moeimg.add_argument("-T", "--fetch_all_tags", action="store_true", help="fetch all tags from site")
    p_moeimg.add_argument("-t", "--with_tags", action="store_true", help="download with tags")
    p_moeimg.add_argument("-s", "--sort_with_tags", action="store_true", help="sort files with tags")
    p_moeimg.add_argument("--domain", nargs=1, help="set domain")
    p_moeimg.add_argument("-f", "--tag_file", type=argparse.FileType('r'), help="set specific tag file")

    #caoliu options
    p_caoliu.add_argument("--domain", nargs=1, help="set domain")

    #jandan options
    p_jandan.add_argument("--domain", nargs=1, help="set domain")

    args = ap.parse_args()

    # run with default config (ignore config file)
    if args.ignore_config:
        init_with_config_file = False

    # run without log file
    if args.no_log:
        has_log_file = False

    args.func(args)

if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding(sys.getfilesystemencoding())
    main()
