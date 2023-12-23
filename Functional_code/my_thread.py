# 一个用来测试多线程的简单爬虫，不是项目用到的爬虫
import requests
from bs4 import BeautifulSoup
from queue import Queue
from threading import Thread

proxies_list = [
    {'http': '38.62.222.62:3128'},
    {'http': '154.6.99.95:3128'}
]

# 打开文件
file = open("../agencyID.txt", "r")
lines = file.readlines()
# 关闭文件
file.close()
for line in lines:
    proxies_list.append({'http': line.strip()})


# 定义一个类，继承自Thread类
class Spider(Thread):
    # 初始化方法，接收参数
    def __init__(self, name, url_queue, data_queue):
        super().__init__()  # 调用父类的初始化方法
        self.name = name  # 线程名
        self.url_queue = url_queue  # URL队列
        self.data_queue = data_queue  # 数据队列
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.41'}

    # 重写run方法，定义线程的执行逻辑
    def run(self):
        print(self.name, '开始运行')
        while not self.url_queue.empty():  # 只要URL队列不为空，就继续执行
            url = self.url_queue.get()  # 从URL队列中获取一个URL
            print(self.name, '正在采集', url)
            response = requests.get(url, headers=self.headers)  # 发送请求，获取响应
            self.data_queue.put(response.text)  # 将响应数据存入数据队列
        print(self.name, '结束运行')


# 定义一个类，继承自Thread类
class Parser(Thread):
    # 初始化方法，接收参数
    def __init__(self, name, data_queue, file):
        super().__init__()  # 调用父类的初始化方法
        self.name = name  # 线程名
        self.data_queue = data_queue  # 数据队列
        self.file = file  # 文件对象

    # 重写run方法，定义线程的执行逻辑
    def run(self):
        print(self.name, '开始运行')
        while not self.data_queue.empty():  # 只要数据队列不为空，就继续执行
            data = self.data_queue.get()  # 从数据队列中获取一个数据
            print(self.name, '正在解析')
            self.parse(data)  # 调用解析方法，传入数据
        print(self.name, '结束运行')

    # 定义一个解析方法，接收数据
    def parse(self, data):
        soup = BeautifulSoup(data, 'lxml')  # 创建一个BeautifulSoup对象，解析数据
        results = soup.find_all('h3', class_='t')  # 找出所有的h3标签，class属性为t的元素，返回一个列表
        for result in results:  # 遍历每个结果
            title = result.a.text  # 获取标题
            link = result.a['href']  # 获取链接
            self.file.write(title + '\n' + link + '\n')  # 写入文件


# 定义一个主函数，运行爬虫
def main():
    # 创建一个URL队列
    url_queue = Queue()
    # 创建一个数据队列
    data_queue = Queue()
    # 定义一个基础URL
    base_url = 'https://www.baidu.com/s?wd=python&pn={}'
    # 循环生成10个URL，存入URL队列
    for i in range(10):
        url = base_url.format(i * 10)
        url_queue.put(url)
    # 打开一个文件，用于保存结果
    file = open('baidu.txt', 'w', encoding='utf-8')
    # 创建一个空列表，用于存储线程对象
    threads = []
    # 创建三个采集线程，传入参数，添加到线程列表
    for i in range(3):
        name = '采集线程' + str(i + 1)
        spider = Spider(name, url_queue, data_queue)
        spider.start()  # 启动一个新的线程，让它进入就绪状态，等待操作系统的调度。当线程被调度后，它会执行由ThreadStart或ParameterizedThreadStart委托表示的方法。
        threads.append(spider)

    for thread in threads:
        thread.join()

    # 创建两个解析线程，传入参数，添加到线程列表
    for i in range(2):
        name = '解析线程' + str(i + 1)
        parser = Parser(name, data_queue, file)
        parser.start()
        threads.append(parser)
    # 等待所有线程结束
    # 如果没有 for 循环中的 join() 方法，那么主线程就不会等待子线程，而是直接执行后面的代码，可能会导致主线程先于子线程结束，或者主线程和子线程同时执行，造成数据不一致或者其他问题。
    for thread in threads:
        thread.join()  # 是一个阻塞方法，它会让调用它的线程挂起，直到被调用的线程执行完毕
    # 关闭文件
    file.close()
    # 打印提示信息
    print('爬虫结束')


# 判断是否是主模块，执行主函数
if __name__ == '__main__':
    # main()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/117.0.0.0 Safari/537.36 Edg/117.0.2045.41'}
    for i in range(len(proxies_list)):
        print(requests.get('http://httpbin.org/ip', headers=headers, proxies=proxies_list[i], timeout=3).text)
