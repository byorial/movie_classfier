# -*- coding: utf-8 -*-
#########################################################
# python
import os
import datetime
import traceback
import urllib
import time
from datetime import datetime
import re
import subprocess
from collections import OrderedDict

# third-party
from sqlalchemy import desc
from sqlalchemy import or_, and_, func, not_
import requests
from lxml import html
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
import platform


# sjva 공용
from framework import app, db, scheduler, path_app_root, path_data, celery
from framework.job import Job
from framework.util import Util


# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem

headers = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1',
    'Accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding' : 'gzip, deflate, br',
    'Accept-Language' : 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'Referer' : ''
}


#########################################################
class LogicNormal(object):
    session = requests.Session()
    driver = None
    moved_queue = list()
    dirs = ['kor', 'kor_vod', 'vod', 'sub_x', 'sub_o', 'imdb', 'no_movie']

    @staticmethod
    @celery.task
    def scheduler_function():
        return LogicNormal.task(True, False)

    @staticmethod
    def one_execute():
        return LogicNormal.task(False, False)

    @staticmethod
    def test():
        return LogicNormal.task(False, True)

    @staticmethod
    def task(time_flag, test_flag):
        logger.debug('%s STARTED', __name__)
        del LogicNormal.moved_queue[:]
        try:
            movie_list = LogicNormal.get_movie_items(time_flag)
            if movie_list is None or len(movie_list) is 0:
                logger.debug('no movie to move')
                return 'Success'
            logger.debug('get movie items(%d)', len(movie_list))
            LogicNormal.movie_classfy(movie_list, test_flag)
            if test_flag: return 'Success'

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            if test_flag: return "Failed"

    @staticmethod
    def movie_classfy(movie_list, test_flag):
        try:
            for movie in movie_list:
                cr_time         = movie[1]
                fname           = movie[2].encode('utf-8')
                is_file         = movie[4]
                target          = movie[6].encode('utf-8')
                dest_folder_name= movie[7].encode('utf-8')
                movie_id        = movie[9]

                if dest_folder_name is '' or movie_id is None:
                    logger.debug('no movie!! skip(fname:%s)', fname)
                    continue

                minfo           = movie[12].encode('utf-8')

                if minfo is None: logger.debug('not found movie info'); continue

                logger.debug('-------------------- [movie_info] -----------------------')
                logger.debug('cr_time  : %s' % cr_time)
                logger.debug('movie_id : %s' % movie_id)
                logger.debug('fname    : %s' % fname)
                logger.debug('minfo    : %s' % minfo)
                logger.debug('is_file  : %s' % is_file)
                logger.debug('target   : %s' % target)
                logger.debug('dstfolder: %s' % dest_folder_name)
                logger.debug('---------------------------------------------------------')

                fname_first = ModelSetting.get_bool('fname_first')
                proc_type_dict = LogicNormal.get_proc_type()
                for proc_type, func in proc_type_dict.items():
                    if proc_type is 'fname': arg = fname
                    else: arg = minfo
                    new_target = func(arg)

                    if new_target is not None:
                        logger.debug('[%s] movie is target content(%s) move to (%s)', proc_type, fname, new_target)
                        entity = LogicNormal.save_item(fname, minfo, target, new_target, movie_id, proc_type, True)
                        if test_flag:
                            logger.debug('file does not moved: just test(%s)', fname)
                        else:
                            LogicNormal.move_target_movie(fname, target, dest_folder_name, new_target) 
                        break
                    else:
                        logger.debug('[%s] movie is not target content(%s)', proc_type, fname, new_target)
                        entity = LogicNormal.save_item(fname, minfo, target, "none", movie_id, "none", True)

            if test_flag is False and ModelSetting.get_bool('move_other'):
                LogicNormal.move_other_movie()

            logger.debug('movie classfier processed')
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def save_item(fname, movie_info, orig_target, dest_target, movie_id, match_type, is_moved):
        entity = {}
        entity['id'] = ''
        entity['fname'] = fname
        entity['movie_info'] = movie_info
        entity['orig_target'] = orig_target
        entity['dest_target'] = dest_target
        entity['movie_id'] = movie_id
        entity['match_type'] = match_type
        entity['is_movied'] = is_moved
        ModelItem.save_as_dict(entity)
        return entity

    @staticmethod
    def get_proc_type():
        if ModelSetting.get_bool('fname_first'):
            return OrderedDict([('fname', LogicNormal.is_target_fname), ('minfo', LogicNormal.is_target_minfo)])
        return OrderedDict([('minfo', LogicNormal.is_target_minfo), ('fname', LogicNormal.is_target_fname)])

    @staticmethod
    def get_movie_items(time_flag):
        try:
            import sqlite3
            db_path = os.path.join(path_data, 'db', 'sjva.db')
            if platform.system() is 'Linux':
                # connect to read only for Linux
                fd = os.open(db_path, os.O_RDONLY)
                conn = sqlite3.connect('/dev/fd/%d' % fd)
                os.close(fd)
            else:
                conn = sqlite3.connect(db_path)
            cur = conn.cursor()

            query = 'SELECT * FROM plugin_fileprocess_movie_item'

            if time_flag:
                cr_time = ModelItem.get_last_time()
                if cr_time is not 0:
                    logger.debug('time target (%s)', cr_time)
                    cr_time = cr_time + '.000000'
                    query = 'SELECT * FROM plugin_fileprocess_movie_item where created_time > Datetime("{cr_time}")'.format(cr_time=cr_time)

            cur.execute(query)
            mlist = cur.fetchall()
            conn.close()
            return mlist

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return None

    @staticmethod
    def is_target_fname(fname):
        try:
            from .logic import Logic
            rules = Logic.fname_rules

            for keywords in rules.keys():
                found = False

                for keyword in keywords.split('|'):
                    gregx = re.compile(keyword, re.I)
                    if gregx.search(fname) is not None:
                        logger.debug('[target] fname matched (%s:%s)', keyword, fname)
                        return rules[keywords].encode('utf-8')
                    else:
                        logger.debug('[target] fname not matched (%s:%s)', keyword, fname)

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return None

    @staticmethod
    def is_target_minfo(info):
        try:
            from .logic import Logic
            rules = Logic.minfo_rules

            for keywords in rules.keys():
                enckeywords = keywords.encode('utf-8')
                found = False

                for keyword in enckeywords.split('|'):
                    gregx = re.compile(keyword, re.I)
                    if gregx.search(info) is not None:
                        logger.debug('[target] minfo matched (%s:%s)', keyword, info)
                        found = True
                        target = rules[keywords].encode('utf-8')
                    else:
                        logger.debug('[target] minfo not matched (%s:%s)', keywords, info)
                        found = False
                        break

                if found is True: return target

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return None

    @staticmethod
    def move_dir(orig, dest):
        import shutil
        try:
            new_dest = os.path.join(dest, orig[orig.rfind('/') + 1:])
            if os.path.isdir(new_dest):
                for item in os.listdir(orig):
                    new_orig = os.path.join(orig, item)
                    logger.debug('movie file: orig(%s) > dest(%s)', new_orig, new_dest)
                    shutil.move(new_orig, new_dest)
            else:
                shutil.move(orig, dest)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def move_target_movie(fname, orig, dest_folder_name, dest):
        try:
            orig_path   = os.path.join(ModelSetting.get('proc_path'), orig, dest_folder_name)
            orig_fpath  = os.path.join(orig_path, fname)
            dest_path   = os.path.join(ModelSetting.get('post_path'), dest)

            if orig_path in LogicNormal.moved_queue:
                logger.debug('already moved file(%s)', orig_fpath)
                return

            if os.path.isdir(orig_path):
                logger.debug('move target movie: orig(%s) > dest(%s)', orig_path, dest_path)
                if os.path.isdir(dest_path) is False: os.mkdir(dest_path)
                LogigNormal.move_dir(orig_path, dest_path)
                LogicNormal.moved_queue.append(orig_path)
            else:
                logger.info('orig_path not exist(%s)', orig_path)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def move_other_movie():
        try:
            for target in LogicNormal.dirs:
                orig_path   = os.path.join(ModelSetting.get('proc_path'), target)
                logger.debug('move other movie: from(%s) to(%s)', orig_path, ModelSetting.get('post_path'))

                if os.path.isdir(orig_path) is False:
                    logger.info('not exist orig_dir(%s)', orig_path)
                    continue
                for dname in os.listdir(orig_path):
                    orig = os.path.join(orig_path, dname)
                    dest = os.path.join(ModelSetting.get('post_path'), target)

                    logger.debug('move movie orig(%s) > dest(%s)', orig, dest)
                    LogigNormal.move_dir(orig, dest)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_html(url, referer=None, stream=False):
        try:
            data = ""

            if LogicNormal.session is None:
                LogicNormal.session = requests.session()
            #logger.debug('get_html :%s', url)
            headers['Referer'] = '' if referer is None else referer
            try:
                page_content = LogicNormal.session.get(url, headers=headers)
            except Exception as e:
                logger.debug("Connection aborted!!!!!!!!!!!")
                time.sleep(10) #Connection aborted 시 10초 대기 후 다시 시작
                page_content = LogicNormal.session.get(url, headers=headers)

            data = page_content.text
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return data
    
    @staticmethod
    def lcs(a, b):

        if len(a) == 0 or len(b) == 0:
            return 0
        if a == b :
            if len(a)<len(b):
                return len(b)
            else:
                return len(a)

        if len(a)<len(b):
            c = a
            a = b
            b = c
        prev = [0]*len(a)
        for i,r in enumerate(a):
            current = []
            for j,c in enumerate(b):
                if r==c:
                    e = prev[j-1]+1 if i* j > 0 else 1
                else:
                    e = max(prev[j] if i > 0 else 0, current[-1] if j > 0 else 0)
                current.append(e)
            prev = current
        
        return current[-1]
