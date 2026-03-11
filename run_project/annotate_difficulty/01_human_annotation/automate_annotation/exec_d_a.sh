#!/bin/bash

ver=$1 

echo "HelloWorld : "$1

ps_cnt=`ps -ef | grep /home/mghan/sopjt/git/stackoverflow_src_2425/difficulty/automate_annotation/main.py | grep ${ver} | grep -v color | wc -l`
ps_cnt=$((ps_cnt + 0))

echo "ps_cnt : "$ps_cnt

cd /home/mghan/sopjt/git

if [ $ps_cnt -eq 0 ]; then
    echo "Hello World"
    venv_stackoverflow_src/bin/python /home/mghan/sopjt/git/stackoverflow_src_2425/difficulty/automate_annotation/main.py `echo $ver` > ./log/${ver}.log
fi
