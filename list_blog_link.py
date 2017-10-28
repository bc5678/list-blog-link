#!/usr/bin/env python3
#coding:utf-8
import re
import os
import json
import shutil
import subprocess
import multiprocessing
from collections import defaultdict
import requests
from bs4 import BeautifulSoup
from bs4 import SoupStrainer
import redis

git_dir = 'bc5678.github.io'
collected_data = defaultdict(list)


def prepare_html_folder():
    git_html_addr = 'https://github.com/bc5678/bc5678.github.io.git'
    if os.path.exists(git_dir):
        shutil.rmtree(git_dir)
    subprocess.call(('git clone ' + git_html_addr).split())


def upload_html():
    os.chdir(git_dir)
    subprocess.call('git add *.html'.split())
    subprocess.call('git commit -m "auto_commit"'.split())
    subprocess.call('git push origin master'.split())


def collect_data():
    global collected_data
    collected_data.clear()
    conn = redis.Redis()
    result = conn.lrange('list_blog_link', 0, -1)
    for r in result:
        d = json.loads(r.decode())
        if set(d.keys()) & set(collected_data.keys()):
            for key in d.keys():
                collected_data[key] += d[key]
        else:
            collected_data.update(d)


def write_html():
    HTML_HEAD = '''<html>
<head>
    <title> </title>
</head>
<body>
    <p style="margin: 0px 0px 1em; padding: 0px; color: rgb(85, 85, 85); font-family: Verdana;">
        <span style="font-family:arial,helvetica,sans-serif"><span style="font-size:16px">-延伸閱讀-</span></span>
    </p>
'''
    HTML_TAIL = '''
</body>
</html>
'''
    fix_type_content_part1 = '<p style="margin: 0px 0px 1em; padding: 0px; color: rgb(84, 155, 237);"><span style="font-family:arial,helvetica,sans-serif; font-size:18px;"><strong>'
    fix_type_content_part2 = '</strong></span></p>\n'

    fix_link_content_part1 = '<p style="margin: 0px 0px 1em; padding: 0px; color: rgb(85, 85, 85);"><span style="font-family:arial,helvetica,sans-serif"><strong>►'
    fix_link_content_part2 = ' target="_blank">'
    fix_link_content_part3 = '</a></span></strong></p>\n'

    HTML_TABLE = [
        ('link_taipei_zhongzheng_station.html', ['台北中正', '台北北車']),
        ('link_taipei_daan.html', ['台北大安']),
        ('link_taipei_nangang.html', ['台北南港']),
        ('link_taipei_neihu.html', ['台北內湖']),
        ('link_taipei_shilin.html', ['台北士林']),
        ('link_taipei_songshan_minsheng.html', ['台北松山', '台北民生社區']),
        ('link_taipei_wanhua.html', ['台北萬華']),
        ('link_taipei_xinyi.html', ['台北信義']),
        ('link_taipei_zhongshan_dazhi.html', ['台北中山', '台北大直']),
        ('link_taipei_datong.html', ['台北大同']),
        ('link_taiwan_instant_food.html', ['台灣‧速食']),
        ('link_china_shanghai.html', ['中國上海']),
    ]

    for entry in HTML_TABLE:
        with open(os.path.join(git_dir, entry[0]), 'wt') as fout:
            fout.write(HTML_HEAD)

    for category, article_list in sorted(collected_data.items()):
        output_str = ''
        output_str += fix_type_content_part1
        output_str += category
        output_str += fix_type_content_part2
        for link_title_pair in article_list:
            output_str += fix_link_content_part1
            output_str += '<a href="{:s}"'.format(link_title_pair[0])
            output_str += fix_link_content_part2
            output_str += link_title_pair[1]
            output_str += fix_link_content_part3
        for html in HTML_TABLE:
            for keyword in html[1]:
                if keyword in category:
                    with open(os.path.join(git_dir, html[0]), 'at') as fout:
                        fout.write(output_str)

    for entry in HTML_TABLE:
        with open(os.path.join(git_dir, entry[0]), 'at') as fout:
            fout.write(HTML_TAIL)


def get_link(text):
    global collected_data
    articles_only = SoupStrainer('div', id='article-area')
    soup = BeautifulSoup(text, 'lxml', parse_only=articles_only)
    articles = soup('div', 'article')
    for article in articles:
        a = article.find('li', 'title')
        s = re.split('\|', a.string.strip())
        collected_data['|' + s[1] + '|'].append((a['data-article-link'], a.string.strip()))


def visit_category(link):
    global collected_data
    req = requests.get(link)
    req.encoding = 'utf8'
    get_link(req.text)

    nextpages = set(re.findall(link + '/\d+', req.text))
    for n in nextpages:
        req = requests.get(n)
        req.encoding = 'utf8'
        get_link(req.text)

    conn = redis.Redis()
    conn.rpush('list_blog_link', json.dumps(collected_data))


if __name__ == '__main__':
    homepage = 'http://ffuyue.pixnet.net/blog'
    home_dir = 'http://ffuyue.pixnet.net'

    pfolder = multiprocessing.Process(target=prepare_html_folder)
    pfolder.start()
    subprocess.call('redis-server &', shell=True)

    req = requests.get(homepage)
    req.encoding = 'utf8'

    only_category = SoupStrainer('div', id='category')
    category = BeautifulSoup(req.text, 'lxml', parse_only=only_category)

    plist = list()
    conn = redis.Redis()
    conn.delete('list_blog_link')
    for link in category('a'):
        if '(0)' in link.string:
            continue
        print('[Category] {:s}'.format(link.string))
        p = multiprocessing.Process(target=visit_category, args=(home_dir + link['href'],))
        plist.append(p)
        p.start()

    for p in plist:
        p.join()

    collect_data()
    subprocess.call('redis-cli shutdown &', shell=True)

    pfolder.join()
    write_html()
    upload_html()
