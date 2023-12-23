import jieba
import math
import operator
import sqlite3
import configparser
from datetime import *


# 判断数字
def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class Search:
    stop_words = set()
    config_path = ''
    config_encoding = ''

    conn = None

    K1 = 0
    B = 0
    N = 0
    AVG_L = 0

    HOT_K1 = 0  # HOT_K1 越大，表示 BM25 得分对热度得分的影响越大；HOT_K2 越大，表示时间距离对热度得分的影响越大
    HOT_K2 = 0

    def __init__(self, config_path, config_encoding):
        self.config_path = config_path
        self.config_encoding = config_encoding

        config = configparser.ConfigParser()
        config.read(config_path, config_encoding)
        # 读取文件中的停用词
        words = open(config['DEFAULT']['stop_words_path'], encoding=config['DEFAULT']['stop_words_encoding']).read()
        self.stop_words = set(words.split('\n'))
        # 建立数据库连接
        self.conn = sqlite3.connect(config['DEFAULT']['db_path'])

        self.K1 = float(config['DEFAULT']['k1'])
        self.B = float(config['DEFAULT']['b'])
        self.N = int(config['DEFAULT']['n'])
        self.AVG_L = float(config['DEFAULT']['avg_l'])
        self.HOT_K1 = float(config['DEFAULT']['hot_k1'])
        self.HOT_K2 = float(config['DEFAULT']['hot_k2'])

    def clean_list(self, seg_list):
        cleaned_fict = {}
        n = 0
        for word in seg_list:
            word = word.strip().lower()
            if word != '' and not is_number(word) and word not in self.stop_words:
                n = n + 1
                if word in cleaned_fict:
                    cleaned_fict[word] = cleaned_fict[word] + 1
                else:
                    cleaned_fict[word] = 1
        return n, cleaned_fict

    def get_db(self, term):
        c = self.conn.cursor()  # 创建游标对象
        c.execute('SELECT * FROM postings WHERE term=?', (term,))
        return c.fetchone()  # 返回一条记录

    # 用BM25算法计算文档相关度分数
    def result_by_bm25(self, sentence):
        # 给查询语句分词
        query = jieba.lcut(sentence, cut_all=False)
        n, cleaned_dict = self.clean_list(query)
        bm25_scores = {}
        for term in cleaned_dict.keys():  # 遍历query中的关键词
            r = self.get_db(term)
            if r is None:
                continue  # 如果找不到对应的文档，就换下一个关键词
            df = r[1]  # 文档频率
            # w是计算bm25中的参数，代表权重idf
            w = math.log2((self.N - df + 0.5) / (df + 0.5))
            docs = r[2].split('\n')  # 文档集合
            for doc in docs:
                temp = doc.split(',')
                doc_id, date_time, tf, ld = temp

                doc_id = int(doc_id)
                tf = int(tf)
                ld = int(ld)
                # s是计算对应的词term与文档的相关度
                s = (self.K1 * tf * w) / (tf + self.K1 * (1 - self.B + self.B * ld / self.AVG_L))
                if doc_id in bm25_scores:  # 计算文档对于query的bm25得分，分数是每一个关键词对文档分数之和
                    bm25_scores[doc_id] = bm25_scores[doc_id] + s
                else:
                    bm25_scores[doc_id] = s
        # 按得分进行排序
        bm25_scores = sorted(bm25_scores.items(), key=operator.itemgetter(1))
        # 降序
        bm25_scores.reverse()
        if len(bm25_scores) == 0:
            return 0, []
        else:
            return 1, bm25_scores

    def result_by_time(self, sentence):
        seg_list = jieba.lcut(sentence, cut_all=False)
        n, cleaned_dict = self.clean_list(seg_list)
        time_scores = {}
        for term in cleaned_dict.keys():
            r = self.get_db(term)  # 获取一条数据库记录
            if r is None:
                continue
            docs = r[2].split('\n')
            for doc in docs:
                docid, date_time, tf, ld = doc.split(',')
                if docid in time_scores:
                    continue
                news_datetime = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
                now_datetime = datetime.now()
                td = now_datetime - news_datetime
                docid = int(docid)
                td = (timedelta.total_seconds(td) / 3600)  # hour
                time_scores[docid] = td
        time_scores = sorted(time_scores.items(), key=operator.itemgetter(1))
        if len(time_scores) == 0:
            return 0, []
        else:
            return 1, time_scores

    def result_by_hot(self, sentence):
        seg_list = jieba.lcut(sentence, cut_all=False)
        n, cleaned_dict = self.clean_list(seg_list)
        hot_scores = {}
        for term in cleaned_dict.keys():
            r = self.get_db(term)
            if r is None:
                continue
            df = r[1]
            w = math.log2((self.N - df + 0.5) / (df + 0.5))
            docs = r[2].split('\n')
            for doc in docs:
                docid, date_time, tf, ld = doc.split(',')
                docid = int(docid)
                tf = int(tf)
                ld = int(ld)
                news_datetime = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
                now_datetime = datetime.now()
                td = now_datetime - news_datetime
                BM25_score = (self.K1 * tf * w) / (tf + self.K1 * (1 - self.B + self.B * ld / self.AVG_L))
                td = (timedelta.total_seconds(td) / 3600)  # hour
                #                hot_score = math.log(BM25_score) + 1 / td
                hot_score = self.HOT_K1 * self.sigmoid(BM25_score) + self.HOT_K2 / td  # HOT法
                if docid in hot_scores:
                    hot_scores[docid] = hot_scores[docid] + hot_score
                else:
                    hot_scores[docid] = hot_score
        hot_scores = sorted(hot_scores.items(), key=operator.itemgetter(1))
        hot_scores.reverse()
        if len(hot_scores) == 0:
            return 0, []
        else:
            return 1, hot_scores

    def sigmoid(self, x):
        return 1 / (1 + math.exp(-x))

    def search(self, sentence, sort_type=0):
        if sort_type == 0:
            return self.result_by_bm25(sentence)
        elif sort_type == 1:
            return self.result_by_time(sentence)
        elif sort_type == 2:
            return self.result_by_hot(sentence)


if __name__ == '__main__':
    search = Search('../config.ini', 'utf-8')
    flag, rs = search.search('俄罗斯和乌克兰', 1)
    print(rs[:10])
