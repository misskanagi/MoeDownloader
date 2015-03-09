import sys
import logging
import os
import os.path
import requests
import re
import ConfigParser
from HTMLParser import HTMLParser

def success(val): return val,None
def error(why): return None,why
def get_val(m_val): return m_val[0]
def get_error(m_val): return m_val[1]

class Downloader(object):
    """docstring for ClassName"""
    def __init__(self):
        super(Downloader, self).__init__()

        self.type = 'none'
        self._isUrlFormat = re.compile(r'https?://([\w-]+\.)+[\w-]+(/[\w\- ./?%&=]*)?');
        self._path = self.DealDir("Images")
        self.currentDir = ""
        self.cf = ConfigParser.ConfigParser()
        self.pageNum = 1
        self.pageTo = 1
        self.isMono = True
        self.keepOriginTitle = False
        self.numToDownload = -1
        self.loggingFile = 'log.txt'
        self.retryTimes = 5
        self.encode = None

        #moeimg specific
        self.moeimgdomain = 'example.com'
        self.moeimgTags = False

        #caoliu specific
        self.caoliudomain = 'example.com'

        #jandan specific
        self.jandandomain = 'example.com'
        self.jandanNewest = 1346
        self.jandanPageToDownload = 1


        if not os.path.exists('config'):
            print('No config file. Creating a default one.')
            self.SetDefaultConfig();
        self.LoadConfig()

        #init logging file
        logging.basicConfig(filename = os.path.join(os.getcwd(), self.loggingFile), level = logging.WARN, filemode = 'a+', format = '%(asctime)s - %(levelname)s: %(message)s')

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

    def SetDefaultConfig(self):
        self.cf.add_section('basic')
        self.cf.set('basic','log_file','log.txt')
        self.cf.add_section('web')
        self.cf.set('web','page_from','1')
        self.cf.set('web','page_to','1')
        self.cf.set('web','num_to_download','-1')
        self.cf.set('web','retry_times','5')
        self.cf.add_section('caoliu')
        self.cf.set('caoliu','domain','example.com')
        self.cf.add_section('moeimg')
        self.cf.set('moeimg','domain','example.com')
        self.cf.set('moeimg','tags','false')
        self.cf.add_section('jandan')
        self.cf.set('jandan','domain','jandan.net')
        self.cf.set('jandan','pages_to_download','1')
        self.cf.add_section('file')
        self.cf.set('file','mono','true')
        self.cf.set('file','keep_origin_title','false')
        with open('config', 'wb') as configfile:
            self.cf.write(configfile)

    def DealDir(self, path):
        if not os.path.exists(path):
            os.mkdir(path);
            return path;

    def FetchHtml(self, url):
        retry = 0
        while True:
            try:
                response = requests.get(url)
                if response.status_code != 200:
                    return error("Failed to fetch html. CODE:%i" % response.status_code)
                elif (response.text) == 0:
                    return error("Empty html.")
                else:
                    if self.encode != None:
                        response.encoding = self.encode
                    #print(response.encoding)
                    #print(response.text)
                    return success(response.text)
            except requests.ConnectionError:
                if retry<self.retryTimes:
                    retry+=1
                    print('Can\'t retrive html. retry %i' % retry)
                    continue
                logging.error('Can not connect to %s' % url)
                return error("The server is not responding.")

    def DoFetch(self, domain):
        res = self.FetchHtml(domain)
        if get_error(res):
            return res
        html = get_val(res)
        self.FetchThreadsLinks(html);
        return success(0)

    def FetchThreadsLinks(self, htmlSource):
        prog = re.compile(self.ThreadsRegex, re.IGNORECASE)
        matchesThreads = prog.findall(htmlSource)
        num = 0
        for href in matchesThreads:
            if self.CheckThreadsValid(href) is True:
                #print href
                threadurl = self.GetThreadUrl(href)
                print('Thread '+str(num + 1)+':'+threadurl)
                if self.keepOriginTitle:
                    self.currentDir = self.GetTitle(href)
                else:
                    self.currentDir = self.GetCurrentDir(href)

                #TODO: gb2312 bug
                try:
                    print(self.currentDir+'/')
                except UnicodeEncodeError:
                    logging.warning('Unicode encode error at %s' % threadurl)
                    self.currentDir = self.GetCurrentDir(href)
                    print(self.currentDir+'/')

                res = self.FetchImageLinks(threadurl)
                if(get_error(res)):
                    print(get_error(res))
                num+=1
                if self.numToDownload>0 and num>=self.numToDownload:
                    break

    # need to rewrite
    def GetThreadUrl(self, href):pass
    def GetTitle(self, href):pass
    def CheckThreadsValid(self, href):pass
    def GetCurrentDir(self, href):pass

    def PreHandleImgLink(self, href):
        return href

    def FetchImageLinks(self, threadurl):
        res = self.FetchHtml(threadurl)
        if get_error(res):
            return res
        html = get_val(res)
        self.FetchLinksFromSource(html);
        return success(html)

    def FetchLinksFromSource(self, htmlSource):
        prog = re.compile(self.ImgRegex, re.IGNORECASE)
        matchesImgSrc = prog.findall(htmlSource)
        for href in matchesImgSrc:
            href = self.PreHandleImgLink(href)
            if not self.CheckIsUrlFormat(href):
                print('oops')
                continue;
            res = self.download_file(href)
            if get_error(res):
                print(get_error(res))

    def CheckIsUrlFormat(self, value):
        return self._isUrlFormat.match(value) is not None

    def download_file(self, url):
        dir = self.type
        local_filename = ""
        if self.isMono:
            self.DealDir("Images/" + dir + '/')
            local_filename = "Images/"+ dir + '/' + url.split('/')[-1]
        else:
            self.DealDir("Images/" + dir + '/')
            self.DealDir("Images/" + dir + '/' + self.currentDir + '/')
            local_filename = "Images/" + dir + '/' + self.currentDir + '/' + url.split('/')[-1]
        if os.path.exists(local_filename):
            return error('\t skip '+local_filename)
        else:
            print('\t=>'+local_filename)
            # NOTE the stream=True parameter
            retry = 0
            while True:
                try:
                    r = requests.get(url, stream=True)
                    break
                except requests.ConnectionError:
                    if retry<self.retryTimes:
                        retry+=1
                        print('\tCan\'t retrive image. retry %i' % retry)
                        continue
                    logging.error('Can not connect to %s' % url)
                    return error('The server is not responding.')
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
                        f.flush()
            return success(local_filename)

