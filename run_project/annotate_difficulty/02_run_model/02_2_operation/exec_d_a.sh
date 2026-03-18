#!/bin/bash

ver=$1 

echo "HelloWorld : "$1

ps_cnt=`ps -ef | grep /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/main.py | grep ${ver} | grep -v color | wc -l`
ps_cnt=$((ps_cnt + 0))

echo "ps_cnt : "$ps_cnt


if [ $ps_cnt -eq 0 ]; then
    echo "Start Batch"
    CUDA_VISIBLE_DEVICES=2,3 /home/mghan/sopjt/git/so_difficulty_measure/venv_so_difficulty_measure/bin/python /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/main.py `echo $ver`
fi
