#!/bin/bash
date

pushd test_audio

rm -rf *.txt
./tinyplay 16k2ch.wav -D 1 -d 1 -p 320 -n 4 &
sleep 3
./tinycap 8k2chn.wav -D 0 -d 0 -r 8000 -c 2 -T 10
if [ $? -ne 0 ];then
	echo "record audio failed"
	echo "QA_FAIL_AUDIO"
	exit 1
fi

./audio_to_txt 8k2chn.wav 8k2chn.txt
if [ $? -ne 0 ];then
	echo "analyze 8k2chn.wav failed"
	echo "QA_FAIL_AUDIO"
	exit 1
fi

if [ ! -s "8k2chn.txt" ];then
	echo "8k2chn.txt is empty"
	echo "QA_FAIL_AUDIO"
	exit 1
fi

popd

date
echo "QA_PASS_AUDIO"
