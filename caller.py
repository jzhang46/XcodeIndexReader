#!/usr/bin/python
#  -*- coding: UTF-8 -*-


import sys
import os.path
import sqlite3
from functools import partial
from StringIO import StringIO
import re
import findIndexForProject


db_folder_path  = ""
db_file_name    = "db.xcindexdb"
sym_file_name   = "db.xcindexdb.strings-sym"
file_file_name  = "db.xcindexdb.strings-file"
dir_file_name   = "db.xcindexdb.strings-dir"
res_file_name   = "db.xcindexdb.strings-res"

file_name_to_content = {}
g_cursor = None
keyword_to_oc_func = {'im':'-', 'cm':'+', 'py':'-'}
oc_func_to_keyword = {'-':'im', '+':'cm'}
g_method_set = set()

# return True if not already read
# return False otherwise
def read_file_if_needed(file_name):
    if file_name not in file_name_to_content:
        file_path = db_folder_path + file_name
        f = open(file_path, 'rb')
        content = f.read()
        file_name_to_content[file_name] = content
        return True
    return False


# read target string from str_file, and return its offset from the file head
def get_target_pos_from_file(target, str_file):
    read_file_if_needed(str_file)
    file_content = file_name_to_content[str_file]
    if len(file_content) > 0:
        return file_content.find(target)
    return -1


# read the string from the offset pos in str_file
def get_string_from_pos_in_file(pos, str_file):
    read_file_if_needed(str_file)
    content = file_name_to_content[str_file];
    fl = StringIO(content)
    fl.seek(pos)
    return bytearray(iter(partial(fl.read, 1), b'\x00')).__str__()


def get_callers_for_resolution(resolution):
    callers = []

    #get position from resolution file for the resolution
    res_pos = get_target_pos_from_file(resolution, res_file_name)
    if res_pos < 0:
        print "error: didnot find %s" % resolution
        return []

    sql = "SELECT s.resolution, s.spelling, s.kind, s.language FROM symbol s \
            JOIN reference r WHERE r.resolution=? AND s.id=r.container"

    # sql = "SELECT r.resolution FROM reference r " \
    #       "JOIN symbol s ON s.id=r.container " \
    #       "WHERE s.resolution =? "
    query = g_cursor.execute(sql, (str(res_pos),))
    results = query.fetchall()
    for r in results:
        caller_res = get_string_from_pos_in_file(r[0], res_file_name)
        # caller_spelling = get_string_from_pos_in_file(r[1], sym_file_name)
        caller = caller_res
        callers.append(caller)
    return callers


def get_objc_string_from_res(resolution):
    m = re.match(r"(c:objc\(\w+\))(\w+)\((\w+)\)([\w:]+)", resolution)
    if m is not None:
        g = m.groups()
        if g[0] == 'c:objc(cs)':
            if g[2] in keyword_to_oc_func:
                prefix = keyword_to_oc_func[g[2]]
                return '%s[%s %s]' %(prefix, g[1], g[3])
    else:
        if resolution.startswith('c:@F@'):
            return resolution[5:]

    return None


def get_res_from_objc_method(method):
    m = re.match(r"([+-])\[(\w+) ([\w:]+)\]", method)
    g = m.groups()
    if g[0] in oc_func_to_keyword:
        keyword = oc_func_to_keyword[g[0]]
        return "c:objc(cs)%s(%s)%s" % (g[1], keyword, g[2])
    return method


def get_res_from_c_method(method):
    return "c:@F@%s" % method


def print_callhierarchy(prefix, method_res):
    if method_res in g_method_set:
        return
    g_method_set.add(method_res)

    printable_name = get_objc_string_from_res(method_res)
    if not printable_name:
        return
    print prefix + printable_name

    callers = get_callers_for_resolution(method_res)
    if callers and len(callers) > 0:
        for caller in callers:
            print_callhierarchy(prefix + "\t", caller)


def main(method):
    global g_cursor
    global db_folder_path

    arg_count = len(sys.argv)
    if arg_count > 1:
        db_folder_path = findIndexForProject.get_index_path_for_project_path(sys.argv[1])
        if not db_folder_path:
            print 'Could not find index folder for project: %s' % sys.argv[1]
            exit(0)
        if arg_count > 2:
            method = sys.argv[2]
    else:
        print 'Format: python caller.py project_path [func_name]'
        exit(0)

    db_path = db_folder_path + db_file_name
    if not os.path.exists(db_path):
        print 'Error: Cannot find database at: %s' % db_folder_path
        return

    db = sqlite3.connect(db_path)
    g_cursor = db.cursor()

    if method.find('[') >= 0:
        method_name = get_res_from_objc_method(method)
    else:
        method_name = get_res_from_c_method(method)
    print_callhierarchy("", method_name)

    g_cursor.close()
    db.close()
    g_cursor = None

if __name__ == "__main__":
    main('-[KeyboardViewController viewDidLoad]')
