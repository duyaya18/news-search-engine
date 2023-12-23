import sqlite3
from os import listdir
import xml.etree.ElementTree as ET
import jieba
import configparser


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class Index:
    stop_word = set()  # 停用词集合
    post_list = {}  # 倒排表

    config_path = ''  # 配置文件路径
    config_encoding = ''

    def __init__(self, config_path, config_encoding):
        self.config_path = config_path
        self.config_encoding = config_encoding
        config = configparser.ConfigParser()
        config.read(config_path, config_encoding)
        f = open(config['DEFAULT']['stop_words_path'], encoding=config['DEFAULT']['stop_words_encoding'])
        words = f.read()
        self.stop_words = set(words.split('\n'))

    # 计算一个文件的总词数和对应词词频
    def claen_list(self, seg_list):
        cleaned_dict = {}
        n = 0  # 总词数
        for word in seg_list:
            word = word.strip().lower()  # 每个词去掉前后空格再转小写，标准化
            if word != '' and not is_number(word) and word not in self.stop_words:  # 筛选合法的词
                n = n + 1
                if word in cleaned_dict:
                    cleaned_dict[word] = cleaned_dict[word] + 1
                else:
                    cleaned_dict[word] = 1
        return n, cleaned_dict

    def construct_list(self):
        config = configparser.ConfigParser()
        config.read(self.config_path, self.config_encoding)
        files = listdir(config['DEFAULT']['doc_dir_path'])  # 读取路径下所有子文件或文件的名字
        averageL = 0  # 平均文件长
        for file in files:
            # 获取每一个文件的路径，并获取文件
            root = ET.parse(config['DEFAULT']['doc_dir_path'] + file).getroot()
            title = root.find('title').text
            body = root.find('body').text
            doc_id = int(root.find('id').text)  # 文件的id
            date_time = root.find('datatime').text
            # 将一个文件所有文本用jieba分词
            seg_list = jieba.lcut(title + '。' + body, cut_all=False)

            ld, cleaned_dict = self.claen_list(seg_list)

            averageL = averageL + ld

            for word, value in cleaned_dict.items():
                d = str(doc_id)+','+date_time+','+str(value)+','+str(ld)  # 每一个关键词对应诸多文件,一个元组一个文件

                if word in self.post_list:
                    self.post_list[word][0] = self.post_list[word][0] + 1  # df加
                    self.post_list[word][1].append(d)  # 加入关键字列表
                else:
                    self.post_list[word] = [1, [d]]  # [df,[对应的文档...]]
        averageL = averageL / len(files)
        config.set('DEFAULT', 'N', str(len(files)))
        config.set('DEFAULT', 'avg_l', str(averageL))
        with open(self.config_path, 'w', encoding=self.config_encoding) as configfile:
            config.write(configfile)  # 更新配置文件
        self.write_to_db(config['DEFAULT']['db_path'])

    def write_to_db(self, db_path):  # 将倒排索引写入数据库
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        c.execute('''DROP TABLE IF EXISTS postings''')
        c.execute('''CREATE TABLE postings
                     (term TEXT PRIMARY KEY, df INTEGER, docs TEXT)''')

        for key, value in self.post_list.items():
            doc_list = '\n'.join(map(str, value[1]))
            t = (key, value[0], doc_list)
            c.execute("INSERT INTO postings VALUES (?, ?, ?)", t)

        conn.commit()
        conn.close()


if __name__ == '__main__':
    index = Index('../config.ini', 'utf-8')
    index.construct_list()
