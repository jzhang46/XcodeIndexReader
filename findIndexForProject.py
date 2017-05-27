#!/usr/bin/python
#  -*- coding: UTF-8 -*-


import sys
import os.path


def get_index_folder_for_project_path(project_path):
    if len(project_path) == 0:
        print "What project do you want to find?"
        exit(0)

    derived_data_dir = os.path.expanduser("~/Library/Developer/Xcode/DerivedData/")
    for dirname in os.listdir(derived_data_dir):
        sub_dir = os.path.join(derived_data_dir, dirname)
        if not os.path.isdir(sub_dir):
            continue

        for target_dir in os.listdir(sub_dir):
            if target_dir.lower() == 'info.plist':
                file_path = os.path.join(sub_dir, target_dir)
                f = open(file_path, 'r')
                contents = f.read()
                if contents.find(project_path) > 0:
                    return sub_dir + '/'


def get_index_path_for_project_path(project_path):
    folder = get_index_folder_for_project_path(project_path)
    if not folder:
        return None

    for subdirs, dirs, files in os.walk(folder):
        for aDir in dirs:
            if aDir.lower().endswith('.xcindex'):
                return os.path.join(subdirs, aDir)+'/'

    return None