class MoeimgDownloader(Downloader):
    def __init__(self):
        super(MoeimgDownloader, self).__init__()

        self.type = 'moeimg'
        self.encode = 'utf-8'
        self.ImgRegex = r'<img\s*src=["\']?([^\'" >]+?)[ \'"]\s*alt="\d*"\s*class="thumbnail_image"'
        self.ThreadsRegex = r'<h[23]\s*class="entry-header"\s*>\s*<a\s*href=["\']?([^\'">]+?)[\'"]\s*title=["\']?([^\'"]+?)[\'"]'

    def Download(self):
        if self.moeimgTags:
            res = self.LoadTags()
            if get_error(res):
                print(get_error(res))
                return
            tags = get_val(res)
        else:
            tags = ['default']
        print("===============   start   ===============");
        i = self.pageNum
        domain = ''
        for tag in tags:
            for i in range(self.pageNum, self.pageTo+1):
                if not self.moeimgTags:
                    print("===============   loading page {0}   ===============".format(i))
                    domain = "http://"+self.moeimgdomain+"/page-{0}.html".format(i-1)
                else:
                    print("===============   loading tag: %s page %i  ===============" % (tag,i))
                    domain = "http://"+self.moeimgdomain+"/?tag=%s&page=%i" % (tag,i-1)
                    #print(domain)
                res = self.DoFetch(domain)
                if get_error(res):
                    print(get_error(res))
        print("===============   end   ===============")

    def LoadTags(self):
        if os.path.exists('tags'):
            tagsfile = open('tags', 'r')
        else:
            return error('No tags file.')

        tags = []
        for tag in tagsfile:
            tags.append(tag.strip('\n'))
        #print(tags)
        return success(tags)

    def GetCurrentDir(self, href):
        dir = href[0].split('/')[-1]
        dir = dir.split('.')[-2]
        return dir

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
        self.ImgRegex = r'<input\s*type=\'image\'\s*src\s*=\s*["\']?([^\'" >]+?)[ \'"]'
        self.ThreadsRegex = r'<h3><a\s*href\s*=\s*["\']?([^\'">]+?)[ \'"][^>]*?>(?:<font color=green>)?([^<]*)(?:</font>)?</a></h3>'

    def Download(self):
        print("===============   start   ===============");
        for i in range(self.pageNum, self.pageTo+1):
            print("===============   loading page {0}   ===============".format(i))
            domain = "http://"+self.caoliudomain+"/thread0806.php?fid=16&search=&page={0}".format(i)
            res = self.DoFetch(domain)
            if get_error(res):
                print(get_error(res))
        print("===============   end   ===============")

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
        self.ImgRegex = r'<p><img\s*src=["\']?([^\'" >]+?)[ \'"]\s*(?:org_src=["\']?([^\'" >]+?)[ \'"])?'

    def Download(self):
        #get max
        res = self.FetchHtml("http://"+self.jandandomain+"/ooxx")
        if get_error(res):
            return res
        html = get_val(res)
        self.jandanNewest = self.get_max(html)

        print("===============   start   ===============");
        for i in range(self.jandanNewest-self.jandanPageToDownload+1, self.jandanNewest+1):
            print("===============   loading page {0}   ===============".format(i))
            domain = "http://"+self.jandandomain+"/ooxx/page-{0}#comments".format(i)
            res = self.FetchImageLinks(domain)
            if get_error(res):
                print(get_error(res))
        print("===============   end   ===============")

    def strip_tags(self, html):
        s = MLStripper()
        s.feed(html)
        return s.get_data()

    def get_max(self, html_code):
        m = re.search('.+cp-pagenavi.+', html_code)
        m = re.search('\d+', self.strip_tags(m.group(0)).strip())
        return int(m.group(0))

    def PreHandleImgLink(self, href):
        if href[1] != '':
            return href[1]
        else:
            return href[0]

def main(argv):
    #reload(sys)
    #sys.setdefaultencoding('utf-8')
    processed = False

    if 'caoliu' in argv or 'all' in argv:
        print("Processing caoliu...")
        CaoliuDownloader().Download()
        processed = True

    if 'moeimg' in argv or 'all' in argv:
        print("Processing moeimg...")
        MoeimgDownloader().Download()
        processed = True

    if 'jandan' in argv or 'all' in argv:
        print("Processing jandan...")
        JanDanDownloader().Download()
        processed = True

    if not processed:
        print("Usage: python catch.py [all][caoliu][moeimg][jandan]")

if __name__ == '__main__':
    main(sys.argv[1:])
