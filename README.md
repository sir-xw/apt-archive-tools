# 用于修改apt软件仓库的工具集

安装：
===
推荐:

    python setup.py sdist
    sudo pip install dist/* 或 pip install --user dist/*

不推荐:

    sudo python setup.py install --record install.log

卸载：
===
如果是pip安装：

    pip uninstall apt-tools-xiewei

如果是setup.py安装：

    cat install.log | xargs sudo rm -rf

临时使用：
===
直接运行 archive-man.py

查看命令行帮助
===

    archive-man --help

依赖：
===
python-2.7

apt-utils

reprepro

gnupg

普通软件源操作：
===

有一堆deb包，想要发布成一个apt源
---
创建源文件夹a（名字可以随意，但不要用中文），在里面创建一个pool的子文件夹

    mkdir -p a/pool

把deb包放到pool目录里

    cp /path-to-my-package/*.deb a/pool/

执行发布命令

    archive-man publish a -s stable -a arm64

- -s 指定版本代号

- -a 可以指定多次，如果想要用同一个目录提供多个体系结构的软件源

发布完后会提示source.list的写法。

复制一个远程软件源
---
可以复制某个软件源的一部分（指定需要的系列，指定需要的体系结构，指定需要的component）

    archive-man copy http://archive.ubuntu.com/ubuntu /local-path -s xenial -a amd64 -a i386 -c main -c universe

- -s 指定版本代号
- -a 指定体系结构，可以指定多次
- -c 指定软件源component，可以指定多次

All Functions
===
   key
   ---
   import PGP key for signing

   sign
   ---
   sign Release file with imported PGP key

   copy
   ---
   copy archive (only one suite) to a local directory

   local-copy
   ---
   just like cp, but files in pool/ will be a hardlink to source

   publish
   ---
   publish a customized archive form a package pool

   merge
   ---
   merge 2 or more suites into a new suite in the same archive

   strip
   ---
   remove unnecessary files from pool/ if local archive

   diff
   ---
   compare the package list of two dists

   check
   ---
   check missing or unnecessary  debian packages in archive

   checkdep
   ---
   check dependencies of packages in an archive

   rename
   ---
   change filename of package in the archive indexes
