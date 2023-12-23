# -*- encoding:utf-8 -*-
from __future__ import print_function  # 中文文本摘要
import xml.etree.ElementTree as ET
from textrank4zh import TextRank4Keyword, TextRank4Sentence


def textrank(text):
    key_sentence = ''
    tr4w = TextRank4Keyword()
    text = str(text)
    tr4w.analyze(text=text, lower=True, window=2)
    tr4s = TextRank4Sentence()
    tr4s.analyze(text=text, lower=True, source='all_filters')
    for item in tr4s.get_key_sentences(num=4):  # 取4句
        key_sentence = key_sentence + item['sentence'] + '。'  # index是语句在文本中位置，weight是权重
    return key_sentence


if __name__ == '__main__':
    root = ET.parse('../data/news/1.xml').getroot()
    body = root.find('body').text
    print(textrank(body))
