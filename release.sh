#!/bin/bash

version=$(cat version)

artifact=whisper-backup-"$version".zip

if [[ ! -f "$artifact" ]];
then
    zip "$artifact" setup.py whisperbackup/*
fi

if echo $version | grep -q -v dev
then
    git tag "$version"
    git push --tags origin master
fi
