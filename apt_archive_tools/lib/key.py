# encoding: utf-8

from __future__ import print_function

'''
Created on 2016-6-14

@author: xiewei
'''

import os
import sys
from ..contrib import gnupg
from ..contrib import docopt
from . import config
from . import logging

logger = logging.getLogger('archive_man')

cmd_doc = """
Usage:
   archive_man key import <keyfile> [-p <password>]
   archive_man key delete <keyid>
   archive_man key list

Options:
   -h, --help                   show this help
   -p, --password=<password>    save password in the config file,
                                then automatically use it while signing file
"""


def add_key(keyfile):
    gpg = gnupg.GPG(gnupghome=config.GPGHOME)
    with open(keyfile) as f:
        result = gpg.import_keys(f.read())
    try:
        assert result.stderr.find('IMPORT_OK') >= 0, result.stderr
    except AssertionError:
        logger.error(u'导入出错: %s' % result.stderr)
        sys.exit(1)


def delete_key(keyid):
    gpg = gnupg.GPG(gnupghome=config.GPGHOME)
    result = gpg.delete_keys(keyid, secret=True)
    try:
        assert str(result) == 'ok', result.stderr
    except AssertionError:
        logger.error(u'删除出错: %s' % result.stderr)
        sys.exit(1)


def list_key():
    gpg = gnupg.GPG(gnupghome=config.GPGHOME)
    result = gpg.list_keys(secret=True)
    for secret in result:
        print(secret['fingerprint'], ', '.join(secret['uids']))


def main(argv=None):
    """
    import PGP key for signing
    """
    args = docopt.docopt(cmd_doc, argv, help=True)
    if args['import']:
        add_key(args['<keyfile>'])
        if args['--password']:
            config.conf.set('app', 'gpgpass', args['--password'])
            config.store()
    elif args['delete']:
        delete_key(args['<keyid>'])
    elif args['list']:
        list_key()
    else:
        pass
    return 0
