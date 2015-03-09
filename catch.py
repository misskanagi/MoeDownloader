import sys
import logging
import os
import os.path
import requests
import re
import ConfigParser

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
        self.isMono = True
        self.keepOriginTitle = False
        self.numToDownload = -1
        self.loggingFile = 'log.txt'
        self.retryTimes = 5
        self.encode = None

        #moeimg specific
        self.moeimgdomain = 'example.com'

        #caoliu specific
        self.caoliudomain = 'example.com'

        if not os.path.exists('config'):
            print('No config file. Creating a default one.')
            self.SetDefaultConfig();
        self.LoadConfig()

        #init logging file
        logging.basicConfig(filename = os.path.join(os.getcwd(), self.loggingFile), level = logging.WARN, filemode = 'a+', format = '%(asctime)s - %(levelname)s: %(message)s')

    def LoadConfig(self):
        self.cf.read("config")
        self.pageNum = self.cf.getint('web','page')
        self.isMono = self.cf.getboolean('file','mono')
        self.numToDownload = self.cf.getint('web','num_to_download')
        self.loggingFile = self.cf.get('basic','log_file')
        self.retryTimes = self.cf.getint('web','retry_times')
        self.caoliudomain = self.cf.get('caoliu','domain')
        self.moeimgdomain = self.cf.get('moeimg','domain')
        self.keepOriginTitle = self.cf.getboolean('file','keep_origin_title')

    def SetDefaultConfig(self):
        self.cf.add_section('basic')
        self.cf.set('basic','log_file','log.txt')
        self.cf.add_section('web')
        self.cf.set('web','page','1')
        self.cf.set('web','num_to_download','-1')
        self.cf.set('web','retry_times','5')
        self.cf.add_section('caoliu')
        self.cf.set('caoliu','domain','example.com')
        self.cf.add_section('moeimg')
        self.cf.set('moeimg','domain','example.com')
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
        self.FetchThreadsLinks(domain, html);
        return success(0)

    def FetchThreadsLinks(self, domain, htmlSource):
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

    def GetThreadUrl(self, href):pass
    def GetTitle(self, href):pass
    def CheckThreadsValid(self, href):pass
    def GetCurrentDir(self, href):pass

    def FetchImageLinks(self, threadurl):
        res = self.FetchHtml(threadurl)
        if get_error(res):
            return res
        html = get_val(res)
        self.FetchLinksFromSource(html);
        return success(0)

    def FetchLinksFromSource(self, htmlSource):
        prog = re.compile(self.ImgRegex, re.IGNORECASE)
        matchesImgSrc = prog.findall(htmlSource)
        for href in matchesImgSrc:
            if not self.CheckIsUrlFormat(href):
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
        self.ThreadsRegex = r'<h2\s*class="entry-header"\s*>\s*<a\s*href=["\']?([^\'">]+?)[\'"]\s*title=["\']?([^\'"]+?)[\'"]'

    def Download(self):
        print("===============   start   ===============");
        i = self.pageNum
        print("===============   loading page {0}   ===============".format(i-1))
        domain = "http://"+self.moeimgdomain+"/page-{0}.html".format(i-1)
        res = self.DoFetch(domain)
        if get_error(res):
            print(get_error(res))
        print("===============   end   ===============")

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
        self.encode = 'gb2312'
        self.ImgRegex = r'<input\s*type=\'image\'\s*src\s*=\s*["\']?([^\'" >]+?)[ \'"]'
        self.ThreadsRegex = r'<h3><a\s*href\s*=\s*["\']?([^\'">]+?)[ \'"][^>]*?>(?:<font color=green>)?([^<]*)(?:</font>)?</a></h3>'

    def Download(self):
        print("===============   start   ===============");
        i = self.pageNum
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

def main(argv):
    reload(sys)                         # 2
    sys.setdefaultencoding('utf-8')     # 3
    if argv[0] == 'caoliu':
        g = CaoliuDownloader()
    elif argv[0] == 'moeimg':
        g = MoeimgDownloader()
    else:
        g = CaoliuDownloader()
    g.Download()


if __name__ == '__main__':
    main(sys.argv[1:])
