#!/usr/bin/env python

# Clone all of our SVN projects to git repos, then merge them into a "libraries" git repo.

import sys, os, shutil, subprocess, re, getopt, signal, shlex, functools
from collections import namedtuple

def call(cmd):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    return subprocess.call(args)
    
def readcall(cmd):
    print cmd
    args = shlex.split(cmd.encode('utf8'))
    return subprocess.check_output(args)
    
    
rootrepo = "file:///home/chrisknyfe/migration/localsvn"

remoterepos = [ "https://pl3.projectlocker.com/Vigilo/orion/svn",
                "https://equity3.projectlocker.com/Vigilo/orion/svn",
                ]

libraries= {
            "common":                   "/trunk/src/sensory/Libs/common/dev/common/",
            "dsdef_pkt":                "/trunk/src/sensory/Libs/dsdef_pkt/",
            "biosensor_algorithms":     "/trunk/src/sensory/Libs/biosensor_algorithms/dev/implementation/",
            "openssl":                  "/trunk/src/sensory/Libs/external/openssl/",
            "yajl":                     "/trunk/src/sensory/Libs/external/yajl/",
            "fw_bundle":                "/trunk/src/sensory/Libs/fw_bundle/dev/fw_bundle/",
            "rslib":                    "/trunk/src/sensory/Libs/rslib/dev/rslib/",
            "sensor_stream":            "/trunk/src/sensory/Libs/sensor_stream/dev/sensor_stream/",
            "ss_pkt_gen":               "/trunk/src/sensory/Libs/ss_pkt_gen/dev/ss_pkt_gen/",
            "store_forward":            "/trunk/src/sensory/Libs/store_forward/dev/",
            "vc_auth":                  "/trunk/src/sensory/Libs/vc_auth/dev/vc_auth/",
            "vc_cfg":                   "/trunk/src/sensory/Libs/vc_cfg/dev/",
            "vc_cmd":                   "/trunk/src/sensory/Libs/vc_cmd/dev/vc_cmd/",
            "vc_crypto":                "/trunk/src/sensory/Libs/vc_crypto/dev/vc_crypto/",
            "vc_decomp":                "/trunk/src/sensory/Libs/vc_decomp/",
            "vc_relay_core":            "/trunk/src/sensory/Libs/vc_relay_core/",
            "vc_sleep":                 "/trunk/src/sensory/Libs/vc_sleep/",
            "vc_slp":                   "/trunk/src/sensory/Libs/vc_slp/dev/vc_slp/",
            "vc_timer":                 "/trunk/src/sensory/Libs/vc_timer/dev/vc_timer/",
            "vcpp":                     "/trunk/src/sensory/Libs/vcpp/dev/vcpp/",
            "vcsensorstoolbox":         "/trunk/src/sensory/Tools/VCSensorsToolbox/",
            }
              
gitfilterprefix = os.path.abspath('git-filter-prefix.sh')
gitcherrysort = os.path.abspath('git-cherry-sort.sh')
gitusers = os.path.abspath('gitusers.txt')
converttogit = os.path.abspath('convert-to-git.py')

# Make a subfolder to contain all these wild shenanigans
if not os.path.exists('libraries_build'):
    os.mkdir('libraries_build')
os.chdir('libraries_build')
rootleveldir = os.getcwd()

# Make a "libraries" git repo that we'll fill with these libraries

librariesrepo = os.path.abspath('libraries')

if not os.path.exists(librariesrepo):
    os.mkdir(librariesrepo)
os.chdir(librariesrepo)
call("git init")
with open(".gitignore", 'a') as gitignore:
    gitignore.write("**/.svn/**\n")
call("git add .gitignore")
call("git commit -m 'Create libraries repo'")

for modname, url in libraries.iteritems():
    os.chdir(rootleveldir)
    dirname = os.path.abspath("cloned_" + modname)
    #retval = call("git svn clone -A %s %s %s" % (gitusers, rootrepo + url, dirname)))
    
    cmdstr = "%s --no-externals --root %s --repo %s --users %s" % (converttogit, rootrepo, url, gitusers)
    for remote in remoterepos:
        cmdstr += " --remote %s" % remote
    cmdstr += " %s" % dirname
    retval = call(cmdstr)
    exit()
    if retval != 0:
        raise RuntimeError("git svn clone error")
        
    os.chdir(dirname)
    retval = call("%s %s" % (gitfilterprefix, modname))
    if retval != 0:
        raise RuntimeError("git-filter-prefix error")
        
    os.chdir(librariesrepo)
    retval = call("git pull --no-edit %s" % (dirname))
    if retval != 0:
        raise RuntimeError("git pull error")
    
os.chdir(librariesrepo)
retval = call(gitcherrysort)
if retval != 0:
    raise RuntimeError("git-cherry-sort error")
        
        
