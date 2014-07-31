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
            "common":                   rootrepo + "/trunk/src/sensory/Libs/common/dev/common/ common_exp",
            "dsdef_pkt":                rootrepo + "/trunk/src/sensory/Libs/dsdef_pkt/ dsdef_pkt_exp",
            "biosensor_algorithms":     rootrepo + "/trunk/src/sensory/Libs/biosensor_algorithms/dev/implementation/ biosensor_algorithms_exp",
            "openssl":                  rootrepo + "/trunk/src/sensory/Libs/external/openssl/ openssl_exp",
            "yajl":                     rootrepo + "/trunk/src/sensory/Libs/external/yajl/ yajl_exp",
            "fw_bundle":                rootrepo + "/trunk/src/sensory/Libs/fw_bundle/dev/fw_bundle/ fw_bundle_exp",
            "rslib":                    rootrepo + "/trunk/src/sensory/Libs/rslib/dev/rslib/ rslib_exp",
            "sensor_stream":            rootrepo + "/trunk/src/sensory/Libs/sensor_stream/dev/sensor_stream/ sensor_stream_exp",
            "ss_pkt_gen":               rootrepo + "/trunk/src/sensory/Libs/ss_pkt_gen/dev/ss_pkt_gen/ ss_pkt_gen_exp",
            "store_forward":            rootrepo + "/svn/trunk/src/sensory/Libs/store_forward/dev/ store_forward_exp",
            "vc_auth":                  rootrepo + "/svn/trunk/src/sensory/Libs/vc_auth/dev/vc_auth/ vc_auth_exp",
            "vc_cfg":                   rootrepo + "/svn/trunk/src/sensory/Libs/vc_cfg/dev/ vc_cfg_exp",
            "vc_cmd":                   rootrepo + "/svn/trunk/src/sensory/Libs/vc_cmd/dev/vc_cmd/ vc_cmd_exp",
            "vc_crypto":                rootrepo + "/svn/trunk/src/sensory/Libs/vc_crypto/dev/vc_crypto/ vc_crypto_exp",
            "vc_decomp":                rootrepo + "/svn/trunk/src/sensory/Libs/vc_decomp/ vc_decomp_exp",
            "vc_relay_core":            rootrepo + "/svn/trunk/src/sensory/Libs/vc_relay_core/ vc_relay_core_exp",
            "vc_sleep":                 rootrepo + "/svn/trunk/src/sensory/Libs/vc_sleep/ vc_sleep_exp",
            "vc_slp":                   rootrepo + "/svn/trunk/src/sensory/Libs/vc_slp/dev/vc_slp/ vc_slp_exp",
            "vc_timer":                 rootrepo + "/svn/trunk/src/sensory/Libs/vc_timer/dev/vc_timer/ vc_timer_exp",
            "vcpp":                     rootrepo + "/svn/trunk/src/sensory/Libs/vcpp/dev/vcpp/ vcpp_exp",
            "vcsensorstoolbox":         rootrepo + "/svn/trunk/src/sensory/Tools/VCSensorsToolbox/ vcsensorstoolbox_exp",
            }
            
gitfilterprefix = os.path.abspath('git-filter-prefix.sh')
gitcherrysort = os.path.abspath('git-cherry-sort.sh')

if not os.path.exists('libraries_build'):
    os.mkdir('libraries_build')
os.chdir('libraries_build')
rootleveldir = os.getcwd()

print libraries
print gitfilterprefix
print gitcherrysort
print rootleveldir

exit()
for modname, url in libraries.iteritems():
    dirname = "cloned_" + modname
    retval = call("git svn clone -A gitusers.txt %s %s" % (url, dirname))
    if retval != 0:
        raise RuntimeError("git-svn error")
        
    os.chdir(dirname)
    retval = call("%s %s" % (gitfilterprefix, modname))
    if retval != 0:
        raise RuntimeError("git-filter-prefix error")
    os.chdir(rootleveldir)
    exit()
        
        
