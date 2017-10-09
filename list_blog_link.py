#!/usr/bin/env python3
#coding:utf-8
import re
import os
import json
import redis
import requests
import multiprocessing
from collections import defaultdict
from bs4 import BeautifulSoup
from bs4 import SoupStrainer

homepage = 'http://ffuyue.pixnet.net/blog'
home_dir = 'http://ffuyue.pixnet.net'
collected_data = defaultdict(list)

def write_blog_link():
	fix_link_title = '<p style="margin: 0px 0px 1em; padding: 0px; color: rgb(85, 85, 85); font-family: Verdana;"><span style="font-family:arial,helvetica,sans-serif"><span style="font-size:16px">-延伸閱讀-</span></span></p>\n'
	fix_type_content_part1 = '<p style="margin: 0px 0px 1em; padding: 0px; color: rgb(84, 155, 237);"><span style="font-family:arial,helvetica,sans-serif; font-size:18px;"><strong>'
	fix_type_content_part2 = '</strong></span></p>\n'

	fix_link_content_part1 = '<p style="margin: 0px 0px 1em; padding: 0px; color: rgb(85, 85, 85);"><span style="font-family:arial,helvetica,sans-serif"><strong>►'
	fix_link_content_part2 = ' target="_blank">'
	fix_link_content_part3 = '</a></span></strong></p>\n'

	output = fix_link_title
	for category, article_list in sorted(collected_data.items()):
		output += fix_type_content_part1
		output += category
		output += fix_type_content_part2
		for link_title_pair in article_list:
			output += fix_link_content_part1
			output += '<a href="{:s}"'.format(link_title_pair[0])
			output += fix_link_content_part2
			output += link_title_pair[1]
			output += fix_link_content_part3
		output += '\n\n'

	with open('links.txt', 'wt') as fout:
		fout.write(output)


def get_link(text):
	global collected_data
	articles_only = SoupStrainer('div', id='article-area')
	soup = BeautifulSoup(text, 'lxml', parse_only = articles_only)
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


if '__main__' == __name__:
	os.system('redis-server &')

	req = requests.get(homepage)
	req.encoding = 'utf8'
	
	only_category = SoupStrainer('div', id='category')
	category = BeautifulSoup(req.text, 'lxml', parse_only=only_category)
	plist = list()
	for link in category('a'):
		if '(0)' in link.string:
			continue
		print('[Category] {:s}'.format(link.string))
		p = multiprocessing.Process(target = visit_category, args = (home_dir + link['href'],) )
		plist.append(p)
		p.start()

	for p in plist:
		p.join()

	collected_data.clear()
	conn = redis.Redis()
	result = conn.lrange('list_blog_link', 0, -1)
	for r in result:
		collected_data.update(json.loads(r.decode()))
	
	write_blog_link()
	os.system('redis-cli shutdown')
