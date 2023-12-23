from os import listdir
import xml.etree.ElementTree as ET
import jieba
import jieba.analyse
import sqlite3
import configparser
from datetime import *
import math

import pandas as pd
import numpy as np

from sklearn.metrics import pairwise_distances


class RecommendationModule:
    stop_words = set()
    k_nearest = []

    config_path = ''
    config_encoding = ''

    doc_dir_path = ''
    doc_encoding = ''
    stop_words_path = ''
    stop_words_encoding = ''
    idf_path = ''
    db_path = ''

    def __init__(self, config_path, config_encoding):
        self.config_path = config_path
        self.config_encoding = config_encoding
        config = configparser.ConfigParser()
        config.read(config_path, config_encoding)

        self.doc_dir_path = config['DEFAULT']['doc_dir_path']
        self.doc_encoding = config['DEFAULT']['doc_encoding']
        self.stop_words_path = config['DEFAULT']['stop_words_path']
        self.stop_words_encoding = config['DEFAULT']['stop_words_encoding']
        self.idf_path = config['DEFAULT']['idf_path']
        self.db_path = config['DEFAULT']['db_path']

        f = open(self.stop_words_path, encoding=self.stop_words_encoding)
        words = f.read()
        self.stop_words = set(words.split('\n'))

    def write_k_nearest_matrix_to_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute('''DROP TABLE IF EXISTS knearest''')
        c.execute('''CREATE TABLE knearest
                     (id INTEGER PRIMARY KEY, first INTEGER, second INTEGER,
                     third INTEGER, fourth INTEGER, fifth INTEGER)''')

        for docid, doclist in self.k_nearest:
            c.execute("INSERT INTO knearest VALUES (?, ?, ?, ?, ?, ?)", tuple([docid] + doclist))

        conn.commit()
        conn.close()

    def is_number(self, s):
        try:
            float(s)
            return True
        except ValueError:
            return False

    def construct_dt_matrix(self, files, topK=200):
        jieba.analyse.set_stop_words(self.stop_words_path)
        jieba.analyse.set_idf_path(self.idf_path)
        M = len(files)
        N = 1
        terms = {}
        dt = []
        for i in files:
            root = ET.parse(self.doc_dir_path + i).getroot()
            title = root.find('title').text
            body = root.find('body').text
            docid = int(root.find('id').text)
            # 根据TF-IDF算法计算每个词语在文本中的重要程度，并返回权重排名靠前的关键词作为结果
            tags = jieba.analyse.extract_tags(title + '。' + body, topK=topK, withWeight=True)
            # tags = jieba.analyse.extract_tags(title, topK=topK, withWeight=True)
            cleaned_dict = {}
            for word, tfidf in tags:
                word = word.strip().lower()
                if word == '' or self.is_number(word):
                    continue
                cleaned_dict[word] = tfidf  # 单词和对于的tfidf值
                if word not in terms:
                    terms[word] = N
                    N += 1  # 每添加一个单词进去，就加1，给每一个单词编号
            dt.append([docid, cleaned_dict])  # dt存放的是每一个文件对应一个列表，列表中存放的是[文件编号,{每个单词：对应的tfidf值,...}]
        dt_matrix = [[0 for i in range(N)] for j in range(M)]  # N是总的单词数，M是文件数，生成一个MxN的矩阵
        i = 0
        for docid, t_tfidf in dt:  # docid:文件编号，tfidf:字典，遍历每一个文件和它的字典
            dt_matrix[i][0] = docid  # 二维数组的每一行第一个元素是文件编号
            for term, tfidf in t_tfidf.items():
                dt_matrix[i][terms[term]] = tfidf
            i += 1

        dt_matrix = pd.DataFrame(dt_matrix)
        dt_matrix.index = dt_matrix[0]  # 将第一列设置为索引，也就是用文件编号作为索引
        print('dt_matrix shape:(%d %d)' % (dt_matrix.shape))
        return dt_matrix

    def construct_k_nearest_matrix(self, dt_matrix, k):
        tmp = np.array(1 - pairwise_distances(dt_matrix[dt_matrix.columns[1:]], metric="cosine"))  # 1-余弦相似度
        similarity_matrix = pd.DataFrame(tmp, index=dt_matrix.index.tolist(),
                                         columns=dt_matrix.index.tolist())  # 文档与文档之间的相似性
        for i in similarity_matrix.index:
            tmp = [int(i), []]
            j = 0
            while j < k:  # 找到5个相关性最接近的
                temp = similarity_matrix.loc[i, :] # temp是series，需要转成dataframe
                temp = temp.to_frame()
                max_col = temp.idxmax()  # 返回最大的那个
                max_c = max_col.iloc[0]
                similarity_matrix.loc[i][max_c] = -1 # 找到以后就设置为-1，从下次查找中排除
                if max_c != int(i): # 排除文档本身
                    tmp[1].append(int(max_c))  # max column name
                    j += 1
            self.k_nearest.append(tmp)

    def gen_idf_file(self):
        files = listdir(self.doc_dir_path)
        n = float(len(files))
        idf = {}
        for i in files:
            root = ET.parse(self.doc_dir_path + i).getroot()
            title = root.find('title').text
            body = root.find('body').text
            seg_list = jieba.lcut(title + '。' + body, cut_all=False)
            seg_list = set(seg_list) - self.stop_words
            for word in seg_list:
                word = word.strip().lower()
                if word == '' or self.is_number(word):
                    continue
                if word not in idf:
                    idf[word] = 1
                else:
                    idf[word] = idf[word] + 1
        idf_file = open(self.idf_path, 'w', encoding='utf-8')
        for word, df in idf.items():
            idf_file.write('%s %.9f\n' % (word, math.log(n / df)))
        idf_file.close()

    def find_k_nearest(self, k, topK):
        self.gen_idf_file()
        files = listdir(self.doc_dir_path)
        dt_matrix = self.construct_dt_matrix(files, topK)
        self.construct_k_nearest_matrix(dt_matrix, k)
        self.write_k_nearest_matrix_to_db()


if __name__ == "__main__":
    print('-----start time: %s-----' % (datetime.today()))
    rm = RecommendationModule('../config.ini', 'utf-8')
    rm.find_k_nearest(15, 25)
    print('-----finish time: %s-----' % (datetime.today()))
