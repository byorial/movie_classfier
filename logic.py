# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
import threading
import subprocess
import json

# third-party
import datetime, re
from collections import OrderedDict

# sjva 공용
from framework import db, scheduler, path_data, celery, app
from framework.job import Job
from framework.util import Util

# 패키지 
from .plugin import logger, package_name
from .model import ModelSetting, ModelItem

from .logic_normal import LogicNormal

#########################################################

class Logic(object):
    db_default = {
        'db_version' : '1',
        'auto_start' : 'False',
        'interval' : '10',
        'proc_path' : '',
        'post_path' : '',
        'target_dirs' : u'kor|kor_vod|sub_o|sub_x|vod',
        'fname_first' : 'True',
        'fname_rules' : u'201[0-9][.], 2010s',
        'minfo_rules' : u'애니메이션|전체관람가, child',
        'move_other' : 'True',
    }
    fname_rules = OrderedDict()
    minfo_rules = OrderedDict()
    target_dirs = list()

    @staticmethod
    def db_init():
        try:
            for key, value in Logic.db_default.items():
                if db.session.query(ModelSetting).filter_by(key=key).count() == 0:
                    db.session.add(ModelSetting(key, value))
            db.session.commit()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_load():
        try:
            logger.debug('%s plugin_load', package_name)
            Logic.db_init()

            if ModelSetting.get_bool('auto_start'):
                Logic.scheduler_start()

            # 경로규칙 변환
            Logic.load_rules()
            Logic.load_target_dirs()
            # 편의를 위해 json 파일 생성
            from plugin import plugin_info
            Util.save_from_dict_to_json(plugin_info, os.path.join(os.path.dirname(__file__), 'info.json'))

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def plugin_unload():
        try:
            logger.debug('%s plugin_unload', package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_start():
        try:
            logger.debug('%s scheduler_start' % package_name)
            job = Job(package_name, package_name, ModelSetting.get('interval'), Logic.scheduler_function, u"영화분류", False)
            scheduler.add_job_instance(job)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def scheduler_stop():
        try:
            logger.debug('%s scheduler_stop' % package_name)
            scheduler.remove_job(package_name)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def scheduler_function():
        try:
            #LogicNormal.scheduler_function()
            from framework import app
            if app.config['config']['use_celery']:
                result = LogicNormal.scheduler_function.apply_async()
                result.get()
            else:
                LogicNormal.scheduler_function()
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


    @staticmethod
    def reset_db():
        try:
            from .model import ModelItem
            db.session.query(ModelItem).delete()
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            return False

    @staticmethod
    def get_app_config():
        try:
            config = {}
            for key, value in app.config.items():
                config[key] = value
            del config['SECRET_KEY']
            config = json.dumps(config, sort_keys=True, indent=4, default=lambda x: str(x))
            return config
        except Exception as e:
            logger.error('Exception: %s', e)
            logger.error(traceback.format_exc())
            return ''


    @staticmethod
    def one_execute():
        try:
            def func():
                time.sleep(2)
                LogicNormal.one_execute()

            threading.Thread(target=func, args=()).start()
            ret = 'thread'
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
        return ret

    @staticmethod
    def load_target_dirs():
        try:
            str_dirs = ModelSetting.get('target_dirs')
            Logic.target_dirs = [x.strip() for x in str_dirs.split('|')]
            logger.debug(Logic.target_dirs)

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'

    @staticmethod
    def load_rules():
        try:
            list_rules  = []
            str_rules   = ModelSetting.get('fname_rules')
            lines = list(x.strip() for x in str_rules.split('\n'))
            for line in lines: list_rules.append(tuple(x.strip() for x in line.split(',')))
            Logic.fname_rules = OrderedDict(list_rules)
            logger.debug(Logic.fname_rules)

            list_rules  = []
            str_rules   = ModelSetting.get('minfo_rules')
            lines = list(x.strip() for x in str_rules.split('\n'))
            for line in lines: list_rules.append(tuple(x.strip() for x in line.split(',')))
            Logic.minfo_rules = OrderedDict(list_rules)
            logger.debug(Logic.minfo_rules)

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            ret = 'fail'
