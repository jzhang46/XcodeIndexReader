#!/usr/bin/python
#  -*- coding: UTF-8 -*-


import sys
import os.path
import sqlite3
from functools import partial
from StringIO import StringIO
import re
import findIndexForProject


#NOTE: Because this file was modified based on the caller.py, there are many function/variable names called caller, while in fact, in this context, it means callee

db_folder_path  = ""
db_file_name    = "db.xcindexdb"
sym_file_name   = "db.xcindexdb.strings-sym"
file_file_name  = "db.xcindexdb.strings-file"
dir_file_name   = "db.xcindexdb.strings-dir"
res_file_name   = "db.xcindexdb.strings-res"

file_name_to_content = {}
g_cursor = None
keyword_to_oc_func = {'im':'-', 'cm':'+'} #, 'py':'-prop'}
oc_func_to_keyword = {'-':'im', '+':'cm'}
g_method_to_set = {}

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

    sql = "SELECT r.resolution FROM reference r " \
          "JOIN symbol s ON s.id=r.container " \
          "WHERE s.resolution =?"
    query = g_cursor.execute(sql, (str(res_pos),))
    results = query.fetchall()
    for r in results:
        caller_res = get_string_from_pos_in_file(r[0], res_file_name)
        # caller_spelling = get_string_from_pos_in_file(r[1], sym_file_name)
        caller = caller_res
        callers.append(caller)
    callers.sort()
    return callers
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


def print_callhierarchy(prefix, parent_method_res, method_res):
    """Print call hierarchy, parent-child-child etc"""

    # parent_components = parent_method_res.split('##')
    # if method_res in parent_components:
    #     return

    if parent_method_res not in g_method_to_set:
        g_method_to_set[parent_method_res] = set()

    s = g_method_to_set[parent_method_res]
    if method_res in s:
        return

    s.add(method_res)
    g_method_to_set[parent_method_res] = s

    printable_name = get_objc_string_from_res(method_res)
    if not printable_name:
        return
    print prefix + printable_name

    callers = get_callers_for_resolution(method_res)
    if callers and len(callers) > 0:
        for caller in callers:
            print_callhierarchy(prefix + "\t", method_res, caller)



# Used for recording all {func, [direct children]} relations
g_parent_to_children = {}


def fetch_allmethods(parent_method_printable_name, method_res):
    """Print all parent-child relations, in one level"""

    if not parent_method_printable_name:
        return

    method_printable_name = get_objc_string_from_res(method_res)
    if not method_printable_name:
        return

    if parent_method_printable_name not in g_parent_to_children:
        g_parent_to_children[parent_method_printable_name] = set()
    s = g_parent_to_children[parent_method_printable_name]

    if method_printable_name in s:
        return

    s.add(method_printable_name)
    g_parent_to_children[parent_method_printable_name] = s

    callers = get_callers_for_resolution(method_res)
    if callers and len(callers) > 0:
        for caller in callers:
            fetch_allmethods(method_printable_name, caller)


def print_all_descendents(method_name):
        """ Print all descendents and its direct children """
        fetch_allmethods("root", method_name)
        for key in sorted(g_parent_to_children.iterkeys()):
            s = g_parent_to_children[key]
            if len(s) < 1 or key == "root":
                continue
            print "%s" % key
            for val in sorted(s):
                print "\t%s" % val


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
        print 'Format: python callee.py project_path [func_name]'
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

    # Print the call hierarchy
    # print_callhierarchy("", "root", method_name)

    # Print the descendents impl
    print_all_descendents(method_name)

    g_cursor.close()
    db.close()
    g_cursor = None

if __name__ == "__main__":
    main('-[KeyboardViewController viewDidLoad]')
