# MoeDownloader
测试用，准备做成各种福利图的嗅探器。
"`
usage: catch.py [-h] [-p PAGES] [-i] [-n] [-r RETRY] [-m] [-t THREADS]
                [-q | -v] [-d | --proxy PROXY] [--version]
                {caoliu,moeimg,jandan} ...

optional arguments:
  -h, --help            show this help message and exit
  -p PAGES, --pages PAGES
                        number of pages to download
  -i, --ignore_config   ignore config file and load with default options
  -n, --no_log          run without log
  -r RETRY, --retry RETRY
                        retry times if failed
  -m, --mono            set if mono file
  -t THREADS, --threads THREADS
                        number of threads to download
  -q, --quiet           run quietly and briefly
  -v, --verbose         run verbosely
  -d, --direct          connect directly(without proxy)
  --proxy PROXY         set http and https proxy
  --version             show program's version number and exit

subcommands:
  available subcommands

  {caoliu,moeimg,jandan}
    caoliu              download caoliu images
    moeimg              download moeimg images
    jandan              download jandan images
`"
