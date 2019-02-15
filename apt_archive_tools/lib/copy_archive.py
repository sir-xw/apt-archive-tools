# encoding: utf-8
'''
Created on 2016-6-23

@author: xiewei

复制已有源中的某个suite，同时生成reprepro的db

'''

from ..contrib import docopt
import os
import logging

logger = logging.getLogger('archive_man')

cmd_doc = """
Usage:
   archive_man copy <source> <destdir> -s <suite> [-a <arch>...] [-c <components>...]

Options:
   -h, --help   show this help.
   -s, --suite=<suite>  codename of suite.
   -a, --arch=<arch>    choosed architectures, May be specified multiple
                        times. [default: i386 amd64 armhf arm64]
   -c, --component=<components>
                        components of local archive, May be specified
                        multiple times. [default: main restricted universe multiverse]
"""

command = 'copy'

def _verify_args(args):
    data = {}
    data['arch'] = ' '.join(args['--arch'])
    data['suite'] = args['--suite']
    data['component'] = ' '.join(args['--component'])
    if args['<source>'].find(':/') > 0:
        data['source'] = args['<source>']
    else:
        data['source'] = 'file://' + os.path.abspath(args['<source>'])
    data['destdir'] = os.path.expanduser(args['<destdir>'])
    return data


def _init_config(data):
    basedir = data['destdir']
    confdir = os.path.join(basedir, 'conf')
    try:
        os.makedirs(confdir, mode=0o775)
    except:
        pass
    if not os.path.isdir(confdir):
        raise Exception('cannot create config directory: "%s"' % confdir)
    with open(os.path.join(confdir, 'distributions'), 'w') as f:
        f.write("""Codename: %(suite)s
Architectures: %(arch)s
Components: %(component)s
Update: - %(suite)s
""" % data)
    with open(os.path.join(confdir, 'updates'), 'w') as f:
        f.write("""Name: %(suite)s
Method: %(source)s
Suite: %(suite)s
Components: %(component)s
Architectures: %(arch)s
""" % data)
    with open(os.path.join(confdir, 'options'), 'w') as f:
        f.write("""verbose
basedir .
""")
    logger.info(u'已生成reprepro配置文件')
    return


def copy_archive(data):
    _init_config(data)
    result = os.system('reprepro -b "%(destdir)s" update' % data)
    if result != 0:
        logger.error(u'复制软件源失败')
    else:
        logger.info(u'复制完成')
    return result


def main(argv=None):
    """
    copy archive (only one suite) to a local directory
    """
    args = docopt.docopt(cmd_doc, argv, help=True)
    data = _verify_args(args)
    return copy_archive(data)
