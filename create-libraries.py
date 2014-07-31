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

libraries= {
            "common":                   rootrepo + "/trunk/src/sensory/Libs/common/dev/common/",
            "dsdef_pkt":                rootrepo + "/trunk/src/sensory/Libs/dsdef_pkt/",
            "biosensor_algorithms":     rootrepo + "/trunk/src/sensory/Libs/biosensor_algorithms/dev/implementation/",
            "openssl":                  rootrepo + "/trunk/src/sensory/Libs/external/openssl/",
            "yajl":                     rootrepo + "/trunk/src/sensory/Libs/external/yajl/",
            "fw_bundle":                rootrepo + "/trunk/src/sensory/Libs/fw_bundle/dev/fw_bundle/",
            "rslib":                    rootrepo + "/trunk/src/sensory/Libs/rslib/dev/rslib/",
            "sensor_stream":            rootrepo + "/trunk/src/sensory/Libs/sensor_stream/dev/sensor_stream/",
            "ss_pkt_gen":               rootrepo + "/trunk/src/sensory/Libs/ss_pkt_gen/dev/ss_pkt_gen/",
            "store_forward":            rootrepo + "/trunk/src/sensory/Libs/store_forward/dev/",
            "vc_auth":                  rootrepo + "/trunk/src/sensory/Libs/vc_auth/dev/vc_auth/",
            "vc_cfg":                   rootrepo + "/trunk/src/sensory/Libs/vc_cfg/dev/",
            "vc_cmd":                   rootrepo + "/trunk/src/sensory/Libs/vc_cmd/dev/vc_cmd/",
            "vc_crypto":                rootrepo + "/trunk/src/sensory/Libs/vc_crypto/dev/vc_crypto/",
            "vc_decomp":                rootrepo + "/trunk/src/sensory/Libs/vc_decomp/",
            "vc_relay_core":            rootrepo + "/trunk/src/sensory/Libs/vc_relay_core/",
            "vc_sleep":                 rootrepo + "/trunk/src/sensory/Libs/vc_sleep/",
            "vc_slp":                   rootrepo + "/trunk/src/sensory/Libs/vc_slp/dev/vc_slp/",
            "vc_timer":                 rootrepo + "/trunk/src/sensory/Libs/vc_timer/dev/vc_timer/",
            "vcpp":                     rootrepo + "/trunk/src/sensory/Libs/vcpp/dev/vcpp/",
            "vcsensorstoolbox":         rootrepo + "/trunk/src/sensory/Tools/VCSensorsToolbox/",
            }
              
gitfilterprefix = os.path.abspath('git-filter-prefix.sh')
gitcherrysort = os.path.abspath('git-cherry-sort.sh')
gitusers = os.path.abspath('gitusers.txt')

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
    retval = call("git svn clone -A %s %s %s" % (gitusers, url, dirname))
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
        
        
