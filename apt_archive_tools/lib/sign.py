# encoding: utf-8
'''
Created on 2019-01-22

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
   archive_man sign <file> [-p <password>]

Options:
   -h, --help  show this help
   -p, --password=<password>    the password of the imported signing key,
                                if you need and didn't set it in the config file

This command help user sign the "Release" file of a apt archive,
the signed file will be "InRelease" and "Release.gpg".

if <file> is a directory, then sign "<dir>/Release".
if <file> is a normal file, then directly sign it, even the file name is not "Release".
"""


def sign_file(filepath, password=None, restrict=False):
    gpg = gnupg.GPG(gnupghome=config.GPGHOME)
    if not gpg.list_keys(secret=True):
        error_str = '尝试签名出错，未导入私钥，请先执行 %s key import' % sys.argv[0]
        if restrict:
            logger.error(error_str)
            sys.exit(1)
        else:
            logger.warning(error_str)
            return 1
    if os.path.isdir(filepath):
        release_file = os.path.join(filepath, 'Release')
        fn = 'Release'
    else:
        release_file = filepath
        filepath, fn = os.path.split(release_file)

    if not os.path.exists(release_file):
        error_str = 'File not exist: %s'
        if restrict:
            logger.error(error_str, release_file)
            sys.exit(1)
        else:
            logger.warning(error_str, release_file)
            return 1

    data = open(release_file, 'rb').read()
    if password is None:
        password = config.GPGKEYPASS
    result = gpg.sign(data, passphrase=password,
                      clearsign=True, binary=False,
                      algo='sha512'
                      )
    assert result.data, result.stderr
    with open(os.path.join(filepath, 'In' + fn), 'wb') as f:
        f.write(result.data)

    result = gpg.sign(data, passphrase=password,
                      clearsign=False, binary=True,
                      algo='sha512'
                      )
    assert result.data, result.stderr
    with open(os.path.join(filepath, fn + '.gpg'), 'wb') as f:
        f.write(result.data)
    logger.info('Release signed')
    return 0


def main(argv=None):
    """
    sign Release file with imported PGP key
    """
    args = docopt.docopt(cmd_doc, argv, help=True)
    return sign_file(args['<file>'], password=args['--password'],restrict=True)
