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
    def scheduler_function():
        if app.config['config']['use_celery']:
            result = LogicNormal.task.apply_async((True, False,))
            result.get()
        else:
            LogicNormal.task(True, False)

    @staticmethod
    def one_execute():
        if app.config['config']['use_celery']:
            result = LogicNormal.task_one.apply_async((False, False,))
            result.get()
        else:
            LogicNormal.task(False, False)
            
    @staticmethod
    def test():
        if app.config['config']['use_celery']:
            result = LogicNormal.task_test.apply_async((False, True,))
            result.get()
        else:
            LogicNormal.task(False, True)

    @staticmethod
    @celery.task(bind=True)
    def task(self, *flag):
        time_flag = flag[0]
        test_flag = flag[1]
        logger.debug('%s STARTED (time_flag: %s, test_flag:%s)', __name__, str(time_flag), str(test_flag))
        
        del LogicNormal.moved_queue[:]
        try:
            movie_list = LogicNormal.get_movie_items(time_flag)
            if movie_list is None or len(movie_list) is 0:
                logger.debug('no movie to move')
            else:
                logger.debug('get movie items(%d)', len(movie_list))
                LogicNormal.movie_classfy(movie_list, test_flag)

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def movie_classfy(movie_list, test_flag):
        from .logic import Logic
        try:
            if ModelSetting.get('target_dirs') == u'' or ModelSetting.get('proc_path') == u'' \
                    or ModelSetting.get('post_path') == u'':
                logger.warning('path setting is empty, please set pathes and target_dirs')
                return
            # for celery
            Logic.load_target_dirs()

            for movie in movie_list:
                cr_time         = movie[1]
                fname           = movie[2].encode('utf-8')
                is_file         = movie[4]
                target          = movie[6].encode('utf-8')
                dest_folder_name= movie[7].encode('utf-8')
                movie_id        = movie[9]

                if dest_folder_name is '' or movie_id is None or movie[12] is None:
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

                # 이동대상 타겟인지 확인하여 타겟이 아닌 경우 처리결과에만 저장 하고 스킵 처리
                if target not in Logic.target_dirs:
                    logger.info('not target content(target: %s)', target)
                    entity = LogicNormal.save_item(fname, minfo, target, 'none', movie_id, 'none', False)
                    continue

                fname_first = ModelSetting.get_bool('fname_first')
                proc_type_dict = LogicNormal.get_proc_type()
                dict_len = len(proc_type_dict)
                curr_idx = 0
                for proc_type, func in proc_type_dict.items():
                    if proc_type is 'fname': arg = fname
                    else: arg = minfo
                    new_target = func(arg)
                    curr_idx = curr_idx + 1

                    if new_target is not None:
                        logger.debug('[%s] movie is target content(%s) move to (%s)', proc_type, fname, new_target)
                        entity = LogicNormal.save_item(fname, minfo, target, new_target, movie_id, proc_type, True)
                        if test_flag:
                            logger.debug('file does not moved: just test(%s)', fname)
                        else:
                            LogicNormal.move_target_movie(fname, target, dest_folder_name, new_target) 
                        break
                    else:
                        logger.debug('[%s] movie is not target content(%s)', proc_type, fname)
                        if curr_idx is dict_len:
                            entity = LogicNormal.save_item(fname, minfo, target, "none", movie_id, "none", True)

            logger.debug('END target-movie classfier processed')
            if test_flag is False and ModelSetting.get_bool('move_other'):
                logger.info('START non-targeted movie move')
                LogicNormal.move_other_movie()
                logger.info('END non-targeted movie is moved')

            logger.debug('END movie classfier processed')
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
        if is_moved: entity['is_moved'] = 1
        else: entity['is_moved'] = 0
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
                enckeywords = keywords.encode('utf-8')
                for keyword in enckeywords.split('|'):
                    found = False
                    for akeyword in keyword.split('&'):
                        gregx = re.compile(akeyword, re.I)
                        if gregx.search(fname) is None:
                            found = False
                            break
                        else: found = True

                    if found is True:
                        logger.info('[target] fname matched (%s:%s)', keyword, fname)
                        return rules[keywords].encode('utf-8')
                    else:
                        logger.debug('[target] fname not matched (%s:%s)', keyword, fname)

            return None

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
                for keyword in enckeywords.split('|'):
                    found = False
                    for akeyword in keyword.split('&'):
                        gregx = re.compile(akeyword, re.I)
                        if gregx.search(info) is None:
                            found = False
                            break
                        else: found = True

                    if found is True:
                        logger.info('[target] minfo matched (%s:%s)', keyword, info)
                        return rules[keywords].encode('utf-8')
                    else:
                        logger.debug('[target] minfo not matched (%s:%s)', keywords, info)

            return None

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return None

    @staticmethod
    def move_dir(orig, dest):
        import shutil
        try:
            new_dest = os.path.join(dest, orig[orig.rfind('/') + 1:])
            # 이동할 위치에 대상 폴더가 존재하는 경우 파일단위로 이동시킴
            if os.path.isdir(new_dest):
                for item in os.listdir(orig):
                    orig_file = os.path.join(orig, item)
                    dest_file = os.path.join(new_dest, item)
                    logger.debug('try to move file: orig(%s) > dest(%s)', orig_file, new_dest)

                    # 이동파일 덮어쓰기 On 인경우
                    if ModelSetting.get_bool('overwrite'):
                        if os.path.isfile(dest_file):
                            logger.debug('overwrite file: orig(%s) > dest(%s)', orig_file, dest_file)
                            shutil.move(orig_file, dest_file)
                        else:
                            logger.debug('move file: orig(%s) > dest(%s)', orig_file, new_dest)
                            shutil.move(orig_file, new_dest)
                    # 이동파일 덮어쓰기 Off 인경우
                    else:
                        # 대상폴더에 같은 파일이 있으면 SKIP: 아무것도 안함
                        if os.path.isfile(dest_file):
                            logger.debug('skip move: dest file already exist: dest(%s)', dest_file)
                        else:
                            logger.debug('move file: orig(%s) > dest(%s)', orig_file, new_dest)
                            shutil.move(orig_file, new_dest)
                # 파일단위로 이동완료 후 원본 폴더 삭제처리
                logger.debug('remove orig dir(%s)', orig)
                os.rmdir(orig)
            else:
                # 폴더 단위로 이동
                logger.debug('movie file: orig(%s) > dest(%s)', orig, dest)
                shutil.move(orig, dest)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def move_target_movie(fname, orig, dest_folder_name, dest):
        try:
            orig_path   = os.path.join(ModelSetting.get('proc_path'), orig, dest_folder_name)
            orig_fpath  = os.path.join(orig_path, fname)

            if dest.startswith('/'): dest_path = dest
            else: dest_path   = os.path.join(ModelSetting.get('post_path'), dest)

            if orig_path in LogicNormal.moved_queue:
                logger.debug('already moved file(%s)', orig_fpath)
                return

            if os.path.isdir(orig_path):
                logger.debug('move target movie: orig(%s) > dest(%s)', orig_path, dest_path)
                if os.path.isdir(dest_path) is False: os.makedirs(dest_path)
                LogicNormal.move_dir(orig_path, dest_path)
                LogicNormal.moved_queue.append(orig_path)
            else:
                logger.warning('orig_path not exist(%s)', orig_path)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def move_other_movie():
        try:
            from .logic import Logic
            for target in Logic.target_dirs:
                orig_path   = os.path.join(ModelSetting.get('proc_path'), target)
                logger.debug('move other movie: from(%s) to(%s)', orig_path, ModelSetting.get('post_path'))

                if os.path.isdir(orig_path) is False:
                    logger.warning('not exist orig_dir(%s)', orig_path)
                    continue
                for dname in os.listdir(orig_path):
                    orig = os.path.join(orig_path, dname)
                    dest = os.path.join(ModelSetting.get('post_path'), target)

                    logger.debug('move movie orig(%s) > dest(%s)', orig, dest)
                    LogicNormal.move_dir(orig, dest)
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
