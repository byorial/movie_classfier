# -*- coding: utf-8 -*-
#########################################################
# python
import traceback
from datetime import datetime
import json
import os

# third-party
from sqlalchemy import or_, and_, func, not_, desc
from sqlalchemy.orm import backref

# sjva 공용
from framework import app, db, path_app_root
from framework.util import Util

# 패키지 
from .plugin import logger, package_name
from sqlalchemy import create_engine

app.config['SQLALCHEMY_BINDS'][package_name] = 'sqlite:///%s' % (os.path.join(path_app_root, 'data', 'db', '%s.db' % package_name))
#########################################################
class ModelSetting(db.Model):
    __tablename__ = '%s_setting' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String, nullable=False)

    def __init__(self, key, value):
        self.key = key
        self.value = value

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    @staticmethod
    def get(key):
        try:
            return db.session.query(ModelSetting).filter_by(key=key).first().value.strip()
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def get_int(key):
        try:
            return int(ModelSetting.get(key))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def get_bool(key):
        try:
            return (ModelSetting.get(key) == 'True')
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def set(key, value):
        try:
            item = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
            if item is not None:
                item.value = value.strip()
                db.session.commit()
            else:
                db.session.add(ModelSetting(key, value.strip()))
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())

    @staticmethod
    def to_dict():
        try:
            return Util.db_list_to_dict(db.session.query(ModelSetting).all())
        except Exception as e:
            logger.error('Exception:%s %s', e, key)
            logger.error(traceback.format_exc())


    @staticmethod
    def setting_save(req):
        try:
            for key, value in req.form.items():
                if key in ['scheduler', 'is_running']:
                    continue
                logger.debug('Key:%s Value:%s', key, value)
                entity = db.session.query(ModelSetting).filter_by(key=key).with_for_update().first()
                entity.value = value
            db.session.commit()
            return True
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
            logger.debug('Error Key:%s Value:%s', key, value)
            return False




class ModelItem(db.Model):
    __tablename__ = '%s_item' % package_name
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = package_name

    id = db.Column(db.Integer, primary_key=True)
    json = db.Column(db.JSON)
    created_time = db.Column(db.DateTime)

    fname = db.Column(db.String)
    movie_info = db.Column(db.String)
    orig_target = db.Column(db.String)
    dest_target = db.Column(db.String)
    movie_id = db.Column(db.String)
    match_type = db.Column(db.String)
    is_moved = db.Column(db.Boolean)

    def __init__(self):
        self.created_time = datetime.now()

    def __repr__(self):
        return repr(self.as_dict())

    def as_dict(self):
        ret = {x.name: getattr(self, x.name) for x in self.__table__.columns}
        ret['created_time'] = self.created_time.strftime('%Y-%m-%d %H:%M:%S') 
        #ret['start_time'] = self.start_time.strftime('%m-%d %H:%M:%S') if self.start_time is not None else None
        #ret['end_time'] = self.end_time.strftime('%m-%d %H:%M:%S') if self.end_time is not None else None

        return ret

    @staticmethod
    def save_as_dict(d):
        try:
            entity = ModelItem()
            entity.fname = unicode(d['fname'])
            entity.movie_info = unicode(d['movie_info'])
            entity.orig_target = unicode(d['orig_target'])
            entity.dest_target = unicode(d['dest_target'])
            entity.movie_id = unicode(d['movie_id'])
            entity.match_type = unicode(d['match_type'])
            entity.is_moved = d['is_moved']

            db.session.add(entity)
            db.session.commit()
        except Exception as e:
            logger.error(d)
            logger.error('Exception:%s', e)

    @staticmethod
    def get_last_time():
        query = db.session.query(ModelItem)
        query = query.order_by(desc(ModelItem.created_time))
        query = query.limit(1).offset(0)
        lists = query.all()
        count = int(query.count())

        if count is 1:
            result = lists[0].as_dict()
            created_time = result['created_time']
            return created_time

        return 0

    @staticmethod
    def web_list(req):
        try:
            ret = {}
            page = 1
            page_size = 30
            job_id = ''
            search = ''
            option = req.form['option']
            if 'page' in req.form:
                page = int(req.form['page'])
            if 'search_word' in req.form:
                search = req.form['search_word']
            order = req.form['order'] if 'order' in req.form else 'desc'
            match_type = req.form['option']

            query = ModelItem.make_query(search=search, match_type=match_type, order=order)
            count = query.count()
            query = query.limit(page_size).offset((page-1)*page_size)
            lists = query.all()
            ret['list'] = [item.as_dict() for item in lists]
            ret['paging'] = Util.get_paging_info(count, page, page_size)
            return ret
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def make_query(search='', match_type='all', order='desc'):
        query = db.session.query(ModelItem)
        if search is not None and search != '':
            if search.find('|') != -1:
                conditions = []
                for tt in search.split('|'):
                    if tt != '': conditions.append(ModelItem.fname.like('%'+tt.strip()+'%'))
                query = query.filter(or_(*conditions))
            elif search.find(',') != -1:
                for tt in search.split('|'):
                    if tt != '': query = query.filter(ModelItem.fname.like('%'+tt.strip()+'%'))
            else:
                query = query.filter(ModelItem.fname.like('%'+search+'%'))

        if match_type != 'all':
            query = query.filter(ModelItem.match_type == match_type)

        if order == 'desc':
            query = query.order_by(desc(ModelItem.id))
        else:
            query = query.order_by(ModelItem.id)

        return query

    @staticmethod
    def get(id):
        try:
            entity = db.session.query(ModelItem).filter_by(id=id).with_for_update().first()
            return entity
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    @staticmethod
    def delete(id):
        try:
            logger.debug( "delete")
            db.session.query(ModelItem).filter_by(id=id).delete()
            db.session.commit()

        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
