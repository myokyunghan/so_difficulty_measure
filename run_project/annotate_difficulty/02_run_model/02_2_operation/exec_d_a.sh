#!/bin/bash



echo "HelloWorld : "$1
ver=$1
ps_cnt=`ps -ef | grep /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/main.py | grep ${ver} | grep -v color | wc -l`
# ps_cnt=`ps -ef | grep /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/python_main.py | grep -v color | grep -v grep | wc -l`
ps_cnt=$((ps_cnt + 0))

echo "ps_cnt : "$ps_cnt


if [ $ps_cnt -eq 0 ]; then
    echo "Start Batch"
    CUDA_VISIBLE_DEVICES=0,1 /home/mghan/sopjt/git/so_difficulty_measure/venv_so_difficulty_measure/bin/python /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/main.py `echo $ver`

    # CUDA_VISIBLE_DEVICES=2,3 /home/mghan/sopjt/git/so_difficulty_measure/venv_so_difficulty_measure/bin/python /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/main.py ver555550000
    
    # CUDA_VISIBLE_DEVICES=2,3 /home/mghan/sopjt/git/so_difficulty_measure/venv_so_difficulty_measure/bin/python /home/mghan/sopjt/git/so_difficulty_measure/lib/annotation/operation/python_main.py
fi
