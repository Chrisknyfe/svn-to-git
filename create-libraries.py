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

def createlibraries(    rootrepo,
                        libraries,
                        remoterepos=[],
                        gitfilterprefix=None,
                        gitcherrysort=None,
                        gitusers=None,
                        converttogit=None ):
    if not gitfilterprefix:
        gitfilterprefix = os.path.abspath('git-filter-prefix.sh')
    if not gitcherrysort:
        gitcherrysort = os.path.abspath('git-cherry-sort.sh')
    if not gitusers:
        gitusers = os.path.abspath('gitusers.txt')
    if not converttogit:
        converttogit = os.path.abspath('convert-to-git.py')

    # Make a subfolder to contain all these wild shenanigans
    if not os.path.exists('libraries_build'):
        os.mkdir('libraries_build')
    os.chdir('libraries_build')
    rootleveldir = os.getcwd()

    for modname, url in libraries.iteritems():
        os.chdir(rootleveldir)
        dirname = os.path.abspath("export_" + modname)
        outputdirname = os.path.abspath("filtered_" + modname)
        
        # Export each library from the svn repo
        print "\n-- Exporting library %s --\n" % modname
        cmdstr = "%s --no-externals --root %s --repo %s --users %s" % (converttogit, rootrepo, url, gitusers)
        for remote in remoterepos:
            cmdstr += " --remote %s" % remote
        cmdstr += " %s" % dirname
        retval = call(cmdstr)
        if retval != 0:
            raise RuntimeError("convert-to-git error")
            
        # Copy the exported library somewhere else to be filtered.
        if os.path.exists(outputdirname):
            call("rm -rf %s" % outputdirname)
        call("cp -R %s %s" % (dirname, outputdirname))

        # Filter each library's commits into a subfolder
        print "\n-- Filtering library %s --\n" % modname
        os.chdir(outputdirname)
        retval = call("%s %s" % (gitfilterprefix, modname))
        if retval != 0:
            raise RuntimeError("git-filter-prefix error")
            
            
    # Make a "libraries" git repo that we'll fill with these libraries
    print "\n-- Creating \"libraries\" repo --\n"
    librariesrepo = os.path.abspath('libraries') 
    if os.path.exists(librariesrepo):
        call("rm -rf %s" % librariesrepo)
        
    os.mkdir(librariesrepo)
    os.chdir(librariesrepo)
    call("git init")
    with open(".gitignore", 'a') as gitignore:
        gitignore.write("**/.svn/**\n")
    call("git add .gitignore")
    call("git commit -m 'Create libraries repo'")

    # Pull each library
    for modname, url in libraries.iteritems():
        print "\n-- Pulling library %s --\n" % modname
        os.chdir(rootleveldir)
        dirname = os.path.abspath("filtered_" + modname)
        os.chdir(librariesrepo)
        retval = call("git pull --no-edit %s" % (dirname))
        if retval != 0:
            raise RuntimeError("git pull error")

    # Merge the git repo
    print "\n-- Sorting and Filtering \"libraries\" repo --\n"
    os.chdir(librariesrepo)
    retval = call(gitcherrysort)
    if retval != 0:
        raise RuntimeError("git-cherry-sort error")
        
if __name__ == '__main__':
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
                
    createlibraries(rootrepo, libraries, remoterepos=remoterepos)
            
        
