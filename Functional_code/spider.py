# 爬取新闻网页的爬虫
import random
import requests
import get_key
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import configparser
from datetime import timedelta, date
import time
import socket
from queue import Queue
from threading import Thread  # 多线程实现

# 设置请求头
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.41'}

keyword = '编辑'

# 新闻计数
num = 1
count = 0

# 代理ip池
proxies_list = []

# 打开文件读取代理Ip列表
file = open("../agencyID.txt", "r")
lines = file.readlines()
# 关闭文件
file.close()
for line in lines:
    proxies_list.append({'http': line.strip()})


# 定义一个类，继承自Thread类
class Spider(Thread):
    def __init__(self, name, news_pool, min_len, doc_path, doc_encoding, my_sum):
        super().__init__()  # 调用父类的初始化方法
        self.news_pool = news_pool
        self.min_len = min_len
        self.doc_path = doc_path
        self.doc_encoding = doc_encoding
        self.name = name
        self.my_sum = my_sum

    # 重写run方法，定义线程的执行逻辑
    def run(self):
        self.crawling()

    # 根据新闻池爬取每一条新闻的信息,同时剔除新闻过短的无用信息
    def crawling(self):
        print(self.name, '开始运行')
        global num
        global count
        for n in range(self.news_pool.qsize() + 1):
            if news_pool.empty():
                break
            count = count + 1
            # 打印当前采集信息
            print(self.name, '%d/%d' % (count, self.my_sum))
            news = self.news_pool.get()
            try:
                proxies = random.choice(proxies_list)
                response = requests.get(news[1], headers=headers, proxies=proxies, timeout=10)  # 发送请求，获取响应
                response.encoding = "utf-8"  # 修改编码方式，否则解析后中文是乱码
                html = response.text
                # 抛出异常以后休息几分钟，防止被服务器封禁，也是为了可持续爬取
            except socket.timeout as err:
                print('socket.timeout')
                print(err)
                print(news[1])
                print("Sleeping for 1 minute")
                time.sleep(60)
                continue
            except Exception as e:
                print("------%s:%s-----" % (type(e), news[1]))
                print("Sleeping for 20 s")
                time.sleep(20)
                continue

            soup = BeautifulSoup(html, 'lxml')
            try:
                ps = soup.find('div', class_='left_zw').find_all('p')
            except Exception as e:
                print("Sleeping for 10 s")
                time.sleep(10)
                continue

            body = ''
            for p in ps:
                cur = p.get_text().strip()
                if cur == '':  # 没有文本就继续循环
                    continue
                body += '\t' + cur + '\n'  # 文本分段
            body = body.replace(' ', '')

            if len(body) <= self.min_len:  # 过滤篇幅过小的文本
                continue

            doc = ET.Element('doc')
            ET.SubElement(doc, 'id').text = '%d' % num
            ET.SubElement(doc, 'url').text = news[1]
            ET.SubElement(doc, 'title').text = news[2]
            ET.SubElement(doc, 'datatime').text = news[0]
            ET.SubElement(doc, 'body').text = body
            ET.SubElement(doc, 'key_sentence').text = get_key.textrank(body)  # 获取新闻摘要
            tree = ET.ElementTree(doc)
            tree.write(self.doc_path + '%d.xml' % num, encoding=self.doc_encoding, xml_declaration=True)
            num = num + 1  # 文件数加1
            if num % 300 == 0:
                # 每爬取300个新闻网页，就休息3分钟保证友好性
                print("Sleeping for 10 s")
                time.sleep(10)


# 获取一个网页的新闻信息
def get_one_page(news_pool, page_url):
    root = 'http://www.chinanews.com'
    try:
        # 打开网络连接，超过10秒无响应就抛出异常
        proxies = random.choice(proxies_list)
        response = requests.get(page_url, headers=headers, proxies=proxies, timeout=10)  # 发送请求，获取响应
        response.encoding = "utf-8"  # 修改编码方式，否则解析后中文是乱码
        html = response.text
    except socket.timeout as err:
        # 抛出超时异常
        print('socket.timeout')
        print(page_url)
        print(err)
        return []
    except Exception as e:
        # 抛出其他异常，并打印异常信息
        print("-----%s: %s" % (type(e), page_url))
        return []
    # 解析html代码
    soup = BeautifulSoup(html, 'lxml')
    news_list = soup.find('div', class_='content_list')
    items = news_list.find_all('li')

    for i, item in enumerate(items):
        if len(item) == 0:
            continue
        # 寻找包含所需要信息的对应的元素块
        a = item.find('div', class_='dd_bt').find('a')
        title = a.string
        url = a.get('href')
        if root in url:
            url = url[len(root):]  # 去掉包含root的连接，只保留相对路径

        # 获取新闻类别
        category = ''
        try:
            category = item.find('div', class_='dd_lm').find('a').string
        except Exception as e:
            continue
        # 剔除图片数据
        if category == '图片':
            continue
        # 从连接提取年份
        year = url.split('/')[-3]
        date_time = item.find('div', class_='dd_time').string
        data_time = '%s-%s:00' % (year, date_time)  # 时间
        news_info = [data_time, 'http://www.chinanews.com' + url, title]  # 一条新闻信息
        news_pool.put(news_info)  # 将新闻链接入队


# 获取网页信息形成新闻页面池
def get_news(news_pool, start_date, end_date):
    delta = timedelta(days=1)
    n = 0
    # 爬取起止时间的网页
    while start_date <= end_date:
        n = n + 1
        data_str = start_date.strftime('%Y/%m%d')  # 将时间转为字符串格
        page_url = 'http://www.chinanews.com/scroll-news/%s/news.shtml' % data_str
        print('获取日期为 %s 的新闻' % data_str)
        # 获取单个日期的所有新闻
        get_one_page(news_pool, page_url)

        start_date += delta


if __name__ == '__main__':
    config = configparser.ConfigParser()
    # 加载配置文件
    config.read('../config.ini', 'utf-8')
    delta = timedelta(days=-40)  # 设置一个-n天，将起始时间设置为n天前，爬取最近n天的信息
    end_date = date.today()
    start_date = end_date + delta

    # 创建一个URL队列
    news_pool = Queue()
    # 获取新闻放入新闻池队列
    get_news(news_pool, start_date, end_date)

    print('本次爬取共 %d 条新闻' % news_pool.qsize())
    # print(delta, start_date)

    my_sum = news_pool.qsize()

    # 创建一个空列表，用于存储线程对象
    threads = []

    # 创建100个爬虫线程，传入参数，添加到线程列表
    for i in range(100):
        name = '爬虫线程' + str(i + 1)
        spider = Spider(name, news_pool, 10, "../data/thread_data/", config['DEFAULT']['doc_encoding'], my_sum)
        spider.start()  # 启动一个新的线程，让它进入就绪状态，等待操作系统的调度。当线程被调度后，它会执行由ThreadStart或ParameterizedThreadStart委托表示的方法。
        threads.append(spider)

    # 等待所有线程结束
    # 如果没有 for 循环中的 join() 方法，那么主线程就不会等待子线程，而是直接执行后面的代码，可能会导致主线程先于子线程结束，或者主线程和子线程同时执行，造成数据不一致或者其他问题。
    for thread in threads:
        thread.join()  # 是一个阻塞方法，它会让调用它的线程挂起，直到被调用的线程执行完毕

    # crawling(news_pool, 10, config['DEFAULT']['doc_dir_path'], config['DEFAULT']['doc_encoding'])
    print('工作完成')
