'''
Created on 2016-6-14

@author: xiewei
'''

import os
try:
    from ConfigParser import SafeConfigParser
except ImportError:
    from configparser import SafeConfigParser

conf = SafeConfigParser()
conf.read([os.path.join(os.path.dirname(__file__), 'default.conf'),
           '/etc/apt-tools.conf',
           os.path.expanduser('~/.config/apt-tools.conf')
           ])

GPGHOME = os.path.expanduser(conf.get('app', 'gpghome'))
GPGKEYPASS = conf.get('app', 'gpgpass')
if not GPGKEYPASS:
    GPGKEYPASS = None

options = {'suite': conf.get('options', 'suite'),
           'arch': conf.get('options', 'arch')
           }


def store(path=os.path.expanduser('~/.config/apt-tools.conf')):
    path_dir = os.path.dirname(path)
    if not os.path.exists(path_dir):
        os.makedirs(path_dir)
    with open(path,'wb') as f:
        conf.write(f)
    return True
