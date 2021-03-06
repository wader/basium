#! /usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (c) 2012-2013, Anders Lowinger, Abundo AB
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the <organization> nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Main entrypoint for all basium functionality

This file does all the heavy lifting, setting up and initializing
everything that is needed to use the persistence framework, together
with some common code for all modules

Usage:
 Create a new instance of this class, with the correct driver name
 Register the tables that should be persisted
 Call start
"""


import json
import datetime
import decimal

import basium_common as bc

log = bc.Logger()
log.info("Basium default logger started")

# These must be after definition of the logger instance
import basium_orm
import basium_model

Error = bc.Error


class DbConf:
    """
    Information to the selected database driver, how to connect to database
    """
    def __init__(self, host=None, port=None, username=None, password=None, database=None, debugSQL=False, log=None):
        self.host = host
        self.port = None
        self.username = username
        self.password = password
        self.database = database
        self.debugSQL = debugSQL


class Basium(basium_orm.BasiumOrm):
    """
    Main class for basium usage
    """
    def __init__(self, logger=None, driver=None, checkTables=True, dbconf=None):
        global log
        if logger:
            self.log = logger
            log = logger
            log.debug("Switching to external logger")
        else:
            self.log = log  # use simple logger
        self.log.info("Basium logging started.")
        self.drivername = driver
        self.checkTables = checkTables
        self.dbconf = dbconf

        self.cls = {}
        self.drivermodule = None
        self.Response = bc.Response      # for convenience in dynamic pages
        self.Error = bc.Error            # for convenience in dynamic pages
        self.debug = 0

    def setDebug(self, debugLevel):
        self.debug = debugLevel

    def addClass(self, cls):
        if not isinstance(cls, type):
            self.log.error('addClass() called with an instance of an object')
            return False
        if not issubclass(cls, basium_model.Model):
            self.log.error("Fatal: addClass() called with object that doesn't inherit from basium_model.Model")
            return False
        if cls._table in self.cls:
            self.log.error("addClass() already called for %s" % cls._table)
            return False
        self.cls[cls._table] = cls
        return True

    class JsonOrmEncoder(json.JSONEncoder):
        """Handle additional types in JSON encoder"""
        def default(self, obj):
            if isinstance(obj, bc.Response):
                return obj.data
            if isinstance(obj, datetime.date):
                return strFromDatetime(obj)
            if isinstance(obj, datetime.datetime):
                return strFromDatetime(obj)
            if isinstance(obj, decimal.Decimal):
                return str(obj)
            if isinstance(obj, basium_model.Model):
                return obj._getStrValues()
            if isinstance(obj, bytes):
                return obj.decode()
            return json.JSONEncoder.default(self, obj)

    def start(self):
        if self.drivermodule:
            self.log.error("basium::start() already called")
            return None

        driverfile = "basium_driver_%s" % self.drivername
        try:
            self.drivermodule = __import__(driverfile)
        except bc.Error as err:
            self.log.error(str(err))
            return None
        except ImportError:
            self.log.error('Unknown driver %s, cannot find file %s.py' % (self.drivername, driverfile))
            return None

        self.driver = self.drivermodule.BasiumDriver(log=self.log, dbconf=self.dbconf)
        self.driver.debug = self.debug
        if not self.startOrm(self.driver, self.drivermodule):
            log.error("Cannot initialize ORM")
            return None
        if not self.isDatabase(self.dbconf.database):
            log.error("Database %s does not exist" % self.dbconf.database)
            return None

        for cls in self.cls.values():
            obj = cls()
            if not self.isTable(obj):
                if self.checkTables:
                    if not self.createTable(obj):
                        return None
            else:
                if self.checkTables:
                    actions = self.verifyTable(obj)
                    if actions is not None and len(actions) > 0:
                        self.modifyTable(obj, actions)

        return True


def dateFromStr(s):
    """
    Take a date formatted as a string and return a datetime object
    """
    return datetime.datetime.strptime(s, '%Y-%m-%d %H:%M:%S')


def strFromDate(d):
    """
    Take a date object and return a string
    """
    return d.strftime('%Y-%m-%d')


def strFromDatetime(d):
    """
    Take a datetime object and return a string
    """
    return d.strftime('%Y-%m-%d %H:%M:%S')
